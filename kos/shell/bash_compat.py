"""
Bash and ZSH Compatibility Layer for KOS Shell
==============================================

Provides compatibility with bash and zsh features:
- Command completion
- History management
- Variable expansion
- Shell scripting features
- Built-in commands
- Job control
"""

import os
import sys
import re
import glob
import shlex
import subprocess
import threading
import signal
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from pathlib import Path
import readline
import atexit
import fnmatch

class BashVariables:
    """Bash-compatible variable management"""
    
    def __init__(self):
        self.variables = {}
        self.exported = set()
        self.readonly = set()
        
        # Initialize default variables
        self._init_default_vars()
    
    def _init_default_vars(self):
        """Initialize default bash variables"""
        self.variables.update({
            'BASH': '/bin/bash',
            'BASH_VERSION': '5.1.0(KOS-compat)',
            'HOME': os.path.expanduser('~'),
            'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
            'PWD': os.getcwd(),
            'OLDPWD': os.getcwd(),
            'USER': os.environ.get('USER', 'kos'),
            'SHELL': '/bin/kos-shell',
            'TERM': os.environ.get('TERM', 'xterm-256color'),
            'PS1': '\\u@\\h:\\w\\$ ',
            'PS2': '> ',
            'IFS': ' \t\n',
            'HISTFILE': os.path.expanduser('~/.kos_history'),
            'HISTSIZE': '1000',
            'HISTFILESIZE': '2000',
            'HOSTNAME': os.uname().nodename,
            'MACHTYPE': f"{os.uname().machine}-unknown-linux-gnu",
            'OSTYPE': 'linux-gnu',
            'PPID': str(os.getppid()),
            'UID': str(os.getuid()),
            'EUID': str(os.geteuid()),
            'GROUPS': ' '.join(str(gid) for gid in os.getgroups()),
            'SECONDS': '0',
            'RANDOM': '12345',
            'LINENO': '1',
            'BASHPID': str(os.getpid()),
        })
        
        # Export important variables
        self.exported.update(['PATH', 'HOME', 'USER', 'SHELL', 'TERM', 'PWD'])
    
    def get(self, name: str, default: str = "") -> str:
        """Get variable value"""
        return self.variables.get(name, default)
    
    def set(self, name: str, value: str, export: bool = False, readonly: bool = False):
        """Set variable value"""
        if name in self.readonly:
            raise ValueError(f"bash: {name}: readonly variable")
        
        self.variables[name] = value
        
        if export:
            self.exported.add(name)
        
        if readonly:
            self.readonly.add(name)
    
    def unset(self, name: str):
        """Unset variable"""
        if name in self.readonly:
            raise ValueError(f"bash: unset: {name}: cannot unset: readonly variable")
        
        self.variables.pop(name, None)
        self.exported.discard(name)
    
    def export(self, name: str):
        """Export variable"""
        if name in self.variables:
            self.exported.add(name)
    
    def get_exported(self) -> Dict[str, str]:
        """Get all exported variables"""
        return {name: value for name, value in self.variables.items() if name in self.exported}

class BashExpansion:
    """Bash-style parameter and command expansion"""
    
    def __init__(self, variables: BashVariables):
        self.variables = variables
    
    def expand(self, text: str) -> str:
        """Perform all bash expansions"""
        # Brace expansion
        text = self._brace_expansion(text)
        
        # Tilde expansion
        text = self._tilde_expansion(text)
        
        # Parameter expansion
        text = self._parameter_expansion(text)
        
        # Command substitution
        text = self._command_substitution(text)
        
        # Arithmetic expansion
        text = self._arithmetic_expansion(text)
        
        # Pathname expansion (globbing)
        return self._pathname_expansion(text)
    
    def _brace_expansion(self, text: str) -> str:
        """Brace expansion: {a,b,c} -> a b c"""
        # Simplified brace expansion
        brace_pattern = re.compile(r'\{([^{}]+)\}')
        
        def expand_braces(match):
            content = match.group(1)
            if ',' in content:
                items = [item.strip() for item in content.split(',')]
                return ' '.join(items)
            return match.group(0)
        
        return brace_pattern.sub(expand_braces, text)
    
    def _tilde_expansion(self, text: str) -> str:
        """Tilde expansion: ~ -> $HOME"""
        if text.startswith('~/'):
            return os.path.join(self.variables.get('HOME'), text[2:])
        elif text == '~':
            return self.variables.get('HOME')
        return text
    
    def _parameter_expansion(self, text: str) -> str:
        """Parameter expansion: $VAR, ${VAR}, etc."""
        # Simple $VAR expansion
        var_pattern = re.compile(r'\$(\w+)')
        text = var_pattern.sub(lambda m: self.variables.get(m.group(1), ''), text)
        
        # ${VAR} expansion
        brace_var_pattern = re.compile(r'\$\{(\w+)\}')
        text = brace_var_pattern.sub(lambda m: self.variables.get(m.group(1), ''), text)
        
        # ${VAR:-default} expansion
        default_pattern = re.compile(r'\$\{(\w+):-([^}]+)\}')
        def expand_default(match):
            var_name = match.group(1)
            default_val = match.group(2)
            return self.variables.get(var_name) or default_val
        text = default_pattern.sub(expand_default, text)
        
        # ${VAR:=default} expansion
        assign_pattern = re.compile(r'\$\{(\w+):=([^}]+)\}')
        def expand_assign(match):
            var_name = match.group(1)
            default_val = match.group(2)
            if not self.variables.get(var_name):
                self.variables.set(var_name, default_val)
            return self.variables.get(var_name, '')
        text = assign_pattern.sub(expand_assign, text)
        
        return text
    
    def _command_substitution(self, text: str) -> str:
        """Command substitution: $(command) and `command`"""
        # $(command) substitution
        cmd_pattern = re.compile(r'\$\(([^)]+)\)')
        
        def expand_command(match):
            command = match.group(1)
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return result.stdout.strip()
            except Exception:
                return ''
        
        text = cmd_pattern.sub(expand_command, text)
        
        # `command` substitution
        backtick_pattern = re.compile(r'`([^`]+)`')
        text = backtick_pattern.sub(expand_command, text)
        
        return text
    
    def _arithmetic_expansion(self, text: str) -> str:
        """Arithmetic expansion: $((expression))"""
        arith_pattern = re.compile(r'\$\(\(([^)]+)\)\)')
        
        def expand_arithmetic(match):
            expression = match.group(1)
            try:
                # Simple arithmetic evaluation
                # Replace variables
                for var_name, var_value in self.variables.variables.items():
                    if var_value.isdigit():
                        expression = expression.replace(var_name, var_value)
                
                # Evaluate safely (limited operators)
                allowed_chars = '0123456789+-*/%() '
                if all(c in allowed_chars for c in expression):
                    result = eval(expression)
                    return str(result)
            except Exception:
                pass
            return '0'
        
        return arith_pattern.sub(expand_arithmetic, text)
    
    def _pathname_expansion(self, text: str) -> str:
        """Pathname expansion (globbing): *.txt"""
        # Split by spaces but preserve quoted strings
        parts = shlex.split(text) if text else []
        expanded_parts = []
        
        for part in parts:
            if any(char in part for char in '*?[]'):
                # Perform globbing
                matches = glob.glob(part)
                if matches:
                    expanded_parts.extend(sorted(matches))
                else:
                    expanded_parts.append(part)  # No matches, keep original
            else:
                expanded_parts.append(part)
        
        return ' '.join(expanded_parts)

class BashCompletion:
    """Bash-style tab completion"""
    
    def __init__(self, shell):
        self.shell = shell
        self.completers = {}
        self._setup_readline()
    
    def _setup_readline(self):
        """Setup readline for completion"""
        try:
            readline.set_completer(self.complete)
            readline.parse_and_bind("tab: complete")
            readline.set_completer_delims(" \t\n`!@#$%^&*()=+[{]}\\|;:'\",<>?")
        except Exception:
            pass  # readline not available
    
    def complete(self, text: str, state: int) -> Optional[str]:
        """Main completion function"""
        try:
            line = readline.get_line_buffer()
            begin = readline.get_begidx()
            end = readline.get_endidx()
            
            # Get completion candidates
            candidates = self._get_completions(text, line, begin, end)
            
            if state < len(candidates):
                return candidates[state]
            else:
                return None
                
        except Exception:
            return None
    
    def _get_completions(self, text: str, line: str, begin: int, end: int) -> List[str]:
        """Get completion candidates"""
        words = line[:begin].split()
        
        if not words or begin == 0 or line[:begin].isspace():
            # Complete command names
            return self._complete_commands(text)
        else:
            # Complete filenames/paths
            return self._complete_filenames(text)
    
    def _complete_commands(self, text: str) -> List[str]:
        """Complete command names"""
        candidates = []
        
        # Built-in commands
        if hasattr(self.shell, 'commands'):
            for cmd in self.shell.commands:
                if cmd.startswith(text):
                    candidates.append(cmd)
        
        # PATH commands
        path_dirs = os.environ.get('PATH', '').split(':')
        for path_dir in path_dirs:
            try:
                if os.path.isdir(path_dir):
                    for filename in os.listdir(path_dir):
                        filepath = os.path.join(path_dir, filename)
                        if (os.path.isfile(filepath) and 
                            os.access(filepath, os.X_OK) and 
                            filename.startswith(text)):
                            candidates.append(filename)
            except OSError:
                continue
        
        return sorted(list(set(candidates)))
    
    def _complete_filenames(self, text: str) -> List[str]:
        """Complete filenames and paths"""
        if not text:
            text = '.'
        
        # Handle ~ expansion
        if text.startswith('~'):
            text = os.path.expanduser(text)
        
        dirname, basename = os.path.split(text)
        if not dirname:
            dirname = '.'
        
        try:
            candidates = []
            for item in os.listdir(dirname):
                if item.startswith(basename):
                    full_path = os.path.join(dirname, item)
                    if os.path.isdir(full_path):
                        candidates.append(item + '/')
                    else:
                        candidates.append(item)
            
            return sorted(candidates)
        except OSError:
            return []

class BashHistory:
    """Bash-style command history"""
    
    def __init__(self, variables: BashVariables):
        self.variables = variables
        self.history = []
        self.history_file = variables.get('HISTFILE')
        self.max_size = int(variables.get('HISTSIZE', '1000'))
        self.max_file_size = int(variables.get('HISTFILESIZE', '2000'))
        
        self._load_history()
        self._setup_readline()
        atexit.register(self._save_history)
    
    def _setup_readline(self):
        """Setup readline for history"""
        try:
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
            readline.set_history_length(self.max_size)
        except Exception:
            pass
    
    def _load_history(self):
        """Load history from file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.history = [line.strip() for line in f.readlines()]
        except Exception:
            pass
    
    def _save_history(self):
        """Save history to file"""
        try:
            # Limit history size
            if len(self.history) > self.max_file_size:
                self.history = self.history[-self.max_file_size:]
            
            with open(self.history_file, 'w') as f:
                for line in self.history:
                    f.write(line + '\n')
            
            # Update readline history
            readline.write_history_file(self.history_file)
        except Exception:
            pass
    
    def add(self, command: str):
        """Add command to history"""
        if command and command != self.history[-1:]:
            self.history.append(command)
            if len(self.history) > self.max_size:
                self.history.pop(0)
            
            try:
                readline.add_history(command)
            except Exception:
                pass
    
    def get_history(self) -> List[str]:
        """Get command history"""
        return self.history.copy()

class JobControl:
    """Bash-style job control"""
    
    def __init__(self):
        self.jobs = {}
        self.job_counter = 0
        self.current_job = None
        self.previous_job = None
    
    def add_job(self, command: str, process: subprocess.Popen, background: bool = False) -> int:
        """Add a job"""
        self.job_counter += 1
        job_id = self.job_counter
        
        self.jobs[job_id] = {
            'id': job_id,
            'command': command,
            'process': process,
            'background': background,
            'status': 'Running',
            'pid': process.pid
        }
        
        if not background:
            self.current_job = job_id
        
        return job_id
    
    def remove_job(self, job_id: int):
        """Remove a job"""
        if job_id in self.jobs:
            del self.jobs[job_id]
            if self.current_job == job_id:
                self.current_job = None
    
    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs"""
        # Update job statuses
        for job in self.jobs.values():
            if job['process'].poll() is not None:
                job['status'] = 'Done' if job['process'].returncode == 0 else 'Exit'
        
        return list(self.jobs.values())
    
    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def fg_job(self, job_id: int = None) -> bool:
        """Bring job to foreground"""
        if job_id is None:
            job_id = self.current_job
        
        if job_id and job_id in self.jobs:
            job = self.jobs[job_id]
            try:
                # Send SIGCONT if stopped
                job['process'].send_signal(signal.SIGCONT)
                # Wait for completion
                job['process'].wait()
                job['status'] = 'Done' if job['process'].returncode == 0 else 'Exit'
                return True
            except Exception:
                return False
        
        return False
    
    def bg_job(self, job_id: int = None) -> bool:
        """Send job to background"""
        if job_id is None:
            job_id = self.current_job
        
        if job_id and job_id in self.jobs:
            job = self.jobs[job_id]
            try:
                # Send SIGCONT
                job['process'].send_signal(signal.SIGCONT)
                job['background'] = True
                job['status'] = 'Running'
                return True
            except Exception:
                return False
        
        return False

class BashCompatShell:
    """Bash-compatible shell interface"""
    
    def __init__(self, original_shell):
        self.original_shell = original_shell
        self.variables = BashVariables()
        self.expansion = BashExpansion(self.variables)
        self.completion = BashCompletion(self)
        self.history = BashHistory(self.variables)
        self.job_control = JobControl()
        
        # Shell options
        self.options = {
            'errexit': False,    # -e
            'nounset': False,    # -u
            'pipefail': False,   # pipefail
            'xtrace': False,     # -x
            'verbose': False,    # -v
        }
        
        # Add bash built-ins
        self._register_bash_builtins()
    
    def _register_bash_builtins(self):
        """Register bash built-in commands"""
        builtins = {
            'export': self._builtin_export,
            'unset': self._builtin_unset,
            'set': self._builtin_set,
            'declare': self._builtin_declare,
            'readonly': self._builtin_readonly,
            'local': self._builtin_local,
            'source': self._builtin_source,
            'alias': self._builtin_alias,
            'unalias': self._builtin_unalias,
            'history': self._builtin_history,
            'jobs': self._builtin_jobs,
            'fg': self._builtin_fg,
            'bg': self._builtin_bg,
            'kill': self._builtin_kill,
            'test': self._builtin_test,
            '[': self._builtin_test,
            'echo': self._builtin_echo,
            'printf': self._builtin_printf,
            'read': self._builtin_read,
            'shift': self._builtin_shift,
            'exit': self._builtin_exit,
            'return': self._builtin_return,
        }
        
        # Register with original shell
        if hasattr(self.original_shell, 'register_command'):
            for name, func in builtins.items():
                self.original_shell.register_command(name, func)
    
    def process_command(self, command_line: str) -> Tuple[bool, str]:
        """Process command line with bash compatibility"""
        if not command_line.strip():
            return True, ""
        
        # Add to history
        self.history.add(command_line)
        
        # Handle background jobs
        background = command_line.strip().endswith('&')
        if background:
            command_line = command_line.strip()[:-1].strip()
        
        # Expand command line
        try:
            expanded = self.expansion.expand(command_line)
        except Exception as e:
            return False, f"bash: expansion error: {e}"
        
        # Parse command
        try:
            args = shlex.split(expanded)
        except ValueError as e:
            return False, f"bash: parse error: {e}"
        
        if not args:
            return True, ""
        
        command = args[0]
        command_args = args[1:]
        
        # Execute command
        return self._execute_command(command, command_args, background)
    
    def _execute_command(self, command: str, args: List[str], background: bool = False) -> Tuple[bool, str]:
        """Execute a command"""
        # Check if it's a built-in
        if hasattr(self.original_shell, 'commands') and command in self.original_shell.commands:
            try:
                result = self.original_shell.commands[command](args)
                return True, ""
            except Exception as e:
                return False, str(e)
        
        # External command
        try:
            full_args = [command] + args
            process = subprocess.Popen(
                full_args,
                stdout=subprocess.PIPE if background else None,
                stderr=subprocess.PIPE if background else None,
                text=True,
                env=self.variables.get_exported()
            )
            
            if background:
                job_id = self.job_control.add_job(' '.join(full_args), process, True)
                return True, f"[{job_id}] {process.pid}"
            else:
                process.wait()
                return process.returncode == 0, ""
                
        except FileNotFoundError:
            return False, f"bash: {command}: command not found"
        except Exception as e:
            return False, f"bash: {command}: {e}"
    
    # Built-in command implementations
    def _builtin_export(self, args: List[str]) -> bool:
        """export built-in"""
        if not args:
            # List exported variables
            for name in sorted(self.variables.exported):
                value = self.variables.get(name)
                print(f"declare -x {name}=\"{value}\"")
            return True
        
        for arg in args:
            if '=' in arg:
                name, value = arg.split('=', 1)
                self.variables.set(name, value, export=True)
            else:
                self.variables.export(arg)
        
        return True
    
    def _builtin_unset(self, args: List[str]) -> bool:
        """unset built-in"""
        for name in args:
            try:
                self.variables.unset(name)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return False
        return True
    
    def _builtin_set(self, args: List[str]) -> bool:
        """set built-in"""
        if not args:
            # List all variables
            for name, value in sorted(self.variables.variables.items()):
                print(f"{name}={value}")
            return True
        
        # Process options
        for arg in args:
            if arg.startswith('-'):
                options = arg[1:]
                for opt in options:
                    if opt == 'e':
                        self.options['errexit'] = True
                    elif opt == 'u':
                        self.options['nounset'] = True
                    elif opt == 'x':
                        self.options['xtrace'] = True
                    elif opt == 'v':
                        self.options['verbose'] = True
            elif arg.startswith('+'):
                options = arg[1:]
                for opt in options:
                    if opt == 'e':
                        self.options['errexit'] = False
                    elif opt == 'u':
                        self.options['nounset'] = False
                    elif opt == 'x':
                        self.options['xtrace'] = False
                    elif opt == 'v':
                        self.options['verbose'] = False
        
        return True
    
    def _builtin_declare(self, args: List[str]) -> bool:
        """declare built-in"""
        # Simplified declare implementation
        for arg in args:
            if '=' in arg:
                name, value = arg.split('=', 1)
                self.variables.set(name, value)
            else:
                value = self.variables.get(arg)
                print(f"declare -- {arg}=\"{value}\"")
        return True
    
    def _builtin_readonly(self, args: List[str]) -> bool:
        """readonly built-in"""
        for arg in args:
            if '=' in arg:
                name, value = arg.split('=', 1)
                self.variables.set(name, value, readonly=True)
            else:
                try:
                    self.variables.readonly.add(arg)
                except ValueError:
                    pass
        return True
    
    def _builtin_local(self, args: List[str]) -> bool:
        """local built-in (simplified)"""
        # In a real implementation, this would handle function-local variables
        return self._builtin_declare(args)
    
    def _builtin_source(self, args: List[str]) -> bool:
        """source built-in"""
        if not args:
            print("source: filename argument required", file=sys.stderr)
            return False
        
        filename = args[0]
        try:
            with open(filename, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.process_command(line)
            return True
        except Exception as e:
            print(f"source: {filename}: {e}", file=sys.stderr)
            return False
    
    def _builtin_alias(self, args: List[str]) -> bool:
        """alias built-in (placeholder)"""
        print("alias: not implemented", file=sys.stderr)
        return False
    
    def _builtin_unalias(self, args: List[str]) -> bool:
        """unalias built-in (placeholder)"""
        print("unalias: not implemented", file=sys.stderr)
        return False
    
    def _builtin_history(self, args: List[str]) -> bool:
        """history built-in"""
        history = self.history.get_history()
        for i, cmd in enumerate(history, 1):
            print(f"{i:5d}  {cmd}")
        return True
    
    def _builtin_jobs(self, args: List[str]) -> bool:
        """jobs built-in"""
        jobs = self.job_control.list_jobs()
        for job in jobs:
            status_char = '+' if job['id'] == self.job_control.current_job else '-'
            print(f"[{job['id']}]{status_char}  {job['status']:<12} {job['command']}")
        return True
    
    def _builtin_fg(self, args: List[str]) -> bool:
        """fg built-in"""
        job_id = None
        if args:
            try:
                job_id = int(args[0])
            except ValueError:
                print("fg: invalid job number", file=sys.stderr)
                return False
        
        return self.job_control.fg_job(job_id)
    
    def _builtin_bg(self, args: List[str]) -> bool:
        """bg built-in"""
        job_id = None
        if args:
            try:
                job_id = int(args[0])
            except ValueError:
                print("bg: invalid job number", file=sys.stderr)
                return False
        
        return self.job_control.bg_job(job_id)
    
    def _builtin_kill(self, args: List[str]) -> bool:
        """kill built-in"""
        if not args:
            print("kill: usage: kill [-s sigspec | -n signum | -sigspec] pid | jobspec", file=sys.stderr)
            return False
        
        sig = signal.SIGTERM
        targets = args
        
        # Parse signal option
        if args[0].startswith('-'):
            sig_arg = args[0][1:]
            if sig_arg.isdigit():
                sig = int(sig_arg)
            else:
                sig = getattr(signal, f'SIG{sig_arg.upper()}', signal.SIGTERM)
            targets = args[1:]
        
        for target in targets:
            try:
                if target.startswith('%'):
                    # Job specification
                    job_id = int(target[1:])
                    job = self.job_control.get_job(job_id)
                    if job:
                        os.kill(job['pid'], sig)
                else:
                    # PID
                    pid = int(target)
                    os.kill(pid, sig)
            except (ValueError, OSError) as e:
                print(f"kill: {target}: {e}", file=sys.stderr)
                return False
        
        return True
    
    def _builtin_test(self, args: List[str]) -> bool:
        """test built-in"""
        # Simplified test implementation
        if not args:
            return False
        
        # Handle [ ... ] syntax
        if args[0] == '[' and args[-1] == ']':
            args = args[1:-1]
        
        if len(args) == 1:
            # Test if string is non-empty
            return bool(args[0])
        elif len(args) == 2:
            operator, operand = args
            if operator == '-f':
                return os.path.isfile(operand)
            elif operator == '-d':
                return os.path.isdir(operand)
            elif operator == '-e':
                return os.path.exists(operand)
            elif operator == '-r':
                return os.access(operand, os.R_OK)
            elif operator == '-w':
                return os.access(operand, os.W_OK)
            elif operator == '-x':
                return os.access(operand, os.X_OK)
        elif len(args) == 3:
            left, operator, right = args
            if operator == '=':
                return left == right
            elif operator == '!=':
                return left != right
            elif operator == '-eq':
                return int(left) == int(right)
            elif operator == '-ne':
                return int(left) != int(right)
            elif operator == '-lt':
                return int(left) < int(right)
            elif operator == '-le':
                return int(left) <= int(right)
            elif operator == '-gt':
                return int(left) > int(right)
            elif operator == '-ge':
                return int(left) >= int(right)
        
        return False
    
    def _builtin_echo(self, args: List[str]) -> bool:
        """echo built-in"""
        output = ' '.join(args)
        
        # Handle escape sequences (simplified)
        output = output.replace('\\n', '\n')
        output = output.replace('\\t', '\t')
        output = output.replace('\\\\', '\\')
        
        print(output)
        return True
    
    def _builtin_printf(self, args: List[str]) -> bool:
        """printf built-in"""
        if not args:
            return True
        
        format_str = args[0]
        values = args[1:]
        
        try:
            # Simple printf implementation
            output = format_str % tuple(values) if values else format_str
            print(output, end='')
            return True
        except Exception as e:
            print(f"printf: {e}", file=sys.stderr)
            return False
    
    def _builtin_read(self, args: List[str]) -> bool:
        """read built-in"""
        var_name = args[0] if args else 'REPLY'
        
        try:
            value = input()
            self.variables.set(var_name, value)
            return True
        except EOFError:
            return False
    
    def _builtin_shift(self, args: List[str]) -> bool:
        """shift built-in (placeholder)"""
        # Would shift positional parameters
        return True
    
    def _builtin_exit(self, args: List[str]) -> bool:
        """exit built-in"""
        code = 0
        if args:
            try:
                code = int(args[0])
            except ValueError:
                code = 1
        
        sys.exit(code)
    
    def _builtin_return(self, args: List[str]) -> bool:
        """return built-in (placeholder)"""
        # Would return from function
        return True

def enable_bash_compatibility(shell):
    """Enable bash compatibility for a shell"""
    bash_shell = BashCompatShell(shell)
    
    # Replace shell's command processing
    original_onecmd = shell.onecmd
    
    def bash_onecmd(line):
        if line.strip():
            success, output = bash_shell.process_command(line)
            if output:
                print(output)
            return not success  # Return True to exit shell
        return original_onecmd(line)
    
    shell.onecmd = bash_onecmd
    shell.bash_compat = bash_shell
    
    return bash_shell

__all__ = ['BashCompatShell', 'enable_bash_compatibility']
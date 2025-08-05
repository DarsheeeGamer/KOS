"""
Advanced Shell Emulation for KOS
================================

Provides proper BASH, ZSH, and SOURCE command implementations
with realistic shell functionality and script execution capabilities.
"""

import os
import sys
import subprocess
import tempfile
import logging
from typing import List, Dict, Any, Optional
import shlex
import json
from pathlib import Path

logger = logging.getLogger('KOS.shell.shell_emulation')

class ShellEnvironment:
    """Manages shell environment variables and state"""
    
    def __init__(self):
        self.variables = {}
        self.aliases = {}
        self.functions = {}
        self.history = []
        
    def set_variable(self, name: str, value: str):
        """Set environment variable"""
        self.variables[name] = value
        os.environ[name] = value
        
    def get_variable(self, name: str) -> Optional[str]:
        """Get environment variable"""
        return self.variables.get(name) or os.environ.get(name)
    
    def expand_variables(self, text: str) -> str:
        """Expand variables in text (basic $VAR expansion)"""
        result = text
        for var_name, var_value in self.variables.items():
            result = result.replace(f"${var_name}", var_value)
            result = result.replace(f"${{{var_name}}}", var_value)
        return result

class BashEmulator:
    """BASH shell emulator with script execution"""
    
    def __init__(self, shell_instance):
        self.shell = shell_instance
        self.env = ShellEnvironment()
        self.interactive = True
        
    def execute_command(self, command: str) -> bool:
        """Execute a bash command"""
        try:
            # Handle built-in commands
            if command.startswith('cd '):
                path = command[3:].strip()
                return self._builtin_cd(path)
            elif command.startswith('export '):
                return self._builtin_export(command[7:])
            elif command.startswith('echo '):
                return self._builtin_echo(command[5:])
            elif command == 'pwd':
                return self._builtin_pwd()
            elif command.startswith('alias '):
                return self._builtin_alias(command[6:])
            elif command in ['exit', 'logout']:
                return self._builtin_exit()
            else:
                # Try to execute as KOS command
                return self.shell.onecmd(command)
                
        except Exception as e:
            print(f"bash: {command}: {e}")
            return False
    
    def _builtin_cd(self, path: str) -> bool:
        """Built-in cd command"""
        try:
            if not path or path == '~':
                path = os.path.expanduser('~')
            elif path == '-':
                path = self.env.get_variable('OLDPWD') or os.getcwd()
            
            old_pwd = os.getcwd()
            os.chdir(os.path.expanduser(path))
            self.env.set_variable('OLDPWD', old_pwd)
            self.env.set_variable('PWD', os.getcwd())
            return True
        except Exception as e:
            print(f"bash: cd: {path}: {e}")
            return False
    
    def _builtin_export(self, assignment: str) -> bool:
        """Built-in export command"""
        try:
            if '=' in assignment:
                name, value = assignment.split('=', 1)
                self.env.set_variable(name, value)
                print(f"Exported {name}={value}")
            else:
                # Show exported variables
                for name, value in self.env.variables.items():
                    print(f"export {name}={value}")
            return True
        except Exception as e:
            print(f"bash: export: {e}")
            return False
    
    def _builtin_echo(self, args: str) -> bool:
        """Built-in echo command"""
        try:
            expanded = self.env.expand_variables(args)
            print(expanded)
            return True
        except Exception as e:
            print(f"bash: echo: {e}")
            return False
    
    def _builtin_pwd(self) -> bool:
        """Built-in pwd command"""
        print(os.getcwd())
        return True
    
    def _builtin_alias(self, args: str) -> bool:
        """Built-in alias command"""
        try:
            if '=' in args:
                name, command = args.split('=', 1)
                self.env.aliases[name] = command.strip('\'"')
                print(f"alias {name}='{command}'")
            else:
                # Show aliases
                for name, command in self.env.aliases.items():
                    print(f"alias {name}='{command}'")
            return True
        except Exception as e:
            print(f"bash: alias: {e}")
            return False
    
    def _builtin_exit(self) -> bool:
        """Built-in exit command"""
        print("exit")
        return self.shell.onecmd("quit")
    
    def run_script(self, script_path: str) -> bool:
        """Execute a bash script"""
        try:
            if not os.path.exists(script_path):
                print(f"bash: {script_path}: No such file or directory")
                return False
            
            print(f"Executing bash script: {script_path}")
            
            with open(script_path, 'r') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                print(f"[{line_num}] {line}")
                if not self.execute_command(line):
                    print(f"bash: script failed at line {line_num}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"bash: error executing script {script_path}: {e}")
            return False

class ZshEmulator:
    """ZSH shell emulator"""
    
    def __init__(self, shell_instance):
        self.shell = shell_instance
        self.env = ShellEnvironment()
        
    def run_interactive(self):
        """Run interactive ZSH session"""
        print("KOS ZSH Emulator v5.8")
        print("Type 'exit' to return to KOS shell")
        print()
        
        while True:
            try:
                prompt = f"kos-zsh% "
                command = input(prompt).strip()
                
                if not command:
                    continue
                    
                if command in ['exit', 'logout']:
                    break
                    
                # Execute command
                self.execute_command(command)
                
            except KeyboardInterrupt:
                print("^C")
                continue
            except EOFError:
                break
        
        print("Exiting ZSH emulator")
    
    def execute_command(self, command: str) -> bool:
        """Execute ZSH command"""
        # ZSH-specific features
        if command.startswith('autoload '):
            print(f"zsh: autoload {command[9:]}")
            return True
        elif command.startswith('compinit'):
            print("zsh: completion system initialized")
            return True
        else:
            # Use bash emulator for common commands
            bash_emu = BashEmulator(self.shell)
            return bash_emu.execute_command(command)

class SourceCommand:
    """SOURCE command implementation"""
    
    def __init__(self, shell_instance):
        self.shell = shell_instance
        self.env = ShellEnvironment()
    
    def source_file(self, file_path: str) -> bool:
        """Source a script file"""
        try:
            if not os.path.exists(file_path):
                print(f"source: {file_path}: No such file or directory")
                return False
            
            print(f"Sourcing: {file_path}")
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Execute line by line
            lines = content.split('\n')
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # Handle variable assignments
                if '=' in line and not line.startswith('if ') and not line.startswith('for '):
                    self._handle_assignment(line)
                # Handle export statements
                elif line.startswith('export '):
                    self._handle_export(line[7:])
                # Handle alias statements
                elif line.startswith('alias '):
                    self._handle_alias(line[6:])
                # Handle other commands
                else:
                    try:
                        bash_emu = BashEmulator(self.shell)
                        bash_emu.execute_command(line)
                    except Exception as e:
                        print(f"source: error at line {line_num}: {e}")
            
            print(f"Successfully sourced {file_path}")
            return True
            
        except Exception as e:
            print(f"source: error reading {file_path}: {e}")
            return False
    
    def _handle_assignment(self, line: str):
        """Handle variable assignment"""
        try:
            if '=' in line:
                name, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('\'"')
                self.env.set_variable(name, value)
                print(f"Set {name}={value}")
        except Exception as e:
            print(f"source: invalid assignment: {line}")
    
    def _handle_export(self, line: str):
        """Handle export statement"""
        try:
            if '=' in line:
                name, value = line.split('=', 1)
                value = value.strip('\'"')
                self.env.set_variable(name, value)
                print(f"Exported {name}={value}")
        except Exception as e:
            print(f"source: invalid export: {line}")
    
    def _handle_alias(self, line: str):
        """Handle alias statement"""
        try:
            if '=' in line:
                name, command = line.split('=', 1)
                command = command.strip('\'"')
                self.env.aliases[name] = command
                print(f"Created alias {name}='{command}'")
        except Exception as e:
            print(f"source: invalid alias: {line}")

def register_commands(shell):
    """Register shell emulation commands with the shell"""
    
    def bash_command(shell_instance, args):
        """Enhanced BASH shell emulator"""
        bash_emu = BashEmulator(shell_instance)
        
        if not args:
            # Interactive bash mode
            print("KOS BASH Emulator v5.1.16")
            print("GNU bash, version 5.1.16(1)-release (x86_64-kos-linux-gnu)")
            print("Type 'help' for KOS commands, 'exit' to return to KOS shell")
            print()
            
            # Set initial environment
            bash_emu.env.set_variable('SHELL', '/bin/kos-bash')
            bash_emu.env.set_variable('BASH_VERSION', '5.1.16(1)-release')
            bash_emu.env.set_variable('PS1', 'bash-5.1$ ')
            
            # Interactive loop
            while True:
                try:
                    prompt = "bash-5.1$ "
                    command = input(prompt).strip()
                    
                    if not command:
                        continue
                        
                    if command in ['exit', 'logout']:
                        break
                        
                    bash_emu.execute_command(command)
                    
                except KeyboardInterrupt:
                    print("^C")
                    continue
                except EOFError:
                    break
            
            print("Exiting BASH emulator")
            return True
        else:
            # Execute bash script or command
            args_list = shlex.split(args)
            
            if args_list[0] == '-c':
                # Execute command
                if len(args_list) > 1:
                    command = ' '.join(args_list[1:])
                    return bash_emu.execute_command(command)
                else:
                    print("bash: -c: option requires an argument")
                    return False
            else:
                # Execute script file
                script_path = args_list[0]
                return bash_emu.run_script(script_path)
    
    def zsh_command(shell_instance, args):
        """ZSH shell emulator"""
        if not args:
            # Interactive ZSH
            zsh_emu = ZshEmulator(shell_instance)
            zsh_emu.run_interactive()
            return True
        else:
            # Execute ZSH script
            print(f"Executing ZSH script: {args}")
            zsh_emu = ZshEmulator(shell_instance)
            return zsh_emu.execute_command(args)
    
    def source_command(shell_instance, args):
        """Enhanced SOURCE command"""
        if not args:
            print("Usage: source filename [arguments]")
            print("   or: . filename [arguments]")
            print()
            print("Execute commands from filename in the current shell.")
            return True
        
        # Parse arguments
        args_list = shlex.split(args) if args else []
        if not args_list:
            print("source: filename argument required")
            return False
        
        file_path = args_list[0]
        source_cmd = SourceCommand(shell_instance)
        return source_cmd.source_file(file_path)
    
    def dot_command(shell_instance, args):
        """Dot command (. filename) - alias for source"""
        return source_command(shell_instance, args)
    
    def sh_command(shell_instance, args):
        """Enhanced SH shell command"""
        if not args:
            print("KOS Shell (POSIX sh compatibility)")
            print("This is the KOS native shell with POSIX sh features.")
            print("Type 'exit' to return to normal KOS shell")
            return True
        else:
            # Execute as bash script for compatibility
            bash_emu = BashEmulator(shell_instance)
            args_list = shlex.split(args)
            
            if args_list[0] == '-c':
                if len(args_list) > 1:
                    command = ' '.join(args_list[1:])
                    return bash_emu.execute_command(command)
                else:
                    print("sh: -c: option requires an argument")
                    return False
            else:
                script_path = args_list[0]
                return bash_emu.run_script(script_path)
    
    def env_enhanced_command(shell_instance, args):
        """Enhanced environment command"""
        if not args:
            # Show all environment variables
            print("KOS Environment Variables:")
            print("=" * 50)
            for key, value in sorted(os.environ.items()):
                print(f"{key}={value}")
            return True
        
        args_list = shlex.split(args)
        
        # Handle variable assignments
        env_vars = {}
        command_start = 0
        
        for i, arg in enumerate(args_list):
            if '=' in arg:
                name, value = arg.split('=', 1)
                env_vars[name] = value
                command_start = i + 1
            else:
                break
        
        if command_start < len(args_list):
            # Execute command with modified environment
            command = ' '.join(args_list[command_start:])
            
            # Save current environment
            old_env = {}
            for name, value in env_vars.items():
                old_env[name] = os.environ.get(name)
                os.environ[name] = value
            
            try:
                # Execute command
                result = shell_instance.onecmd(command)
                
                # Restore environment
                for name, old_value in old_env.items():
                    if old_value is None:
                        if name in os.environ:
                            del os.environ[name]
                    else:
                        os.environ[name] = old_value
                
                return result
            except Exception as e:
                print(f"env: error executing command: {e}")
                return False
        else:
            # Just set environment variables
            for name, value in env_vars.items():
                os.environ[name] = value
                print(f"Set {name}={value}")
            return True
    
    # Register all enhanced shell commands
    shell_commands = {
        'bash': (bash_command, "BASH shell emulator with script execution"),
        'zsh': (zsh_command, "ZSH shell emulator"),
        'source': (source_command, "Execute commands from file in current shell"),
        '.': (dot_command, "Execute commands from file (source alias)"),
        'sh': (sh_command, "POSIX shell compatibility"),
        'env': (env_enhanced_command, "Enhanced environment variable management"),
    }
    
    for cmd_name, (cmd_func, cmd_help) in shell_commands.items():
        shell.register_command(cmd_name, cmd_func, cmd_help)
    
    logger.info(f"Registered {len(shell_commands)} enhanced shell emulation commands")

__all__ = ['register_commands']
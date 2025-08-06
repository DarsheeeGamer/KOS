"""
Process and script execution commands for KOS Shell
"""

import types
import os
import time
from typing import Optional

def register_commands(shell):
    """Register process commands with shell"""
    
    def do_sh(self, arg):
        """Execute a shell script
        Usage: sh <script_file> [args...]"""
        if not arg:
            print("Usage: sh <script_file> [args...]")
            return
        
        args = arg.split()
        script_file = args[0]
        script_args = args[1:] if len(args) > 1 else []
        
        # Resolve path
        if not script_file.startswith('/'):
            script_file = os.path.join(self.cwd, script_file)
            script_file = os.path.normpath(script_file)
        
        # Read script
        if not self.vfs or not self.vfs.exists(script_file):
            print(f"sh: {script_file}: No such file")
            return
        
        if self.vfs.isdir(script_file):
            print(f"sh: {script_file}: Is a directory")
            return
        
        try:
            with self.vfs.open(script_file, 'r') as f:
                script_content = f.read().decode()
        except Exception as e:
            print(f"sh: Error reading {script_file}: {e}")
            return
        
        # Execute script
        if not hasattr(self, 'script_interpreter'):
            from kos.core.executor import ScriptInterpreter, ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
            self.script_interpreter = ScriptInterpreter(self.executor, self)
        
        exit_code = self.script_interpreter.execute_script(script_content, script_args)
        
        # Store exit code for $?
        self.last_exit_code = exit_code
    
    def do_bash(self, arg):
        """Alias for sh command"""
        self.do_sh(arg)
    
    def do_source(self, arg):
        """Execute commands from a file in current shell
        Usage: source <script_file>"""
        if not arg:
            print("Usage: source <script_file>")
            return
        
        script_file = arg.strip()
        
        # Resolve path
        if not script_file.startswith('/'):
            script_file = os.path.join(self.cwd, script_file)
            script_file = os.path.normpath(script_file)
        
        # Read script
        if not self.vfs or not self.vfs.exists(script_file):
            print(f"source: {script_file}: No such file")
            return
        
        try:
            with self.vfs.open(script_file, 'r') as f:
                script_content = f.read().decode()
        except Exception as e:
            print(f"source: Error reading {script_file}: {e}")
            return
        
        # Execute each line as a command
        for line in script_content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                self.onecmd(line)
    
    def do_exec(self, arg):
        """Execute a command
        Usage: exec <command>"""
        if not arg:
            print("Usage: exec <command>")
            return
        
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        # Execute command
        exit_code = self.executor.execute(arg)
        self.last_exit_code = exit_code
    
    def do_ps(self, arg):
        """List running processes
        Usage: ps [options]"""
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        processes = self.executor.list_processes()
        
        # Display processes
        print(f"{'PID':<8} {'PPID':<8} {'USER':<10} {'STATE':<12} {'TIME':<10} COMMAND")
        print("-" * 70)
        
        for proc in processes:
            runtime = f"{proc.runtime:.1f}s"
            ppid = proc.parent_pid if proc.parent_pid else 0
            print(f"{proc.pid:<8} {ppid:<8} {proc.user:<10} "
                  f"{proc.state.value:<12} {runtime:<10} {proc.command}")
    
    def do_kill(self, arg):
        """Terminate a process
        Usage: kill [-signal] <pid>"""
        if not arg:
            print("Usage: kill [-signal] <pid>")
            return
        
        args = arg.split()
        signal = 15  # SIGTERM
        
        # Parse signal if provided
        if args[0].startswith('-'):
            try:
                signal = int(args[0][1:])
                args = args[1:]
            except:
                print(f"kill: invalid signal: {args[0]}")
                return
        
        if not args:
            print("Usage: kill [-signal] <pid>")
            return
        
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        # Kill process
        try:
            pid = int(args[0])
            if self.executor.kill_process(pid, signal):
                print(f"Process {pid} terminated")
            else:
                print(f"kill: ({pid}) - No such process")
        except ValueError:
            print(f"kill: invalid PID: {args[0]}")
    
    def do_sleep(self, arg):
        """Sleep for specified seconds
        Usage: sleep <seconds>"""
        if not arg:
            print("Usage: sleep <seconds>")
            return
        
        try:
            seconds = float(arg)
            time.sleep(seconds)
        except ValueError:
            print(f"sleep: invalid time interval: {arg}")
    
    def do_wait(self, arg):
        """Wait for a process to complete
        Usage: wait [pid]"""
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        if arg:
            # Wait for specific PID
            try:
                pid = int(arg)
                exit_code = self.executor.wait_for_process(pid)
                if exit_code is not None:
                    self.last_exit_code = exit_code
                else:
                    print(f"wait: pid {pid} is not a child of this shell")
            except ValueError:
                print(f"wait: invalid PID: {arg}")
        else:
            # Wait for all background processes
            # In this simplified version, just return
            pass
    
    def do_jobs(self, arg):
        """List background jobs"""
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        # Find background processes
        from kos.core.executor import ProcessState
        jobs = []
        for proc in self.executor.list_processes():
            if proc.state == ProcessState.RUNNING and proc.pid != 1:
                jobs.append(proc)
        
        if not jobs:
            print("No background jobs")
        else:
            for i, job in enumerate(jobs, 1):
                print(f"[{i}]  {job.state.value}     {job.command}")
    
    def do_export(self, arg):
        """Export environment variable
        Usage: export VAR=value"""
        if not arg:
            # Show all environment variables
            if hasattr(self, 'executor'):
                for key, value in self.executor.environment.items():
                    print(f"{key}={value}")
            return
        
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        # Set variable
        if '=' in arg:
            var_name, var_value = arg.split('=', 1)
            self.executor.environment[var_name] = var_value
            os.environ[var_name] = var_value  # Also set in actual environment
        else:
            print(f"export: {arg}: not a valid identifier")
    
    def do_env(self, arg):
        """Display environment variables"""
        # Initialize executor if needed
        if not hasattr(self, 'executor'):
            from kos.core.executor import ProcessExecutor
            self.executor = ProcessExecutor(self.vfs, self.auth)
        
        for key, value in self.executor.environment.items():
            print(f"{key}={value}")
    
    def do_which(self, arg):
        """Locate a command
        Usage: which <command>"""
        if not arg:
            print("Usage: which <command>")
            return
        
        command = arg.strip()
        
        # Check built-in commands
        if hasattr(self, f'do_{command}'):
            print(f"{command}: shell built-in command")
            return
        
        # Check PATH (simplified - just check common locations)
        paths = ['/bin', '/usr/bin', '/sbin', '/usr/sbin']
        
        if self.vfs:
            for path in paths:
                full_path = os.path.join(path, command)
                if self.vfs.exists(full_path):
                    print(full_path)
                    return
        
        print(f"{command}: command not found")
    
    def do_alias(self, arg):
        """Create command alias
        Usage: alias name=command"""
        if not hasattr(self, 'aliases'):
            self.aliases = {}
        
        if not arg:
            # Show all aliases
            for name, command in self.aliases.items():
                print(f"alias {name}='{command}'")
            return
        
        if '=' in arg:
            name, command = arg.split('=', 1)
            # Remove quotes if present
            if command.startswith('"') and command.endswith('"'):
                command = command[1:-1]
            elif command.startswith("'") and command.endswith("'"):
                command = command[1:-1]
            
            self.aliases[name] = command
        else:
            # Show specific alias
            if arg in self.aliases:
                print(f"alias {arg}='{self.aliases[arg]}'")
            else:
                print(f"alias: {arg}: not found")
    
    def do_unalias(self, arg):
        """Remove alias
        Usage: unalias <name>"""
        if not hasattr(self, 'aliases'):
            self.aliases = {}
        
        if not arg:
            print("Usage: unalias <name>")
            return
        
        if arg in self.aliases:
            del self.aliases[arg]
        else:
            print(f"unalias: {arg}: not found")
    
    # Override default to handle aliases
    def default(self, line):
        """Handle unknown commands and aliases"""
        if hasattr(self, 'aliases'):
            # Check if it's an alias
            cmd = line.split()[0] if line else ""
            if cmd in self.aliases:
                # Execute aliased command
                aliased = self.aliases[cmd]
                if len(line.split()) > 1:
                    # Add arguments
                    aliased += " " + " ".join(line.split()[1:])
                self.onecmd(aliased)
                return
        
        # Call original default
        print(f"{line.split()[0] if line else ''}: command not found")
    
    # Register commands using MethodType
    shell.do_sh = types.MethodType(do_sh, shell)
    shell.do_bash = types.MethodType(do_bash, shell)
    shell.do_source = types.MethodType(do_source, shell)
    shell.do_exec = types.MethodType(do_exec, shell)
    shell.do_ps = types.MethodType(do_ps, shell)
    shell.do_kill = types.MethodType(do_kill, shell)
    shell.do_sleep = types.MethodType(do_sleep, shell)
    shell.do_wait = types.MethodType(do_wait, shell)
    shell.do_jobs = types.MethodType(do_jobs, shell)
    shell.do_export = types.MethodType(do_export, shell)
    shell.do_env = types.MethodType(do_env, shell)
    shell.do_which = types.MethodType(do_which, shell)
    shell.do_alias = types.MethodType(do_alias, shell)
    shell.do_unalias = types.MethodType(do_unalias, shell)
    
    # Override default if not already done
    if not hasattr(shell, '_original_default'):
        shell._original_default = shell.default
        shell.default = types.MethodType(default, shell)
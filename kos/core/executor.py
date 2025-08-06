"""
Process execution and script interpreter for KOS
"""

import os
import time
import threading
import queue
import shlex
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

class ProcessState(Enum):
    """Process states"""
    READY = "ready"
    RUNNING = "running"
    BLOCKED = "blocked"
    TERMINATED = "terminated"
    ZOMBIE = "zombie"

@dataclass
class Process:
    """Process representation"""
    pid: int
    name: str
    command: str
    state: ProcessState = ProcessState.READY
    parent_pid: Optional[int] = None
    children: List[int] = field(default_factory=list)
    exit_code: Optional[int] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    environment: Dict[str, str] = field(default_factory=dict)
    working_dir: str = "/"
    user: str = "system"
    
    @property
    def runtime(self) -> float:
        """Get process runtime"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time

class ScriptInterpreter:
    """KOS script interpreter (bash-like)"""
    
    def __init__(self, executor: 'ProcessExecutor', shell):
        self.executor = executor
        self.shell = shell
        self.variables = {}
        self.functions = {}
        self.exit_code = 0
        
    def execute_script(self, script: str, args: List[str] = None) -> int:
        """Execute a script"""
        lines = script.split('\n')
        
        # Set script arguments
        if args:
            for i, arg in enumerate(args):
                self.variables[str(i)] = arg
            self.variables['#'] = str(len(args))
            self.variables['@'] = ' '.join(args)
        
        # Execute line by line
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                i += 1
                continue
            
            # Handle control structures
            if line.startswith('if '):
                i = self._handle_if(lines, i)
            elif line.startswith('while '):
                i = self._handle_while(lines, i)
            elif line.startswith('for '):
                i = self._handle_for(lines, i)
            elif line.startswith('function '):
                i = self._handle_function(lines, i)
            else:
                # Execute command
                self.execute_command(line)
                i += 1
        
        return self.exit_code
    
    def execute_command(self, command: str) -> int:
        """Execute a single command"""
        # Variable substitution
        command = self._substitute_variables(command)
        
        # Handle variable assignment
        if '=' in command and not ' ' in command.split('=')[0]:
            var_name, var_value = command.split('=', 1)
            self.variables[var_name] = var_value
            return 0
        
        # Handle built-in commands
        if command.startswith('export '):
            return self._builtin_export(command[7:])
        elif command.startswith('echo '):
            return self._builtin_echo(command[5:])
        elif command == 'pwd':
            return self._builtin_pwd()
        elif command.startswith('cd '):
            return self._builtin_cd(command[3:])
        elif command.startswith('exit'):
            parts = command.split()
            self.exit_code = int(parts[1]) if len(parts) > 1 else 0
            return self.exit_code
        
        # Execute as shell command
        if self.shell:
            self.shell.onecmd(command)
            return 0
        
        return 127  # Command not found
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text"""
        # Handle $VAR and ${VAR}
        import re
        
        def replace_var(match):
            var_name = match.group(1) or match.group(2)
            return self.variables.get(var_name, '')
        
        text = re.sub(r'\$\{([^}]+)\}', replace_var, text)
        text = re.sub(r'\$(\w+)', replace_var, text)
        
        # Special variables
        text = text.replace('$?', str(self.exit_code))
        text = text.replace('$$', str(os.getpid()))
        
        return text
    
    def _builtin_export(self, args: str) -> int:
        """Export command"""
        if '=' in args:
            var_name, var_value = args.split('=', 1)
            self.variables[var_name] = var_value
            if self.executor:
                self.executor.environment[var_name] = var_value
        return 0
    
    def _builtin_echo(self, args: str) -> int:
        """Echo command"""
        print(args)
        return 0
    
    def _builtin_pwd(self) -> int:
        """PWD command"""
        if self.shell:
            print(self.shell.cwd)
        else:
            print("/")
        return 0
    
    def _builtin_cd(self, path: str) -> int:
        """CD command"""
        if self.shell and hasattr(self.shell, 'do_cd'):
            self.shell.do_cd(path)
            return 0
        return 1
    
    def _handle_if(self, lines: List[str], start: int) -> int:
        """Handle if statement"""
        # Simple if implementation
        condition_line = lines[start][3:].strip()
        
        # Find then, else, fi
        then_line = start + 1
        else_line = None
        fi_line = None
        
        for i in range(start + 1, len(lines)):
            line = lines[i].strip()
            if line == 'then':
                then_line = i + 1
            elif line == 'else':
                else_line = i + 1
            elif line == 'fi':
                fi_line = i
                break
        
        if not fi_line:
            return len(lines)  # Error: no fi found
        
        # Evaluate condition (simplified)
        condition_result = self._evaluate_condition(condition_line)
        
        # Execute appropriate block
        if condition_result:
            # Execute then block
            for i in range(then_line, else_line - 1 if else_line else fi_line):
                if lines[i].strip() not in ['then', 'else', 'fi']:
                    self.execute_command(lines[i])
        elif else_line:
            # Execute else block
            for i in range(else_line, fi_line):
                if lines[i].strip() not in ['then', 'else', 'fi']:
                    self.execute_command(lines[i])
        
        return fi_line + 1
    
    def _handle_while(self, lines: List[str], start: int) -> int:
        """Handle while loop"""
        condition_line = lines[start][6:].strip()
        
        # Find do and done
        do_line = start + 1
        done_line = None
        
        for i in range(start + 1, len(lines)):
            if lines[i].strip() == 'do':
                do_line = i + 1
            elif lines[i].strip() == 'done':
                done_line = i
                break
        
        if not done_line:
            return len(lines)
        
        # Execute loop
        while self._evaluate_condition(condition_line):
            for i in range(do_line, done_line):
                if lines[i].strip() not in ['do', 'done']:
                    self.execute_command(lines[i])
        
        return done_line + 1
    
    def _handle_for(self, lines: List[str], start: int) -> int:
        """Handle for loop"""
        # Simple for var in items implementation
        for_line = lines[start][4:].strip()
        
        # Parse for var in items
        if ' in ' in for_line:
            var_name, items_str = for_line.split(' in ', 1)
            items = shlex.split(items_str)
        else:
            return start + 1
        
        # Find do and done
        do_line = start + 1
        done_line = None
        
        for i in range(start + 1, len(lines)):
            if lines[i].strip() == 'do':
                do_line = i + 1
            elif lines[i].strip() == 'done':
                done_line = i
                break
        
        if not done_line:
            return len(lines)
        
        # Execute loop
        for item in items:
            self.variables[var_name] = item
            for i in range(do_line, done_line):
                if lines[i].strip() not in ['do', 'done']:
                    self.execute_command(lines[i])
        
        return done_line + 1
    
    def _handle_function(self, lines: List[str], start: int) -> int:
        """Handle function definition"""
        # Extract function name
        func_line = lines[start][9:].strip()
        if '(' in func_line:
            func_name = func_line.split('(')[0].strip()
        else:
            func_name = func_line.strip()
        
        # Find function body
        body_start = start + 1
        body_end = None
        brace_count = 0
        
        for i in range(start + 1, len(lines)):
            line = lines[i].strip()
            if line == '{':
                brace_count += 1
                if brace_count == 1:
                    body_start = i + 1
            elif line == '}':
                brace_count -= 1
                if brace_count == 0:
                    body_end = i
                    break
        
        if body_end:
            # Store function
            self.functions[func_name] = lines[body_start:body_end]
            return body_end + 1
        
        return len(lines)
    
    def _evaluate_condition(self, condition: str) -> bool:
        """Evaluate a condition (simplified)"""
        condition = self._substitute_variables(condition)
        
        # Handle test/[ commands
        if condition.startswith('[') and condition.endswith(']'):
            condition = condition[1:-1].strip()
        elif condition.startswith('test '):
            condition = condition[5:].strip()
        
        # Simple comparisons
        if ' = ' in condition or ' == ' in condition:
            parts = condition.split(' = ' if ' = ' in condition else ' == ')
            if len(parts) == 2:
                return parts[0].strip() == parts[1].strip()
        elif ' != ' in condition:
            parts = condition.split(' != ')
            if len(parts) == 2:
                return parts[0].strip() != parts[1].strip()
        elif ' -eq ' in condition:
            parts = condition.split(' -eq ')
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()) == int(parts[1].strip())
                except:
                    return False
        elif ' -ne ' in condition:
            parts = condition.split(' -ne ')
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()) != int(parts[1].strip())
                except:
                    return False
        elif ' -lt ' in condition:
            parts = condition.split(' -lt ')
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()) < int(parts[1].strip())
                except:
                    return False
        elif ' -gt ' in condition:
            parts = condition.split(' -gt ')
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()) > int(parts[1].strip())
                except:
                    return False
        
        # File tests (simplified)
        if condition.startswith('-f '):
            # File exists
            filepath = condition[3:].strip()
            if self.shell and self.shell.vfs:
                return self.shell.vfs.exists(filepath) and self.shell.vfs.isfile(filepath)
        elif condition.startswith('-d '):
            # Directory exists
            dirpath = condition[3:].strip()
            if self.shell and self.shell.vfs:
                return self.shell.vfs.exists(dirpath) and self.shell.vfs.isdir(dirpath)
        elif condition.startswith('-e '):
            # Path exists
            path = condition[3:].strip()
            if self.shell and self.shell.vfs:
                return self.shell.vfs.exists(path)
        
        # Default to true for non-empty strings
        return bool(condition)


class ProcessExecutor:
    """Process execution manager"""
    
    def __init__(self, vfs, auth=None):
        self.vfs = vfs
        self.auth = auth
        self.processes: Dict[int, Process] = {}
        self.next_pid = 1000
        self.environment = os.environ.copy()
        self.current_dir = "/"
        
        # Create init process
        self.init_process = Process(
            pid=1,
            name="init",
            command="/sbin/init",
            state=ProcessState.RUNNING,
            user="root"
        )
        self.processes[1] = self.init_process
    
    def create_process(self, command: str, parent_pid: Optional[int] = None,
                      user: Optional[str] = None) -> Process:
        """Create a new process"""
        pid = self.next_pid
        self.next_pid += 1
        
        # Get process name from command
        name = command.split()[0] if command else "unknown"
        if '/' in name:
            name = name.split('/')[-1]
        
        # Create process
        process = Process(
            pid=pid,
            name=name,
            command=command,
            parent_pid=parent_pid or 1,
            environment=self.environment.copy(),
            working_dir=self.current_dir,
            user=user or "system"
        )
        
        self.processes[pid] = process
        
        # Add to parent's children
        if parent_pid and parent_pid in self.processes:
            self.processes[parent_pid].children.append(pid)
        
        return process
    
    def execute(self, command: str, background: bool = False) -> int:
        """Execute a command"""
        # Create process
        process = self.create_process(command)
        
        # Run process
        process.state = ProcessState.RUNNING
        
        # Simulate execution (in real implementation, would fork/exec)
        if not background:
            # Wait for completion
            time.sleep(0.1)  # Simulate execution time
            process.state = ProcessState.TERMINATED
            process.exit_code = 0
            process.end_time = time.time()
            return 0
        else:
            # Return immediately for background processes
            # In real implementation, would run in separate thread
            def run_background():
                time.sleep(1)
                process.state = ProcessState.TERMINATED
                process.exit_code = 0
                process.end_time = time.time()
            
            thread = threading.Thread(target=run_background)
            thread.daemon = True
            thread.start()
            
            return process.pid
    
    def kill_process(self, pid: int, signal: int = 15) -> bool:
        """Kill a process"""
        if pid not in self.processes:
            return False
        
        process = self.processes[pid]
        
        # Don't kill init
        if pid == 1:
            return False
        
        # Terminate process
        process.state = ProcessState.TERMINATED
        process.exit_code = -signal
        process.end_time = time.time()
        
        # Kill children
        for child_pid in process.children[:]:
            self.kill_process(child_pid, signal)
        
        return True
    
    def get_process(self, pid: int) -> Optional[Process]:
        """Get process by PID"""
        return self.processes.get(pid)
    
    def list_processes(self) -> List[Process]:
        """List all processes"""
        return list(self.processes.values())
    
    def wait_for_process(self, pid: int) -> Optional[int]:
        """Wait for process to complete"""
        if pid not in self.processes:
            return None
        
        process = self.processes[pid]
        
        # Wait for termination
        while process.state != ProcessState.TERMINATED:
            time.sleep(0.1)
        
        return process.exit_code
"""
ShellInterface Component for KLayer

This module provides shell access capabilities for KOS applications,
allowing them to execute and control shell operations in a secure manner.
"""

import os
import sys
import subprocess
import threading
import logging
import time
import shlex
import queue
import re
from typing import Dict, List, Any, Optional, Union, Callable, Tuple

logger = logging.getLogger('KOS.layer.shell')

class CommandResult:
    """Result of a shell command execution"""
    
    def __init__(self, command: str, return_code: int, stdout: str = None, stderr: str = None, duration: float = 0):
        """
        Initialize a command result
        
        Args:
            command: The command that was executed
            return_code: The return code of the command
            stdout: Standard output of the command
            stderr: Standard error of the command
            duration: Duration of the command execution in seconds
        """
        self.command = command
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration = duration
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "command": self.command,
            "return_code": self.return_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "success": self.return_code == 0,
            "duration": self.duration,
            "timestamp": self.timestamp
        }
    
    def __str__(self) -> str:
        """String representation"""
        return f"CommandResult(command='{self.command}', return_code={self.return_code}, duration={self.duration:.2f}s)"

class CommandHistory:
    """History of executed shell commands"""
    
    def __init__(self, max_size: int = 100):
        """
        Initialize command history
        
        Args:
            max_size: Maximum number of commands to store
        """
        self.max_size = max_size
        self.history = []
        self.lock = threading.RLock()
    
    def add(self, command: str, result: CommandResult):
        """
        Add a command and its result to history
        
        Args:
            command: The command that was executed
            result: The result of the command
        """
        with self.lock:
            self.history.append((command, result))
            
            # Trim history if needed
            if len(self.history) > self.max_size:
                self.history = self.history[-self.max_size:]
    
    def get(self, count: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get command history
        
        Args:
            count: Number of recent commands to return (None for all)
            
        Returns:
            List of command history entries
        """
        with self.lock:
            if count is None or count >= len(self.history):
                commands = self.history
            else:
                commands = self.history[-count:]
            
            return [
                {
                    "command": command,
                    "result": result.to_dict()
                }
                for command, result in commands
            ]
    
    def clear(self):
        """Clear command history"""
        with self.lock:
            self.history = []
    
    def search(self, pattern: str) -> List[Dict[str, Any]]:
        """
        Search command history
        
        Args:
            pattern: Pattern to search for
            
        Returns:
            List of matching command history entries
        """
        try:
            regex = re.compile(pattern)
            results = []
            
            with self.lock:
                for command, result in self.history:
                    if regex.search(command):
                        results.append({
                            "command": command,
                            "result": result.to_dict()
                        })
            
            return results
        except re.error:
            # Treat as plain text search if not a valid regex
            results = []
            
            with self.lock:
                for command, result in self.history:
                    if pattern in command:
                        results.append({
                            "command": command,
                            "result": result.to_dict()
                        })
            
            return results

class AsyncCommandExecutor:
    """Executes commands asynchronously with real-time output"""
    
    def __init__(self, command: str, shell: bool = False, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None):
        """
        Initialize an async command executor
        
        Args:
            command: Command to execute
            shell: Whether to use shell
            cwd: Working directory
            env: Environment variables
        """
        self.command = command
        self.shell = shell
        self.cwd = cwd
        self.env = env
        
        self.process = None
        self.stdout_queue = queue.Queue()
        self.stderr_queue = queue.Queue()
        self.stdout_thread = None
        self.stderr_thread = None
        self.main_thread = None
        
        self.is_running = False
        self.is_completed = False
        self.return_code = None
        self.start_time = None
        self.end_time = None
        
        self.output_callbacks = []
        self.completion_callbacks = []
    
    def _read_output(self, stream, queue_obj):
        """
        Read output from a stream
        
        Args:
            stream: Stream to read from
            queue_obj: Queue to put output into
        """
        for line in iter(stream.readline, b''):
            try:
                line_str = line.decode('utf-8')
                queue_obj.put(line_str)
                
                # Call output callbacks
                for callback in self.output_callbacks:
                    try:
                        callback(line_str, "stdout" if stream == self.process.stdout else "stderr")
                    except Exception as e:
                        logger.error(f"Error in output callback: {e}")
            except UnicodeDecodeError:
                # Handle non-UTF-8 output
                queue_obj.put("[Non-UTF-8 output]\n")
        
        stream.close()
    
    def _main_thread(self):
        """Main execution thread"""
        try:
            # Start process
            self.process = subprocess.Popen(
                self.command if self.shell else shlex.split(self.command),
                shell=self.shell,
                cwd=self.cwd,
                env=self.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=False
            )
            
            # Start output reader threads
            self.stdout_thread = threading.Thread(
                target=self._read_output,
                args=(self.process.stdout, self.stdout_queue)
            )
            self.stdout_thread.daemon = True
            self.stdout_thread.start()
            
            self.stderr_thread = threading.Thread(
                target=self._read_output,
                args=(self.process.stderr, self.stderr_queue)
            )
            self.stderr_thread.daemon = True
            self.stderr_thread.start()
            
            # Wait for process to complete
            self.return_code = self.process.wait()
            
            # Wait for output threads to finish
            self.stdout_thread.join()
            self.stderr_thread.join()
            
            # Set completion status
            self.is_running = False
            self.is_completed = True
            self.end_time = time.time()
            
            # Call completion callbacks
            for callback in self.completion_callbacks:
                try:
                    callback(self.return_code)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")
        except Exception as e:
            logger.error(f"Error in command execution: {e}")
            self.is_running = False
            self.is_completed = True
            self.end_time = time.time()
            self.return_code = -1
            
            # Call completion callbacks with error
            for callback in self.completion_callbacks:
                try:
                    callback(-1)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")
    
    def start(self) -> bool:
        """
        Start command execution
        
        Returns:
            Success status
        """
        if self.is_running:
            return False
        
        self.is_running = True
        self.is_completed = False
        self.return_code = None
        self.start_time = time.time()
        self.end_time = None
        
        # Start main thread
        self.main_thread = threading.Thread(target=self._main_thread)
        self.main_thread.daemon = True
        self.main_thread.start()
        
        return True
    
    def get_output(self) -> Tuple[List[str], List[str]]:
        """
        Get current output
        
        Returns:
            Tuple of (stdout_lines, stderr_lines)
        """
        stdout_lines = []
        stderr_lines = []
        
        # Get stdout
        while not self.stdout_queue.empty():
            stdout_lines.append(self.stdout_queue.get())
        
        # Get stderr
        while not self.stderr_queue.empty():
            stderr_lines.append(self.stderr_queue.get())
        
        return stdout_lines, stderr_lines
    
    def terminate(self) -> bool:
        """
        Terminate command execution
        
        Returns:
            Success status
        """
        if not self.is_running or self.process is None:
            return False
        
        try:
            self.process.terminate()
            return True
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
            return False
    
    def kill(self) -> bool:
        """
        Kill command execution
        
        Returns:
            Success status
        """
        if not self.is_running or self.process is None:
            return False
        
        try:
            self.process.kill()
            return True
        except Exception as e:
            logger.error(f"Error killing process: {e}")
            return False
    
    def register_output_callback(self, callback: Callable) -> bool:
        """
        Register an output callback
        
        Args:
            callback: Callback function
            
        Returns:
            Success status
        """
        self.output_callbacks.append(callback)
        return True
    
    def register_completion_callback(self, callback: Callable) -> bool:
        """
        Register a completion callback
        
        Args:
            callback: Callback function
            
        Returns:
            Success status
        """
        self.completion_callbacks.append(callback)
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get execution status
        
        Returns:
            Dictionary with execution status
        """
        return {
            "command": self.command,
            "is_running": self.is_running,
            "is_completed": self.is_completed,
            "return_code": self.return_code,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": (self.end_time or time.time()) - self.start_time if self.start_time else None
        }

class ShellInterface:
    """
    Provides shell access for KOS applications
    
    This class provides methods for KOS applications to execute
    and control shell commands in a secure manner.
    """
    
    def __init__(self):
        """Initialize the ShellInterface component"""
        self.lock = threading.RLock()
        self.command_history = CommandHistory()
        self.async_commands = {}  # command_id -> AsyncCommandExecutor
        self.next_command_id = 1
        
        # Environment variables
        self.default_env = os.environ.copy()
        
        logger.debug("ShellInterface component initialized")
    
    def execute_command(self, app_id: str, command: str, shell: bool = True, 
                       cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None,
                       timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute a shell command
        
        Args:
            app_id: Application ID
            command: Command to execute
            shell: Whether to use shell
            cwd: Working directory
            env: Environment variables
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with execution results
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        # Prepare environment
        merged_env = None
        if env:
            merged_env = self.default_env.copy()
            merged_env.update(env)
        
        try:
            # Execute command
            start_time = time.time()
            
            result = subprocess.run(
                command if shell else shlex.split(command),
                shell=shell,
                cwd=cwd,
                env=merged_env,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Create command result
            cmd_result = CommandResult(
                command=command,
                return_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration=duration
            )
            
            # Add to history
            self.command_history.add(command, cmd_result)
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration": duration
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def execute_async_command(self, app_id: str, command: str, shell: bool = True,
                            cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute a command asynchronously
        
        Args:
            app_id: Application ID
            command: Command to execute
            shell: Whether to use shell
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Dictionary with execution status
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        # Prepare environment
        merged_env = None
        if env:
            merged_env = self.default_env.copy()
            merged_env.update(env)
        
        try:
            # Generate command ID
            with self.lock:
                command_id = str(self.next_command_id)
                self.next_command_id += 1
            
            # Create executor
            executor = AsyncCommandExecutor(
                command=command,
                shell=shell,
                cwd=cwd,
                env=merged_env
            )
            
            # Store executor
            with self.lock:
                self.async_commands[command_id] = executor
            
            # Start execution
            if executor.start():
                return {
                    "success": True,
                    "command_id": command_id,
                    "command": command
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to start command"
                }
        except Exception as e:
            logger.error(f"Error executing async command: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_async_command_output(self, app_id: str, command_id: str) -> Dict[str, Any]:
        """
        Get output from an asynchronous command
        
        Args:
            app_id: Application ID
            command_id: Command ID
            
        Returns:
            Dictionary with command output
        """
        with self.lock:
            if command_id not in self.async_commands:
                return {
                    "success": False,
                    "error": f"Command not found: {command_id}"
                }
            
            executor = self.async_commands[command_id]
        
        # Get output
        stdout_lines, stderr_lines = executor.get_output()
        
        # Get status
        status = executor.get_status()
        
        return {
            "success": True,
            "command_id": command_id,
            "stdout": stdout_lines,
            "stderr": stderr_lines,
            "is_running": status["is_running"],
            "is_completed": status["is_completed"],
            "return_code": status["return_code"],
            "duration": status["duration"]
        }
    
    def terminate_async_command(self, app_id: str, command_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Terminate an asynchronous command
        
        Args:
            app_id: Application ID
            command_id: Command ID
            force: Whether to forcefully kill the command
            
        Returns:
            Dictionary with termination status
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.kill"):
            return {
                "success": False,
                "error": "Permission denied: App does not have kill permission"
            }
        
        with self.lock:
            if command_id not in self.async_commands:
                return {
                    "success": False,
                    "error": f"Command not found: {command_id}"
                }
            
            executor = self.async_commands[command_id]
        
        # Terminate or kill
        if force:
            success = executor.kill()
        else:
            success = executor.terminate()
        
        return {
            "success": success,
            "command_id": command_id,
            "force": force
        }
    
    def register_output_callback(self, app_id: str, command_id: str, callback: Callable) -> Dict[str, Any]:
        """
        Register an output callback for an asynchronous command
        
        Args:
            app_id: Application ID
            command_id: Command ID
            callback: Callback function
            
        Returns:
            Dictionary with registration status
        """
        with self.lock:
            if command_id not in self.async_commands:
                return {
                    "success": False,
                    "error": f"Command not found: {command_id}"
                }
            
            executor = self.async_commands[command_id]
        
        # Register callback
        success = executor.register_output_callback(callback)
        
        return {
            "success": success,
            "command_id": command_id
        }
    
    def register_completion_callback(self, app_id: str, command_id: str, callback: Callable) -> Dict[str, Any]:
        """
        Register a completion callback for an asynchronous command
        
        Args:
            app_id: Application ID
            command_id: Command ID
            callback: Callback function
            
        Returns:
            Dictionary with registration status
        """
        with self.lock:
            if command_id not in self.async_commands:
                return {
                    "success": False,
                    "error": f"Command not found: {command_id}"
                }
            
            executor = self.async_commands[command_id]
        
        # Register callback
        success = executor.register_completion_callback(callback)
        
        return {
            "success": success,
            "command_id": command_id
        }
    
    def get_command_history(self, app_id: str, count: Optional[int] = None) -> Dict[str, Any]:
        """
        Get command history
        
        Args:
            app_id: Application ID
            count: Number of recent commands to return
            
        Returns:
            Dictionary with command history
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        history = self.command_history.get(count)
        
        return {
            "success": True,
            "history": history,
            "count": len(history)
        }
    
    def search_command_history(self, app_id: str, pattern: str) -> Dict[str, Any]:
        """
        Search command history
        
        Args:
            app_id: Application ID
            pattern: Pattern to search for
            
        Returns:
            Dictionary with search results
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        results = self.command_history.search(pattern)
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "pattern": pattern
        }
    
    def clear_command_history(self, app_id: str) -> Dict[str, Any]:
        """
        Clear command history
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with clear status
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        self.command_history.clear()
        
        return {
            "success": True
        }
    
    def get_async_commands(self, app_id: str) -> Dict[str, Any]:
        """
        Get active asynchronous commands
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with active commands
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        commands = []
        
        with self.lock:
            for command_id, executor in self.async_commands.items():
                if executor.is_running:
                    commands.append({
                        "command_id": command_id,
                        "command": executor.command,
                        "status": executor.get_status()
                    })
        
        return {
            "success": True,
            "commands": commands,
            "count": len(commands)
        }
    
    def pipe_commands(self, app_id: str, commands: List[str], cwd: Optional[str] = None,
                     env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute piped commands
        
        Args:
            app_id: Application ID
            commands: List of commands to pipe
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Dictionary with execution results
        """
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(app_id, "process.execute"):
            return {
                "success": False,
                "error": "Permission denied: App does not have execute permission"
            }
        
        if not commands:
            return {
                "success": False,
                "error": "No commands provided"
            }
        
        # Create piped command
        piped_command = " | ".join(commands)
        
        # Execute command
        return self.execute_command(app_id, piped_command, True, cwd, env)
    
    def set_default_env(self, env: Dict[str, str]) -> bool:
        """
        Set default environment variables
        
        Args:
            env: Environment variables
            
        Returns:
            Success status
        """
        if not isinstance(env, dict):
            return False
        
        with self.lock:
            self.default_env = env.copy()
            logger.debug("Updated default environment variables")
            return True
    
    def get_default_env(self) -> Dict[str, str]:
        """
        Get default environment variables
        
        Returns:
            Default environment variables
        """
        with self.lock:
            return self.default_env.copy()
    
    def add_default_env(self, key: str, value: str) -> bool:
        """
        Add or update a default environment variable
        
        Args:
            key: Environment variable name
            value: Environment variable value
            
        Returns:
            Success status
        """
        with self.lock:
            self.default_env[key] = value
            logger.debug(f"Added default environment variable: {key}")
            return True
    
    def remove_default_env(self, key: str) -> bool:
        """
        Remove a default environment variable
        
        Args:
            key: Environment variable name
            
        Returns:
            Success status
        """
        with self.lock:
            if key in self.default_env:
                del self.default_env[key]
                logger.debug(f"Removed default environment variable: {key}")
                return True
            else:
                return False

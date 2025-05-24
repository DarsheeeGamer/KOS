"""
ProcessManager Component for KADVLayer

This module provides advanced process management capabilities,
allowing KOS to execute, monitor, and control processes on the host system.
"""

import os
import sys
import subprocess
import threading
import logging
import signal
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union, Callable

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.process_manager')

class ProcessInfo:
    """Information about a process managed by KADVLayer"""
    
    def __init__(self, pid: int, command: str, start_time: float = None):
        """
        Initialize a ProcessInfo object
        
        Args:
            pid: Process ID
            command: Command that started the process
            start_time: Process start time (timestamp)
        """
        self.pid = pid
        self.command = command
        self.start_time = start_time or time.time()
        self.end_time = None
        self.exit_code = None
        self.stdout = None
        self.stderr = None
        self.status = "running"  # running, completed, terminated, failed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pid": self.pid,
            "command": self.command,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "exit_code": self.exit_code,
            "status": self.status,
            "runtime": (self.end_time or time.time()) - self.start_time
        }
    
    def __str__(self) -> str:
        """String representation"""
        runtime = (self.end_time or time.time()) - self.start_time
        return f"Process(pid={self.pid}, status={self.status}, runtime={runtime:.2f}s)"

class ProcessManager:
    """
    Manages processes on the host system
    
    This class provides methods to execute, monitor, and control
    processes on the host system with enhanced capabilities beyond
    standard subprocess functionality.
    """
    
    def __init__(self):
        """Initialize the ProcessManager component"""
        self.managed_processes = {}  # pid -> ProcessInfo
        self.lock = threading.RLock()
        self.max_processes = 50  # Maximum number of managed processes to track
        self.cleanup_interval = 3600  # Cleanup interval in seconds (1 hour)
        self.last_cleanup = time.time()
        logger.debug("ProcessManager component initialized")
    
    def execute_command(self, command: str, shell: bool = True, 
                      timeout: Optional[float] = None,
                      capture_output: bool = True,
                      cwd: Optional[str] = None,
                      env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute a command on the host system
        
        Args:
            command: Command to execute
            shell: Whether to use shell
            timeout: Timeout in seconds
            capture_output: Whether to capture stdout/stderr
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Dictionary with execution results
        """
        try:
            start_time = time.time()
            
            # Prepare subprocess arguments
            kwargs = {
                "shell": shell,
                "cwd": cwd,
                "env": env
            }
            
            if capture_output:
                kwargs["stdout"] = subprocess.PIPE
                kwargs["stderr"] = subprocess.PIPE
                kwargs["text"] = True
            
            # Execute command
            process = subprocess.run(command, timeout=timeout, **kwargs)
            
            # Record process information
            end_time = time.time()
            runtime = end_time - start_time
            
            # Prepare result
            result = {
                "success": process.returncode == 0,
                "return_code": process.returncode,
                "runtime": runtime
            }
            
            if capture_output:
                result["stdout"] = process.stdout
                result["stderr"] = process.stderr
            
            return result
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Command timed out",
                "timeout": timeout
            }
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def start_process(self, command: List[str], shell: bool = False,
                     capture_output: bool = True,
                     cwd: Optional[str] = None,
                     env: Optional[Dict[str, str]] = None,
                     callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Start a process asynchronously
        
        Args:
            command: Command to execute (list of arguments)
            shell: Whether to use shell
            capture_output: Whether to capture stdout/stderr
            cwd: Working directory
            env: Environment variables
            callback: Callback function when process completes
            
        Returns:
            Dictionary with process information
        """
        try:
            # Cleanup old processes if needed
            self._cleanup_processes()
            
            # Prepare subprocess arguments
            kwargs = {
                "shell": shell,
                "cwd": cwd,
                "env": env
            }
            
            if capture_output:
                kwargs["stdout"] = subprocess.PIPE
                kwargs["stderr"] = subprocess.PIPE
                kwargs["text"] = True
            
            # Start process
            process = subprocess.Popen(command, **kwargs)
            
            # Create process info
            cmd_str = " ".join(command) if isinstance(command, list) else str(command)
            proc_info = ProcessInfo(process.pid, cmd_str)
            
            # Add to managed processes
            with self.lock:
                self.managed_processes[process.pid] = proc_info
            
            # Start monitoring thread if callback provided
            if callback:
                def monitor_thread():
                    process.wait()
                    proc_info.exit_code = process.returncode
                    proc_info.end_time = time.time()
                    proc_info.status = "completed" if process.returncode == 0 else "failed"
                    
                    if capture_output:
                        proc_info.stdout, proc_info.stderr = process.communicate()
                    
                    # Call callback
                    try:
                        callback(proc_info)
                    except Exception as e:
                        logger.error(f"Error in process callback: {e}")
                
                threading.Thread(target=monitor_thread, daemon=True).start()
            
            return {
                "success": True,
                "pid": process.pid,
                "process_info": proc_info.to_dict()
            }
        except Exception as e:
            logger.error(f"Error starting process: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def terminate_process(self, pid: int, force: bool = False) -> Dict[str, Any]:
        """
        Terminate a process
        
        Args:
            pid: Process ID
            force: Whether to forcefully kill the process
            
        Returns:
            Dictionary with termination results
        """
        try:
            # Check if process exists
            if not PSUTIL_AVAILABLE:
                # Fallback to os.kill for existence check
                try:
                    os.kill(pid, 0)  # 0 signal just checks if process exists
                except OSError:
                    return {
                        "success": False,
                        "error": f"Process with PID {pid} does not exist"
                    }
            else:
                # Use psutil to check process
                if not psutil.pid_exists(pid):
                    return {
                        "success": False,
                        "error": f"Process with PID {pid} does not exist"
                    }
            
            # Get process info from managed processes
            proc_info = self.managed_processes.get(pid)
            
            # Terminate process
            if force:
                # Use SIGKILL (force kill)
                if hasattr(signal, 'SIGKILL'):
                    os.kill(pid, signal.SIGKILL)
                else:
                    # Windows fallback
                    os.kill(pid, signal.SIGTERM)
            else:
                # Use SIGTERM (graceful termination)
                os.kill(pid, signal.SIGTERM)
            
            # Update process info if available
            if proc_info:
                proc_info.status = "terminated"
                proc_info.end_time = time.time()
            
            return {
                "success": True,
                "pid": pid,
                "force": force
            }
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_process_info(self, pid: int) -> Dict[str, Any]:
        """
        Get information about a process
        
        Args:
            pid: Process ID
            
        Returns:
            Dictionary with process information
        """
        # First check managed processes
        if pid in self.managed_processes:
            return {
                "success": True,
                "managed": True,
                "process_info": self.managed_processes[pid].to_dict()
            }
        
        # If not managed, try to get info using psutil
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(pid)
                
                # Get process information
                info = {
                    "pid": process.pid,
                    "name": process.name(),
                    "status": process.status(),
                    "created": process.create_time()
                }
                
                # Get additional information if available
                try:
                    info["cpu_percent"] = process.cpu_percent(interval=0.1)
                except:
                    pass
                
                try:
                    info["memory_info"] = process.memory_info()._asdict()
                except:
                    pass
                
                try:
                    info["username"] = process.username()
                except:
                    pass
                
                try:
                    info["cmdline"] = process.cmdline()
                except:
                    pass
                
                return {
                    "success": True,
                    "managed": False,
                    "process_info": info
                }
            except psutil.NoSuchProcess:
                return {
                    "success": False,
                    "error": f"Process with PID {pid} does not exist"
                }
            except Exception as e:
                logger.error(f"Error getting process info: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Cannot get detailed process info without psutil
            return {
                "success": False,
                "error": "Cannot get detailed process info without psutil"
            }
    
    def list_processes(self, include_system: bool = False) -> Dict[str, Any]:
        """
        List all processes
        
        Args:
            include_system: Whether to include system processes
            
        Returns:
            Dictionary with process list
        """
        if PSUTIL_AVAILABLE:
            try:
                processes = []
                
                for process in psutil.process_iter(['pid', 'name', 'username', 'status']):
                    try:
                        # Skip system processes if not requested
                        if not include_system and process.username() in ['NT AUTHORITY\\SYSTEM', 'root']:
                            continue
                        
                        proc_info = {
                            "pid": process.info['pid'],
                            "name": process.info['name'],
                            "username": process.info['username'],
                            "status": process.info['status']
                        }
                        
                        # Check if managed
                        if process.info['pid'] in self.managed_processes:
                            proc_info["managed"] = True
                            proc_info.update(self.managed_processes[process.info['pid']].to_dict())
                        else:
                            proc_info["managed"] = False
                        
                        processes.append(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                return {
                    "success": True,
                    "processes": processes
                }
            except Exception as e:
                logger.error(f"Error listing processes: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            # Return only managed processes if psutil not available
            managed_processes = []
            
            for pid, proc_info in self.managed_processes.items():
                managed_processes.append(proc_info.to_dict())
            
            return {
                "success": True,
                "processes": managed_processes,
                "note": "Only managed processes available without psutil"
            }
    
    def _cleanup_processes(self):
        """Clean up old processes"""
        current_time = time.time()
        
        # Only cleanup if enough time has passed
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        with self.lock:
            # Find processes to remove
            to_remove = []
            
            for pid, proc_info in self.managed_processes.items():
                # Remove terminated processes older than 1 hour
                if proc_info.status != "running" and proc_info.end_time:
                    if current_time - proc_info.end_time > 3600:
                        to_remove.append(pid)
            
            # Remove old processes
            for pid in to_remove:
                del self.managed_processes[pid]
            
            # Update last cleanup time
            self.last_cleanup = current_time
            
            logger.debug(f"Cleaned up {len(to_remove)} old processes")
    
    def set_process_priority(self, pid: int, priority: int) -> Dict[str, Any]:
        """
        Set process priority
        
        Args:
            pid: Process ID
            priority: Priority level (lower value = higher priority)
            
        Returns:
            Dictionary with result
        """
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(pid)
                process.nice(priority)
                
                return {
                    "success": True,
                    "pid": pid,
                    "priority": priority
                }
            except psutil.NoSuchProcess:
                return {
                    "success": False,
                    "error": f"Process with PID {pid} does not exist"
                }
            except Exception as e:
                logger.error(f"Error setting process priority: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            return {
                "success": False,
                "error": "Cannot set process priority without psutil"
            }
    
    def get_child_processes(self, pid: int) -> Dict[str, Any]:
        """
        Get child processes of a process
        
        Args:
            pid: Process ID
            
        Returns:
            Dictionary with child process list
        """
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(pid)
                children = process.children(recursive=True)
                
                child_info = []
                for child in children:
                    try:
                        info = {
                            "pid": child.pid,
                            "name": child.name(),
                            "status": child.status()
                        }
                        
                        # Check if managed
                        if child.pid in self.managed_processes:
                            info["managed"] = True
                            info.update(self.managed_processes[child.pid].to_dict())
                        else:
                            info["managed"] = False
                        
                        child_info.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                return {
                    "success": True,
                    "pid": pid,
                    "children": child_info
                }
            except psutil.NoSuchProcess:
                return {
                    "success": False,
                    "error": f"Process with PID {pid} does not exist"
                }
            except Exception as e:
                logger.error(f"Error getting child processes: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
        else:
            return {
                "success": False,
                "error": "Cannot get child processes without psutil"
            }

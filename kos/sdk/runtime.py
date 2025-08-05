"""
KOS Runtime - Runtime support for KOS applications
"""

import os
import sys
import signal
import subprocess
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

class ProcessState(Enum):
    """Application process states"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    CRASHED = "crashed"

class KOSRuntime:
    """
    KOS Runtime Environment
    Provides runtime services for KOS applications
    """
    
    def __init__(self):
        self.processes: Dict[int, 'AppProcess'] = {}
        self.next_pid = 1000
        self.signal_handlers: Dict[int, Callable] = {}
        
        # Runtime configuration
        self.env_vars = os.environ.copy()
        self.env_vars['KOS_RUNTIME'] = '1.0'
        self.env_vars['KOS_SDK_PATH'] = os.path.dirname(os.path.dirname(__file__))
        
        # Resource limits
        self.resource_limits = {
            'max_memory': 512 * 1024 * 1024,  # 512MB
            'max_cpu_time': 3600,  # 1 hour
            'max_open_files': 256
        }
        
    def execute(self, executable: str, args: List[str] = None, 
                env: Dict[str, str] = None,
                working_dir: str = None,
                capture_output: bool = False) -> 'AppProcess':
        """
        Execute a KOS application
        
        Args:
            executable: Path to executable
            args: Command line arguments
            env: Environment variables
            working_dir: Working directory
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            AppProcess instance
        """
        
        if not os.path.exists(executable):
            raise FileNotFoundError(f"Executable not found: {executable}")
            
        # Create process object
        pid = self._allocate_pid()
        process = AppProcess(
            pid=pid,
            executable=executable,
            args=args or [],
            env=env or self.env_vars,
            working_dir=working_dir,
            capture_output=capture_output
        )
        
        # Register process
        self.processes[pid] = process
        
        # Start process
        process.start()
        
        return process
        
    def execute_python(self, script: str, args: List[str] = None,
                      env: Dict[str, str] = None,
                      working_dir: str = None) -> 'AppProcess':
        """Execute a Python script"""
        
        # Prepare Python execution
        python_exe = sys.executable
        full_args = [python_exe, script]
        if args:
            full_args.extend(args)
            
        # Create process for Python script
        pid = self._allocate_pid()
        process = AppProcess(
            pid=pid,
            executable=python_exe,
            args=full_args[1:],  # Skip python executable
            env=env or self.env_vars,
            working_dir=working_dir,
            capture_output=True
        )
        
        # Register and start
        self.processes[pid] = process
        process.start()
        
        return process
        
    def kill_process(self, pid: int, signal_num: int = signal.SIGTERM) -> bool:
        """Send signal to process"""
        if pid not in self.processes:
            return False
            
        process = self.processes[pid]
        return process.send_signal(signal_num)
        
    def wait_process(self, pid: int, timeout: Optional[float] = None) -> Optional[int]:
        """Wait for process to complete"""
        if pid not in self.processes:
            return None
            
        process = self.processes[pid]
        return process.wait(timeout)
        
    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """Get process information"""
        if pid not in self.processes:
            return None
            
        process = self.processes[pid]
        return {
            'pid': process.pid,
            'executable': process.executable,
            'args': process.args,
            'state': process.state.value,
            'start_time': process.start_time,
            'exit_code': process.exit_code,
            'cpu_time': process.cpu_time,
            'memory_usage': process.memory_usage
        }
        
    def list_processes(self) -> List[Dict[str, Any]]:
        """List all processes"""
        return [self.get_process_info(pid) for pid in self.processes]
        
    def _allocate_pid(self) -> int:
        """Allocate a new PID"""
        pid = self.next_pid
        self.next_pid += 1
        return pid
        
    def cleanup(self):
        """Cleanup all processes"""
        for process in list(self.processes.values()):
            if process.state == ProcessState.RUNNING:
                process.terminate()
                
class AppProcess:
    """
    KOS Application Process
    """
    
    def __init__(self, pid: int, executable: str, args: List[str],
                 env: Dict[str, str], working_dir: Optional[str] = None,
                 capture_output: bool = False):
        self.pid = pid
        self.executable = executable
        self.args = args
        self.env = env
        self.working_dir = working_dir
        self.capture_output = capture_output
        
        # Process state
        self.state = ProcessState.CREATED
        self.proc: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.exit_code: Optional[int] = None
        
        # Resource tracking
        self.cpu_time = 0.0
        self.memory_usage = 0
        
        # Output capture
        self.stdout_data = []
        self.stderr_data = []
        self.output_thread: Optional[threading.Thread] = None
        
    def start(self) -> bool:
        """Start the process"""
        if self.state != ProcessState.CREATED:
            return False
            
        try:
            # Prepare command
            cmd = [self.executable] + self.args
            
            # Start process
            if self.capture_output:
                self.proc = subprocess.Popen(
                    cmd,
                    env=self.env,
                    cwd=self.working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Start output capture thread
                self.output_thread = threading.Thread(
                    target=self._capture_output,
                    daemon=True
                )
                self.output_thread.start()
            else:
                self.proc = subprocess.Popen(
                    cmd,
                    env=self.env,
                    cwd=self.working_dir
                )
                
            self.state = ProcessState.RUNNING
            self.start_time = time.time()
            
            # Start monitoring thread
            monitor_thread = threading.Thread(
                target=self._monitor_process,
                daemon=True
            )
            monitor_thread.start()
            
            return True
            
        except Exception as e:
            self.state = ProcessState.CRASHED
            print(f"Failed to start process: {e}")
            return False
            
    def send_signal(self, signal_num: int) -> bool:
        """Send signal to process"""
        if self.state != ProcessState.RUNNING or not self.proc:
            return False
            
        try:
            self.proc.send_signal(signal_num)
            return True
        except Exception:
            return False
            
    def terminate(self) -> bool:
        """Terminate the process"""
        return self.send_signal(signal.SIGTERM)
        
    def kill(self) -> bool:
        """Kill the process"""
        return self.send_signal(signal.SIGKILL)
        
    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """Wait for process to complete"""
        if not self.proc:
            return self.exit_code
            
        try:
            exit_code = self.proc.wait(timeout=timeout)
            self.exit_code = exit_code
            self.state = ProcessState.STOPPED
            return exit_code
        except subprocess.TimeoutExpired:
            return None
            
    def get_output(self) -> tuple[str, str]:
        """Get captured output"""
        stdout = ''.join(self.stdout_data)
        stderr = ''.join(self.stderr_data)
        return stdout, stderr
        
    def _capture_output(self):
        """Capture process output"""
        if not self.proc:
            return
            
        # Read stdout
        if self.proc.stdout:
            for line in self.proc.stdout:
                self.stdout_data.append(line)
                
        # Read stderr
        if self.proc.stderr:
            for line in self.proc.stderr:
                self.stderr_data.append(line)
                
    def _monitor_process(self):
        """Monitor process state"""
        if not self.proc:
            return
            
        # Wait for process to complete
        exit_code = self.proc.wait()
        self.exit_code = exit_code
        
        # Update state
        if exit_code == 0:
            self.state = ProcessState.STOPPED
        else:
            self.state = ProcessState.CRASHED
            
        # Calculate CPU time
        if self.start_time:
            self.cpu_time = time.time() - self.start_time
            
    def __repr__(self):
        return f"<AppProcess pid={self.pid} executable={self.executable} state={self.state.value}>"

# Global runtime instance
_runtime = None

def get_runtime() -> KOSRuntime:
    """Get global KOS runtime instance"""
    global _runtime
    if _runtime is None:
        _runtime = KOSRuntime()
    return _runtime
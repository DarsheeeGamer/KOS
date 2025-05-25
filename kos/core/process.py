"""
KOS Process Management

This module provides process management capabilities for KOS, including
process creation, scheduling, and inter-process communication.
"""

import os
import sys
import time
import uuid
import signal
import logging
import threading
import subprocess
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.core.process')

# Process manager state
_process_state = {
    'initialized': False,
    'processes': {},
    'next_pid': 1000,
    'scheduler_running': False,
    'current_process': None,
    'process_callbacks': {}
}

# Locks
_process_lock = threading.RLock()
_scheduler_lock = threading.RLock()


class ProcessState(Enum):
    """Process states"""
    NEW = "new"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    TERMINATED = "terminated"


class ProcessPriority(Enum):
    """Process priorities"""
    IDLE = 0
    LOW = 1
    BELOW_NORMAL = 2
    NORMAL = 3
    ABOVE_NORMAL = 4
    HIGH = 5
    REALTIME = 6


class Process:
    """Process class"""
    
    def __init__(self, name, command=None, args=None, env=None, cwd=None, priority=ProcessPriority.NORMAL, parent_pid=None):
        """
        Initialize a process
        
        Args:
            name: Process name
            command: Command to execute (None for system processes)
            args: Command arguments
            env: Environment variables
            cwd: Current working directory
            priority: Process priority
            parent_pid: Parent process ID
        """
        self.pid = _get_next_pid()
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd or os.getcwd()
        self.priority = priority
        self.parent_pid = parent_pid
        
        self.creation_time = time.time()
        self.start_time = None
        self.end_time = None
        
        self.state = ProcessState.NEW
        self.exit_code = None
        
        self._process = None
        self._thread = None
        self._children = set()
    
    def start(self):
        """Start the process"""
        if self.state != ProcessState.NEW:
            return False
        
        if self.command:
            # External process
            try:
                full_command = [self.command] + self.args
                self._process = subprocess.Popen(
                    full_command,
                    env=self.env,
                    cwd=self.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self._thread = threading.Thread(target=self._monitor_process)
                self._thread.daemon = True
                self._thread.start()
                
                self.state = ProcessState.RUNNING
                self.start_time = time.time()
                
                logger.info(f"Started process {self.pid} ({self.name}): {self.command}")
                return True
            
            except Exception as e:
                logger.error(f"Error starting process {self.pid}: {e}")
                self.state = ProcessState.TERMINATED
                self.exit_code = 1
                self.end_time = time.time()
                return False
        else:
            # System process
            self.state = ProcessState.RUNNING
            self.start_time = time.time()
            logger.info(f"Started system process {self.pid} ({self.name})")
            return True
    
    def _monitor_process(self):
        """Monitor the external process"""
        if not self._process:
            return
        
        # Wait for process to complete
        stdout, stderr = self._process.communicate()
        exit_code = self._process.returncode
        
        with _process_lock:
            self.state = ProcessState.TERMINATED
            self.exit_code = exit_code
            self.end_time = time.time()
        
        # Notify callbacks
        _notify_process_state_change(self.pid, self.state)
        
        logger.info(f"Process {self.pid} ({self.name}) terminated with exit code {exit_code}")
    
    def terminate(self):
        """Terminate the process"""
        if self.state == ProcessState.TERMINATED:
            return True
        
        if self._process:
            try:
                self._process.terminate()
                return True
            except Exception as e:
                logger.error(f"Error terminating process {self.pid}: {e}")
                return False
        else:
            # System process
            with _process_lock:
                self.state = ProcessState.TERMINATED
                self.exit_code = 0
                self.end_time = time.time()
            
            # Notify callbacks
            _notify_process_state_change(self.pid, self.state)
            
            logger.info(f"Terminated system process {self.pid} ({self.name})")
            return True
    
    def kill(self):
        """Kill the process"""
        if self.state == ProcessState.TERMINATED:
            return True
        
        if self._process:
            try:
                self._process.kill()
                return True
            except Exception as e:
                logger.error(f"Error killing process {self.pid}: {e}")
                return False
        else:
            # Same as terminate for system processes
            return self.terminate()
    
    def get_status(self):
        """
        Get process status
        
        Returns:
            Process status
        """
        # Get current resource usage if process is running
        cpu_percent = 0
        memory_percent = 0
        
        if self._process and self.state == ProcessState.RUNNING:
            try:
                import psutil
                proc = psutil.Process(self._process.pid)
                cpu_percent = proc.cpu_percent(interval=0.1)
                memory_percent = proc.memory_percent()
            except Exception as e:
                logger.debug(f"Error getting process stats: {e}")
        
        return {
            'pid': self.pid,
            'name': self.name,
            'command': self.command,
            'args': self.args,
            'cwd': self.cwd,
            'state': self.state.value,
            'priority': self.priority.value,
            'parent_pid': self.parent_pid,
            'creation_time': self.creation_time,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'runtime': (self.end_time or time.time()) - (self.start_time or self.creation_time) if self.start_time else 0,
            'exit_code': self.exit_code,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'children': list(self._children)
        }
    
    def suspend(self):
        """Suspend the process"""
        if self.state != ProcessState.RUNNING:
            return False
        
        if self._process:
            try:
                self._process.send_signal(signal.SIGSTOP)
                self.state = ProcessState.WAITING
                _notify_process_state_change(self.pid, self.state)
                return True
            except Exception as e:
                logger.error(f"Error suspending process {self.pid}: {e}")
                return False
        else:
            # System process
            with _process_lock:
                self.state = ProcessState.WAITING
            
            # Notify callbacks
            _notify_process_state_change(self.pid, self.state)
            
            logger.info(f"Suspended system process {self.pid} ({self.name})")
            return True
    
    def resume(self):
        """Resume the process"""
        if self.state != ProcessState.WAITING:
            return False
        
        if self._process:
            try:
                self._process.send_signal(signal.SIGCONT)
                self.state = ProcessState.RUNNING
                _notify_process_state_change(self.pid, self.state)
                return True
            except Exception as e:
                logger.error(f"Error resuming process {self.pid}: {e}")
                return False
        else:
            # System process
            with _process_lock:
                self.state = ProcessState.RUNNING
            
            # Notify callbacks
            _notify_process_state_change(self.pid, self.state)
            
            logger.info(f"Resumed system process {self.pid} ({self.name})")
            return True
    
    def add_child(self, pid):
        """Add a child process"""
        self._children.add(pid)
    
    def remove_child(self, pid):
        """Remove a child process"""
        if pid in self._children:
            self._children.remove(pid)


def _get_next_pid():
    """
    Get the next available process ID
    
    Returns:
        Process ID
    """
    with _process_lock:
        pid = _process_state['next_pid']
        _process_state['next_pid'] += 1
        return pid


def _notify_process_state_change(pid, state):
    """
    Notify process state change
    
    Args:
        pid: Process ID
        state: New state
    """
    callbacks = _process_state['process_callbacks'].get(pid, [])
    callbacks.extend(_process_state['process_callbacks'].get('all', []))
    
    for callback in callbacks:
        try:
            callback(pid, state)
        except Exception as e:
            logger.error(f"Error in process state change callback: {e}")


def create_process(name, command=None, args=None, env=None, cwd=None, 
                  priority=ProcessPriority.NORMAL, parent_pid=None, start=True):
    """
    Create a new process
    
    Args:
        name: Process name
        command: Command to execute
        args: Command arguments
        env: Environment variables
        cwd: Current working directory
        priority: Process priority
        parent_pid: Parent process ID
        start: Start the process immediately
    
    Returns:
        Process ID
    """
    # Create process object
    process = Process(
        name=name,
        command=command,
        args=args,
        env=env,
        cwd=cwd,
        priority=priority,
        parent_pid=parent_pid
    )
    
    # Add to parent's children
    if parent_pid and parent_pid in _process_state['processes']:
        _process_state['processes'][parent_pid].add_child(process.pid)
    
    # Add to process list
    with _process_lock:
        _process_state['processes'][process.pid] = process
    
    # Start if requested
    if start:
        process.start()
    
    return process.pid


def terminate_process(pid, force=False):
    """
    Terminate a process
    
    Args:
        pid: Process ID
        force: Force termination (kill)
    
    Returns:
        Success status
    """
    with _process_lock:
        process = _process_state['processes'].get(pid)
        if not process:
            return False
    
    # Terminate or kill the process
    if force:
        return process.kill()
    else:
        return process.terminate()


def get_process(pid):
    """
    Get a process by ID
    
    Args:
        pid: Process ID
    
    Returns:
        Process object
    """
    with _process_lock:
        return _process_state['processes'].get(pid)


def get_all_processes():
    """
    Get all processes
    
    Returns:
        Dictionary of processes by PID
    """
    with _process_lock:
        return dict(_process_state['processes'])


def get_process_status(pid):
    """
    Get process status
    
    Args:
        pid: Process ID
    
    Returns:
        Process status
    """
    with _process_lock:
        process = _process_state['processes'].get(pid)
        if not process:
            return None
    
    return process.get_status()


def register_process_callback(pid, callback):
    """
    Register a callback for process state changes
    
    Args:
        pid: Process ID or 'all' for all processes
        callback: Callback function
    
    Returns:
        Success status
    """
    with _process_lock:
        if pid not in _process_state['process_callbacks']:
            _process_state['process_callbacks'][pid] = []
        
        _process_state['process_callbacks'][pid].append(callback)
        return True


def unregister_process_callback(pid, callback):
    """
    Unregister a process callback
    
    Args:
        pid: Process ID
        callback: Callback function
    
    Returns:
        Success status
    """
    with _process_lock:
        if pid in _process_state['process_callbacks']:
            if callback in _process_state['process_callbacks'][pid]:
                _process_state['process_callbacks'][pid].remove(callback)
                return True
    
    return False


def _scheduler_thread():
    """Process scheduler thread"""
    logger.info("Process scheduler started")
    
    while _process_state['scheduler_running']:
        # Simple round-robin scheduler
        try:
            with _scheduler_lock:
                # Get all runnable processes
                runnable = []
                for pid, process in _process_state['processes'].items():
                    if process.state == ProcessState.READY:
                        runnable.append((pid, process))
                
                # If we have a current process, add it back to the runnable list
                current_pid = _process_state['current_process']
                if current_pid:
                    current = _process_state['processes'].get(current_pid)
                    if current and current.state == ProcessState.RUNNING:
                        current.state = ProcessState.READY
                        _process_state['current_process'] = None
                
                # If we have runnable processes, schedule the next one
                if runnable:
                    # Sort by priority (higher value = higher priority)
                    runnable.sort(key=lambda x: x[1].priority.value, reverse=True)
                    
                    # Schedule the highest priority process
                    next_pid, next_process = runnable[0]
                    next_process.state = ProcessState.RUNNING
                    _process_state['current_process'] = next_pid
                    
                    # Notify state change
                    _notify_process_state_change(next_pid, ProcessState.RUNNING)
        
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
        
        # Sleep for a bit (simple time-slicing)
        time.sleep(0.1)
    
    logger.info("Process scheduler stopped")


def start_scheduler():
    """Start the process scheduler"""
    with _scheduler_lock:
        if _process_state['scheduler_running']:
            return False
        
        _process_state['scheduler_running'] = True
        
        # Start scheduler thread
        scheduler_thread = threading.Thread(target=_scheduler_thread)
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        return True


def stop_scheduler():
    """Stop the process scheduler"""
    with _scheduler_lock:
        if not _process_state['scheduler_running']:
            return False
        
        _process_state['scheduler_running'] = False
        return True


def initialize():
    """
    Initialize the process manager
    
    Returns:
        Success status
    """
    global _process_state
    
    with _process_lock:
        if _process_state['initialized']:
            logger.warning("Process manager already initialized")
            return True
        
        logger.info("Initializing process manager")
        
        # Create kernel process (PID 1)
        kernel_proc = Process(name="kernel", priority=ProcessPriority.REALTIME)
        kernel_proc.state = ProcessState.RUNNING
        kernel_proc.start_time = time.time()
        kernel_proc.pid = 1
        
        _process_state['processes'][1] = kernel_proc
        _process_state['current_process'] = 1
        
        # Start scheduler
        start_scheduler()
        
        # Mark as initialized
        _process_state['initialized'] = True
        
        logger.info("Process manager initialized")
        
        return True

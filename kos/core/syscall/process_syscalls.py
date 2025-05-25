"""
KOS Process System Calls

This module provides system calls for process management, including creation,
termination, scheduling, and inter-process communication.
"""

import logging
import time
import os
from typing import Dict, List, Any, Optional, Tuple

from . import syscall, SyscallCategory, SyscallResult, SyscallError
from .. import process
from ..process import ProcessState, ProcessPriority

logger = logging.getLogger('KOS.syscall.process')

@syscall(SyscallCategory.PROCESS)
def create_process(name: str, command: str = None, args: List[str] = None, 
                  env: Dict[str, str] = None, cwd: str = None, 
                  priority: ProcessPriority = ProcessPriority.NORMAL,
                  parent_pid: int = None) -> int:
    """
    Create a new process
    
    Args:
        name: Process name
        command: Command to execute (None for system process)
        args: Command arguments
        env: Environment variables
        cwd: Current working directory
        priority: Process priority
        parent_pid: Parent process ID
    
    Returns:
        Process ID or error
    """
    try:
        # Validate arguments
        if not name:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Process name cannot be empty")
        
        if command and not os.path.exists(command):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Command not found: {command}")
        
        if parent_pid and not process.process_exists(parent_pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Parent process {parent_pid} not found")
        
        # Create the process
        pid = process.create_process(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            cwd=cwd,
            priority=priority,
            parent_pid=parent_pid
        )
        
        if pid is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message="Failed to create process")
        
        return pid
    
    except Exception as e:
        logger.error(f"Error creating process: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def terminate_process(pid: int, force: bool = False) -> bool:
    """
    Terminate a process
    
    Args:
        pid: Process ID
        force: Force termination
    
    Returns:
        Success status or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Terminate the process
        result = process.terminate_process(pid, force)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to terminate process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error terminating process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def get_process_info(pid: int) -> Dict[str, Any]:
    """
    Get process information
    
    Args:
        pid: Process ID
    
    Returns:
        Process information or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Get process status
        status = process.get_process_status(pid)
        
        if not status:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to get process information for {pid}")
        
        return status
    
    except Exception as e:
        logger.error(f"Error getting process information for {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def get_all_processes() -> Dict[int, Dict[str, Any]]:
    """
    Get information about all processes
    
    Returns:
        Dictionary of process information indexed by PID or error
    """
    try:
        # Get all processes
        all_processes = process.get_all_processes()
        
        # Convert Process objects to dictionaries
        result = {}
        for pid, proc in all_processes.items():
            result[pid] = proc.get_status()
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting all processes: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def set_process_priority(pid: int, priority: ProcessPriority) -> bool:
    """
    Set process priority
    
    Args:
        pid: Process ID
        priority: New priority
    
    Returns:
        Success status or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Set process priority
        result = process.set_process_priority(pid, priority)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to set priority for process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting priority for process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def suspend_process(pid: int) -> bool:
    """
    Suspend a process
    
    Args:
        pid: Process ID
    
    Returns:
        Success status or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Suspend the process
        result = process.suspend_process(pid)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to suspend process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error suspending process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def resume_process(pid: int) -> bool:
    """
    Resume a suspended process
    
    Args:
        pid: Process ID
    
    Returns:
        Success status or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Resume the process
        result = process.resume_process(pid)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to resume process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error resuming process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def wait_process(pid: int, timeout: float = None) -> Dict[str, Any]:
    """
    Wait for a process to terminate
    
    Args:
        pid: Process ID
        timeout: Maximum time to wait in seconds (None for infinite)
    
    Returns:
        Process exit information or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Wait for the process
        start_time = time.time()
        
        while process.process_exists(pid):
            # Check if process has terminated
            status = process.get_process_status(pid)
            if status['state'] == ProcessState.TERMINATED:
                return {
                    'pid': pid,
                    'exit_code': status.get('exit_code', 0),
                    'runtime': status.get('runtime', 0),
                    'state': status['state'].name
                }
            
            # Check timeout
            if timeout is not None and (time.time() - start_time) > timeout:
                return SyscallResult(False, SyscallError.TIMEOUT, 
                                   message=f"Timeout waiting for process {pid}")
            
            # Sleep briefly to avoid busy waiting
            time.sleep(0.1)
        
        # Process no longer exists
        return SyscallResult(False, SyscallError.NOT_FOUND, 
                           message=f"Process {pid} not found")
    
    except Exception as e:
        logger.error(f"Error waiting for process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def get_process_children(pid: int) -> List[int]:
    """
    Get child processes of a process
    
    Args:
        pid: Process ID
    
    Returns:
        List of child process IDs or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Get process children
        children = process.get_process_children(pid)
        
        return children
    
    except Exception as e:
        logger.error(f"Error getting children of process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.PROCESS)
def send_signal(pid: int, signal: int) -> bool:
    """
    Send a signal to a process
    
    Args:
        pid: Process ID
        signal: Signal number
    
    Returns:
        Success status or error
    """
    try:
        # Check if process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Send signal to the process
        result = process.send_signal(pid, signal)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to send signal {signal} to process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending signal {signal} to process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

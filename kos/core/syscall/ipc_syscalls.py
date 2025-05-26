"""
KOS IPC (Inter-Process Communication) System Calls

This module provides system calls for inter-process communication, including
pipes, signals, shared memory, message queues, and semaphores. These syscalls
are backed by real OS-level IPC mechanisms for robust multi-process communication.
"""

import logging
import time
import os
from typing import Dict, List, Any, Optional, Union, Tuple

from . import syscall, SyscallCategory, SyscallResult, SyscallError
from .. import process
from .. import ipc
from ..memory import MemoryPermission

logger = logging.getLogger('KOS.syscall.ipc')

@syscall(SyscallCategory.IPC)
def create_pipe(name: str = None, buffer_size: int = 4096) -> str:
    """
    Create a new pipe for inter-process communication
    
    Args:
        name: Optional pipe name
        buffer_size: Pipe buffer size in bytes
    
    Returns:
        Pipe ID or error
    """
    try:
        # Validate arguments
        if buffer_size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Buffer size must be positive")
        
        # Create the pipe using our real IPC implementation
        pipe_id = ipc.create_pipe(name=name, buffer_size=buffer_size)
        
        if not pipe_id:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR,
                               message="Failed to create pipe")
        
        return pipe_id
    
    except Exception as e:
        logger.error(f"Error creating pipe: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def close_pipe(pipe_id: str) -> bool:
    """
    Close a pipe
    
    Args:
        pipe_id: Pipe ID
    
    Returns:
        Success status or error
    """
    try:
        # Close the pipe using our real IPC implementation
        success = ipc.close_pipe(pipe_id)
        
        if not success:
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Failed to close pipe {pipe_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error closing pipe {pipe_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def write_pipe(pipe_id: str, data: bytes, nonblocking: bool = False) -> int:
    """
    Write data to a pipe
    
    Args:
        pipe_id: Pipe ID
        data: Data to write
        nonblocking: Whether to return immediately if the pipe is full
    
    Returns:
        Number of bytes written or error
    """
    try:
        # Validate arguments
        if not data:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Data cannot be empty")
        
        # Write to the pipe using our real IPC implementation
        bytes_written = ipc.write_pipe(pipe_id, data, nonblocking)
        
        if bytes_written == 0 and len(data) > 0:
            # Could be full pipe or non-existent pipe
            return SyscallResult(False, SyscallError.RESOURCE_BUSY,
                               message="Pipe is full or does not exist")
        
        return bytes_written
    
    except Exception as e:
        logger.error(f"Error writing to pipe {pipe_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def read_pipe(pipe_id: str, size: int, nonblocking: bool = False) -> bytes:
    """
    Read data from a pipe
    
    Args:
        pipe_id: Pipe ID
        size: Maximum number of bytes to read
        nonblocking: Whether to return immediately if the pipe is empty
    
    Returns:
        Data read or error
    """
    try:
        # Validate arguments
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Size must be positive")
        
        # Read from the pipe using our real IPC implementation
        data = ipc.read_pipe(pipe_id, size, nonblocking)
        
        # Empty data could mean pipe is empty or an error occurred
        # In a real implementation we would distinguish these cases
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading from pipe {pipe_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def create_message_queue(name: str = None, max_messages: int = 100, 
                        max_size: int = 4096) -> str:
    """
    Create a new message queue
    
    Args:
        name: Optional queue name
        max_messages: Maximum number of messages in the queue
        max_size: Maximum message size in bytes
    
    Returns:
        Queue ID or error
    """
    try:
        # Validate arguments
        if max_messages <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Maximum number of messages must be positive")
        
        if max_size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Maximum message size must be positive")
        
        # Create the message queue using our real IPC implementation
        queue_id = ipc.create_message_queue(name=name, max_messages=max_messages, max_size=max_size)
        
        if not queue_id:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR,
                               message="Failed to create message queue")
        
        return queue_id
    
    except Exception as e:
        logger.error(f"Error creating message queue: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def delete_message_queue(queue_id: str) -> bool:
    """
    Delete a message queue
    
    Args:
        queue_id: Queue ID
    
    Returns:
        Success status or error
    """
    try:
        # Delete the message queue using our real IPC implementation
        success = ipc.delete_message_queue(queue_id)
        
        if not success:
            return SyscallResult(False, SyscallError.NOT_FOUND,
                               message=f"Failed to delete message queue {queue_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting message queue {queue_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def send_message(queue_id: str, message: Any, msg_type: int = 0, 
                priority: int = 0, nonblocking: bool = False) -> bool:
    """
    Send a message to a message queue
    
    Args:
        queue_id: Queue ID
        message: Message data (must be serializable)
        msg_type: Message type (0-255)
        priority: Message priority (0-255, higher is more important)
        nonblocking: Whether to return immediately if the queue is full
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not message:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Message cannot be empty")
        
        # Validate type and priority
        msg_type = max(0, min(255, int(msg_type)))
        priority = max(0, min(255, int(priority)))
        
        # Send the message using our real IPC implementation
        success = ipc.send_message(queue_id, message, msg_type, priority, nonblocking)
        
        if not success:
            return SyscallResult(False, SyscallError.RESOURCE_BUSY, 
                               message=f"Message queue {queue_id} is full or does not exist")
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending message to queue {queue_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def receive_message(queue_id: str, msg_type: int = 0, 
                   nonblocking: bool = False) -> Dict[str, Any]:
    """
    Receive a message from a message queue
    
    Args:
        queue_id: Queue ID
        msg_type: Message type to receive (0 for any type)
        nonblocking: Whether to return immediately if no message is available
    
    Returns:
        Message data or error
    """
    try:
        # Validate arguments
        msg_type = max(0, min(255, int(msg_type)))
        
        # Receive a message using our real IPC implementation
        message = ipc.receive_message(queue_id, msg_type, nonblocking)
        
        if message is None:
            return SyscallResult(False, SyscallError.RESOURCE_UNAVAILABLE, 
                               message=f"No message available in queue {queue_id} or queue does not exist")
        
        return message
    
    except Exception as e:
        logger.error(f"Error receiving message from queue {queue_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def send_signal_to_process(pid: int, signal: int, data: Any = None) -> bool:
    """
    Send a signal to a process
    
    Args:
        pid: Process ID
        signal: Signal number
        data: Optional signal data (must be serializable)
    
    Returns:
        Success status or error
    """
    try:
        # Check if the process exists
        if not process.process_exists(pid):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Process {pid} not found")
        
        # Send the signal using our real IPC implementation
        success = ipc.send_signal(pid, signal, data)
        
        if not success:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to send signal {signal} to process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending signal {signal} to process {pid}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def register_signal_handler(signal: int, handler_func: callable) -> bool:
    """
    Register a handler for a specific signal
    
    Args:
        signal: Signal number
        handler_func: Function to call when signal is received
    
    Returns:
        Success status or error
    """
    try:
        # Register the signal handler using our real IPC implementation
        success = ipc.register_signal_handler(signal, handler_func)
        
        if not success:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to register handler for signal {signal}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error registering signal handler for signal {signal}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def create_shared_memory(name: str = None, size: int = 4096, 
                        permissions: MemoryPermission = MemoryPermission.READ_WRITE) -> str:
    """
    Create a shared memory segment
    
    Args:
        name: Optional segment name
        size: Size of the segment in bytes
        permissions: Memory access permissions
    
    Returns:
        Shared memory ID or error
    """
    try:
        # Validate arguments
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Size must be positive")
        
        # Create the shared memory segment using our real IPC implementation
        shm_id = ipc.create_shared_memory(name=name, size=size, permissions=permissions)
        
        if not shm_id:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR,
                               message="Failed to create shared memory segment")
        
        return shm_id
    
    except Exception as e:
        logger.error(f"Error creating shared memory: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def delete_shared_memory(shm_id: str) -> bool:
    """
    Delete a shared memory segment
    
    Args:
        shm_id: Shared memory ID
    
    Returns:
        Success status or error
    """
    try:
        # Delete the shared memory segment using our real IPC implementation
        success = ipc.delete_shared_memory(shm_id)
        
        if not success:
            return SyscallResult(False, SyscallError.NOT_FOUND,
                               message=f"Failed to delete shared memory {shm_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting shared memory {shm_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def write_shared_memory(shm_id: str, data: bytes, offset: int = 0) -> int:
    """
    Write data to a shared memory segment
    
    Args:
        shm_id: Shared memory ID
        data: Data to write
        offset: Offset in the segment to write at
    
    Returns:
        Number of bytes written or error
    """
    try:
        # Validate arguments
        if offset < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Offset must be non-negative")
        
        if not data:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Data cannot be empty")
        
        # Write to shared memory using our real IPC implementation
        bytes_written = ipc.write_shared_memory(shm_id, data, offset)
        
        if bytes_written == 0 and len(data) > 0:
            return SyscallResult(False, SyscallError.RESOURCE_UNAVAILABLE,
                               message=f"Failed to write to shared memory {shm_id}")
        
        return bytes_written
    
    except Exception as e:
        logger.error(f"Error writing to shared memory {shm_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def read_shared_memory(shm_id: str, size: int, offset: int = 0) -> bytes:
    """
    Read data from a shared memory segment
    
    Args:
        shm_id: Shared memory ID
        size: Number of bytes to read
        offset: Offset in the segment to read from
    
    Returns:
        Data read or error
    """
    try:
        # Validate arguments
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Size must be positive")
        
        if offset < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Offset must be non-negative")
        
        # Read from shared memory using our real IPC implementation
        data = ipc.read_shared_memory(shm_id, size, offset)
        
        if data is None:
            return SyscallResult(False, SyscallError.RESOURCE_UNAVAILABLE,
                               message=f"Failed to read from shared memory {shm_id}")
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading from shared memory {shm_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def create_semaphore(name: str = None, value: int = 1, max_value: int = 1) -> str:
    """
    Create a new semaphore
    
    Args:
        name: Optional semaphore name
        value: Initial semaphore value
        max_value: Maximum semaphore value
    
    Returns:
        Semaphore ID or error
    """
    try:
        # Validate arguments
        if value < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Initial value must be non-negative")
        
        if max_value <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Maximum value must be positive")
        
        if value > max_value:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Initial value cannot exceed maximum value")
        
        # Create the semaphore using our real IPC implementation
        sem_id = ipc.create_semaphore(name=name, value=value, max_value=max_value)
        
        if not sem_id:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR,
                               message="Failed to create semaphore")
        
        return sem_id
    
    except Exception as e:
        logger.error(f"Error creating semaphore: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def delete_semaphore(sem_id: str) -> bool:
    """
    Delete a semaphore
    
    Args:
        sem_id: Semaphore ID
    
    Returns:
        Success status or error
    """
    try:
        # Delete the semaphore using our real IPC implementation
        success = ipc.delete_semaphore(sem_id)
        
        if not success:
            return SyscallResult(False, SyscallError.NOT_FOUND,
                               message=f"Failed to delete semaphore {sem_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting semaphore {sem_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def acquire_semaphore(sem_id: str, timeout: Optional[float] = None) -> bool:
    """
    Acquire (wait on) a semaphore
    
    Args:
        sem_id: Semaphore ID
        timeout: Maximum time to wait (None for indefinite)
    
    Returns:
        Success status or error
    """
    try:
        # Acquire the semaphore using our real IPC implementation
        success = ipc.acquire_semaphore(sem_id, timeout)
        
        if not success:
            return SyscallResult(False, SyscallError.RESOURCE_UNAVAILABLE,
                               message=f"Failed to acquire semaphore {sem_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error acquiring semaphore {sem_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.IPC)
def release_semaphore(sem_id: str) -> bool:
    """
    Release a semaphore
    
    Args:
        sem_id: Semaphore ID
    
    Returns:
        Success status or error
    """
    try:
        # Release the semaphore using our real IPC implementation
        success = ipc.release_semaphore(sem_id)
        
        if not success:
            return SyscallResult(False, SyscallError.RESOURCE_UNAVAILABLE,
                               message=f"Failed to release semaphore {sem_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error releasing semaphore {sem_id}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

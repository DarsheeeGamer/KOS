"""
KOS System Call Interface

This module provides the standardized API for user-space applications to request
kernel services. It serves as the boundary between user-space and kernel-space,
ensuring proper validation, security checks, and error handling.
"""

import logging
import inspect
import functools
import time
from enum import Enum, auto
from typing import Dict, Any, Callable, List, Tuple, Optional, Union

logger = logging.getLogger('KOS.syscall')

# System call registry
_syscalls = {}

# System call error codes
class SyscallError(Enum):
    SUCCESS = 0
    INVALID_ARGUMENT = 1
    PERMISSION_DENIED = 2
    NOT_FOUND = 3
    ALREADY_EXISTS = 4
    RESOURCE_BUSY = 5
    RESOURCE_UNAVAILABLE = 6
    INSUFFICIENT_RESOURCES = 7
    NOT_IMPLEMENTED = 8
    TIMEOUT = 9
    INTERRUPTED = 10
    IO_ERROR = 11
    INTERNAL_ERROR = 12
    NOT_SUPPORTED = 13
    INVALID_STATE = 14
    LIMIT_EXCEEDED = 15

class SyscallResult:
    """
    Result of a system call execution
    """
    def __init__(self, success: bool, error_code: SyscallError = SyscallError.SUCCESS, 
                 data: Any = None, message: str = None):
        self.success = success
        self.error_code = error_code
        self.data = data
        self.message = message
        self.timestamp = time.time()
    
    def __str__(self):
        if self.success:
            return f"SyscallResult(success=True, data={type(self.data) if self.data is not None else None})"
        else:
            return f"SyscallResult(success=False, error={self.error_code.name}, message='{self.message}')"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to a dictionary"""
        return {
            'success': self.success,
            'error_code': self.error_code.name if self.error_code else None,
            'data': self.data,
            'message': self.message,
            'timestamp': self.timestamp
        }

class SyscallCategory(Enum):
    """Categories of system calls"""
    PROCESS = auto()
    MEMORY = auto()
    FILESYSTEM = auto()
    DEVICE = auto()
    NETWORK = auto()
    SECURITY = auto()
    IPC = auto()
    TIME = auto()
    SYSTEM = auto()

def syscall(category: SyscallCategory, name: str = None):
    """
    Decorator to register a function as a system call
    
    Args:
        category: Category of the system call
        name: Optional name override (defaults to function name)
    
    Returns:
        Decorated function
    """
    def decorator(func):
        # Get function signature for parameter validation
        sig = inspect.signature(func)
        func_name = name or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            syscall_name = f"{category.name.lower()}.{func_name}"
            
            # Log the syscall invocation
            logger.debug(f"Syscall invoked: {syscall_name}")
            
            try:
                # Validate arguments against signature
                try:
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                except TypeError as e:
                    logger.error(f"Invalid arguments for syscall {syscall_name}: {e}")
                    return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                                        message=f"Invalid arguments: {e}")
                
                # Execute the system call
                start_time = time.time()
                result = func(*bound_args.args, **bound_args.kwargs)
                execution_time = time.time() - start_time
                
                # Log execution time for performance monitoring
                logger.debug(f"Syscall {syscall_name} executed in {execution_time:.6f} seconds")
                
                # Process the result
                if isinstance(result, SyscallResult):
                    return result
                else:
                    return SyscallResult(True, data=result)
                
            except Exception as e:
                logger.error(f"Error executing syscall {syscall_name}: {str(e)}", exc_info=True)
                return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))
        
        # Register the syscall
        syscall_id = f"{category.name.lower()}.{func_name}"
        _syscalls[syscall_id] = {
            'function': wrapper,
            'category': category,
            'name': func_name,
            'signature': sig,
            'doc': func.__doc__
        }
        
        return wrapper
    
    return decorator

def initialize() -> bool:
    """
    Initialize the syscall subsystem
    
    Returns:
        Success status
    """
    try:
        logger.info("Initializing system call interface")
        
        # Import syscall modules to register their functions
        from . import process_syscalls
        from . import memory_syscalls
        from . import filesystem_syscalls
        from . import ipc_syscalls
        from . import system_syscalls
        
        logger.info(f"System call interface initialized with {len(_syscalls)} syscalls")
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize system call interface: {e}")
        return False

def shutdown() -> bool:
    """
    Shutdown the syscall subsystem
    
    Returns:
        Success status
    """
    # Not much to do here since the syscall registry is just in-memory
    logger.info("Shutting down system call interface")
    return True

def get_syscall_info() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all registered system calls
    
    Returns:
        Dictionary of syscall information
    """
    return {
        syscall_id: {
            'category': info['category'].name,
            'name': info['name'],
            'signature': str(info['signature']),
            'doc': info['doc']
        }
        for syscall_id, info in _syscalls.items()
    }

def invoke_syscall(syscall_id: str, *args, **kwargs) -> SyscallResult:
    """
    Invoke a system call by its ID
    
    Args:
        syscall_id: ID of the system call to invoke
        *args: Positional arguments for the system call
        **kwargs: Keyword arguments for the system call
    
    Returns:
        Result of the system call
    """
    if syscall_id not in _syscalls:
        return SyscallResult(False, SyscallError.NOT_FOUND, 
                           message=f"System call '{syscall_id}' not found")
    
    return _syscalls[syscall_id]['function'](*args, **kwargs)

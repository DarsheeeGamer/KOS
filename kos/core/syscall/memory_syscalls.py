"""
KOS Memory System Calls

This module provides system calls for memory management, including allocation,
deallocation, and memory protection operations.
"""

import logging
from typing import Dict, Any, Optional

from . import syscall, SyscallCategory, SyscallResult, SyscallError
from .. import memory
from ..memory import MemoryType, MemoryPermission

logger = logging.getLogger('KOS.syscall.memory')

@syscall(SyscallCategory.MEMORY)
def allocate_memory(size: int, mem_type: MemoryType = MemoryType.USER, 
                   permissions: MemoryPermission = MemoryPermission.READ_WRITE,
                   name: str = None) -> int:
    """
    Allocate memory
    
    Args:
        size: Size of memory to allocate in bytes
        mem_type: Memory type
        permissions: Memory permissions
        name: Optional name for the memory block
    
    Returns:
        Memory address or error
    """
    try:
        # Validate arguments
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Memory size must be positive")
        
        # Allocate memory
        addr = memory.allocate_memory(size, mem_type, permissions, name)
        
        if addr is None or addr == 0:
            return SyscallResult(False, SyscallError.INSUFFICIENT_RESOURCES, 
                               message=f"Failed to allocate {size} bytes of memory")
        
        return addr
    
    except Exception as e:
        logger.error(f"Error allocating memory: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def free_memory(addr: int) -> bool:
    """
    Free allocated memory
    
    Args:
        addr: Memory address to free
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        # Check if the memory is allocated
        if not memory.is_allocated(addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Memory at address 0x{addr:x} is not allocated")
        
        # Free the memory
        result = memory.free_memory(addr)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to free memory at address 0x{addr:x}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error freeing memory at address 0x{addr:x}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def read_memory(addr: int, size: int) -> bytes:
    """
    Read data from memory
    
    Args:
        addr: Memory address
        size: Number of bytes to read
    
    Returns:
        Memory data or error
    """
    try:
        # Validate arguments
        if addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Size must be positive")
        
        # Check if the memory is allocated
        if not memory.is_allocated(addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Memory at address 0x{addr:x} is not allocated")
        
        # Check if we have permission to read this memory
        info = memory.get_memory_info(addr)
        if info and (info['permissions'] & MemoryPermission.READ) == 0:
            return SyscallResult(False, SyscallError.PERMISSION_DENIED, 
                               message=f"No read permission for memory at address 0x{addr:x}")
        
        # Read the memory
        data = memory.read_memory(addr, size)
        
        if data is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to read memory at address 0x{addr:x}")
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading memory at address 0x{addr:x}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def write_memory(addr: int, data: bytes) -> bool:
    """
    Write data to memory
    
    Args:
        addr: Memory address
        data: Data to write
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        if not data:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Data cannot be empty")
        
        # Check if the memory is allocated
        if not memory.is_allocated(addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Memory at address 0x{addr:x} is not allocated")
        
        # Check if we have permission to write to this memory
        info = memory.get_memory_info(addr)
        if info and (info['permissions'] & MemoryPermission.WRITE) == 0:
            return SyscallResult(False, SyscallError.PERMISSION_DENIED, 
                               message=f"No write permission for memory at address 0x{addr:x}")
        
        # Check if the data fits within the allocated memory
        if info and (addr + len(data) > addr + info['size']):
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message=f"Data exceeds allocated memory size at address 0x{addr:x}")
        
        # Write to the memory
        result = memory.write_memory(addr, data)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to write to memory at address 0x{addr:x}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error writing to memory at address 0x{addr:x}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def get_memory_info(addr: int = None) -> Dict[str, Any]:
    """
    Get memory information
    
    Args:
        addr: Memory address (None for global memory information)
    
    Returns:
        Memory information or error
    """
    try:
        # Get memory information
        if addr is None:
            # Get global memory information
            info = memory.get_memory_info()
        else:
            # Get information for a specific memory block
            if not memory.is_allocated(addr):
                return SyscallResult(False, SyscallError.NOT_FOUND, 
                                   message=f"Memory at address 0x{addr:x} is not allocated")
            
            info = memory.get_memory_info(addr)
        
        if info is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message="Failed to get memory information")
        
        return info
    
    except Exception as e:
        logger.error(f"Error getting memory information: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def set_memory_permissions(addr: int, permissions: MemoryPermission) -> bool:
    """
    Set memory permissions
    
    Args:
        addr: Memory address
        permissions: New permissions
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        # Check if the memory is allocated
        if not memory.is_allocated(addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Memory at address 0x{addr:x} is not allocated")
        
        # Set the permissions
        result = memory.set_memory_permissions(addr, permissions)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to set permissions for memory at address 0x{addr:x}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting permissions for memory at address 0x{addr:x}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def resize_memory(addr: int, new_size: int) -> int:
    """
    Resize allocated memory
    
    Args:
        addr: Memory address
        new_size: New size in bytes
    
    Returns:
        New memory address (may be different from original) or error
    """
    try:
        # Validate arguments
        if addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        if new_size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="New size must be positive")
        
        # Check if the memory is allocated
        if not memory.is_allocated(addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Memory at address 0x{addr:x} is not allocated")
        
        # Resize the memory
        new_addr = memory.resize_memory(addr, new_size)
        
        if new_addr is None or new_addr == 0:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to resize memory at address 0x{addr:x}")
        
        return new_addr
    
    except Exception as e:
        logger.error(f"Error resizing memory at address 0x{addr:x}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.MEMORY)
def copy_memory(src_addr: int, dst_addr: int, size: int) -> bool:
    """
    Copy memory from one location to another
    
    Args:
        src_addr: Source memory address
        dst_addr: Destination memory address
        size: Number of bytes to copy
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if src_addr <= 0 or dst_addr <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Invalid memory address")
        
        if size <= 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Size must be positive")
        
        # Check if the memory is allocated
        if not memory.is_allocated(src_addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Source memory at address 0x{src_addr:x} is not allocated")
        
        if not memory.is_allocated(dst_addr):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Destination memory at address 0x{dst_addr:x} is not allocated")
        
        # Check permissions
        src_info = memory.get_memory_info(src_addr)
        if src_info and (src_info['permissions'] & MemoryPermission.READ) == 0:
            return SyscallResult(False, SyscallError.PERMISSION_DENIED, 
                               message=f"No read permission for memory at address 0x{src_addr:x}")
        
        dst_info = memory.get_memory_info(dst_addr)
        if dst_info and (dst_info['permissions'] & MemoryPermission.WRITE) == 0:
            return SyscallResult(False, SyscallError.PERMISSION_DENIED, 
                               message=f"No write permission for memory at address 0x{dst_addr:x}")
        
        # Check if the data fits within the allocated memory
        if src_info and (src_addr + size > src_addr + src_info['size']):
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message=f"Copy size exceeds source memory size at address 0x{src_addr:x}")
        
        if dst_info and (dst_addr + size > dst_addr + dst_info['size']):
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message=f"Copy size exceeds destination memory size at address 0x{dst_addr:x}")
        
        # Read from source
        data = memory.read_memory(src_addr, size)
        
        if data is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to read memory at address 0x{src_addr:x}")
        
        # Write to destination
        result = memory.write_memory(dst_addr, data)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to write to memory at address 0x{dst_addr:x}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error copying memory: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

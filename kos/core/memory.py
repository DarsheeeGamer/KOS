"""
KOS Memory Management

This module provides memory management capabilities for KOS, including
memory allocation, paging, and virtual memory concepts.
"""

import os
import sys
import time
import logging
import threading
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.core.memory')

# Memory manager state
_memory_state = {
    'initialized': False,
    'total_memory': 0,
    'available_memory': 0,
    'allocated_memory': 0,
    'memory_regions': {},
    'page_size': 4096,  # 4KB pages by default
    'page_table': {},
    'memory_callbacks': {}
}

# Locks
_memory_lock = threading.RLock()
_allocation_lock = threading.RLock()


class MemoryPermission(Enum):
    """Memory region permissions"""
    READ = 1
    WRITE = 2
    EXECUTE = 4
    READ_WRITE = 3  # READ | WRITE
    READ_EXECUTE = 5  # READ | EXECUTE
    READ_WRITE_EXECUTE = 7  # READ | WRITE | EXECUTE


class MemoryType(Enum):
    """Memory region types"""
    FREE = "free"
    USER = "user"
    KERNEL = "kernel"
    SHARED = "shared"
    DEVICE = "device"
    RESERVED = "reserved"


class MemoryRegion:
    """Memory region class"""
    
    def __init__(self, address, size, mem_type=MemoryType.USER, permissions=MemoryPermission.READ_WRITE, owner=None, name=None):
        """
        Initialize a memory region
        
        Args:
            address: Base address
            size: Size in bytes
            mem_type: Memory region type
            permissions: Memory region permissions
            owner: Owner process ID
            name: Region name
        """
        self.address = address
        self.size = size
        self.end_address = address + size - 1
        self.mem_type = mem_type
        self.permissions = permissions
        self.owner = owner
        self.name = name or f"mem_{address:x}_{size:x}"
        self.allocation_time = time.time()
        self.last_access_time = self.allocation_time
        self.access_count = 0
        
        # For simulation, we'll use a bytearray to represent the memory
        self._memory = None
        if mem_type != MemoryType.FREE:
            self._memory = bytearray(size)
    
    def read(self, offset, size):
        """
        Read from the memory region
        
        Args:
            offset: Offset from base address
            size: Number of bytes to read
        
        Returns:
            Data read
        """
        if self.mem_type == MemoryType.FREE:
            raise ValueError("Cannot read from a free memory region")
        
        if not (self.permissions == MemoryPermission.READ or 
                self.permissions == MemoryPermission.READ_WRITE or
                self.permissions == MemoryPermission.READ_EXECUTE or
                self.permissions == MemoryPermission.READ_WRITE_EXECUTE):
            raise ValueError("Memory region does not have read permission")
        
        if offset < 0 or offset + size > self.size:
            raise ValueError("Read operation out of bounds")
        
        self.last_access_time = time.time()
        self.access_count += 1
        
        return bytes(self._memory[offset:offset+size])
    
    def write(self, offset, data):
        """
        Write to the memory region
        
        Args:
            offset: Offset from base address
            data: Data to write
        
        Returns:
            Number of bytes written
        """
        if self.mem_type == MemoryType.FREE:
            raise ValueError("Cannot write to a free memory region")
        
        if not (self.permissions == MemoryPermission.WRITE or 
                self.permissions == MemoryPermission.READ_WRITE or
                self.permissions == MemoryPermission.READ_WRITE_EXECUTE):
            raise ValueError("Memory region does not have write permission")
        
        if offset < 0 or offset + len(data) > self.size:
            raise ValueError("Write operation out of bounds")
        
        self.last_access_time = time.time()
        self.access_count += 1
        
        self._memory[offset:offset+len(data)] = data
        return len(data)
    
    def execute(self, offset, size):
        """
        Execute from the memory region (simulated)
        
        Args:
            offset: Offset from base address
            size: Number of bytes to execute
        
        Returns:
            Execution result
        """
        if self.mem_type == MemoryType.FREE:
            raise ValueError("Cannot execute from a free memory region")
        
        if not (self.permissions == MemoryPermission.EXECUTE or 
                self.permissions == MemoryPermission.READ_EXECUTE or
                self.permissions == MemoryPermission.READ_WRITE_EXECUTE):
            raise ValueError("Memory region does not have execute permission")
        
        if offset < 0 or offset + size > self.size:
            raise ValueError("Execute operation out of bounds")
        
        self.last_access_time = time.time()
        self.access_count += 1
        
        # This is a simulation, so we'll just return a success status
        return True
    
    def can_merge(self, other):
        """
        Check if this region can be merged with another
        
        Args:
            other: Other memory region
        
        Returns:
            True if regions can be merged, False otherwise
        """
        # Can only merge free regions
        if self.mem_type != MemoryType.FREE or other.mem_type != MemoryType.FREE:
            return False
        
        # Regions must be adjacent
        return (self.end_address + 1 == other.address or
                other.end_address + 1 == self.address)
    
    def merge(self, other):
        """
        Merge this region with another
        
        Args:
            other: Other memory region
        
        Returns:
            New merged memory region
        """
        if not self.can_merge(other):
            raise ValueError("Cannot merge non-adjacent or non-free regions")
        
        # Create the new region at the lower address
        if self.address < other.address:
            start = self.address
            size = self.size + other.size
        else:
            start = other.address
            size = self.size + other.size
        
        return MemoryRegion(
            address=start,
            size=size,
            mem_type=MemoryType.FREE,
            permissions=MemoryPermission.READ_WRITE,
            owner=None,
            name=f"free_{start:x}_{size:x}"
        )
    
    def split(self, size):
        """
        Split this region into two
        
        Args:
            size: Size of the first part
        
        Returns:
            Tuple of (first_part, second_part)
        """
        if size <= 0 or size >= self.size:
            raise ValueError("Invalid split size")
        
        first = MemoryRegion(
            address=self.address,
            size=size,
            mem_type=self.mem_type,
            permissions=self.permissions,
            owner=self.owner,
            name=f"{self.name}_part1"
        )
        
        second = MemoryRegion(
            address=self.address + size,
            size=self.size - size,
            mem_type=self.mem_type,
            permissions=self.permissions,
            owner=self.owner,
            name=f"{self.name}_part2"
        )
        
        # Copy data if needed
        if self._memory:
            first._memory = bytearray(self._memory[:size])
            second._memory = bytearray(self._memory[size:])
        
        return (first, second)
    
    def get_info(self):
        """
        Get region information
        
        Returns:
            Region information
        """
        return {
            'address': self.address,
            'size': self.size,
            'end_address': self.end_address,
            'type': self.mem_type.value,
            'permissions': self.permissions.value,
            'owner': self.owner,
            'name': self.name,
            'allocation_time': self.allocation_time,
            'last_access_time': self.last_access_time,
            'access_count': self.access_count
        }


class Page:
    """Memory page class"""
    
    def __init__(self, physical_address, size=None, permissions=MemoryPermission.READ_WRITE, owner=None):
        """
        Initialize a memory page
        
        Args:
            physical_address: Physical address
            size: Page size
            permissions: Page permissions
            owner: Owner process ID
        """
        self.physical_address = physical_address
        self.size = size or _memory_state['page_size']
        self.permissions = permissions
        self.owner = owner
        self.present = True
        self.dirty = False
        self.accessed = False
        self.creation_time = time.time()
        self.last_access_time = self.creation_time
        self.access_count = 0
    
    def mark_accessed(self):
        """Mark the page as accessed"""
        self.accessed = True
        self.last_access_time = time.time()
        self.access_count += 1
    
    def mark_dirty(self):
        """Mark the page as dirty"""
        self.dirty = True
    
    def get_info(self):
        """
        Get page information
        
        Returns:
            Page information
        """
        return {
            'physical_address': self.physical_address,
            'size': self.size,
            'permissions': self.permissions.value,
            'owner': self.owner,
            'present': self.present,
            'dirty': self.dirty,
            'accessed': self.accessed,
            'creation_time': self.creation_time,
            'last_access_time': self.last_access_time,
            'access_count': self.access_count
        }


def _find_free_region(size, alignment=8):
    """
    Find a free memory region of at least size bytes
    
    Args:
        size: Required size in bytes
        alignment: Address alignment requirement
    
    Returns:
        Address of free region, or None if not found
    """
    with _allocation_lock:
        # Find all free regions
        free_regions = [region for region in _memory_state['memory_regions'].values()
                        if region.mem_type == MemoryType.FREE and region.size >= size]
        
        # Sort by size (smallest first) to minimize fragmentation
        free_regions.sort(key=lambda r: r.size)
        
        for region in free_regions:
            # Check alignment
            aligned_address = region.address
            if aligned_address % alignment != 0:
                aligned_address = ((aligned_address // alignment) + 1) * alignment
            
            # Check if there's still enough space after alignment
            if aligned_address + size <= region.end_address + 1:
                return region, aligned_address
        
        # No suitable region found
        return None, 0


def allocate_memory(size, mem_type=MemoryType.USER, permissions=MemoryPermission.READ_WRITE, owner=None, name=None, alignment=8):
    """
    Allocate memory
    
    Args:
        size: Size in bytes
        mem_type: Memory type
        permissions: Memory permissions
        owner: Owner process ID
        name: Region name
        alignment: Address alignment
    
    Returns:
        Allocated memory address, or None if allocation failed
    """
    if size <= 0:
        return None
    
    with _allocation_lock:
        region, address = _find_free_region(size, alignment)
        
        if not region:
            logger.error(f"Failed to allocate {size} bytes: no free memory")
            return None
        
        # Calculate how to split the region
        if address > region.address:
            # Need to create a free region at the beginning
            pre_size = address - region.address
            free_pre = MemoryRegion(
                address=region.address,
                size=pre_size,
                mem_type=MemoryType.FREE,
                permissions=MemoryPermission.READ_WRITE,
                owner=None,
                name=f"free_{region.address:x}_{pre_size:x}"
            )
            _memory_state['memory_regions'][free_pre.address] = free_pre
        
        if address + size < region.end_address + 1:
            # Need to create a free region at the end
            post_size = region.end_address + 1 - (address + size)
            free_post = MemoryRegion(
                address=address + size,
                size=post_size,
                mem_type=MemoryType.FREE,
                permissions=MemoryPermission.READ_WRITE,
                owner=None,
                name=f"free_{address + size:x}_{post_size:x}"
            )
            _memory_state['memory_regions'][free_post.address] = free_post
        
        # Create the allocated region
        allocated = MemoryRegion(
            address=address,
            size=size,
            mem_type=mem_type,
            permissions=permissions,
            owner=owner,
            name=name
        )
        
        # Remove the original free region and add the new allocated region
        del _memory_state['memory_regions'][region.address]
        _memory_state['memory_regions'][allocated.address] = allocated
        
        # Update memory stats
        _memory_state['allocated_memory'] += size
        _memory_state['available_memory'] -= size
        
        # Notify memory allocation
        _notify_memory_event('allocation', allocated.address, size, mem_type, owner)
        
        logger.debug(f"Allocated {size} bytes at {address:x} for {owner or 'unknown'}")
        
        return allocated.address


def free_memory(address):
    """
    Free memory
    
    Args:
        address: Memory address to free
    
    Returns:
        Success status
    """
    with _allocation_lock:
        # Find the region
        region = _memory_state['memory_regions'].get(address)
        
        if not region or region.mem_type == MemoryType.FREE:
            logger.error(f"Cannot free non-allocated memory at {address:x}")
            return False
        
        # Update memory stats
        _memory_state['allocated_memory'] -= region.size
        _memory_state['available_memory'] += region.size
        
        # Create a free region
        free_region = MemoryRegion(
            address=address,
            size=region.size,
            mem_type=MemoryType.FREE,
            permissions=MemoryPermission.READ_WRITE,
            owner=None,
            name=f"free_{address:x}_{region.size:x}"
        )
        
        # Replace the region
        _memory_state['memory_regions'][address] = free_region
        
        # Try to merge with adjacent free regions
        _merge_adjacent_free_regions(free_region)
        
        # Notify memory free
        _notify_memory_event('free', address, region.size, region.mem_type, region.owner)
        
        logger.debug(f"Freed {region.size} bytes at {address:x} from {region.owner or 'unknown'}")
        
        return True


def _merge_adjacent_free_regions(region):
    """
    Merge a free region with any adjacent free regions
    
    Args:
        region: Free region to merge
    """
    # Look for regions to merge
    while True:
        merged = False
        
        # Check all regions
        regions = list(_memory_state['memory_regions'].values())
        
        for other in regions:
            if other.address != region.address and region.can_merge(other):
                # Merge regions
                merged_region = region.merge(other)
                
                # Remove old regions
                del _memory_state['memory_regions'][region.address]
                del _memory_state['memory_regions'][other.address]
                
                # Add new merged region
                _memory_state['memory_regions'][merged_region.address] = merged_region
                
                # Continue with the merged region
                region = merged_region
                merged = True
                break
        
        if not merged:
            break


def read_memory(address, size):
    """
    Read from memory
    
    Args:
        address: Memory address
        size: Number of bytes to read
    
    Returns:
        Data read
    """
    # Find the region containing the address
    region = _find_region_containing_address(address)
    
    if not region:
        raise ValueError(f"Invalid memory address: {address:x}")
    
    # Calculate offset within the region
    offset = address - region.address
    
    # Read from the region
    return region.read(offset, size)


def write_memory(address, data):
    """
    Write to memory
    
    Args:
        address: Memory address
        data: Data to write
    
    Returns:
        Number of bytes written
    """
    # Find the region containing the address
    region = _find_region_containing_address(address)
    
    if not region:
        raise ValueError(f"Invalid memory address: {address:x}")
    
    # Calculate offset within the region
    offset = address - region.address
    
    # Write to the region
    return region.write(offset, data)


def _find_region_containing_address(address):
    """
    Find the memory region containing an address
    
    Args:
        address: Memory address
    
    Returns:
        Memory region, or None if not found
    """
    with _memory_lock:
        for region in _memory_state['memory_regions'].values():
            if region.address <= address <= region.end_address:
                return region
        
        return None


def get_memory_info(address=None):
    """
    Get memory information
    
    Args:
        address: Memory address, or None for global info
    
    Returns:
        Memory information
    """
    with _memory_lock:
        if address is not None:
            # Find the region
            region = _find_region_containing_address(address)
            
            if not region:
                return None
            
            return region.get_info()
        else:
            # Global memory info
            return {
                'total_memory': _memory_state['total_memory'],
                'available_memory': _memory_state['available_memory'],
                'allocated_memory': _memory_state['allocated_memory'],
                'page_size': _memory_state['page_size'],
                'region_count': len(_memory_state['memory_regions']),
                'free_regions': sum(1 for r in _memory_state['memory_regions'].values() 
                                 if r.mem_type == MemoryType.FREE),
                'fragmentation': _calculate_memory_fragmentation()
            }


def _calculate_memory_fragmentation():
    """
    Calculate memory fragmentation
    
    Returns:
        Fragmentation percentage (0-100)
    """
    with _memory_lock:
        # Count free regions
        free_regions = [r for r in _memory_state['memory_regions'].values() 
                     if r.mem_type == MemoryType.FREE]
        
        # If no free memory, fragmentation is 0
        if _memory_state['available_memory'] == 0:
            return 0
        
        # Calculate fragmentation based on number of free regions and their average size
        if len(free_regions) == 1:
            return 0  # No fragmentation
        
        # The more free regions, the higher the fragmentation
        # Normalize to a 0-100 scale
        fragmentation = min(100, (len(free_regions) - 1) * 10)
        
        return fragmentation


def _notify_memory_event(event_type, address, size, mem_type, owner):
    """
    Notify memory event
    
    Args:
        event_type: Event type ('allocation', 'free', etc.)
        address: Memory address
        size: Memory size
        mem_type: Memory type
        owner: Owner process ID
    """
    # Call all registered callbacks
    for callback in _memory_state['memory_callbacks'].get(event_type, []):
        try:
            callback(event_type, address, size, mem_type, owner)
        except Exception as e:
            logger.error(f"Error in memory event callback: {e}")


def register_memory_callback(event_type, callback):
    """
    Register a callback for memory events
    
    Args:
        event_type: Event type ('allocation', 'free', etc.)
        callback: Callback function
    
    Returns:
        Success status
    """
    with _memory_lock:
        if event_type not in _memory_state['memory_callbacks']:
            _memory_state['memory_callbacks'][event_type] = []
        
        _memory_state['memory_callbacks'][event_type].append(callback)
        return True


def unregister_memory_callback(event_type, callback):
    """
    Unregister a memory callback
    
    Args:
        event_type: Event type
        callback: Callback function
    
    Returns:
        Success status
    """
    with _memory_lock:
        if event_type in _memory_state['memory_callbacks']:
            if callback in _memory_state['memory_callbacks'][event_type]:
                _memory_state['memory_callbacks'][event_type].remove(callback)
                return True
    
    return False


def map_virtual_address(virtual_address, physical_address, size, permissions=MemoryPermission.READ_WRITE, owner=None):
    """
    Map a virtual address to a physical address
    
    Args:
        virtual_address: Virtual address
        physical_address: Physical address
        size: Size in bytes
        permissions: Memory permissions
        owner: Owner process ID
    
    Returns:
        Success status
    """
    with _memory_lock:
        # Calculate number of pages needed
        page_size = _memory_state['page_size']
        pages_needed = (size + page_size - 1) // page_size
        
        # Map each page
        for i in range(pages_needed):
            v_addr = virtual_address + i * page_size
            p_addr = physical_address + i * page_size
            
            # Create a page
            page = Page(
                physical_address=p_addr,
                size=page_size,
                permissions=permissions,
                owner=owner
            )
            
            # Add to page table
            _memory_state['page_table'][v_addr] = page
        
        return True


def unmap_virtual_address(virtual_address, size):
    """
    Unmap a virtual address
    
    Args:
        virtual_address: Virtual address
        size: Size in bytes
    
    Returns:
        Success status
    """
    with _memory_lock:
        # Calculate number of pages
        page_size = _memory_state['page_size']
        pages = (size + page_size - 1) // page_size
        
        # Unmap each page
        for i in range(pages):
            v_addr = virtual_address + i * page_size
            
            if v_addr in _memory_state['page_table']:
                del _memory_state['page_table'][v_addr]
        
        return True


def translate_address(virtual_address):
    """
    Translate a virtual address to a physical address
    
    Args:
        virtual_address: Virtual address
    
    Returns:
        Physical address, or None if not mapped
    """
    with _memory_lock:
        # Calculate page-aligned address
        page_size = _memory_state['page_size']
        page_aligned = (virtual_address // page_size) * page_size
        offset = virtual_address - page_aligned
        
        # Look up in page table
        page = _memory_state['page_table'].get(page_aligned)
        
        if not page:
            return None
        
        # Mark the page as accessed
        page.mark_accessed()
        
        # Return physical address
        return page.physical_address + offset


def get_page_info(virtual_address):
    """
    Get page information
    
    Args:
        virtual_address: Virtual address
    
    Returns:
        Page information
    """
    with _memory_lock:
        # Calculate page-aligned address
        page_size = _memory_state['page_size']
        page_aligned = (virtual_address // page_size) * page_size
        
        # Look up in page table
        page = _memory_state['page_table'].get(page_aligned)
        
        if not page:
            return None
        
        return page.get_info()


def initialize(memory_size=1024*1024*1024, page_size=4096):
    """
    Initialize the memory manager
    
    Args:
        memory_size: Total memory size in bytes
        page_size: Page size in bytes
    
    Returns:
        Success status
    """
    global _memory_state
    
    with _memory_lock:
        if _memory_state['initialized']:
            logger.warning("Memory manager already initialized")
            return True
        
        logger.info(f"Initializing memory manager with {memory_size} bytes")
        
        # Set memory parameters
        _memory_state['total_memory'] = memory_size
        _memory_state['available_memory'] = memory_size
        _memory_state['allocated_memory'] = 0
        _memory_state['page_size'] = page_size
        
        # Create initial free region
        free_region = MemoryRegion(
            address=0,
            size=memory_size,
            mem_type=MemoryType.FREE,
            permissions=MemoryPermission.READ_WRITE,
            owner=None,
            name=f"free_0_{memory_size:x}"
        )
        
        _memory_state['memory_regions'][0] = free_region
        
        # Mark as initialized
        _memory_state['initialized'] = True
        
        logger.info("Memory manager initialized")
        
        return True

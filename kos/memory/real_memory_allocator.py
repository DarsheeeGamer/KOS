"""
KOS Real Memory Allocator Implementation
Direct memory allocation using mmap and real address tracking
"""

import os
import mmap
import struct
import threading
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from collections import OrderedDict

logger = logging.getLogger('kos.memory.real_allocator')


@dataclass
class MemoryRegion:
    """Physical memory region"""
    start: int
    size: int
    mmap_obj: Optional[mmap.mmap] = None
    allocated: bool = False
    name: str = ""


class RealBuddyAllocator:
    """Real buddy allocator using mmap"""
    
    def __init__(self, base_addr: int = 0x100000000, total_size: int = 1024 * 1024 * 1024):
        """Initialize with 1GB of virtual memory by default"""
        self.base_addr = base_addr
        self.total_size = total_size
        self.min_order = 12  # 4KB minimum
        self.max_order = 30  # 1GB maximum
        
        # Free lists for each order
        self.free_lists = {order: [] for order in range(self.min_order, self.max_order + 1)}
        
        # Allocated blocks tracking
        self.allocated_blocks = {}  # addr -> (size, mmap_obj)
        
        # Lock for thread safety
        self.lock = threading.RLock()
        
        # Memory mapped regions
        self.mmap_regions = {}  # addr -> mmap object
        
        # Initialize with one large block
        self._init_memory()
        
    def _init_memory(self):
        """Initialize memory with large mmap region"""
        try:
            # Create anonymous mmap region
            self.main_mmap = mmap.mmap(-1, self.total_size, 
                                      mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                                      prot=mmap.PROT_READ | mmap.PROT_WRITE)
            
            # Add to highest order free list
            self.free_lists[self.max_order].append(self.base_addr)
            
            logger.info(f"Initialized buddy allocator with {self.total_size} bytes at 0x{self.base_addr:x}")
            
        except Exception as e:
            logger.error(f"Failed to initialize memory: {e}")
            raise
            
    def allocate(self, size: int) -> Optional[int]:
        """Allocate memory of given size"""
        # Round up to next power of 2
        order = self._size_to_order(size)
        if order < self.min_order:
            order = self.min_order
        if order > self.max_order:
            return None
            
        with self.lock:
            # Find a free block
            addr = self._find_free_block(order)
            if addr is None:
                return None
                
            # Track allocation
            block_size = 1 << order
            self.allocated_blocks[addr] = (block_size, order)
            
            return addr
            
    def _size_to_order(self, size: int) -> int:
        """Convert size to order (log2)"""
        order = 0
        size -= 1
        while size > 0:
            size >>= 1
            order += 1
        return order
        
    def _find_free_block(self, order: int) -> Optional[int]:
        """Find free block of given order, splitting if necessary"""
        # Check if we have a block of this order
        if self.free_lists[order]:
            return self.free_lists[order].pop(0)
            
        # Try to split a larger block
        for higher_order in range(order + 1, self.max_order + 1):
            if self.free_lists[higher_order]:
                # Remove block from higher order
                addr = self.free_lists[higher_order].pop(0)
                
                # Split it down to desired order
                for split_order in range(higher_order - 1, order - 1, -1):
                    buddy_addr = addr + (1 << split_order)
                    self.free_lists[split_order].append(buddy_addr)
                    
                return addr
                
        return None
        
    def free(self, addr: int):
        """Free allocated memory"""
        with self.lock:
            if addr not in self.allocated_blocks:
                logger.warning(f"Attempt to free unallocated address: 0x{addr:x}")
                return
                
            size, order = self.allocated_blocks.pop(addr)
            
            # Try to coalesce with buddy
            self._coalesce_block(addr, order)
            
    def _coalesce_block(self, addr: int, order: int):
        """Coalesce block with its buddy if possible"""
        while order < self.max_order:
            # Calculate buddy address
            buddy_addr = addr ^ (1 << order)
            
            # Check if buddy is free
            if buddy_addr in self.free_lists[order]:
                # Remove buddy from free list
                self.free_lists[order].remove(buddy_addr)
                
                # Merge blocks
                addr = min(addr, buddy_addr)
                order += 1
            else:
                # Can't coalesce, add to free list
                break
                
        self.free_lists[order].append(addr)
        
    def read_memory(self, addr: int, size: int) -> bytes:
        """Read from allocated memory"""
        with self.lock:
            # Calculate offset from base
            offset = addr - self.base_addr
            
            if offset < 0 or offset + size > self.total_size:
                raise ValueError(f"Invalid memory read: 0x{addr:x}")
                
            # Read from mmap
            return bytes(self.main_mmap[offset:offset + size])
            
    def write_memory(self, addr: int, data: bytes):
        """Write to allocated memory"""
        with self.lock:
            # Calculate offset from base
            offset = addr - self.base_addr
            
            if offset < 0 or offset + len(data) > self.total_size:
                raise ValueError(f"Invalid memory write: 0x{addr:x}")
                
            # Write to mmap
            self.main_mmap[offset:offset + len(data)] = data
            
    def get_stats(self) -> Dict[str, int]:
        """Get allocator statistics"""
        with self.lock:
            stats = {
                'total_size': self.total_size,
                'allocated_blocks': len(self.allocated_blocks),
                'allocated_bytes': sum(size for size, _ in self.allocated_blocks.values())
            }
            
            # Count free blocks
            for order, blocks in self.free_lists.items():
                if blocks:
                    stats[f'free_order_{order}'] = len(blocks)
                    
            return stats


class RealSlabAllocator:
    """Real slab allocator for small objects"""
    
    SLAB_SIZE = 16 * 1024  # 16KB slabs
    
    def __init__(self, buddy_allocator: RealBuddyAllocator):
        self.buddy_allocator = buddy_allocator
        self.caches = {}  # object_size -> cache
        self.lock = threading.RLock()
        
    def create_cache(self, name: str, object_size: int, align: int = 8) -> 'SlabCache':
        """Create new slab cache"""
        # Align object size
        aligned_size = (object_size + align - 1) & ~(align - 1)
        
        with self.lock:
            if aligned_size not in self.caches:
                cache = SlabCache(name, aligned_size, self)
                self.caches[aligned_size] = cache
                
            return self.caches[aligned_size]
            
    def allocate(self, size: int) -> Optional[int]:
        """Allocate object of given size"""
        # Find appropriate cache
        cache = None
        with self.lock:
            for cache_size, c in sorted(self.caches.items()):
                if cache_size >= size:
                    cache = c
                    break
                    
        if cache:
            return cache.alloc_object()
            
        # No suitable cache, use buddy allocator
        return self.buddy_allocator.allocate(size)
        
    def free(self, addr: int):
        """Free object"""
        # Try each cache
        with self.lock:
            for cache in self.caches.values():
                if cache.contains_address(addr):
                    cache.free_object(addr)
                    return
                    
        # Not in any cache, use buddy allocator
        self.buddy_allocator.free(addr)


class SlabCache:
    """Cache for objects of specific size"""
    
    def __init__(self, name: str, object_size: int, allocator: RealSlabAllocator):
        self.name = name
        self.object_size = object_size
        self.allocator = allocator
        self.slabs = []  # List of Slab objects
        self.lock = threading.RLock()
        
        # Calculate objects per slab
        self.objects_per_slab = RealSlabAllocator.SLAB_SIZE // object_size
        
    def alloc_object(self) -> Optional[int]:
        """Allocate object from cache"""
        with self.lock:
            # Try existing slabs
            for slab in self.slabs:
                addr = slab.alloc_object()
                if addr is not None:
                    return addr
                    
            # Need new slab
            slab_addr = self.allocator.buddy_allocator.allocate(RealSlabAllocator.SLAB_SIZE)
            if slab_addr is None:
                return None
                
            # Create new slab
            slab = Slab(slab_addr, self.object_size, self.objects_per_slab)
            self.slabs.append(slab)
            
            return slab.alloc_object()
            
    def free_object(self, addr: int):
        """Free object back to cache"""
        with self.lock:
            for slab in self.slabs:
                if slab.contains_address(addr):
                    slab.free_object(addr)
                    
                    # If slab is now empty, consider freeing it
                    if slab.is_empty() and len(self.slabs) > 1:
                        self.slabs.remove(slab)
                        self.allocator.buddy_allocator.free(slab.base_addr)
                        
                    return
                    
    def contains_address(self, addr: int) -> bool:
        """Check if address belongs to this cache"""
        with self.lock:
            for slab in self.slabs:
                if slab.contains_address(addr):
                    return True
        return False


class Slab:
    """Single slab containing objects"""
    
    def __init__(self, base_addr: int, object_size: int, num_objects: int):
        self.base_addr = base_addr
        self.object_size = object_size
        self.num_objects = num_objects
        
        # Bitmap for free objects
        self.free_bitmap = [True] * num_objects
        self.num_free = num_objects
        
    def alloc_object(self) -> Optional[int]:
        """Allocate object from slab"""
        for i, is_free in enumerate(self.free_bitmap):
            if is_free:
                self.free_bitmap[i] = False
                self.num_free -= 1
                return self.base_addr + (i * self.object_size)
        return None
        
    def free_object(self, addr: int):
        """Free object in slab"""
        if self.contains_address(addr):
            index = (addr - self.base_addr) // self.object_size
            if not self.free_bitmap[index]:
                self.free_bitmap[index] = True
                self.num_free += 1
                
    def contains_address(self, addr: int) -> bool:
        """Check if address is in this slab"""
        end_addr = self.base_addr + (self.num_objects * self.object_size)
        return self.base_addr <= addr < end_addr
        
    def is_empty(self) -> bool:
        """Check if slab is empty"""
        return self.num_free == self.num_objects
        
    def is_full(self) -> bool:
        """Check if slab is full"""
        return self.num_free == 0


class RealVMAllocator:
    """Real vmalloc-style allocator for virtual memory regions"""
    
    def __init__(self, start_addr: int = 0x200000000, size: int = 1024 * 1024 * 1024):
        self.start_addr = start_addr
        self.size = size
        self.regions = OrderedDict()  # addr -> MemoryRegion
        self.lock = threading.RLock()
        self.next_addr = start_addr
        
    def vmalloc(self, size: int, name: str = "") -> Optional[int]:
        """Allocate virtual memory region"""
        # Align to page boundary
        page_size = 4096
        size = (size + page_size - 1) & ~(page_size - 1)
        
        with self.lock:
            # Find free space
            addr = self._find_free_space(size)
            if addr is None:
                return None
                
            # Create mmap region
            try:
                mmap_obj = mmap.mmap(-1, size,
                                    mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                                    prot=mmap.PROT_READ | mmap.PROT_WRITE)
                
                region = MemoryRegion(addr, size, mmap_obj, True, name)
                self.regions[addr] = region
                
                return addr
                
            except Exception as e:
                logger.error(f"vmalloc failed: {e}")
                return None
                
    def vfree(self, addr: int):
        """Free virtual memory region"""
        with self.lock:
            if addr in self.regions:
                region = self.regions.pop(addr)
                if region.mmap_obj:
                    region.mmap_obj.close()
                    
    def _find_free_space(self, size: int) -> Optional[int]:
        """Find free address space"""
        if not self.regions:
            return self.start_addr
            
        # Check gaps between regions
        prev_end = self.start_addr
        
        for addr, region in self.regions.items():
            gap = addr - prev_end
            if gap >= size:
                return prev_end
            prev_end = addr + region.size
            
        # Check space after last region
        if prev_end + size <= self.start_addr + self.size:
            return prev_end
            
        return None
        
    def read_vmem(self, addr: int, size: int) -> bytes:
        """Read from vmalloc'd memory"""
        with self.lock:
            # Find containing region
            for region_addr, region in self.regions.items():
                if region_addr <= addr < region_addr + region.size:
                    offset = addr - region_addr
                    if offset + size > region.size:
                        raise ValueError("Read crosses region boundary")
                    return bytes(region.mmap_obj[offset:offset + size])
                    
            raise ValueError(f"Address 0x{addr:x} not in any vmalloc region")
            
    def write_vmem(self, addr: int, data: bytes):
        """Write to vmalloc'd memory"""
        with self.lock:
            # Find containing region
            for region_addr, region in self.regions.items():
                if region_addr <= addr < region_addr + region.size:
                    offset = addr - region_addr
                    if offset + len(data) > region.size:
                        raise ValueError("Write crosses region boundary")
                    region.mmap_obj[offset:offset + len(data)] = data
                    return
                    
            raise ValueError(f"Address 0x{addr:x} not in any vmalloc region")


# Global allocator instances
_buddy_allocator = None
_slab_allocator = None
_vm_allocator = None

def get_buddy_allocator() -> RealBuddyAllocator:
    """Get global buddy allocator"""
    global _buddy_allocator
    if _buddy_allocator is None:
        _buddy_allocator = RealBuddyAllocator()
    return _buddy_allocator

def get_slab_allocator() -> RealSlabAllocator:
    """Get global slab allocator"""
    global _slab_allocator
    if _slab_allocator is None:
        _slab_allocator = RealSlabAllocator(get_buddy_allocator())
    return _slab_allocator

def get_vm_allocator() -> RealVMAllocator:
    """Get global VM allocator"""
    global _vm_allocator
    if _vm_allocator is None:
        _vm_allocator = RealVMAllocator()
    return _vm_allocator
"""
KOS Memory Allocators - Buddy and Slab allocators
"""

import threading
import math
from typing import List, Optional, Dict, Any
from collections import defaultdict

class BuddyAllocator:
    """
    Buddy allocator for page allocation
    Similar to Linux buddy allocator
    """
    
    def __init__(self, memory_manager: 'KOSMemoryManager'):
        self.memory_manager = memory_manager
        self.max_order = memory_manager.MAX_ORDER
        self.page_size = memory_manager.PAGE_SIZE
        
        # Free lists for each order (0 to MAX_ORDER)
        self.free_lists = [[] for _ in range(self.max_order + 1)]
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Statistics
        self.allocations = defaultdict(int)  # order -> count
        self.deallocations = defaultdict(int)
        self.coalesced_blocks = 0
        
    def init_free_lists(self):
        """Initialize free lists with available pages"""
        with self.lock:
            total_pages = self.memory_manager.num_pages
            
            # Start with largest possible blocks
            order = self.max_order
            pages_processed = 0
            
            while pages_processed < total_pages and order >= 0:
                block_size = 1 << order
                
                while pages_processed + block_size <= total_pages:
                    # Create a block starting at pages_processed
                    start_pfn = pages_processed
                    block_pages = []
                    
                    for i in range(block_size):
                        page = self.memory_manager.page_frames[start_pfn + i]
                        block_pages.append(page)
                        
                    self.free_lists[order].append(block_pages)
                    pages_processed += block_size
                    
                order -= 1
                
    def alloc_pages(self, order: int, gfp_flags: int = 0) -> Optional[List['PageFrame']]:
        """
        Allocate 2^order contiguous pages
        """
        if order > self.max_order:
            return None
            
        with self.lock:
            # Try to find a free block of the requested size
            for current_order in range(order, self.max_order + 1):
                if self.free_lists[current_order]:
                    # Found a block
                    block = self.free_lists[current_order].pop(0)
                    
                    # Split the block if it's larger than needed
                    while current_order > order:
                        current_order -= 1
                        buddy_size = 1 << current_order
                        
                        # Split block in half
                        buddy = block[buddy_size:]
                        block = block[:buddy_size]
                        
                        # Add buddy to appropriate free list
                        self.free_lists[current_order].append(buddy)
                        
                    # Mark pages as allocated
                    for page in block:
                        page.page_type = page.page_type.__class__.KERNEL
                        
                    self.allocations[order] += 1
                    return block
                    
            return None  # No free blocks available
            
    def free_pages(self, pages: List['PageFrame']):
        """
        Free pages and try to coalesce with buddies
        """
        if not pages:
            return
            
        with self.lock:
            # Determine the order from the number of pages
            order = int(math.log2(len(pages)))
            
            # Mark pages as free
            for page in pages:
                page.page_type = page.page_type.__class__.FREE
                
            # Try to coalesce with buddy blocks
            block = pages
            current_order = order
            
            while current_order < self.max_order:
                buddy_block = self._find_buddy(block, current_order)
                
                if buddy_block and buddy_block in self.free_lists[current_order]:
                    # Coalesce with buddy
                    self.free_lists[current_order].remove(buddy_block)
                    
                    # Merge blocks (keep lower address first)
                    if buddy_block[0].pfn < block[0].pfn:
                        block = buddy_block + block
                    else:
                        block = block + buddy_block
                        
                    current_order += 1
                    self.coalesced_blocks += 1
                else:
                    # Can't coalesce further
                    break
                    
            # Add the final block to the appropriate free list
            self.free_lists[current_order].append(block)
            self.deallocations[order] += 1
            
    def _find_buddy(self, block: List['PageFrame'], order: int) -> Optional[List['PageFrame']]:
        """
        Find the buddy block for coalescing
        """
        block_size = 1 << order
        start_pfn = block[0].pfn
        
        # Calculate buddy's starting page frame number
        buddy_start_pfn = start_pfn ^ block_size
        
        # Look for buddy in the free list
        for free_block in self.free_lists[order]:
            if free_block[0].pfn == buddy_start_pfn and len(free_block) == block_size:
                return free_block
                
        return None
        
    def get_free_pages_count(self, order: int) -> int:
        """Get count of free blocks of given order"""
        with self.lock:
            if 0 <= order <= self.max_order:
                return len(self.free_lists[order])
        return 0
        
    def get_stats(self) -> Dict[str, Any]:
        """Get allocator statistics"""
        with self.lock:
            return {
                'allocations': dict(self.allocations),
                'deallocations': dict(self.deallocations),
                'coalesced_blocks': self.coalesced_blocks,
                'free_lists': [len(fl) for fl in self.free_lists],
                'total_free_pages': sum(len(fl) * (1 << i) for i, fl in enumerate(self.free_lists))
            }

class SlabCache:
    """
    A slab cache for objects of a specific size
    """
    
    def __init__(self, name: str, object_size: int, align: int = 8):
        self.name = name
        self.object_size = max(object_size, align)  # Ensure minimum alignment
        self.align = align
        
        # Calculate objects per slab
        self.page_size = 4096
        self.objects_per_slab = self.page_size // self.object_size
        
        # Slab lists
        self.full_slabs = []
        self.partial_slabs = []
        self.empty_slabs = []
        
        # Statistics
        self.total_objects = 0
        self.used_objects = 0
        self.total_slabs = 0
        
        self.lock = threading.Lock()
        
    def alloc_object(self) -> Optional[int]:
        """Allocate an object from this cache"""
        with self.lock:
            # Try partial slabs first
            if self.partial_slabs:
                slab = self.partial_slabs[0]
            elif self.empty_slabs:
                # Use empty slab
                slab = self.empty_slabs.pop(0)
                self.partial_slabs.append(slab)
            else:
                # Create new slab
                slab = self._create_slab()
                if not slab:
                    return None
                self.partial_slabs.append(slab)
                
            # Allocate object from slab
            obj_addr = slab.alloc_object()
            if obj_addr:
                self.used_objects += 1
                
                # Move slab to full list if no more free objects
                if slab.is_full():
                    self.partial_slabs.remove(slab)
                    self.full_slabs.append(slab)
                    
            return obj_addr
            
    def free_object(self, obj_addr: int):
        """Free an object back to the cache"""
        with self.lock:
            # Find which slab contains this object
            slab = self._find_slab_for_address(obj_addr)
            if not slab:
                return
                
            was_full = slab.is_full()
            slab.free_object(obj_addr)
            self.used_objects -= 1
            
            # Move slab between lists if needed
            if was_full:
                self.full_slabs.remove(slab)
                self.partial_slabs.append(slab)
            elif slab.is_empty():
                self.partial_slabs.remove(slab)
                self.empty_slabs.append(slab)
                
    def _create_slab(self) -> Optional['Slab']:
        """Create a new slab"""
        # Would allocate page from buddy allocator
        # For simulation, create slab object
        slab = Slab(self.object_size, self.objects_per_slab)
        self.total_slabs += 1
        self.total_objects += self.objects_per_slab
        return slab
        
    def _find_slab_for_address(self, addr: int) -> Optional['Slab']:
        """Find slab containing the given address"""
        # Check all slab lists
        for slab_list in [self.full_slabs, self.partial_slabs, self.empty_slabs]:
            for slab in slab_list:
                if slab.contains_address(addr):
                    return slab
        return None
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            return {
                'name': self.name,
                'object_size': self.object_size,
                'objects_per_slab': self.objects_per_slab,
                'total_objects': self.total_objects,
                'used_objects': self.used_objects,
                'free_objects': self.total_objects - self.used_objects,
                'total_slabs': self.total_slabs,
                'full_slabs': len(self.full_slabs),
                'partial_slabs': len(self.partial_slabs),
                'empty_slabs': len(self.empty_slabs)
            }

class Slab:
    """
    A single slab containing objects of the same size
    """
    
    def __init__(self, object_size: int, num_objects: int):
        self.object_size = object_size
        self.num_objects = num_objects
        self.base_addr = id(self) * 1000  # Simulated base address
        
        # Free object tracking
        self.free_objects = list(range(num_objects))
        
    def alloc_object(self) -> Optional[int]:
        """Allocate an object from this slab"""
        if self.free_objects:
            obj_index = self.free_objects.pop(0)
            return self.base_addr + (obj_index * self.object_size)
        return None
        
    def free_object(self, obj_addr: int):
        """Free an object back to this slab"""
        if self.contains_address(obj_addr):
            obj_index = (obj_addr - self.base_addr) // self.object_size
            if obj_index not in self.free_objects:
                self.free_objects.append(obj_index)
                self.free_objects.sort()
                
    def contains_address(self, addr: int) -> bool:
        """Check if address belongs to this slab"""
        end_addr = self.base_addr + (self.num_objects * self.object_size)
        return self.base_addr <= addr < end_addr
        
    def is_full(self) -> bool:
        """Check if slab is full"""
        return len(self.free_objects) == 0
        
    def is_empty(self) -> bool:
        """Check if slab is empty"""
        return len(self.free_objects) == self.num_objects

class SlabAllocator:
    """
    Slab allocator for efficient small object allocation
    """
    
    def __init__(self, memory_manager: 'KOSMemoryManager'):
        self.memory_manager = memory_manager
        self.caches = {}  # size -> SlabCache
        self.lock = threading.Lock()
        
        # Create standard caches
        self._create_standard_caches()
        
    def _create_standard_caches(self):
        """Create standard slab caches for common sizes"""
        standard_sizes = [32, 64, 128, 256, 512, 1024, 2048, 4096]
        
        for size in standard_sizes:
            cache_name = f"kmalloc-{size}"
            self.caches[size] = SlabCache(cache_name, size)
            
    def alloc(self, size: int, gfp_flags: int = 0) -> Optional[int]:
        """Allocate memory from appropriate slab cache"""
        if size <= 0:
            return None
            
        # Find appropriate cache
        cache = self._find_cache(size)
        if cache:
            return cache.alloc_object()
            
        return None
        
    def free(self, addr: int) -> bool:
        """Free memory back to slab cache"""
        if addr == 0:
            return False
            
        # Find which cache contains this address
        with self.lock:
            for cache in self.caches.values():
                if cache._find_slab_for_address(addr):
                    cache.free_object(addr)
                    return True
                    
        return False
        
    def _find_cache(self, size: int) -> Optional[SlabCache]:
        """Find appropriate cache for the given size"""
        # Find smallest cache that can fit the size
        best_size = None
        for cache_size in sorted(self.caches.keys()):
            if cache_size >= size:
                best_size = cache_size
                break
                
        if best_size:
            return self.caches[best_size]
            
        return None
        
    def create_cache(self, name: str, size: int, align: int = 8) -> SlabCache:
        """Create a new slab cache"""
        with self.lock:
            cache = SlabCache(name, size, align)
            # Don't add to size-based lookup, this is for specific objects
            return cache
            
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about all caches"""
        with self.lock:
            info = {}
            for size, cache in self.caches.items():
                info[f"size-{size}"] = cache.get_stats()
            return info
"""
KOS Memory Manager - Main memory management subsystem
"""

import threading
import time
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from collections import defaultdict

class MemoryZone(Enum):
    """Memory zones similar to Linux"""
    DMA = "DMA"
    NORMAL = "Normal"
    HIGHMEM = "HighMem"

class PageFlags(Enum):
    """Page flags"""
    LOCKED = 1
    DIRTY = 2
    WRITEBACK = 4
    UPTODATE = 8
    LRU = 16
    ACTIVE = 32
    SLAB = 64
    RESERVED = 128
    COMPOUND = 256

@dataclass
class MemoryStats:
    """Memory statistics"""
    total: int = 0
    free: int = 0
    used: int = 0
    cached: int = 0
    buffers: int = 0
    swap_total: int = 0
    swap_free: int = 0
    swap_cached: int = 0

class KOSMemoryManager:
    """
    Virtual memory manager for KOS
    Simulates Linux-like memory management
    """
    
    PAGE_SIZE = 4096
    MAX_ORDER = 11  # 4MB max allocation
    
    def __init__(self, total_memory: int):
        self.total_memory = total_memory
        self.page_size = self.PAGE_SIZE
        self.num_pages = total_memory // self.page_size
        
        # Memory zones
        self.zones = {
            MemoryZone.DMA: self._create_zone(0, 16 * 1024 * 1024),  # First 16MB
            MemoryZone.NORMAL: self._create_zone(16 * 1024 * 1024, total_memory),
        }
        
        # Page frames - simulate physical pages
        from .page import PageFrame
        self.page_frames = [PageFrame(i) for i in range(self.num_pages)]
        
        # Free lists for buddy allocator
        self.free_lists = [[] for _ in range(self.MAX_ORDER + 1)]
        
        # Memory allocators
        from .allocator import BuddyAllocator, SlabAllocator
        self.buddy_allocator = BuddyAllocator(self)
        self.slab_allocator = SlabAllocator(self)
        
        # Page cache and buffers
        self.page_cache = {}  # inode -> page mapping
        self.buffer_cache = {}  # block device buffers
        
        # Memory pressure and reclaim
        self.memory_pressure = 0.0
        self.reclaim_watermarks = {
            'low': total_memory * 0.05,    # 5% free
            'high': total_memory * 0.10,   # 10% free
            'min': total_memory * 0.02     # 2% free (critical)
        }
        
        # LRU lists for page reclaim
        self.lru_lists = {
            'active_anon': [],
            'inactive_anon': [],
            'active_file': [],
            'inactive_file': [],
        }
        
        # Memory cgroups
        self.cgroups = {}
        
        # Statistics
        self.stats = MemoryStats(total=total_memory)
        self.allocation_count = 0
        self.deallocation_count = 0
        
        # Locks
        self.lock = threading.RLock()
        self.zone_locks = {zone: threading.Lock() for zone in self.zones}
        
        # Initialize free memory
        self._init_free_memory()
        
        # Start background threads
        self._start_kswapd()
        
    def _create_zone(self, start: int, end: int) -> Dict:
        """Create a memory zone"""
        return {
            'start': start,
            'end': end,
            'size': end - start,
            'free_pages': (end - start) // self.page_size,
            'managed_pages': (end - start) // self.page_size,
            'watermark_low': (end - start) * 0.05,
            'watermark_high': (end - start) * 0.10,
            'watermark_min': (end - start) * 0.02
        }
        
    def _init_free_memory(self):
        """Initialize free memory structures"""
        # Mark all pages as free initially
        for page in self.page_frames:
            page.flags = 0
            page.count = 0
            
        # Add pages to buddy allocator free lists
        self.buddy_allocator.init_free_lists()
        
        # Update statistics
        self.stats.free = self.total_memory
        self.stats.used = 0
        
    def alloc_pages(self, order: int, gfp_flags: int = 0) -> Optional[List['PageFrame']]:
        """
        Allocate 2^order contiguous pages
        Similar to Linux __alloc_pages()
        """
        if order > self.MAX_ORDER:
            return None
            
        with self.lock:
            pages = self.buddy_allocator.alloc_pages(order, gfp_flags)
            
            if pages:
                # Update statistics
                allocated_size = len(pages) * self.page_size
                self.stats.free -= allocated_size
                self.stats.used += allocated_size
                self.allocation_count += 1
                
                # Mark pages as allocated
                for page in pages:
                    page.count = 1
                    page.flags |= PageFlags.LOCKED.value
                    
            else:
                # Try memory reclaim if allocation failed
                if self._should_reclaim_memory():
                    reclaimed = self._reclaim_memory(1 << order)
                    if reclaimed >= (1 << order):
                        # Try allocation again
                        pages = self.buddy_allocator.alloc_pages(order, gfp_flags)
                        
            return pages
            
    def free_pages(self, pages: List['PageFrame']):
        """
        Free allocated pages
        Similar to Linux __free_pages()
        """
        with self.lock:
            if not pages:
                return
                
            # Validate pages
            for page in pages:
                if page.count <= 0:
                    raise ValueError(f"Double free of page {page.pfn}")
                page.count -= 1
                
            # Only free if reference count reaches zero
            pages_to_free = [p for p in pages if p.count == 0]
            
            if pages_to_free:
                # Clear page flags
                for page in pages_to_free:
                    page.flags = 0
                    
                # Return to buddy allocator
                self.buddy_allocator.free_pages(pages_to_free)
                
                # Update statistics
                freed_size = len(pages_to_free) * self.page_size
                self.stats.free += freed_size
                self.stats.used -= freed_size
                self.deallocation_count += 1
                
    def alloc_page(self, gfp_flags: int = 0) -> Optional['PageFrame']:
        """Allocate a single page"""
        pages = self.alloc_pages(0, gfp_flags)
        return pages[0] if pages else None
        
    def free_page(self, page: 'PageFrame'):
        """Free a single page"""
        self.free_pages([page])
        
    def kmalloc(self, size: int, gfp_flags: int = 0) -> Optional[int]:
        """
        Allocate kernel memory
        Returns virtual address (simulated as integer)
        """
        if size <= 0:
            return None
            
        # Use slab allocator for small allocations
        if size <= 4096:
            return self.slab_allocator.alloc(size, gfp_flags)
        else:
            # Use buddy allocator for large allocations
            order = self._size_to_order(size)
            pages = self.alloc_pages(order, gfp_flags)
            if pages:
                return pages[0].get_virtual_address()
            return None
            
    def kfree(self, addr: int):
        """Free kernel memory"""
        if addr == 0:
            return
            
        # Try slab allocator first
        if self.slab_allocator.free(addr):
            return
            
        # Try buddy allocator
        page = self._addr_to_page(addr)
        if page:
            self.free_page(page)
            
    def vmalloc(self, size: int) -> Optional[int]:
        """
        Allocate virtually contiguous memory
        May not be physically contiguous
        """
        if size <= 0:
            return None
            
        pages_needed = (size + self.page_size - 1) // self.page_size
        pages = []
        
        # Allocate individual pages
        for _ in range(pages_needed):
            page = self.alloc_page()
            if page:
                pages.append(page)
            else:
                # Free already allocated pages on failure
                self.free_pages(pages)
                return None
                
        # In real kernel, would map to virtual address space
        # For simulation, just return first page address
        return pages[0].get_virtual_address()
        
    def vfree(self, addr: int):
        """Free vmalloc'd memory"""
        # In real implementation, would unmap virtual pages
        # For simulation, just free the page
        page = self._addr_to_page(addr)
        if page:
            self.free_page(page)
            
    def get_free_memory(self) -> int:
        """Get amount of free memory"""
        return self.stats.free
        
    def get_used_memory(self) -> int:
        """Get amount of used memory"""
        return self.stats.used
        
    def get_cached_memory(self) -> int:
        """Get amount of cached memory"""
        return self.stats.cached
        
    def get_buffer_memory(self) -> int:
        """Get amount of buffer memory"""
        return self.stats.buffers
        
    def reserve_kernel_memory(self, start: int, size: int):
        """Reserve memory for kernel use"""
        pages_to_reserve = size // self.page_size
        start_page = start // self.page_size
        
        with self.lock:
            for i in range(pages_to_reserve):
                page_idx = start_page + i
                if page_idx < len(self.page_frames):
                    page = self.page_frames[page_idx]
                    page.flags |= PageFlags.RESERVED.value
                    page.count = 1
                    
            # Update statistics
            self.stats.free -= size
            self.stats.used += size
            
    def add_to_page_cache(self, inode_id: int, offset: int, page: 'PageFrame'):
        """Add page to page cache"""
        key = (inode_id, offset)
        self.page_cache[key] = page
        page.flags |= PageFlags.LRU.value
        
        # Add to LRU list
        self.lru_lists['active_file'].append(page)
        
        # Update statistics
        self.stats.cached += self.page_size
        
    def remove_from_page_cache(self, inode_id: int, offset: int):
        """Remove page from page cache"""
        key = (inode_id, offset)
        page = self.page_cache.pop(key, None)
        
        if page:
            page.flags &= ~PageFlags.LRU.value
            
            # Remove from LRU lists
            for lru_list in self.lru_lists.values():
                if page in lru_list:
                    lru_list.remove(page)
                    break
                    
            # Update statistics
            self.stats.cached -= self.page_size
            
    def _should_reclaim_memory(self) -> bool:
        """Check if memory reclaim is needed"""
        return self.stats.free < self.reclaim_watermarks['low']
        
    def _reclaim_memory(self, pages_needed: int) -> int:
        """
        Reclaim memory pages
        Similar to Linux memory reclaim/kswapd
        """
        reclaimed = 0
        
        # Try to reclaim from page cache first
        cache_to_reclaim = min(len(self.page_cache), pages_needed)
        if cache_to_reclaim > 0:
            # Remove oldest pages from cache (LRU)
            for _ in range(cache_to_reclaim):
                if self.lru_lists['inactive_file']:
                    page = self.lru_lists['inactive_file'].pop(0)
                    # Find and remove from page cache
                    for key, cached_page in list(self.page_cache.items()):
                        if cached_page == page:
                            del self.page_cache[key]
                            break
                    self.free_page(page)
                    reclaimed += 1
                    
        # Move pages between LRU lists (aging)
        self._age_lru_lists()
        
        return reclaimed
        
    def _age_lru_lists(self):
        """Age LRU lists by moving pages between active/inactive"""
        # Move some active pages to inactive
        active_file = self.lru_lists['active_file']
        inactive_file = self.lru_lists['inactive_file']
        
        move_count = min(len(active_file) // 4, 10)  # Move 25% or 10 pages
        for _ in range(move_count):
            if active_file:
                page = active_file.pop(0)
                inactive_file.append(page)
                
    def _start_kswapd(self):
        """Start kernel swap daemon thread"""
        def kswapd():
            while True:
                time.sleep(1.0)  # Check every second
                
                if self._should_reclaim_memory():
                    pages_to_reclaim = max(1, (self.reclaim_watermarks['high'] - self.stats.free) // self.page_size)
                    self._reclaim_memory(pages_to_reclaim)
                    
        thread = threading.Thread(target=kswapd, name="kswapd", daemon=True)
        thread.start()
        
    def _size_to_order(self, size: int) -> int:
        """Convert size to buddy allocator order"""
        pages_needed = (size + self.page_size - 1) // self.page_size
        order = 0
        while (1 << order) < pages_needed:
            order += 1
        return min(order, self.MAX_ORDER)
        
    def _addr_to_page(self, addr: int) -> Optional['PageFrame']:
        """Convert virtual address to page frame"""
        # In real kernel, would use page tables
        # For simulation, just calculate page number
        page_num = addr // self.page_size
        if 0 <= page_num < len(self.page_frames):
            return self.page_frames[page_num]
        return None
        
    def get_memory_stats(self) -> MemoryStats:
        """Get current memory statistics"""
        return self.stats
        
    def dump_memory_info(self) -> Dict:
        """Dump detailed memory information"""
        info = {
            'total_memory': self.total_memory,
            'page_size': self.page_size,
            'num_pages': self.num_pages,
            'free_memory': self.stats.free,
            'used_memory': self.stats.used,
            'cached_memory': self.stats.cached,
            'buffer_memory': self.stats.buffers,
            'allocation_count': self.allocation_count,
            'deallocation_count': self.deallocation_count,
            'page_cache_size': len(self.page_cache),
            'slab_caches': self.slab_allocator.get_cache_info(),
            'buddy_free_lists': [len(fl) for fl in self.free_lists],
            'zones': {
                zone.name: {
                    'start': zinfo['start'],
                    'end': zinfo['end'],
                    'size': zinfo['size'],
                    'free_pages': zinfo['free_pages']
                }
                for zone, zinfo in self.zones.items()
            }
        }
        
        return info
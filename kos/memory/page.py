"""
KOS Page Management - Page and page frame structures
"""

import time
from typing import Optional, List
from enum import Enum

class PageType(Enum):
    """Types of pages"""
    FREE = "free"
    KERNEL = "kernel"
    USER = "user"  
    CACHE = "cache"
    BUFFER = "buffer"
    SLAB = "slab"

class PageFrame:
    """
    Represents a physical page frame
    Similar to Linux struct page
    """
    
    def __init__(self, pfn: int):
        self.pfn = pfn  # Page frame number
        self.flags = 0  # Page flags (from PageFlags enum)
        self.count = 0  # Reference count
        self.mapping = None  # Address space mapping
        self.index = 0  # Index within mapping
        self.private = None  # Private data
        self.lru = None  # LRU list links
        self.compound_head = None  # For compound pages
        self.compound_order = 0  # Order for compound pages
        self.page_type = PageType.FREE
        
        # Statistics
        self.allocation_time = None
        self.last_access_time = None
        
    def get_physical_address(self) -> int:
        """Get physical address of this page"""
        return self.pfn * 4096  # PAGE_SIZE
        
    def get_virtual_address(self) -> int:
        """Get virtual address (simulated)"""
        # In real kernel, would use page tables
        # For simulation, just offset from a base
        return 0xFFFF880000000000 + self.get_physical_address()
        
    def is_free(self) -> bool:
        """Check if page is free"""
        return self.count == 0 and self.page_type == PageType.FREE
        
    def is_locked(self) -> bool:
        """Check if page is locked"""
        from .manager import PageFlags
        return bool(self.flags & PageFlags.LOCKED.value)
        
    def is_dirty(self) -> bool:
        """Check if page is dirty"""
        from .manager import PageFlags
        return bool(self.flags & PageFlags.DIRTY.value)
        
    def is_uptodate(self) -> bool:
        """Check if page is up to date"""
        from .manager import PageFlags
        return bool(self.flags & PageFlags.UPTODATE.value)
        
    def mark_dirty(self):
        """Mark page as dirty"""
        from .manager import PageFlags
        self.flags |= PageFlags.DIRTY.value
        
    def clear_dirty(self):
        """Clear dirty flag"""
        from .manager import PageFlags
        self.flags &= ~PageFlags.DIRTY.value
        
    def lock_page(self):
        """Lock the page"""
        from .manager import PageFlags
        self.flags |= PageFlags.LOCKED.value
        
    def unlock_page(self):
        """Unlock the page"""
        from .manager import PageFlags
        self.flags &= ~PageFlags.LOCKED.value
        
    def get_page(self):
        """Increment reference count"""
        self.count += 1
        if self.allocation_time is None:
            self.allocation_time = time.time()
        self.last_access_time = time.time()
        
    def put_page(self):
        """Decrement reference count"""
        if self.count > 0:
            self.count -= 1
        self.last_access_time = time.time()
        
    def set_compound_head(self, head: 'PageFrame', order: int):
        """Set up compound page"""
        self.compound_head = head
        self.compound_order = order
        from .manager import PageFlags
        self.flags |= PageFlags.COMPOUND.value
        
    def __repr__(self):
        return f"PageFrame(pfn={self.pfn}, count={self.count}, type={self.page_type.value})"

class Page:
    """
    Virtual page in an address space
    Similar to Linux VMA (Virtual Memory Area)
    """
    
    def __init__(self, vaddr: int, size: int = 4096):
        self.vaddr = vaddr  # Virtual address
        self.size = size
        self.page_frames = []  # Physical pages backing this virtual page
        self.protection = 0  # Protection bits (read/write/execute)
        self.flags = 0  # VMA flags
        self.offset = 0  # Offset in file/device
        self.vm_file = None  # Backing file
        
        # Page fault handling
        self.fault_count = 0
        self.last_fault_time = None
        
    def is_mapped(self) -> bool:
        """Check if page is mapped to physical memory"""
        return len(self.page_frames) > 0
        
    def map_page_frame(self, page_frame: PageFrame):
        """Map a physical page frame"""
        if page_frame not in self.page_frames:
            self.page_frames.append(page_frame)
            page_frame.get_page()
            
    def unmap_page_frame(self, page_frame: PageFrame):
        """Unmap a physical page frame"""
        if page_frame in self.page_frames:
            self.page_frames.remove(page_frame)
            page_frame.put_page()
            
    def unmap_all(self):
        """Unmap all physical pages"""
        for page_frame in self.page_frames[:]:
            self.unmap_page_frame(page_frame)
            
    def handle_page_fault(self) -> bool:
        """Handle page fault on this page"""
        self.fault_count += 1
        self.last_fault_time = time.time()
        
        # If no physical page mapped, this is a demand page
        if not self.is_mapped():
            # Would allocate physical page and map it
            return True
            
        return False
        
    def set_protection(self, prot: int):
        """Set page protection"""
        self.protection = prot
        
    def can_read(self) -> bool:
        """Check if page is readable"""
        return bool(self.protection & 0x1)  # PROT_READ
        
    def can_write(self) -> bool:
        """Check if page is writable"""
        return bool(self.protection & 0x2)  # PROT_WRITE
        
    def can_execute(self) -> bool:
        """Check if page is executable"""
        return bool(self.protection & 0x4)  # PROT_EXEC
        
    def __repr__(self):
        return f"Page(vaddr=0x{self.vaddr:x}, size={self.size}, mapped={self.is_mapped()})"

class PageTable:
    """
    Simple page table implementation
    Maps virtual addresses to physical page frames
    """
    
    def __init__(self):
        self.entries = {}  # vaddr -> PageFrame
        self.lock = None  # Would be a spinlock in real kernel
        
    def map_page(self, vaddr: int, page_frame: PageFrame, protection: int = 0x7):
        """Map virtual address to physical page frame"""
        page_aligned_addr = vaddr & ~0xFFF  # Align to page boundary
        self.entries[page_aligned_addr] = {
            'page_frame': page_frame,
            'protection': protection,
            'present': True,
            'accessed': False,
            'dirty': False
        }
        
    def unmap_page(self, vaddr: int):
        """Unmap virtual address"""
        page_aligned_addr = vaddr & ~0xFFF
        return self.entries.pop(page_aligned_addr, None)
        
    def lookup_page(self, vaddr: int) -> Optional[PageFrame]:
        """Look up physical page frame for virtual address"""
        page_aligned_addr = vaddr & ~0xFFF
        entry = self.entries.get(page_aligned_addr)
        if entry and entry['present']:
            entry['accessed'] = True
            return entry['page_frame']
        return None
        
    def protect_page(self, vaddr: int, protection: int):
        """Change page protection"""
        page_aligned_addr = vaddr & ~0xFFF
        entry = self.entries.get(page_aligned_addr)
        if entry:
            entry['protection'] = protection
            
    def mark_dirty(self, vaddr: int):
        """Mark page as dirty"""
        page_aligned_addr = vaddr & ~0xFFF
        entry = self.entries.get(page_aligned_addr)
        if entry:
            entry['dirty'] = True
            entry['page_frame'].mark_dirty()
            
    def get_stats(self) -> dict:
        """Get page table statistics"""
        total_pages = len(self.entries)
        present_pages = sum(1 for e in self.entries.values() if e['present'])
        accessed_pages = sum(1 for e in self.entries.values() if e['accessed'])
        dirty_pages = sum(1 for e in self.entries.values() if e['dirty'])
        
        return {
            'total_pages': total_pages,
            'present_pages': present_pages,
            'accessed_pages': accessed_pages,
            'dirty_pages': dirty_pages
        }
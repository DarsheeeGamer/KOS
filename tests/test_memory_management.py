"""
Unit tests for KOS memory management components
"""

import unittest
import ctypes
import os
import sys
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Add KOS to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from kos.memory.manager import MemoryManager
from kos.memory.allocator import KOSAllocator
from kos.memory.page import PageFrame, PageFrameAllocator

class TestMemoryManager(unittest.TestCase):
    """Test memory manager functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.memory_manager = MemoryManager()
    
    def test_initialization(self):
        """Test memory manager initialization"""
        self.assertIsNotNone(self.memory_manager)
        self.assertTrue(hasattr(self.memory_manager, 'total_memory'))
        self.assertTrue(hasattr(self.memory_manager, 'free_memory'))
    
    def test_memory_allocation(self):
        """Test memory allocation"""
        # Test basic allocation
        size = 1024
        addr = self.memory_manager.allocate(size)
        self.assertIsNotNone(addr)
        self.assertGreater(addr, 0)
        
        # Test deallocation
        result = self.memory_manager.deallocate(addr, size)
        self.assertTrue(result)
    
    def test_memory_mapping(self):
        """Test memory mapping operations"""
        # Test mmap
        size = 4096
        addr = self.memory_manager.mmap(0, size, 
                                       self.memory_manager.PROT_READ | self.memory_manager.PROT_WRITE,
                                       self.memory_manager.MAP_PRIVATE | self.memory_manager.MAP_ANONYMOUS,
                                       -1, 0)
        self.assertIsNotNone(addr)
        self.assertNotEqual(addr, -1)
        
        # Test munmap
        result = self.memory_manager.munmap(addr, size)
        self.assertEqual(result, 0)
    
    def test_memory_protection(self):
        """Test memory protection changes"""
        size = 4096
        addr = self.memory_manager.mmap(0, size,
                                       self.memory_manager.PROT_READ | self.memory_manager.PROT_WRITE,
                                       self.memory_manager.MAP_PRIVATE | self.memory_manager.MAP_ANONYMOUS,
                                       -1, 0)
        
        # Change protection to read-only
        result = self.memory_manager.mprotect(addr, size, self.memory_manager.PROT_READ)
        self.assertEqual(result, 0)
        
        # Cleanup
        self.memory_manager.munmap(addr, size)
    
    def test_memory_stats(self):
        """Test memory statistics"""
        stats = self.memory_manager.get_memory_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('total_memory', stats)
        self.assertIn('free_memory', stats)
        self.assertIn('used_memory', stats)
        self.assertIn('cached_memory', stats)

class TestKOSAllocator(unittest.TestCase):
    """Test KOS allocator functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.allocator = KOSAllocator()
    
    def test_malloc_free(self):
        """Test malloc and free operations"""
        # Test allocation
        size = 256
        ptr = self.allocator.malloc(size)
        self.assertIsNotNone(ptr)
        self.assertGreater(ptr, 0)
        
        # Test free
        self.allocator.free(ptr)
    
    def test_calloc(self):
        """Test calloc operation"""
        num = 10
        size = 32
        ptr = self.allocator.calloc(num, size)
        self.assertIsNotNone(ptr)
        self.assertGreater(ptr, 0)
        
        self.allocator.free(ptr)
    
    def test_realloc(self):
        """Test realloc operation"""
        # Initial allocation
        size1 = 128
        ptr1 = self.allocator.malloc(size1)
        self.assertIsNotNone(ptr1)
        
        # Resize
        size2 = 256
        ptr2 = self.allocator.realloc(ptr1, size2)
        self.assertIsNotNone(ptr2)
        
        self.allocator.free(ptr2)
    
    def test_alignment(self):
        """Test aligned allocation"""
        size = 64
        alignment = 16
        ptr = self.allocator.aligned_alloc(alignment, size)
        self.assertIsNotNone(ptr)
        self.assertEqual(ptr % alignment, 0)  # Check alignment
        
        self.allocator.free(ptr)
    
    def test_allocation_limits(self):
        """Test allocation limits and failures"""
        # Test huge allocation (should fail)
        huge_size = 2**40  # 1TB
        ptr = self.allocator.malloc(huge_size)
        self.assertIsNone(ptr)
        
        # Test zero allocation
        ptr = self.allocator.malloc(0)
        self.assertIsNotNone(ptr)  # Some allocators return valid pointer for 0
        if ptr:
            self.allocator.free(ptr)

class TestPageFrameAllocator(unittest.TestCase):
    """Test page frame allocator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.page_allocator = PageFrameAllocator()
    
    def test_page_allocation(self):
        """Test page allocation and deallocation"""
        # Allocate single page
        page = self.page_allocator.alloc_page()
        self.assertIsInstance(page, PageFrame)
        self.assertIsNotNone(page.physical_addr)
        
        # Free page
        self.page_allocator.free_page(page)
    
    def test_multi_page_allocation(self):
        """Test multi-page allocation"""
        order = 2  # 4 pages
        pages = self.page_allocator.alloc_pages(order)
        self.assertIsInstance(pages, list)
        self.assertEqual(len(pages), 2**order)
        
        for page in pages:
            self.assertIsInstance(page, PageFrame)
        
        # Free pages
        self.page_allocator.free_pages(pages)
    
    def test_page_flags(self):
        """Test page flags and metadata"""
        page = self.page_allocator.alloc_page()
        
        # Test flag operations
        self.assertFalse(page.is_dirty())
        page.set_dirty()
        self.assertTrue(page.is_dirty())
        
        page.clear_dirty()
        self.assertFalse(page.is_dirty())
        
        self.page_allocator.free_page(page)
    
    def test_page_reference_counting(self):
        """Test page reference counting"""
        page = self.page_allocator.alloc_page()
        
        # Initial reference count should be 1
        self.assertEqual(page.ref_count, 1)
        
        # Increment reference
        page.get()
        self.assertEqual(page.ref_count, 2)
        
        # Decrement reference
        page.put()
        self.assertEqual(page.ref_count, 1)
        
        self.page_allocator.free_page(page)

class TestPageFrame(unittest.TestCase):
    """Test page frame functionality"""
    
    def test_page_creation(self):
        """Test page frame creation"""
        phys_addr = 0x1000
        page = PageFrame(phys_addr)
        
        self.assertEqual(page.physical_addr, phys_addr)
        self.assertEqual(page.ref_count, 1)
        self.assertEqual(page.flags, 0)
    
    def test_page_mapping(self):
        """Test virtual-physical mapping"""
        phys_addr = 0x2000
        virt_addr = 0x40000000
        page = PageFrame(phys_addr)
        
        page.map_virtual(virt_addr)
        self.assertEqual(page.virtual_addr, virt_addr)
        self.assertTrue(page.is_mapped())
        
        page.unmap_virtual()
        self.assertIsNone(page.virtual_addr)
        self.assertFalse(page.is_mapped())
    
    def test_page_locking(self):
        """Test page locking mechanisms"""
        page = PageFrame(0x3000)
        
        self.assertFalse(page.is_locked())
        
        page.lock()
        self.assertTrue(page.is_locked())
        
        page.unlock()
        self.assertFalse(page.is_locked())

class TestKernelMemorySubsystem(unittest.TestCase):
    """Test kernel memory management integration"""
    
    @patch('kos.kernel.mm.mm_wrapper')
    def test_buddy_allocator(self, mock_mm):
        """Test buddy allocator integration"""
        # Mock C library functions
        mock_mm.buddy_alloc.return_value = 0x10000
        mock_mm.buddy_free.return_value = 0
        
        from kos.kernel.mm.mm_wrapper import buddy_alloc, buddy_free
        
        # Test allocation
        order = 2
        addr = buddy_alloc(order)
        self.assertEqual(addr, 0x10000)
        
        # Test deallocation
        result = buddy_free(addr, order)
        self.assertEqual(result, 0)
    
    @patch('kos.kernel.mm.mm_wrapper')
    def test_slab_allocator(self, mock_mm):
        """Test slab allocator integration"""
        # Mock slab functions
        mock_mm.slab_create.return_value = 1  # cache ID
        mock_mm.slab_alloc.return_value = 0x20000
        mock_mm.slab_free.return_value = 0
        
        from kos.kernel.mm.mm_wrapper import slab_create, slab_alloc, slab_free
        
        # Create slab cache
        cache_id = slab_create("test_cache", 64, 16)
        self.assertEqual(cache_id, 1)
        
        # Allocate from slab
        addr = slab_alloc(cache_id)
        self.assertEqual(addr, 0x20000)
        
        # Free to slab
        result = slab_free(cache_id, addr)
        self.assertEqual(result, 0)
    
    def test_memory_stress(self):
        """Stress test memory operations"""
        allocator = KOSAllocator()
        allocated_ptrs = []
        
        # Allocate many small blocks
        for i in range(100):
            size = 32 + (i % 64)
            ptr = allocator.malloc(size)
            if ptr:
                allocated_ptrs.append(ptr)
        
        # Free all blocks
        for ptr in allocated_ptrs:
            allocator.free(ptr)
        
        # Test should complete without crashes
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
#!/usr/bin/env python3
"""
Comprehensive test suite for KOS Kernel Memory Management System

This test suite validates all components of the memory management system:
- Buddy allocator
- Slab allocator  
- kmalloc/kfree
- Page table management
- Memory mapping (mmap/munmap)
- Page fault handling
"""

import unittest
import sys
import os
import time
import random
from typing import List, Dict, Any

# Add the mm module to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from mm_wrapper import (
        KernelMM, GFPFlags, ProtFlags, MapFlags, PTEFlags,
        alloc_pages, free_pages, kmalloc, kfree, mmap, munmap,
        get_kernel_mm, MMError
    )
except ImportError as e:
    print(f"Failed to import mm_wrapper: {e}")
    print("Make sure the memory management library is built and accessible")
    sys.exit(1)

class TestBuddyAllocator(unittest.TestCase):
    """Test buddy allocator functionality"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_single_page_allocation(self):
        """Test allocating and freeing single pages"""
        pfn = self.mm.alloc_pages(order=0)
        self.assertIsNotNone(pfn, "Failed to allocate single page")
        self.assertGreater(pfn, 0, "Invalid PFN returned")
        
        result = self.mm.free_pages(pfn, order=0)
        self.assertTrue(result, "Failed to free single page")
    
    def test_multi_page_allocation(self):
        """Test allocating multiple contiguous pages"""
        for order in range(1, 6):  # Test orders 1-5 (2-32 pages)
            with self.subTest(order=order):
                pfn = self.mm.alloc_pages(order=order)
                self.assertIsNotNone(pfn, f"Failed to allocate {1<<order} pages")
                
                result = self.mm.free_pages(pfn, order=order)
                self.assertTrue(result, f"Failed to free {1<<order} pages")
    
    def test_allocation_failure_handling(self):
        """Test handling of allocation failures"""
        # Try to allocate a very large order that should fail
        pfn = self.mm.alloc_pages(order=20)  # 1M pages - should fail
        self.assertIsNone(pfn, "Should fail to allocate excessive pages")
    
    def test_fragmentation_handling(self):
        """Test allocator behavior under fragmentation"""
        allocated = []
        
        # Allocate many small blocks
        for i in range(100):
            pfn = self.mm.alloc_pages(order=0)
            if pfn:
                allocated.append(pfn)
        
        # Free every other block to create fragmentation
        for i in range(0, len(allocated), 2):
            self.mm.free_pages(allocated[i], order=0)
        
        # Try to allocate larger blocks
        large_pfn = self.mm.alloc_pages(order=2)  # 4 pages
        # This might fail due to fragmentation, which is expected
        
        # Clean up remaining allocations
        for i in range(1, len(allocated), 2):
            self.mm.free_pages(allocated[i], order=0)
        
        if large_pfn:
            self.mm.free_pages(large_pfn, order=2)

class TestSlabAllocator(unittest.TestCase):
    """Test slab allocator functionality"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_cache_creation(self):
        """Test creating slab caches"""
        cache = self.mm.create_cache("test_cache_32", 32)
        self.assertIsNotNone(cache, "Failed to create 32-byte cache")
        
        cache = self.mm.create_cache("test_cache_64", 64)
        self.assertIsNotNone(cache, "Failed to create 64-byte cache")
        
        cache = self.mm.create_cache("test_cache_128", 128)
        self.assertIsNotNone(cache, "Failed to create 128-byte cache")
    
    def test_object_allocation(self):
        """Test allocating objects from caches"""
        cache = self.mm.create_cache("test_alloc_cache", 64)
        self.assertIsNotNone(cache)
        
        # Allocate multiple objects
        objects = []
        for i in range(10):
            obj = self.mm.cache_alloc(cache)
            self.assertIsNotNone(obj, f"Failed to allocate object {i}")
            objects.append(obj)
        
        # Free all objects
        for obj in objects:
            result = self.mm.cache_free(cache, obj)
            self.assertTrue(result, f"Failed to free object {obj}")
    
    def test_cache_behavior(self):
        """Test cache behavior with many allocations"""
        cache = self.mm.create_cache("test_behavior_cache", 128)
        self.assertIsNotNone(cache)
        
        allocated = []
        
        # Allocate many objects
        for i in range(200):
            obj = self.mm.cache_alloc(cache)
            if obj:
                allocated.append(obj)
        
        self.assertGreater(len(allocated), 0, "No objects were allocated")
        
        # Free half the objects
        for i in range(0, len(allocated), 2):
            self.mm.cache_free(cache, allocated[i])
        
        # Allocate more objects (should reuse freed ones)
        new_objects = []
        for i in range(50):
            obj = self.mm.cache_alloc(cache)
            if obj:
                new_objects.append(obj)
        
        # Clean up
        for i in range(1, len(allocated), 2):
            self.mm.cache_free(cache, allocated[i])
        for obj in new_objects:
            self.mm.cache_free(cache, obj)

class TestKmalloc(unittest.TestCase):
    """Test kernel memory allocation (kmalloc/kfree)"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_small_allocations(self):
        """Test small memory allocations"""
        for size in [16, 32, 64, 128, 256, 512]:
            with self.subTest(size=size):
                addr = self.mm.kmalloc(size)
                self.assertIsNotNone(addr, f"Failed to allocate {size} bytes")
                self.assertGreater(addr, 0, "Invalid address returned")
                
                result = self.mm.kfree(addr)
                self.assertTrue(result, f"Failed to free {size} byte allocation")
    
    def test_large_allocations(self):
        """Test large memory allocations"""
        for size in [1024, 2048, 4096, 8192, 16384]:
            with self.subTest(size=size):
                addr = self.mm.kmalloc(size)
                self.assertIsNotNone(addr, f"Failed to allocate {size} bytes")
                
                result = self.mm.kfree(addr)
                self.assertTrue(result, f"Failed to free {size} byte allocation")
    
    def test_zero_size_allocation(self):
        """Test zero-size allocation handling"""
        addr = self.mm.kmalloc(0)
        self.assertIsNone(addr, "Should return None for zero-size allocation")
    
    def test_very_large_allocation(self):
        """Test very large allocation that should use buddy allocator"""
        size = 64 * 1024  # 64KB - should go to buddy allocator
        addr = self.mm.kmalloc(size)
        # This might succeed or fail depending on available memory
        if addr:
            result = self.mm.kfree(addr)
            self.assertTrue(result, "Failed to free large allocation")
    
    def test_allocation_patterns(self):
        """Test various allocation patterns"""
        # Allocate increasing sizes
        allocated = []
        for i in range(1, 11):
            size = i * 100
            addr = self.mm.kmalloc(size)
            if addr:
                allocated.append((addr, size))
        
        # Free in reverse order
        for addr, size in reversed(allocated):
            result = self.mm.kfree(addr)
            self.assertTrue(result, f"Failed to free {size} byte allocation")
        
        # Allocate random sizes
        allocated = []
        for i in range(50):
            size = random.randint(1, 2048)
            addr = self.mm.kmalloc(size)
            if addr:
                allocated.append(addr)
        
        # Free randomly
        random.shuffle(allocated)
        for addr in allocated:
            self.mm.kfree(addr)

class TestMemoryMapping(unittest.TestCase):
    """Test memory mapping functionality"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_anonymous_mapping(self):
        """Test anonymous memory mapping"""
        addr = self.mm.mmap(
            length=4096,
            prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
            flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
        )
        self.assertIsNotNone(addr, "Failed to create anonymous mapping")
        self.assertGreater(addr, 0, "Invalid mapping address")
        
        result = self.mm.munmap(addr, 4096)
        self.assertTrue(result, "Failed to unmap memory")
    
    def test_fixed_mapping(self):
        """Test fixed address mapping"""
        fixed_addr = 0x10000000
        addr = self.mm.mmap(
            addr=fixed_addr,
            length=8192,
            prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
            flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS | MapFlags.MAP_FIXED
        )
        
        if addr:  # Might fail if address is not available
            self.assertEqual(addr, fixed_addr, "Fixed mapping at wrong address")
            result = self.mm.munmap(addr, 8192)
            self.assertTrue(result, "Failed to unmap fixed mapping")
    
    def test_multiple_mappings(self):
        """Test multiple mappings"""
        mappings = []
        
        # Create multiple mappings
        for i in range(10):
            size = (i + 1) * 4096
            addr = self.mm.mmap(
                length=size,
                prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
                flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
            )
            if addr:
                mappings.append((addr, size))
        
        self.assertGreater(len(mappings), 0, "No mappings were created")
        
        # Unmap all mappings
        for addr, size in mappings:
            result = self.mm.munmap(addr, size)
            self.assertTrue(result, f"Failed to unmap {size} byte mapping")
    
    def test_protection_flags(self):
        """Test different protection flags"""
        # Read-only mapping
        addr = self.mm.mmap(
            length=4096,
            prot=ProtFlags.PROT_READ,
            flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
        )
        if addr:
            self.mm.munmap(addr, 4096)
        
        # Read-write mapping
        addr = self.mm.mmap(
            length=4096,
            prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
            flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
        )
        if addr:
            self.mm.munmap(addr, 4096)
        
        # Executable mapping
        addr = self.mm.mmap(
            length=4096,
            prot=ProtFlags.PROT_READ | ProtFlags.PROT_EXEC,
            flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
        )
        if addr:
            self.mm.munmap(addr, 4096)

class TestMemoryStatistics(unittest.TestCase):
    """Test memory statistics and information functions"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_memory_info(self):
        """Test getting memory information"""
        mem_info = self.mm.get_memory_info()
        self.assertIsNotNone(mem_info)
        self.assertGreater(mem_info.total_ram, 0)
        self.assertGreaterEqual(mem_info.total_ram, mem_info.free_ram)
    
    def test_buddy_stats(self):
        """Test buddy allocator statistics"""
        stats = self.mm.get_buddy_stats()
        self.assertIsNotNone(stats)
        self.assertIn('zones', stats)
        self.assertGreater(len(stats['zones']), 0)
    
    def test_slab_stats(self):
        """Test slab allocator statistics"""
        stats = self.mm.get_slab_stats()
        self.assertIsNotNone(stats)
        self.assertIn('caches', stats)
    
    def test_vma_list(self):
        """Test virtual memory area listing"""
        # Create some mappings first
        addr1 = self.mm.mmap(length=4096)
        addr2 = self.mm.mmap(length=8192)
        
        vmas = self.mm.get_vma_list()
        self.assertIsInstance(vmas, list)
        
        # Clean up
        if addr1:
            self.mm.munmap(addr1, 4096)
        if addr2:
            self.mm.munmap(addr2, 8192)
    
    def test_system_state_dump(self):
        """Test system state dump"""
        state = self.mm.dump_system_state()
        self.assertIsInstance(state, str)
        self.assertGreater(len(state), 0)
        self.assertIn("Memory Management System State", state)

class TestStressAndPerformance(unittest.TestCase):
    """Stress tests and performance measurements"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_allocation_stress(self):
        """Stress test with many allocations"""
        allocated = []
        failures = 0
        
        # Allocate many blocks
        for i in range(500):
            size = random.randint(32, 2048)
            addr = self.mm.kmalloc(size)
            if addr:
                allocated.append((addr, size))
            else:
                failures += 1
        
        self.assertGreater(len(allocated), 0, "No allocations succeeded")
        
        # Free all allocations
        freed = 0
        for addr, size in allocated:
            if self.mm.kfree(addr):
                freed += 1
        
        self.assertEqual(freed, len(allocated), "Not all allocations were freed")
    
    def test_mapping_stress(self):
        """Stress test with many mappings"""
        mappings = []
        
        # Create many mappings
        for i in range(100):
            size = random.choice([4096, 8192, 16384])
            addr = self.mm.mmap(length=size)
            if addr:
                mappings.append((addr, size))
        
        # Unmap all
        for addr, size in mappings:
            self.mm.munmap(addr, size)
    
    def test_mixed_operations(self):
        """Test mixed allocation and mapping operations"""
        allocations = []
        mappings = []
        
        for i in range(200):
            if random.choice([True, False]):
                # kmalloc
                size = random.randint(64, 1024)
                addr = self.mm.kmalloc(size)
                if addr:
                    allocations.append((addr, size))
            else:
                # mmap
                size = random.choice([4096, 8192])
                addr = self.mm.mmap(length=size)
                if addr:
                    mappings.append((addr, size))
        
        # Clean up
        for addr, size in allocations:
            self.mm.kfree(addr)
        
        for addr, size in mappings:
            self.mm.munmap(addr, size)
    
    def test_performance_benchmark(self):
        """Basic performance benchmark"""
        # Time kmalloc operations
        start_time = time.time()
        allocations = []
        
        for i in range(1000):
            addr = self.mm.kmalloc(128)
            if addr:
                allocations.append(addr)
        
        alloc_time = time.time() - start_time
        
        # Time kfree operations
        start_time = time.time()
        for addr in allocations:
            self.mm.kfree(addr)
        
        free_time = time.time() - start_time
        
        print(f"\nPerformance Benchmark:")
        print(f"  1000 kmalloc(128): {alloc_time:.4f}s ({1000/alloc_time:.0f} ops/sec)")
        print(f"  1000 kfree:        {free_time:.4f}s ({1000/free_time:.0f} ops/sec)")

class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        self.mm = get_kernel_mm()
    
    def test_double_free(self):
        """Test double free detection/handling"""
        addr = self.mm.kmalloc(128)
        if addr:
            # First free should succeed
            result1 = self.mm.kfree(addr)
            self.assertTrue(result1)
            
            # Second free should be handled gracefully
            result2 = self.mm.kfree(addr)
            # Don't assert on result2 as behavior may vary
    
    def test_invalid_addresses(self):
        """Test handling of invalid addresses"""
        # Try to free invalid addresses
        result = self.mm.kfree(0)
        # Should handle gracefully
        
        result = self.mm.kfree(0xDEADBEEF)
        # Should handle gracefully
        
        # Try to unmap invalid addresses
        result = self.mm.munmap(0, 4096)
        # Should handle gracefully
    
    def test_excessive_allocations(self):
        """Test handling of excessive allocation requests"""
        # Try to allocate way too much memory
        addr = self.mm.kmalloc(1024 * 1024 * 1024)  # 1GB
        # Should return None or handle gracefully
        
        if addr:
            self.mm.kfree(addr)

def run_comprehensive_tests():
    """Run all test suites"""
    print("KOS Kernel Memory Management Test Suite")
    print("=" * 50)
    
    # Test basic functionality first
    basic_tests = [
        TestBuddyAllocator,
        TestSlabAllocator,
        TestKmalloc,
        TestMemoryMapping,
        TestMemoryStatistics
    ]
    
    # Advanced tests
    advanced_tests = [
        TestStressAndPerformance,
        TestErrorHandling
    ]
    
    all_tests = basic_tests + advanced_tests
    
    suite = unittest.TestSuite()
    
    for test_class in all_tests:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_comprehensive_tests()
    
    if success:
        print("\n" + "=" * 50)
        print("All tests passed! Memory management system is working correctly.")
        
        # Show final system state
        mm = get_kernel_mm()
        print("\nFinal system state:")
        print(mm.dump_system_state())
    else:
        print("\n" + "=" * 50)
        print("Some tests failed. Please check the implementation.")
        sys.exit(1)
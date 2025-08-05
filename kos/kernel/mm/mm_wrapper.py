#!/usr/bin/env python3
"""
Kernel Memory Management Python Bindings for KOS

This module provides Python bindings for the KOS kernel memory management system,
including buddy allocator, slab allocator, page table management, and memory mapping.
"""

import ctypes
import ctypes.util
import os
import sys
import logging
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MMError(Exception):
    """Memory Management Error"""
    pass

class GFPFlags(IntEnum):
    """GFP (Get Free Pages) allocation flags"""
    GFP_KERNEL = 0x01
    GFP_ATOMIC = 0x02
    GFP_USER = 0x04
    GFP_HIGHMEM = 0x08
    GFP_DMA = 0x10

class ProtFlags(IntEnum):
    """Memory protection flags"""
    PROT_READ = 0x1
    PROT_WRITE = 0x2
    PROT_EXEC = 0x4

class MapFlags(IntEnum):
    """Memory mapping flags"""
    MAP_SHARED = 0x01
    MAP_PRIVATE = 0x02
    MAP_FIXED = 0x10
    MAP_ANONYMOUS = 0x20

class PTEFlags(IntEnum):
    """Page table entry flags"""
    PTE_PRESENT = 0x001
    PTE_WRITE = 0x002
    PTE_USER = 0x004
    PTE_ACCESSED = 0x020
    PTE_DIRTY = 0x040

@dataclass
class PageInfo:
    """Information about a memory page"""
    pfn: int
    flags: int
    count: int
    order: int
    zone_name: str

@dataclass
class MemInfo:
    """System memory information"""
    total_ram: int
    free_ram: int
    shared_ram: int
    buffer_ram: int
    total_swap: int
    free_swap: int
    total_high: int
    free_high: int
    mem_unit: int

@dataclass
class VMArea:
    """Virtual memory area information"""
    start: int
    end: int
    flags: int
    pgoff: int
    size_kb: int

class KernelMM:
    """Kernel Memory Management Interface"""
    
    def __init__(self):
        self.lib = None
        self._load_library()
        self._setup_functions()
        self._initialize_subsystems()
        
    def _load_library(self):
        """Load the compiled memory management library"""
        # Try to find the compiled library
        lib_paths = [
            os.path.join(os.path.dirname(__file__), "libkos_mm.so"),
            "libkos_mm.so",
            "./libkos_mm.so"
        ]
        
        for lib_path in lib_paths:
            if os.path.exists(lib_path):
                try:
                    self.lib = ctypes.CDLL(lib_path)
                    logger.info(f"Loaded memory management library from {lib_path}")
                    return
                except OSError as e:
                    logger.warning(f"Failed to load {lib_path}: {e}")
        
        # If no compiled library found, create a mock implementation
        logger.warning("No compiled MM library found, using Python mock implementation")
        self._create_mock_implementation()
        
    def _create_mock_implementation(self):
        """Create a mock implementation for testing without compiled library"""
        class MockLib:
            def __init__(self):
                self.pages = {}  # pfn -> page_info
                self.caches = {}  # name -> cache_info
                self.allocations = {}  # addr -> size
                self.vmas = []  # list of VMAs
                self.next_pfn = 0x1000
                self.next_addr = 0x10000000
                
            def buddy_init(self):
                logger.info("Mock: Buddy allocator initialized")
                return 0
                
            def buddy_add_memory(self, start_pfn, end_pfn):
                logger.info(f"Mock: Added memory 0x{start_pfn:x} - 0x{end_pfn:x}")
                for pfn in range(start_pfn, end_pfn):
                    self.pages[pfn] = {
                        'flags': 1 << 8,  # PG_RESERVED
                        'count': 0,
                        'order': 0
                    }
                return 0
                
            def alloc_pages(self, gfp_mask, order):
                pages_needed = 1 << order
                
                # Simulate allocation failure for excessive orders
                if order > 10:
                    return 0
                
                # Find contiguous free pages
                for start_pfn in range(0x1000, 0x10000 - pages_needed):
                    # Check if all needed pages are free
                    all_free = True
                    for i in range(pages_needed):
                        pfn = start_pfn + i
                        if pfn not in self.pages or self.pages[pfn]['count'] != 0:
                            all_free = False
                            break
                    
                    if all_free:
                        # Allocate all pages
                        for i in range(pages_needed):
                            self.pages[start_pfn + i]['count'] = 1
                        return start_pfn
                
                return 0
                
            def free_pages(self, pfn, order):
                pages_to_free = 1 << order
                for i in range(pages_to_free):
                    if pfn + i in self.pages:
                        self.pages[pfn + i]['count'] = 0
                return 0
                
            def slab_init(self):
                logger.info("Mock: Slab allocator initialized")
                return 0
                
            def kmem_cache_create(self, name, size, align, flags, ctor=None):
                cache_id = len(self.caches) + 1  # Start from 1, 0 means failure
                cache_name = name.decode() if isinstance(name, bytes) else name
                self.caches[cache_name] = {
                    'id': cache_id,
                    'size': size,
                    'align': align,
                    'flags': flags,
                    'objects': {}
                }
                return cache_id
                
            def kmem_cache_alloc(self, cache_id, flags):
                addr = self.next_addr
                self.next_addr += 4096
                self.allocations[addr] = 0  # Will be set by cache
                return addr
                
            def kmem_cache_free(self, cache_id, addr):
                if addr in self.allocations:
                    del self.allocations[addr]
                return 0
                
            def kmalloc(self, size, flags):
                if size == 0:
                    return 0  # Return NULL for zero size
                addr = self.next_addr
                self.next_addr += ((size + 4095) // 4096) * 4096
                self.allocations[addr] = size
                return addr
                
            def kfree(self, addr):
                if addr in self.allocations:
                    del self.allocations[addr]
                return 0
                
            def do_mmap(self, addr, length, prot, flags, fd, offset):
                if addr == 0:
                    addr = self.next_addr
                    self.next_addr += length
                
                self.vmas.append({
                    'start': addr,
                    'end': addr + length,
                    'flags': flags,
                    'pgoff': offset // 4096
                })
                return addr
                
            def do_munmap(self, addr, length):
                self.vmas = [vma for vma in self.vmas 
                           if not (vma['start'] <= addr < vma['end'])]
                return 0
                
        self.lib = MockLib()
        
    def _setup_functions(self):
        """Setup function signatures for the C library"""
        if hasattr(self.lib, 'argtypes'):  # Real ctypes library
            # Buddy allocator functions
            self.lib.buddy_init.argtypes = []
            self.lib.buddy_init.restype = None
            
            self.lib.buddy_add_memory.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
            self.lib.buddy_add_memory.restype = None
            
            self.lib.alloc_pages.argtypes = [ctypes.c_uint, ctypes.c_uint]
            self.lib.alloc_pages.restype = ctypes.c_void_p
            
            self.lib.free_pages.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            self.lib.free_pages.restype = None
            
            # Slab allocator functions
            self.lib.slab_init.argtypes = []
            self.lib.slab_init.restype = None
            
            self.lib.kmem_cache_create.argtypes = [
                ctypes.c_char_p, ctypes.c_size_t, ctypes.c_size_t, 
                ctypes.c_ulong, ctypes.c_void_p
            ]
            self.lib.kmem_cache_create.restype = ctypes.c_void_p
            
            self.lib.kmem_cache_alloc.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            self.lib.kmem_cache_alloc.restype = ctypes.c_void_p
            
            self.lib.kmem_cache_free.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            self.lib.kmem_cache_free.restype = None
            
            # Kernel memory allocation
            self.lib.kmalloc.argtypes = [ctypes.c_size_t, ctypes.c_uint]
            self.lib.kmalloc.restype = ctypes.c_void_p
            
            self.lib.kfree.argtypes = [ctypes.c_void_p]
            self.lib.kfree.restype = None
            
            # Memory mapping
            self.lib.do_mmap.argtypes = [
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong
            ]
            self.lib.do_mmap.restype = ctypes.c_ulong
            
            self.lib.do_munmap.argtypes = [ctypes.c_ulong, ctypes.c_size_t]
            self.lib.do_munmap.restype = ctypes.c_int
        
    def _initialize_subsystems(self):
        """Initialize all memory management subsystems"""
        try:
            self.lib.buddy_init()
            self.lib.slab_init()
            
            # Add some initial memory for testing
            self.lib.buddy_add_memory(0x1000, 0x10000)  # 64MB
            
            logger.info("Memory management subsystems initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MM subsystems: {e}")
            raise MMError(f"Initialization failed: {e}")
    
    # Buddy Allocator Interface
    def alloc_pages(self, order: int = 0, gfp_flags: int = GFPFlags.GFP_KERNEL) -> Optional[int]:
        """Allocate 2^order contiguous pages"""
        try:
            pfn = self.lib.alloc_pages(gfp_flags, order)
            if pfn == 0:
                return None
            return pfn if isinstance(pfn, int) else int(pfn)
        except Exception as e:
            logger.error(f"Failed to allocate pages: {e}")
            return None
    
    def free_pages(self, pfn: int, order: int = 0) -> bool:
        """Free 2^order contiguous pages starting at pfn"""
        try:
            self.lib.free_pages(pfn, order)
            return True
        except Exception as e:
            logger.error(f"Failed to free pages: {e}")
            return False
    
    def add_memory_range(self, start_pfn: int, end_pfn: int) -> bool:
        """Add memory range to buddy allocator"""
        try:
            self.lib.buddy_add_memory(start_pfn, end_pfn)
            logger.info(f"Added memory range: 0x{start_pfn:x} - 0x{end_pfn:x}")
            return True
        except Exception as e:
            logger.error(f"Failed to add memory range: {e}")
            return False
    
    # Slab Allocator Interface
    def create_cache(self, name: str, obj_size: int, align: int = 0, 
                    flags: int = 0) -> Optional[int]:
        """Create a new slab cache"""
        try:
            cache = self.lib.kmem_cache_create(
                name.encode(), obj_size, align, flags, None
            )
            if cache == 0:
                return None
            return cache if isinstance(cache, int) else int(cache)
        except Exception as e:
            logger.error(f"Failed to create cache '{name}': {e}")
            return None
    
    def cache_alloc(self, cache: int, flags: int = GFPFlags.GFP_KERNEL) -> Optional[int]:
        """Allocate object from slab cache"""
        try:
            addr = self.lib.kmem_cache_alloc(cache, flags)
            if addr == 0:
                return None
            return addr if isinstance(addr, int) else int(addr)
        except Exception as e:
            logger.error(f"Failed to allocate from cache: {e}")
            return None
    
    def cache_free(self, cache: int, addr: int) -> bool:
        """Free object back to slab cache"""
        try:
            self.lib.kmem_cache_free(cache, addr)
            return True
        except Exception as e:
            logger.error(f"Failed to free to cache: {e}")
            return False
    
    # Kernel Memory Allocation Interface
    def kmalloc(self, size: int, flags: int = GFPFlags.GFP_KERNEL) -> Optional[int]:
        """Allocate kernel memory"""
        try:
            addr = self.lib.kmalloc(size, flags)
            if addr == 0:
                return None
            return addr if isinstance(addr, int) else int(addr)
        except Exception as e:
            logger.error(f"Failed to kmalloc {size} bytes: {e}")
            return None
    
    def kfree(self, addr: int) -> bool:
        """Free kernel memory"""
        try:
            self.lib.kfree(addr)
            return True
        except Exception as e:
            logger.error(f"Failed to kfree address 0x{addr:x}: {e}")
            return False
    
    # Memory Mapping Interface
    def mmap(self, addr: int = 0, length: int = 4096, 
            prot: int = ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
            flags: int = MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS,
            fd: int = -1, offset: int = 0) -> Optional[int]:
        """Map memory region"""
        try:
            result = self.lib.do_mmap(addr, length, prot, flags, fd, offset)
            if result == 0 or (result & 0xFFF00000) == 0xFFF00000:  # Error codes
                return None
            return result if isinstance(result, int) else int(result)
        except Exception as e:
            logger.error(f"Failed to mmap: {e}")
            return None
    
    def munmap(self, addr: int, length: int) -> bool:
        """Unmap memory region"""
        try:
            result = self.lib.do_munmap(addr, length)
            return result == 0
        except Exception as e:
            logger.error(f"Failed to munmap: {e}")
            return False
    
    # Information and Statistics
    def get_memory_info(self) -> MemInfo:
        """Get system memory information"""
        # Mock implementation
        return MemInfo(
            total_ram=64 * 1024 * 1024,  # 64MB
            free_ram=32 * 1024 * 1024,   # 32MB
            shared_ram=0,
            buffer_ram=1024 * 1024,      # 1MB
            total_swap=0,
            free_swap=0,
            total_high=0,
            free_high=0,
            mem_unit=1
        )
    
    def get_buddy_stats(self) -> Dict[str, Any]:
        """Get buddy allocator statistics"""
        if hasattr(self.lib, 'get_buddy_stats') and callable(self.lib.get_buddy_stats):
            # Would call actual C function
            pass
            
        # Mock implementation
        return {
            'zones': [
                {
                    'name': 'Normal',
                    'start_pfn': 0x1000,
                    'size': 0xF000,
                    'free_pages': 0x8000,
                    'free_areas': {i: 100 >> i for i in range(12)}
                }
            ]
        }
    
    def get_slab_stats(self) -> Dict[str, Any]:
        """Get slab allocator statistics"""
        # Mock implementation
        return {
            'caches': [
                {
                    'name': 'kmalloc-32',
                    'obj_size': 32,
                    'objs_per_slab': 128,
                    'slabs_full': 5,
                    'slabs_partial': 2,
                    'slabs_free': 1
                }
            ]
        }
    
    def get_vma_list(self) -> List[VMArea]:
        """Get list of virtual memory areas"""
        if hasattr(self.lib, 'vmas'):  # Mock implementation
            return [
                VMArea(
                    start=vma['start'],
                    end=vma['end'],
                    flags=vma['flags'],
                    pgoff=vma['pgoff'],
                    size_kb=(vma['end'] - vma['start']) // 1024
                )
                for vma in self.lib.vmas
            ]
        return []
    
    # Test and Debug Functions
    def run_memory_tests(self) -> Dict[str, bool]:
        """Run comprehensive memory management tests"""
        results = {}
        
        # Test buddy allocator
        try:
            pfn = self.alloc_pages(order=2)  # 4 pages
            if pfn:
                self.free_pages(pfn, order=2)
                results['buddy_allocator'] = True
            else:
                results['buddy_allocator'] = False
        except Exception as e:
            logger.error(f"Buddy allocator test failed: {e}")
            results['buddy_allocator'] = False
        
        # Test slab allocator
        try:
            cache = self.create_cache("test_cache", 64)
            if cache:
                addr = self.cache_alloc(cache)
                if addr:
                    self.cache_free(cache, addr)
                    results['slab_allocator'] = True
                else:
                    results['slab_allocator'] = False
            else:
                results['slab_allocator'] = False
        except Exception as e:
            logger.error(f"Slab allocator test failed: {e}")
            results['slab_allocator'] = False
        
        # Test kmalloc
        try:
            addr = self.kmalloc(1024)
            if addr:
                self.kfree(addr)
                results['kmalloc'] = True
            else:
                results['kmalloc'] = False
        except Exception as e:
            logger.error(f"kmalloc test failed: {e}")
            results['kmalloc'] = False
        
        # Test mmap
        try:
            addr = self.mmap(length=8192)
            if addr:
                self.munmap(addr, 8192)
                results['mmap'] = True
            else:
                results['mmap'] = False
        except Exception as e:
            logger.error(f"mmap test failed: {e}")
            results['mmap'] = False
        
        return results
    
    def stress_test(self, iterations: int = 1000) -> Dict[str, Any]:
        """Run stress test on memory management"""
        results = {
            'iterations': iterations,
            'allocations_succeeded': 0,
            'allocations_failed': 0,
            'frees_succeeded': 0,
            'frees_failed': 0,
            'errors': []
        }
        
        allocated = []
        
        for i in range(iterations):
            try:
                # Random allocation size
                size = (i % 10 + 1) * 1024
                addr = self.kmalloc(size)
                
                if addr:
                    allocated.append((addr, size))
                    results['allocations_succeeded'] += 1
                else:
                    results['allocations_failed'] += 1
                
                # Randomly free some allocations
                if len(allocated) > 100 and i % 10 == 0:
                    addr, size = allocated.pop(0)
                    if self.kfree(addr):
                        results['frees_succeeded'] += 1
                    else:
                        results['frees_failed'] += 1
                        
            except Exception as e:
                results['errors'].append(str(e))
        
        # Free remaining allocations
        for addr, size in allocated:
            try:
                if self.kfree(addr):
                    results['frees_succeeded'] += 1
                else:
                    results['frees_failed'] += 1
            except Exception as e:
                results['errors'].append(str(e))
        
        return results
    
    def dump_system_state(self) -> str:
        """Dump complete memory management system state"""
        output = []
        output.append("KOS Kernel Memory Management System State")
        output.append("=" * 50)
        
        # Memory info
        mem_info = self.get_memory_info()
        output.append(f"\nMemory Information:")
        output.append(f"  Total RAM: {mem_info.total_ram // 1024} KB")
        output.append(f"  Free RAM:  {mem_info.free_ram // 1024} KB")
        output.append(f"  Buffer:    {mem_info.buffer_ram // 1024} KB")
        
        # Buddy stats
        buddy_stats = self.get_buddy_stats()
        output.append(f"\nBuddy Allocator:")
        for zone in buddy_stats['zones']:
            output.append(f"  Zone {zone['name']}:")
            output.append(f"    Start PFN: 0x{zone['start_pfn']:x}")
            output.append(f"    Size: {zone['size']} pages")
            output.append(f"    Free: {zone['free_pages']} pages")
        
        # Slab stats
        slab_stats = self.get_slab_stats()
        output.append(f"\nSlab Allocator:")
        for cache in slab_stats['caches']:
            output.append(f"  Cache {cache['name']}:")
            output.append(f"    Object size: {cache['obj_size']} bytes")
            output.append(f"    Objects per slab: {cache['objs_per_slab']}")
            output.append(f"    Slabs: {cache['slabs_full']} full, "
                         f"{cache['slabs_partial']} partial, {cache['slabs_free']} free")
        
        # VMA list
        vmas = self.get_vma_list()
        if vmas:
            output.append(f"\nVirtual Memory Areas:")
            for vma in vmas:
                output.append(f"  0x{vma.start:08x} - 0x{vma.end:08x} "
                             f"[{vma.size_kb} KB] flags=0x{vma.flags:x}")
        
        return "\n".join(output)

# Global instance
_kernel_mm = None

def get_kernel_mm() -> KernelMM:
    """Get global kernel memory management instance"""
    global _kernel_mm
    if _kernel_mm is None:
        _kernel_mm = KernelMM()
    return _kernel_mm

# Convenience functions
def alloc_pages(order: int = 0, gfp_flags: int = GFPFlags.GFP_KERNEL) -> Optional[int]:
    """Allocate pages using buddy allocator"""
    return get_kernel_mm().alloc_pages(order, gfp_flags)

def free_pages(pfn: int, order: int = 0) -> bool:
    """Free pages to buddy allocator"""
    return get_kernel_mm().free_pages(pfn, order)

def kmalloc(size: int, flags: int = GFPFlags.GFP_KERNEL) -> Optional[int]:
    """Allocate kernel memory"""
    return get_kernel_mm().kmalloc(size, flags)

def kfree(addr: int) -> bool:
    """Free kernel memory"""
    return get_kernel_mm().kfree(addr)

def mmap(addr: int = 0, length: int = 4096, 
         prot: int = ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
         flags: int = MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS,
         fd: int = -1, offset: int = 0) -> Optional[int]:
    """Map memory"""
    return get_kernel_mm().mmap(addr, length, prot, flags, fd, offset)

def munmap(addr: int, length: int) -> bool:
    """Unmap memory"""
    return get_kernel_mm().munmap(addr, length)

if __name__ == "__main__":
    # Demo and test
    print("KOS Kernel Memory Management System")
    print("=" * 40)
    
    mm = get_kernel_mm()
    
    # Run tests
    print("\nRunning memory management tests...")
    test_results = mm.run_memory_tests()
    
    for test_name, passed in test_results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {test_name}: {status}")
    
    # Show system state
    print("\n" + mm.dump_system_state())
    
    # Run stress test
    print("\nRunning stress test...")
    stress_results = mm.stress_test(100)
    print(f"  Allocations: {stress_results['allocations_succeeded']} succeeded, "
          f"{stress_results['allocations_failed']} failed")
    print(f"  Frees: {stress_results['frees_succeeded']} succeeded, "
          f"{stress_results['frees_failed']} failed")
    
    if stress_results['errors']:
        print(f"  Errors: {len(stress_results['errors'])}")
        for error in stress_results['errors'][:5]:  # Show first 5 errors
            print(f"    {error}")
    
    print("\nMemory management system ready!")
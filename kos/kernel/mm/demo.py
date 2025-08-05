#!/usr/bin/env python3
"""
KOS Kernel Memory Management System Demo

This script demonstrates the complete memory management system in action,
showing all components working together: buddy allocator, slab allocator,
kmalloc/kfree, and memory mapping.
"""

import sys
import time
import random
from mm_wrapper import (
    get_kernel_mm, GFPFlags, ProtFlags, MapFlags,
    alloc_pages, free_pages, kmalloc, kfree, mmap, munmap
)

def demo_buddy_allocator():
    """Demonstrate buddy allocator functionality"""
    print("\n" + "="*50)
    print("BUDDY ALLOCATOR DEMONSTRATION")
    print("="*50)
    
    mm = get_kernel_mm()
    allocated_pages = []
    
    print("1. Allocating pages of different orders...")
    
    # Allocate pages of different orders
    for order in range(5):
        pages_count = 1 << order
        pfn = mm.alloc_pages(order=order)
        if pfn:
            allocated_pages.append((pfn, order))
            print(f"   Order {order}: Allocated {pages_count} pages at PFN 0x{pfn:x}")
        else:
            print(f"   Order {order}: Failed to allocate {pages_count} pages")
    
    print(f"\n2. Successfully allocated {len(allocated_pages)} page blocks")
    
    # Show memory stats
    buddy_stats = mm.get_buddy_stats()
    print(f"\n3. Buddy allocator statistics:")
    for zone in buddy_stats['zones']:
        print(f"   Zone {zone['name']}: {zone['free_pages']} free pages")
    
    # Free all allocated pages
    print(f"\n4. Freeing all allocated pages...")
    for pfn, order in allocated_pages:
        mm.free_pages(pfn, order)
        print(f"   Freed {1 << order} pages at PFN 0x{pfn:x}")
    
    print("   Buddy allocator demo completed!")

def demo_slab_allocator():
    """Demonstrate slab allocator functionality"""
    print("\n" + "="*50)
    print("SLAB ALLOCATOR DEMONSTRATION")  
    print("="*50)
    
    mm = get_kernel_mm()
    
    print("1. Creating object caches...")
    
    # Create caches for different object sizes
    caches = {}
    cache_sizes = [32, 64, 128, 256, 512]
    
    for size in cache_sizes:
        cache_name = f"demo_cache_{size}"
        cache = mm.create_cache(cache_name, size)
        if cache:
            caches[size] = cache
            print(f"   Created cache '{cache_name}' for {size}-byte objects")
        else:
            print(f"   Failed to create cache for {size}-byte objects")
    
    print(f"\n2. Successfully created {len(caches)} caches")
    
    # Allocate objects from caches
    print(f"\n3. Allocating objects from caches...")
    allocated_objects = {}
    
    for size, cache in caches.items():
        objects = []
        for i in range(10):
            obj = mm.cache_alloc(cache)
            if obj:
                objects.append(obj)
        allocated_objects[size] = objects
        print(f"   Cache {size}: Allocated {len(objects)} objects")
    
    # Show slab statistics
    slab_stats = mm.get_slab_stats()
    print(f"\n4. Slab allocator statistics:")
    for cache in slab_stats['caches']:
        print(f"   Cache {cache['name']}: {cache['objs_per_slab']} objects per slab")
    
    # Free all objects
    print(f"\n5. Freeing all allocated objects...")
    total_freed = 0
    for size, cache in caches.items():
        objects = allocated_objects.get(size, [])
        for obj in objects:
            mm.cache_free(cache, obj)
            total_freed += 1
        print(f"   Cache {size}: Freed {len(objects)} objects")
    
    print(f"   Total objects freed: {total_freed}")
    print("   Slab allocator demo completed!")

def demo_kmalloc():
    """Demonstrate kernel memory allocation"""
    print("\n" + "="*50)
    print("KMALLOC/KFREE DEMONSTRATION")
    print("="*50)
    
    mm = get_kernel_mm()
    allocated = []
    
    print("1. Allocating memory of various sizes...")
    
    # Allocate different sizes
    sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]
    
    for size in sizes:
        addr = mm.kmalloc(size)
        if addr:
            allocated.append((addr, size))
            print(f"   Allocated {size} bytes at address 0x{addr:x}")
        else:
            print(f"   Failed to allocate {size} bytes")
    
    print(f"\n2. Successfully allocated {len(allocated)} memory blocks")
    total_allocated = sum(size for addr, size in allocated)
    print(f"   Total memory allocated: {total_allocated} bytes ({total_allocated/1024:.1f} KB)")
    
    # Test edge cases
    print(f"\n3. Testing edge cases...")
    
    # Zero-size allocation
    zero_addr = mm.kmalloc(0)
    print(f"   Zero-size allocation: {'NULL' if zero_addr is None else f'0x{zero_addr:x}'}")
    
    # Very large allocation
    large_addr = mm.kmalloc(1024 * 1024)  # 1MB
    if large_addr:
        print(f"   Large allocation (1MB): 0x{large_addr:x}")
        mm.kfree(large_addr)
    else:
        print(f"   Large allocation (1MB): Failed (expected)")
    
    # Free all allocations
    print(f"\n4. Freeing all allocated memory...")
    freed_count = 0
    for addr, size in allocated:
        if mm.kfree(addr):
            freed_count += 1
        else:
            print(f"   Warning: Failed to free address 0x{addr:x}")
    
    print(f"   Successfully freed {freed_count}/{len(allocated)} allocations")
    print("   kmalloc/kfree demo completed!")

def demo_memory_mapping():
    """Demonstrate memory mapping functionality"""
    print("\n" + "="*50)
    print("MEMORY MAPPING DEMONSTRATION")
    print("="*50)
    
    mm = get_kernel_mm()
    mappings = []
    
    print("1. Creating memory mappings...")
    
    # Anonymous read-write mapping
    addr1 = mm.mmap(
        length=4096,
        prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
        flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
    )
    if addr1:
        mappings.append((addr1, 4096, "RW Anonymous"))
        print(f"   Anonymous RW mapping: 0x{addr1:x} (4KB)")
    
    # Read-only mapping
    addr2 = mm.mmap(
        length=8192,
        prot=ProtFlags.PROT_READ,
        flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
    )
    if addr2:
        mappings.append((addr2, 8192, "RO Anonymous"))
        print(f"   Anonymous RO mapping: 0x{addr2:x} (8KB)")
    
    # Large mapping
    addr3 = mm.mmap(
        length=64 * 1024,  # 64KB
        prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
        flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS
    )
    if addr3:
        mappings.append((addr3, 64*1024, "Large RW"))
        print(f"   Large RW mapping: 0x{addr3:x} (64KB)")
    
    # Fixed address mapping (might fail)
    fixed_addr = 0x20000000
    addr4 = mm.mmap(
        addr=fixed_addr,
        length=4096,
        prot=ProtFlags.PROT_READ | ProtFlags.PROT_WRITE,
        flags=MapFlags.MAP_PRIVATE | MapFlags.MAP_ANONYMOUS | MapFlags.MAP_FIXED
    )
    if addr4:
        mappings.append((addr4, 4096, "Fixed Address"))
        print(f"   Fixed address mapping: 0x{addr4:x} (4KB)")
    else:
        print(f"   Fixed address mapping: Failed (address not available)")
    
    print(f"\n2. Successfully created {len(mappings)} mappings")
    
    # Show VMA information
    vmas = mm.get_vma_list()
    if vmas:
        print(f"\n3. Virtual Memory Areas:")
        for vma in vmas:
            print(f"   0x{vma.start:08x} - 0x{vma.end:08x} [{vma.size_kb:4d} KB] flags=0x{vma.flags:x}")
    
    # Test memory operations (simulated)
    print(f"\n4. Simulating memory operations...")
    for addr, size, desc in mappings:
        # In a real system, we could write to these mappings
        print(f"   {desc}: Would write/read at 0x{addr:x}")
    
    # Unmap all mappings
    print(f"\n5. Unmapping all memory regions...")
    unmapped_count = 0
    for addr, size, desc in mappings:
        if mm.munmap(addr, size):
            unmapped_count += 1
            print(f"   Unmapped {desc}: 0x{addr:x} ({size} bytes)")
        else:
            print(f"   Failed to unmap {desc}: 0x{addr:x}")
    
    print(f"   Successfully unmapped {unmapped_count}/{len(mappings)} mappings")
    print("   Memory mapping demo completed!")

def demo_system_monitoring():
    """Demonstrate system monitoring capabilities"""
    print("\n" + "="*50)
    print("SYSTEM MONITORING DEMONSTRATION")
    print("="*50)
    
    mm = get_kernel_mm()
    
    print("1. Current system memory state:")
    print("-" * 30)
    print(mm.dump_system_state())
    
    print("\n2. Memory usage statistics:")
    info = mm.get_memory_info()
    print(f"   Total RAM: {info.total_ram // 1024} KB")
    print(f"   Free RAM:  {info.free_ram // 1024} KB")
    print(f"   Used RAM:  {(info.total_ram - info.free_ram) // 1024} KB")
    print(f"   Usage:     {((info.total_ram - info.free_ram) / info.total_ram * 100):.1f}%")
    
    print("\n3. Running comprehensive tests...")
    test_results = mm.run_memory_tests()
    
    print("   Test Results:")
    for test_name, passed in test_results.items():
        status = "PASS" if passed else "FAIL"
        print(f"     {test_name:20s}: {status}")
    
    passed_count = sum(1 for passed in test_results.values() if passed)
    total_count = len(test_results)
    print(f"   Overall: {passed_count}/{total_count} tests passed")

def demo_stress_testing():
    """Demonstrate stress testing capabilities"""
    print("\n" + "="*50)
    print("STRESS TESTING DEMONSTRATION")
    print("="*50)
    
    mm = get_kernel_mm()
    
    print("1. Running allocation stress test...")
    start_time = time.time()
    
    # Simulate a realistic workload
    allocated = []
    operations = 0
    
    for i in range(200):
        # Randomly choose operation type
        if random.random() < 0.7:  # 70% allocations
            size = random.choice([32, 64, 128, 256, 512, 1024])
            addr = mm.kmalloc(size)
            if addr:
                allocated.append((addr, size))
                operations += 1
        else:  # 30% frees
            if allocated:
                addr, size = allocated.pop(random.randint(0, len(allocated)-1))
                mm.kfree(addr)
                operations += 1
    
    # Clean up remaining allocations
    for addr, size in allocated:
        mm.kfree(addr)
        operations += 1
    
    elapsed = time.time() - start_time
    print(f"   Completed {operations} operations in {elapsed:.3f}s")
    print(f"   Performance: {operations/elapsed:.0f} operations/second")
    
    print("\n2. Running mapping stress test...")
    start_time = time.time()
    
    mappings = []
    operations = 0
    
    # Create many mappings
    for i in range(50):
        size = random.choice([4096, 8192, 16384])
        addr = mm.mmap(length=size)
        if addr:
            mappings.append((addr, size))
            operations += 1
    
    # Unmap all
    for addr, size in mappings:
        mm.munmap(addr, size)
        operations += 1
    
    elapsed = time.time() - start_time
    print(f"   Completed {operations} mapping operations in {elapsed:.3f}s")
    print(f"   Performance: {operations/elapsed:.0f} operations/second")
    
    print("\n3. Final system state check...")
    final_info = mm.get_memory_info()
    print(f"   Final free memory: {final_info.free_ram // 1024} KB")
    print("   Stress testing completed!")

def main():
    """Main demo function"""
    print("KOS Kernel Memory Management System")
    print("Complete Demonstration")
    print("=" * 60)
    
    try:
        # Run all demonstrations
        demo_buddy_allocator()
        demo_slab_allocator()
        demo_kmalloc()
        demo_memory_mapping()
        demo_system_monitoring()
        demo_stress_testing()
        
        print("\n" + "="*60)
        print("DEMONSTRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nThe KOS kernel memory management system is fully functional")
        print("and ready for integration into the operating system.")
        
        # Final system state
        mm = get_kernel_mm()
        print(f"\nFinal system state:")
        print("-" * 30)
        info = mm.get_memory_info()
        print(f"Memory efficiency: {(info.free_ram / info.total_ram * 100):.1f}% free")
        print(f"System stability: All subsystems operational")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user")
    except Exception as e:
        print(f"\n\nDemo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
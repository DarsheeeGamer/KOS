#!/usr/bin/env python3
"""
Simple test for KOS components
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_bootloader():
    from kos.boot.bootloader import KOSBootloader
    print("Testing bootloader...")
    bootloader = KOSBootloader()
    print("✓ Bootloader created successfully")
    return bootloader

def test_memory_manager():
    from kos.memory.manager import KOSMemoryManager
    print("Testing memory manager...")
    mm = KOSMemoryManager(1024 * 1024 * 1024)  # 1GB
    print("✓ Memory manager created successfully")
    
    # Test allocation
    page = mm.alloc_page()
    if page:
        print("✓ Page allocation works")
        mm.free_page(page)
        print("✓ Page deallocation works")
    return mm

def test_process_manager():
    from kos.boot.kernel import KOSKernel
    from kos.process.manager import KOSProcessManager
    print("Testing process manager...")
    
    # Create a mock kernel
    kernel = KOSKernel()
    pm = KOSProcessManager(kernel)
    print("✓ Process manager created successfully")
    
    # Test process creation
    proc = pm.create_process("test", "/bin/test")
    if proc:
        print(f"✓ Process created successfully (PID: {proc.pid})")
    return pm

def main():
    print("=" * 50)
    print("KOS Component Test Suite")
    print("=" * 50)
    
    try:
        # Test individual components
        bootloader = test_bootloader()
        mm = test_memory_manager()
        pm = test_process_manager()
        
        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
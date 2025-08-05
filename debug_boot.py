#!/usr/bin/env python3
"""
Debug boot process step by step
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_kernel_init():
    print("Creating kernel...")
    from kos.boot.kernel import KOSKernel
    kernel = KOSKernel()
    print("✓ Kernel created")
    
    print("Testing memory init...")
    hardware_info = {
        'memory': {'total': 1024 * 1024 * 1024},  # 1GB
        'cpu': {'cores': 2, 'model': 'Intel Test CPU', 'frequency': 2400}
    }
    kernel.hardware_info = hardware_info
    try:
        kernel._init_memory_management()
        print("✓ Memory management initialized")
    except Exception as e:
        print(f"❌ Memory init failed: {e}")
        return
    
    print("Testing process init...")
    try:
        kernel._init_process_management()
        print("✓ Process management initialized")
    except Exception as e:
        print(f"❌ Process init failed: {e}")
        return
    
    print("Testing scheduler init...")
    try:
        kernel._init_scheduler()
        print("✓ Scheduler initialized")
    except Exception as e:
        print(f"❌ Scheduler init failed: {e}")
        return
        
    print("Testing VFS init...")
    try:
        kernel._init_vfs()
        print("✓ VFS initialized")
    except Exception as e:
        print(f"❌ VFS init failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    debug_kernel_init()
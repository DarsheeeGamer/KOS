#!/usr/bin/env python3
"""
Debug boot process - device and network init
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def debug_device_network_init():
    print("Creating kernel...")
    from kos.boot.kernel import KOSKernel
    kernel = KOSKernel()
    
    hardware_info = {
        'memory': {'total': 1024 * 1024 * 1024},  # 1GB
        'cpu': {'cores': 2, 'model': 'Intel Test CPU', 'frequency': 2400}
    }
    kernel.hardware_info = hardware_info
    
    # Initialize dependencies
    kernel._init_memory_management()
    kernel._init_process_management()
    kernel._init_scheduler()
    kernel._init_vfs()
    
    print("Testing device init...")
    try:
        kernel._init_device_drivers()
        print("✓ Device drivers initialized")
    except Exception as e:
        print(f"❌ Device init failed: {e}")
        import traceback
        traceback.print_exc()
        return
        
    print("Testing network init...")
    try:
        kernel._init_network_stack()
        print("✓ Network stack initialized")
    except Exception as e:
        print(f"❌ Network init failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    debug_device_network_init()
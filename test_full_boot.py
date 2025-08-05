#!/usr/bin/env python3
"""
Test full boot process with timeout
"""

import sys
import os
import signal
import threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def timeout_handler(signum, frame):
    print("\n❌ Boot process timed out!")
    sys.exit(1)

def test_full_boot():
    from kos.boot.bootloader import KOSBootloader
    
    print("=" * 50)
    print("Testing Full KOS Boot Process")
    print("=" * 50)
    
    # Set timeout of 10 seconds
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(10)
    
    try:
        bootloader = KOSBootloader()
        print("Bootloader created, starting boot...")
        
        # This should complete within 10 seconds
        kernel = bootloader.boot()
        
        signal.alarm(0)  # Cancel timeout
        print("✓ Boot completed successfully!")
        
        # Test some kernel functionality
        print(f"Kernel version: {kernel.system_info['kernel_version']}")
        print(f"Uptime: {kernel.get_uptime():.3f} seconds")
        print(f"Memory info: {kernel.get_memory_info()}")
        
        # Gracefully shutdown
        print("Shutting down...")
        kernel.halt()
        
    except Exception as e:
        signal.alarm(0)
        print(f"❌ Boot failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(test_full_boot())
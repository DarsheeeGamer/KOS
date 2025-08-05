#!/usr/bin/env python3
"""
Test script for KOS boot process
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kos.boot.bootloader import KOSBootloader

def main():
    """Test the complete KOS boot process"""
    print("=" * 60)
    print("KOS (Kaede Operating System) - Boot Test")
    print("=" * 60)
    print()
    
    # Create bootloader
    bootloader = KOSBootloader()
    
    # Configure boot parameters for testing
    bootloader.set_boot_param('kos.debug', True)
    bootloader.set_boot_param('quiet', False)
    
    try:
        # Start boot process
        kernel = bootloader.boot()
        
        if kernel:
            print("\n" + "=" * 60)
            print("BOOT COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            
            # Show system information
            print(f"Kernel Version: {kernel.VERSION}-{kernel.RELEASE}")
            print(f"System uptime: {kernel.get_uptime():.3f} seconds")
            print(f"Boot time: {bootloader.boot_time:.3f} seconds")
            
            # Memory information
            if kernel.memory_manager:
                mem_info = kernel.get_memory_info()
                print(f"Total Memory: {mem_info['total'] // (1024*1024)}MB")
                print(f"Free Memory: {mem_info['free'] // (1024*1024)}MB")
                print(f"Used Memory: {mem_info['used'] // (1024*1024)}MB")
                
            # Process information
            if kernel.process_manager:
                proc_stats = kernel.get_process_count()
                print(f"Total Processes: {proc_stats['total']}")
                print(f"Running: {proc_stats['running']}")
                print(f"Sleeping: {proc_stats['sleeping']}")
                
            # Load average
            load_avg = kernel.get_load_average()
            print(f"Load Average: {load_avg[0]:.2f}, {load_avg[1]:.2f}, {load_avg[2]:.2f}")
            
            print("\nKOS is now running! Press Ctrl+C to shutdown.")
            
            # Keep system running
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down KOS...")
                kernel.halt()
                
        else:
            print("BOOT FAILED!")
            return 1
            
    except Exception as e:
        print(f"BOOT ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
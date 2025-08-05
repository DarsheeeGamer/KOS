#!/usr/bin/env python3
"""
Minimal test for KOS Device Driver Framework
"""

def test_imports():
    try:
        # Test basic imports
        import ctypes
        import threading
        from enum import IntEnum
        from dataclasses import dataclass
        print("✓ Basic imports successful")
        
        # Test driver wrapper import
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        print("✓ Attempting to import drivers_wrapper...")
        from drivers_wrapper import DeviceType, IOCTLCommands, create_char_device
        print("✓ drivers_wrapper imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_basic_device():
    try:
        from drivers_wrapper import create_char_device, destroy_device
        
        # Create a simple character device
        print("Creating character device...")
        char_dev = create_char_device("minimal_test")
        print(f"✓ Created device: {char_dev.name}")
        
        # Test basic write/read
        test_data = b"Test"
        char_dev.write(test_data)
        read_data = char_dev.read()
        
        if read_data == test_data:
            print("✓ Basic I/O test passed")
        else:
            print(f"✗ I/O test failed: {read_data} != {test_data}")
        
        # Cleanup
        destroy_device("minimal_test")
        print("✓ Device cleanup successful")
        
        return True
    except Exception as e:
        print(f"✗ Device test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("KOS Driver Framework - Minimal Test")
    print("=" * 40)
    
    if test_imports():
        if test_basic_device():
            print("\n✓ All minimal tests passed!")
        else:
            print("\n✗ Device tests failed")
    else:
        print("\n✗ Import tests failed")
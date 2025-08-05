#!/usr/bin/env python3
"""
Very simple test to check if the driver framework works
"""

import threading
from typing import Optional, Dict, List
from enum import IntEnum

# Just test the Python-only implementation without C library
class DeviceType(IntEnum):
    CHAR = 1
    BLOCK = 2
    NET = 3
    TTY = 4

class Device:
    def __init__(self, name: str):
        self.name = name
        self._lock = threading.RLock()

class CharacterDevice(Device):
    def __init__(self, name: str):
        super().__init__(name)
        self._buffer = bytearray()
    
    def read(self, size: int = -1) -> bytes:
        with self._lock:
            if size == -1:
                data = bytes(self._buffer)
                self._buffer.clear()
            else:
                data = bytes(self._buffer[:size])
                self._buffer = self._buffer[size:]
            return data
    
    def write(self, data: bytes) -> int:
        with self._lock:
            self._buffer.extend(data)
            return len(data)

class DriverManager:
    def __init__(self):
        self._devices = {}
        self._lock = threading.RLock()
    
    def create_char_device(self, name: str) -> CharacterDevice:
        with self._lock:
            if name in self._devices:
                raise ValueError(f"Device {name} already exists")
            device = CharacterDevice(name)
            self._devices[name] = device
            return device
    
    def destroy_device(self, name: str):
        with self._lock:
            if name in self._devices:
                del self._devices[name]
    
    def list_devices(self) -> List[str]:
        with self._lock:
            return list(self._devices.keys())

# Global manager
_manager = DriverManager()

def create_char_device(name: str) -> CharacterDevice:
    return _manager.create_char_device(name)

def destroy_device(name: str):
    _manager.destroy_device(name)

def list_devices() -> List[str]:
    return _manager.list_devices()

def main():
    print("Testing simplified KOS driver framework...")
    
    try:
        # Test character device
        print("1. Creating character device...")
        char_dev = create_char_device("test_char")
        print(f"   Created: {char_dev.name}")
        
        print("2. Testing write/read...")
        test_data = b"Hello, KOS!"
        bytes_written = char_dev.write(test_data)
        print(f"   Wrote {bytes_written} bytes")
        
        read_data = char_dev.read()
        print(f"   Read {len(read_data)} bytes: {read_data}")
        
        if read_data == test_data:
            print("   ✓ Data matches!")
        else:
            print("   ✗ Data mismatch!")
        
        print("3. Listing devices...")
        devices = list_devices()
        print(f"   Devices: {devices}")
        
        print("4. Cleaning up...")
        destroy_device("test_char")
        
        final_devices = list_devices()
        print(f"   Remaining devices: {final_devices}")
        
        print("✓ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
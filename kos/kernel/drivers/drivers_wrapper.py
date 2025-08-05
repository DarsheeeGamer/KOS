"""
KOS Device Driver Manager Python Wrapper

Provides Python interface to KOS device drivers including:
- Character devices
- Block devices
- Network devices
- TTY subsystem
"""

import ctypes
import os
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger('KOS.drivers')


class DeviceType(IntEnum):
    """Device types"""
    CHAR = 1
    BLOCK = 2
    NETWORK = 3
    TTY = 4


@dataclass
class DeviceInfo:
    """Device information"""
    name: str
    type: DeviceType
    major: int
    minor: int
    flags: int = 0


class KOSDriverManager:
    """KOS Device Driver Manager"""
    
    def __init__(self):
        self.lib = None
        self._devices: Dict[str, DeviceInfo] = {}
        self._load_library()
    
    def _load_library(self):
        """Load the driver library"""
        lib_path = os.path.join(os.path.dirname(__file__), "..", "libkos_kernel.so")
        
        if os.path.exists(lib_path):
            try:
                self.lib = ctypes.CDLL(lib_path)
                logger.info("Driver library loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load driver library: {e}")
        else:
            logger.warning("Driver library not found, using mock implementation")
    
    def register_device(self, name: str, dev_type: DeviceType, major: int, minor: int) -> bool:
        """Register a device"""
        device = DeviceInfo(name, dev_type, major, minor)
        self._devices[name] = device
        logger.info(f"Registered device: {name}")
        return True
    
    def unregister_device(self, name: str) -> bool:
        """Unregister a device"""
        if name in self._devices:
            del self._devices[name]
            logger.info(f"Unregistered device: {name}")
            return True
        return False
    
    def get_devices(self) -> List[DeviceInfo]:
        """Get list of registered devices"""
        return list(self._devices.values())
    
    def shutdown(self):
        """Shutdown driver manager"""
        self._devices.clear()
        logger.info("Driver manager shutdown")
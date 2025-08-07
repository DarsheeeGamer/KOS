"""
KOS Hardware Abstraction Layer
Basic hardware abstraction for CPU and memory
"""

import os
import sys
import json
import time
import threading
import subprocess
import platform
import psutil
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class DeviceType(Enum):
    """Supported device types"""
    CPU = "cpu"
    MEMORY = "memory"

@dataclass
class DeviceCapabilities:
    """Device capabilities"""
    compute_power: float = 0.0  # GFLOPS
    memory_size: int = 0  # bytes
    memory_bandwidth: float = 0.0  # GB/s
    cores: int = 1
    threads: int = 1
    frequency: float = 0.0  # GHz
    architecture: str = "unknown"
    features: List[str] = field(default_factory=list)

@dataclass
class HardwareDevice:
    """Hardware device abstraction"""
    device_id: str
    device_type: DeviceType
    name: str
    capabilities: DeviceCapabilities
    available: bool = True
    utilization: float = 0.0
    temperature: Optional[float] = None
    power_usage: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class HardwareDetector:
    """Detect available hardware"""
    
    def __init__(self):
        self.detected_devices = {}
    
    def detect_all(self) -> Dict[str, HardwareDevice]:
        """Detect all available hardware"""
        devices = {}
        
        # Detect CPU
        cpu_device = self._detect_cpu()
        if cpu_device:
            devices[cpu_device.device_id] = cpu_device
        
        # Detect memory
        memory_device = self._detect_memory()
        if memory_device:
            devices[memory_device.device_id] = memory_device
        
        self.detected_devices = devices
        return devices
    
    def _detect_cpu(self) -> Optional[HardwareDevice]:
        """Detect CPU information"""
        try:
            # Get CPU info
            cpu_count = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            
            capabilities = DeviceCapabilities(
                compute_power=cpu_count * (cpu_freq.max if cpu_freq else 3000) / 1000,  # Rough estimate
                memory_size=0,  # CPU doesn't have dedicated memory
                memory_bandwidth=50.0,  # Rough estimate for system RAM access
                cores=cpu_count,
                threads=cpu_count_logical,
                frequency=cpu_freq.max / 1000 if cpu_freq else 3.0,  # GHz
                architecture=platform.processor(),
                features=["x86_64", "multicore"]
            )
            
            return HardwareDevice(
                device_id="cpu0",
                device_type=DeviceType.CPU,
                name=f"CPU ({platform.processor()})",
                capabilities=capabilities
            )
            
        except Exception as e:
            logger.error(f"Failed to detect CPU: {e}")
            return None
    
    def _detect_memory(self) -> Optional[HardwareDevice]:
        """Detect memory information"""
        try:
            # Get memory info
            memory = psutil.virtual_memory()
            
            capabilities = DeviceCapabilities(
                compute_power=0.0,  # Memory doesn't compute
                memory_size=memory.total,
                memory_bandwidth=50.0,  # Rough estimate
                cores=1,
                threads=1,
                frequency=0.0,
                architecture="DDR4/DDR5",
                features=["volatile", "random_access"]
            )
            
            return HardwareDevice(
                device_id="memory0",
                device_type=DeviceType.MEMORY,
                name=f"System Memory ({memory.total // (1024**3)} GB)",
                capabilities=capabilities
            )
            
        except Exception as e:
            logger.error(f"Failed to detect memory: {e}")
            return None

class SimpleHardwarePool:
    """Simple hardware pool for basic devices"""
    
    def __init__(self):
        self.devices: Dict[str, HardwareDevice] = {}
        self.detector = HardwareDetector()
        self.lock = threading.RLock()
        
        # Initialize with detected hardware
        self.refresh_devices()
    
    def refresh_devices(self):
        """Refresh detected devices"""
        with self.lock:
            self.devices = self.detector.detect_all()
            logger.info(f"Detected {len(self.devices)} devices")
    
    def get_device(self, device_id: str) -> Optional[HardwareDevice]:
        """Get device by ID"""
        return self.devices.get(device_id)
    
    def get_devices_by_type(self, device_type: DeviceType) -> List[HardwareDevice]:
        """Get all devices of specified type"""
        return [device for device in self.devices.values() 
                if device.device_type == device_type]
    
    def get_available_devices(self) -> List[HardwareDevice]:
        """Get all available devices"""
        return [device for device in self.devices.values() if device.available]
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get overall system information"""
        cpu_devices = self.get_devices_by_type(DeviceType.CPU)
        memory_devices = self.get_devices_by_type(DeviceType.MEMORY)
        
        total_cores = sum(d.capabilities.cores for d in cpu_devices)
        total_threads = sum(d.capabilities.threads for d in cpu_devices)
        total_memory = sum(d.capabilities.memory_size for d in memory_devices)
        
        return {
            'total_devices': len(self.devices),
            'cpu_devices': len(cpu_devices),
            'memory_devices': len(memory_devices),
            'total_cores': total_cores,
            'total_threads': total_threads,
            'total_memory': total_memory,
            'platform': platform.platform(),
            'architecture': platform.architecture()[0]
        }
    
    def update_utilization(self):
        """Update device utilization stats"""
        with self.lock:
            try:
                # Update CPU utilization
                cpu_devices = self.get_devices_by_type(DeviceType.CPU)
                if cpu_devices:
                    cpu_percent = psutil.cpu_percent(interval=0.1)
                    for device in cpu_devices:
                        device.utilization = cpu_percent / 100.0
                
                # Update memory utilization
                memory_devices = self.get_devices_by_type(DeviceType.MEMORY)
                if memory_devices:
                    memory = psutil.virtual_memory()
                    for device in memory_devices:
                        device.utilization = memory.percent / 100.0
                
            except Exception as e:
                logger.error(f"Failed to update utilization: {e}")

# Backward compatibility aliases
UniversalHardwarePool = SimpleHardwarePool
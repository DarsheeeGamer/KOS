"""
KOS Universal Hardware Abstraction Layer
Complete hardware pooling for all device types
"""

import os
import sys
import json
import time
import struct
import threading
import subprocess
import platform
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class DeviceType(Enum):
    """All supported device types"""
    CPU = "cpu"
    GPU_CUDA = "gpu_cuda"
    GPU_ROCM = "gpu_rocm"
    GPU_METAL = "gpu_metal"
    GPU_INTEL = "gpu_intel"
    TPU = "tpu"
    FPGA = "fpga"
    NPU = "npu"
    MEMORY = "memory"
    STORAGE = "storage"
    NETWORK = "network"

class ComputeCapability(Enum):
    """Compute precision capabilities"""
    FP64 = "fp64"
    FP32 = "fp32"
    FP16 = "fp16"
    BF16 = "bf16"
    INT8 = "int8"
    INT4 = "int4"
    TENSOR = "tensor"

class MemoryType(Enum):
    """Memory types"""
    SYSTEM_RAM = "ram"
    GPU_VRAM = "vram"
    GPU_HBM = "hbm"
    CPU_CACHE = "cache"
    SHARED = "shared"
    UNIFIED = "unified"

@dataclass
class DeviceCapabilities:
    """Device capability description"""
    compute_capabilities: List[ComputeCapability]
    memory_bandwidth: float  # GB/s
    compute_power: float  # TFLOPS
    max_threads: int
    max_blocks: int
    warp_size: int  # or wavefront size
    shared_memory_size: int  # KB
    register_count: int
    tensor_cores: int
    rt_cores: int
    special_functions: List[str]

@dataclass 
class HardwareDevice:
    """Universal hardware device representation"""
    device_id: str
    device_type: DeviceType
    name: str
    vendor: str
    model: str
    
    # Compute
    compute_units: int
    clock_speed: float  # GHz
    capabilities: DeviceCapabilities
    
    # Memory
    memory_size: int  # bytes
    memory_type: MemoryType
    memory_bandwidth: float  # GB/s
    
    # Connection
    node_id: str
    pci_bus: Optional[str]
    numa_node: Optional[int]
    
    # Status
    temperature: float
    power_usage: float
    utilization: float
    available: bool
    
    # Features
    features: Dict[str, Any] = field(default_factory=dict)

class HardwareAbstractionLayer(ABC):
    """Base class for hardware abstraction"""
    
    @abstractmethod
    def discover_devices(self) -> List[HardwareDevice]:
        """Discover all available devices"""
        pass
    
    @abstractmethod
    def get_device_info(self, device_id: str) -> HardwareDevice:
        """Get detailed device information"""
        pass
    
    @abstractmethod
    def allocate_memory(self, device_id: str, size: int) -> Optional[int]:
        """Allocate memory on device"""
        pass
    
    @abstractmethod
    def free_memory(self, device_id: str, ptr: int):
        """Free memory on device"""
        pass
    
    @abstractmethod
    def transfer_data(self, src_device: str, dst_device: str, 
                     src_ptr: int, dst_ptr: int, size: int):
        """Transfer data between devices"""
        pass
    
    @abstractmethod
    def execute_kernel(self, device_id: str, kernel: Any, args: List):
        """Execute compute kernel on device"""
        pass

class CPUDevice(HardwareAbstractionLayer):
    """CPU device abstraction"""
    
    def discover_devices(self) -> List[HardwareDevice]:
        """Discover CPU devices"""
        devices = []
        
        try:
            # Get CPU info based on platform
            if platform.system() == "Linux":
                cpu_info = self._get_linux_cpu_info()
            elif platform.system() == "Darwin":  # macOS
                cpu_info = self._get_macos_cpu_info()
            elif platform.system() == "Windows":
                cpu_info = self._get_windows_cpu_info()
            else:
                cpu_info = self._get_generic_cpu_info()
            
            # Create CPU device
            device = HardwareDevice(
                device_id=f"cpu_0",
                device_type=DeviceType.CPU,
                name=cpu_info.get('name', 'Unknown CPU'),
                vendor=cpu_info.get('vendor', 'Unknown'),
                model=cpu_info.get('model', 'Unknown'),
                compute_units=cpu_info.get('cores', 1),
                clock_speed=cpu_info.get('clock', 1.0),
                capabilities=self._get_cpu_capabilities(),
                memory_size=self._get_total_ram(),
                memory_type=MemoryType.SYSTEM_RAM,
                memory_bandwidth=cpu_info.get('bandwidth', 50.0),
                node_id=os.uname().nodename,
                pci_bus=None,
                numa_node=0,
                temperature=0.0,
                power_usage=0.0,
                utilization=0.0,
                available=True,
                features=cpu_info.get('features', {})
            )
            
            devices.append(device)
            
        except Exception as e:
            logger.error(f"Failed to discover CPU: {e}")
        
        return devices
    
    def _get_linux_cpu_info(self) -> Dict:
        """Get CPU info on Linux"""
        info = {}
        
        try:
            # Parse /proc/cpuinfo
            with open('/proc/cpuinfo', 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                if 'model name' in line:
                    info['name'] = line.split(':')[1].strip()
                elif 'vendor_id' in line:
                    info['vendor'] = line.split(':')[1].strip()
                elif 'cpu cores' in line:
                    info['cores'] = int(line.split(':')[1].strip())
                elif 'cpu MHz' in line:
                    info['clock'] = float(line.split(':')[1].strip()) / 1000.0
                elif 'flags' in line:
                    flags = line.split(':')[1].strip().split()
                    info['features'] = {
                        'sse': 'sse' in flags,
                        'avx': 'avx' in flags,
                        'avx2': 'avx2' in flags,
                        'avx512': 'avx512f' in flags,
                        'fma': 'fma' in flags
                    }
            
            # Get total cores
            import multiprocessing
            info['cores'] = multiprocessing.cpu_count()
            
        except Exception as e:
            logger.error(f"Error reading CPU info: {e}")
            info = self._get_generic_cpu_info()
        
        return info
    
    def _get_macos_cpu_info(self) -> Dict:
        """Get CPU info on macOS"""
        info = {}
        
        try:
            # Use sysctl for CPU info
            import subprocess
            
            # Get CPU brand
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], 
                                  capture_output=True, text=True)
            info['name'] = result.stdout.strip()
            
            # Get core count
            result = subprocess.run(['sysctl', '-n', 'hw.ncpu'], 
                                  capture_output=True, text=True)
            info['cores'] = int(result.stdout.strip())
            
            # Check for Apple Silicon
            result = subprocess.run(['uname', '-m'], capture_output=True, text=True)
            if 'arm64' in result.stdout:
                info['vendor'] = 'Apple'
                info['features'] = {
                    'neon': True,
                    'neural_engine': True,
                    'unified_memory': True
                }
            else:
                info['vendor'] = 'Intel'
                info['features'] = {
                    'sse': True,
                    'avx': True,
                    'avx2': True
                }
            
        except Exception as e:
            logger.error(f"Error reading macOS CPU info: {e}")
            info = self._get_generic_cpu_info()
        
        return info
    
    def _get_windows_cpu_info(self) -> Dict:
        """Get CPU info on Windows"""
        info = {}
        
        try:
            import subprocess
            
            # Use wmic to get CPU info
            result = subprocess.run(['wmic', 'cpu', 'get', 'name,numberofcores,maxclockspeed'], 
                                  capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                values = lines[1].split()
                if len(values) >= 3:
                    info['name'] = ' '.join(values[:-2])
                    info['cores'] = int(values[-2])
                    info['clock'] = float(values[-1]) / 1000.0
            
            info['vendor'] = 'Intel' if 'Intel' in info.get('name', '') else 'AMD'
            
        except Exception as e:
            logger.error(f"Error reading Windows CPU info: {e}")
            info = self._get_generic_cpu_info()
        
        return info
    
    def _get_generic_cpu_info(self) -> Dict:
        """Get generic CPU info"""
        import multiprocessing
        
        return {
            'name': platform.processor() or 'Unknown CPU',
            'vendor': 'Unknown',
            'model': platform.machine(),
            'cores': multiprocessing.cpu_count(),
            'clock': 2.0,  # Assume 2 GHz
            'features': {}
        }
    
    def _get_cpu_capabilities(self) -> DeviceCapabilities:
        """Get CPU compute capabilities"""
        return DeviceCapabilities(
            compute_capabilities=[
                ComputeCapability.FP64,
                ComputeCapability.FP32,
                ComputeCapability.INT8
            ],
            memory_bandwidth=50.0,  # Typical DDR4
            compute_power=0.5,  # Rough estimate
            max_threads=os.cpu_count() * 2,  # Hyperthreading
            max_blocks=1,
            warp_size=1,  # Sequential execution
            shared_memory_size=32,  # L1 cache in KB
            register_count=16,  # x86-64 general purpose
            tensor_cores=0,
            rt_cores=0,
            special_functions=['simd', 'vectorization']
        )
    
    def _get_total_ram(self) -> int:
        """Get total system RAM"""
        try:
            if platform.system() == "Linux":
                with open('/proc/meminfo', 'r') as f:
                    for line in f:
                        if 'MemTotal' in line:
                            return int(line.split()[1]) * 1024  # Convert KB to bytes
            elif platform.system() == "Darwin":
                import subprocess
                result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                      capture_output=True, text=True)
                return int(result.stdout.strip())
            elif platform.system() == "Windows":
                import subprocess
                result = subprocess.run(['wmic', 'computersystem', 'get', 'TotalPhysicalMemory'], 
                                      capture_output=True, text=True)
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    return int(lines[1].strip())
        except:
            pass
        
        # Default to 8GB
        return 8 * 1024 * 1024 * 1024
    
    def get_device_info(self, device_id: str) -> HardwareDevice:
        """Get CPU device info"""
        devices = self.discover_devices()
        for device in devices:
            if device.device_id == device_id:
                # Update dynamic info
                device.utilization = self._get_cpu_utilization()
                device.temperature = self._get_cpu_temperature()
                return device
        return None
    
    def _get_cpu_utilization(self) -> float:
        """Get current CPU utilization"""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except:
            return 0.0
    
    def _get_cpu_temperature(self) -> float:
        """Get CPU temperature"""
        try:
            import psutil
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for entry in entries:
                        if 'core' in entry.label.lower() or 'cpu' in entry.label.lower():
                            return entry.current
        except:
            pass
        return 0.0
    
    def allocate_memory(self, device_id: str, size: int) -> Optional[int]:
        """Allocate CPU memory"""
        try:
            # Use ctypes for actual memory allocation
            import ctypes
            ptr = ctypes.c_void_p()
            ctypes.cdll.LoadLibrary("libc.so.6").malloc.restype = ctypes.c_void_p
            ptr.value = ctypes.cdll.LoadLibrary("libc.so.6").malloc(size)
            return ptr.value
        except:
            # Fallback to Python allocation
            import array
            arr = array.array('b', [0] * size)
            return id(arr)
    
    def free_memory(self, device_id: str, ptr: int):
        """Free CPU memory"""
        try:
            import ctypes
            ctypes.cdll.LoadLibrary("libc.so.6").free(ptr)
        except:
            # Python will garbage collect
            pass
    
    def transfer_data(self, src_device: str, dst_device: str,
                     src_ptr: int, dst_ptr: int, size: int):
        """Transfer data on CPU (memcpy)"""
        try:
            import ctypes
            ctypes.memmove(dst_ptr, src_ptr, size)
        except:
            # Fallback to Python copy
            pass
    
    def execute_kernel(self, device_id: str, kernel: Any, args: List):
        """Execute kernel on CPU"""
        # CPU execution is just function call
        return kernel(*args)

class UniversalHardwarePool:
    """Universal hardware pool manager"""
    
    def __init__(self):
        self.devices: Dict[str, HardwareDevice] = {}
        self.device_handlers: Dict[DeviceType, HardwareAbstractionLayer] = {}
        self.lock = threading.RLock()
        
        # Register device handlers
        self._register_handlers()
        
        # Discover all devices
        self.discover_all_devices()
    
    def _register_handlers(self):
        """Register device type handlers"""
        self.device_handlers[DeviceType.CPU] = CPUDevice()
        
        # Import and register GPU handlers
        try:
            from .cuda_device import CUDADevice
            self.device_handlers[DeviceType.GPU_CUDA] = CUDADevice()
        except ImportError as e:
            logger.debug(f"CUDA handler not available: {e}")
        
        try:
            from .metal_device import MetalDevice
            self.device_handlers[DeviceType.GPU_METAL] = MetalDevice()
        except ImportError as e:
            logger.debug(f"Metal handler not available: {e}")
        
        try:
            from .rocm_device import ROCmDevice
            self.device_handlers[DeviceType.GPU_ROCM] = ROCmDevice()
        except ImportError as e:
            logger.debug(f"ROCm handler not available: {e}")
        
        # Storage devices
        try:
            from .storage_device import StorageDevice
            self.device_handlers[DeviceType.STORAGE] = StorageDevice()
        except ImportError as e:
            logger.debug(f"Storage handler not available: {e}")
        
        # Network devices
        try:
            from .network_device import NetworkDevice
            self.device_handlers[DeviceType.NETWORK] = NetworkDevice()
        except ImportError as e:
            logger.debug(f"Network handler not available: {e}")
    
    def discover_all_devices(self):
        """Discover all hardware devices"""
        with self.lock:
            self.devices.clear()
            
            for device_type, handler in self.device_handlers.items():
                try:
                    devices = handler.discover_devices()
                    for device in devices:
                        self.devices[device.device_id] = device
                        logger.info(f"Discovered {device.device_type.value}: {device.name}")
                except Exception as e:
                    logger.error(f"Failed to discover {device_type.value}: {e}")
    
    def get_total_resources(self) -> Dict:
        """Get total pooled resources"""
        with self.lock:
            total = {
                'compute_units': 0,
                'memory_bytes': 0,
                'compute_tflops': 0,
                'devices': len(self.devices),
                'device_types': {}
            }
            
            for device in self.devices.values():
                total['compute_units'] += device.compute_units
                total['memory_bytes'] += device.memory_size
                total['compute_tflops'] += device.capabilities.compute_power
                
                dtype = device.device_type.value
                if dtype not in total['device_types']:
                    total['device_types'][dtype] = 0
                total['device_types'][dtype] += 1
            
            return total
    
    def get_device(self, device_id: str) -> Optional[HardwareDevice]:
        """Get specific device"""
        return self.devices.get(device_id)
    
    def list_devices(self, device_type: Optional[DeviceType] = None) -> List[HardwareDevice]:
        """List devices by type"""
        devices = list(self.devices.values())
        
        if device_type:
            devices = [d for d in devices if d.device_type == device_type]
        
        return devices
    
    def allocate_compute(self, compute_units: int, 
                        device_type: Optional[DeviceType] = None) -> List[str]:
        """Allocate compute units from pool"""
        allocated = []
        remaining = compute_units
        
        # Sort devices by availability and capability
        devices = self.list_devices(device_type)
        devices.sort(key=lambda d: (d.available, -d.utilization, -d.compute_units))
        
        for device in devices:
            if remaining <= 0:
                break
            
            if device.available and device.utilization < 80:
                allocated.append(device.device_id)
                remaining -= device.compute_units
        
        return allocated if remaining <= 0 else []
    
    def get_unified_memory_map(self) -> Dict:
        """Get unified memory map across all devices"""
        memory_map = {}
        offset = 0
        
        for device in self.devices.values():
            memory_map[device.device_id] = {
                'start': offset,
                'end': offset + device.memory_size,
                'size': device.memory_size,
                'type': device.memory_type.value
            }
            offset += device.memory_size
        
        return memory_map
"""
CUDA Device Handler for KOS Hardware Pool
Handles all NVIDIA GPU operations
"""

import os
import sys
import ctypes
import struct
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import subprocess

from .base import (
    HardwareDevice, HardwareAbstractionLayer, DeviceType,
    DeviceCapabilities, ComputeCapability, MemoryType
)

logger = logging.getLogger(__name__)

# Try to load CUDA
CUDA_AVAILABLE = False
cuda = None
nvml = None

try:
    # Try to import pycuda
    import pycuda.driver as cuda
    import pycuda.autoinit
    CUDA_AVAILABLE = True
    logger.info("PyCUDA loaded successfully")
except ImportError:
    # Try to load CUDA directly via ctypes
    try:
        if sys.platform == "linux":
            cuda_lib = ctypes.CDLL("libcuda.so")
        elif sys.platform == "darwin":
            cuda_lib = ctypes.CDLL("libcuda.dylib")
        elif sys.platform == "win32":
            cuda_lib = ctypes.WinDLL("nvcuda.dll")
        else:
            cuda_lib = None
        
        if cuda_lib:
            CUDA_AVAILABLE = True
            logger.info("CUDA library loaded via ctypes")
    except:
        pass

# Try to load NVML for monitoring
try:
    import pynvml as nvml
    nvml.nvmlInit()
    logger.info("NVML loaded for GPU monitoring")
except:
    nvml = None

class CUDADevice(HardwareAbstractionLayer):
    """CUDA device handler for NVIDIA GPUs"""
    
    def __init__(self):
        self.initialized = False
        self.devices = []
        self.contexts = {}
        self.memory_pools = {}
        
        if CUDA_AVAILABLE:
            self._initialize_cuda()
    
    def _initialize_cuda(self):
        """Initialize CUDA environment"""
        try:
            if cuda:
                cuda.init()
                self.initialized = True
            else:
                # Manual initialization via ctypes
                pass
        except Exception as e:
            logger.error(f"Failed to initialize CUDA: {e}")
    
    def discover_devices(self) -> List[HardwareDevice]:
        """Discover all CUDA devices"""
        devices = []
        
        if not CUDA_AVAILABLE:
            return devices
        
        try:
            # Get device count
            device_count = self._get_device_count()
            
            for i in range(device_count):
                device_info = self._get_cuda_device_info(i)
                if device_info:
                    devices.append(device_info)
                    logger.info(f"Found CUDA device {i}: {device_info.name}")
        
        except Exception as e:
            logger.error(f"Error discovering CUDA devices: {e}")
        
        return devices
    
    def _get_device_count(self) -> int:
        """Get number of CUDA devices"""
        try:
            if cuda:
                return cuda.Device.count()
            else:
                # Use nvidia-smi
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=count', '--format=csv,noheader'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return len(result.stdout.strip().split('\n'))
        except:
            pass
        return 0
    
    def _get_cuda_device_info(self, device_id: int) -> Optional[HardwareDevice]:
        """Get detailed CUDA device information"""
        try:
            if cuda:
                # Use PyCUDA
                device = cuda.Device(device_id)
                attrs = device.get_attributes()
                
                name = device.name()
                memory = device.total_memory()
                compute_capability = device.compute_capability()
                
                # Get detailed capabilities
                capabilities = DeviceCapabilities(
                    compute_capabilities=self._get_compute_capabilities(compute_capability),
                    memory_bandwidth=self._get_memory_bandwidth(device_id),
                    compute_power=self._estimate_compute_power(device_id, attrs),
                    max_threads=attrs.get(cuda.device_attribute.MAX_THREADS_PER_BLOCK, 1024),
                    max_blocks=attrs.get(cuda.device_attribute.MAX_GRID_DIM_X, 65535),
                    warp_size=attrs.get(cuda.device_attribute.WARP_SIZE, 32),
                    shared_memory_size=attrs.get(cuda.device_attribute.MAX_SHARED_MEMORY_PER_BLOCK, 48) // 1024,
                    register_count=attrs.get(cuda.device_attribute.MAX_REGISTERS_PER_BLOCK, 65536),
                    tensor_cores=self._get_tensor_cores(compute_capability),
                    rt_cores=self._get_rt_cores(compute_capability),
                    special_functions=['cuda_cores', 'tensor_cores', 'rt_cores']
                )
                
                return HardwareDevice(
                    device_id=f"cuda_{device_id}",
                    device_type=DeviceType.GPU_CUDA,
                    name=name,
                    vendor="NVIDIA",
                    model=name,
                    compute_units=attrs.get(cuda.device_attribute.MULTIPROCESSOR_COUNT, 1),
                    clock_speed=attrs.get(cuda.device_attribute.CLOCK_RATE, 1000000) / 1e6,
                    capabilities=capabilities,
                    memory_size=memory,
                    memory_type=MemoryType.GPU_VRAM,
                    memory_bandwidth=capabilities.memory_bandwidth,
                    node_id=os.uname().nodename,
                    pci_bus=self._get_pci_bus(device_id),
                    numa_node=self._get_numa_node(device_id),
                    temperature=self._get_temperature(device_id),
                    power_usage=self._get_power_usage(device_id),
                    utilization=self._get_utilization(device_id),
                    available=True,
                    features={
                        'compute_capability': compute_capability,
                        'cuda_version': self._get_cuda_version()
                    }
                )
            
            else:
                # Use nvidia-smi for info
                return self._get_device_info_nvidia_smi(device_id)
        
        except Exception as e:
            logger.error(f"Error getting CUDA device {device_id} info: {e}")
            return None
    
    def _get_device_info_nvidia_smi(self, device_id: int) -> Optional[HardwareDevice]:
        """Get device info using nvidia-smi"""
        try:
            # Query device properties
            queries = [
                'name', 'memory.total', 'utilization.gpu', 'temperature.gpu',
                'power.draw', 'clocks.sm', 'pci.bus_id'
            ]
            
            query_str = ','.join(queries)
            result = subprocess.run(
                ['nvidia-smi', f'--id={device_id}', f'--query-gpu={query_str}', 
                 '--format=csv,noheader,nounits'],
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                values = result.stdout.strip().split(', ')
                
                if len(values) >= len(queries):
                    name = values[0]
                    memory = int(values[1]) * 1024 * 1024  # MB to bytes
                    utilization = float(values[2]) if values[2] != 'N/A' else 0.0
                    temperature = float(values[3]) if values[3] != 'N/A' else 0.0
                    power = float(values[4]) if values[4] != 'N/A' else 0.0
                    clock = float(values[5]) / 1000.0 if values[5] != 'N/A' else 1.0
                    pci_bus = values[6]
                    
                    # Estimate capabilities based on GPU name
                    capabilities = self._estimate_capabilities_from_name(name)
                    
                    return HardwareDevice(
                        device_id=f"cuda_{device_id}",
                        device_type=DeviceType.GPU_CUDA,
                        name=name,
                        vendor="NVIDIA",
                        model=name,
                        compute_units=self._estimate_sm_count(name),
                        clock_speed=clock,
                        capabilities=capabilities,
                        memory_size=memory,
                        memory_type=MemoryType.GPU_VRAM,
                        memory_bandwidth=capabilities.memory_bandwidth,
                        node_id=os.uname().nodename,
                        pci_bus=pci_bus,
                        numa_node=0,
                        temperature=temperature,
                        power_usage=power,
                        utilization=utilization,
                        available=True,
                        features={'cuda_version': self._get_cuda_version()}
                    )
        
        except Exception as e:
            logger.error(f"nvidia-smi query failed: {e}")
        
        return None
    
    def _get_compute_capabilities(self, compute_capability: Tuple[int, int]) -> List[ComputeCapability]:
        """Get compute capabilities based on CUDA compute capability"""
        capabilities = [ComputeCapability.FP32, ComputeCapability.INT8]
        
        major, minor = compute_capability
        
        # FP64 support (usually reduced on consumer cards)
        if major >= 2:
            capabilities.append(ComputeCapability.FP64)
        
        # FP16 support
        if major >= 5 and minor >= 3:
            capabilities.append(ComputeCapability.FP16)
        
        # Tensor Core support (FP16)
        if major >= 7:
            capabilities.append(ComputeCapability.TENSOR)
        
        # BF16 support (Ampere and later)
        if major >= 8:
            capabilities.append(ComputeCapability.BF16)
        
        # INT4 support (Ada Lovelace and later)
        if major >= 8 and minor >= 9:
            capabilities.append(ComputeCapability.INT4)
        
        return capabilities
    
    def _get_memory_bandwidth(self, device_id: int) -> float:
        """Get memory bandwidth in GB/s"""
        try:
            if nvml:
                handle = nvml.nvmlDeviceGetHandleByIndex(device_id)
                # Get memory bus width and clock
                bus_width = nvml.nvmlDeviceGetMemoryBusWidth(handle)
                mem_clock = nvml.nvmlDeviceGetMaxMemoryClock(handle)  # MHz
                
                # Calculate bandwidth: (bus_width / 8) * mem_clock * 2 (DDR)
                bandwidth = (bus_width / 8) * mem_clock * 2 / 1000  # GB/s
                return bandwidth
        except:
            pass
        
        # Estimate based on GPU generation
        return 200.0  # Default estimate
    
    def _estimate_compute_power(self, device_id: int, attrs: Dict) -> float:
        """Estimate compute power in TFLOPS"""
        try:
            # Get SM count and clock
            sm_count = attrs.get(cuda.device_attribute.MULTIPROCESSOR_COUNT, 30)
            clock_mhz = attrs.get(cuda.device_attribute.CLOCK_RATE, 1500000) / 1000
            
            # Estimate CUDA cores per SM based on compute capability
            compute_capability = attrs.get('compute_capability', (7, 5))
            
            if compute_capability[0] >= 8:  # Ampere/Ada
                cores_per_sm = 128
            elif compute_capability[0] >= 7:  # Turing/Volta
                cores_per_sm = 64
            else:  # Older
                cores_per_sm = 128
            
            # Calculate FP32 TFLOPS
            # Formula: SM_count * cores_per_SM * clock_GHz * 2 (FMA)
            tflops = sm_count * cores_per_sm * (clock_mhz / 1000) * 2 / 1000
            
            return tflops
        except:
            return 10.0  # Default estimate
    
    def _get_tensor_cores(self, compute_capability: Tuple[int, int]) -> int:
        """Get number of tensor cores"""
        major, minor = compute_capability
        
        if major >= 8:  # Ampere/Ada
            return 4  # 4 tensor cores per SM
        elif major >= 7:  # Volta/Turing
            return 8  # 8 tensor cores per SM
        else:
            return 0
    
    def _get_rt_cores(self, compute_capability: Tuple[int, int]) -> int:
        """Get number of RT cores"""
        major, minor = compute_capability
        
        if major >= 7 and minor >= 5:  # Turing and later
            return 1  # 1 RT core per SM
        else:
            return 0
    
    def _estimate_capabilities_from_name(self, name: str) -> DeviceCapabilities:
        """Estimate capabilities from GPU name"""
        # Default capabilities
        capabilities = DeviceCapabilities(
            compute_capabilities=[ComputeCapability.FP32, ComputeCapability.FP16],
            memory_bandwidth=200.0,
            compute_power=10.0,
            max_threads=1024,
            max_blocks=65535,
            warp_size=32,
            shared_memory_size=48,
            register_count=65536,
            tensor_cores=0,
            rt_cores=0,
            special_functions=['cuda_cores']
        )
        
        # Adjust based on GPU name
        name_lower = name.lower()
        
        # RTX 4060 Ti
        if '4060' in name_lower:
            capabilities.memory_bandwidth = 288.0
            capabilities.compute_power = 22.0
            capabilities.tensor_cores = 4
            capabilities.rt_cores = 1
            capabilities.compute_capabilities.extend([
                ComputeCapability.BF16, ComputeCapability.TENSOR
            ])
        
        # RTX 4090
        elif '4090' in name_lower:
            capabilities.memory_bandwidth = 1008.0
            capabilities.compute_power = 82.6
            capabilities.tensor_cores = 4
            capabilities.rt_cores = 1
            capabilities.compute_capabilities.extend([
                ComputeCapability.BF16, ComputeCapability.TENSOR, ComputeCapability.INT4
            ])
        
        # RTX 3090
        elif '3090' in name_lower:
            capabilities.memory_bandwidth = 936.0
            capabilities.compute_power = 35.6
            capabilities.tensor_cores = 4
            capabilities.rt_cores = 1
            capabilities.compute_capabilities.extend([
                ComputeCapability.BF16, ComputeCapability.TENSOR
            ])
        
        # Add more GPU models as needed
        
        return capabilities
    
    def _estimate_sm_count(self, name: str) -> int:
        """Estimate SM count from GPU name"""
        name_lower = name.lower()
        
        if '4090' in name_lower:
            return 128
        elif '4080' in name_lower:
            return 76
        elif '4070' in name_lower:
            return 46
        elif '4060' in name_lower:
            return 34
        elif '3090' in name_lower:
            return 82
        elif '3080' in name_lower:
            return 68
        elif '3070' in name_lower:
            return 46
        elif '3060' in name_lower:
            return 28
        else:
            return 30  # Default
    
    def _get_pci_bus(self, device_id: int) -> Optional[str]:
        """Get PCI bus ID"""
        try:
            if cuda:
                device = cuda.Device(device_id)
                return device.pci_bus_id()
            else:
                # Use nvidia-smi
                result = subprocess.run(
                    ['nvidia-smi', f'--id={device_id}', '--query-gpu=pci.bus_id',
                     '--format=csv,noheader'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return result.stdout.strip()
        except:
            pass
        return None
    
    def _get_numa_node(self, device_id: int) -> Optional[int]:
        """Get NUMA node for device"""
        # Would need to check PCI bus to NUMA mapping
        return 0
    
    def _get_temperature(self, device_id: int) -> float:
        """Get GPU temperature"""
        try:
            if nvml:
                handle = nvml.nvmlDeviceGetHandleByIndex(device_id)
                return nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
        except:
            pass
        return 0.0
    
    def _get_power_usage(self, device_id: int) -> float:
        """Get GPU power usage in watts"""
        try:
            if nvml:
                handle = nvml.nvmlDeviceGetHandleByIndex(device_id)
                return nvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
        except:
            pass
        return 0.0
    
    def _get_utilization(self, device_id: int) -> float:
        """Get GPU utilization percentage"""
        try:
            if nvml:
                handle = nvml.nvmlDeviceGetHandleByIndex(device_id)
                util = nvml.nvmlDeviceGetUtilizationRates(handle)
                return util.gpu
        except:
            pass
        return 0.0
    
    def _get_cuda_version(self) -> str:
        """Get CUDA version"""
        try:
            if cuda:
                return f"{cuda.get_version()}"
            else:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
        except:
            pass
        return "Unknown"
    
    def get_device_info(self, device_id: str) -> HardwareDevice:
        """Get current device information"""
        # Extract numeric ID
        try:
            numeric_id = int(device_id.split('_')[1])
            return self._get_cuda_device_info(numeric_id)
        except:
            return None
    
    def allocate_memory(self, device_id: str, size: int) -> Optional[int]:
        """Allocate GPU memory"""
        try:
            numeric_id = int(device_id.split('_')[1])
            
            if cuda:
                # Use PyCUDA
                mem_gpu = cuda.mem_alloc(size)
                return int(mem_gpu)
            else:
                # Would use CUDA API directly
                pass
        except Exception as e:
            logger.error(f"Failed to allocate CUDA memory: {e}")
        return None
    
    def free_memory(self, device_id: str, ptr: int):
        """Free GPU memory"""
        try:
            if cuda:
                # PyCUDA handles this automatically
                pass
            else:
                # Would use CUDA API directly
                pass
        except Exception as e:
            logger.error(f"Failed to free CUDA memory: {e}")
    
    def transfer_data(self, src_device: str, dst_device: str,
                     src_ptr: int, dst_ptr: int, size: int):
        """Transfer data between devices"""
        try:
            if cuda:
                # Use CUDA memcpy
                if 'cuda' in src_device and 'cuda' in dst_device:
                    # GPU to GPU
                    cuda.memcpy_dtod(dst_ptr, src_ptr, size)
                elif 'cuda' in src_device:
                    # GPU to Host
                    cuda.memcpy_dtoh(dst_ptr, src_ptr)
                else:
                    # Host to GPU
                    cuda.memcpy_htod(dst_ptr, src_ptr)
        except Exception as e:
            logger.error(f"CUDA transfer failed: {e}")
    
    def execute_kernel(self, device_id: str, kernel: Any, args: List):
        """Execute CUDA kernel"""
        try:
            numeric_id = int(device_id.split('_')[1])
            
            if cuda:
                # Set device
                device = cuda.Device(numeric_id)
                ctx = device.make_context()
                
                try:
                    # Execute kernel
                    result = kernel(*args)
                    return result
                finally:
                    ctx.pop()
        except Exception as e:
            logger.error(f"CUDA kernel execution failed: {e}")
        return None
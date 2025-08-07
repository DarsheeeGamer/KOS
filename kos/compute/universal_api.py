"""
Universal Compute API for KOS Hardware Pool
Provides unified interface for executing kernels across all device types
"""

import os
import sys
import json
import logging
import threading
from enum import Enum
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from ..hardware.base import UniversalHardwarePool, DeviceType, HardwareDevice

logger = logging.getLogger(__name__)

class KernelType(Enum):
    """Supported kernel types"""
    CUDA_C = "cuda_c"
    HIP_C = "hip_c"  
    METAL_SHADER = "metal_shader"
    OPENCL = "opencl"
    CPU_FUNCTION = "cpu_function"
    PYTHON_FUNCTION = "python_function"
    UNIVERSAL = "universal"  # KOS universal kernel language

class ExecutionMode(Enum):
    """Kernel execution modes"""
    SYNCHRONOUS = "sync"
    ASYNCHRONOUS = "async"
    STREAM = "stream"
    PARALLEL = "parallel"

class MemoryLocation(Enum):
    """Memory location types"""
    HOST = "host"
    DEVICE = "device"
    UNIFIED = "unified"
    DISTRIBUTED = "distributed"

@dataclass
class KernelDefinition:
    """Universal kernel definition"""
    name: str
    kernel_type: KernelType
    source_code: str
    entry_point: str
    parameters: List[Dict[str, Any]]
    local_work_size: tuple
    global_work_size: tuple
    shared_memory_size: int = 0
    compile_flags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)

@dataclass 
class ComputeBuffer:
    """Universal compute buffer"""
    buffer_id: str
    size: int
    device_id: str
    location: MemoryLocation
    ptr: Optional[int] = None
    data_type: str = "float32"
    shape: Optional[tuple] = None
    synchronized: bool = True

@dataclass
class ExecutionContext:
    """Execution context for kernel launches"""
    devices: List[str]
    mode: ExecutionMode
    priority: int = 0
    timeout: float = 30.0
    memory_limit: Optional[int] = None
    compute_limit: Optional[int] = None

class UniversalKernel:
    """Universal kernel that can execute on any device"""
    
    def __init__(self, definition: KernelDefinition):
        self.definition = definition
        self.compiled_kernels: Dict[str, Any] = {}
        self.device_specific_source: Dict[str, str] = {}
        self.execution_history: List[Dict] = []
    
    def compile_for_device(self, device_id: str, hardware_pool: 'UniversalHardwarePool') -> bool:
        """Compile kernel for specific device"""
        try:
            device = hardware_pool.get_device(device_id)
            if not device:
                return False
            
            # Get device handler
            handler = hardware_pool.device_handlers.get(device.device_type)
            if not handler:
                return False
            
            # Translate kernel to device-specific format
            translated_source = self._translate_kernel(device.device_type)
            if not translated_source:
                return False
            
            # Compile using device handler
            if hasattr(handler, 'compile_kernel'):
                compiled = handler.compile_kernel(translated_source)
                if compiled:
                    self.compiled_kernels[device_id] = compiled
                    self.device_specific_source[device_id] = translated_source
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Kernel compilation failed for {device_id}: {e}")
            return False
    
    def _translate_kernel(self, device_type: DeviceType) -> Optional[str]:
        """Translate kernel to device-specific language"""
        if self.definition.kernel_type == KernelType.UNIVERSAL:
            # Translate universal kernel to device-specific
            return self._translate_universal_kernel(device_type)
        elif self.definition.kernel_type == KernelType.PYTHON_FUNCTION:
            # Python functions can run on CPU
            if device_type == DeviceType.CPU:
                return self.definition.source_code
        elif self.definition.kernel_type == KernelType.CUDA_C:
            if device_type == DeviceType.GPU_CUDA:
                return self.definition.source_code
            elif device_type == DeviceType.GPU_ROCM:
                # Convert CUDA to HIP
                return self._cuda_to_hip(self.definition.source_code)
        elif self.definition.kernel_type == KernelType.HIP_C:
            if device_type == DeviceType.GPU_ROCM:
                return self.definition.source_code
            elif device_type == DeviceType.GPU_CUDA:
                # Convert HIP to CUDA
                return self._hip_to_cuda(self.definition.source_code)
        elif self.definition.kernel_type == KernelType.METAL_SHADER:
            if device_type == DeviceType.GPU_METAL:
                return self.definition.source_code
        
        return None
    
    def _translate_universal_kernel(self, device_type: DeviceType) -> str:
        """Translate universal kernel language to device-specific"""
        # This is a simplified example - real implementation would be much more complex
        source = self.definition.source_code
        
        if device_type == DeviceType.GPU_CUDA:
            # Translate to CUDA C
            cuda_source = source.replace("universal_thread_id()", "blockIdx.x * blockDim.x + threadIdx.x")
            cuda_source = cuda_source.replace("universal_barrier()", "__syncthreads()")
            return f"__global__ void {self.definition.entry_point}() {{\n{cuda_source}\n}}"
        
        elif device_type == DeviceType.GPU_ROCM:
            # Translate to HIP
            hip_source = source.replace("universal_thread_id()", "hipBlockIdx_x * hipBlockDim_x + hipThreadIdx_x")
            hip_source = hip_source.replace("universal_barrier()", "__syncthreads()")
            return f"__global__ void {self.definition.entry_point}() {{\n{hip_source}\n}}"
        
        elif device_type == DeviceType.GPU_METAL:
            # Translate to Metal
            metal_source = source.replace("universal_thread_id()", "thread_position_in_grid")
            metal_source = metal_source.replace("universal_barrier()", "threadgroup_barrier()")
            return f"kernel void {self.definition.entry_point}() {{\n{metal_source}\n}}"
        
        elif device_type == DeviceType.CPU:
            # Translate to CPU function
            return f"def {self.definition.entry_point}():\n    {source}"
        
        return source
    
    def _cuda_to_hip(self, cuda_source: str) -> str:
        """Convert CUDA source to HIP"""
        hip_source = cuda_source
        
        # Basic CUDA to HIP conversions
        replacements = {
            'cudaMalloc': 'hipMalloc',
            'cudaFree': 'hipFree',
            'cudaMemcpy': 'hipMemcpy',
            'cudaDeviceSynchronize': 'hipDeviceSynchronize',
            'blockIdx': 'hipBlockIdx',
            'blockDim': 'hipBlockDim',
            'threadIdx': 'hipThreadIdx',
            'gridDim': 'hipGridDim',
            '__syncthreads': '__syncthreads',
            'cudaError_t': 'hipError_t',
            'cudaSuccess': 'hipSuccess'
        }
        
        for cuda_term, hip_term in replacements.items():
            hip_source = hip_source.replace(cuda_term, hip_term)
        
        return hip_source
    
    def _hip_to_cuda(self, hip_source: str) -> str:
        """Convert HIP source to CUDA"""
        cuda_source = hip_source
        
        # Basic HIP to CUDA conversions (reverse of above)
        replacements = {
            'hipMalloc': 'cudaMalloc',
            'hipFree': 'cudaFree',
            'hipMemcpy': 'cudaMemcpy',
            'hipDeviceSynchronize': 'cudaDeviceSynchronize',
            'hipBlockIdx': 'blockIdx',
            'hipBlockDim': 'blockDim',
            'hipThreadIdx': 'threadIdx',
            'hipGridDim': 'gridDim',
            'hipError_t': 'cudaError_t',
            'hipSuccess': 'cudaSuccess'
        }
        
        for hip_term, cuda_term in replacements.items():
            cuda_source = cuda_source.replace(hip_term, cuda_term)
        
        return cuda_source

class UniversalComputeAPI:
    """Universal compute API for hardware pool"""
    
    def __init__(self, hardware_pool: UniversalHardwarePool):
        self.hardware_pool = hardware_pool
        self.kernels: Dict[str, UniversalKernel] = {}
        self.buffers: Dict[str, ComputeBuffer] = {}
        self.execution_queue = []
        self.lock = threading.RLock()
        
        # Initialize device-specific APIs
        self._initialize_device_apis()
    
    def _initialize_device_apis(self):
        """Initialize device-specific compute APIs"""
        # This would initialize CUDA context, Metal device, etc.
        logger.info("Initializing universal compute API")
    
    def register_kernel(self, kernel_def: KernelDefinition) -> bool:
        """Register a new kernel"""
        try:
            with self.lock:
                kernel = UniversalKernel(kernel_def)
                self.kernels[kernel_def.name] = kernel
                logger.info(f"Registered kernel: {kernel_def.name}")
                return True
        except Exception as e:
            logger.error(f"Failed to register kernel {kernel_def.name}: {e}")
            return False
    
    def allocate_buffer(self, name: str, size: int, device_id: Optional[str] = None, 
                       data_type: str = "float32", shape: Optional[tuple] = None) -> Optional[str]:
        """Allocate compute buffer"""
        try:
            with self.lock:
                # Auto-select device if not specified
                if not device_id:
                    available_devices = [d for d in self.hardware_pool.devices.values() if d.available]
                    if not available_devices:
                        return None
                    device_id = available_devices[0].device_id
                
                # Get device handler
                device = self.hardware_pool.get_device(device_id)
                if not device:
                    return None
                
                handler = self.hardware_pool.device_handlers.get(device.device_type)
                if not handler:
                    return None
                
                # Allocate memory on device
                ptr = handler.allocate_memory(device_id, size)
                if ptr is None:
                    return None
                
                # Create buffer record
                buffer_id = f"buffer_{len(self.buffers)}"
                buffer = ComputeBuffer(
                    buffer_id=buffer_id,
                    size=size,
                    device_id=device_id,
                    location=MemoryLocation.DEVICE,
                    ptr=ptr,
                    data_type=data_type,
                    shape=shape
                )
                
                self.buffers[buffer_id] = buffer
                logger.info(f"Allocated buffer {buffer_id} on {device_id}: {size} bytes")
                return buffer_id
        
        except Exception as e:
            logger.error(f"Buffer allocation failed: {e}")
            return None
    
    def free_buffer(self, buffer_id: str) -> bool:
        """Free compute buffer"""
        try:
            with self.lock:
                if buffer_id not in self.buffers:
                    return False
                
                buffer = self.buffers[buffer_id]
                device = self.hardware_pool.get_device(buffer.device_id)
                if not device:
                    return False
                
                handler = self.hardware_pool.device_handlers.get(device.device_type)
                if handler and buffer.ptr:
                    handler.free_memory(buffer.device_id, buffer.ptr)
                
                del self.buffers[buffer_id]
                logger.info(f"Freed buffer {buffer_id}")
                return True
        
        except Exception as e:
            logger.error(f"Failed to free buffer {buffer_id}: {e}")
            return False
    
    def execute_kernel(self, kernel_name: str, context: ExecutionContext, 
                      args: List[Any], buffers: Optional[List[str]] = None) -> bool:
        """Execute kernel on specified devices"""
        try:
            with self.lock:
                if kernel_name not in self.kernels:
                    logger.error(f"Kernel {kernel_name} not found")
                    return False
                
                kernel = self.kernels[kernel_name]
                
                # Compile kernel for target devices if not already compiled
                for device_id in context.devices:
                    if device_id not in kernel.compiled_kernels:
                        if not kernel.compile_for_device(device_id, self.hardware_pool):
                            logger.warning(f"Failed to compile kernel for {device_id}")
                            continue
                
                # Execute on each device
                results = []
                for device_id in context.devices:
                    if device_id in kernel.compiled_kernels:
                        result = self._execute_on_device(kernel, device_id, args, buffers)
                        results.append(result)
                
                # Record execution
                execution_record = {
                    'kernel_name': kernel_name,
                    'devices': context.devices,
                    'mode': context.mode.value,
                    'success': all(results),
                    'timestamp': time.time()
                }
                kernel.execution_history.append(execution_record)
                
                return all(results)
        
        except Exception as e:
            logger.error(f"Kernel execution failed: {e}")
            return False
    
    def _execute_on_device(self, kernel: UniversalKernel, device_id: str, 
                          args: List[Any], buffers: Optional[List[str]] = None) -> bool:
        """Execute kernel on specific device"""
        try:
            device = self.hardware_pool.get_device(device_id)
            if not device:
                return False
            
            handler = self.hardware_pool.device_handlers.get(device.device_type)
            if not handler:
                return False
            
            compiled_kernel = kernel.compiled_kernels.get(device_id)
            if not compiled_kernel:
                return False
            
            # Execute kernel using device handler
            result = handler.execute_kernel(device_id, compiled_kernel, args)
            return result is not None
        
        except Exception as e:
            logger.error(f"Device execution failed for {device_id}: {e}")
            return False
    
    def transfer_buffer(self, buffer_id: str, src_device: str, dst_device: str) -> bool:
        """Transfer buffer between devices"""
        try:
            with self.lock:
                if buffer_id not in self.buffers:
                    return False
                
                buffer = self.buffers[buffer_id]
                
                # Get handlers
                src_device_obj = self.hardware_pool.get_device(src_device)
                dst_device_obj = self.hardware_pool.get_device(dst_device)
                
                if not src_device_obj or not dst_device_obj:
                    return False
                
                src_handler = self.hardware_pool.device_handlers.get(src_device_obj.device_type)
                dst_handler = self.hardware_pool.device_handlers.get(dst_device_obj.device_type)
                
                if not src_handler or not dst_handler:
                    return False
                
                # Allocate destination buffer
                dst_ptr = dst_handler.allocate_memory(dst_device, buffer.size)
                if dst_ptr is None:
                    return False
                
                # Transfer data
                if hasattr(src_handler, 'transfer_data'):
                    src_handler.transfer_data(src_device, dst_device, 
                                            buffer.ptr, dst_ptr, buffer.size)
                
                # Free old buffer and update
                if buffer.ptr:
                    src_handler.free_memory(src_device, buffer.ptr)
                
                buffer.device_id = dst_device
                buffer.ptr = dst_ptr
                
                logger.info(f"Transferred buffer {buffer_id} from {src_device} to {dst_device}")
                return True
        
        except Exception as e:
            logger.error(f"Buffer transfer failed: {e}")
            return False
    
    def get_optimal_devices(self, kernel_name: str, data_size: int) -> List[str]:
        """Get optimal devices for kernel execution"""
        if kernel_name not in self.kernels:
            return []
        
        kernel = self.kernels[kernel_name]
        available_devices = [d for d in self.hardware_pool.devices.values() if d.available]
        
        # Score devices based on capabilities
        device_scores = []
        for device in available_devices:
            score = self._calculate_device_score(device, kernel, data_size)
            device_scores.append((device.device_id, score))
        
        # Sort by score (higher is better)
        device_scores.sort(key=lambda x: x[1], reverse=True)
        
        return [device_id for device_id, score in device_scores[:3]]  # Top 3
    
    def _calculate_device_score(self, device: HardwareDevice, kernel: UniversalKernel, data_size: int) -> float:
        """Calculate device suitability score for kernel"""
        score = 0.0
        
        # Compute power
        score += device.capabilities.compute_power * 10
        
        # Memory bandwidth
        score += device.capabilities.memory_bandwidth / 100
        
        # Available memory
        if device.memory_size > data_size * 2:
            score += 50
        
        # Device utilization (lower is better)
        score += (100 - device.utilization) / 10
        
        # Device type preference (GPU > CPU for compute)
        if device.device_type in [DeviceType.GPU_CUDA, DeviceType.GPU_ROCM, DeviceType.GPU_METAL]:
            score += 100
        elif device.device_type == DeviceType.CPU:
            score += 20
        
        return score
    
    def get_device_utilization(self) -> Dict[str, float]:
        """Get utilization across all devices"""
        utilization = {}
        for device_id, device in self.hardware_pool.devices.items():
            utilization[device_id] = device.utilization
        return utilization
    
    def get_memory_usage(self) -> Dict[str, Dict]:
        """Get memory usage per device"""
        memory_usage = {}
        for device_id, device in self.hardware_pool.devices.items():
            allocated = sum(b.size for b in self.buffers.values() if b.device_id == device_id)
            memory_usage[device_id] = {
                'total': device.memory_size,
                'allocated': allocated,
                'free': device.memory_size - allocated,
                'utilization': (allocated / device.memory_size) * 100
            }
        return memory_usage
    
    def shutdown(self):
        """Shutdown compute API and cleanup"""
        with self.lock:
            # Free all buffers
            for buffer_id in list(self.buffers.keys()):
                self.free_buffer(buffer_id)
            
            # Clear kernels
            self.kernels.clear()
            
            logger.info("Universal compute API shutdown complete")

import time
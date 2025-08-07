"""
Distributed GPU Kernel Execution for KOS Hardware Pool
Real kernel execution across multiple machines with different GPU types
"""

import os
import sys
import time
import threading
import queue
import hashlib
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import pickle

# GPU libraries (conditional imports)
try:
    import cupy as cp  # CUDA
    CUDA_AVAILABLE = True
except ImportError:
    CUDA_AVAILABLE = False
    cp = None

try:
    import pyopencl as cl  # OpenCL for cross-platform
    OPENCL_AVAILABLE = True
except ImportError:
    OPENCL_AVAILABLE = False
    cl = None

from .cluster_communication import KOSClusterManager, NetworkMessage, MessageType
from .distributed_memory import DistributedMemoryCoherency

logger = logging.getLogger(__name__)

class KernelStatus(Enum):
    """Kernel execution status"""
    PENDING = "pending"
    COMPILING = "compiling"
    READY = "ready"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class DistributedKernel:
    """Kernel that can execute across distributed GPUs"""
    kernel_id: str
    name: str
    source_code: str
    language: str  # "cuda", "hip", "metal", "opencl"
    entry_point: str
    compiled_binaries: Dict[str, bytes] = field(default_factory=dict)  # node_id -> binary
    status: KernelStatus = KernelStatus.PENDING
    execution_count: int = 0
    total_execution_time: float = 0.0

@dataclass
class KernelTask:
    """Task for kernel execution"""
    task_id: str
    kernel_id: str
    target_devices: List[Tuple[str, str]]  # [(node_id, device_id), ...]
    input_data: Dict[str, Any]
    output_addresses: Dict[str, int]
    grid_size: Tuple[int, int, int]
    block_size: Tuple[int, int, int]
    shared_memory_size: int
    status: KernelStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None

class DistributedGPUExecutor:
    """Executes GPU kernels across distributed hardware"""
    
    def __init__(self, cluster_manager: KOSClusterManager, 
                 memory_coherency: DistributedMemoryCoherency):
        self.cluster = cluster_manager
        self.memory = memory_coherency
        self.node_id = cluster_manager.node_id
        
        # Kernel registry
        self.kernels: Dict[str, DistributedKernel] = {}
        self.kernel_tasks: Dict[str, KernelTask] = {}
        
        # Execution queues
        self.local_queue = queue.Queue()
        self.remote_queue = queue.Queue()
        
        # GPU contexts (per device)
        self.gpu_contexts: Dict[str, Any] = {}
        
        # Compiled kernel cache
        self.compiled_cache: Dict[Tuple[str, str], Any] = {}  # (kernel_id, device_id) -> compiled
        
        # Statistics
        self.stats = {
            'kernels_registered': 0,
            'kernels_compiled': 0,
            'kernels_executed': 0,
            'remote_executions': 0,
            'compilation_time': 0.0,
            'execution_time': 0.0,
            'data_transfer_time': 0.0,
            'failures': 0
        }
        
        # Initialize GPU contexts
        self._initialize_gpu_contexts()
        
        # Start execution workers
        self._start_execution_workers()
        
        logger.info(f"Distributed GPU executor initialized on node {self.node_id}")
    
    def _initialize_gpu_contexts(self):
        """Initialize GPU contexts for local devices"""
        
        try:
            # Get local GPU devices
            local_devices = self._get_local_gpu_devices()
            
            for device_id, device_info in local_devices.items():
                device_type = device_info['type']
                
                if 'cuda' in device_type and CUDA_AVAILABLE:
                    # Initialize CUDA context
                    self._initialize_cuda_context(device_id, device_info)
                    
                elif 'rocm' in device_type:
                    # Initialize ROCm/HIP context
                    self._initialize_rocm_context(device_id, device_info)
                    
                elif 'metal' in device_type:
                    # Initialize Metal context
                    self._initialize_metal_context(device_id, device_info)
                    
                elif OPENCL_AVAILABLE:
                    # Try OpenCL as fallback
                    self._initialize_opencl_context(device_id, device_info)
                    
        except Exception as e:
            logger.error(f"Failed to initialize GPU contexts: {e}")
    
    def _initialize_cuda_context(self, device_id: str, device_info: Dict):
        """Initialize CUDA context for NVIDIA GPU"""
        
        if not CUDA_AVAILABLE:
            return
        
        try:
            import pycuda.driver as cuda
            import pycuda.autoinit
            from pycuda.compiler import SourceModule
            
            # Get device index
            device_index = int(device_id.split('_')[-1])
            
            # Create context
            cuda.init()
            device = cuda.Device(device_index)
            context = device.make_context()
            
            self.gpu_contexts[device_id] = {
                'type': 'cuda',
                'device': device,
                'context': context,
                'compiler': SourceModule
            }
            
            logger.info(f"Initialized CUDA context for device {device_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize CUDA context for {device_id}: {e}")
    
    def _initialize_opencl_context(self, device_id: str, device_info: Dict):
        """Initialize OpenCL context for cross-platform GPU"""
        
        if not OPENCL_AVAILABLE:
            return
        
        try:
            # Find OpenCL platform and device
            platforms = cl.get_platforms()
            
            for platform in platforms:
                devices = platform.get_devices(device_type=cl.device_type.GPU)
                
                for idx, device in enumerate(devices):
                    if device.name in device_info.get('name', ''):
                        # Create context
                        context = cl.Context([device])
                        queue = cl.CommandQueue(context)
                        
                        self.gpu_contexts[device_id] = {
                            'type': 'opencl',
                            'platform': platform,
                            'device': device,
                            'context': context,
                            'queue': queue
                        }
                        
                        logger.info(f"Initialized OpenCL context for device {device_id}")
                        return
                        
        except Exception as e:
            logger.error(f"Failed to initialize OpenCL context for {device_id}: {e}")
    
    def _initialize_rocm_context(self, device_id: str, device_info: Dict):
        """Initialize ROCm/HIP context for AMD GPU"""
        
        try:
            # ROCm/HIP initialization would go here
            # This requires hippy or similar HIP Python bindings
            pass
            
        except Exception as e:
            logger.error(f"Failed to initialize ROCm context for {device_id}: {e}")
    
    def _initialize_metal_context(self, device_id: str, device_info: Dict):
        """Initialize Metal context for Apple Silicon"""
        
        try:
            # Metal initialization would go here
            # This requires PyObjC and Metal bindings
            pass
            
        except Exception as e:
            logger.error(f"Failed to initialize Metal context for {device_id}: {e}")
    
    def register_kernel(self, name: str, source_code: str, language: str,
                       entry_point: str) -> str:
        """Register a kernel for distributed execution"""
        
        try:
            kernel_id = self._generate_kernel_id(name, source_code)
            
            kernel = DistributedKernel(
                kernel_id=kernel_id,
                name=name,
                source_code=source_code,
                language=language,
                entry_point=entry_point,
                status=KernelStatus.PENDING
            )
            
            self.kernels[kernel_id] = kernel
            self.stats['kernels_registered'] += 1
            
            # Compile for local devices
            self._compile_kernel_local(kernel)
            
            # Distribute to other nodes
            self._distribute_kernel(kernel)
            
            logger.info(f"Registered kernel {name} with ID {kernel_id}")
            return kernel_id
            
        except Exception as e:
            logger.error(f"Failed to register kernel {name}: {e}")
            return ""
    
    def _compile_kernel_local(self, kernel: DistributedKernel):
        """Compile kernel for local GPU devices"""
        
        start_time = time.time()
        kernel.status = KernelStatus.COMPILING
        
        for device_id, context_info in self.gpu_contexts.items():
            try:
                compiled = None
                
                if context_info['type'] == 'cuda' and kernel.language == 'cuda':
                    compiled = self._compile_cuda_kernel(kernel, context_info)
                    
                elif context_info['type'] == 'opencl':
                    compiled = self._compile_opencl_kernel(kernel, context_info)
                
                if compiled:
                    self.compiled_cache[(kernel.kernel_id, device_id)] = compiled
                    kernel.compiled_binaries[device_id] = pickle.dumps(compiled)
                    self.stats['kernels_compiled'] += 1
                    
            except Exception as e:
                logger.error(f"Failed to compile kernel {kernel.name} for {device_id}: {e}")
        
        kernel.status = KernelStatus.READY
        self.stats['compilation_time'] += time.time() - start_time
    
    def _compile_cuda_kernel(self, kernel: DistributedKernel, context_info: Dict) -> Any:
        """Compile CUDA kernel"""
        
        if not CUDA_AVAILABLE:
            return None
        
        try:
            from pycuda.compiler import SourceModule
            
            # Add necessary CUDA headers
            full_source = f"""
            #include <cuda_runtime.h>
            #include <device_launch_parameters.h>
            
            {kernel.source_code}
            """
            
            # Compile
            module = SourceModule(full_source)
            
            # Get kernel function
            kernel_func = module.get_function(kernel.entry_point)
            
            return kernel_func
            
        except Exception as e:
            logger.error(f"CUDA compilation failed: {e}")
            return None
    
    def _compile_opencl_kernel(self, kernel: DistributedKernel, context_info: Dict) -> Any:
        """Compile OpenCL kernel"""
        
        if not OPENCL_AVAILABLE:
            return None
        
        try:
            context = context_info['context']
            
            # Convert kernel to OpenCL if needed
            opencl_source = self._convert_to_opencl(kernel.source_code, kernel.language)
            
            # Build program
            program = cl.Program(context, opencl_source).build()
            
            # Get kernel function
            kernel_func = getattr(program, kernel.entry_point)
            
            return kernel_func
            
        except Exception as e:
            logger.error(f"OpenCL compilation failed: {e}")
            return None
    
    def _convert_to_opencl(self, source_code: str, language: str) -> str:
        """Convert kernel source to OpenCL"""
        
        if language == 'opencl':
            return source_code
        
        # Simple conversion rules (would be more sophisticated in production)
        opencl_source = source_code
        
        if language == 'cuda':
            # CUDA to OpenCL conversion
            replacements = {
                '__global__': '__kernel',
                'blockIdx.x': 'get_group_id(0)',
                'blockIdx.y': 'get_group_id(1)',
                'blockIdx.z': 'get_group_id(2)',
                'threadIdx.x': 'get_local_id(0)',
                'threadIdx.y': 'get_local_id(1)',
                'threadIdx.z': 'get_local_id(2)',
                'blockDim.x': 'get_local_size(0)',
                'blockDim.y': 'get_local_size(1)',
                'blockDim.z': 'get_local_size(2)',
                '__syncthreads()': 'barrier(CLK_LOCAL_MEM_FENCE)',
                '__shared__': '__local'
            }
            
            for cuda_term, opencl_term in replacements.items():
                opencl_source = opencl_source.replace(cuda_term, opencl_term)
        
        return opencl_source
    
    def execute_kernel(self, kernel_id: str, target_devices: List[Tuple[str, str]],
                      input_data: Dict[str, Any], 
                      grid_size: Tuple[int, int, int] = (256, 1, 1),
                      block_size: Tuple[int, int, int] = (256, 1, 1)) -> str:
        """Execute kernel across distributed GPUs"""
        
        try:
            if kernel_id not in self.kernels:
                raise ValueError(f"Kernel {kernel_id} not registered")
            
            kernel = self.kernels[kernel_id]
            
            # Create task
            task_id = self._generate_task_id()
            task = KernelTask(
                task_id=task_id,
                kernel_id=kernel_id,
                target_devices=target_devices,
                input_data=input_data,
                output_addresses={},
                grid_size=grid_size,
                block_size=block_size,
                shared_memory_size=0,
                status=KernelStatus.PENDING
            )
            
            self.kernel_tasks[task_id] = task
            
            # Split execution across nodes
            local_devices = []
            remote_executions = []
            
            for node_id, device_id in target_devices:
                if node_id == self.node_id:
                    local_devices.append(device_id)
                else:
                    remote_executions.append((node_id, device_id))
            
            # Execute locally
            if local_devices:
                self._execute_kernel_local(task, local_devices)
            
            # Execute remotely
            if remote_executions:
                self._execute_kernel_remote(task, remote_executions)
            
            # Wait for completion
            self._wait_for_task_completion(task_id)
            
            return task_id
            
        except Exception as e:
            logger.error(f"Kernel execution failed: {e}")
            self.stats['failures'] += 1
            return ""
    
    def _execute_kernel_local(self, task: KernelTask, devices: List[str]):
        """Execute kernel on local GPUs"""
        
        try:
            kernel = self.kernels[task.kernel_id]
            
            for device_id in devices:
                if device_id not in self.gpu_contexts:
                    logger.error(f"Device {device_id} not available locally")
                    continue
                
                context_info = self.gpu_contexts[device_id]
                
                # Get compiled kernel
                cache_key = (task.kernel_id, device_id)
                if cache_key not in self.compiled_cache:
                    logger.error(f"Kernel not compiled for device {device_id}")
                    continue
                
                compiled_kernel = self.compiled_cache[cache_key]
                
                # Execute based on device type
                if context_info['type'] == 'cuda':
                    self._execute_cuda_kernel(compiled_kernel, task, context_info)
                elif context_info['type'] == 'opencl':
                    self._execute_opencl_kernel(compiled_kernel, task, context_info)
                
                self.stats['kernels_executed'] += 1
            
            task.status = KernelStatus.COMPLETED
            
        except Exception as e:
            logger.error(f"Local kernel execution failed: {e}")
            task.status = KernelStatus.FAILED
            task.error = str(e)
    
    def _execute_cuda_kernel(self, kernel_func, task: KernelTask, context_info: Dict):
        """Execute CUDA kernel"""
        
        if not CUDA_AVAILABLE:
            return
        
        try:
            import pycuda.driver as cuda
            import pycuda.gpuarray as gpuarray
            
            start_time = time.time()
            
            # Transfer input data to GPU
            gpu_arrays = {}
            for name, data in task.input_data.items():
                if isinstance(data, np.ndarray):
                    gpu_arrays[name] = gpuarray.to_gpu(data)
                else:
                    gpu_arrays[name] = data
            
            # Calculate grid and block dimensions
            grid = task.grid_size
            block = task.block_size
            
            # Prepare kernel arguments
            args = [gpu_arrays.get(name) for name in sorted(task.input_data.keys())]
            
            # Launch kernel
            kernel_func(*args, grid=grid, block=block)
            
            # Synchronize
            cuda.Context.synchronize()
            
            # Get results (simplified - would need output specification)
            results = {}
            for name, gpu_array in gpu_arrays.items():
                if hasattr(gpu_array, 'get'):
                    results[name] = gpu_array.get()
            
            task.result = results
            
            execution_time = time.time() - start_time
            self.stats['execution_time'] += execution_time
            
            logger.debug(f"CUDA kernel executed in {execution_time:.3f}s")
            
        except Exception as e:
            logger.error(f"CUDA execution failed: {e}")
            raise
    
    def _execute_opencl_kernel(self, kernel_func, task: KernelTask, context_info: Dict):
        """Execute OpenCL kernel"""
        
        if not OPENCL_AVAILABLE:
            return
        
        try:
            context = context_info['context']
            queue = context_info['queue']
            
            start_time = time.time()
            
            # Transfer input data to device
            buffers = {}
            for name, data in task.input_data.items():
                if isinstance(data, np.ndarray):
                    mf = cl.mem_flags
                    buffers[name] = cl.Buffer(
                        context, mf.READ_WRITE | mf.COPY_HOST_PTR, 
                        hostbuf=data
                    )
            
            # Calculate global and local work sizes
            global_size = tuple(g * b for g, b in zip(task.grid_size, task.block_size))
            local_size = task.block_size
            
            # Prepare kernel arguments
            args = [buffers.get(name) for name in sorted(task.input_data.keys())]
            
            # Launch kernel
            kernel_func(queue, global_size, local_size, *args)
            
            # Wait for completion
            queue.finish()
            
            # Get results
            results = {}
            for name, buffer in buffers.items():
                if name in task.input_data:
                    result = np.empty_like(task.input_data[name])
                    cl.enqueue_copy(queue, result, buffer)
                    results[name] = result
            
            task.result = results
            
            execution_time = time.time() - start_time
            self.stats['execution_time'] += execution_time
            
            logger.debug(f"OpenCL kernel executed in {execution_time:.3f}s")
            
        except Exception as e:
            logger.error(f"OpenCL execution failed: {e}")
            raise
    
    def _execute_kernel_remote(self, task: KernelTask, remote_devices: List[Tuple[str, str]]):
        """Execute kernel on remote nodes"""
        
        for node_id, device_id in remote_devices:
            try:
                # Send kernel execution request
                result = self.cluster.execute_remote_kernel(
                    node_id, task.kernel_id, device_id, task.input_data
                )
                
                if result:
                    task.result = result
                    self.stats['remote_executions'] += 1
                else:
                    logger.error(f"Remote execution failed on {node_id}:{device_id}")
                    
            except Exception as e:
                logger.error(f"Remote kernel execution error: {e}")
    
    def _distribute_kernel(self, kernel: DistributedKernel):
        """Distribute kernel to other nodes"""
        
        try:
            # Package kernel for distribution
            kernel_package = {
                'kernel_id': kernel.kernel_id,
                'name': kernel.name,
                'source_code': kernel.source_code,
                'language': kernel.language,
                'entry_point': kernel.entry_point
            }
            
            # Send to all other nodes
            for node_id in self.cluster.nodes.keys():
                if node_id != self.node_id:
                    # Would send kernel registration message
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to distribute kernel: {e}")
    
    def _wait_for_task_completion(self, task_id: str, timeout: float = 30.0):
        """Wait for task to complete"""
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = self.kernel_tasks.get(task_id)
            
            if task and task.status in [KernelStatus.COMPLETED, KernelStatus.FAILED]:
                return
            
            time.sleep(0.01)
        
        # Timeout
        if task_id in self.kernel_tasks:
            self.kernel_tasks[task_id].status = KernelStatus.FAILED
            self.kernel_tasks[task_id].error = "Execution timeout"
    
    def _start_execution_workers(self):
        """Start worker threads for kernel execution"""
        
        def local_worker():
            """Process local execution queue"""
            while True:
                try:
                    task = self.local_queue.get(timeout=1.0)
                    # Process task
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Local worker error: {e}")
        
        def remote_worker():
            """Process remote execution requests"""
            while True:
                try:
                    task = self.remote_queue.get(timeout=1.0)
                    # Process remote request
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"Remote worker error: {e}")
        
        # Start workers
        local_thread = threading.Thread(target=local_worker, daemon=True)
        remote_thread = threading.Thread(target=remote_worker, daemon=True)
        
        local_thread.start()
        remote_thread.start()
    
    def _get_local_gpu_devices(self) -> Dict[str, Dict]:
        """Get local GPU devices"""
        
        devices = {}
        
        # Get from hardware pool
        from ..hardware.base import UniversalHardwarePool, DeviceType
        
        try:
            pool = UniversalHardwarePool()
            
            for device_id, device in pool.devices.items():
                if device.device_type in [DeviceType.GPU_CUDA, DeviceType.GPU_ROCM, 
                                         DeviceType.GPU_METAL]:
                    devices[device_id] = {
                        'type': device.device_type.value,
                        'name': device.name,
                        'memory': device.memory_size,
                        'compute_power': device.capabilities.compute_power
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get local GPU devices: {e}")
        
        return devices
    
    def _generate_kernel_id(self, name: str, source_code: str) -> str:
        """Generate unique kernel ID"""
        
        content = f"{name}:{source_code}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        
        return f"task_{self.node_id}_{int(time.time() * 1000000)}"
    
    def get_kernel_info(self, kernel_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a kernel"""
        
        if kernel_id not in self.kernels:
            return None
        
        kernel = self.kernels[kernel_id]
        
        return {
            'kernel_id': kernel.kernel_id,
            'name': kernel.name,
            'language': kernel.language,
            'status': kernel.status.value,
            'compiled_for': list(kernel.compiled_binaries.keys()),
            'execution_count': kernel.execution_count,
            'avg_execution_time': (
                kernel.total_execution_time / kernel.execution_count 
                if kernel.execution_count > 0 else 0
            )
        }
    
    def get_task_result(self, task_id: str) -> Optional[Any]:
        """Get result of kernel execution task"""
        
        if task_id not in self.kernel_tasks:
            return None
        
        task = self.kernel_tasks[task_id]
        
        if task.status == KernelStatus.COMPLETED:
            return task.result
        elif task.status == KernelStatus.FAILED:
            return {'error': task.error}
        else:
            return {'status': task.status.value}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""
        
        return {
            **self.stats,
            'active_kernels': len(self.kernels),
            'pending_tasks': sum(
                1 for task in self.kernel_tasks.values() 
                if task.status == KernelStatus.PENDING
            ),
            'gpu_contexts': len(self.gpu_contexts),
            'compiled_kernels': len(self.compiled_cache)
        }
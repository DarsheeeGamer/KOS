"""
KOS Main System - Unified Hardware Pool
Complete hardware transparency for distributed computing
"""

import os
import sys
import time
import json
import logging
import threading
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
import numpy as np

# Import all KOS components
from .hardware.base import UniversalHardwarePool, DeviceType
from .compute.universal_api import UniversalComputeAPI, KernelDefinition, ExecutionContext
from .memory.unified_memory import UnifiedMemorySpace
from .memory.data_distributor import DistributionStrategy

logger = logging.getLogger(__name__)

@dataclass
class KOSConfig:
    """KOS system configuration"""
    enable_gpu_pooling: bool = True
    enable_cpu_pooling: bool = True
    enable_storage_pooling: bool = True
    enable_network_pooling: bool = True
    
    auto_device_discovery: bool = True
    auto_load_balancing: bool = True
    auto_memory_migration: bool = True
    auto_kernel_optimization: bool = True
    
    default_distribution_strategy: DistributionStrategy = DistributionStrategy.LOAD_BALANCED
    cache_coherency_enabled: bool = True
    prefetch_enabled: bool = True
    compression_enabled: bool = False
    
    log_level: str = "INFO"
    telemetry_enabled: bool = True
    
    # Resource limits
    max_memory_per_device: Optional[int] = None
    max_compute_utilization: float = 90.0
    max_network_bandwidth_usage: float = 80.0

class KOSUnifiedSystem:
    """Main KOS system providing unified hardware transparency"""
    
    def __init__(self, config: Optional[KOSConfig] = None):
        self.config = config or KOSConfig()
        self.is_initialized = False
        self.start_time = time.time()
        
        # Core components
        self.hardware_pool: Optional[UniversalHardwarePool] = None
        self.compute_api: Optional[UniversalComputeAPI] = None
        self.unified_memory: Optional[UnifiedMemorySpace] = None
        
        # System state
        self.system_lock = threading.RLock()
        self.running = False
        
        # Performance metrics
        self.metrics = {
            'total_kernels_executed': 0,
            'total_data_transferred': 0,
            'total_compute_time': 0.0,
            'device_utilization': {},
            'memory_usage': {},
            'network_traffic': 0,
            'errors': 0
        }
        
        # Configure logging
        self._setup_logging()
        
        logger.info("KOS Unified System initializing...")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('kos_system.log')
            ]
        )
    
    def initialize(self) -> bool:
        """Initialize the KOS system"""
        
        try:
            with self.system_lock:
                if self.is_initialized:
                    logger.warning("KOS system already initialized")
                    return True
                
                logger.info("Starting KOS system initialization...")
                
                # Initialize hardware pool
                logger.info("Initializing hardware pool...")
                self.hardware_pool = UniversalHardwarePool()
                
                if not self.hardware_pool.devices:
                    logger.error("No hardware devices found!")
                    return False
                
                logger.info(f"Discovered {len(self.hardware_pool.devices)} hardware devices")
                
                # Initialize compute API
                logger.info("Initializing universal compute API...")
                self.compute_api = UniversalComputeAPI(self.hardware_pool)
                
                # Initialize unified memory
                logger.info("Initializing unified memory space...")
                self.unified_memory = UnifiedMemorySpace(self.hardware_pool)
                
                # Start monitoring and background tasks
                self._start_background_tasks()
                
                self.is_initialized = True
                self.running = True
                
                # Log system summary
                self._log_system_summary()
                
                logger.info("KOS system initialization complete!")
                return True
                
        except Exception as e:
            logger.error(f"KOS system initialization failed: {e}")
            return False
    
    def _log_system_summary(self):
        """Log comprehensive system summary"""
        
        if not self.hardware_pool:
            return
        
        total_resources = self.hardware_pool.get_total_resources()
        
        logger.info("=== KOS UNIFIED HARDWARE POOL SUMMARY ===")
        logger.info(f"Total Devices: {total_resources['devices']}")
        logger.info(f"Total Compute Units: {total_resources['compute_units']}")
        logger.info(f"Total Memory: {total_resources['memory_bytes'] / (1024**3):.2f} GB")
        logger.info(f"Total Compute Power: {total_resources['compute_tflops']:.2f} TFLOPS")
        
        logger.info("Device Types:")
        for device_type, count in total_resources['device_types'].items():
            logger.info(f"  {device_type}: {count} devices")
        
        # Log individual devices
        for device in self.hardware_pool.devices.values():
            logger.info(f"Device {device.device_id}: {device.name} ({device.device_type.value})")
            logger.info(f"  Compute Units: {device.compute_units}")
            logger.info(f"  Memory: {device.memory_size / (1024**3):.2f} GB")
            logger.info(f"  Bandwidth: {device.memory_bandwidth:.1f} GB/s")
            logger.info(f"  Compute Power: {device.capabilities.compute_power:.2f} TFLOPS")
        
        logger.info("==========================================")
    
    def _start_background_tasks(self):
        """Start background monitoring and maintenance tasks"""
        
        def monitoring_task():
            """Monitor system health and performance"""
            while self.running:
                try:
                    self._update_metrics()
                    self._check_system_health()
                    
                    if self.config.auto_load_balancing:
                        self._perform_load_balancing()
                    
                    time.sleep(10)  # Update every 10 seconds
                    
                except Exception as e:
                    logger.error(f"Monitoring task error: {e}")
                    self.metrics['errors'] += 1
                    time.sleep(5)
        
        def maintenance_task():
            """Perform system maintenance"""
            while self.running:
                try:
                    # Clean up resources
                    self._cleanup_resources()
                    
                    # Optimize memory layout
                    if self.config.auto_memory_migration:
                        self._optimize_memory_layout()
                    
                    time.sleep(300)  # Every 5 minutes
                    
                except Exception as e:
                    logger.error(f"Maintenance task error: {e}")
                    self.metrics['errors'] += 1
                    time.sleep(60)
        
        # Start background threads
        monitor_thread = threading.Thread(target=monitoring_task, daemon=True)
        maintenance_thread = threading.Thread(target=maintenance_task, daemon=True)
        
        monitor_thread.start()
        maintenance_thread.start()
        
        logger.info("Background tasks started")
    
    # ===== USER API METHODS =====
    
    def malloc(self, size: int, device_hint: Optional[str] = None) -> Optional[int]:
        """Allocate memory in the unified hardware pool"""
        
        if not self.is_initialized or not self.unified_memory:
            logger.error("KOS system not initialized")
            return None
        
        try:
            # Use device hint if provided
            region = "general"
            if device_hint:
                device = self.hardware_pool.get_device(device_hint)
                if device and device.device_type in [DeviceType.GPU_CUDA, DeviceType.GPU_ROCM, DeviceType.GPU_METAL]:
                    region = "high_performance"
            
            virtual_address = self.unified_memory.malloc(size, region=region)
            
            if virtual_address:
                logger.debug(f"Allocated {size} bytes at 0x{virtual_address:x}")
            
            return virtual_address
            
        except Exception as e:
            logger.error(f"Memory allocation failed: {e}")
            self.metrics['errors'] += 1
            return None
    
    def free(self, address: int) -> bool:
        """Free memory in the unified hardware pool"""
        
        if not self.is_initialized or not self.unified_memory:
            return False
        
        try:
            success = self.unified_memory.free(address)
            if success:
                logger.debug(f"Freed memory at 0x{address:x}")
            return success
            
        except Exception as e:
            logger.error(f"Memory free failed: {e}")
            self.metrics['errors'] += 1
            return False
    
    def read(self, address: int, size: int) -> Optional[bytes]:
        """Read data from unified memory"""
        
        if not self.is_initialized or not self.unified_memory:
            return None
        
        try:
            return self.unified_memory.read(address, size)
            
        except Exception as e:
            logger.error(f"Memory read failed: {e}")
            self.metrics['errors'] += 1
            return None
    
    def write(self, address: int, data: bytes) -> bool:
        """Write data to unified memory"""
        
        if not self.is_initialized or not self.unified_memory:
            return False
        
        try:
            success = self.unified_memory.write(address, data)
            if success:
                self.metrics['total_data_transferred'] += len(data)
            return success
            
        except Exception as e:
            logger.error(f"Memory write failed: {e}")
            self.metrics['errors'] += 1
            return False
    
    def create_numpy_array(self, shape: Tuple[int, ...], dtype: np.dtype) -> Optional[Tuple[int, np.ndarray]]:
        """Create numpy array in unified memory"""
        
        if not self.is_initialized or not self.unified_memory:
            return None
        
        try:
            return self.unified_memory.numpy_array(shape, dtype)
            
        except Exception as e:
            logger.error(f"NumPy array creation failed: {e}")
            self.metrics['errors'] += 1
            return None
    
    def register_kernel(self, name: str, source_code: str, entry_point: str,
                       kernel_type: str = "universal") -> bool:
        """Register a compute kernel"""
        
        if not self.is_initialized or not self.compute_api:
            return False
        
        try:
            from .compute.universal_api import KernelDefinition, KernelType
            
            # Convert string to enum
            kernel_type_enum = KernelType.UNIVERSAL
            if kernel_type == "cuda":
                kernel_type_enum = KernelType.CUDA_C
            elif kernel_type == "hip":
                kernel_type_enum = KernelType.HIP_C
            elif kernel_type == "metal":
                kernel_type_enum = KernelType.METAL_SHADER
            elif kernel_type == "python":
                kernel_type_enum = KernelType.PYTHON_FUNCTION
            
            kernel_def = KernelDefinition(
                name=name,
                kernel_type=kernel_type_enum,
                source_code=source_code,
                entry_point=entry_point,
                parameters=[],
                local_work_size=(256, 1, 1),
                global_work_size=(65536, 1, 1)
            )
            
            success = self.compute_api.register_kernel(kernel_def)
            if success:
                logger.info(f"Registered kernel: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Kernel registration failed: {e}")
            self.metrics['errors'] += 1
            return False
    
    def execute_kernel(self, kernel_name: str, args: List[Any], 
                      device_hints: Optional[List[str]] = None) -> bool:
        """Execute kernel on optimal devices"""
        
        if not self.is_initialized or not self.compute_api:
            return False
        
        try:
            from .compute.universal_api import ExecutionContext, ExecutionMode
            
            # Select devices
            if device_hints:
                devices = device_hints
            else:
                # Auto-select optimal devices
                devices = self.compute_api.get_optimal_devices(kernel_name, 1024*1024)  # 1MB default
            
            if not devices:
                logger.error(f"No suitable devices for kernel {kernel_name}")
                return False
            
            # Create execution context
            context = ExecutionContext(
                devices=devices,
                mode=ExecutionMode.SYNCHRONOUS
            )
            
            # Execute kernel
            start_time = time.time()
            success = self.compute_api.execute_kernel(kernel_name, context, args)
            execution_time = time.time() - start_time
            
            if success:
                self.metrics['total_kernels_executed'] += 1
                self.metrics['total_compute_time'] += execution_time
                logger.debug(f"Executed kernel {kernel_name} in {execution_time:.3f}s on {len(devices)} devices")
            
            return success
            
        except Exception as e:
            logger.error(f"Kernel execution failed: {e}")
            self.metrics['errors'] += 1
            return False
    
    def get_device_list(self) -> List[Dict[str, Any]]:
        """Get list of all available devices"""
        
        if not self.is_initialized or not self.hardware_pool:
            return []
        
        devices = []
        for device in self.hardware_pool.devices.values():
            devices.append({
                'device_id': device.device_id,
                'name': device.name,
                'type': device.device_type.value,
                'vendor': device.vendor,
                'compute_units': device.compute_units,
                'memory_size': device.memory_size,
                'memory_bandwidth': device.memory_bandwidth,
                'compute_power': device.capabilities.compute_power,
                'utilization': device.utilization,
                'available': device.available
            })
        
        return devices
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        
        stats = {
            'uptime': time.time() - self.start_time,
            'initialized': self.is_initialized,
            'running': self.running,
            'metrics': self.metrics.copy()
        }
        
        if self.is_initialized:
            if self.hardware_pool:
                stats['hardware'] = self.hardware_pool.get_total_resources()
            
            if self.unified_memory:
                stats['memory'] = self.unified_memory.get_memory_stats()
            
            if self.compute_api:
                stats['compute'] = {
                    'device_utilization': self.compute_api.get_device_utilization(),
                    'memory_usage': self.compute_api.get_memory_usage()
                }
        
        return stats
    
    def optimize_for_workload(self, workload_type: str, workload_size: int) -> bool:
        """Optimize system for specific workload"""
        
        if not self.is_initialized:
            return False
        
        try:
            logger.info(f"Optimizing for {workload_type} workload of size {workload_size}")
            
            if workload_type == "ml_training":
                # GPU-heavy workload
                self._optimize_for_gpu_compute()
            elif workload_type == "data_processing":
                # Memory-bandwidth heavy
                self._optimize_for_memory_bandwidth()
            elif workload_type == "scientific_computing":
                # Mixed workload
                self._optimize_for_mixed_workload()
            else:
                logger.warning(f"Unknown workload type: {workload_type}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Workload optimization failed: {e}")
            self.metrics['errors'] += 1
            return False
    
    # ===== INTERNAL METHODS =====
    
    def _update_metrics(self):
        """Update system metrics"""
        
        try:
            if self.hardware_pool:
                # Update device utilization
                for device in self.hardware_pool.devices.values():
                    handler = self.hardware_pool.device_handlers.get(device.device_type)
                    if handler:
                        updated_device = handler.get_device_info(device.device_id)
                        if updated_device:
                            device.utilization = updated_device.utilization
                            device.temperature = updated_device.temperature
                            device.power_usage = updated_device.power_usage
                    
                    self.metrics['device_utilization'][device.device_id] = device.utilization
            
            if self.unified_memory:
                memory_stats = self.unified_memory.get_memory_stats()
                self.metrics['memory_usage'] = memory_stats['unified_memory']
                
        except Exception as e:
            logger.error(f"Metrics update failed: {e}")
    
    def _check_system_health(self):
        """Check system health and alert on issues"""
        
        try:
            # Check device temperatures
            for device in self.hardware_pool.devices.values():
                if device.temperature > 85.0:  # 85°C threshold
                    logger.warning(f"Device {device.device_id} temperature high: {device.temperature}°C")
                
                if device.utilization > self.config.max_compute_utilization:
                    logger.warning(f"Device {device.device_id} utilization high: {device.utilization}%")
            
            # Check memory usage
            if self.unified_memory:
                memory_stats = self.unified_memory.get_memory_stats()
                if memory_stats['unified_memory']['active_allocations'] > 10000:
                    logger.warning("High number of active memory allocations")
                    
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    def _perform_load_balancing(self):
        """Perform automatic load balancing"""
        
        try:
            if not self.hardware_pool:
                return
            
            # Find overutilized devices
            overutilized = [
                d for d in self.hardware_pool.devices.values() 
                if d.utilization > 80.0 and d.available
            ]
            
            # Find underutilized devices
            underutilized = [
                d for d in self.hardware_pool.devices.values()
                if d.utilization < 30.0 and d.available
            ]
            
            # TODO: Implement workload migration between devices
            if overutilized and underutilized:
                logger.debug(f"Load balancing: {len(overutilized)} overutilized, {len(underutilized)} underutilized")
                
        except Exception as e:
            logger.error(f"Load balancing failed: {e}")
    
    def _cleanup_resources(self):
        """Clean up unused resources"""
        
        try:
            # Clean up cache in unified memory system
            if self.unified_memory:
                self.unified_memory.data_distributor.cleanup_cache()
            
            # Clean up compute API resources
            if self.compute_api:
                # Would clean up unused kernels, buffers, etc.
                pass
                
        except Exception as e:
            logger.error(f"Resource cleanup failed: {e}")
    
    def _optimize_memory_layout(self):
        """Optimize memory layout across devices"""
        
        try:
            # This would analyze memory access patterns and migrate data
            # to optimal devices for better performance
            pass
            
        except Exception as e:
            logger.error(f"Memory layout optimization failed: {e}")
    
    def _optimize_for_gpu_compute(self):
        """Optimize system for GPU-heavy workloads"""
        
        # Prioritize GPU devices
        # Increase GPU memory allocation
        # Enable aggressive prefetching
        pass
    
    def _optimize_for_memory_bandwidth(self):
        """Optimize system for memory bandwidth"""
        
        # Use devices with highest memory bandwidth
        # Enable compression if beneficial
        # Optimize data distribution strategy
        pass
    
    def _optimize_for_mixed_workload(self):
        """Optimize system for mixed CPU/GPU workloads"""
        
        # Balance between CPU and GPU usage
        # Use hybrid distribution strategies
        pass
    
    def shutdown(self):
        """Shutdown the KOS system"""
        
        logger.info("KOS system shutting down...")
        
        try:
            with self.system_lock:
                self.running = False
                
                # Shutdown components in reverse order
                if self.unified_memory:
                    self.unified_memory.shutdown()
                
                if self.compute_api:
                    self.compute_api.shutdown()
                
                # Hardware pool cleanup is automatic
                
                self.is_initialized = False
                
                logger.info("KOS system shutdown complete")
                
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        if not self.initialize():
            raise RuntimeError("Failed to initialize KOS system")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.shutdown()

# Convenience functions for easy usage

def initialize_kos(config: Optional[KOSConfig] = None) -> Optional[KOSUnifiedSystem]:
    """Initialize KOS system with optional configuration"""
    
    system = KOSUnifiedSystem(config)
    if system.initialize():
        return system
    else:
        return None

def get_device_count() -> int:
    """Get total number of available devices"""
    
    try:
        hardware_pool = UniversalHardwarePool()
        return len(hardware_pool.devices)
    except:
        return 0

def get_total_compute_power() -> float:
    """Get total compute power in TFLOPS"""
    
    try:
        hardware_pool = UniversalHardwarePool()
        total_resources = hardware_pool.get_total_resources()
        return total_resources['compute_tflops']
    except:
        return 0.0

def get_total_memory() -> int:
    """Get total memory in bytes"""
    
    try:
        hardware_pool = UniversalHardwarePool()
        total_resources = hardware_pool.get_total_resources()
        return total_resources['memory_bytes']
    except:
        return 0
"""
KOS - Unified Hardware Pool Operating System
Complete hardware transparency for distributed computing

This package provides a unified interface to all hardware resources (CPUs, GPUs, 
storage, network) across multiple machines, making them appear as a single computer.

Key Features:
- Hardware Abstraction: Unified interface for CUDA, Metal, ROCm, CPU
- Byte-Level Distribution: Transparent data distribution across all devices  
- Memory Coherency: MOESI protocol ensures data consistency
- Kernel Translation: Automatic conversion between GPU languages
- Unified Memory: Single memory space across all hardware
- Complete Transparency: Applications see all hardware as one machine

Example Usage:

    import kos
    
    # Initialize the unified system
    with kos.initialize_kos() as system:
        # Allocate memory (distributed automatically)
        addr = system.malloc(1024 * 1024)  # 1MB
        
        # Create numpy array in unified memory
        addr, array = system.create_numpy_array((1000, 1000), np.float32)
        
        # Register and execute kernel across all GPUs
        system.register_kernel("vector_add", cuda_source, "vector_add")
        system.execute_kernel("vector_add", [addr1, addr2, addr3])
        
        # All operations are transparent across the entire hardware pool
"""

# Core system exports
from .kos_system import (
    KOSUnifiedSystem,
    KOSConfig,
    initialize_kos,
    get_device_count,
    get_total_compute_power,
    get_total_memory
)

# Hardware abstraction
from .hardware.base import (
    UniversalHardwarePool,
    HardwareDevice,
    DeviceType,
    DeviceCapabilities
)

# Compute API
from .compute.universal_api import (
    UniversalComputeAPI,
    KernelDefinition,
    ExecutionContext,
    KernelType,
    ExecutionMode
)

# Memory management
from .memory.unified_memory import UnifiedMemorySpace
from .memory.data_distributor import DistributionStrategy, DataType
from .memory.coherency_protocol import CoherencyState

__version__ = "1.0.0"
__author__ = "KOS Development Team"
__description__ = "Unified Hardware Pool Operating System"

__all__ = [
    # Core system
    'KOSUnifiedSystem',
    'KOSConfig',
    'initialize_kos',
    'get_device_count',
    'get_total_compute_power',
    'get_total_memory',
    
    # Hardware
    'UniversalHardwarePool',
    'HardwareDevice',
    'DeviceType', 
    'DeviceCapabilities',
    
    # Compute
    'UniversalComputeAPI',
    'KernelDefinition',
    'ExecutionContext',
    'KernelType',
    'ExecutionMode',
    
    # Memory
    'UnifiedMemorySpace',
    'DistributionStrategy',
    'DataType',
    'CoherencyState'
]

# Module-level convenience functions
def info():
    """Print KOS system information"""
    
    print(f"KOS (Unified Hardware Pool) v{__version__}")
    print(f"Total Devices: {get_device_count()}")
    print(f"Total Compute Power: {get_total_compute_power():.2f} TFLOPS")
    print(f"Total Memory: {get_total_memory() / (1024**3):.2f} GB")
    
    print("\nSupported Hardware:")
    print("  ✓ NVIDIA GPUs (CUDA)")
    print("  ✓ AMD GPUs (ROCm/HIP)")
    print("  ✓ Apple Silicon (Metal)")
    print("  ✓ Multi-core CPUs")
    print("  ✓ Storage devices (NVMe, SSD, HDD)")
    print("  ✓ Network interfaces")
    
    print("\nKey Features:")
    print("  ✓ Complete hardware transparency")
    print("  ✓ Byte-level data distribution") 
    print("  ✓ Universal kernel translation")
    print("  ✓ MOESI memory coherency")
    print("  ✓ Unified memory space")
    print("  ✓ Automatic load balancing")
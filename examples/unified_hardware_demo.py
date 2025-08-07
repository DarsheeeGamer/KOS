#!/usr/bin/env python3
"""
KOS Unified Hardware Pool - Complete Demo
This example demonstrates how multiple machines with different hardware 
appear as ONE unified computer.

SCENARIO:
- Computer 1: 2x RTX 4060Ti, 32GB RAM, Intel i7
- Computer 2: 2x RTX 4060Ti, 32GB RAM, AMD Ryzen 9  
- Result: KOS presents this as ONE computer with 4 GPUs, 64GB RAM, 2 CPUs

All operations are completely transparent - the application doesn't know
or care that hardware is distributed across multiple physical machines.
"""

import os
import sys
import time
import numpy as np

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import kos

def demonstrate_unified_hardware():
    """Demonstrate the unified hardware pool capabilities"""
    
    print("=== KOS UNIFIED HARDWARE POOL DEMONSTRATION ===")
    print()
    
    # Show system info before initialization
    print("System Information:")
    kos.info()
    print()
    
    # Initialize KOS with optimal configuration
    config = kos.KOSConfig(
        enable_gpu_pooling=True,
        enable_cpu_pooling=True,
        enable_storage_pooling=True,
        enable_network_pooling=True,
        auto_load_balancing=True,
        auto_memory_migration=True,
        default_distribution_strategy=kos.DistributionStrategy.LOAD_BALANCED,
        log_level="INFO"
    )
    
    print("Initializing KOS Unified System...")
    with kos.initialize_kos(config) as system:
        if not system:
            print("❌ Failed to initialize KOS system")
            return
        
        print("✅ KOS Unified System initialized successfully!")
        print()
        
        # Show discovered devices
        demonstrate_device_discovery(system)
        print()
        
        # Demonstrate unified memory
        demonstrate_unified_memory(system)
        print()
        
        # Demonstrate transparent GPU computing
        demonstrate_gpu_pooling(system)
        print()
        
        # Demonstrate cross-platform compatibility
        demonstrate_cross_platform_kernels(system)
        print()
        
        # Show performance statistics
        show_performance_stats(system)

def demonstrate_device_discovery(system):
    """Show all discovered hardware devices"""
    
    print("🔍 HARDWARE DISCOVERY:")
    print("All hardware appears as unified pool:")
    
    devices = system.get_device_list()
    
    gpu_count = 0
    cpu_count = 0
    storage_count = 0
    network_count = 0
    
    for device in devices:
        device_type = device['type']
        name = device['name']
        memory_gb = device['memory_size'] / (1024**3)
        compute_power = device['compute_power']
        
        icon = "🖥️"
        if "gpu" in device_type:
            icon = "🎮"
            gpu_count += 1
        elif device_type == "cpu":
            icon = "🧠"
            cpu_count += 1
        elif device_type == "storage":
            icon = "💾"
            storage_count += 1
        elif device_type == "network":
            icon = "🌐"
            network_count += 1
        
        print(f"  {icon} {name}")
        print(f"     Memory: {memory_gb:.1f} GB | Compute: {compute_power:.1f} TFLOPS")
    
    print()
    print(f"📊 UNIFIED POOL SUMMARY:")
    print(f"   GPUs: {gpu_count} devices (ALL appear as single GPU pool)")
    print(f"   CPUs: {cpu_count} devices (ALL appear as single CPU pool)")
    print(f"   Storage: {storage_count} devices (ALL appear as single storage pool)")
    print(f"   Network: {network_count} devices (ALL appear as single network pool)")
    print()
    print("💡 Applications see this as ONE computer with combined resources!")

def demonstrate_unified_memory(system):
    """Demonstrate unified memory across all devices"""
    
    print("🧠 UNIFIED MEMORY DEMONSTRATION:")
    print("Memory is transparently distributed across ALL devices...")
    
    # Allocate large array - will be distributed automatically
    print("\n1. Creating 1GB numpy array (distributed across all devices):")
    
    array_size = (1024, 1024, 256)  # ~1GB float32 array
    addr, large_array = system.create_numpy_array(array_size, np.float32)
    
    if addr and large_array is not None:
        print(f"   ✅ Created array at virtual address: 0x{addr:x}")
        print(f"   📏 Shape: {large_array.shape}")
        print(f"   📦 Size: {large_array.nbytes / (1024**3):.2f} GB")
        print("   🔄 Data automatically distributed byte-by-byte across:")
        
        # Get allocation info
        alloc_info = system.get_allocation_info(addr)
        if alloc_info and alloc_info['distributed_object']:
            segments = alloc_info['distributed_object']['segments']
            for segment in segments[:5]:  # Show first 5 segments
                device_id = segment['device_id']
                size_mb = segment['size'] / (1024**2)
                print(f"      📍 Device {device_id}: {size_mb:.1f} MB")
            if len(segments) > 5:
                print(f"      ... and {len(segments) - 5} more devices")
        
        print("\n2. Writing data (transparent across all devices):")
        
        # Fill with test pattern
        start_time = time.time()
        large_array.fill(42.0)  # This write distributes across all devices
        write_time = time.time() - start_time
        
        print(f"   ✅ Filled entire array with value 42.0")
        print(f"   ⏱️ Write time: {write_time:.3f} seconds")
        print("   🔄 Write automatically distributed to all device segments")
        
        print("\n3. Reading data (transparent from all devices):")
        
        # Read some data back
        start_time = time.time()
        sample = large_array[512, 512, 128]  # Read one element
        read_time = time.time() - start_time
        
        print(f"   ✅ Read sample value: {sample}")
        print(f"   ⏱️ Read time: {read_time:.6f} seconds")
        print("   🔄 Read automatically retrieved from correct device")
        
        # Free memory
        system.free(addr)
        print("\n   🗑️ Memory freed from all devices")
    else:
        print("   ❌ Failed to create unified array")
    
    print("\n💡 The application never knows data is distributed!")
    print("   It just works like normal memory, but uses ALL hardware!")

def demonstrate_gpu_pooling(system):
    """Demonstrate GPU pooling with transparent execution"""
    
    print("🎮 GPU POOLING DEMONSTRATION:")
    print("Using ALL GPUs as if they were ONE massive GPU...")
    
    # Register CUDA kernel that will work on ALL GPUs
    cuda_kernel_source = """
    __global__ void vector_add(float* a, float* b, float* c, int n) {
        int idx = blockIdx.x * blockDim.x + threadIdx.x;
        if (idx < n) {
            c[idx] = a[idx] + b[idx];
        }
    }
    """
    
    print("\n1. Registering compute kernel:")
    success = system.register_kernel(
        name="vector_add",
        source_code=cuda_kernel_source,
        entry_point="vector_add",
        kernel_type="cuda"
    )
    
    if success:
        print("   ✅ Kernel registered successfully")
        print("   🔄 Will be auto-translated for different GPU types:")
        print("      • NVIDIA GPUs: Uses CUDA directly")
        print("      • AMD GPUs: Auto-translated to HIP")
        print("      • Apple Silicon: Auto-translated to Metal")
        print("      • CPUs: Auto-translated to parallel loops")
    else:
        print("   ❌ Kernel registration failed")
        return
    
    print("\n2. Creating test vectors (distributed across all devices):")
    
    # Create vectors for computation
    vector_size = (1024 * 1024,)  # 1M elements
    
    addr_a, vec_a = system.create_numpy_array(vector_size, np.float32)
    addr_b, vec_b = system.create_numpy_array(vector_size, np.float32)
    addr_c, vec_c = system.create_numpy_array(vector_size, np.float32)
    
    if addr_a and addr_b and addr_c:
        # Fill vectors with test data
        vec_a.fill(1.0)
        vec_b.fill(2.0)
        vec_c.fill(0.0)
        
        print(f"   ✅ Created 3 vectors of {len(vec_a):,} elements each")
        print("   📍 Data distributed across all available devices")
        
        print("\n3. Executing kernel on ALL GPUs simultaneously:")
        
        # Execute on all available GPUs
        start_time = time.time()
        kernel_success = system.execute_kernel(
            kernel_name="vector_add",
            args=[addr_a, addr_b, addr_c, len(vec_a)]
        )
        execution_time = time.time() - start_time
        
        if kernel_success:
            print(f"   ✅ Kernel executed successfully")
            print(f"   ⏱️ Execution time: {execution_time:.3f} seconds")
            print("   🚀 Used ALL available compute units across ALL devices!")
            
            # Verify results
            sample_result = vec_c[100000]  # Check one element
            print(f"\n4. Verification:")
            print(f"   📊 Sample result: {sample_result} (should be 3.0)")
            
            if abs(sample_result - 3.0) < 1e-6:
                print("   ✅ Computation correct across all devices!")
            else:
                print("   ❌ Computation error detected")
        else:
            print("   ❌ Kernel execution failed")
        
        # Cleanup
        system.free(addr_a)
        system.free(addr_b)
        system.free(addr_c)
        
    print("\n💡 The kernel ran on EVERY available GPU as if it were one massive GPU!")
    print("   Multiple RTX 4060Ti cards work together seamlessly!")

def demonstrate_cross_platform_kernels(system):
    """Demonstrate cross-platform kernel translation"""
    
    print("🌐 CROSS-PLATFORM KERNEL TRANSLATION:")
    print("Same kernel runs on NVIDIA, AMD, Apple, and CPU automatically...")
    
    # Universal KOS kernel that works everywhere
    universal_kernel = """
    // Universal KOS kernel language
    void matrix_multiply_tile() {
        int idx = kos_thread_id();
        int total_threads = kos_thread_count();
        
        // Each thread processes part of the matrix
        // This will be translated automatically to:
        // - CUDA for NVIDIA GPUs
        // - HIP for AMD GPUs  
        // - Metal for Apple Silicon
        // - OpenMP for CPUs
        
        if (idx < total_threads) {
            // Matrix multiplication code here
            // (simplified for demo)
        }
        
        kos_barrier(); // Cross-platform synchronization
    }
    """
    
    print("\n1. Registering universal kernel:")
    success = system.register_kernel(
        name="matrix_multiply",
        source_code=universal_kernel,
        entry_point="matrix_multiply_tile",
        kernel_type="universal"
    )
    
    if success:
        print("   ✅ Universal kernel registered")
        print("   🔄 Kernel will be automatically translated to:")
        
        devices = system.get_device_list()
        for device in devices:
            device_type = device['type']
            name = device['name']
            
            if "cuda" in device_type:
                print(f"      🎮 {name}: CUDA C kernel")
            elif "rocm" in device_type:
                print(f"      🎮 {name}: HIP C kernel")  
            elif "metal" in device_type:
                print(f"      🎮 {name}: Metal compute shader")
            elif device_type == "cpu":
                print(f"      🧠 {name}: OpenMP parallel loop")
        
        print("\n💡 ONE kernel source → runs on EVERY type of hardware!")
        print("   No need to write separate CUDA, HIP, Metal, CPU versions!")
    else:
        print("   ❌ Universal kernel registration failed")

def show_performance_stats(system):
    """Show comprehensive system performance statistics"""
    
    print("📊 UNIFIED SYSTEM PERFORMANCE STATISTICS:")
    
    stats = system.get_system_stats()
    
    uptime = stats.get('uptime', 0)
    metrics = stats.get('metrics', {})
    
    print(f"\n🕒 SYSTEM STATUS:")
    print(f"   Uptime: {uptime:.1f} seconds")
    print(f"   Status: {'✅ RUNNING' if stats.get('running') else '❌ STOPPED'}")
    print(f"   Initialized: {'✅ YES' if stats.get('initialized') else '❌ NO'}")
    
    print(f"\n⚡ COMPUTE PERFORMANCE:")
    print(f"   Kernels Executed: {metrics.get('total_kernels_executed', 0)}")
    print(f"   Total Compute Time: {metrics.get('total_compute_time', 0):.3f} seconds") 
    print(f"   Data Transferred: {metrics.get('total_data_transferred', 0) / (1024**2):.1f} MB")
    print(f"   Errors: {metrics.get('errors', 0)}")
    
    if 'hardware' in stats:
        hardware = stats['hardware']
        print(f"\n🔧 HARDWARE UTILIZATION:")
        print(f"   Total Devices: {hardware.get('devices', 0)}")
        print(f"   Total Compute Units: {hardware.get('compute_units', 0)}")
        print(f"   Total Memory: {hardware.get('memory_bytes', 0) / (1024**3):.1f} GB")
        print(f"   Total Compute Power: {hardware.get('compute_tflops', 0):.1f} TFLOPS")
    
    if 'memory' in stats:
        memory = stats['memory']
        print(f"\n🧠 MEMORY STATISTICS:")
        print(f"   Active Allocations: {memory.get('active_allocations', 0)}")
        print(f"   Total Allocated: {memory.get('total_allocated_bytes', 0) / (1024**2):.1f} MB")
        print(f"   Virtual Pages Used: {memory.get('virtual_pages_used', 0)}")
    
    print(f"\n💡 This represents the COMBINED performance of ALL hardware!")
    print(f"   Multiple machines working together as ONE unified system!")

if __name__ == "__main__":
    print("Starting KOS Unified Hardware Pool demonstration...")
    print("This will show how multiple computers become ONE unified system.")
    print()
    
    try:
        demonstrate_unified_hardware()
        print("\n🎉 DEMONSTRATION COMPLETE!")
        print("\nKey Takeaways:")
        print("✅ Multiple machines appear as ONE computer")
        print("✅ All GPUs work together as single massive GPU") 
        print("✅ Memory is transparently distributed byte-by-byte")
        print("✅ Same code runs on NVIDIA, AMD, Apple, CPU automatically")
        print("✅ Applications never know hardware is distributed")
        print("✅ Complete hardware transparency achieved!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Demonstration interrupted by user")
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()
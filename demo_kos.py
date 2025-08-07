#!/usr/bin/env python3
"""
KOS Demo - Showcasing the Unified Hardware System
"""

import time
import numpy as np
from kos import KOSUnifiedSystem, KOSConfig

def demo_kos():
    """Demonstrate KOS functionality"""
    
    print("=" * 60)
    print("KOS - Unified Hardware Pool Operating System")
    print("=" * 60)
    
    # Initialize KOS with configuration
    config = KOSConfig(
        enable_gpu_pooling=True,
        enable_cpu_pooling=True,
        auto_load_balancing=True,
        log_level="INFO"
    )
    
    print("\n[1] Initializing KOS System...")
    kos = KOSUnifiedSystem(config)
    
    if not kos.initialize():
        print("Failed to initialize KOS!")
        return
    
    print("\n[2] Hardware Discovery Complete:")
    devices = kos.get_device_list()
    for device in devices:
        print(f"  - {device['name']} ({device['type']})")
        print(f"    Memory: {device['memory_size'] / (1024**3):.2f} GB")
        print(f"    Compute: {device['compute_power']:.2f} TFLOPS")
    
    # Get system statistics
    stats = kos.get_system_stats()
    total_memory = sum(d['memory_size'] for d in devices)
    total_compute = sum(d['compute_power'] for d in devices)
    
    print(f"\n[3] Total System Resources:")
    print(f"  - Total Devices: {len(devices)}")
    print(f"  - Total Memory: {total_memory / (1024**3):.2f} GB")
    print(f"  - Total Compute Power: {total_compute:.2f} TFLOPS")
    
    # Demonstrate unified memory allocation
    print("\n[4] Testing Unified Memory Space...")
    
    # Allocate memory in unified space
    size_mb = 10
    size_bytes = size_mb * 1024 * 1024
    addr = kos.malloc(size_bytes)
    
    if addr:
        print(f"  ✓ Allocated {size_mb} MB at address 0x{addr:x}")
        
        # Write data to unified memory
        test_pattern = b"Hello from KOS unified memory! "  # 32 bytes
        test_data = test_pattern * (size_bytes // len(test_pattern))
        test_data = test_data[:size_bytes]  # Ensure exact size
        success = kos.write(addr, test_data)
        
        if success:
            print(f"  ✓ Wrote {len(test_data)} bytes to unified memory")
            
            # Read data back
            read_data = kos.read(addr, len(test_data))
            if read_data and read_data[:32] == test_pattern:
                print(f"  ✓ Successfully read data back from unified memory")
            else:
                print(f"  ✗ Failed to read correct data")
        
        # Free memory
        if kos.free(addr):
            print(f"  ✓ Freed memory at 0x{addr:x}")
    
    # Test numpy array in unified memory
    print("\n[5] Testing NumPy Arrays in Unified Memory...")
    
    shape = (1000, 1000)
    result = kos.create_numpy_array(shape, np.float32)
    
    if result:
        addr, array = result
        print(f"  ✓ Created {shape} float32 array at 0x{addr:x}")
        print(f"  ✓ Array size: {array.nbytes / (1024**2):.2f} MB")
        
        # Perform computation
        array[:] = np.random.randn(*shape)
        mean = array.mean()
        std = array.std()
        print(f"  ✓ Array statistics: mean={mean:.4f}, std={std:.4f}")
        
        # Free the array
        kos.free(addr)
        print(f"  ✓ Freed numpy array")
    
    # Test kernel registration (simple Python kernel for now)
    print("\n[6] Testing Kernel Registration...")
    
    python_kernel = '''
def vector_add(a, b, c, n):
    """Simple vector addition kernel"""
    for i in range(n):
        c[i] = a[i] + b[i]
'''
    
    success = kos.register_kernel(
        "vector_add",
        python_kernel,
        "vector_add",
        kernel_type="python"
    )
    
    if success:
        print("  ✓ Registered 'vector_add' kernel")
    else:
        print("  ✗ Failed to register kernel")
    
    # Show final statistics
    print("\n[7] System Statistics:")
    final_stats = kos.get_system_stats()
    print(f"  - Uptime: {final_stats['uptime']:.2f} seconds")
    print(f"  - Total kernels executed: {final_stats['metrics']['total_kernels_executed']}")
    print(f"  - Data transferred: {final_stats['metrics']['total_data_transferred']} bytes")
    print(f"  - Errors: {final_stats['metrics']['errors']}")
    
    # Test process management through advlayer
    print("\n[8] Testing Process Management...")
    from kos.advlayer.process_manager import ProcessManager
    pm = ProcessManager()
    
    result = pm.execute_command('echo "Process executed through KOS"')
    if result['success']:
        print(f"  ✓ Process execution: {result['stdout'].strip()}")
    
    # Test VFS
    print("\n[9] Testing Virtual File System...")
    from kos.core.vfs import get_vfs
    vfs = get_vfs("demo_kos.vfs")
    
    test_file = "/home/user/test_kos.txt"
    test_content = b"KOS VFS is working!"
    
    with vfs.open(test_file, 'w') as f:
        f.write(test_content)
    print(f"  ✓ Wrote file to VFS: {test_file}")
    
    with vfs.open(test_file, 'r') as f:
        read_content = f.read()
    
    if read_content == test_content:
        print(f"  ✓ Successfully read file from VFS")
    
    # Cleanup
    vfs.unlink(test_file)
    print(f"  ✓ Cleaned up test file")
    
    # Shutdown
    print("\n[10] Shutting down KOS...")
    kos.shutdown()
    print("  ✓ KOS shutdown complete")
    
    print("\n" + "=" * 60)
    print("KOS Demo Complete!")
    print("=" * 60)

if __name__ == "__main__":
    demo_kos()
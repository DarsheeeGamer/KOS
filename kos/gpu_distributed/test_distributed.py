#!/usr/bin/env python3
"""
Test script for KOS Distributed GPU System

This shows how to use the REAL distributed GPU implementation from Python
"""

import os
import sys
import time
import numpy as np

# Try to import the compiled module
try:
    import kos_gpu
    HAS_KOS_GPU = True
except ImportError:
    HAS_KOS_GPU = False
    print("❌ kos_gpu module not found. Please run 'make python' first.")

# Fallback to PyTorch for comparison
try:
    import torch
    import torch.distributed as dist
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


def test_kos_distributed():
    """Test KOS distributed GPU system"""
    if not HAS_KOS_GPU:
        print("Skipping KOS test - module not available")
        return
    
    print("\n" + "="*60)
    print("Testing KOS Distributed GPU System")
    print("="*60)
    
    # Initialize distributed system
    gpu_system = kos_gpu.DistributedGPU()
    gpu_system.initialize()
    
    # Get cluster info
    info = gpu_system.get_info()
    print(f"\nCluster Information:")
    print(f"  Local GPUs: {info['gpu_count']}")
    print(f"  World Rank: {info['world_rank']}")
    print(f"  World Size: {info['world_size']}")
    print(f"  Total GPUs: {info['gpu_count'] * info['world_size']}")
    
    # Test tensor allocation
    print("\n1. Testing Tensor Allocation...")
    shape = np.array([1024, 1024], dtype=np.int32)  # 1M floats = 4MB
    tensor = gpu_system.allocate_tensor(shape)
    print(f"   Allocated tensor shape: {tensor.shape}")
    print(f"   Tensor size: {tensor.nbytes / (1024*1024):.2f} MB")
    
    # Test AllReduce
    print("\n2. Testing AllReduce...")
    # Initialize with rank value
    tensor.fill(info['world_rank'] + 1.0)
    print(f"   Before AllReduce: tensor[0] = {tensor[0]}")
    
    gpu_system.all_reduce(tensor)
    kos_gpu.synchronize()
    
    expected = sum(range(1, info['world_size'] + 1))
    print(f"   After AllReduce: tensor[0] = {tensor[0]}")
    print(f"   Expected: {expected}")
    
    # Test Broadcast
    print("\n3. Testing Broadcast...")
    if info['world_rank'] == 0:
        tensor.fill(42.0)
    else:
        tensor.fill(0.0)
    
    print(f"   Before Broadcast: tensor[0] = {tensor[0]}")
    gpu_system.broadcast(tensor, root=0)
    kos_gpu.synchronize()
    print(f"   After Broadcast: tensor[0] = {tensor[0]}")
    
    # Benchmark
    print("\n4. Running Benchmark...")
    gpu_system.benchmark()
    
    print("\n✅ KOS Distributed GPU test complete!")


def test_pytorch_comparison():
    """Compare with PyTorch DDP for validation"""
    if not HAS_TORCH:
        print("Skipping PyTorch comparison - not installed")
        return
    
    print("\n" + "="*60)
    print("PyTorch DDP Comparison")
    print("="*60)
    
    # Initialize PyTorch distributed
    if 'RANK' in os.environ:
        dist.init_process_group(backend='nccl')
        rank = dist.get_rank()
        world_size = dist.get_world_size()
        
        print(f"\nPyTorch Distributed:")
        print(f"  Rank: {rank}")
        print(f"  World Size: {world_size}")
        
        # Create tensor on GPU
        device = torch.device(f'cuda:{rank % torch.cuda.device_count()}')
        tensor = torch.ones(1024, 1024, device=device) * (rank + 1)
        
        print(f"\n1. Before AllReduce: {tensor[0, 0].item()}")
        dist.all_reduce(tensor)
        print(f"   After AllReduce: {tensor[0, 0].item()}")
        
        # Broadcast test
        if rank == 0:
            tensor.fill_(42.0)
        else:
            tensor.fill_(0.0)
        
        print(f"\n2. Before Broadcast: {tensor[0, 0].item()}")
        dist.broadcast(tensor, src=0)
        print(f"   After Broadcast: {tensor[0, 0].item()}")
        
        dist.destroy_process_group()
    else:
        print("PyTorch distributed requires RANK and WORLD_SIZE env vars")


def benchmark_comparison():
    """Benchmark KOS vs PyTorch"""
    print("\n" + "="*60)
    print("Performance Comparison")
    print("="*60)
    
    size = 100 * 1024 * 1024  # 100M floats = 400MB
    iterations = 100
    
    # KOS benchmark
    if HAS_KOS_GPU:
        print("\nKOS Performance:")
        gpu_system = kos_gpu.DistributedGPU()
        gpu_system.initialize()
        
        shape = np.array([size], dtype=np.int32)
        tensor = gpu_system.allocate_tensor(shape)
        
        # Warmup
        for _ in range(10):
            gpu_system.all_reduce(tensor)
        kos_gpu.synchronize()
        
        # Benchmark
        start = time.time()
        for _ in range(iterations):
            gpu_system.all_reduce(tensor)
        kos_gpu.synchronize()
        kos_time = time.time() - start
        
        bandwidth = (size * 4 * iterations) / (kos_time * 1024**3)  # GB/s
        print(f"  Time: {kos_time:.3f}s")
        print(f"  Bandwidth: {bandwidth:.2f} GB/s")
    
    # PyTorch benchmark
    if HAS_TORCH and torch.cuda.is_available():
        print("\nPyTorch Performance:")
        device = torch.device('cuda:0')
        tensor = torch.ones(size, device=device)
        
        # Warmup
        for _ in range(10):
            # Note: This is single GPU, not distributed
            tensor = tensor * 2.0
        torch.cuda.synchronize()
        
        # Benchmark
        start = time.time()
        for _ in range(iterations):
            tensor = tensor * 2.0
        torch.cuda.synchronize()
        torch_time = time.time() - start
        
        bandwidth = (size * 4 * iterations) / (torch_time * 1024**3)
        print(f"  Time: {torch_time:.3f}s")
        print(f"  Bandwidth: {bandwidth:.2f} GB/s")


def main():
    print("========================================")
    print("   KOS DISTRIBUTED GPU SYSTEM TEST")
    print("========================================")
    
    # Check CUDA availability
    if HAS_KOS_GPU:
        gpu_count = kos_gpu.get_gpu_count()
        print(f"\n✓ Found {gpu_count} GPUs")
    else:
        print("\n❌ KOS GPU module not available")
        print("   Please compile with: make python")
        return
    
    # Run tests
    test_kos_distributed()
    test_pytorch_comparison()
    benchmark_comparison()
    
    print("\n" + "="*60)
    print("All tests complete!")
    print("="*60)


if __name__ == "__main__":
    main()
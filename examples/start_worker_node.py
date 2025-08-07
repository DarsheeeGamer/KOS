#!/usr/bin/env python3
"""
Start KOS Worker Node - Add This Computer to the Distributed Hardware Pool

This script starts a worker node that contributes its hardware to the unified pool.
Run this on each additional computer with RTX 4060Ti or other GPUs.

Usage:
    python start_worker_node.py --master 192.168.1.100 [--port 5555] [--name worker1]
"""

import os
import sys
import argparse
import logging
import time
import signal
from typing import Optional

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kos.distributed_system import (
    KOSDistributedSystem,
    DistributedKOSConfig,
    create_kos_cluster
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global system reference for signal handling
distributed_system: Optional[KOSDistributedSystem] = None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global distributed_system
    
    logger.info("\nReceived shutdown signal. Gracefully shutting down...")
    
    if distributed_system:
        distributed_system.shutdown()
    
    sys.exit(0)

def start_worker_node(master_address: str, port: int = 5555, 
                     node_name: Optional[str] = None):
    """Start a KOS worker node"""
    
    global distributed_system
    
    print("\n" + "=" * 70)
    print("🔧 STARTING KOS DISTRIBUTED WORKER NODE")
    print("=" * 70)
    print()
    
    # Create configuration
    config = DistributedKOSConfig(
        node_name=node_name,  # Will auto-generate if None
        is_master_node=False,
        master_address=master_address,
        master_port=port,
        
        # Enable all distributed features
        enable_distributed_memory=True,
        enable_remote_execution=True,
        enable_checkpointing=True,
        
        # Performance settings
        network_compression=True,
        memory_migration_threshold=0.8,
        load_balance_strategy="least_loaded"
    )
    
    print(f"📋 Configuration:")
    print(f"   Node Name: {config.node_name or 'auto-generated'}")
    print(f"   Master Address: {config.master_address}:{config.master_port}")
    print(f"   Distributed Memory: {config.enable_distributed_memory}")
    print(f"   Remote Execution: {config.enable_remote_execution}")
    print()
    
    print(f"🔗 Connecting to master at {master_address}:{port}...")
    
    # Create and initialize system
    distributed_system = KOSDistributedSystem(config)
    
    if not distributed_system.initialize():
        logger.error("Failed to initialize distributed system")
        return False
    
    print("\n" + "=" * 70)
    print("✅ WORKER NODE CONNECTED SUCCESSFULLY")
    print("=" * 70)
    print()
    
    # Get local hardware info
    hardware_pool = distributed_system.hardware_pool
    
    print("🖥️  Local Hardware Contributing to Pool:")
    
    # Count devices by type
    cpu_count = 0
    gpu_count = 0
    gpu_memory = 0
    
    for device in hardware_pool.devices.values():
        device_type = device.device_type.value
        
        if 'cpu' in device_type:
            cpu_count += 1
            print(f"   🧠 CPU: {device.name}")
            print(f"      Cores: {device.capabilities.compute_power}")
            print(f"      Memory: {device.memory_size / (1024**3):.1f} GB")
            
        elif 'gpu' in device_type:
            gpu_count += 1
            gpu_memory += device.memory_size
            print(f"   🎮 GPU: {device.name}")
            print(f"      Memory: {device.memory_size / (1024**3):.1f} GB")
            print(f"      Compute: {device.capabilities.compute_power}")
            
            # Show specific GPU capabilities
            if 'cuda' in device_type:
                print(f"      Type: NVIDIA CUDA")
                if hasattr(device.capabilities, 'tensor_cores'):
                    print(f"      Tensor Cores: {device.capabilities.tensor_cores}")
            elif 'rocm' in device_type:
                print(f"      Type: AMD ROCm")
            elif 'metal' in device_type:
                print(f"      Type: Apple Metal")
    
    print()
    print(f"📊 Hardware Summary:")
    print(f"   CPUs: {cpu_count}")
    print(f"   GPUs: {gpu_count}")
    if gpu_count > 0:
        print(f"   Total GPU Memory: {gpu_memory / (1024**3):.1f} GB")
    print()
    
    # Show cluster status
    time.sleep(2)  # Wait for cluster sync
    cluster_info = distributed_system.get_cluster_info()
    cluster_stats = cluster_info.get('cluster', {})
    
    print("🌐 Unified Cluster Status:")
    print(f"   Total Nodes: {cluster_stats.get('node_count', 1)}")
    print(f"   Total GPUs: {cluster_stats.get('total_gpus', gpu_count)}")
    print(f"   Total Memory: {cluster_stats.get('total_memory', 0) / (1024**3):.1f} GB")
    print()
    
    # Special message for RTX 4060Ti
    rtx_4060ti_count = 0
    for device in hardware_pool.devices.values():
        if '4060' in device.name.upper() and 'TI' in device.name.upper():
            rtx_4060ti_count += 1
    
    if rtx_4060ti_count > 0:
        print(f"🎯 Found {rtx_4060ti_count}x RTX 4060Ti on this node!")
        print("   These GPUs are now part of the unified pool")
        print("   ML models will automatically use ALL 4060Ti GPUs across all nodes")
        print()
    
    print("⚡ Worker node is active and contributing to the unified hardware pool")
    print("   All local hardware is now transparently available to the cluster")
    print("   Press Ctrl+C to disconnect from cluster")
    print()
    
    # Monitor and report status
    last_report_time = time.time()
    
    try:
        while True:
            time.sleep(10)  # Check every 10 seconds
            
            # Periodic status report
            if time.time() - last_report_time > 60:  # Every minute
                cluster_stats = distributed_system.cluster_manager.get_cluster_stats()
                
                print(f"\n📈 Status Update:")
                print(f"   Node Status: ACTIVE")
                print(f"   Cluster Size: {cluster_stats['node_count']} nodes")
                print(f"   Total GPUs in Pool: {cluster_stats['total_gpus']}")
                
                # Check for distributed operations
                memory_stats = distributed_system.distributed_memory.get_statistics()
                compute_stats = distributed_system.distributed_compute.get_statistics()
                
                if memory_stats['remote_reads'] > 0 or memory_stats['remote_writes'] > 0:
                    print(f"   Memory Operations:")
                    print(f"      Remote Reads: {memory_stats['remote_reads']}")
                    print(f"      Remote Writes: {memory_stats['remote_writes']}")
                
                if compute_stats['kernels_executed'] > 0:
                    print(f"   Compute Operations:")
                    print(f"      Kernels Executed: {compute_stats['kernels_executed']}")
                    print(f"      Remote Executions: {compute_stats['remote_executions']}")
                
                last_report_time = time.time()
                
    except KeyboardInterrupt:
        pass
    
    return True

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Start KOS Distributed Worker Node"
    )
    parser.add_argument(
        '--master',
        type=str,
        required=True,
        help='Master node IP address (e.g., 192.168.1.100)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5555,
        help='Master node port (default: 5555)'
    )
    parser.add_argument(
        '--name',
        type=str,
        default=None,
        help='Worker node name (default: auto-generated)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start worker node
    success = start_worker_node(args.master, args.port, args.name)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
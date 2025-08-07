#!/usr/bin/env python3
"""
Start KOS Master Node - The Primary Node in the Distributed Hardware Pool

This script starts the master node that coordinates the entire cluster.
Run this on the first computer that will manage the unified hardware pool.

Usage:
    python start_master_node.py [--port 5555] [--name master]
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

def start_master_node(port: int = 5555, node_name: Optional[str] = None):
    """Start the KOS master node"""
    
    global distributed_system
    
    print("\n" + "=" * 70)
    print("🚀 STARTING KOS DISTRIBUTED MASTER NODE")
    print("=" * 70)
    print()
    
    # Create configuration
    config = DistributedKOSConfig(
        node_name=node_name or "kos_master",
        is_master_node=True,
        master_port=port,
        
        # Enable all distributed features
        enable_distributed_memory=True,
        enable_remote_execution=True,
        enable_checkpointing=True,
        
        # Performance settings
        network_compression=True,
        memory_migration_threshold=0.8,
        load_balance_strategy="least_loaded",
        
        # Checkpoint every 5 minutes
        checkpoint_interval=300
    )
    
    print(f"📋 Configuration:")
    print(f"   Node Name: {config.node_name}")
    print(f"   Master Port: {config.master_port}")
    print(f"   Distributed Memory: {config.enable_distributed_memory}")
    print(f"   Remote Execution: {config.enable_remote_execution}")
    print(f"   Load Balance Strategy: {config.load_balance_strategy}")
    print()
    
    # Create and initialize system
    print("🔧 Initializing distributed system...")
    distributed_system = KOSDistributedSystem(config)
    
    if not distributed_system.initialize():
        logger.error("Failed to initialize distributed system")
        return False
    
    print("\n" + "=" * 70)
    print("✅ MASTER NODE STARTED SUCCESSFULLY")
    print("=" * 70)
    print()
    
    # Get cluster info
    cluster_info = distributed_system.get_cluster_info()
    
    print("📊 Master Node Information:")
    print(f"   Node ID: {cluster_info.get('node_id', 'unknown')}")
    print(f"   Status: MASTER")
    print(f"   Uptime: {cluster_info.get('uptime', 0):.1f} seconds")
    print()
    
    # Show how to connect workers
    import socket
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    
    print("🔗 Worker Connection Instructions:")
    print(f"   On other machines, run:")
    print(f"   python start_worker_node.py --master {ip_address} --port {port}")
    print()
    
    print("📌 Waiting for worker nodes to connect...")
    print("   The cluster will automatically discover and integrate new nodes")
    print("   Press Ctrl+C to shutdown the master node")
    print()
    
    # Monitor cluster growth
    last_node_count = 1
    monitoring_start = time.time()
    
    try:
        while True:
            time.sleep(5)  # Check every 5 seconds
            
            cluster_stats = distributed_system.cluster_manager.get_cluster_stats()
            current_node_count = cluster_stats['node_count']
            
            if current_node_count != last_node_count:
                print(f"\n🆕 Cluster Update:")
                print(f"   Total Nodes: {current_node_count}")
                print(f"   Total GPUs: {cluster_stats['total_gpus']}")
                print(f"   Total Memory: {cluster_stats['total_memory'] / (1024**3):.1f} GB")
                print(f"   Active Nodes: {', '.join(cluster_stats['active_nodes'])}")
                
                # Show all devices
                all_devices = distributed_system.cluster_manager.get_all_devices()
                gpu_devices = [d for d in all_devices if 'gpu' in d.get('type', '')]
                
                if gpu_devices:
                    print(f"\n   GPU Pool:")
                    for device in gpu_devices:
                        node = device.get('node_id', 'unknown')
                        name = device.get('name', 'Unknown')
                        memory_gb = device.get('memory_size', 0) / (1024**3)
                        print(f"      [{node}] {name} - {memory_gb:.1f} GB")
                
                print()
                last_node_count = current_node_count
            
            # Periodic status update
            if time.time() - monitoring_start > 60:  # Every minute
                print(f"⏱️  Master node uptime: {(time.time() - monitoring_start) / 60:.1f} minutes")
                print(f"   Cluster size: {current_node_count} nodes, {cluster_stats['total_gpus']} GPUs")
                monitoring_start = time.time()
                
    except KeyboardInterrupt:
        pass
    
    return True

def main():
    """Main entry point"""
    
    parser = argparse.ArgumentParser(
        description="Start KOS Distributed Master Node"
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
        help='Node name (default: auto-generated)'
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
    
    # Start master node
    success = start_master_node(args.port, args.name)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
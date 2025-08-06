"""
Cluster Management Commands for KOS
Provides commands for distributed computing operations
"""

import os
import sys
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class ClusterCommands:
    """Cluster management commands"""
    
    def __init__(self, shell):
        self.shell = shell
        self.cluster_node = None
        self.dvfs = None
        self.scheduler = None
        
    def initialize_cluster_components(self):
        """Initialize cluster components if not already done"""
        if not self.cluster_node:
            from ...distributed.cluster import ClusterNode
            # Get local IP address
            import socket
            hostname = socket.gethostname()
            try:
                local_ip = socket.gethostbyname(hostname)
            except:
                local_ip = "127.0.0.1"
            
            self.cluster_node = ClusterNode(address=local_ip)
            
            # Initialize distributed VFS
            from ...distributed.dvfs import DistributedVFS
            if self.shell.vfs:
                self.dvfs = DistributedVFS(
                    local_vfs=self.shell.vfs,
                    cluster_node=self.cluster_node
                )
            
            # Initialize distributed scheduler
            from ...distributed.scheduler import DistributedScheduler
            if self.shell.klayer:
                self.scheduler = DistributedScheduler(
                    cluster_node=self.cluster_node,
                    local_executor=self.shell.klayer.process_manager
                )
    
    def do_cluster(self, args):
        """Cluster management commands
        Usage:
            cluster create <name>              - Create a new cluster
            cluster join <name> <address>      - Join existing cluster
            cluster status                     - Show cluster status
            cluster nodes                      - List cluster nodes
            cluster leave                      - Leave current cluster
            cluster exec <command>             - Execute command on cluster
            cluster distribute <file>          - Distribute file across nodes
        """
        if not args:
            print("Usage: cluster <subcommand> [options]")
            print("Type 'help cluster' for detailed help")
            return
        
        parts = args.strip().split()
        subcommand = parts[0].lower()
        
        if subcommand == 'create':
            self._cluster_create(parts[1:] if len(parts) > 1 else [])
        elif subcommand == 'join':
            self._cluster_join(parts[1:] if len(parts) > 1 else [])
        elif subcommand == 'status':
            self._cluster_status()
        elif subcommand == 'nodes':
            self._cluster_nodes()
        elif subcommand == 'leave':
            self._cluster_leave()
        elif subcommand == 'exec':
            self._cluster_exec(' '.join(parts[1:]) if len(parts) > 1 else '')
        elif subcommand == 'distribute':
            self._cluster_distribute(parts[1:] if len(parts) > 1 else [])
        else:
            print(f"Unknown cluster subcommand: {subcommand}")
    
    def _cluster_create(self, args):
        """Create a new cluster"""
        if not args:
            print("Usage: cluster create <name>")
            return
        
        cluster_name = args[0]
        
        # Initialize cluster components
        self.initialize_cluster_components()
        
        print(f"Creating cluster '{cluster_name}'...")
        
        if self.cluster_node.create_cluster(cluster_name):
            print(f"✓ Cluster '{cluster_name}' created successfully")
            print(f"  Node ID: {self.cluster_node.node_id}")
            print(f"  Role: Leader")
            print(f"  Address: {self.cluster_node.address}:{self.cluster_node.port}")
            
            # Start distributed services
            if self.dvfs:
                self.dvfs.start()
                print("  ✓ Distributed VFS started")
            
            if self.scheduler:
                self.scheduler.start()
                print("  ✓ Distributed scheduler started")
            
            print(f"\nOther nodes can join with:")
            print(f"  kos cluster join {cluster_name} {self.cluster_node.address}")
        else:
            print(f"✗ Failed to create cluster '{cluster_name}'")
    
    def _cluster_join(self, args):
        """Join an existing cluster"""
        if len(args) < 2:
            print("Usage: cluster join <name> <address> [port]")
            return
        
        cluster_name = args[0]
        address = args[1]
        port = int(args[2]) if len(args) > 2 else 9000
        
        # Initialize cluster components
        self.initialize_cluster_components()
        
        print(f"Joining cluster '{cluster_name}' at {address}:{port}...")
        
        if self.cluster_node.join_cluster(cluster_name, address, port):
            print(f"✓ Successfully joined cluster '{cluster_name}'")
            print(f"  Node ID: {self.cluster_node.node_id}")
            print(f"  Role: {self.cluster_node.consensus.state.value}")
            
            # Start distributed services
            if self.dvfs:
                self.dvfs.start()
                print("  ✓ Distributed VFS synchronized")
            
            if self.scheduler:
                self.scheduler.start()
                print("  ✓ Distributed scheduler connected")
            
            # Show cluster status
            status = self.cluster_node.get_cluster_status()
            print(f"\nCluster Status:")
            print(f"  Active nodes: {status['active_nodes']}")
            print(f"  Leader: {status['leader']}")
        else:
            print(f"✗ Failed to join cluster '{cluster_name}'")
            print("  Check that the cluster exists and is reachable")
    
    def _cluster_status(self):
        """Show cluster status"""
        if not self.cluster_node or self.cluster_node.state.value == 'disconnected':
            print("Not connected to any cluster")
            return
        
        status = self.cluster_node.get_cluster_status()
        
        print("\nCluster Status")
        print("=" * 40)
        print(f"Cluster Name: {status['cluster_name'] or 'None'}")
        print(f"Node ID:      {status['node_id']}")
        print(f"State:        {status['state']}")
        print(f"Role:         {status['role']}")
        print(f"Total Nodes:  {status['nodes']}")
        print(f"Active Nodes: {status['active_nodes']}")
        print(f"Leader:       {status['leader'] or 'None'}")
        
        # Show distributed services status
        if self.dvfs:
            repl_status = self.dvfs.get_replication_status()
            print(f"\nDistributed VFS:")
            print(f"  Total files:       {repl_status['total_files']}")
            print(f"  Fully replicated:  {repl_status['fully_replicated']}")
            print(f"  Under-replicated:  {repl_status['under_replicated']}")
            print(f"  Replication factor: {repl_status['replication_factor']}")
            print(f"  Conflicts:         {repl_status['conflicts']}")
        
        if self.scheduler:
            processes = self.scheduler.list_processes()
            print(f"\nDistributed Processes:")
            print(f"  Total processes: {len(processes)}")
            print(f"  Scheduling policy: {self.scheduler.policy.value}")
    
    def _cluster_nodes(self):
        """List cluster nodes"""
        if not self.cluster_node or self.cluster_node.state.value == 'disconnected':
            print("Not connected to any cluster")
            return
        
        print("\nCluster Nodes")
        print("=" * 60)
        print(f"{'Node ID':<20} {'Address':<15} {'Port':<8} {'State':<12} {'Role':<10}")
        print("-" * 60)
        
        for node_id, node_info in self.cluster_node.nodes.items():
            mark = "*" if node_id == self.cluster_node.node_id else " "
            print(f"{mark}{node_id[:18]:<19} {node_info.address:<15} {node_info.port:<8} "
                  f"{node_info.state.value:<12} {node_info.role.value:<10}")
        
        print("\n* = This node")
    
    def _cluster_leave(self):
        """Leave current cluster"""
        if not self.cluster_node or self.cluster_node.state.value == 'disconnected':
            print("Not connected to any cluster")
            return
        
        cluster_name = self.cluster_node.cluster_name
        print(f"Leaving cluster '{cluster_name}'...")
        
        # Stop distributed services
        if self.dvfs:
            self.dvfs.stop()
        
        if self.scheduler:
            self.scheduler.stop()
        
        # Leave cluster
        self.cluster_node.stop()
        
        print(f"✓ Left cluster '{cluster_name}'")
        
        # Reset components
        self.cluster_node = None
        self.dvfs = None
        self.scheduler = None
    
    def _cluster_exec(self, command):
        """Execute command on cluster"""
        if not command:
            print("Usage: cluster exec <command>")
            return
        
        if not self.scheduler:
            print("Distributed scheduler not initialized")
            return
        
        print(f"Executing on cluster: {command}")
        
        # Parse command
        parts = command.split()
        cmd = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Submit to distributed scheduler
        pid = self.scheduler.submit_process(cmd, args)
        
        print(f"✓ Process submitted with PID: {pid}")
        print("  Use 'cluster ps' to monitor execution")
    
    def _cluster_distribute(self, args):
        """Distribute file across cluster"""
        if not args:
            print("Usage: cluster distribute <file>")
            return
        
        if not self.dvfs:
            print("Distributed VFS not initialized")
            return
        
        filepath = args[0]
        
        # Check if file exists
        if not self.shell.vfs or not self.shell.vfs.exists(filepath):
            print(f"File not found: {filepath}")
            return
        
        print(f"Distributing {filepath} across cluster...")
        
        # Read file
        try:
            with self.shell.vfs.open(filepath, 'rb') as f:
                data = f.read()
        except Exception as e:
            print(f"Failed to read file: {e}")
            return
        
        # Write to distributed VFS
        if self.dvfs.write(filepath, data):
            info = self.dvfs.get_file_info(filepath)
            if info:
                print(f"✓ File distributed successfully")
                print(f"  Size: {info['size']} bytes")
                print(f"  Replicas: {len(info['replicas'])}")
                print(f"  Nodes: {', '.join(info['replicas'][:3])}{'...' if len(info['replicas']) > 3 else ''}")
        else:
            print(f"✗ Failed to distribute file")
    
    def do_ps(self, args):
        """List distributed processes
        Usage: ps [--all]
        """
        if not self.scheduler:
            # Fall back to local ps
            if hasattr(self.shell, 'do_ps'):
                return self.shell.do_ps(args)
            print("Process scheduler not available")
            return
        
        processes = self.scheduler.list_processes()
        
        if not processes:
            print("No distributed processes running")
            return
        
        print("\nDistributed Processes")
        print("=" * 80)
        print(f"{'PID':<10} {'Command':<20} {'State':<12} {'Node':<20} {'CPU%':<8} {'Memory':<10}")
        print("-" * 80)
        
        for proc_info in processes:
            if proc_info:
                pid = proc_info['pid']
                command = proc_info['command'][:18]
                state = proc_info['state']
                node = proc_info['node'][:18] if proc_info['node'] else 'pending'
                cpu = f"{proc_info['cpu_usage']:.1f}%"
                mem = self._format_bytes(proc_info['memory_usage'])
                
                print(f"{pid:<10} {command:<20} {state:<12} {node:<20} {cpu:<8} {mem:<10}")
    
    def do_migrate(self, args):
        """Migrate process to another node
        Usage: migrate <pid> <target_node>
        """
        if not self.scheduler:
            print("Distributed scheduler not available")
            return
        
        parts = args.strip().split()
        if len(parts) < 2:
            print("Usage: migrate <pid> <target_node>")
            return
        
        try:
            pid = int(parts[0])
        except ValueError:
            print(f"Invalid PID: {parts[0]}")
            return
        
        target_node = parts[1]
        
        print(f"Migrating process {pid} to node {target_node}...")
        
        if self.scheduler.migrate_process(pid, target_node):
            print(f"✓ Process {pid} migrated successfully")
        else:
            print(f"✗ Failed to migrate process {pid}")
            print("  Check that the target node exists and is active")
    
    def _format_bytes(self, bytes_val):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}TB"

def register_commands(shell):
    """Register cluster commands with shell"""
    cluster_cmds = ClusterCommands(shell)
    
    # Add commands to shell
    shell.do_cluster = cluster_cmds.do_cluster
    shell.do_ps = cluster_cmds.do_ps
    shell.do_migrate = cluster_cmds.do_migrate
    
    # Store reference
    shell.cluster_commands = cluster_cmds

"""
Node Management for KOS Orchestration

This module implements node management for the KOS orchestration system,
tracking node status, resources, and managing node lifecycle.
"""

import os
import json
import logging
import threading
import time
import uuid
import socket
import platform
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
NODES_PATH = os.path.join(ORCHESTRATION_ROOT, 'nodes')

# Ensure directories exist
os.makedirs(NODES_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)

# Import KADVLayer for system metrics if available
try:
    from kos.core.kadvlayer.system_metrics import SystemMetrics
    KADVLAYER_AVAILABLE = True
except ImportError:
    KADVLAYER_AVAILABLE = False
    logger.warning("KADVLayer not available for advanced system metrics")


class NodeConditionType:
    """Node condition types."""
    READY = "Ready"
    MEMORY_PRESSURE = "MemoryPressure"
    DISK_PRESSURE = "DiskPressure"
    PID_PRESSURE = "PIDPressure"
    NETWORK_UNAVAILABLE = "NetworkUnavailable"


class NodeConditionStatus:
    """Node condition statuses."""
    TRUE = "True"
    FALSE = "False"
    UNKNOWN = "Unknown"


class NodeCondition:
    """Node condition."""
    
    def __init__(self, type: str, status: str, 
                 last_heartbeat_time: Optional[float] = None,
                 last_transition_time: Optional[float] = None,
                 reason: str = "", message: str = ""):
        """
        Initialize a NodeCondition.
        
        Args:
            type: Condition type (e.g., Ready)
            status: Condition status (True, False, Unknown)
            last_heartbeat_time: Last heartbeat time
            last_transition_time: Last transition time
            reason: Reason for the condition
            message: Message explaining the condition
        """
        self.type = type
        self.status = status
        self.last_heartbeat_time = last_heartbeat_time or time.time()
        self.last_transition_time = last_transition_time or time.time()
        self.reason = reason
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "status": self.status,
            "lastHeartbeatTime": self.last_heartbeat_time,
            "lastTransitionTime": self.last_transition_time,
            "reason": self.reason,
            "message": self.message
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeCondition':
        """Create from dictionary."""
        return cls(
            type=data.get("type", ""),
            status=data.get("status", NodeConditionStatus.UNKNOWN),
            last_heartbeat_time=data.get("lastHeartbeatTime"),
            last_transition_time=data.get("lastTransitionTime"),
            reason=data.get("reason", ""),
            message=data.get("message", "")
        )
    
    def update(self, status: str, reason: str = "", message: str = "") -> bool:
        """
        Update the condition.
        
        Args:
            status: New status
            reason: New reason
            message: New message
            
        Returns:
            bool: Whether the status changed
        """
        self.last_heartbeat_time = time.time()
        
        # Check if status changed
        status_changed = self.status != status
        
        if status_changed:
            self.status = status
            self.last_transition_time = time.time()
        
        # Update reason and message
        if reason:
            self.reason = reason
        
        if message:
            self.message = message
        
        return status_changed


class NodeStatus:
    """Node status."""
    
    def __init__(self):
        """Initialize NodeStatus."""
        self.conditions = []
        self.capacity = {}
        self.allocatable = {}
        self.addresses = []
        self.daemon_endpoints = {"kubeletEndpoint": {"Port": 0}}
        self.node_info = {
            "machineID": "",
            "systemUUID": "",
            "bootID": "",
            "kernelVersion": "",
            "osImage": "",
            "containerRuntimeVersion": "",
            "kubeletVersion": "",
            "kubeProxyVersion": "",
            "operatingSystem": "",
            "architecture": ""
        }
        self.images = []
        self.volumes_in_use = []
        self.volumes_attached = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "capacity": self.capacity,
            "allocatable": self.allocatable,
            "addresses": self.addresses,
            "daemonEndpoints": self.daemon_endpoints,
            "nodeInfo": self.node_info,
            "images": self.images,
            "volumesInUse": self.volumes_in_use,
            "volumesAttached": self.volumes_attached
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NodeStatus':
        """Create from dictionary."""
        status = cls()
        
        # Parse conditions
        conditions_data = data.get("conditions", [])
        for condition_data in conditions_data:
            status.conditions.append(NodeCondition.from_dict(condition_data))
        
        # Copy other fields
        status.capacity = data.get("capacity", {})
        status.allocatable = data.get("allocatable", {})
        status.addresses = data.get("addresses", [])
        status.daemon_endpoints = data.get("daemonEndpoints", {"kubeletEndpoint": {"Port": 0}})
        status.node_info = data.get("nodeInfo", {})
        status.images = data.get("images", [])
        status.volumes_in_use = data.get("volumesInUse", [])
        status.volumes_attached = data.get("volumesAttached", [])
        
        return status
    
    def get_condition(self, condition_type: str) -> Optional[NodeCondition]:
        """
        Get a condition by type.
        
        Args:
            condition_type: Condition type
            
        Returns:
            NodeCondition or None if not found
        """
        for condition in self.conditions:
            if condition.type == condition_type:
                return condition
        return None
    
    def set_condition(self, condition: NodeCondition) -> None:
        """
        Set a condition.
        
        Args:
            condition: NodeCondition to set
        """
        for i, existing in enumerate(self.conditions):
            if existing.type == condition.type:
                self.conditions[i] = condition
                return
        
        # Not found, append
        self.conditions.append(condition)


class Node:
    """
    Node in the KOS orchestration system.
    
    A Node is a worker machine in the orchestration system.
    """
    
    def __init__(self, name: str):
        """
        Initialize a Node.
        
        Args:
            name: Node name
        """
        self.name = name
        self.metadata = {
            "name": name,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self.spec = {
            "podCIDR": "",
            "unschedulable": False,
            "taints": []
        }
        self.status = NodeStatus()
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this Node."""
        return os.path.join(NODES_PATH, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the Node from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update spec
            self.spec = data.get("spec", self.spec)
            
            # Update status
            status_data = data.get("status", {})
            self.status = NodeStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Node {self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Node to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        
        try:
            with self._lock:
                data = {
                    "kind": "Node",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec,
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Node {self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Node.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Node {self.name}: {e}")
            return False
    
    def update_status(self) -> bool:
        """
        Update the Node status.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update addresses
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                
                self.status.addresses = [
                    {"type": "Hostname", "address": hostname},
                    {"type": "InternalIP", "address": ip}
                ]
                
                # Update node info
                self.status.node_info = {
                    "machineID": platform.node(),
                    "systemUUID": str(uuid.getnode()),
                    "bootID": str(uuid.uuid4()),
                    "kernelVersion": platform.release(),
                    "osImage": platform.platform(),
                    "containerRuntimeVersion": "kos://1.0.0",
                    "kubeletVersion": "kos://1.0.0",
                    "kubeProxyVersion": "kos://1.0.0",
                    "operatingSystem": platform.system(),
                    "architecture": platform.machine()
                }
                
                # Update capacity and allocatable resources
                if KADVLAYER_AVAILABLE:
                    metrics = SystemMetrics()
                    
                    # Get CPU cores
                    cpu_count = metrics.get_cpu_count()
                    
                    # Get memory
                    memory_info = metrics.get_memory_info()
                    memory_bytes = memory_info.get("total", 0)
                    
                    # Get disk
                    disk_info = metrics.get_disk_info()
                    disk_bytes = disk_info.get("total", 0)
                    
                    # Set capacity
                    self.status.capacity = {
                        "cpu": str(cpu_count),
                        "memory": f"{memory_bytes}",
                        "ephemeral-storage": f"{disk_bytes}",
                        "pods": "110"
                    }
                    
                    # Set allocatable (a bit less than capacity to account for system usage)
                    self.status.allocatable = {
                        "cpu": str(max(1, int(cpu_count * 0.9))),
                        "memory": f"{int(memory_bytes * 0.9)}",
                        "ephemeral-storage": f"{int(disk_bytes * 0.9)}",
                        "pods": "100"
                    }
                else:
                    # Fallback to basic info
                    import psutil
                    
                    # Get CPU cores
                    cpu_count = psutil.cpu_count()
                    
                    # Get memory
                    memory_bytes = psutil.virtual_memory().total
                    
                    # Get disk
                    disk_bytes = psutil.disk_usage('/').total
                    
                    # Set capacity
                    self.status.capacity = {
                        "cpu": str(cpu_count),
                        "memory": f"{memory_bytes}",
                        "ephemeral-storage": f"{disk_bytes}",
                        "pods": "110"
                    }
                    
                    # Set allocatable (a bit less than capacity to account for system usage)
                    self.status.allocatable = {
                        "cpu": str(max(1, int(cpu_count * 0.9))),
                        "memory": f"{int(memory_bytes * 0.9)}",
                        "ephemeral-storage": f"{int(disk_bytes * 0.9)}",
                        "pods": "100"
                    }
                
                # Update conditions
                self._update_conditions()
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to update Node status for {self.name}: {e}")
            return False
    
    def _update_conditions(self) -> None:
        """Update node conditions based on current system state."""
        try:
            import psutil
            
            # Ready condition
            ready_condition = self.status.get_condition(NodeConditionType.READY)
            if not ready_condition:
                ready_condition = NodeCondition(
                    type=NodeConditionType.READY,
                    status=NodeConditionStatus.UNKNOWN
                )
            
            # Set Ready to True if we can get here
            ready_condition.update(
                status=NodeConditionStatus.TRUE,
                reason="KubeletReady",
                message="Node is ready"
            )
            self.status.set_condition(ready_condition)
            
            # Memory pressure
            memory = psutil.virtual_memory()
            memory_pressure = self.status.get_condition(NodeConditionType.MEMORY_PRESSURE)
            if not memory_pressure:
                memory_pressure = NodeCondition(
                    type=NodeConditionType.MEMORY_PRESSURE,
                    status=NodeConditionStatus.UNKNOWN
                )
            
            # Check memory pressure (available memory < 10%)
            if memory.percent > 90:
                memory_pressure.update(
                    status=NodeConditionStatus.TRUE,
                    reason="MemoryPressure",
                    message=f"Memory usage is high: {memory.percent}%"
                )
            else:
                memory_pressure.update(
                    status=NodeConditionStatus.FALSE,
                    reason="KubeletHasSufficientMemory",
                    message="Node has sufficient memory"
                )
            self.status.set_condition(memory_pressure)
            
            # Disk pressure
            disk = psutil.disk_usage('/')
            disk_pressure = self.status.get_condition(NodeConditionType.DISK_PRESSURE)
            if not disk_pressure:
                disk_pressure = NodeCondition(
                    type=NodeConditionType.DISK_PRESSURE,
                    status=NodeConditionStatus.UNKNOWN
                )
            
            # Check disk pressure (available disk < 10%)
            if disk.percent > 90:
                disk_pressure.update(
                    status=NodeConditionStatus.TRUE,
                    reason="DiskPressure",
                    message=f"Disk usage is high: {disk.percent}%"
                )
            else:
                disk_pressure.update(
                    status=NodeConditionStatus.FALSE,
                    reason="KubeletHasNoDiskPressure",
                    message="Node has sufficient disk space"
                )
            self.status.set_condition(disk_pressure)
            
            # PID pressure
            pid_pressure = self.status.get_condition(NodeConditionType.PID_PRESSURE)
            if not pid_pressure:
                pid_pressure = NodeCondition(
                    type=NodeConditionType.PID_PRESSURE,
                    status=NodeConditionStatus.UNKNOWN
                )
            
            # Check PID pressure (hard to do accurately, assume False)
            pid_pressure.update(
                status=NodeConditionStatus.FALSE,
                reason="KubeletHasSufficientPIDs",
                message="Node has sufficient PIDs"
            )
            self.status.set_condition(pid_pressure)
            
            # Network unavailable
            network_unavailable = self.status.get_condition(NodeConditionType.NETWORK_UNAVAILABLE)
            if not network_unavailable:
                network_unavailable = NodeCondition(
                    type=NodeConditionType.NETWORK_UNAVAILABLE,
                    status=NodeConditionStatus.UNKNOWN
                )
            
            # Check network (assume available if we can get hostname)
            try:
                socket.gethostbyname(socket.gethostname())
                network_unavailable.update(
                    status=NodeConditionStatus.FALSE,
                    reason="NetworkReady",
                    message="Network is ready"
                )
            except Exception:
                network_unavailable.update(
                    status=NodeConditionStatus.TRUE,
                    reason="NetworkNotReady",
                    message="Network is not ready"
                )
            self.status.set_condition(network_unavailable)
        except Exception as e:
            logger.error(f"Failed to update Node conditions for {self.name}: {e}")
    
    @staticmethod
    def list_nodes() -> List['Node']:
        """
        List all Nodes.
        
        Returns:
            List of Nodes
        """
        nodes = []
        
        try:
            if os.path.exists(NODES_PATH):
                for filename in os.listdir(NODES_PATH):
                    if not filename.endswith('.json'):
                        continue
                    
                    node_name = filename[:-5]  # Remove .json extension
                    node = Node(node_name)
                    nodes.append(node)
        except Exception as e:
            logger.error(f"Failed to list Nodes: {e}")
        
        return nodes
    
    @staticmethod
    def get_node(name: str) -> Optional['Node']:
        """
        Get a Node by name.
        
        Args:
            name: Node name
            
        Returns:
            Node object or None if not found
        """
        node = Node(name)
        
        if os.path.exists(node._file_path()):
            return node
        
        return None


class NodeManager:
    """
    Node manager for the KOS orchestration system.
    
    This class provides methods to manage nodes.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(NodeManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the node manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._nodes = {}
        self._heartbeat_thread = None
        self._stop_event = threading.Event()
        
        # Create/update local node
        self._init_local_node()
        
        # Start heartbeat thread
        self._start_heartbeat()
    
    def _init_local_node(self) -> None:
        """Initialize the local node."""
        try:
            hostname = socket.gethostname()
            local_node = Node(hostname)
            
            # Set node as schedulable
            local_node.spec["unschedulable"] = False
            
            # Update status
            local_node.update_status()
            
            # Add to nodes dict
            self._nodes[hostname] = local_node
        except Exception as e:
            logger.error(f"Failed to initialize local node: {e}")
    
    def _start_heartbeat(self) -> None:
        """Start the heartbeat thread."""
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()
    
    def _heartbeat_loop(self) -> None:
        """Heartbeat loop for updating node status."""
        while not self._stop_event.is_set():
            try:
                self._update_nodes()
            except Exception as e:
                logger.error(f"Error in node heartbeat loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(60)  # Heartbeat once per minute
    
    def _update_nodes(self) -> None:
        """Update all nodes."""
        try:
            # Update local node
            hostname = socket.gethostname()
            if hostname in self._nodes:
                self._nodes[hostname].update_status()
            
            # TODO: Check remote nodes (if any)
        except Exception as e:
            logger.error(f"Failed to update nodes: {e}")
    
    def register_node(self, node: Node) -> bool:
        """
        Register a node.
        
        Args:
            node: Node to register
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Add to nodes dict
                self._nodes[node.name] = node
                
                # Save to disk
                return node.save()
        except Exception as e:
            logger.error(f"Failed to register Node {node.name}: {e}")
            return False
    
    def unregister_node(self, name: str) -> bool:
        """
        Unregister a node.
        
        Args:
            name: Node name
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Remove from nodes dict
                if name in self._nodes:
                    node = self._nodes.pop(name)
                    
                    # Delete from disk
                    return node.delete()
                
                return False
        except Exception as e:
            logger.error(f"Failed to unregister Node {name}: {e}")
            return False
    
    def get_node(self, name: str) -> Optional[Node]:
        """
        Get a node by name.
        
        Args:
            name: Node name
            
        Returns:
            Node object or None if not found
        """
        with self._lock:
            # Check in-memory cache
            if name in self._nodes:
                return self._nodes[name]
            
            # Load from disk
            node = Node.get_node(name)
            if node:
                self._nodes[name] = node
            
            return node
    
    def list_nodes(self) -> List[Node]:
        """
        List all nodes.
        
        Returns:
            List of Nodes
        """
        with self._lock:
            # Get from in-memory cache
            return list(self._nodes.values())
    
    def stop(self) -> None:
        """Stop the node manager."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            self._stop_event.set()
            self._heartbeat_thread.join(timeout=5)
    
    @staticmethod
    def instance() -> 'NodeManager':
        """
        Get the singleton instance.
        
        Returns:
            NodeManager instance
        """
        return NodeManager()


def get_node(name: str) -> Optional[Node]:
    """
    Get a node by name.
    
    Args:
        name: Node name
        
    Returns:
        Node object or None if not found
    """
    manager = NodeManager.instance()
    return manager.get_node(name)


def list_nodes() -> List[Node]:
    """
    List all nodes.
    
    Returns:
        List of Nodes
    """
    manager = NodeManager.instance()
    return manager.list_nodes()


def register_node(node: Node) -> bool:
    """
    Register a node.
    
    Args:
        node: Node to register
        
    Returns:
        bool: Success or failure
    """
    manager = NodeManager.instance()
    return manager.register_node(node)


def unregister_node(name: str) -> bool:
    """
    Unregister a node.
    
    Args:
        name: Node name
        
    Returns:
        bool: Success or failure
    """
    manager = NodeManager.instance()
    return manager.unregister_node(name)

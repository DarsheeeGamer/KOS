"""
Scheduler for KOS Container Orchestration

This module implements a Kubernetes-like scheduler for the KOS container orchestration system,
responsible for assigning pods to nodes based on resource requirements, affinity rules,
and other constraints.
"""

import os
import json
import time
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

from .pod import Pod, PodSpec, PodStatus, PodPhase

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
NODES_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration/nodes')
SCHEDULER_CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/kos/orchestration/scheduler.json')

# Ensure directories exist
os.makedirs(NODES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SCHEDULER_CONFIG_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class SchedulerPolicy(str, Enum):
    """Scheduling policy types."""
    ROUND_ROBIN = "RoundRobin"
    BINPACK = "BinPack"
    SPREAD = "Spread"
    RANDOM = "Random"
    CUSTOM = "Custom"


class NodeStatus:
    """Status information for a node in the cluster."""
    
    def __init__(self, name: str, address: str, 
                 capacity: Dict[str, Any] = None,
                 allocatable: Dict[str, Any] = None,
                 conditions: List[Dict[str, Any]] = None,
                 labels: Dict[str, str] = None,
                 taints: List[Dict[str, Any]] = None):
        """
        Initialize node status.
        
        Args:
            name: Node name
            address: Node address
            capacity: Total resource capacity
            allocatable: Allocatable resources
            conditions: Node conditions
            labels: Node labels
            taints: Node taints
        """
        self.name = name
        self.address = address
        self.capacity = capacity or {
            "cpu": "1",
            "memory": "1Gi",
            "pods": "10"
        }
        self.allocatable = allocatable or self.capacity.copy()
        self.conditions = conditions or [
            {
                "type": "Ready",
                "status": "True",
                "lastHeartbeatTime": time.time(),
                "lastTransitionTime": time.time(),
                "reason": "KubeletReady",
                "message": "kubelet is ready."
            }
        ]
        self.labels = labels or {}
        self.taints = taints or []
        self.pods = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the node status to a dictionary.
        
        Returns:
            Dict representation of the node status
        """
        return {
            "name": self.name,
            "address": self.address,
            "capacity": self.capacity,
            "allocatable": self.allocatable,
            "conditions": self.conditions,
            "labels": self.labels,
            "taints": self.taints,
            "pods": self.pods
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'NodeStatus':
        """
        Create a node status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            NodeStatus object
        """
        return NodeStatus(
            name=data.get("name", ""),
            address=data.get("address", ""),
            capacity=data.get("capacity", {}),
            allocatable=data.get("allocatable", {}),
            conditions=data.get("conditions", []),
            labels=data.get("labels", {}),
            taints=data.get("taints", [])
        )
    
    def save(self) -> bool:
        """
        Save the node status to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            node_file = os.path.join(NODES_DIR, f"{self.name}.json")
            with open(node_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved node status for {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save node status for {self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str) -> Optional['NodeStatus']:
        """
        Load a node status from disk.
        
        Args:
            name: Node name
            
        Returns:
            NodeStatus object or None if not found
        """
        node_file = os.path.join(NODES_DIR, f"{name}.json")
        if not os.path.exists(node_file):
            return None
        
        try:
            with open(node_file, 'r') as f:
                data = json.load(f)
            
            return NodeStatus.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load node status for {name}: {e}")
            return None


class Scheduler:
    """
    Container scheduler for KOS orchestration.
    
    The scheduler is responsible for assigning pods to nodes based on
    resource requirements, affinity rules, and other constraints.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Scheduler, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the scheduler."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = self._load_config()
        self._stop_event = threading.Event()
        self._scheduler_thread = None
    
    def _load_config(self) -> Dict[str, Any]:
        """Load scheduler configuration from disk."""
        if os.path.exists(SCHEDULER_CONFIG_PATH):
            try:
                with open(SCHEDULER_CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load scheduler config: {e}")
        
        # Default configuration
        default_config = {
            "policy": SchedulerPolicy.SPREAD.value,
            "interval": 10,  # seconds
            "enabled": True
        }
        
        # Save default configuration
        try:
            os.makedirs(os.path.dirname(SCHEDULER_CONFIG_PATH), exist_ok=True)
            with open(SCHEDULER_CONFIG_PATH, 'w') as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save default scheduler config: {e}")
        
        return default_config
    
    def _save_config(self) -> bool:
        """
        Save scheduler configuration to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with open(SCHEDULER_CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info("Saved scheduler configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to save scheduler configuration: {e}")
            return False
    
    def start(self):
        """Start the scheduler."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Scheduler is already running")
            return
        
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._run, daemon=True)
        self._scheduler_thread.start()
        logger.info("Started scheduler")
    
    def stop(self):
        """Stop the scheduler."""
        if not self._scheduler_thread or not self._scheduler_thread.is_alive():
            logger.warning("Scheduler is not running")
            return
        
        self._stop_event.set()
        self._scheduler_thread.join(timeout=5)
        logger.info("Stopped scheduler")
    
    def _run(self):
        """Main scheduler loop."""
        while not self._stop_event.is_set():
            if self.config.get("enabled", True):
                try:
                    self._schedule_pending_pods()
                except Exception as e:
                    logger.error(f"Error in scheduler: {e}")
            
            # Wait for next scheduling interval
            interval = self.config.get("interval", 10)
            self._stop_event.wait(interval)
    
    def _schedule_pending_pods(self):
        """Schedule all pending pods."""
        # Get pending pods
        pending_pods = []
        for pod in Pod.list_pods():
            if pod.status.phase == PodPhase.PENDING and not pod.status.host_ip:
                pending_pods.append(pod)
        
        if not pending_pods:
            return
        
        # Get available nodes
        nodes = self._list_nodes()
        if not nodes:
            logger.warning("No nodes available for scheduling")
            return
        
        # Sort pending pods by creation timestamp (oldest first)
        pending_pods.sort(key=lambda p: p.creation_timestamp)
        
        # Schedule each pod
        for pod in pending_pods:
            self._schedule_pod(pod, nodes)
    
    def _schedule_pod(self, pod: Pod, nodes: List[NodeStatus]) -> bool:
        """
        Schedule a pod on a suitable node.
        
        Args:
            pod: Pod to schedule
            nodes: List of available nodes
            
        Returns:
            bool: Whether the pod was scheduled
        """
        logger.info(f"Scheduling pod {pod.namespace}/{pod.name}")
        
        # Filter nodes based on node selector
        filtered_nodes = self._filter_nodes(pod, nodes)
        if not filtered_nodes:
            logger.warning(f"No suitable nodes found for pod {pod.namespace}/{pod.name}")
            
            # Update pod status
            pod.status.phase = PodPhase.PENDING
            pod.status.reason = "FailedScheduling"
            pod.status.message = "No suitable nodes available"
            pod.save()
            return False
        
        # Prioritize nodes based on scheduling policy
        prioritized_nodes = self._prioritize_nodes(pod, filtered_nodes)
        
        # Select the best node
        selected_node = prioritized_nodes[0]
        
        # Assign pod to node
        pod.status.host_ip = selected_node.address
        pod.save()
        
        # Update node status
        selected_node.pods.append(f"{pod.namespace}/{pod.name}")
        selected_node.save()
        
        logger.info(f"Scheduled pod {pod.namespace}/{pod.name} on node {selected_node.name}")
        return True
    
    def _filter_nodes(self, pod: Pod, nodes: List[NodeStatus]) -> List[NodeStatus]:
        """
        Filter nodes based on pod requirements.
        
        Args:
            pod: Pod to schedule
            nodes: List of available nodes
            
        Returns:
            List of suitable nodes
        """
        filtered_nodes = []
        
        for node in nodes:
            # Check node selector
            if pod.spec.node_selector:
                matches = True
                for key, value in pod.spec.node_selector.items():
                    if node.labels.get(key) != value:
                        matches = False
                        break
                
                if not matches:
                    continue
            
            # Check node conditions
            ready = False
            for condition in node.conditions:
                if condition.get("type") == "Ready" and condition.get("status") == "True":
                    ready = True
                    break
            
            if not ready:
                continue
            
            # Check taints and tolerations
            if node.taints and not self._pod_tolerates_taints(pod, node.taints):
                continue
            
            # Check resource capacity
            if not self._node_has_capacity(pod, node):
                continue
            
            filtered_nodes.append(node)
        
        return filtered_nodes
    
    def _pod_tolerates_taints(self, pod: Pod, taints: List[Dict[str, Any]]) -> bool:
        """
        Check if a pod tolerates node taints.
        
        Args:
            pod: Pod to check
            taints: List of node taints
            
        Returns:
            bool: Whether the pod tolerates all taints
        """
        # Get pod tolerations
        tolerations = pod.spec.to_dict().get("tolerations", [])
        
        for taint in taints:
            taint_key = taint.get("key", "")
            taint_value = taint.get("value", "")
            taint_effect = taint.get("effect", "NoSchedule")
            
            tolerated = False
            for toleration in tolerations:
                toleration_key = toleration.get("key", "")
                toleration_value = toleration.get("value", "")
                toleration_effect = toleration.get("effect", "")
                toleration_operator = toleration.get("operator", "Equal")
                
                # Check if toleration matches taint
                if toleration_key == taint_key or toleration_key == "":
                    if toleration_effect == "" or toleration_effect == taint_effect:
                        if toleration_operator == "Exists":
                            tolerated = True
                            break
                        elif toleration_operator == "Equal" and toleration_value == taint_value:
                            tolerated = True
                            break
            
            if not tolerated and taint_effect == "NoSchedule":
                return False
        
        return True
    
    def _node_has_capacity(self, pod: Pod, node: NodeStatus) -> bool:
        """
        Check if a node has enough capacity for a pod.
        
        Args:
            pod: Pod to check
            node: Node to check
            
        Returns:
            bool: Whether the node has enough capacity
        """
        # Get pod resource requirements
        pod_resources = self._calculate_pod_resources(pod)
        
        # Get node available resources
        node_available = node.allocatable.copy()
        
        # Subtract resources used by existing pods
        for pod_name in node.pods:
            existing_pod_namespace, existing_pod_name = pod_name.split('/')
            existing_pod = Pod.load(existing_pod_name, existing_pod_namespace)
            if existing_pod:
                existing_resources = self._calculate_pod_resources(existing_pod)
                for resource, value in existing_resources.items():
                    if resource in node_available:
                        node_available[resource] = self._subtract_resource(
                            node_available[resource], value
                        )
        
        # Check if node has enough resources
        for resource, value in pod_resources.items():
            if resource not in node_available:
                continue
            
            if not self._has_enough_resource(node_available[resource], value):
                return False
        
        return True
    
    def _calculate_pod_resources(self, pod: Pod) -> Dict[str, Any]:
        """
        Calculate total resource requirements for a pod.
        
        Args:
            pod: Pod to calculate resources for
            
        Returns:
            Dict of resource requirements
        """
        resources = {
            "cpu": "0",
            "memory": "0",
            "pods": "1"
        }
        
        for container_spec in pod.spec.containers:
            container_resources = container_spec.get("resources", {})
            requests = container_resources.get("requests", {})
            
            for resource, value in requests.items():
                if resource in resources:
                    resources[resource] = self._add_resource(resources[resource], value)
        
        return resources
    
    def _add_resource(self, a: str, b: str) -> str:
        """
        Add two resource values.
        
        Args:
            a: First resource value
            b: Second resource value
            
        Returns:
            Sum of the resource values
        """
        # For simplicity, just handle CPU and memory as numeric values
        # In a real implementation, this would handle units like "100m" or "1Gi"
        try:
            return str(float(a) + float(b))
        except ValueError:
            return a
    
    def _subtract_resource(self, a: str, b: str) -> str:
        """
        Subtract one resource value from another.
        
        Args:
            a: Resource value to subtract from
            b: Resource value to subtract
            
        Returns:
            Result of the subtraction
        """
        try:
            result = max(0, float(a) - float(b))
            return str(result)
        except ValueError:
            return a
    
    def _has_enough_resource(self, available: str, required: str) -> bool:
        """
        Check if there's enough of a resource available.
        
        Args:
            available: Available resource amount
            required: Required resource amount
            
        Returns:
            bool: Whether there's enough resource
        """
        try:
            return float(available) >= float(required)
        except ValueError:
            return False
    
    def _prioritize_nodes(self, pod: Pod, nodes: List[NodeStatus]) -> List[NodeStatus]:
        """
        Prioritize nodes based on scheduling policy.
        
        Args:
            pod: Pod to schedule
            nodes: List of suitable nodes
            
        Returns:
            List of nodes in priority order
        """
        policy = self.config.get("policy", SchedulerPolicy.SPREAD.value)
        
        if policy == SchedulerPolicy.ROUND_ROBIN.value:
            # Round-robin: use node with least recent pod
            nodes.sort(key=lambda n: len(n.pods))
        elif policy == SchedulerPolicy.BINPACK.value:
            # Bin-packing: use node with most pods first
            nodes.sort(key=lambda n: len(n.pods), reverse=True)
        elif policy == SchedulerPolicy.SPREAD.value:
            # Spread: distribute pods evenly
            nodes.sort(key=lambda n: len(n.pods))
        elif policy == SchedulerPolicy.RANDOM.value:
            # Random: shuffle nodes
            import random
            random.shuffle(nodes)
        elif policy == SchedulerPolicy.CUSTOM.value:
            # Custom: use scoring function
            nodes.sort(key=lambda n: self._score_node(pod, n), reverse=True)
        
        return nodes
    
    def _score_node(self, pod: Pod, node: NodeStatus) -> float:
        """
        Calculate a score for a node based on custom criteria.
        
        Args:
            pod: Pod to schedule
            node: Node to score
            
        Returns:
            float: Node score (higher is better)
        """
        score = 0.0
        
        # Factor 1: Available resources (higher is better)
        pod_resources = self._calculate_pod_resources(pod)
        for resource, required in pod_resources.items():
            if resource in node.allocatable:
                available = node.allocatable[resource]
                try:
                    ratio = float(available) / float(required)
                    score += min(ratio, 10.0)  # Cap at 10
                except (ValueError, ZeroDivisionError):
                    pass
        
        # Factor 2: Number of pods (lower is better)
        pod_count = len(node.pods)
        score -= pod_count * 0.1
        
        # Factor 3: Label match (higher is better)
        for key, value in pod.labels.items():
            if node.labels.get(key) == value:
                score += 1.0
        
        return score
    
    def _list_nodes(self) -> List[NodeStatus]:
        """
        Get a list of all nodes.
        
        Returns:
            List of node statuses
        """
        nodes = []
        
        if not os.path.exists(NODES_DIR):
            return nodes
        
        for filename in os.listdir(NODES_DIR):
            if not filename.endswith('.json'):
                continue
            
            node_file = os.path.join(NODES_DIR, filename)
            try:
                with open(node_file, 'r') as f:
                    data = json.load(f)
                
                nodes.append(NodeStatus.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load node from {node_file}: {e}")
        
        return nodes
    
    def register_node(self, name: str, address: str, 
                     capacity: Dict[str, Any] = None,
                     labels: Dict[str, str] = None) -> bool:
        """
        Register a new node or update an existing one.
        
        Args:
            name: Node name
            address: Node address
            capacity: Node resource capacity
            labels: Node labels
            
        Returns:
            bool: Success or failure
        """
        try:
            # Check if node already exists
            existing_node = NodeStatus.load(name)
            if existing_node:
                # Update existing node
                existing_node.address = address
                if capacity:
                    existing_node.capacity = capacity
                    existing_node.allocatable = capacity.copy()
                if labels:
                    existing_node.labels.update(labels)
                
                # Update "Ready" condition
                for condition in existing_node.conditions:
                    if condition.get("type") == "Ready":
                        condition["status"] = "True"
                        condition["lastHeartbeatTime"] = time.time()
                        condition["lastTransitionTime"] = time.time()
                        condition["reason"] = "KubeletReady"
                        condition["message"] = "kubelet is ready."
                        break
                
                return existing_node.save()
            
            # Create new node
            node = NodeStatus(
                name=name,
                address=address,
                capacity=capacity,
                labels=labels
            )
            
            return node.save()
        except Exception as e:
            logger.error(f"Failed to register node {name}: {e}")
            return False
    
    def unregister_node(self, name: str) -> bool:
        """
        Unregister a node.
        
        Args:
            name: Node name
            
        Returns:
            bool: Success or failure
        """
        node_file = os.path.join(NODES_DIR, f"{name}.json")
        if not os.path.exists(node_file):
            logger.warning(f"Node not found: {name}")
            return False
        
        try:
            os.remove(node_file)
            logger.info(f"Unregistered node {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister node {name}: {e}")
            return False
    
    def set_policy(self, policy: SchedulerPolicy) -> bool:
        """
        Set the scheduling policy.
        
        Args:
            policy: New scheduling policy
            
        Returns:
            bool: Success or failure
        """
        try:
            self.config["policy"] = policy.value if isinstance(policy, SchedulerPolicy) else policy
            return self._save_config()
        except Exception as e:
            logger.error(f"Failed to set scheduling policy: {e}")
            return False
    
    def set_interval(self, interval: int) -> bool:
        """
        Set the scheduling interval.
        
        Args:
            interval: New interval in seconds
            
        Returns:
            bool: Success or failure
        """
        try:
            self.config["interval"] = max(1, interval)
            return self._save_config()
        except Exception as e:
            logger.error(f"Failed to set scheduling interval: {e}")
            return False
    
    def enable(self) -> bool:
        """
        Enable the scheduler.
        
        Returns:
            bool: Success or failure
        """
        try:
            self.config["enabled"] = True
            return self._save_config()
        except Exception as e:
            logger.error(f"Failed to enable scheduler: {e}")
            return False
    
    def disable(self) -> bool:
        """
        Disable the scheduler.
        
        Returns:
            bool: Success or failure
        """
        try:
            self.config["enabled"] = False
            return self._save_config()
        except Exception as e:
            logger.error(f"Failed to disable scheduler: {e}")
            return False

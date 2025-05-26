"""
Pod Management for KOS Orchestration

This module implements the Pod concept, which is the basic deployment unit
in the KOS container orchestration system (similar to Kubernetes pods).

A Pod represents a group of containers that share storage and network namespace,
and are scheduled together on the same host.
"""

import os
import uuid
import json
import time
import logging
from enum import Enum
from typing import Dict, List, Set, Optional, Union, Any

# Import core modules
from ..container import Container
from ..container.network import ContainerNetwork
from ..container.storage import StorageManager

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
PODS_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration/pods')

# Ensure directories exist
os.makedirs(PODS_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class PodPhase(str, Enum):
    """Pod lifecycle phases."""
    PENDING = "Pending"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    UNKNOWN = "Unknown"


class ContainerState(str, Enum):
    """Container states within a pod."""
    WAITING = "Waiting"
    RUNNING = "Running"
    TERMINATED = "Terminated"


class RestartPolicy(str, Enum):
    """Pod restart policies."""
    ALWAYS = "Always"
    ON_FAILURE = "OnFailure"
    NEVER = "Never"


class PodSpec:
    """
    Specification for a Pod, defining its desired state.
    
    This is similar to the Kubernetes PodSpec.
    """
    
    def __init__(self, containers: List[Dict[str, Any]],
                 volumes: Optional[List[Dict[str, Any]]] = None,
                 restart_policy: RestartPolicy = RestartPolicy.ALWAYS,
                 hostname: Optional[str] = None,
                 node_selector: Optional[Dict[str, str]] = None,
                 security_context: Optional[Dict[str, Any]] = None):
        """
        Initialize a pod specification.
        
        Args:
            containers: List of container specs
            volumes: List of volume specs
            restart_policy: Pod restart policy
            hostname: Pod hostname
            node_selector: Node selection constraints
            security_context: Pod security context
        """
        self.containers = containers
        self.volumes = volumes or []
        self.restart_policy = restart_policy
        self.hostname = hostname
        self.node_selector = node_selector or {}
        self.security_context = security_context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the pod spec to a dictionary.
        
        Returns:
            Dict representation of the pod spec
        """
        return {
            "containers": self.containers,
            "volumes": self.volumes,
            "restart_policy": self.restart_policy,
            "hostname": self.hostname,
            "node_selector": self.node_selector,
            "security_context": self.security_context
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PodSpec':
        """
        Create a pod spec from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PodSpec object
        """
        return PodSpec(
            containers=data.get("containers", []),
            volumes=data.get("volumes", []),
            restart_policy=data.get("restart_policy", RestartPolicy.ALWAYS),
            hostname=data.get("hostname"),
            node_selector=data.get("node_selector", {}),
            security_context=data.get("security_context", {})
        )


class ContainerStatus:
    """Status information for a container within a pod."""
    
    def __init__(self, name: str, container_id: Optional[str] = None,
                 image: Optional[str] = None, state: ContainerState = ContainerState.WAITING,
                 ready: bool = False, restart_count: int = 0,
                 started: bool = False, exit_code: Optional[int] = None,
                 reason: Optional[str] = None, message: Optional[str] = None,
                 last_state: Optional[Dict[str, Any]] = None):
        """
        Initialize container status.
        
        Args:
            name: Container name
            container_id: Container ID (if created)
            image: Container image
            state: Current container state
            ready: Whether the container is ready
            restart_count: Number of restarts
            started: Whether the container has started
            exit_code: Exit code (if terminated)
            reason: Reason for current state
            message: Human-readable message
            last_state: Previous container state
        """
        self.name = name
        self.container_id = container_id
        self.image = image
        self.state = state
        self.ready = ready
        self.restart_count = restart_count
        self.started = started
        self.exit_code = exit_code
        self.reason = reason
        self.message = message
        self.last_state = last_state or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the container status to a dictionary.
        
        Returns:
            Dict representation of the container status
        """
        return {
            "name": self.name,
            "container_id": self.container_id,
            "image": self.image,
            "state": self.state,
            "ready": self.ready,
            "restart_count": self.restart_count,
            "started": self.started,
            "exit_code": self.exit_code,
            "reason": self.reason,
            "message": self.message,
            "last_state": self.last_state
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ContainerStatus':
        """
        Create a container status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ContainerStatus object
        """
        return ContainerStatus(
            name=data.get("name", ""),
            container_id=data.get("container_id"),
            image=data.get("image"),
            state=data.get("state", ContainerState.WAITING),
            ready=data.get("ready", False),
            restart_count=data.get("restart_count", 0),
            started=data.get("started", False),
            exit_code=data.get("exit_code"),
            reason=data.get("reason"),
            message=data.get("message"),
            last_state=data.get("last_state", {})
        )


class PodStatus:
    """Status information for a pod."""
    
    def __init__(self, phase: PodPhase = PodPhase.PENDING,
                 container_statuses: Optional[List[ContainerStatus]] = None,
                 host_ip: Optional[str] = None, pod_ip: Optional[str] = None,
                 start_time: Optional[float] = None, conditions: Optional[List[Dict[str, Any]]] = None,
                 reason: Optional[str] = None, message: Optional[str] = None):
        """
        Initialize pod status.
        
        Args:
            phase: Current pod phase
            container_statuses: List of container statuses
            host_ip: IP address of the host
            pod_ip: IP address of the pod
            start_time: Pod start time (Unix timestamp)
            conditions: List of pod conditions
            reason: Reason for current phase
            message: Human-readable message
        """
        self.phase = phase
        self.container_statuses = container_statuses or []
        self.host_ip = host_ip
        self.pod_ip = pod_ip
        self.start_time = start_time
        self.conditions = conditions or []
        self.reason = reason
        self.message = message
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the pod status to a dictionary.
        
        Returns:
            Dict representation of the pod status
        """
        return {
            "phase": self.phase,
            "container_statuses": [cs.to_dict() for cs in self.container_statuses],
            "host_ip": self.host_ip,
            "pod_ip": self.pod_ip,
            "start_time": self.start_time,
            "conditions": self.conditions,
            "reason": self.reason,
            "message": self.message
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PodStatus':
        """
        Create a pod status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PodStatus object
        """
        container_statuses = [
            ContainerStatus.from_dict(cs) 
            for cs in data.get("container_statuses", [])
        ]
        
        return PodStatus(
            phase=data.get("phase", PodPhase.PENDING),
            container_statuses=container_statuses,
            host_ip=data.get("host_ip"),
            pod_ip=data.get("pod_ip"),
            start_time=data.get("start_time"),
            conditions=data.get("conditions", []),
            reason=data.get("reason"),
            message=data.get("message")
        )


class Pod:
    """
    Represents a pod in the KOS orchestration system.
    
    A pod is a group of containers that share storage and network,
    and are scheduled together on the same host.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[PodSpec] = None, 
                 status: Optional[PodStatus] = None,
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 owner_reference: Optional[Dict[str, Any]] = None,
                 uid: Optional[str] = None):
        """
        Initialize a pod.
        
        Args:
            name: Pod name
            namespace: Namespace
            spec: Pod specification
            status: Pod status
            labels: Pod labels
            annotations: Pod annotations
            owner_reference: Owner reference (for garbage collection)
            uid: Unique ID
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or PodSpec([])
        self.status = status or PodStatus()
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.owner_reference = owner_reference
        self.uid = uid or str(uuid.uuid4())
        self.creation_timestamp = time.time()
        
        # Runtime-specific fields (not serialized)
        self._containers = {}  # container_name -> Container object
        self._network = None  # Shared network namespace
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the pod to a dictionary.
        
        Returns:
            Dict representation of the pod
        """
        return {
            "kind": "Pod",
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "labels": self.labels,
                "annotations": self.annotations,
                "ownerReference": self.owner_reference
            },
            "spec": self.spec.to_dict(),
            "status": self.status.to_dict()
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Pod':
        """
        Create a pod from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Pod object
        """
        metadata = data.get("metadata", {})
        
        return Pod(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            spec=PodSpec.from_dict(data.get("spec", {})),
            status=PodStatus.from_dict(data.get("status", {})),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            owner_reference=metadata.get("ownerReference"),
            uid=metadata.get("uid", str(uuid.uuid4()))
        )
    
    def save(self) -> bool:
        """
        Save the pod state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            namespace_dir = os.path.join(PODS_DIR, self.namespace)
            os.makedirs(namespace_dir, exist_ok=True)
            
            pod_file = os.path.join(namespace_dir, f"{self.name}.json")
            with open(pod_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved pod {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save pod {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str, namespace: str = "default") -> Optional['Pod']:
        """
        Load a pod from disk.
        
        Args:
            name: Pod name
            namespace: Namespace
            
        Returns:
            Pod object or None if not found
        """
        pod_file = os.path.join(PODS_DIR, namespace, f"{name}.json")
        if not os.path.exists(pod_file):
            logger.error(f"Pod not found: {namespace}/{name}")
            return None
        
        try:
            with open(pod_file, 'r') as f:
                data = json.load(f)
            
            return Pod.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load pod {namespace}/{name}: {e}")
            return None
    
    @staticmethod
    def list_pods(namespace: Optional[str] = None) -> List['Pod']:
        """
        List pods.
        
        Args:
            namespace: Namespace to list pods from, or None for all namespaces
            
        Returns:
            List of Pod objects
        """
        pods = []
        
        if namespace:
            # List pods in a specific namespace
            namespace_dir = os.path.join(PODS_DIR, namespace)
            if not os.path.exists(namespace_dir):
                return []
            
            namespaces = [namespace]
        else:
            # List pods in all namespaces
            if not os.path.exists(PODS_DIR):
                return []
            
            namespaces = os.listdir(PODS_DIR)
        
        for ns in namespaces:
            namespace_dir = os.path.join(PODS_DIR, ns)
            if not os.path.isdir(namespace_dir):
                continue
            
            for filename in os.listdir(namespace_dir):
                if not filename.endswith('.json'):
                    continue
                
                pod_file = os.path.join(namespace_dir, filename)
                try:
                    with open(pod_file, 'r') as f:
                        data = json.load(f)
                    
                    pods.append(Pod.from_dict(data))
                except Exception as e:
                    logger.error(f"Failed to load pod from {pod_file}: {e}")
        
        return pods
    
    def delete(self) -> bool:
        """
        Delete the pod from disk.
        
        Returns:
            bool: Success or failure
        """
        pod_file = os.path.join(PODS_DIR, self.namespace, f"{self.name}.json")
        if not os.path.exists(pod_file):
            logger.warning(f"Pod not found for deletion: {self.namespace}/{self.name}")
            return False
        
        try:
            os.remove(pod_file)
            logger.info(f"Deleted pod {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete pod {self.namespace}/{self.name}: {e}")
            return False
    
    def create(self) -> bool:
        """
        Create the pod's resources.
        
        This sets up the shared network namespace and prepares
        container configurations, but doesn't start containers.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Update status
            self.status.phase = PodPhase.PENDING
            self.status.reason = "Creating"
            self.status.message = "Creating pod resources"
            self.save()
            
            # Create shared network namespace
            network = ContainerNetwork()
            network_name = f"pod-{self.namespace}-{self.name}"
            network.create_network(network_name)
            self._network = network
            
            # Initialize container statuses
            self.status.container_statuses = []
            for container_spec in self.spec.containers:
                container_name = container_spec.get("name")
                if not container_name:
                    logger.error(f"Container spec missing name in pod {self.namespace}/{self.name}")
                    continue
                
                container_status = ContainerStatus(
                    name=container_name,
                    image=container_spec.get("image"),
                    state=ContainerState.WAITING,
                    reason="ContainerCreating",
                    message="Creating container"
                )
                self.status.container_statuses.append(container_status)
            
            self.save()
            logger.info(f"Created pod {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create pod {self.namespace}/{self.name}: {e}")
            self.status.phase = PodPhase.FAILED
            self.status.reason = "FailedCreate"
            self.status.message = f"Failed to create pod: {str(e)}"
            self.save()
            return False
    
    def start(self) -> bool:
        """
        Start the pod's containers.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Update status
            self.status.phase = PodPhase.PENDING
            self.status.reason = "Starting"
            self.status.message = "Starting pod containers"
            self.status.start_time = time.time()
            self.save()
            
            # Start each container
            for container_spec in self.spec.containers:
                container_name = container_spec.get("name")
                if not container_name:
                    logger.error(f"Container spec missing name in pod {self.namespace}/{self.name}")
                    continue
                
                image = container_spec.get("image")
                if not image:
                    logger.error(f"Container spec missing image in pod {self.namespace}/{self.name}")
                    continue
                
                # Create container
                container = Container(
                    name=f"{self.namespace}-{self.name}-{container_name}",
                    image=image,
                    command=container_spec.get("command"),
                    args=container_spec.get("args"),
                    env=container_spec.get("env", []),
                    ports=container_spec.get("ports", []),
                    volume_mounts=container_spec.get("volumeMounts", []),
                    working_dir=container_spec.get("workingDir"),
                    network=f"pod-{self.namespace}-{self.name}",
                    labels={
                        "pod": self.name,
                        "namespace": self.namespace,
                        **self.labels
                    },
                    restart_policy=self.spec.restart_policy
                )
                
                # Start container
                if container.start():
                    # Update container status
                    for cs in self.status.container_statuses:
                        if cs.name == container_name:
                            cs.container_id = container.id
                            cs.state = ContainerState.RUNNING
                            cs.ready = True
                            cs.started = True
                            cs.reason = None
                            cs.message = None
                            break
                    
                    # Store container reference
                    self._containers[container_name] = container
                else:
                    # Update container status on failure
                    for cs in self.status.container_statuses:
                        if cs.name == container_name:
                            cs.state = ContainerState.WAITING
                            cs.reason = "ContainerStartupFailed"
                            cs.message = "Failed to start container"
                            break
                    
                    # If restart policy is Never, mark pod as failed
                    if self.spec.restart_policy == RestartPolicy.NEVER:
                        self.status.phase = PodPhase.FAILED
                        self.status.reason = "ContainerStartupFailed"
                        self.status.message = f"Failed to start container {container_name}"
                        self.save()
                        return False
            
            # Check if all containers are running
            all_running = all(
                cs.state == ContainerState.RUNNING
                for cs in self.status.container_statuses
            )
            
            if all_running:
                self.status.phase = PodPhase.RUNNING
                self.status.reason = None
                self.status.message = None
            
            self.save()
            logger.info(f"Started pod {self.namespace}/{self.name}")
            return all_running
        except Exception as e:
            logger.error(f"Failed to start pod {self.namespace}/{self.name}: {e}")
            self.status.phase = PodPhase.FAILED
            self.status.reason = "FailedStart"
            self.status.message = f"Failed to start pod: {str(e)}"
            self.save()
            return False
    
    def stop(self) -> bool:
        """
        Stop the pod's containers.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Update status
            self.status.phase = PodPhase.PENDING
            self.status.reason = "Stopping"
            self.status.message = "Stopping pod containers"
            self.save()
            
            # Stop each container
            for container_name, container in self._containers.items():
                if container.stop():
                    # Update container status
                    for cs in self.status.container_statuses:
                        if cs.name == container_name:
                            cs.state = ContainerState.TERMINATED
                            cs.ready = False
                            cs.started = False
                            cs.reason = "Stopped"
                            cs.message = "Container stopped"
                            break
                else:
                    logger.warning(f"Failed to stop container {container_name} in pod {self.namespace}/{self.name}")
            
            # Update pod status
            self.status.phase = PodPhase.SUCCEEDED
            self.status.reason = "Stopped"
            self.status.message = "Pod stopped"
            self.save()
            
            logger.info(f"Stopped pod {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop pod {self.namespace}/{self.name}: {e}")
            self.status.phase = PodPhase.FAILED
            self.status.reason = "FailedStop"
            self.status.message = f"Failed to stop pod: {str(e)}"
            self.save()
            return False
    
    def restart(self) -> bool:
        """
        Restart the pod's containers.
        
        Returns:
            bool: Success or failure
        """
        if self.stop():
            return self.start()
        return False
    
    def destroy(self) -> bool:
        """
        Destroy the pod and its resources.
        
        This stops and removes all containers, and cleans up
        the pod's network and volumes.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Stop all containers
            self.stop()
            
            # Remove each container
            for container_name, container in self._containers.items():
                if not container.remove():
                    logger.warning(f"Failed to remove container {container_name} in pod {self.namespace}/{self.name}")
            
            # Clean up network
            if self._network:
                network_name = f"pod-{self.namespace}-{self.name}"
                self._network.remove_network(network_name)
            
            # Delete pod file
            self.delete()
            
            logger.info(f"Destroyed pod {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to destroy pod {self.namespace}/{self.name}: {e}")
            return False
    
    def execute(self, container_name: str, command: List[str]) -> Tuple[int, str, str]:
        """
        Execute a command in a container.
        
        Args:
            container_name: Container name
            command: Command to execute
            
        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        container = self._containers.get(container_name)
        if not container:
            logger.error(f"Container not found: {container_name} in pod {self.namespace}/{self.name}")
            return (-1, "", f"Container {container_name} not found")
        
        return container.execute(command)
    
    def get_logs(self, container_name: str, follow: bool = False,
                previous: bool = False, tail: int = -1) -> str:
        """
        Get logs from a container.
        
        Args:
            container_name: Container name
            follow: Whether to follow the logs
            previous: Whether to get logs from a previous container instance
            tail: Number of lines to return (-1 for all)
            
        Returns:
            Container logs
        """
        container = self._containers.get(container_name)
        if not container:
            logger.error(f"Container not found: {container_name} in pod {self.namespace}/{self.name}")
            return f"Container {container_name} not found"
        
        return container.logs(follow, previous, tail)
    
    def get_container_status(self, container_name: str) -> Optional[ContainerStatus]:
        """
        Get the status of a container.
        
        Args:
            container_name: Container name
            
        Returns:
            ContainerStatus or None if not found
        """
        for cs in self.status.container_statuses:
            if cs.name == container_name:
                return cs
        return None
    
    def update_status(self) -> bool:
        """
        Update the pod status based on container states.
        
        Returns:
            bool: Whether the status changed
        """
        changed = False
        
        # Check if any containers are running
        any_running = False
        all_succeeded = True
        any_failed = False
        
        for container_name, container in self._containers.items():
            # Update container status
            container_status = None
            for cs in self.status.container_statuses:
                if cs.name == container_name:
                    container_status = cs
                    break
            
            if not container_status:
                continue
            
            # Get container state
            state = container.get_state()
            if state == "running":
                container_status.state = ContainerState.RUNNING
                container_status.ready = True
                container_status.started = True
                container_status.reason = None
                container_status.message = None
                any_running = True
                all_succeeded = False
                changed = True
            elif state == "exited":
                exit_code = container.get_exit_code()
                
                # Update last state
                if container_status.state == ContainerState.RUNNING:
                    container_status.last_state = {
                        "state": container_status.state,
                        "exit_code": container_status.exit_code,
                        "reason": container_status.reason,
                        "message": container_status.message
                    }
                
                container_status.state = ContainerState.TERMINATED
                container_status.ready = False
                container_status.exit_code = exit_code
                
                if exit_code == 0:
                    container_status.reason = "Completed"
                    container_status.message = "Container exited successfully"
                else:
                    container_status.reason = "Error"
                    container_status.message = f"Container exited with code {exit_code}"
                    all_succeeded = False
                    any_failed = True
                
                # Handle restart policy
                if self.spec.restart_policy == RestartPolicy.ALWAYS:
                    # Always restart, regardless of exit code
                    logger.info(f"Restarting container {container_name} in pod {self.namespace}/{self.name} (policy: Always)")
                    container.restart()
                    container_status.restart_count += 1
                    changed = True
                elif self.spec.restart_policy == RestartPolicy.ON_FAILURE and exit_code != 0:
                    # Restart only on failure
                    logger.info(f"Restarting container {container_name} in pod {self.namespace}/{self.name} (policy: OnFailure)")
                    container.restart()
                    container_status.restart_count += 1
                    changed = True
                # For NEVER policy, do nothing
            else:
                # Container is in another state (created, paused, etc.)
                container_status.state = ContainerState.WAITING
                container_status.ready = False
                container_status.reason = "ContainerWaiting"
                container_status.message = f"Container is in state: {state}"
                all_succeeded = False
                changed = True
        
        # Update pod phase based on container states
        old_phase = self.status.phase
        
        if any_running:
            self.status.phase = PodPhase.RUNNING
        elif all_succeeded:
            self.status.phase = PodPhase.SUCCEEDED
        elif any_failed and self.spec.restart_policy == RestartPolicy.NEVER:
            self.status.phase = PodPhase.FAILED
        else:
            self.status.phase = PodPhase.PENDING
        
        if old_phase != self.status.phase:
            changed = True
        
        if changed:
            self.save()
        
        return changed

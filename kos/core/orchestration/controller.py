"""
Controllers for KOS Orchestration

This module implements controllers for the KOS container orchestration system,
similar to Kubernetes controllers like ReplicaSet, Deployment, and StatefulSet.

Controllers manage the desired state of the system by creating, updating,
and deleting pods to match the specified requirements.
"""

import os
import uuid
import json
import time
import logging
import threading
import hashlib
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

from .pod import Pod, PodSpec, PodStatus, PodPhase

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
CONTROLLERS_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration/controllers')

# Ensure directories exist
os.makedirs(CONTROLLERS_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ControllerType(str, Enum):
    """Controller types."""
    REPLICA_SET = "ReplicaSet"
    DEPLOYMENT = "Deployment"
    STATEFUL_SET = "StatefulSet"
    DAEMON_SET = "DaemonSet"
    JOB = "Job"
    CRON_JOB = "CronJob"


class ControllerStatus:
    """Status information for a controller."""
    
    def __init__(self, replicas: int = 0, ready_replicas: int = 0,
                 available_replicas: int = 0, updated_replicas: int = 0,
                 conditions: List[Dict[str, Any]] = None):
        """
        Initialize controller status.
        
        Args:
            replicas: Total number of replicas
            ready_replicas: Number of ready replicas
            available_replicas: Number of available replicas
            updated_replicas: Number of updated replicas
            conditions: List of status conditions
        """
        self.replicas = replicas
        self.ready_replicas = ready_replicas
        self.available_replicas = available_replicas
        self.updated_replicas = updated_replicas
        self.conditions = conditions or []
        self.observed_generation = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the controller status to a dictionary.
        
        Returns:
            Dict representation of the controller status
        """
        return {
            "replicas": self.replicas,
            "ready_replicas": self.ready_replicas,
            "available_replicas": self.available_replicas,
            "updated_replicas": self.updated_replicas,
            "conditions": self.conditions,
            "observed_generation": self.observed_generation
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ControllerStatus':
        """
        Create a controller status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ControllerStatus object
        """
        status = ControllerStatus(
            replicas=data.get("replicas", 0),
            ready_replicas=data.get("ready_replicas", 0),
            available_replicas=data.get("available_replicas", 0),
            updated_replicas=data.get("updated_replicas", 0),
            conditions=data.get("conditions", [])
        )
        status.observed_generation = data.get("observed_generation", 0)
        
        return status


class Controller(ABC):
    """
    Base class for controllers in the KOS orchestration system.
    
    Controllers manage the desired state of the system by creating, updating,
    and deleting pods to match the specified requirements.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 selector: Optional[Dict[str, str]] = None,
                 template: Optional[Dict[str, Any]] = None,
                 replicas: int = 1,
                 status: Optional[ControllerStatus] = None,
                 uid: Optional[str] = None,
                 controller_type: ControllerType = ControllerType.REPLICA_SET):
        """
        Initialize a controller.
        
        Args:
            name: Controller name
            namespace: Namespace
            labels: Controller labels
            annotations: Controller annotations
            selector: Label selector for pods
            template: Pod template
            replicas: Desired number of replicas
            status: Controller status
            uid: Unique ID
            controller_type: Type of controller
        """
        self.name = name
        self.namespace = namespace
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.selector = selector or {}
        self.template = template or {}
        self.replicas = replicas
        self.status = status or ControllerStatus()
        self.uid = uid or str(uuid.uuid4())
        self.controller_type = controller_type
        self.creation_timestamp = time.time()
        self.generation = 1
        
        # Runtime-specific fields (not serialized)
        self._pods = {}  # pod_name -> Pod object
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._controller_thread = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the controller to a dictionary.
        
        Returns:
            Dict representation of the controller
        """
        return {
            "kind": self.controller_type,
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "generation": self.generation,
                "labels": self.labels,
                "annotations": self.annotations
            },
            "spec": {
                "selector": self.selector,
                "template": self.template,
                "replicas": self.replicas
            },
            "status": self.status.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Controller':
        """
        Create a controller from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Controller object
        """
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        
        controller_type = ControllerType(data.get("kind", ControllerType.REPLICA_SET))
        
        if controller_type == ControllerType.REPLICA_SET:
            controller_class = ReplicaSet
        elif controller_type == ControllerType.DEPLOYMENT:
            controller_class = Deployment
        elif controller_type == ControllerType.STATEFUL_SET:
            controller_class = StatefulSet
        else:
            # Default to ReplicaSet if unknown type
            controller_class = ReplicaSet
        
        return controller_class(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            selector=spec.get("selector", {}),
            template=spec.get("template", {}),
            replicas=spec.get("replicas", 1),
            status=ControllerStatus.from_dict(data.get("status", {})),
            uid=metadata.get("uid", str(uuid.uuid4())),
            controller_type=controller_type
        )
    
    def save(self) -> bool:
        """
        Save the controller state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            namespace_dir = os.path.join(CONTROLLERS_DIR, self.namespace)
            os.makedirs(namespace_dir, exist_ok=True)
            
            controller_file = os.path.join(
                namespace_dir, f"{self.controller_type}_{self.name}.json"
            )
            with open(controller_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved controller {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save controller {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str, namespace: str = "default", 
            controller_type: ControllerType = ControllerType.REPLICA_SET) -> Optional['Controller']:
        """
        Load a controller from disk.
        
        Args:
            name: Controller name
            namespace: Namespace
            controller_type: Type of controller
            
        Returns:
            Controller object or None if not found
        """
        controller_file = os.path.join(
            CONTROLLERS_DIR, namespace, f"{controller_type}_{name}.json"
        )
        if not os.path.exists(controller_file):
            logger.error(f"Controller not found: {namespace}/{name}")
            return None
        
        try:
            with open(controller_file, 'r') as f:
                data = json.load(f)
            
            return Controller.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load controller {namespace}/{name}: {e}")
            return None
    
    @staticmethod
    def list_controllers(namespace: Optional[str] = None, 
                        controller_type: Optional[ControllerType] = None) -> List['Controller']:
        """
        List controllers.
        
        Args:
            namespace: Namespace to list controllers from, or None for all namespaces
            controller_type: Type of controllers to list, or None for all types
            
        Returns:
            List of Controller objects
        """
        controllers = []
        
        if namespace:
            # List controllers in a specific namespace
            namespace_dir = os.path.join(CONTROLLERS_DIR, namespace)
            if not os.path.exists(namespace_dir):
                return []
            
            namespaces = [namespace]
        else:
            # List controllers in all namespaces
            if not os.path.exists(CONTROLLERS_DIR):
                return []
            
            namespaces = os.listdir(CONTROLLERS_DIR)
        
        for ns in namespaces:
            namespace_dir = os.path.join(CONTROLLERS_DIR, ns)
            if not os.path.isdir(namespace_dir):
                continue
            
            for filename in os.listdir(namespace_dir):
                if not filename.endswith('.json'):
                    continue
                
                # Check controller type filter
                if controller_type:
                    if not filename.startswith(f"{controller_type}_"):
                        continue
                
                controller_file = os.path.join(namespace_dir, filename)
                try:
                    with open(controller_file, 'r') as f:
                        data = json.load(f)
                    
                    controllers.append(Controller.from_dict(data))
                except Exception as e:
                    logger.error(f"Failed to load controller from {controller_file}: {e}")
        
        return controllers
    
    def delete(self) -> bool:
        """
        Delete the controller from disk.
        
        Returns:
            bool: Success or failure
        """
        controller_file = os.path.join(
            CONTROLLERS_DIR, self.namespace, f"{self.controller_type}_{self.name}.json"
        )
        if not os.path.exists(controller_file):
            logger.warning(f"Controller not found for deletion: {self.namespace}/{self.name}")
            return False
        
        try:
            os.remove(controller_file)
            logger.info(f"Deleted controller {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete controller {self.namespace}/{self.name}: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start the controller.
        
        This starts the controller's reconciliation loop, which periodically
        checks and updates the state of the system to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        if self._controller_thread and self._controller_thread.is_alive():
            logger.warning(f"Controller {self.namespace}/{self.name} is already running")
            return False
        
        self._stop_event.clear()
        self._controller_thread = threading.Thread(
            target=self._reconcile_loop, daemon=True
        )
        self._controller_thread.start()
        
        logger.info(f"Started controller {self.namespace}/{self.name}")
        return True
    
    def stop(self) -> bool:
        """
        Stop the controller.
        
        This stops the controller's reconciliation loop.
        
        Returns:
            bool: Success or failure
        """
        if not self._controller_thread or not self._controller_thread.is_alive():
            logger.warning(f"Controller {self.namespace}/{self.name} is not running")
            return False
        
        self._stop_event.set()
        self._controller_thread.join(timeout=5)
        
        logger.info(f"Stopped controller {self.namespace}/{self.name}")
        return True
    
    def _reconcile_loop(self):
        """Main reconciliation loop."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in controller reconciliation: {e}")
            
            # Sleep for a while before next reconciliation
            self._stop_event.wait(10)
    
    @abstractmethod
    def reconcile(self) -> bool:
        """
        Reconcile the desired state with the actual state.
        
        This is the main logic of the controller, responsible for creating,
        updating, and deleting pods to match the desired state.
        
        Returns:
            bool: Whether the reconciliation was successful
        """
        pass
    
    def update_status(self) -> bool:
        """
        Update the controller status based on pod states.
        
        Returns:
            bool: Whether the status changed
        """
        with self._lock:
            old_status = self.status.to_dict()
            
            # Count pods by status
            total = 0
            ready = 0
            available = 0
            updated = 0
            
            # Find matching pods
            matching_pods = self._find_matching_pods()
            
            for pod in matching_pods:
                total += 1
                
                # Check if pod is ready
                pod_ready = all(
                    cs.ready for cs in pod.status.container_statuses
                ) if pod.status.container_statuses else False
                
                if pod_ready:
                    ready += 1
                
                # Check if pod is available
                if pod.status.phase == PodPhase.RUNNING:
                    available += 1
                
                # Check if pod is updated
                if self._is_pod_updated(pod):
                    updated += 1
            
            # Update status
            self.status.replicas = total
            self.status.ready_replicas = ready
            self.status.available_replicas = available
            self.status.updated_replicas = updated
            self.status.observed_generation = self.generation
            
            # Update conditions
            self._update_conditions()
            
            # Check if status changed
            changed = (old_status != self.status.to_dict())
            
            if changed:
                self.save()
            
            return changed
    
    def _find_matching_pods(self) -> List[Pod]:
        """
        Find pods that match this controller's selector.
        
        Returns:
            List of matching pods
        """
        matching_pods = []
        
        for pod in Pod.list_pods(self.namespace):
            # Check if pod labels match controller selector
            matches = True
            for key, value in self.selector.items():
                if pod.labels.get(key) != value:
                    matches = False
                    break
            
            if matches:
                matching_pods.append(pod)
                
                # Add to controller's pod cache
                self._pods[pod.name] = pod
        
        return matching_pods
    
    def _is_pod_updated(self, pod: Pod) -> bool:
        """
        Check if a pod is updated according to the controller's template.
        
        Args:
            pod: Pod to check
            
        Returns:
            bool: Whether the pod is updated
        """
        # By default, just check if the pod has the controller's template revision
        template_hash = self._get_template_hash()
        return pod.labels.get("controller-revision-hash") == template_hash
    
    def _get_template_hash(self) -> str:
        """
        Get a hash of the pod template.
        
        Returns:
            Hash string
        """
        # Create a hash of the template
        template_str = json.dumps(self.template, sort_keys=True)
        return hashlib.md5(template_str.encode()).hexdigest()[:10]
    
    def _update_conditions(self):
        """Update controller status conditions."""
        # Default implementation is a no-op
        pass
    
    def _create_pod_from_template(self, index: int = 0) -> Pod:
        """
        Create a pod from the controller's template.
        
        Args:
            index: Pod index for generating name
            
        Returns:
            Created pod
        """
        # Clone the template
        template = self.template.copy()
        
        # Generate pod name
        pod_name = f"{self.name}-{index}"
        
        # Set metadata
        metadata = template.get("metadata", {}).copy()
        metadata["name"] = pod_name
        metadata["namespace"] = self.namespace
        
        # Add controller labels and annotations
        labels = metadata.get("labels", {}).copy()
        labels.update(self.selector)
        labels["controller-revision-hash"] = self._get_template_hash()
        metadata["labels"] = labels
        
        annotations = metadata.get("annotations", {}).copy()
        annotations["kos.controller/name"] = self.name
        annotations["kos.controller/type"] = self.controller_type
        annotations["kos.controller/uid"] = self.uid
        metadata["annotations"] = annotations
        
        # Update template with metadata
        template["metadata"] = metadata
        
        # Create pod from template
        pod = Pod(
            name=pod_name,
            namespace=self.namespace,
            spec=PodSpec.from_dict(template.get("spec", {})),
            labels=labels,
            annotations=annotations,
            owner_reference={
                "kind": self.controller_type,
                "name": self.name,
                "uid": self.uid
            }
        )
        
        return pod
    
    def scale(self, replicas: int) -> bool:
        """
        Scale the controller to the specified number of replicas.
        
        Args:
            replicas: New replica count
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if replicas < 0:
                logger.error(f"Invalid replica count: {replicas}")
                return False
            
            self.replicas = replicas
            self.generation += 1
            self.save()
            
            logger.info(f"Scaled controller {self.namespace}/{self.name} to {replicas} replicas")
            
            # Trigger immediate reconciliation
            self.reconcile()
            
            return True

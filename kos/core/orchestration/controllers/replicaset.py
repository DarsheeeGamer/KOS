"""
ReplicaSet Controller for KOS Orchestration System

This module implements the ReplicaSet controller for the KOS orchestration system,
which ensures a specified number of pod replicas are running at any given time.
"""

import os
import json
import time
import logging
import threading
import copy
from typing import Dict, List, Any, Optional, Set, Tuple

from kos.core.orchestration.pod import Pod, PodStatus, PodSpec
from kos.core.orchestration.scheduler import Scheduler

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
REPLICASETS_PATH = os.path.join(ORCHESTRATION_ROOT, 'replicasets')

# Ensure directories exist
os.makedirs(REPLICASETS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ReplicaSetSpec:
    """Specification for a ReplicaSet."""
    
    def __init__(self, replicas: int = 1, selector: Optional[Dict[str, str]] = None,
                 template: Optional[PodSpec] = None):
        """
        Initialize a ReplicaSet specification.
        
        Args:
            replicas: Number of replicas to maintain
            selector: Label selector for pods
            template: Pod template to use for creating new pods
        """
        self.replicas = replicas
        self.selector = selector or {}
        self.template = template or PodSpec()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ReplicaSet specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "selector": self.selector,
            "template": self.template.to_dict() if self.template else {}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReplicaSetSpec':
        """
        Create a ReplicaSet specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ReplicaSetSpec object
        """
        template_data = data.get("template", {})
        template = PodSpec.from_dict(template_data) if template_data else None
        
        return cls(
            replicas=data.get("replicas", 1),
            selector=data.get("selector", {}),
            template=template
        )


class ReplicaSetStatus:
    """Status of a ReplicaSet."""
    
    def __init__(self, replicas: int = 0, ready_replicas: int = 0,
                 available_replicas: int = 0, observed_generation: int = 0):
        """
        Initialize ReplicaSet status.
        
        Args:
            replicas: Total number of replicas
            ready_replicas: Number of ready replicas
            available_replicas: Number of available replicas
            observed_generation: Last observed generation
        """
        self.replicas = replicas
        self.ready_replicas = ready_replicas
        self.available_replicas = available_replicas
        self.observed_generation = observed_generation
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ReplicaSet status to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "readyReplicas": self.ready_replicas,
            "availableReplicas": self.available_replicas,
            "observedGeneration": self.observed_generation
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ReplicaSetStatus':
        """
        Create a ReplicaSet status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ReplicaSetStatus object
        """
        return cls(
            replicas=data.get("replicas", 0),
            ready_replicas=data.get("readyReplicas", 0),
            available_replicas=data.get("availableReplicas", 0),
            observed_generation=data.get("observedGeneration", 0)
        )


class ReplicaSet:
    """
    ReplicaSet resource in the KOS orchestration system.
    
    A ReplicaSet ensures that a specified number of pod replicas are running
    at any given time. It is often used to guarantee the availability of a
    specified number of identical pods.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[ReplicaSetSpec] = None):
        """
        Initialize a ReplicaSet.
        
        Args:
            name: ReplicaSet name
            namespace: Namespace
            spec: ReplicaSet specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or ReplicaSetSpec()
        self.status = ReplicaSetStatus()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": "",
            "generation": 1,
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        self._reconcile_thread = None
        self._stop_event = threading.Event()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this ReplicaSet."""
        return os.path.join(REPLICASETS_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the ReplicaSet from disk.
        
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
            spec_data = data.get("spec", {})
            self.spec = ReplicaSetSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = ReplicaSetStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load ReplicaSet {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the ReplicaSet to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "ReplicaSet",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save ReplicaSet {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the ReplicaSet.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Stop reconciliation
            self.stop()
            
            # Delete pods
            self._delete_pods()
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete ReplicaSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _delete_pods(self) -> int:
        """
        Delete all pods managed by this ReplicaSet.
        
        Returns:
            Number of pods deleted
        """
        count = 0
        try:
            # Get managed pods
            pods = self._get_managed_pods()
            
            # Delete each pod
            for pod in pods:
                try:
                    if pod.delete():
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to delete pod {pod.namespace}/{pod.name}: {e}")
            
            return count
        except Exception as e:
            logger.error(f"Failed to delete pods for ReplicaSet {self.namespace}/{self.name}: {e}")
            return count
    
    def _get_managed_pods(self) -> List[Pod]:
        """
        Get all pods managed by this ReplicaSet.
        
        Returns:
            List of pods
        """
        try:
            # Get all pods in namespace
            pods = Pod.list_pods(self.namespace)
            
            # Filter by selector
            if not self.spec.selector:
                return []
            
            managed_pods = []
            for pod in pods:
                # Check if pod is managed by this ReplicaSet
                if self._pod_matches_selector(pod):
                    managed_pods.append(pod)
            
            return managed_pods
        except Exception as e:
            logger.error(f"Failed to get managed pods for ReplicaSet {self.namespace}/{self.name}: {e}")
            return []
    
    def _pod_matches_selector(self, pod: Pod) -> bool:
        """
        Check if a pod matches the ReplicaSet's selector.
        
        Args:
            pod: Pod to check
            
        Returns:
            bool: True if pod matches selector
        """
        # Check if pod has owner reference to this ReplicaSet
        for owner_ref in pod.metadata.get("ownerReferences", []):
            if (owner_ref.get("kind") == "ReplicaSet" and
                owner_ref.get("name") == self.name and
                owner_ref.get("uid") == self.metadata.get("uid")):
                return True
        
        # Check if pod matches selector
        for key, value in self.spec.selector.items():
            if pod.metadata.get("labels", {}).get(key) != value:
                return False
        
        return True
    
    def _create_pod(self) -> Optional[Pod]:
        """
        Create a new pod from the template.
        
        Returns:
            New pod or None if creation failed
        """
        try:
            if not self.spec.template:
                logger.error(f"No pod template for ReplicaSet {self.namespace}/{self.name}")
                return None
            
            # Generate unique pod name
            pod_name = f"{self.name}-{hash(time.time()) % 10000:04d}"
            
            # Create pod from template
            pod = Pod(pod_name, self.namespace, copy.deepcopy(self.spec.template))
            
            # Set owner reference
            owner_ref = {
                "kind": "ReplicaSet",
                "name": self.name,
                "uid": self.metadata.get("uid", ""),
                "controller": True,
                "blockOwnerDeletion": True
            }
            
            if "ownerReferences" not in pod.metadata:
                pod.metadata["ownerReferences"] = []
            
            pod.metadata["ownerReferences"].append(owner_ref)
            
            # Add selector labels to pod
            if "labels" not in pod.metadata:
                pod.metadata["labels"] = {}
            
            for key, value in self.spec.selector.items():
                pod.metadata["labels"][key] = value
            
            # Create pod
            if not pod.save():
                logger.error(f"Failed to save pod {pod.namespace}/{pod.name}")
                return None
            
            # Schedule pod
            scheduler = Scheduler()
            if not scheduler.schedule_pod(pod):
                logger.error(f"Failed to schedule pod {pod.namespace}/{pod.name}")
                pod.delete()
                return None
            
            logger.info(f"Created pod {pod.namespace}/{pod.name} for ReplicaSet {self.namespace}/{self.name}")
            return pod
        except Exception as e:
            logger.error(f"Failed to create pod for ReplicaSet {self.namespace}/{self.name}: {e}")
            return None
    
    def reconcile(self) -> bool:
        """
        Reconcile the ReplicaSet to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Get managed pods
                managed_pods = self._get_managed_pods()
                
                # Update status
                self._update_status(managed_pods)
                
                # Check if we need to create or delete pods
                current_replicas = len(managed_pods)
                desired_replicas = self.spec.replicas
                
                if current_replicas < desired_replicas:
                    # Need to create pods
                    for _ in range(desired_replicas - current_replicas):
                        self._create_pod()
                elif current_replicas > desired_replicas:
                    # Need to delete pods
                    pods_to_delete = managed_pods[desired_replicas:]
                    for pod in pods_to_delete:
                        pod.delete()
                
                # Save updated status
                self.save()
                
                return True
        except Exception as e:
            logger.error(f"Failed to reconcile ReplicaSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _update_status(self, pods: Optional[List[Pod]] = None) -> None:
        """
        Update the ReplicaSet status.
        
        Args:
            pods: List of managed pods (will be fetched if None)
        """
        if pods is None:
            pods = self._get_managed_pods()
        
        # Update status
        self.status.replicas = len(pods)
        self.status.ready_replicas = sum(1 for pod in pods if pod.status.phase == PodStatus.RUNNING)
        self.status.available_replicas = sum(1 for pod in pods if pod.status.phase == PodStatus.RUNNING)
        self.status.observed_generation = self.metadata.get("generation", 0)
    
    def start(self) -> bool:
        """
        Start reconciliation loop.
        
        Returns:
            bool: Success or failure
        """
        if self._reconcile_thread and self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.clear()
        self._reconcile_thread = threading.Thread(
            target=self._reconcile_loop,
            daemon=True
        )
        self._reconcile_thread.start()
        
        return True
    
    def stop(self) -> bool:
        """
        Stop reconciliation loop.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the ReplicaSet."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in ReplicaSet reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(10)  # Check every 10 seconds
    
    @staticmethod
    def list_replicasets(namespace: Optional[str] = None) -> List['ReplicaSet']:
        """
        List all ReplicaSets.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of ReplicaSets
        """
        replicasets = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespace_dir = REPLICASETS_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
                else:
                    namespaces = []
            
            # List ReplicaSets in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(REPLICASETS_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    replicaset_name = filename[:-5]  # Remove .json extension
                    replicaset = ReplicaSet(replicaset_name, ns)
                    replicasets.append(replicaset)
        except Exception as e:
            logger.error(f"Failed to list ReplicaSets: {e}")
        
        return replicasets
    
    @staticmethod
    def get_replicaset(name: str, namespace: str = "default") -> Optional['ReplicaSet']:
        """
        Get a ReplicaSet by name and namespace.
        
        Args:
            name: ReplicaSet name
            namespace: Namespace
            
        Returns:
            ReplicaSet or None if not found
        """
        replicaset = ReplicaSet(name, namespace)
        
        if os.path.exists(replicaset._file_path()):
            return replicaset
        
        return None

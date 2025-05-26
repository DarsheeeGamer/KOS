"""
StatefulSet Controller for KOS Orchestration System

This module implements the StatefulSet controller for the KOS orchestration system,
which manages the deployment and scaling of a set of Pods with unique identities
and persistent storage.
"""

import os
import json
import time
import logging
import threading
import copy
import re
from typing import Dict, List, Any, Optional, Set, Tuple

from kos.core.orchestration.pod import Pod, PodStatus, PodSpec
from kos.core.orchestration.service import Service
from kos.core.storage.volume import PersistentVolumeClaim

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
STATEFULSETS_PATH = os.path.join(ORCHESTRATION_ROOT, 'statefulsets')

# Ensure directories exist
os.makedirs(STATEFULSETS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class StatefulSetSpec:
    """Specification for a StatefulSet."""
    
    def __init__(self, replicas: int = 1, selector: Optional[Dict[str, str]] = None,
                 template: Optional[PodSpec] = None, service_name: str = "",
                 pod_management_policy: str = "OrderedReady",
                 update_strategy: Optional[Dict[str, Any]] = None,
                 volume_claim_templates: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize a StatefulSet specification.
        
        Args:
            replicas: Number of replicas to maintain
            selector: Label selector for pods
            template: Pod template to use for creating new pods
            service_name: Name of the Service that governs this StatefulSet
            pod_management_policy: Pod management policy ("OrderedReady" or "Parallel")
            update_strategy: Update strategy for the StatefulSet
            volume_claim_templates: Templates for PersistentVolumeClaims
        """
        self.replicas = replicas
        self.selector = selector or {}
        self.template = template or PodSpec()
        self.service_name = service_name
        self.pod_management_policy = pod_management_policy
        self.update_strategy = update_strategy or {"type": "RollingUpdate"}
        self.volume_claim_templates = volume_claim_templates or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the StatefulSet specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "selector": self.selector,
            "template": self.template.to_dict() if self.template else {},
            "serviceName": self.service_name,
            "podManagementPolicy": self.pod_management_policy,
            "updateStrategy": self.update_strategy,
            "volumeClaimTemplates": self.volume_claim_templates
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatefulSetSpec':
        """
        Create a StatefulSet specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            StatefulSetSpec object
        """
        template_data = data.get("template", {})
        template = PodSpec.from_dict(template_data) if template_data else None
        
        return cls(
            replicas=data.get("replicas", 1),
            selector=data.get("selector", {}),
            template=template,
            service_name=data.get("serviceName", ""),
            pod_management_policy=data.get("podManagementPolicy", "OrderedReady"),
            update_strategy=data.get("updateStrategy", {"type": "RollingUpdate"}),
            volume_claim_templates=data.get("volumeClaimTemplates", [])
        )


class StatefulSetStatus:
    """Status of a StatefulSet."""
    
    def __init__(self, replicas: int = 0, ready_replicas: int = 0,
                 current_replicas: int = 0, updated_replicas: int = 0,
                 observed_generation: int = 0, collision_count: int = 0):
        """
        Initialize StatefulSet status.
        
        Args:
            replicas: Total number of replicas
            ready_replicas: Number of ready replicas
            current_replicas: Number of current replicas
            updated_replicas: Number of updated replicas
            observed_generation: Last observed generation
            collision_count: Count of hash collisions
        """
        self.replicas = replicas
        self.ready_replicas = ready_replicas
        self.current_replicas = current_replicas
        self.updated_replicas = updated_replicas
        self.observed_generation = observed_generation
        self.collision_count = collision_count
        self.conditions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the StatefulSet status to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "readyReplicas": self.ready_replicas,
            "currentReplicas": self.current_replicas,
            "updatedReplicas": self.updated_replicas,
            "observedGeneration": self.observed_generation,
            "collisionCount": self.collision_count,
            "conditions": self.conditions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatefulSetStatus':
        """
        Create a StatefulSet status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            StatefulSetStatus object
        """
        status = cls(
            replicas=data.get("replicas", 0),
            ready_replicas=data.get("readyReplicas", 0),
            current_replicas=data.get("currentReplicas", 0),
            updated_replicas=data.get("updatedReplicas", 0),
            observed_generation=data.get("observedGeneration", 0),
            collision_count=data.get("collisionCount", 0)
        )
        
        status.conditions = data.get("conditions", [])
        
        return status


class StatefulSet:
    """
    StatefulSet resource in the KOS orchestration system.
    
    A StatefulSet manages the deployment and scaling of a set of Pods, and provides
    guarantees about the ordering and uniqueness of these Pods. Like a Deployment,
    a StatefulSet manages Pods that are based on an identical container spec. Unlike
    a Deployment, a StatefulSet maintains a sticky identity for each of their Pods.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[StatefulSetSpec] = None):
        """
        Initialize a StatefulSet.
        
        Args:
            name: StatefulSet name
            namespace: Namespace
            spec: StatefulSet specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or StatefulSetSpec()
        self.status = StatefulSetStatus()
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
        """Get the file path for this StatefulSet."""
        return os.path.join(STATEFULSETS_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the StatefulSet from disk.
        
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
            self.spec = StatefulSetSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = StatefulSetStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the StatefulSet to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "StatefulSet",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the StatefulSet.
        
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
            logger.error(f"Failed to delete StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _delete_pods(self) -> int:
        """
        Delete all pods managed by this StatefulSet.
        
        Returns:
            Number of pods deleted
        """
        count = 0
        try:
            # Get managed pods
            pods = self._get_managed_pods()
            
            # Delete each pod in reverse order
            for pod in sorted(pods, key=lambda p: self._get_pod_ordinal(p.name), reverse=True):
                try:
                    if pod.delete():
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to delete pod {pod.namespace}/{pod.name}: {e}")
            
            return count
        except Exception as e:
            logger.error(f"Failed to delete pods for StatefulSet {self.namespace}/{self.name}: {e}")
            return count
    
    def _get_managed_pods(self) -> List[Pod]:
        """
        Get all pods managed by this StatefulSet.
        
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
                # Check if pod is managed by this StatefulSet
                if self._pod_matches_selector(pod):
                    managed_pods.append(pod)
            
            return managed_pods
        except Exception as e:
            logger.error(f"Failed to get managed pods for StatefulSet {self.namespace}/{self.name}: {e}")
            return []
    
    def _pod_matches_selector(self, pod: Pod) -> bool:
        """
        Check if a pod matches the StatefulSet's selector.
        
        Args:
            pod: Pod to check
            
        Returns:
            bool: True if pod matches selector
        """
        # Check if pod has owner reference to this StatefulSet
        for owner_ref in pod.metadata.get("ownerReferences", []):
            if (owner_ref.get("kind") == "StatefulSet" and
                owner_ref.get("name") == self.name and
                owner_ref.get("uid") == self.metadata.get("uid")):
                return True
        
        # Check if pod matches selector
        for key, value in self.spec.selector.items():
            if pod.metadata.get("labels", {}).get(key) != value:
                return False
        
        # Check if pod name matches pattern
        pod_name_pattern = f"^{self.name}-\\d+$"
        if not re.match(pod_name_pattern, pod.name):
            return False
        
        return True
    
    def _get_pod_ordinal(self, pod_name: str) -> int:
        """
        Get the ordinal of a pod.
        
        Args:
            pod_name: Pod name
            
        Returns:
            Ordinal or -1 if not a valid pod name
        """
        match = re.match(f"^{self.name}-(\\d+)$", pod_name)
        if match:
            return int(match.group(1))
        
        return -1
    
    def _create_pod(self, ordinal: int) -> Optional[Pod]:
        """
        Create a new pod for the StatefulSet.
        
        Args:
            ordinal: Pod ordinal
            
        Returns:
            New pod or None if creation failed
        """
        try:
            if not self.spec.template:
                logger.error(f"No pod template for StatefulSet {self.namespace}/{self.name}")
                return None
            
            # Generate pod name
            pod_name = f"{self.name}-{ordinal}"
            
            # Create pod from template
            pod = Pod(pod_name, self.namespace, copy.deepcopy(self.spec.template))
            
            # Set hostname and subdomain
            pod.spec.hostname = pod_name
            if self.spec.service_name:
                pod.spec.subdomain = self.spec.service_name
            
            # Set owner reference
            owner_ref = {
                "kind": "StatefulSet",
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
            
            # Create volume claims
            self._create_volume_claims(pod, ordinal)
            
            # Create pod
            if not pod.save():
                logger.error(f"Failed to save pod {pod.namespace}/{pod.name}")
                return None
            
            logger.info(f"Created pod {pod.namespace}/{pod.name} for StatefulSet {self.namespace}/{self.name}")
            return pod
        except Exception as e:
            logger.error(f"Failed to create pod for StatefulSet {self.namespace}/{self.name}: {e}")
            return None
    
    def _create_volume_claims(self, pod: Pod, ordinal: int) -> bool:
        """
        Create volume claims for a pod.
        
        Args:
            pod: Pod to create volume claims for
            ordinal: Pod ordinal
            
        Returns:
            bool: Success or failure
        """
        try:
            if not self.spec.volume_claim_templates:
                return True
            
            # Create volume claims from templates
            for template in self.spec.volume_claim_templates:
                # Generate claim name
                template_name = template.get("metadata", {}).get("name", "data")
                claim_name = f"{template_name}-{self.name}-{ordinal}"
                
                # Create claim
                claim = PersistentVolumeClaim(
                    name=claim_name,
                    namespace=self.namespace
                )
                
                # Set spec from template
                claim.spec.from_dict(template.get("spec", {}))
                
                # Set owner reference
                owner_ref = {
                    "kind": "Pod",
                    "name": pod.name,
                    "uid": pod.metadata.get("uid", ""),
                    "controller": False,
                    "blockOwnerDeletion": True
                }
                
                if "ownerReferences" not in claim.metadata:
                    claim.metadata["ownerReferences"] = []
                
                claim.metadata["ownerReferences"].append(owner_ref)
                
                # Save claim
                if not claim.save():
                    logger.error(f"Failed to save claim {claim.namespace}/{claim.name}")
                    continue
                
                # Add volume mount to pod
                volume = {
                    "name": template_name,
                    "persistentVolumeClaim": {
                        "claimName": claim_name
                    }
                }
                
                if "volumes" not in pod.spec.volumes:
                    pod.spec.volumes = []
                
                pod.spec.volumes.append(volume)
                
                # Add volume mount to containers
                for container in pod.spec.containers:
                    mount_path = template.get("spec", {}).get("mountPath", f"/data/{template_name}")
                    
                    volume_mount = {
                        "name": template_name,
                        "mountPath": mount_path
                    }
                    
                    if "volumeMounts" not in container:
                        container["volumeMounts"] = []
                    
                    container["volumeMounts"].append(volume_mount)
            
            return True
        except Exception as e:
            logger.error(f"Failed to create volume claims for pod {pod.namespace}/{pod.name}: {e}")
            return False
    
    def reconcile(self) -> bool:
        """
        Reconcile the StatefulSet to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Get managed pods
                managed_pods = self._get_managed_pods()
                
                # Sort pods by ordinal
                sorted_pods = sorted(managed_pods, key=lambda p: self._get_pod_ordinal(p.name))
                
                # Get existing ordinals
                existing_ordinals = set(self._get_pod_ordinal(pod.name) for pod in sorted_pods)
                
                # Ensure pods are created in order
                if self.spec.pod_management_policy == "OrderedReady":
                    # Check if we need to create or delete pods
                    for ordinal in range(self.spec.replicas):
                        if ordinal not in existing_ordinals:
                            # Create pod with this ordinal
                            pod = self._create_pod(ordinal)
                            if not pod:
                                # Stop here if pod creation failed
                                break
                            
                            # Wait for pod to be ready before creating next one
                            if ordinal < self.spec.replicas - 1:
                                break
                else:  # Parallel
                    # Create all missing pods
                    for ordinal in range(self.spec.replicas):
                        if ordinal not in existing_ordinals:
                            self._create_pod(ordinal)
                
                # Delete pods with ordinals >= replicas
                for pod in sorted_pods:
                    ordinal = self._get_pod_ordinal(pod.name)
                    if ordinal >= self.spec.replicas:
                        pod.delete()
                
                # Update status
                self._update_status(sorted_pods)
                
                # Save updated status
                self.save()
                
                return True
        except Exception as e:
            logger.error(f"Failed to reconcile StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _update_status(self, pods: Optional[List[Pod]] = None) -> None:
        """
        Update the StatefulSet status.
        
        Args:
            pods: List of managed pods (will be fetched if None)
        """
        if pods is None:
            pods = self._get_managed_pods()
        
        # Sort pods by ordinal
        sorted_pods = sorted(pods, key=lambda p: self._get_pod_ordinal(p.name))
        
        # Count current replicas (all pods)
        self.status.replicas = len(sorted_pods)
        
        # Count ready replicas
        self.status.ready_replicas = sum(1 for pod in sorted_pods if pod.status.phase == PodStatus.RUNNING)
        
        # Count current replicas (pods with current spec)
        self.status.current_replicas = len(sorted_pods)  # Simplified, should check revision
        
        # Count updated replicas
        self.status.updated_replicas = len(sorted_pods)  # Simplified, should check revision
        
        # Update observed generation
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
        """Reconciliation loop for the StatefulSet."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in StatefulSet reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(10)  # Check every 10 seconds
    
    def scale(self, replicas: int) -> bool:
        """
        Scale the StatefulSet to the specified number of replicas.
        
        Args:
            replicas: Number of replicas
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update spec
                self.spec.replicas = replicas
                
                # Save
                if not self.save():
                    logger.error(f"Failed to save StatefulSet {self.namespace}/{self.name}")
                    return False
                
                # Reconcile
                return self.reconcile()
        except Exception as e:
            logger.error(f"Failed to scale StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_statefulsets(namespace: Optional[str] = None) -> List['StatefulSet']:
        """
        List all StatefulSets.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of StatefulSets
        """
        statefulsets = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespace_dir = STATEFULSETS_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
                else:
                    namespaces = []
            
            # List StatefulSets in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(STATEFULSETS_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    statefulset_name = filename[:-5]  # Remove .json extension
                    statefulset = StatefulSet(statefulset_name, ns)
                    statefulsets.append(statefulset)
        except Exception as e:
            logger.error(f"Failed to list StatefulSets: {e}")
        
        return statefulsets
    
    @staticmethod
    def get_statefulset(name: str, namespace: str = "default") -> Optional['StatefulSet']:
        """
        Get a StatefulSet by name and namespace.
        
        Args:
            name: StatefulSet name
            namespace: Namespace
            
        Returns:
            StatefulSet or None if not found
        """
        statefulset = StatefulSet(name, namespace)
        
        if os.path.exists(statefulset._file_path()):
            return statefulset
        
        return None

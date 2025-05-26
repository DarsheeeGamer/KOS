"""
Deployment Controller for KOS Orchestration System

This module implements the Deployment controller for the KOS orchestration system,
which provides declarative updates to applications.
"""

import os
import json
import time
import logging
import threading
import copy
import hashlib
from typing import Dict, List, Any, Optional, Set, Tuple

from kos.core.orchestration.pod import Pod, PodStatus, PodSpec
from kos.core.orchestration.controllers.replicaset import ReplicaSet, ReplicaSetSpec

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
DEPLOYMENTS_PATH = os.path.join(ORCHESTRATION_ROOT, 'deployments')

# Ensure directories exist
os.makedirs(DEPLOYMENTS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class DeploymentStrategy:
    """Strategy for deploying updates to a Deployment."""
    
    RECREATE = "Recreate"
    ROLLING_UPDATE = "RollingUpdate"
    
    def __init__(self, type: str = ROLLING_UPDATE,
                 max_unavailable: Optional[int] = None,
                 max_surge: Optional[int] = None):
        """
        Initialize a deployment strategy.
        
        Args:
            type: Strategy type (Recreate or RollingUpdate)
            max_unavailable: Maximum number of unavailable pods during update
            max_surge: Maximum number of extra pods that can be created during update
        """
        self.type = type
        self.max_unavailable = max_unavailable
        self.max_surge = max_surge
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the deployment strategy to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {"type": self.type}
        
        if self.type == self.ROLLING_UPDATE:
            result["rollingUpdate"] = {}
            
            if self.max_unavailable is not None:
                result["rollingUpdate"]["maxUnavailable"] = self.max_unavailable
            
            if self.max_surge is not None:
                result["rollingUpdate"]["maxSurge"] = self.max_surge
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentStrategy':
        """
        Create a deployment strategy from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DeploymentStrategy object
        """
        strategy_type = data.get("type", cls.ROLLING_UPDATE)
        
        if strategy_type == cls.ROLLING_UPDATE:
            rolling_update = data.get("rollingUpdate", {})
            max_unavailable = rolling_update.get("maxUnavailable")
            max_surge = rolling_update.get("maxSurge")
            
            return cls(
                type=strategy_type,
                max_unavailable=max_unavailable,
                max_surge=max_surge
            )
        else:
            return cls(type=strategy_type)


class DeploymentSpec:
    """Specification for a Deployment."""
    
    def __init__(self, replicas: int = 1, selector: Optional[Dict[str, str]] = None,
                 template: Optional[PodSpec] = None,
                 strategy: Optional[DeploymentStrategy] = None,
                 min_ready_seconds: int = 0,
                 revision_history_limit: int = 10,
                 progress_deadline_seconds: int = 600):
        """
        Initialize a Deployment specification.
        
        Args:
            replicas: Number of replicas to maintain
            selector: Label selector for pods
            template: Pod template to use for creating new pods
            strategy: Deployment strategy
            min_ready_seconds: Minimum seconds a pod should be ready before considered available
            revision_history_limit: Number of old ReplicaSets to retain
            progress_deadline_seconds: Maximum time for deployment before it is considered failed
        """
        self.replicas = replicas
        self.selector = selector or {}
        self.template = template or PodSpec()
        self.strategy = strategy or DeploymentStrategy()
        self.min_ready_seconds = min_ready_seconds
        self.revision_history_limit = revision_history_limit
        self.progress_deadline_seconds = progress_deadline_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Deployment specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "selector": self.selector,
            "template": self.template.to_dict() if self.template else {},
            "strategy": self.strategy.to_dict(),
            "minReadySeconds": self.min_ready_seconds,
            "revisionHistoryLimit": self.revision_history_limit,
            "progressDeadlineSeconds": self.progress_deadline_seconds
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentSpec':
        """
        Create a Deployment specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DeploymentSpec object
        """
        template_data = data.get("template", {})
        template = PodSpec.from_dict(template_data) if template_data else None
        
        strategy_data = data.get("strategy", {})
        strategy = DeploymentStrategy.from_dict(strategy_data)
        
        return cls(
            replicas=data.get("replicas", 1),
            selector=data.get("selector", {}),
            template=template,
            strategy=strategy,
            min_ready_seconds=data.get("minReadySeconds", 0),
            revision_history_limit=data.get("revisionHistoryLimit", 10),
            progress_deadline_seconds=data.get("progressDeadlineSeconds", 600)
        )


class DeploymentStatus:
    """Status of a Deployment."""
    
    def __init__(self, replicas: int = 0, ready_replicas: int = 0,
                 updated_replicas: int = 0, available_replicas: int = 0,
                 unavailable_replicas: int = 0, observed_generation: int = 0,
                 collision_count: int = 0):
        """
        Initialize Deployment status.
        
        Args:
            replicas: Total number of replicas
            ready_replicas: Number of ready replicas
            updated_replicas: Number of updated replicas
            available_replicas: Number of available replicas
            unavailable_replicas: Number of unavailable replicas
            observed_generation: Last observed generation
            collision_count: Count of hash collisions
        """
        self.replicas = replicas
        self.ready_replicas = ready_replicas
        self.updated_replicas = updated_replicas
        self.available_replicas = available_replicas
        self.unavailable_replicas = unavailable_replicas
        self.observed_generation = observed_generation
        self.collision_count = collision_count
        self.conditions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Deployment status to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "replicas": self.replicas,
            "readyReplicas": self.ready_replicas,
            "updatedReplicas": self.updated_replicas,
            "availableReplicas": self.available_replicas,
            "unavailableReplicas": self.unavailable_replicas,
            "observedGeneration": self.observed_generation,
            "collisionCount": self.collision_count,
            "conditions": self.conditions
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DeploymentStatus':
        """
        Create a Deployment status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DeploymentStatus object
        """
        status = cls(
            replicas=data.get("replicas", 0),
            ready_replicas=data.get("readyReplicas", 0),
            updated_replicas=data.get("updatedReplicas", 0),
            available_replicas=data.get("availableReplicas", 0),
            unavailable_replicas=data.get("unavailableReplicas", 0),
            observed_generation=data.get("observedGeneration", 0),
            collision_count=data.get("collisionCount", 0)
        )
        
        status.conditions = data.get("conditions", [])
        
        return status


class Deployment:
    """
    Deployment resource in the KOS orchestration system.
    
    A Deployment provides declarative updates for Pods and ReplicaSets. You describe a
    desired state in a Deployment, and the Deployment Controller changes the actual
    state to the desired state at a controlled rate.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[DeploymentSpec] = None):
        """
        Initialize a Deployment.
        
        Args:
            name: Deployment name
            namespace: Namespace
            spec: Deployment specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or DeploymentSpec()
        self.status = DeploymentStatus()
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
        """Get the file path for this Deployment."""
        return os.path.join(DEPLOYMENTS_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the Deployment from disk.
        
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
            self.spec = DeploymentSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = DeploymentStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Deployment to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "Deployment",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Deployment.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Stop reconciliation
            self.stop()
            
            # Delete ReplicaSets
            self._delete_replicasets()
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    def _delete_replicasets(self) -> int:
        """
        Delete all ReplicaSets managed by this Deployment.
        
        Returns:
            Number of ReplicaSets deleted
        """
        count = 0
        try:
            # Get managed ReplicaSets
            replicasets = self._get_managed_replicasets()
            
            # Delete each ReplicaSet
            for rs in replicasets:
                try:
                    if rs.delete():
                        count += 1
                except Exception as e:
                    logger.error(f"Failed to delete ReplicaSet {rs.namespace}/{rs.name}: {e}")
            
            return count
        except Exception as e:
            logger.error(f"Failed to delete ReplicaSets for Deployment {self.namespace}/{self.name}: {e}")
            return count
    
    def _get_managed_replicasets(self) -> List[ReplicaSet]:
        """
        Get all ReplicaSets managed by this Deployment.
        
        Returns:
            List of ReplicaSets
        """
        try:
            # Get all ReplicaSets in namespace
            replicasets = ReplicaSet.list_replicasets(self.namespace)
            
            # Filter by owner reference
            managed_replicasets = []
            for rs in replicasets:
                # Check if ReplicaSet is managed by this Deployment
                for owner_ref in rs.metadata.get("ownerReferences", []):
                    if (owner_ref.get("kind") == "Deployment" and
                        owner_ref.get("name") == self.name and
                        owner_ref.get("uid") == self.metadata.get("uid")):
                        managed_replicasets.append(rs)
                        break
            
            return managed_replicasets
        except Exception as e:
            logger.error(f"Failed to get managed ReplicaSets for Deployment {self.namespace}/{self.name}: {e}")
            return []
    
    def _get_current_replicaset(self) -> Optional[ReplicaSet]:
        """
        Get the current ReplicaSet for this Deployment.
        
        Returns:
            Current ReplicaSet or None
        """
        try:
            # Get managed ReplicaSets
            replicasets = self._get_managed_replicasets()
            if not replicasets:
                return None
            
            # Find ReplicaSet with matching pod template hash
            pod_template_hash = self._get_pod_template_hash()
            
            for rs in replicasets:
                if rs.metadata.get("labels", {}).get("pod-template-hash") == pod_template_hash:
                    return rs
            
            # No matching ReplicaSet found
            return None
        except Exception as e:
            logger.error(f"Failed to get current ReplicaSet for Deployment {self.namespace}/{self.name}: {e}")
            return None
    
    def _get_pod_template_hash(self) -> str:
        """
        Get the pod template hash for this Deployment.
        
        Returns:
            Pod template hash
        """
        # Create a hash of the pod template
        template_json = json.dumps(self.spec.template.to_dict(), sort_keys=True)
        return hashlib.md5(template_json.encode()).hexdigest()[:10]
    
    def _create_replicaset(self) -> Optional[ReplicaSet]:
        """
        Create a new ReplicaSet for this Deployment.
        
        Returns:
            New ReplicaSet or None if creation failed
        """
        try:
            if not self.spec.template:
                logger.error(f"No pod template for Deployment {self.namespace}/{self.name}")
                return None
            
            # Generate pod template hash
            pod_template_hash = self._get_pod_template_hash()
            
            # Create ReplicaSet name
            rs_name = f"{self.name}-{pod_template_hash}"
            
            # Create ReplicaSet
            rs_spec = ReplicaSetSpec(
                replicas=self.spec.replicas,
                selector=self.spec.selector,
                template=copy.deepcopy(self.spec.template)
            )
            
            rs = ReplicaSet(rs_name, self.namespace, rs_spec)
            
            # Add labels
            if "labels" not in rs.metadata:
                rs.metadata["labels"] = {}
            
            rs.metadata["labels"]["pod-template-hash"] = pod_template_hash
            
            # Add labels from Deployment
            for key, value in self.metadata.get("labels", {}).items():
                rs.metadata["labels"][key] = value
            
            # Set owner reference
            owner_ref = {
                "kind": "Deployment",
                "name": self.name,
                "uid": self.metadata.get("uid", ""),
                "controller": True,
                "blockOwnerDeletion": True
            }
            
            if "ownerReferences" not in rs.metadata:
                rs.metadata["ownerReferences"] = []
            
            rs.metadata["ownerReferences"].append(owner_ref)
            
            # Save ReplicaSet
            if not rs.save():
                logger.error(f"Failed to save ReplicaSet {rs.namespace}/{rs.name}")
                return None
            
            # Start ReplicaSet controller
            rs.start()
            
            logger.info(f"Created ReplicaSet {rs.namespace}/{rs.name} for Deployment {self.namespace}/{self.name}")
            return rs
        except Exception as e:
            logger.error(f"Failed to create ReplicaSet for Deployment {self.namespace}/{self.name}: {e}")
            return None
    
    def reconcile(self) -> bool:
        """
        Reconcile the Deployment to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Get current ReplicaSet
                current_rs = self._get_current_replicaset()
                
                # Create new ReplicaSet if needed
                if not current_rs:
                    current_rs = self._create_replicaset()
                    if not current_rs:
                        logger.error(f"Failed to create ReplicaSet for Deployment {self.namespace}/{self.name}")
                        return False
                
                # Update ReplicaSet replicas if needed
                if current_rs.spec.replicas != self.spec.replicas:
                    current_rs.spec.replicas = self.spec.replicas
                    current_rs.save()
                
                # Get all managed ReplicaSets
                all_rs = self._get_managed_replicasets()
                
                # Scale down old ReplicaSets
                for rs in all_rs:
                    if rs.name != current_rs.name and rs.spec.replicas > 0:
                        # Handle strategy
                        if self.spec.strategy.type == DeploymentStrategy.RECREATE:
                            # Scale down to 0
                            rs.spec.replicas = 0
                            rs.save()
                        elif self.spec.strategy.type == DeploymentStrategy.ROLLING_UPDATE:
                            # Handle rolling update logic
                            self._handle_rolling_update(current_rs, rs)
                
                # Update status
                self._update_status(all_rs)
                
                # Save updated status
                self.save()
                
                return True
        except Exception as e:
            logger.error(f"Failed to reconcile Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    def _handle_rolling_update(self, new_rs: ReplicaSet, old_rs: ReplicaSet) -> None:
        """
        Handle rolling update strategy.
        
        Args:
            new_rs: New ReplicaSet
            old_rs: Old ReplicaSet
        """
        # Calculate max unavailable and max surge
        max_unavailable = self.spec.strategy.max_unavailable or 1
        max_surge = self.spec.strategy.max_surge or 1
        
        # Calculate current state
        total_replicas = sum(rs.status.replicas for rs in [new_rs, old_rs])
        available_replicas = sum(rs.status.available_replicas for rs in [new_rs, old_rs])
        unavailable_replicas = total_replicas - available_replicas
        
        # Determine how many pods we can scale down
        max_scale_down = max(0, old_rs.spec.replicas - max(0, unavailable_replicas - max_unavailable))
        
        # Determine how many pods we can scale up
        desired_replicas = self.spec.replicas
        max_scale_up = min(desired_replicas, new_rs.spec.replicas + max(0, max_surge - (total_replicas - desired_replicas)))
        
        # Scale down old ReplicaSet
        if old_rs.spec.replicas > 0 and max_scale_down > 0:
            old_rs.spec.replicas = max(0, old_rs.spec.replicas - max_scale_down)
            old_rs.save()
        
        # Scale up new ReplicaSet
        if new_rs.spec.replicas < desired_replicas and max_scale_up > new_rs.spec.replicas:
            new_rs.spec.replicas = max_scale_up
            new_rs.save()
    
    def _update_status(self, replicasets: Optional[List[ReplicaSet]] = None) -> None:
        """
        Update the Deployment status.
        
        Args:
            replicasets: List of managed ReplicaSets (will be fetched if None)
        """
        if replicasets is None:
            replicasets = self._get_managed_replicasets()
        
        # Get pod template hash
        pod_template_hash = self._get_pod_template_hash()
        
        # Calculate status
        self.status.replicas = sum(rs.status.replicas for rs in replicasets)
        self.status.ready_replicas = sum(rs.status.ready_replicas for rs in replicasets)
        self.status.available_replicas = sum(rs.status.available_replicas for rs in replicasets)
        
        # Calculate updated replicas
        self.status.updated_replicas = sum(
            rs.status.replicas for rs in replicasets
            if rs.metadata.get("labels", {}).get("pod-template-hash") == pod_template_hash
        )
        
        self.status.unavailable_replicas = self.status.replicas - self.status.available_replicas
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
        """Reconciliation loop for the Deployment."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in Deployment reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(10)  # Check every 10 seconds
    
    def scale(self, replicas: int) -> bool:
        """
        Scale the Deployment to the specified number of replicas.
        
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
                    logger.error(f"Failed to save Deployment {self.namespace}/{self.name}")
                    return False
                
                # Reconcile
                return self.reconcile()
        except Exception as e:
            logger.error(f"Failed to scale Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_deployments(namespace: Optional[str] = None) -> List['Deployment']:
        """
        List all Deployments.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of Deployments
        """
        deployments = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespace_dir = DEPLOYMENTS_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
                else:
                    namespaces = []
            
            # List Deployments in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(DEPLOYMENTS_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    deployment_name = filename[:-5]  # Remove .json extension
                    deployment = Deployment(deployment_name, ns)
                    deployments.append(deployment)
        except Exception as e:
            logger.error(f"Failed to list Deployments: {e}")
        
        return deployments
    
    @staticmethod
    def get_deployment(name: str, namespace: str = "default") -> Optional['Deployment']:
        """
        Get a Deployment by name and namespace.
        
        Args:
            name: Deployment name
            namespace: Namespace
            
        Returns:
            Deployment or None if not found
        """
        deployment = Deployment(name, namespace)
        
        if os.path.exists(deployment._file_path()):
            return deployment
        
        return None

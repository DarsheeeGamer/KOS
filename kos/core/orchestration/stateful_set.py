"""
StatefulSet Controller for KOS Orchestration

This module implements the StatefulSet controller for the KOS container
orchestration system, which manages stateful applications with stable 
identities and persistent storage.
"""

import os
import re
import copy
import time
import logging
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any, Union

from .controller import Controller, ControllerType, ControllerStatus
from .pod import Pod, PodSpec, PodPhase, PodStatus

# Logging setup
logger = logging.getLogger(__name__)


class StatefulSetUpdateStrategy:
    """Strategy for updating pods in a StatefulSet."""
    
    class Type(str, Enum):
        """StatefulSet update strategy types."""
        ROLLING_UPDATE = "RollingUpdate"
        ON_DELETE = "OnDelete"
    
    def __init__(self, type: Type = Type.ROLLING_UPDATE,
                 partition: int = 0):
        """
        Initialize a StatefulSet update strategy.
        
        Args:
            type: Strategy type
            partition: Only pods with an ordinal index greater than or equal 
                      to this value will be updated
        """
        self.type = type
        self.partition = partition
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the strategy to a dictionary.
        
        Returns:
            Dict representation of the strategy
        """
        result = {"type": self.type}
        
        if self.type == self.Type.ROLLING_UPDATE:
            result["rollingUpdate"] = {"partition": self.partition}
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatefulSetUpdateStrategy':
        """
        Create a strategy from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            StatefulSetUpdateStrategy object
        """
        strategy_type = cls.Type(data.get("type", cls.Type.ROLLING_UPDATE))
        
        partition = 0
        if strategy_type == cls.Type.ROLLING_UPDATE:
            rolling_update = data.get("rollingUpdate", {})
            partition = rolling_update.get("partition", 0)
        
        return cls(
            type=strategy_type,
            partition=partition
        )


class PersistentVolumeClaimSpec:
    """Specification for a persistent volume claim."""
    
    def __init__(self, name: str, storage_class: Optional[str] = None,
                 access_modes: Optional[List[str]] = None,
                 storage: str = "1Gi"):
        """
        Initialize a PVC specification.
        
        Args:
            name: Name of the PVC
            storage_class: Storage class for the PVC
            access_modes: Access modes (e.g., ["ReadWriteOnce"])
            storage: Storage size (e.g., "1Gi")
        """
        self.name = name
        self.storage_class = storage_class
        self.access_modes = access_modes or ["ReadWriteOnce"]
        self.storage = storage
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PVC spec to a dictionary.
        
        Returns:
            Dict representation of the PVC spec
        """
        return {
            "name": self.name,
            "storageClass": self.storage_class,
            "accessModes": self.access_modes,
            "storage": self.storage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistentVolumeClaimSpec':
        """
        Create a PVC spec from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PersistentVolumeClaimSpec object
        """
        return cls(
            name=data.get("name", ""),
            storage_class=data.get("storageClass"),
            access_modes=data.get("accessModes", ["ReadWriteOnce"]),
            storage=data.get("storage", "1Gi")
        )


class StatefulSet(Controller):
    """
    StatefulSet controller for the KOS orchestration system.
    
    A StatefulSet manages a set of Pods that have unique, persistent identities
    and stable hostnames. It's suited for applications that require stable
    network identities and persistent storage.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 selector: Optional[Dict[str, str]] = None,
                 template: Optional[Dict[str, Any]] = None,
                 volume_claim_templates: Optional[List[PersistentVolumeClaimSpec]] = None,
                 service_name: str = "",
                 replicas: int = 1,
                 update_strategy: Optional[StatefulSetUpdateStrategy] = None,
                 pod_management_policy: str = "OrderedReady",
                 revision_history_limit: int = 10,
                 status: Optional[ControllerStatus] = None,
                 uid: Optional[str] = None):
        """
        Initialize a StatefulSet controller.
        
        Args:
            name: Controller name
            namespace: Namespace
            labels: Controller labels
            annotations: Controller annotations
            selector: Label selector for pods
            template: Pod template
            volume_claim_templates: Templates for PVCs to be created
            service_name: Name of the service that governs the StatefulSet
            replicas: Desired number of replicas
            update_strategy: Update strategy
            pod_management_policy: Pod management policy (OrderedReady or Parallel)
            revision_history_limit: Number of old revisions to retain
            status: Controller status
            uid: Unique ID
        """
        super().__init__(
            name=name,
            namespace=namespace,
            labels=labels,
            annotations=annotations,
            selector=selector,
            template=template,
            replicas=replicas,
            status=status,
            uid=uid,
            controller_type=ControllerType.STATEFUL_SET
        )
        
        self.volume_claim_templates = volume_claim_templates or []
        self.service_name = service_name
        self.update_strategy = update_strategy or StatefulSetUpdateStrategy()
        self.pod_management_policy = pod_management_policy
        self.revision_history_limit = revision_history_limit
        
        # Additional status fields
        self.current_revision = ""
        self.update_revision = ""
        self.current_replicas = 0
        self.update_replicas = 0
        self.ready_replicas = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the StatefulSet to a dictionary.
        
        Returns:
            Dict representation of the StatefulSet
        """
        base_dict = super().to_dict()
        
        # Add StatefulSet-specific fields
        spec = base_dict["spec"]
        spec["volumeClaimTemplates"] = [
            vct.to_dict() for vct in self.volume_claim_templates
        ]
        spec["serviceName"] = self.service_name
        spec["updateStrategy"] = self.update_strategy.to_dict()
        spec["podManagementPolicy"] = self.pod_management_policy
        spec["revisionHistoryLimit"] = self.revision_history_limit
        
        # Add StatefulSet-specific status fields
        status = base_dict["status"]
        status["currentRevision"] = self.current_revision
        status["updateRevision"] = self.update_revision
        status["currentReplicas"] = self.current_replicas
        status["updateReplicas"] = self.update_replicas
        status["readyReplicas"] = self.ready_replicas
        
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StatefulSet':
        """
        Create a StatefulSet from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            StatefulSet object
        """
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status_data = data.get("status", {})
        
        # Parse volume claim templates
        volume_claim_templates = [
            PersistentVolumeClaimSpec.from_dict(vct)
            for vct in spec.get("volumeClaimTemplates", [])
        ]
        
        # Create StatefulSet
        stateful_set = cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            selector=spec.get("selector", {}),
            template=spec.get("template", {}),
            volume_claim_templates=volume_claim_templates,
            service_name=spec.get("serviceName", ""),
            replicas=spec.get("replicas", 1),
            update_strategy=StatefulSetUpdateStrategy.from_dict(
                spec.get("updateStrategy", {})
            ),
            pod_management_policy=spec.get("podManagementPolicy", "OrderedReady"),
            revision_history_limit=spec.get("revisionHistoryLimit", 10),
            status=ControllerStatus.from_dict(status_data),
            uid=metadata.get("uid")
        )
        
        # Set StatefulSet-specific status fields
        stateful_set.current_revision = status_data.get("currentRevision", "")
        stateful_set.update_revision = status_data.get("updateRevision", "")
        stateful_set.current_replicas = status_data.get("currentReplicas", 0)
        stateful_set.update_replicas = status_data.get("updateReplicas", 0)
        stateful_set.ready_replicas = status_data.get("readyReplicas", 0)
        
        return stateful_set
    
    def reconcile(self) -> bool:
        """
        Reconcile the desired state with the actual state.
        
        For a StatefulSet, this means creating, updating, or deleting pods
        according to the update strategy, maintaining their ordinal identities.
        
        Returns:
            bool: Whether the reconciliation was successful
        """
        try:
            with self._lock:
                # Find all pods for this StatefulSet
                pods = self._find_matching_pods()
                
                # Group pods by ordinal index
                pods_by_ordinal = {}
                for pod in pods:
                    # Extract ordinal from pod name
                    match = re.match(f"{self.name}-(\\d+)", pod.name)
                    if match:
                        ordinal = int(match.group(1))
                        pods_by_ordinal[ordinal] = pod
                
                # Determine current revision if not set
                if not self.current_revision:
                    self.current_revision = self._get_template_hash()
                
                # Check if update is needed
                if self._need_update():
                    # Set update revision
                    self.update_revision = self._get_template_hash()
                else:
                    # Keep update revision in sync with current revision
                    self.update_revision = self.current_revision
                
                # Calculate current and update replicas
                self.current_replicas = sum(
                    1 for pod in pods
                    if pod.annotations.get("kos.statefulset/revision") == self.current_revision
                )
                self.update_replicas = sum(
                    1 for pod in pods
                    if pod.annotations.get("kos.statefulset/revision") == self.update_revision
                )
                
                # Reconcile pods
                if self.update_strategy.type == StatefulSetUpdateStrategy.Type.ON_DELETE:
                    self._reconcile_on_delete(pods_by_ordinal)
                else:  # RollingUpdate
                    self._reconcile_rolling_update(pods_by_ordinal)
                
                # Update status
                self.update_status()
                
                return True
        except Exception as e:
            logger.error(f"Error reconciling StatefulSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _need_update(self) -> bool:
        """
        Check if an update is needed.
        
        Returns:
            bool: Whether an update is needed
        """
        # Check if template has changed
        current_template_hash = self.current_revision
        new_template_hash = self._get_template_hash()
        
        return current_template_hash != new_template_hash
    
    def _reconcile_on_delete(self, pods_by_ordinal: Dict[int, Pod]):
        """
        Reconcile using OnDelete strategy.
        
        This strategy only updates pods when they are manually deleted.
        
        Args:
            pods_by_ordinal: Dictionary mapping ordinal indices to pods
        """
        # Create missing pods
        self._create_missing_pods(pods_by_ordinal)
        
        # Scale down if needed
        self._scale_down_pods(pods_by_ordinal)
    
    def _reconcile_rolling_update(self, pods_by_ordinal: Dict[int, Pod]):
        """
        Reconcile using RollingUpdate strategy.
        
        This strategy updates pods in reverse ordinal order when they
        are not already at the update revision.
        
        Args:
            pods_by_ordinal: Dictionary mapping ordinal indices to pods
        """
        # Create missing pods
        self._create_missing_pods(pods_by_ordinal)
        
        # Scale down if needed
        self._scale_down_pods(pods_by_ordinal)
        
        # Update pods if needed
        self._update_pods(pods_by_ordinal)
    
    def _create_missing_pods(self, pods_by_ordinal: Dict[int, Pod]):
        """
        Create any missing pods up to the desired replica count.
        
        Args:
            pods_by_ordinal: Dictionary mapping ordinal indices to pods
        """
        # Create pods in ordinal order
        for ordinal in range(self.replicas):
            if ordinal not in pods_by_ordinal:
                # Create a new pod
                pod = self._create_pod_at_ordinal(ordinal)
                if pod.create():
                    logger.info(f"Created pod {pod.namespace}/{pod.name}")
                    
                    # Create PVCs for this pod
                    self._create_pvcs_for_pod(pod, ordinal)
                    
                    # Update pods_by_ordinal for future reference
                    pods_by_ordinal[ordinal] = pod
                    
                    # For OrderedReady policy, only create one pod at a time
                    if self.pod_management_policy == "OrderedReady":
                        # Wait for the pod to be ready before creating the next one
                        return
                else:
                    logger.error(f"Failed to create pod {pod.namespace}/{pod.name}")
    
    def _scale_down_pods(self, pods_by_ordinal: Dict[int, Pod]):
        """
        Scale down pods if the replica count has decreased.
        
        Args:
            pods_by_ordinal: Dictionary mapping ordinal indices to pods
        """
        # Find pods that exceed the replica count
        for ordinal in sorted(pods_by_ordinal.keys(), reverse=True):
            if ordinal >= self.replicas:
                pod = pods_by_ordinal[ordinal]
                
                # Delete the pod
                if pod.delete():
                    logger.info(f"Deleted pod {pod.namespace}/{pod.name}")
                    
                    # For OrderedReady policy, only delete one pod at a time
                    if self.pod_management_policy == "OrderedReady":
                        return
                else:
                    logger.error(f"Failed to delete pod {pod.namespace}/{pod.name}")
    
    def _update_pods(self, pods_by_ordinal: Dict[int, Pod]):
        """
        Update pods according to the update strategy.
        
        Args:
            pods_by_ordinal: Dictionary mapping ordinal indices to pods
        """
        # For RollingUpdate, only update pods with ordinal >= partition
        partition = self.update_strategy.partition
        
        # Update pods in reverse ordinal order
        for ordinal in sorted(pods_by_ordinal.keys(), reverse=True):
            if ordinal >= partition:
                pod = pods_by_ordinal[ordinal]
                
                # Check if pod needs update
                current_revision = pod.annotations.get("kos.statefulset/revision", "")
                if current_revision != self.update_revision:
                    # Delete the pod to trigger an update
                    if pod.delete():
                        logger.info(f"Deleting pod {pod.namespace}/{pod.name} for update")
                        
                        # For OrderedReady policy, only update one pod at a time
                        if self.pod_management_policy == "OrderedReady":
                            return
                    else:
                        logger.error(f"Failed to delete pod {pod.namespace}/{pod.name} for update")
    
    def _create_pod_at_ordinal(self, ordinal: int) -> Pod:
        """
        Create a pod at the specified ordinal index.
        
        Args:
            ordinal: Ordinal index
            
        Returns:
            Created pod
        """
        # Generate pod name
        pod_name = f"{self.name}-{ordinal}"
        
        # Clone the template
        template = copy.deepcopy(self.template)
        
        # Set metadata
        metadata = template.get("metadata", {}).copy()
        metadata["name"] = pod_name
        metadata["namespace"] = self.namespace
        
        # Add StatefulSet labels and annotations
        labels = metadata.get("labels", {}).copy()
        labels.update(self.selector)
        metadata["labels"] = labels
        
        annotations = metadata.get("annotations", {}).copy()
        annotations["kos.statefulset/name"] = self.name
        annotations["kos.statefulset/uid"] = self.uid
        annotations["kos.statefulset/revision"] = self.update_revision
        annotations["kos.statefulset/pod-name"] = pod_name
        metadata["annotations"] = annotations
        
        # Set hostname and subdomain for DNS
        spec = template.get("spec", {}).copy()
        spec["hostname"] = pod_name
        
        if self.service_name:
            spec["subdomain"] = self.service_name
        
        # Update template with metadata and spec
        template["metadata"] = metadata
        template["spec"] = spec
        
        # Create pod
        pod = Pod(
            name=pod_name,
            namespace=self.namespace,
            spec=PodSpec.from_dict(spec),
            labels=labels,
            annotations=annotations,
            owner_reference={
                "kind": self.controller_type,
                "name": self.name,
                "uid": self.uid
            }
        )
        
        return pod
    
    def _create_pvcs_for_pod(self, pod: Pod, ordinal: int) -> bool:
        """
        Create PVCs for a pod.
        
        Args:
            pod: Pod to create PVCs for
            ordinal: Ordinal index
            
        Returns:
            bool: Success or failure
        """
        # Check if we have any volume claim templates
        if not self.volume_claim_templates:
            return True
        
        try:
            # Import PVC class here to avoid circular imports
            from ..storage.volume import PersistentVolumeClaim
            
            # Create PVCs for each template
            for vct in self.volume_claim_templates:
                # Generate PVC name
                pvc_name = f"{vct.name}-{self.name}-{ordinal}"
                
                # Create PVC
                pvc = PersistentVolumeClaim(
                    name=pvc_name,
                    namespace=self.namespace,
                    storage_class=vct.storage_class,
                    access_modes=vct.access_modes,
                    storage=vct.storage,
                    labels={
                        "app": self.name,
                        "kos.statefulset/name": self.name,
                        "kos.statefulset/pod-name": pod.name,
                        "kos.statefulset/ordinal": str(ordinal)
                    },
                    annotations={
                        "kos.statefulset/name": self.name,
                        "kos.statefulset/uid": self.uid,
                        "kos.statefulset/pod-name": pod.name
                    }
                )
                
                if pvc.create():
                    logger.info(f"Created PVC {pvc.namespace}/{pvc.name} for pod {pod.namespace}/{pod.name}")
                else:
                    logger.error(f"Failed to create PVC for pod {pod.namespace}/{pod.name}")
                    return False
            
            return True
        except ImportError:
            logger.error("PersistentVolumeClaim class not available")
            return False
        except Exception as e:
            logger.error(f"Error creating PVCs: {e}")
            return False
    
    def update_status(self) -> bool:
        """
        Update the StatefulSet status based on pod states.
        
        Returns:
            bool: Whether the status changed
        """
        with self._lock:
            old_status = self.status.to_dict()
            
            # Find matching pods
            pods = self._find_matching_pods()
            
            # Count pods
            total = len(pods)
            ready = sum(
                1 for pod in pods
                if all(cs.ready for cs in pod.status.container_statuses)
                if pod.status.container_statuses
            )
            
            # Count pods by revision
            current_revision_pods = [
                pod for pod in pods
                if pod.annotations.get("kos.statefulset/revision") == self.current_revision
            ]
            update_revision_pods = [
                pod for pod in pods
                if pod.annotations.get("kos.statefulset/revision") == self.update_revision
            ]
            
            # Update status
            self.status.replicas = total
            self.status.ready_replicas = ready
            self.current_replicas = len(current_revision_pods)
            self.update_replicas = len(update_revision_pods)
            self.ready_replicas = ready
            
            # Check if status changed
            changed = (old_status != self.status.to_dict())
            
            if changed:
                self.save()
            
            return changed

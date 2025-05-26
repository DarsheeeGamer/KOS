"""
Deployment Controller for KOS Orchestration

This module implements the Deployment controller for the KOS container
orchestration system, which provides declarative updates for ReplicaSets.
"""

import os
import time
import json
import copy
import hashlib
import logging
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Set

from .controller import Controller, ControllerType, ControllerStatus
from .replica_set import ReplicaSet
from .pod import Pod, PodPhase

# Logging setup
logger = logging.getLogger(__name__)


class DeploymentStrategyType(str, Enum):
    """Deployment strategy types."""
    RECREATE = "Recreate"
    ROLLING_UPDATE = "RollingUpdate"


class DeploymentConditionType(str, Enum):
    """Deployment condition types."""
    AVAILABLE = "Available"
    PROGRESSING = "Progressing"
    REPLICAFAILURE = "ReplicaFailure"


class RollingUpdateStrategy:
    """Configuration for a rolling update."""
    
    def __init__(self, max_unavailable: Optional[int] = None,
                 max_surge: Optional[int] = None):
        """
        Initialize a rolling update strategy.
        
        Args:
            max_unavailable: Maximum number of unavailable pods
            max_surge: Maximum number of pods that can be created over the desired number
        """
        self.max_unavailable = max_unavailable or 1
        self.max_surge = max_surge or 1
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the strategy to a dictionary.
        
        Returns:
            Dict representation of the strategy
        """
        return {
            "maxUnavailable": self.max_unavailable,
            "maxSurge": self.max_surge
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RollingUpdateStrategy':
        """
        Create a strategy from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            RollingUpdateStrategy object
        """
        return RollingUpdateStrategy(
            max_unavailable=data.get("maxUnavailable", 1),
            max_surge=data.get("maxSurge", 1)
        )


class DeploymentStrategy:
    """Strategy for updating pods during a deployment."""
    
    def __init__(self, type: DeploymentStrategyType = DeploymentStrategyType.ROLLING_UPDATE,
                 rolling_update: Optional[RollingUpdateStrategy] = None):
        """
        Initialize a deployment strategy.
        
        Args:
            type: Strategy type
            rolling_update: Rolling update configuration (only used with RollingUpdate type)
        """
        self.type = type
        self.rolling_update = rolling_update or RollingUpdateStrategy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the strategy to a dictionary.
        
        Returns:
            Dict representation of the strategy
        """
        result = {"type": self.type}
        
        if self.type == DeploymentStrategyType.ROLLING_UPDATE:
            result["rollingUpdate"] = self.rolling_update.to_dict()
        
        return result
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DeploymentStrategy':
        """
        Create a strategy from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DeploymentStrategy object
        """
        strategy_type = DeploymentStrategyType(data.get("type", "RollingUpdate"))
        
        rolling_update = None
        if strategy_type == DeploymentStrategyType.ROLLING_UPDATE:
            rolling_update = RollingUpdateStrategy.from_dict(
                data.get("rollingUpdate", {})
            )
        
        return DeploymentStrategy(
            type=strategy_type,
            rolling_update=rolling_update
        )


class Deployment(Controller):
    """
    Deployment controller for the KOS orchestration system.
    
    A Deployment provides declarative updates for Pods and ReplicaSets,
    allowing for controlled rollouts and rollbacks.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 selector: Optional[Dict[str, str]] = None,
                 template: Optional[Dict[str, Any]] = None,
                 replicas: int = 1,
                 strategy: Optional[DeploymentStrategy] = None,
                 min_ready_seconds: int = 0,
                 revision_history_limit: int = 10,
                 paused: bool = False,
                 progress_deadline_seconds: int = 600,
                 status: Optional[ControllerStatus] = None,
                 uid: Optional[str] = None):
        """
        Initialize a Deployment controller.
        
        Args:
            name: Controller name
            namespace: Namespace
            labels: Controller labels
            annotations: Controller annotations
            selector: Label selector for pods
            template: Pod template
            replicas: Desired number of replicas
            strategy: Deployment strategy
            min_ready_seconds: Minimum seconds a pod should be ready before considered available
            revision_history_limit: Number of old ReplicaSets to retain
            paused: Whether the deployment is paused
            progress_deadline_seconds: Maximum time for a deployment to progress before it's considered failed
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
            controller_type=ControllerType.DEPLOYMENT
        )
        
        self.strategy = strategy or DeploymentStrategy()
        self.min_ready_seconds = min_ready_seconds
        self.revision_history_limit = revision_history_limit
        self.paused = paused
        self.progress_deadline_seconds = progress_deadline_seconds
        
        # Additional status fields
        self.revision = 1
        self.collisions = 0
        
        # Runtime fields
        self._replica_sets = {}  # revision -> ReplicaSet
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the deployment to a dictionary.
        
        Returns:
            Dict representation of the deployment
        """
        base_dict = super().to_dict()
        
        # Add deployment-specific fields
        spec = base_dict["spec"]
        spec["strategy"] = self.strategy.to_dict()
        spec["minReadySeconds"] = self.min_ready_seconds
        spec["revisionHistoryLimit"] = self.revision_history_limit
        spec["paused"] = self.paused
        spec["progressDeadlineSeconds"] = self.progress_deadline_seconds
        
        # Add deployment-specific status fields
        status = base_dict["status"]
        status["revision"] = self.revision
        status["collisions"] = self.collisions
        
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Deployment':
        """
        Create a deployment from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Deployment object
        """
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status_data = data.get("status", {})
        
        # Create base controller
        deployment = cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            selector=spec.get("selector", {}),
            template=spec.get("template", {}),
            replicas=spec.get("replicas", 1),
            strategy=DeploymentStrategy.from_dict(spec.get("strategy", {})),
            min_ready_seconds=spec.get("minReadySeconds", 0),
            revision_history_limit=spec.get("revisionHistoryLimit", 10),
            paused=spec.get("paused", False),
            progress_deadline_seconds=spec.get("progressDeadlineSeconds", 600),
            status=ControllerStatus.from_dict(status_data),
            uid=metadata.get("uid")
        )
        
        # Set deployment-specific status fields
        deployment.revision = status_data.get("revision", 1)
        deployment.collisions = status_data.get("collisions", 0)
        
        return deployment
    
    def reconcile(self) -> bool:
        """
        Reconcile the desired state with the actual state.
        
        For a Deployment, this means managing ReplicaSets to achieve
        the desired state according to the deployment strategy.
        
        Returns:
            bool: Whether the reconciliation was successful
        """
        try:
            with self._lock:
                # Skip reconciliation if paused
                if self.paused:
                    logger.info(f"Deployment {self.namespace}/{self.name} is paused")
                    return True
                
                # Load all ReplicaSets for this deployment
                self._load_replica_sets()
                
                # Get the current and old ReplicaSets
                current_rs = self._get_new_replica_set()
                old_rs_list = self._get_old_replica_sets()
                
                # Update revision if necessary
                new_revision = self._next_revision()
                
                # Check if we need to create or update the current ReplicaSet
                if not current_rs:
                    # Create a new ReplicaSet
                    logger.info(f"Creating new ReplicaSet for deployment {self.namespace}/{self.name}")
                    current_rs = self._create_new_replica_set(new_revision)
                elif self._need_new_replica_set(current_rs):
                    # Create a new ReplicaSet with updated template
                    logger.info(f"Updating ReplicaSet for deployment {self.namespace}/{self.name}")
                    
                    # Add current ReplicaSet to old list
                    old_rs_list.append(current_rs)
                    
                    # Create new ReplicaSet
                    current_rs = self._create_new_replica_set(new_revision)
                
                # Scale ReplicaSets according to strategy
                if self.strategy.type == DeploymentStrategyType.RECREATE:
                    self._reconcile_recreate(current_rs, old_rs_list)
                else:  # RollingUpdate
                    self._reconcile_rolling_update(current_rs, old_rs_list)
                
                # Clean up old ReplicaSets
                self._cleanup_old_replica_sets(current_rs, old_rs_list)
                
                # Update status
                self.update_status()
                
                return True
        except Exception as e:
            logger.error(f"Error reconciling Deployment {self.namespace}/{self.name}: {e}")
            return False
    
    def _load_replica_sets(self):
        """Load all ReplicaSets for this deployment."""
        # Find ReplicaSets owned by this deployment
        all_rs = ReplicaSet.list_controllers(
            namespace=self.namespace,
            controller_type=ControllerType.REPLICA_SET
        )
        
        for rs in all_rs:
            # Check if this ReplicaSet is owned by this deployment
            owner_refs = rs.annotations.get("kos.deployment/owner")
            if owner_refs and owner_refs == self.uid:
                # Get revision
                revision = rs.annotations.get("kos.deployment/revision")
                if revision and revision.isdigit():
                    revision = int(revision)
                    self._replica_sets[revision] = rs
    
    def _get_new_replica_set(self) -> Optional[ReplicaSet]:
        """
        Get the current (newest) ReplicaSet.
        
        Returns:
            Current ReplicaSet or None if not found
        """
        if not self._replica_sets:
            return None
        
        # Find the ReplicaSet with the highest revision
        return self._replica_sets.get(max(self._replica_sets.keys()))
    
    def _get_old_replica_sets(self) -> List[ReplicaSet]:
        """
        Get the old ReplicaSets.
        
        Returns:
            List of old ReplicaSets
        """
        if not self._replica_sets:
            return []
        
        # Get all ReplicaSets except the newest one
        max_revision = max(self._replica_sets.keys())
        
        return [
            rs for rev, rs in self._replica_sets.items()
            if rev != max_revision
        ]
    
    def _next_revision(self) -> int:
        """
        Get the next revision number.
        
        Returns:
            Next revision number
        """
        if not self._replica_sets:
            return 1
        
        return max(self._replica_sets.keys()) + 1
    
    def _create_new_replica_set(self, revision: int) -> ReplicaSet:
        """
        Create a new ReplicaSet for this deployment.
        
        Args:
            revision: Revision number
            
        Returns:
            Created ReplicaSet
        """
        # Generate a name for the ReplicaSet
        template_hash = self._get_template_hash()
        rs_name = f"{self.name}-{template_hash}"
        
        # Check for name collision
        while any(rs.name == rs_name for rs in self._replica_sets.values()):
            # Append a suffix to resolve collision
            rs_name = f"{rs_name}-{self.collisions}"
            self.collisions += 1
        
        # Create ReplicaSet
        rs = ReplicaSet(
            name=rs_name,
            namespace=self.namespace,
            labels=self.labels.copy(),
            annotations={
                "kos.deployment/name": self.name,
                "kos.deployment/uid": self.uid,
                "kos.deployment/revision": str(revision),
                "kos.deployment/template-hash": template_hash
            },
            selector=self.selector.copy(),
            template=copy.deepcopy(self.template),
            replicas=0  # Start with 0 replicas, will scale up according to strategy
        )
        
        # Save ReplicaSet
        if rs.save():
            logger.info(f"Created ReplicaSet {rs.namespace}/{rs.name} for deployment {self.namespace}/{self.name}")
            
            # Add to ReplicaSets map
            self._replica_sets[revision] = rs
            
            # Update deployment revision
            self.revision = revision
            
            return rs
        else:
            logger.error(f"Failed to create ReplicaSet for deployment {self.namespace}/{self.name}")
            raise Exception("Failed to create ReplicaSet")
    
    def _need_new_replica_set(self, current_rs: ReplicaSet) -> bool:
        """
        Check if a new ReplicaSet is needed.
        
        Args:
            current_rs: Current ReplicaSet
            
        Returns:
            True if a new ReplicaSet is needed, False otherwise
        """
        # Check if template has changed
        current_template_hash = current_rs.annotations.get("kos.deployment/template-hash")
        new_template_hash = self._get_template_hash()
        
        return current_template_hash != new_template_hash
    
    def _reconcile_recreate(self, current_rs: ReplicaSet, old_rs_list: List[ReplicaSet]):
        """
        Reconcile using Recreate strategy.
        
        This strategy scales down all old ReplicaSets to 0 before
        scaling up the new ReplicaSet.
        
        Args:
            current_rs: Current ReplicaSet
            old_rs_list: List of old ReplicaSets
        """
        # Scale down old ReplicaSets
        for rs in old_rs_list:
            if rs.replicas > 0:
                logger.info(f"Scaling down old ReplicaSet {rs.namespace}/{rs.name}")
                rs.scale(0)
                return  # Wait for next reconciliation cycle
        
        # Scale up current ReplicaSet
        if current_rs.replicas != self.replicas:
            logger.info(f"Scaling up current ReplicaSet {current_rs.namespace}/{current_rs.name}")
            current_rs.scale(self.replicas)
    
    def _reconcile_rolling_update(self, current_rs: ReplicaSet, old_rs_list: List[ReplicaSet]):
        """
        Reconcile using RollingUpdate strategy.
        
        This strategy gradually scales up the new ReplicaSet while
        scaling down old ReplicaSets.
        
        Args:
            current_rs: Current ReplicaSet
            old_rs_list: List of old ReplicaSets
        """
        # Calculate total replicas
        total_replicas = sum(rs.replicas for rs in [current_rs] + old_rs_list)
        
        # Get max surge and max unavailable
        max_surge = self.strategy.rolling_update.max_surge
        max_unavailable = self.strategy.rolling_update.max_unavailable
        
        # Calculate max total replicas
        max_total = self.replicas + max_surge
        
        # Calculate min available replicas
        min_available = max(0, self.replicas - max_unavailable)
        
        # Calculate total available replicas
        available_replicas = sum(
            min(rs.replicas, rs.status.available_replicas)
            for rs in [current_rs] + old_rs_list
        )
        
        # Check if we need to scale up or down
        if total_replicas > max_total:
            # Need to scale down something
            excess = total_replicas - max_total
            
            # Scale down old ReplicaSets first
            for rs in old_rs_list:
                if rs.replicas > 0 and excess > 0:
                    scale_down = min(rs.replicas, excess)
                    logger.info(f"Scaling down old ReplicaSet {rs.namespace}/{rs.name} by {scale_down}")
                    rs.scale(rs.replicas - scale_down)
                    excess -= scale_down
                    
                    if excess <= 0:
                        break
        
        elif available_replicas < min_available:
            # Need to scale up current ReplicaSet
            needed = min_available - available_replicas
            
            # Calculate how many more replicas we can add
            can_add = max_total - total_replicas
            
            if can_add > 0:
                scale_up = min(needed, can_add)
                logger.info(f"Scaling up current ReplicaSet {current_rs.namespace}/{current_rs.name} by {scale_up}")
                current_rs.scale(current_rs.replicas + scale_up)
        
        elif current_rs.replicas < self.replicas:
            # Current ReplicaSet isn't fully scaled up yet
            
            # Calculate how many more replicas we can add
            can_add = min(self.replicas - current_rs.replicas, max_total - total_replicas)
            
            if can_add > 0:
                logger.info(f"Scaling up current ReplicaSet {current_rs.namespace}/{current_rs.name} by {can_add}")
                current_rs.scale(current_rs.replicas + can_add)
        
        else:
            # Everything is scaled correctly, just clean up old ReplicaSets
            for rs in old_rs_list:
                if rs.replicas > 0:
                    logger.info(f"Scaling down old ReplicaSet {rs.namespace}/{rs.name}")
                    rs.scale(0)
                    break  # Only scale down one at a time
    
    def _cleanup_old_replica_sets(self, current_rs: ReplicaSet, old_rs_list: List[ReplicaSet]):
        """
        Clean up old ReplicaSets.
        
        This method deletes old ReplicaSets that are no longer needed,
        keeping only the number specified by revision_history_limit.
        
        Args:
            current_rs: Current ReplicaSet
            old_rs_list: List of old ReplicaSets
        """
        # Keep only revision_history_limit old ReplicaSets
        if len(old_rs_list) <= self.revision_history_limit:
            return
        
        # Sort old ReplicaSets by revision (oldest first)
        old_rs_list.sort(key=lambda rs: int(rs.annotations.get("kos.deployment/revision", "0")))
        
        # Delete excess old ReplicaSets
        to_delete = old_rs_list[:len(old_rs_list) - self.revision_history_limit]
        
        for rs in to_delete:
            # Only delete if scaled down to 0
            if rs.replicas == 0 and rs.status.replicas == 0:
                logger.info(f"Deleting old ReplicaSet {rs.namespace}/{rs.name}")
                rs.delete()
                
                # Remove from replica_sets map
                revision = int(rs.annotations.get("kos.deployment/revision", "0"))
                if revision in self._replica_sets:
                    del self._replica_sets[revision]
    
    def _update_conditions(self):
        """Update deployment status conditions."""
        # Find existing conditions by type
        conditions_by_type = {
            cond["type"]: cond for cond in self.status.conditions
        }
        
        # Update Progressing condition
        progressing = conditions_by_type.get("Progressing", {
            "type": "Progressing",
            "status": "True",
            "lastTransitionTime": time.time(),
            "reason": "NewReplicaSetCreated",
            "message": "Deployment is progressing"
        })
        
        # Check if deployment is complete
        current_rs = self._get_new_replica_set()
        if current_rs and current_rs.replicas == self.replicas and current_rs.status.available_replicas == self.replicas:
            progressing["status"] = "True"
            progressing["reason"] = "NewReplicaSetAvailable"
            progressing["message"] = "Deployment is complete"
        
        # Update Available condition
        available = conditions_by_type.get("Available", {
            "type": "Available",
            "status": "False",
            "lastTransitionTime": time.time(),
            "reason": "MinimumReplicasUnavailable",
            "message": "Deployment does not have minimum availability"
        })
        
        # Check if deployment is available
        if self.status.available_replicas >= self.replicas:
            available["status"] = "True"
            available["reason"] = "MinimumReplicasAvailable"
            available["message"] = "Deployment has minimum availability"
        
        # Add or update conditions
        for condition_type, condition in [
            ("Progressing", progressing),
            ("Available", available)
        ]:
            if condition_type not in conditions_by_type:
                self.status.conditions.append(condition)
            else:
                for i, cond in enumerate(self.status.conditions):
                    if cond["type"] == condition_type:
                        self.status.conditions[i] = condition
                        break
    
    def rollout_status(self) -> Tuple[str, bool]:
        """
        Get the rollout status.
        
        Returns:
            Tuple of (status message, whether rollout is complete)
        """
        # Get current and old ReplicaSets
        current_rs = self._get_new_replica_set()
        
        if not current_rs:
            return "Waiting for rollout to start", False
        
        # Check if rollout is paused
        if self.paused:
            return "Rollout is paused", False
        
        # Check if rollout is complete
        if current_rs.replicas == self.replicas and current_rs.status.available_replicas == self.replicas:
            return "Rollout complete", True
        
        # Calculate progress
        if self.replicas > 0:
            percent = (current_rs.status.available_replicas * 100) // self.replicas
        else:
            percent = 100
        
        return f"Rollout in progress ({percent}%)", False
    
    def pause(self) -> bool:
        """
        Pause the deployment rollout.
        
        Returns:
            bool: Success or failure
        """
        if self.paused:
            logger.warning(f"Deployment {self.namespace}/{self.name} is already paused")
            return False
        
        self.paused = True
        self.save()
        
        logger.info(f"Paused deployment {self.namespace}/{self.name}")
        return True
    
    def resume(self) -> bool:
        """
        Resume the deployment rollout.
        
        Returns:
            bool: Success or failure
        """
        if not self.paused:
            logger.warning(f"Deployment {self.namespace}/{self.name} is not paused")
            return False
        
        self.paused = False
        self.save()
        
        logger.info(f"Resumed deployment {self.namespace}/{self.name}")
        return True
    
    def rollback(self, revision: Optional[int] = None) -> bool:
        """
        Rollback the deployment to a previous revision.
        
        Args:
            revision: Target revision, or None for previous revision
            
        Returns:
            bool: Success or failure
        """
        try:
            # Load all ReplicaSets
            self._load_replica_sets()
            
            # Determine target revision
            if revision is None:
                # Get current revision
                current_revision = self.revision
                
                # Find the previous revision
                revisions = sorted(self._replica_sets.keys())
                if len(revisions) < 2:
                    logger.error(f"No previous revision found for deployment {self.namespace}/{self.name}")
                    return False
                
                # Get the revision before the current one
                idx = revisions.index(current_revision)
                if idx <= 0:
                    logger.error(f"No previous revision found for deployment {self.namespace}/{self.name}")
                    return False
                
                target_revision = revisions[idx - 1]
            else:
                # Use specified revision
                if revision not in self._replica_sets:
                    logger.error(f"Revision {revision} not found for deployment {self.namespace}/{self.name}")
                    return False
                
                target_revision = revision
            
            # Get target ReplicaSet
            target_rs = self._replica_sets[target_revision]
            
            # Update deployment template from target ReplicaSet
            self.template = copy.deepcopy(target_rs.template)
            
            # Increment generation
            self.generation += 1
            
            # Save deployment
            self.save()
            
            logger.info(f"Rolled back deployment {self.namespace}/{self.name} to revision {target_revision}")
            return True
        except Exception as e:
            logger.error(f"Failed to rollback deployment {self.namespace}/{self.name}: {e}")
            return False

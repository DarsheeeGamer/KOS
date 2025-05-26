"""
ReplicaSet Controller for KOS Orchestration

This module implements the ReplicaSet controller for the KOS container
orchestration system, which maintains a stable set of replica pods.
"""

import logging
from typing import Dict, List, Optional, Any

from .controller import Controller, ControllerType, ControllerStatus
from .pod import Pod, PodPhase

# Logging setup
logger = logging.getLogger(__name__)


class ReplicaSet(Controller):
    """
    ReplicaSet controller for the KOS orchestration system.
    
    A ReplicaSet ensures that a specified number of pod replicas are
    running at any given time.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 selector: Optional[Dict[str, str]] = None,
                 template: Optional[Dict[str, Any]] = None,
                 replicas: int = 1,
                 status: Optional[ControllerStatus] = None,
                 uid: Optional[str] = None):
        """
        Initialize a ReplicaSet controller.
        
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
            controller_type=ControllerType.REPLICA_SET
        )
    
    def reconcile(self) -> bool:
        """
        Reconcile the desired state with the actual state.
        
        For a ReplicaSet, this means ensuring that the correct number of
        pods are running to match the desired replica count.
        
        Returns:
            bool: Whether the reconciliation was successful
        """
        try:
            with self._lock:
                # Find matching pods
                matching_pods = self._find_matching_pods()
                
                # Count active pods (not terminating)
                active_pods = [
                    pod for pod in matching_pods 
                    if pod.status.phase != PodPhase.TERMINATING
                ]
                
                # Scale up or down as needed
                if len(active_pods) < self.replicas:
                    # Need to create more pods
                    to_create = self.replicas - len(active_pods)
                    logger.info(f"ReplicaSet {self.namespace}/{self.name} scaling up: {to_create} pods")
                    
                    for i in range(to_create):
                        # Get the highest index of existing pods
                        existing_indices = [
                            int(pod.name.split('-')[-1])
                            for pod in matching_pods
                            if pod.name.startswith(f"{self.name}-")
                               and pod.name.split('-')[-1].isdigit()
                        ]
                        next_index = max(existing_indices) + 1 if existing_indices else 0
                        
                        # Create a new pod
                        pod = self._create_pod_from_template(next_index)
                        if pod.create():
                            logger.info(f"Created pod {pod.namespace}/{pod.name}")
                        else:
                            logger.error(f"Failed to create pod {pod.namespace}/{pod.name}")
                            
                elif len(active_pods) > self.replicas:
                    # Need to delete some pods
                    to_delete = len(active_pods) - self.replicas
                    logger.info(f"ReplicaSet {self.namespace}/{self.name} scaling down: {to_delete} pods")
                    
                    # Sort pods by creation time (delete newest first)
                    pods_to_delete = sorted(
                        active_pods,
                        key=lambda p: p.creation_timestamp,
                        reverse=True
                    )[:to_delete]
                    
                    for pod in pods_to_delete:
                        if pod.delete():
                            logger.info(f"Deleted pod {pod.namespace}/{pod.name}")
                        else:
                            logger.error(f"Failed to delete pod {pod.namespace}/{pod.name}")
                
                # Update status
                self.update_status()
                
                return True
        except Exception as e:
            logger.error(f"Error reconciling ReplicaSet {self.namespace}/{self.name}: {e}")
            return False
    
    def _update_conditions(self):
        """Update ReplicaSet status conditions."""
        # Find existing conditions by type
        conditions_by_type = {
            cond["type"]: cond for cond in self.status.conditions
        }
        
        # Update ReplicaFailure condition
        replica_failure = conditions_by_type.get("ReplicaFailure", {
            "type": "ReplicaFailure",
            "status": "False",
            "lastTransitionTime": 0,
            "reason": "",
            "message": ""
        })
        
        # Check for pod failures
        failed_pods = [
            pod for pod in self._find_matching_pods()
            if pod.status.phase == PodPhase.FAILED
        ]
        
        if failed_pods:
            pod_names = ", ".join(pod.name for pod in failed_pods)
            replica_failure["status"] = "True"
            replica_failure["reason"] = "PodsFailure"
            replica_failure["message"] = f"Pods failed: {pod_names}"
        else:
            replica_failure["status"] = "False"
            replica_failure["reason"] = ""
            replica_failure["message"] = ""
        
        # Add or update conditions
        if "ReplicaFailure" not in conditions_by_type:
            self.status.conditions.append(replica_failure)
        else:
            for i, cond in enumerate(self.status.conditions):
                if cond["type"] == "ReplicaFailure":
                    self.status.conditions[i] = replica_failure
                    break

"""
Horizontal Pod Autoscaler for KOS Orchestration System

This module implements horizontal pod autoscaling for the KOS orchestration system,
allowing automatic scaling of pods based on resource utilization metrics.
"""

import os
import json
import time
import logging
import threading
import math
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from kos.core.orchestration.controllers.deployment import Deployment
from kos.core.orchestration.controllers.replicaset import ReplicaSet
from kos.core.orchestration.controllers.statefulset import StatefulSet
from kos.core.monitoring.metrics import MetricsCollector, Metric

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
AUTOSCALER_PATH = os.path.join(ORCHESTRATION_ROOT, 'autoscaler')
HPA_PATH = os.path.join(AUTOSCALER_PATH, 'hpa')

# Ensure directories exist
os.makedirs(HPA_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class MetricSpec:
    """Specification for a metric source."""
    
    def __init__(self, type: str, resource_name: Optional[str] = None,
                target_type: str = "Utilization", target_value: int = 50):
        """
        Initialize a metric specification.
        
        Args:
            type: Metric type (e.g., "Resource", "Pods", "Object")
            resource_name: Resource name (e.g., "cpu", "memory")
            target_type: Target type (e.g., "Utilization", "AverageValue", "Value")
            target_value: Target value
        """
        self.type = type
        self.resource_name = resource_name
        self.target_type = target_type
        self.target_value = target_value
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the metric specification to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "type": self.type,
            "target": {
                "type": self.target_type,
                "value": self.target_value
            }
        }
        
        if self.resource_name:
            result["resource"] = {"name": self.resource_name}
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetricSpec':
        """
        Create a metric specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            MetricSpec object
        """
        metric_type = data.get("type", "Resource")
        
        resource_name = None
        if "resource" in data:
            resource_name = data["resource"].get("name")
        
        target = data.get("target", {})
        target_type = target.get("type", "Utilization")
        target_value = target.get("value", 50)
        
        return cls(
            type=metric_type,
            resource_name=resource_name,
            target_type=target_type,
            target_value=target_value
        )


class HPAStatus:
    """Status of a horizontal pod autoscaler."""
    
    def __init__(self, current_replicas: int = 0, desired_replicas: int = 0,
                last_scale_time: Optional[float] = None,
                current_metrics: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize HPA status.
        
        Args:
            current_replicas: Current number of replicas
            desired_replicas: Desired number of replicas
            last_scale_time: Last time the HPA scaled the resource
            current_metrics: Current values of metrics used by the HPA
        """
        self.current_replicas = current_replicas
        self.desired_replicas = desired_replicas
        self.last_scale_time = last_scale_time
        self.current_metrics = current_metrics or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the HPA status to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "currentReplicas": self.current_replicas,
            "desiredReplicas": self.desired_replicas,
            "lastScaleTime": self.last_scale_time,
            "currentMetrics": self.current_metrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HPAStatus':
        """
        Create an HPA status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            HPAStatus object
        """
        return cls(
            current_replicas=data.get("currentReplicas", 0),
            desired_replicas=data.get("desiredReplicas", 0),
            last_scale_time=data.get("lastScaleTime"),
            current_metrics=data.get("currentMetrics", [])
        )


class HPASpec:
    """Specification for a horizontal pod autoscaler."""
    
    def __init__(self, scale_target_ref: Dict[str, str], min_replicas: int = 1,
                max_replicas: int = 10, metrics: Optional[List[MetricSpec]] = None,
                scale_down_stabilization_window_seconds: int = 300,
                scale_up_stabilization_window_seconds: int = 0):
        """
        Initialize an HPA specification.
        
        Args:
            scale_target_ref: Reference to the target to scale
            min_replicas: Minimum number of replicas
            max_replicas: Maximum number of replicas
            metrics: List of metrics to use for scaling
            scale_down_stabilization_window_seconds: Window to wait before scaling down
            scale_up_stabilization_window_seconds: Window to wait before scaling up
        """
        self.scale_target_ref = scale_target_ref
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.metrics = metrics or []
        self.scale_down_stabilization_window_seconds = scale_down_stabilization_window_seconds
        self.scale_up_stabilization_window_seconds = scale_up_stabilization_window_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the HPA specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "scaleTargetRef": self.scale_target_ref,
            "minReplicas": self.min_replicas,
            "maxReplicas": self.max_replicas,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "behavior": {
                "scaleDown": {
                    "stabilizationWindowSeconds": self.scale_down_stabilization_window_seconds
                },
                "scaleUp": {
                    "stabilizationWindowSeconds": self.scale_up_stabilization_window_seconds
                }
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HPASpec':
        """
        Create an HPA specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            HPASpec object
        """
        metrics = []
        for metric_data in data.get("metrics", []):
            metrics.append(MetricSpec.from_dict(metric_data))
        
        behavior = data.get("behavior", {})
        scale_down = behavior.get("scaleDown", {})
        scale_up = behavior.get("scaleUp", {})
        
        return cls(
            scale_target_ref=data.get("scaleTargetRef", {}),
            min_replicas=data.get("minReplicas", 1),
            max_replicas=data.get("maxReplicas", 10),
            metrics=metrics,
            scale_down_stabilization_window_seconds=scale_down.get("stabilizationWindowSeconds", 300),
            scale_up_stabilization_window_seconds=scale_up.get("stabilizationWindowSeconds", 0)
        )


class HorizontalPodAutoscaler:
    """
    Horizontal pod autoscaler resource in the KOS orchestration system.
    
    A HorizontalPodAutoscaler automatically scales the number of pods in a target
    (e.g., a Deployment or StatefulSet) based on observed CPU utilization or other
    metrics.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[HPASpec] = None):
        """
        Initialize a horizontal pod autoscaler.
        
        Args:
            name: HPA name
            namespace: Namespace
            spec: HPA specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or HPASpec({})
        self.status = HPAStatus()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": "",
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Metrics collector
        self._metrics_collector = MetricsCollector.instance()
        
        # Scale history
        self._scale_history: List[Tuple[float, int]] = []
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this HPA."""
        return os.path.join(HPA_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the HPA from disk.
        
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
            self.spec = HPASpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = HPAStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load HPA {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the HPA to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "HorizontalPodAutoscaler",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save HPA {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the HPA.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete HPA {self.namespace}/{self.name}: {e}")
            return False
    
    def reconcile(self) -> bool:
        """
        Reconcile the HPA to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Get target resource
                target = self._get_scale_target()
                if not target:
                    logger.error(f"Scale target not found for HPA {self.namespace}/{self.name}")
                    return False
                
                # Get current metrics
                current_metrics = self._get_current_metrics(target)
                
                # Update status metrics
                self.status.current_metrics = current_metrics
                
                # Determine desired replicas
                desired_replicas = self._calculate_desired_replicas(target, current_metrics)
                
                # Apply scale stabilization
                desired_replicas = self._apply_scale_stabilization(desired_replicas)
                
                # Clamp desired replicas
                desired_replicas = max(self.spec.min_replicas, min(self.spec.max_replicas, desired_replicas))
                
                # Update status
                self.status.current_replicas = self._get_current_replicas(target)
                self.status.desired_replicas = desired_replicas
                
                # Scale target if needed
                if self.status.current_replicas != desired_replicas:
                    if self._scale_target(target, desired_replicas):
                        self.status.last_scale_time = time.time()
                        self._scale_history.append((time.time(), desired_replicas))
                
                # Save updated status
                self.save()
                
                return True
        except Exception as e:
            logger.error(f"Failed to reconcile HPA {self.namespace}/{self.name}: {e}")
            return False
    
    def _get_scale_target(self) -> Optional[Union[Deployment, StatefulSet, ReplicaSet]]:
        """
        Get the target resource to scale.
        
        Returns:
            Target resource or None if not found
        """
        kind = self.spec.scale_target_ref.get("kind")
        name = self.spec.scale_target_ref.get("name")
        
        if not kind or not name:
            return None
        
        if kind == "Deployment":
            return Deployment.get_deployment(name, self.namespace)
        elif kind == "StatefulSet":
            return StatefulSet.get_statefulset(name, self.namespace)
        elif kind == "ReplicaSet":
            return ReplicaSet.get_replicaset(name, self.namespace)
        
        return None
    
    def _get_current_replicas(self, target: Union[Deployment, StatefulSet, ReplicaSet]) -> int:
        """
        Get the current number of replicas for the target.
        
        Args:
            target: Target resource
            
        Returns:
            Current number of replicas
        """
        if hasattr(target, 'status') and hasattr(target.status, 'replicas'):
            return target.status.replicas
        
        return 0
    
    def _scale_target(self, target: Union[Deployment, StatefulSet, ReplicaSet], replicas: int) -> bool:
        """
        Scale the target resource.
        
        Args:
            target: Target resource
            replicas: Desired number of replicas
            
        Returns:
            bool: Success or failure
        """
        try:
            if hasattr(target, 'scale'):
                return target.scale(replicas)
            
            # Fall back to updating spec directly
            target.spec.replicas = replicas
            return target.save()
        except Exception as e:
            logger.error(f"Failed to scale target {target.namespace}/{target.name}: {e}")
            return False
    
    def _get_current_metrics(self, target: Union[Deployment, StatefulSet, ReplicaSet]) -> List[Dict[str, Any]]:
        """
        Get current metrics for the target.
        
        Args:
            target: Target resource
            
        Returns:
            List of current metrics
        """
        metrics_result = []
        
        for metric_spec in self.spec.metrics:
            if metric_spec.type == "Resource" and metric_spec.resource_name:
                # Get resource metrics
                metric_value = self._get_resource_metric_value(target, metric_spec.resource_name)
                
                if metric_value is not None:
                    metrics_result.append({
                        "type": "Resource",
                        "resource": {
                            "name": metric_spec.resource_name,
                            "current": {
                                metric_spec.target_type.lower(): metric_value
                            }
                        }
                    })
            elif metric_spec.type == "Pods":
                # Get pod metrics (not implemented)
                pass
            elif metric_spec.type == "Object":
                # Get object metrics (not implemented)
                pass
        
        return metrics_result
    
    def _get_resource_metric_value(self, target: Union[Deployment, StatefulSet, ReplicaSet], 
                                 resource_name: str) -> Optional[float]:
        """
        Get the current value for a resource metric.
        
        Args:
            target: Target resource
            resource_name: Resource name (e.g., "cpu", "memory")
            
        Returns:
            Current value or None if not available
        """
        # Get pod metrics
        pod_metrics = []
        
        # Get all pods for this target
        kind = self.spec.scale_target_ref.get("kind")
        name = self.spec.scale_target_ref.get("name")
        
        if not kind or not name:
            return None
        
        # Get pod selector
        pod_selector = {}
        if kind == "Deployment":
            if hasattr(target, 'spec') and hasattr(target.spec, 'selector'):
                pod_selector = target.spec.selector
        elif kind == "StatefulSet":
            if hasattr(target, 'spec') and hasattr(target.spec, 'selector'):
                pod_selector = target.spec.selector
        elif kind == "ReplicaSet":
            if hasattr(target, 'spec') and hasattr(target.spec, 'selector'):
                pod_selector = target.spec.selector
        
        # Convert selector to labels
        labels = {}
        for key, value in pod_selector.items():
            labels[key] = value
        
        # Get metrics for resource
        metric_name = f"pod_{resource_name}_percent"
        if resource_name == "memory":
            metric_name = "pod_memory_rss"
        
        metrics = self._metrics_collector.get_metrics(
            name=metric_name,
            labels=labels
        )
        
        if not metrics:
            return None
        
        # Calculate average
        total = 0.0
        count = 0
        
        for metric in metrics:
            if isinstance(metric.value, (int, float)):
                total += metric.value
                count += 1
        
        if count == 0:
            return None
        
        return total / count
    
    def _calculate_desired_replicas(self, target: Union[Deployment, StatefulSet, ReplicaSet],
                                  current_metrics: List[Dict[str, Any]]) -> int:
        """
        Calculate the desired number of replicas based on current metrics.
        
        Args:
            target: Target resource
            current_metrics: Current metrics
            
        Returns:
            Desired number of replicas
        """
        current_replicas = self._get_current_replicas(target)
        if current_replicas == 0:
            return self.spec.min_replicas
        
        desired_replicas = current_replicas
        
        # Process each metric
        for i, metric_spec in enumerate(self.spec.metrics):
            if i >= len(current_metrics):
                continue
            
            current_metric = current_metrics[i]
            
            if metric_spec.type == "Resource" and metric_spec.resource_name:
                # Get current value
                current_value = None
                resource_metric = current_metric.get("resource", {})
                current_data = resource_metric.get("current", {})
                
                if metric_spec.target_type.lower() in current_data:
                    current_value = current_data[metric_spec.target_type.lower()]
                
                if current_value is None:
                    continue
                
                # Calculate ratio
                ratio = current_value / metric_spec.target_value
                
                # Calculate replicas based on ratio
                metric_replicas = math.ceil(current_replicas * ratio)
                
                # Update desired replicas (max across all metrics)
                desired_replicas = max(desired_replicas, metric_replicas)
        
        return desired_replicas
    
    def _apply_scale_stabilization(self, desired_replicas: int) -> int:
        """
        Apply scale stabilization to avoid rapid scale up/down.
        
        Args:
            desired_replicas: Desired number of replicas
            
        Returns:
            Stabilized number of replicas
        """
        current_time = time.time()
        current_replicas = self.status.current_replicas
        
        # If scaling up
        if desired_replicas > current_replicas:
            # Check scale up stabilization window
            if self.spec.scale_up_stabilization_window_seconds > 0:
                # Get recent scale up events
                scale_up_time = current_time - self.spec.scale_up_stabilization_window_seconds
                
                for timestamp, replicas in reversed(self._scale_history):
                    if timestamp < scale_up_time:
                        break
                    
                    if replicas > current_replicas:
                        # Already scaled up in the window, keep current replicas
                        return current_replicas
        
        # If scaling down
        elif desired_replicas < current_replicas:
            # Check scale down stabilization window
            if self.spec.scale_down_stabilization_window_seconds > 0:
                # Get recent scale down events
                scale_down_time = current_time - self.spec.scale_down_stabilization_window_seconds
                
                for timestamp, replicas in reversed(self._scale_history):
                    if timestamp < scale_down_time:
                        break
                    
                    if replicas < current_replicas:
                        # Already scaled down in the window, keep current replicas
                        return current_replicas
        
        return desired_replicas
    
    @staticmethod
    def list_hpas(namespace: Optional[str] = None) -> List['HorizontalPodAutoscaler']:
        """
        List all horizontal pod autoscalers.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of HPAs
        """
        hpas = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespace_dir = HPA_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
                else:
                    namespaces = []
            
            # List HPAs in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(HPA_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    hpa_name = filename[:-5]  # Remove .json extension
                    hpa = HorizontalPodAutoscaler(hpa_name, ns)
                    hpas.append(hpa)
        except Exception as e:
            logger.error(f"Failed to list HPAs: {e}")
        
        return hpas
    
    @staticmethod
    def get_hpa(name: str, namespace: str = "default") -> Optional['HorizontalPodAutoscaler']:
        """
        Get a horizontal pod autoscaler by name and namespace.
        
        Args:
            name: HPA name
            namespace: Namespace
            
        Returns:
            HPA or None if not found
        """
        hpa = HorizontalPodAutoscaler(name, namespace)
        
        if os.path.exists(hpa._file_path()):
            return hpa
        
        return None


class AutoscalerController:
    """
    Controller for horizontal pod autoscalers in the KOS orchestration system.
    
    This class manages the reconciliation of horizontal pod autoscalers.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AutoscalerController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the autoscaler controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the autoscaler controller.
        
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
        Stop the autoscaler controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the autoscaler controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in autoscaler controller reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(15)  # Check every 15 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile all horizontal pod autoscalers.
        
        Returns:
            bool: Success or failure
        """
        try:
            # List all HPAs
            hpas = HorizontalPodAutoscaler.list_hpas()
            
            # Reconcile each HPA
            for hpa in hpas:
                try:
                    hpa.reconcile()
                except Exception as e:
                    logger.error(f"Failed to reconcile HPA {hpa.namespace}/{hpa.name}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile HPAs: {e}")
            return False
    
    @staticmethod
    def instance() -> 'AutoscalerController':
        """
        Get the singleton instance.
        
        Returns:
            AutoscalerController instance
        """
        return AutoscalerController()


def start_autoscaler_controller() -> bool:
    """
    Start the autoscaler controller.
    
    Returns:
        bool: Success or failure
    """
    controller = AutoscalerController.instance()
    return controller.start()


def stop_autoscaler_controller() -> bool:
    """
    Stop the autoscaler controller.
    
    Returns:
        bool: Success or failure
    """
    controller = AutoscalerController.instance()
    return controller.stop()

"""
Resource Quota for KOS Orchestration System

This module implements resource quotas for the KOS orchestration system,
allowing administrators to limit resource usage per namespace.
"""

import os
import json
import logging
import threading
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from kos.core.orchestration.admission import ValidationResult
from kos.core.orchestration.pod import Pod

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
QUOTA_PATH = os.path.join(ORCHESTRATION_ROOT, 'quota')

# Ensure directories exist
os.makedirs(QUOTA_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ResourceQuotaSpec:
    """Specification for a resource quota."""
    
    def __init__(self, hard: Dict[str, str] = None):
        """
        Initialize a resource quota specification.
        
        Args:
            hard: Hard resource limits
        """
        self.hard = hard or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the resource quota specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "hard": self.hard
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceQuotaSpec':
        """
        Create a resource quota specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ResourceQuotaSpec object
        """
        return cls(
            hard=data.get("hard", {})
        )


class ResourceQuotaStatus:
    """Status of a resource quota."""
    
    def __init__(self, hard: Dict[str, str] = None, used: Dict[str, str] = None):
        """
        Initialize a resource quota status.
        
        Args:
            hard: Hard resource limits
            used: Used resources
        """
        self.hard = hard or {}
        self.used = used or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the resource quota status to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "hard": self.hard,
            "used": self.used
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ResourceQuotaStatus':
        """
        Create a resource quota status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ResourceQuotaStatus object
        """
        return cls(
            hard=data.get("hard", {}),
            used=data.get("used", {})
        )


class ResourceQuota:
    """
    Resource quota for a namespace in the KOS orchestration system.
    
    A ResourceQuota provides constraints that limit aggregate resource consumption
    per namespace.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[ResourceQuotaSpec] = None):
        """
        Initialize a resource quota.
        
        Args:
            name: Resource quota name
            namespace: Namespace
            spec: Resource quota specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or ResourceQuotaSpec()
        self.status = ResourceQuotaStatus()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": "",
            "created": 0,
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this resource quota."""
        return os.path.join(QUOTA_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the resource quota from disk.
        
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
            self.spec = ResourceQuotaSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = ResourceQuotaStatus.from_dict(status_data)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load resource quota {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the resource quota to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "ResourceQuota",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict()
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save resource quota {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the resource quota.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete resource quota {self.namespace}/{self.name}: {e}")
            return False
    
    def update_usage(self) -> bool:
        """
        Update resource usage.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Reset usage
                self.status.used = {}
                
                # Get all pods in the namespace
                pods = Pod.list_pods(self.namespace)
                
                # Calculate usage
                for pod in pods:
                    self._add_pod_usage(pod)
                
                # Update status hard limits from spec
                self.status.hard = self.spec.hard
                
                # Save updated status
                return self.save()
        except Exception as e:
            logger.error(f"Failed to update resource quota usage {self.namespace}/{self.name}: {e}")
            return False
    
    def _add_pod_usage(self, pod: Pod) -> None:
        """
        Add pod resource usage to the quota.
        
        Args:
            pod: Pod to add usage for
        """
        # Skip pods that are not running
        if pod.status.phase not in ["Running", "Pending"]:
            return
        
        # Add pod count
        self._increment_usage("pods", 1)
        
        # Add container resource usage
        spec = pod.spec
        for container in spec.containers:
            resources = container.get("resources", {})
            limits = resources.get("limits", {})
            requests = resources.get("requests", {})
            
            # CPU limits
            if "cpu" in limits:
                self._increment_usage("limits.cpu", self._parse_cpu(limits["cpu"]))
            
            # Memory limits
            if "memory" in limits:
                self._increment_usage("limits.memory", self._parse_memory(limits["memory"]))
            
            # CPU requests
            if "cpu" in requests:
                self._increment_usage("requests.cpu", self._parse_cpu(requests["cpu"]))
            
            # Memory requests
            if "memory" in requests:
                self._increment_usage("requests.memory", self._parse_memory(requests["memory"]))
    
    def _increment_usage(self, resource: str, value: Union[int, float, str]) -> None:
        """
        Increment resource usage.
        
        Args:
            resource: Resource name
            value: Resource value
        """
        if resource not in self.status.used:
            self.status.used[resource] = str(value)
            return
        
        # Parse current value
        current_value = self.status.used[resource]
        
        # Handle different resource types
        if resource.endswith(".cpu"):
            # CPU is specified in cores
            current_cpu = self._parse_cpu(current_value)
            new_cpu = current_cpu + self._parse_cpu(value)
            self.status.used[resource] = str(new_cpu)
        elif resource.endswith(".memory"):
            # Memory is specified in bytes
            current_memory = self._parse_memory(current_value)
            new_memory = current_memory + self._parse_memory(value)
            self.status.used[resource] = self._format_memory(new_memory)
        else:
            # Other resources are integers
            try:
                current_int = int(current_value)
                new_int = current_int + int(value)
                self.status.used[resource] = str(new_int)
            except (ValueError, TypeError):
                # If we can't parse it, just replace it
                self.status.used[resource] = str(value)
    
    def _parse_cpu(self, cpu: Union[str, int, float]) -> float:
        """
        Parse CPU value to cores.
        
        Args:
            cpu: CPU value (e.g., "100m", "0.1")
            
        Returns:
            CPU value in cores
        """
        if isinstance(cpu, (int, float)):
            return float(cpu)
        
        try:
            if cpu.endswith("m"):
                return int(cpu[:-1]) / 1000
            
            return float(cpu)
        except (ValueError, TypeError):
            return 0
    
    def _parse_memory(self, memory: Union[str, int, float]) -> int:
        """
        Parse memory value to bytes.
        
        Args:
            memory: Memory value (e.g., "100Mi", "1Gi")
            
        Returns:
            Memory value in bytes
        """
        if isinstance(memory, (int, float)):
            return int(memory)
        
        try:
            if memory.endswith("Ki"):
                return int(memory[:-2]) * 1024
            elif memory.endswith("Mi"):
                return int(memory[:-2]) * 1024 * 1024
            elif memory.endswith("Gi"):
                return int(memory[:-2]) * 1024 * 1024 * 1024
            elif memory.endswith("Ti"):
                return int(memory[:-2]) * 1024 * 1024 * 1024 * 1024
            
            return int(memory)
        except (ValueError, TypeError):
            return 0
    
    def _format_memory(self, bytes_value: int) -> str:
        """
        Format memory value.
        
        Args:
            bytes_value: Memory value in bytes
            
        Returns:
            Formatted memory value
        """
        # Format as the largest unit possible
        if bytes_value >= 1024 * 1024 * 1024 * 1024:
            return f"{bytes_value // (1024 * 1024 * 1024 * 1024)}Ti"
        elif bytes_value >= 1024 * 1024 * 1024:
            return f"{bytes_value // (1024 * 1024 * 1024)}Gi"
        elif bytes_value >= 1024 * 1024:
            return f"{bytes_value // (1024 * 1024)}Mi"
        elif bytes_value >= 1024:
            return f"{bytes_value // 1024}Ki"
        
        return str(bytes_value)
    
    def validate_pod(self, pod: Pod) -> ValidationResult:
        """
        Validate if a pod fits within the resource quota.
        
        Args:
            pod: Pod to validate
            
        Returns:
            ValidationResult object
        """
        # Create a copy of the quota usage
        usage_copy = self.status.used.copy()
        
        # Add pod resources
        self._add_pod_usage_to_dict(pod, usage_copy)
        
        # Check if the updated usage exceeds the hard limits
        for resource, limit in self.spec.hard.items():
            if resource in usage_copy:
                used = usage_copy[resource]
                
                # Compare based on resource type
                if resource.endswith(".cpu"):
                    if self._parse_cpu(used) > self._parse_cpu(limit):
                        return ValidationResult(
                            False,
                            f"Resource quota exceeded: {resource} limited to {limit}, used would be {used}"
                        )
                elif resource.endswith(".memory"):
                    if self._parse_memory(used) > self._parse_memory(limit):
                        return ValidationResult(
                            False,
                            f"Resource quota exceeded: {resource} limited to {limit}, used would be {used}"
                        )
                else:
                    # Integer comparison for other resources
                    try:
                        if int(used) > int(limit):
                            return ValidationResult(
                                False,
                                f"Resource quota exceeded: {resource} limited to {limit}, used would be {used}"
                            )
                    except (ValueError, TypeError):
                        # If we can't compare, assume it's valid
                        pass
        
        return ValidationResult(True)
    
    def _add_pod_usage_to_dict(self, pod: Pod, usage_dict: Dict[str, str]) -> None:
        """
        Add pod resource usage to a usage dictionary.
        
        Args:
            pod: Pod to add usage for
            usage_dict: Usage dictionary to update
        """
        # Add pod count
        self._increment_usage_dict(usage_dict, "pods", 1)
        
        # Add container resource usage
        spec = pod.spec
        for container in spec.containers:
            resources = container.get("resources", {})
            limits = resources.get("limits", {})
            requests = resources.get("requests", {})
            
            # CPU limits
            if "cpu" in limits:
                self._increment_usage_dict(usage_dict, "limits.cpu", self._parse_cpu(limits["cpu"]))
            
            # Memory limits
            if "memory" in limits:
                self._increment_usage_dict(usage_dict, "limits.memory", self._parse_memory(limits["memory"]))
            
            # CPU requests
            if "cpu" in requests:
                self._increment_usage_dict(usage_dict, "requests.cpu", self._parse_cpu(requests["cpu"]))
            
            # Memory requests
            if "memory" in requests:
                self._increment_usage_dict(usage_dict, "requests.memory", self._parse_memory(requests["memory"]))
    
    def _increment_usage_dict(self, usage_dict: Dict[str, str], resource: str, 
                            value: Union[int, float, str]) -> None:
        """
        Increment resource usage in a usage dictionary.
        
        Args:
            usage_dict: Usage dictionary to update
            resource: Resource name
            value: Resource value
        """
        if resource not in usage_dict:
            usage_dict[resource] = str(value)
            return
        
        # Parse current value
        current_value = usage_dict[resource]
        
        # Handle different resource types
        if resource.endswith(".cpu"):
            # CPU is specified in cores
            current_cpu = self._parse_cpu(current_value)
            new_cpu = current_cpu + self._parse_cpu(value)
            usage_dict[resource] = str(new_cpu)
        elif resource.endswith(".memory"):
            # Memory is specified in bytes
            current_memory = self._parse_memory(current_value)
            new_memory = current_memory + self._parse_memory(value)
            usage_dict[resource] = self._format_memory(new_memory)
        else:
            # Other resources are integers
            try:
                current_int = int(current_value)
                new_int = current_int + int(value)
                usage_dict[resource] = str(new_int)
            except (ValueError, TypeError):
                # If we can't parse it, just replace it
                usage_dict[resource] = str(value)
    
    @staticmethod
    def list_quotas(namespace: Optional[str] = None) -> List['ResourceQuota']:
        """
        List all resource quotas.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of resource quotas
        """
        quotas = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = QUOTA_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List quotas in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(QUOTA_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    quota_name = filename[:-5]  # Remove .json extension
                    quota = ResourceQuota(quota_name, ns)
                    quotas.append(quota)
        except Exception as e:
            logger.error(f"Failed to list resource quotas: {e}")
        
        return quotas
    
    @staticmethod
    def get_quota(name: str, namespace: str = "default") -> Optional['ResourceQuota']:
        """
        Get a resource quota by name and namespace.
        
        Args:
            name: Resource quota name
            namespace: Namespace
            
        Returns:
            ResourceQuota object or None if not found
        """
        quota = ResourceQuota(name, namespace)
        
        if os.path.exists(quota._file_path()):
            return quota
        
        return None


class ResourceQuotaController:
    """
    Controller for resource quotas in the KOS orchestration system.
    
    This class manages the reconciliation of resource quotas.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ResourceQuotaController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the resource quota controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the resource quota controller.
        
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
        Stop the resource quota controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the resource quota controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in resource quota controller reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(30)  # Check every 30 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile all resource quotas.
        
        Returns:
            bool: Success or failure
        """
        try:
            # List all resource quotas
            quotas = ResourceQuota.list_quotas()
            
            # Reconcile each quota
            for quota in quotas:
                try:
                    quota.update_usage()
                except Exception as e:
                    logger.error(f"Failed to reconcile quota {quota.namespace}/{quota.name}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile resource quotas: {e}")
            return False
    
    def validate_pod(self, pod: Pod) -> ValidationResult:
        """
        Validate if a pod fits within the namespace's resource quotas.
        
        Args:
            pod: Pod to validate
            
        Returns:
            ValidationResult object
        """
        # Get all quotas for the pod's namespace
        quotas = ResourceQuota.list_quotas(pod.metadata.get("namespace", "default"))
        
        # Validate against each quota
        for quota in quotas:
            result = quota.validate_pod(pod)
            if not result.allowed:
                return result
        
        return ValidationResult(True)
    
    @staticmethod
    def instance() -> 'ResourceQuotaController':
        """
        Get the singleton instance.
        
        Returns:
            ResourceQuotaController instance
        """
        return ResourceQuotaController()


def get_quota_controller() -> ResourceQuotaController:
    """
    Get the resource quota controller instance.
    
    Returns:
        ResourceQuotaController instance
    """
    return ResourceQuotaController.instance()


def validate_pod_quota(pod: Pod) -> ValidationResult:
    """
    Validate if a pod fits within the namespace's resource quotas.
    
    Args:
        pod: Pod to validate
        
    Returns:
        ValidationResult object
    """
    controller = ResourceQuotaController.instance()
    return controller.validate_pod(pod)


def start_quota_controller() -> bool:
    """
    Start the resource quota controller.
    
    Returns:
        bool: Success or failure
    """
    controller = ResourceQuotaController.instance()
    return controller.start()


def stop_quota_controller() -> bool:
    """
    Stop the resource quota controller.
    
    Returns:
        bool: Success or failure
    """
    controller = ResourceQuotaController.instance()
    return controller.stop()

"""
Admission Controller for KOS Orchestration System

This module implements an admission controller for the KOS orchestration system,
validating resource requests before they are processed.
"""

import os
import json
import logging
import threading
import re
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
ADMISSION_CONFIG_PATH = os.path.join(ORCHESTRATION_ROOT, 'admission_config.json')

# Logging setup
logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, allowed: bool, reason: str = ""):
        """
        Initialize a validation result.
        
        Args:
            allowed: Whether the request is allowed
            reason: Reason for disallowing the request
        """
        self.allowed = allowed
        self.reason = reason
    
    def __bool__(self) -> bool:
        """Convert to boolean."""
        return self.allowed


class AdmissionRule:
    """Rule for the admission controller."""
    
    def __init__(self, name: str, resource_kind: str,
                 validate_func: Callable[[Dict[str, Any]], ValidationResult],
                 enabled: bool = True):
        """
        Initialize an admission rule.
        
        Args:
            name: Rule name
            resource_kind: Kind of resource this rule applies to
            validate_func: Validation function
            enabled: Whether the rule is enabled
        """
        self.name = name
        self.resource_kind = resource_kind
        self.validate_func = validate_func
        self.enabled = enabled
    
    def validate(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate a resource.
        
        Args:
            resource: Resource to validate
            
        Returns:
            ValidationResult object
        """
        if not self.enabled:
            return ValidationResult(True)
        
        try:
            return self.validate_func(resource)
        except Exception as e:
            logger.error(f"Error in admission rule {self.name}: {e}")
            return ValidationResult(False, f"Internal error in rule {self.name}")


class AdmissionController:
    """
    Admission controller for the KOS orchestration system.
    
    This class validates resource requests before they are processed.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AdmissionController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the admission controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._rules: Dict[str, Dict[str, AdmissionRule]] = {}
        self._config = self._load_config()
        
        # Register default rules
        self._register_default_rules()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load admission controller configuration from disk.
        
        Returns:
            Configuration dictionary
        """
        if os.path.exists(ADMISSION_CONFIG_PATH):
            try:
                with open(ADMISSION_CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load admission config: {e}")
        
        # Create default configuration
        config = {
            "enabled": True,
            "rules": {}
        }
        self._save_config(config)
        
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save admission controller configuration to disk.
        
        Args:
            config: Configuration to save
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(ADMISSION_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save admission config: {e}")
            return False
    
    def _register_default_rules(self) -> None:
        """Register default admission rules."""
        # Pod validation rules
        self.register_rule(
            name="pod_name_validation",
            resource_kind="Pod",
            validate_func=self._validate_pod_name
        )
        self.register_rule(
            name="pod_resource_limits",
            resource_kind="Pod",
            validate_func=self._validate_pod_resources
        )
        self.register_rule(
            name="pod_image_validation",
            resource_kind="Pod",
            validate_func=self._validate_pod_image
        )
        
        # Service validation rules
        self.register_rule(
            name="service_name_validation",
            resource_kind="Service",
            validate_func=self._validate_service_name
        )
        self.register_rule(
            name="service_port_validation",
            resource_kind="Service",
            validate_func=self._validate_service_ports
        )
        
        # Deployment validation rules
        self.register_rule(
            name="deployment_name_validation",
            resource_kind="Deployment",
            validate_func=self._validate_deployment_name
        )
        self.register_rule(
            name="deployment_replicas_validation",
            resource_kind="Deployment",
            validate_func=self._validate_deployment_replicas
        )
        
        # StatefulSet validation rules
        self.register_rule(
            name="statefulset_name_validation",
            resource_kind="StatefulSet",
            validate_func=self._validate_statefulset_name
        )
        self.register_rule(
            name="statefulset_service_validation",
            resource_kind="StatefulSet",
            validate_func=self._validate_statefulset_service
        )
        
        # PersistentVolumeClaim validation rules
        self.register_rule(
            name="pvc_name_validation",
            resource_kind="PersistentVolumeClaim",
            validate_func=self._validate_pvc_name
        )
        self.register_rule(
            name="pvc_size_validation",
            resource_kind="PersistentVolumeClaim",
            validate_func=self._validate_pvc_size
        )
    
    def register_rule(self, name: str, resource_kind: str,
                     validate_func: Callable[[Dict[str, Any]], ValidationResult],
                     enabled: bool = True) -> None:
        """
        Register an admission rule.
        
        Args:
            name: Rule name
            resource_kind: Kind of resource this rule applies to
            validate_func: Validation function
            enabled: Whether the rule is enabled
        """
        with self._lock:
            if resource_kind not in self._rules:
                self._rules[resource_kind] = {}
            
            self._rules[resource_kind][name] = AdmissionRule(
                name=name,
                resource_kind=resource_kind,
                validate_func=validate_func,
                enabled=enabled
            )
            
            # Update config
            if "rules" not in self._config:
                self._config["rules"] = {}
            
            if resource_kind not in self._config["rules"]:
                self._config["rules"][resource_kind] = {}
            
            self._config["rules"][resource_kind][name] = enabled
            self._save_config(self._config)
    
    def unregister_rule(self, name: str, resource_kind: str) -> bool:
        """
        Unregister an admission rule.
        
        Args:
            name: Rule name
            resource_kind: Kind of resource this rule applies to
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if resource_kind not in self._rules:
                return False
            
            if name not in self._rules[resource_kind]:
                return False
            
            del self._rules[resource_kind][name]
            
            # Update config
            if "rules" in self._config and resource_kind in self._config["rules"]:
                if name in self._config["rules"][resource_kind]:
                    del self._config["rules"][resource_kind][name]
                    self._save_config(self._config)
            
            return True
    
    def enable_rule(self, name: str, resource_kind: str) -> bool:
        """
        Enable an admission rule.
        
        Args:
            name: Rule name
            resource_kind: Kind of resource this rule applies to
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if resource_kind not in self._rules:
                return False
            
            if name not in self._rules[resource_kind]:
                return False
            
            self._rules[resource_kind][name].enabled = True
            
            # Update config
            if "rules" not in self._config:
                self._config["rules"] = {}
            
            if resource_kind not in self._config["rules"]:
                self._config["rules"][resource_kind] = {}
            
            self._config["rules"][resource_kind][name] = True
            self._save_config(self._config)
            
            return True
    
    def disable_rule(self, name: str, resource_kind: str) -> bool:
        """
        Disable an admission rule.
        
        Args:
            name: Rule name
            resource_kind: Kind of resource this rule applies to
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if resource_kind not in self._rules:
                return False
            
            if name not in self._rules[resource_kind]:
                return False
            
            self._rules[resource_kind][name].enabled = False
            
            # Update config
            if "rules" not in self._config:
                self._config["rules"] = {}
            
            if resource_kind not in self._config["rules"]:
                self._config["rules"][resource_kind] = {}
            
            self._config["rules"][resource_kind][name] = False
            self._save_config(self._config)
            
            return True
    
    def validate(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate a resource.
        
        Args:
            resource: Resource to validate
            
        Returns:
            ValidationResult object
        """
        # Check if admission controller is enabled
        if not self._config.get("enabled", True):
            return ValidationResult(True)
        
        # Get resource kind
        kind = resource.get("kind")
        if not kind:
            return ValidationResult(False, "Resource kind is required")
        
        # Check if we have rules for this kind
        if kind not in self._rules:
            return ValidationResult(True)
        
        # Run all rules for this kind
        for rule_name, rule in self._rules[kind].items():
            if not rule.enabled:
                continue
            
            result = rule.validate(resource)
            if not result.allowed:
                return result
        
        return ValidationResult(True)
    
    def is_enabled(self) -> bool:
        """
        Check if the admission controller is enabled.
        
        Returns:
            bool: True if enabled
        """
        return self._config.get("enabled", True)
    
    def enable(self) -> None:
        """Enable the admission controller."""
        self._config["enabled"] = True
        self._save_config(self._config)
    
    def disable(self) -> None:
        """Disable the admission controller."""
        self._config["enabled"] = False
        self._save_config(self._config)
    
    def list_rules(self, resource_kind: Optional[str] = None) -> Dict[str, Dict[str, bool]]:
        """
        List all admission rules.
        
        Args:
            resource_kind: Kind of resource to filter by
            
        Returns:
            Dictionary of rules
        """
        with self._lock:
            result = {}
            
            if resource_kind:
                if resource_kind in self._rules:
                    result[resource_kind] = {
                        rule_name: rule.enabled
                        for rule_name, rule in self._rules[resource_kind].items()
                    }
            else:
                for kind, rules in self._rules.items():
                    result[kind] = {
                        rule_name: rule.enabled
                        for rule_name, rule in rules.items()
                    }
            
            return result
    
    # Default validation functions
    
    def _validate_pod_name(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate pod name.
        
        Args:
            resource: Pod resource
            
        Returns:
            ValidationResult object
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        
        # Check if name is valid
        if not name:
            return ValidationResult(False, "Pod name is required")
        
        # Check if name is valid DNS label
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
            return ValidationResult(
                False,
                "Pod name must consist of lowercase alphanumeric characters or '-', "
                "and must start and end with an alphanumeric character"
            )
        
        return ValidationResult(True)
    
    def _validate_pod_resources(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate pod resource limits.
        
        Args:
            resource: Pod resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        containers = spec.get("containers", [])
        
        for i, container in enumerate(containers):
            # Check if container has resource limits
            resources = container.get("resources", {})
            limits = resources.get("limits", {})
            
            # Check CPU limit
            cpu_limit = limits.get("cpu")
            if cpu_limit is not None:
                try:
                    # Parse CPU limit (e.g., "100m", "0.1")
                    if cpu_limit.endswith("m"):
                        cpu_value = int(cpu_limit[:-1]) / 1000
                    else:
                        cpu_value = float(cpu_limit)
                    
                    # Check if CPU limit is valid
                    if cpu_value <= 0:
                        return ValidationResult(
                            False,
                            f"CPU limit for container {i} must be positive"
                        )
                except (ValueError, TypeError):
                    return ValidationResult(
                        False,
                        f"Invalid CPU limit format for container {i}: {cpu_limit}"
                    )
            
            # Check memory limit
            memory_limit = limits.get("memory")
            if memory_limit is not None:
                try:
                    # Parse memory limit (e.g., "100Mi", "1Gi")
                    if memory_limit.endswith("Ki"):
                        memory_value = int(memory_limit[:-2]) * 1024
                    elif memory_limit.endswith("Mi"):
                        memory_value = int(memory_limit[:-2]) * 1024 * 1024
                    elif memory_limit.endswith("Gi"):
                        memory_value = int(memory_limit[:-2]) * 1024 * 1024 * 1024
                    elif memory_limit.endswith("Ti"):
                        memory_value = int(memory_limit[:-2]) * 1024 * 1024 * 1024 * 1024
                    else:
                        memory_value = int(memory_limit)
                    
                    # Check if memory limit is valid
                    if memory_value <= 0:
                        return ValidationResult(
                            False,
                            f"Memory limit for container {i} must be positive"
                        )
                except (ValueError, TypeError):
                    return ValidationResult(
                        False,
                        f"Invalid memory limit format for container {i}: {memory_limit}"
                    )
        
        return ValidationResult(True)
    
    def _validate_pod_image(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate pod image.
        
        Args:
            resource: Pod resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        containers = spec.get("containers", [])
        
        for i, container in enumerate(containers):
            # Check if container has image
            image = container.get("image")
            if not image:
                return ValidationResult(
                    False,
                    f"Container {i} must have an image"
                )
            
            # Check if image is valid
            if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?(/[a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)*$', image):
                return ValidationResult(
                    False,
                    f"Invalid image format for container {i}: {image}"
                )
        
        return ValidationResult(True)
    
    def _validate_service_name(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate service name.
        
        Args:
            resource: Service resource
            
        Returns:
            ValidationResult object
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        
        # Check if name is valid
        if not name:
            return ValidationResult(False, "Service name is required")
        
        # Check if name is valid DNS label
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
            return ValidationResult(
                False,
                "Service name must consist of lowercase alphanumeric characters or '-', "
                "and must start and end with an alphanumeric character"
            )
        
        return ValidationResult(True)
    
    def _validate_service_ports(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate service ports.
        
        Args:
            resource: Service resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        ports = spec.get("ports", [])
        
        for i, port in enumerate(ports):
            # Check if port has a port number
            port_number = port.get("port")
            if port_number is None:
                return ValidationResult(
                    False,
                    f"Port {i} must have a port number"
                )
            
            # Check if port number is valid
            try:
                port_number = int(port_number)
                if port_number < 1 or port_number > 65535:
                    return ValidationResult(
                        False,
                        f"Port number for port {i} must be between 1 and 65535"
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    False,
                    f"Invalid port number for port {i}: {port_number}"
                )
            
            # Check if target port is valid
            target_port = port.get("targetPort")
            if target_port is not None:
                try:
                    target_port = int(target_port)
                    if target_port < 1 or target_port > 65535:
                        return ValidationResult(
                            False,
                            f"Target port for port {i} must be between 1 and 65535"
                        )
                except (ValueError, TypeError):
                    # Target port can also be a string (port name)
                    if not isinstance(target_port, str):
                        return ValidationResult(
                            False,
                            f"Invalid target port for port {i}: {target_port}"
                        )
        
        return ValidationResult(True)
    
    def _validate_deployment_name(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate deployment name.
        
        Args:
            resource: Deployment resource
            
        Returns:
            ValidationResult object
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        
        # Check if name is valid
        if not name:
            return ValidationResult(False, "Deployment name is required")
        
        # Check if name is valid DNS label
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
            return ValidationResult(
                False,
                "Deployment name must consist of lowercase alphanumeric characters or '-', "
                "and must start and end with an alphanumeric character"
            )
        
        return ValidationResult(True)
    
    def _validate_deployment_replicas(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate deployment replicas.
        
        Args:
            resource: Deployment resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        replicas = spec.get("replicas")
        
        # Check if replicas is valid
        if replicas is not None:
            try:
                replicas = int(replicas)
                if replicas < 0:
                    return ValidationResult(
                        False,
                        "Deployment replicas must be non-negative"
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    False,
                    f"Invalid replicas format: {replicas}"
                )
        
        return ValidationResult(True)
    
    def _validate_statefulset_name(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate statefulset name.
        
        Args:
            resource: StatefulSet resource
            
        Returns:
            ValidationResult object
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        
        # Check if name is valid
        if not name:
            return ValidationResult(False, "StatefulSet name is required")
        
        # Check if name is valid DNS label
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
            return ValidationResult(
                False,
                "StatefulSet name must consist of lowercase alphanumeric characters or '-', "
                "and must start and end with an alphanumeric character"
            )
        
        return ValidationResult(True)
    
    def _validate_statefulset_service(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate statefulset service name.
        
        Args:
            resource: StatefulSet resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        service_name = spec.get("serviceName")
        
        # Check if service name is valid
        if service_name:
            if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', service_name):
                return ValidationResult(
                    False,
                    "StatefulSet service name must consist of lowercase alphanumeric characters or '-', "
                    "and must start and end with an alphanumeric character"
                )
        
        return ValidationResult(True)
    
    def _validate_pvc_name(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate PVC name.
        
        Args:
            resource: PersistentVolumeClaim resource
            
        Returns:
            ValidationResult object
        """
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        
        # Check if name is valid
        if not name:
            return ValidationResult(False, "PVC name is required")
        
        # Check if name is valid DNS label
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', name):
            return ValidationResult(
                False,
                "PVC name must consist of lowercase alphanumeric characters or '-', "
                "and must start and end with an alphanumeric character"
            )
        
        return ValidationResult(True)
    
    def _validate_pvc_size(self, resource: Dict[str, Any]) -> ValidationResult:
        """
        Validate PVC size.
        
        Args:
            resource: PersistentVolumeClaim resource
            
        Returns:
            ValidationResult object
        """
        spec = resource.get("spec", {})
        resources = spec.get("resources", {})
        requests = resources.get("requests", {})
        
        # Check if storage request is valid
        storage = requests.get("storage")
        if storage:
            try:
                # Parse storage size (e.g., "100Mi", "1Gi")
                if storage.endswith("Ki"):
                    storage_value = int(storage[:-2]) * 1024
                elif storage.endswith("Mi"):
                    storage_value = int(storage[:-2]) * 1024 * 1024
                elif storage.endswith("Gi"):
                    storage_value = int(storage[:-2]) * 1024 * 1024 * 1024
                elif storage.endswith("Ti"):
                    storage_value = int(storage[:-2]) * 1024 * 1024 * 1024 * 1024
                else:
                    storage_value = int(storage)
                
                # Check if storage size is valid
                if storage_value <= 0:
                    return ValidationResult(
                        False,
                        "PVC storage size must be positive"
                    )
            except (ValueError, TypeError):
                return ValidationResult(
                    False,
                    f"Invalid storage size format: {storage}"
                )
        
        return ValidationResult(True)
    
    @staticmethod
    def instance() -> 'AdmissionController':
        """
        Get the singleton instance.
        
        Returns:
            AdmissionController instance
        """
        return AdmissionController()


def get_admission_controller() -> AdmissionController:
    """
    Get the admission controller instance.
    
    Returns:
        AdmissionController instance
    """
    return AdmissionController.instance()


def validate_resource(resource: Dict[str, Any]) -> ValidationResult:
    """
    Validate a resource.
    
    Args:
        resource: Resource to validate
        
    Returns:
        ValidationResult object
    """
    controller = AdmissionController.instance()
    return controller.validate(resource)

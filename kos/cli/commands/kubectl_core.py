"""
kubectl_core.py - Core functionality for kubectl command-line interface

This module provides the core functionality for the kubectl CLI, which
is used to manage resources in the KOS orchestration system.
"""

import os
import sys
import json
import yaml
import argparse
import logging
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.core.orchestration import (
    Pod, PodSpec, PodStatus, PodPhase,
    Service, ServiceSpec, ServiceType,
    Controller, ControllerType, ControllerStatus,
    ReplicaSet, Deployment, StatefulSet
)

# Logging setup
logger = logging.getLogger(__name__)

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
KUBE_CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/kos/kube/config')


class KubectlException(Exception):
    """Exception raised for kubectl errors."""
    pass


class OutputFormat:
    """Output formats for kubectl commands."""
    YAML = "yaml"
    JSON = "json"
    TABLE = "table"
    WIDE = "wide"
    NAME = "name"


class KubectlCore:
    """
    Core functionality for kubectl command-line interface.
    
    This class provides methods for interacting with the KOS orchestration
    system, including creating, updating, and deleting resources.
    """
    
    def __init__(self, namespace: str = "default"):
        """
        Initialize kubectl core.
        
        Args:
            namespace: Namespace to use
        """
        self.namespace = namespace
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load kubectl configuration.
        
        Returns:
            Dict of configuration values
        """
        if os.path.exists(KUBE_CONFIG_PATH):
            try:
                with open(KUBE_CONFIG_PATH, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load kubectl config: {e}")
        
        # Default configuration
        return {
            "current-context": "default",
            "contexts": [
                {
                    "name": "default",
                    "context": {
                        "namespace": "default"
                    }
                }
            ]
        }
    
    def _save_config(self) -> bool:
        """
        Save kubectl configuration.
        
        Returns:
            bool: Success or failure
        """
        try:
            os.makedirs(os.path.dirname(KUBE_CONFIG_PATH), exist_ok=True)
            with open(KUBE_CONFIG_PATH, 'w') as f:
                yaml.dump(self.config, f)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save kubectl config: {e}")
            return False
    
    def set_namespace(self, namespace: str) -> bool:
        """
        Set the current namespace.
        
        Args:
            namespace: Namespace to use
            
        Returns:
            bool: Success or failure
        """
        self.namespace = namespace
        
        # Update current context
        current_context = self.config.get("current-context", "default")
        
        # Find current context in contexts
        for context in self.config.get("contexts", []):
            if context.get("name") == current_context:
                context["context"]["namespace"] = namespace
                break
        
        return self._save_config()
    
    def get_current_namespace(self) -> str:
        """
        Get the current namespace.
        
        Returns:
            Current namespace
        """
        return self.namespace
    
    def format_output(self, resources: Union[Dict, List], output_format: str = OutputFormat.TABLE) -> str:
        """
        Format output for display.
        
        Args:
            resources: Resources to format
            output_format: Output format
            
        Returns:
            Formatted output string
        """
        if output_format == OutputFormat.JSON:
            return json.dumps(resources, indent=2)
        elif output_format == OutputFormat.YAML:
            return yaml.dump(resources, default_flow_style=False)
        elif output_format == OutputFormat.NAME:
            if isinstance(resources, list):
                return "\n".join(r.get("metadata", {}).get("name", "") for r in resources)
            else:
                return resources.get("metadata", {}).get("name", "")
        else:
            # Default to table format
            return self._format_table(resources, wide=output_format == OutputFormat.WIDE)
    
    def _format_table(self, resources: Union[Dict, List], wide: bool = False) -> str:
        """
        Format resources as a table.
        
        Args:
            resources: Resources to format
            wide: Whether to use wide format
            
        Returns:
            Formatted table string
        """
        if not resources:
            return "No resources found."
        
        if isinstance(resources, dict):
            resources = [resources]
        
        # Get resource kind
        kind = resources[0].get("kind", "Unknown").lower()
        
        if kind == "pod":
            return self._format_pod_table(resources, wide)
        elif kind == "service":
            return self._format_service_table(resources, wide)
        elif kind in ["replicaset", "deployment", "statefulset"]:
            return self._format_controller_table(resources, wide)
        else:
            # Generic table format
            return self._format_generic_table(resources, wide)
    
    def _format_pod_table(self, pods: List[Dict], wide: bool = False) -> str:
        """
        Format pods as a table.
        
        Args:
            pods: List of pod resources
            wide: Whether to use wide format
            
        Returns:
            Formatted table string
        """
        headers = ["NAME", "READY", "STATUS", "RESTARTS", "AGE"]
        
        if wide:
            headers.extend(["IP", "NODE", "NOMINATED NODE", "READINESS GATES"])
        
        rows = []
        
        for pod in pods:
            metadata = pod.get("metadata", {})
            spec = pod.get("spec", {})
            status = pod.get("status", {})
            
            # Calculate ready containers
            container_statuses = status.get("containerStatuses", [])
            ready_containers = sum(1 for cs in container_statuses if cs.get("ready", False))
            total_containers = len(spec.get("containers", []))
            
            # Calculate restarts
            restarts = sum(cs.get("restartCount", 0) for cs in container_statuses)
            
            # Calculate age
            creation_timestamp = metadata.get("creationTimestamp", 0)
            age = self._format_age(creation_timestamp)
            
            row = [
                metadata.get("name", ""),
                f"{ready_containers}/{total_containers}",
                status.get("phase", "Unknown"),
                str(restarts),
                age
            ]
            
            if wide:
                row.extend([
                    status.get("podIP", ""),
                    status.get("nodeName", ""),
                    status.get("nominatedNodeName", ""),
                    str(len(status.get("conditions", [])))
                ])
            
            rows.append(row)
        
        return self._format_table_output(headers, rows)
    
    def _format_service_table(self, services: List[Dict], wide: bool = False) -> str:
        """
        Format services as a table.
        
        Args:
            services: List of service resources
            wide: Whether to use wide format
            
        Returns:
            Formatted table string
        """
        headers = ["NAME", "TYPE", "CLUSTER-IP", "EXTERNAL-IP", "PORT(S)", "AGE"]
        
        if wide:
            headers.extend(["SELECTOR"])
        
        rows = []
        
        for service in services:
            metadata = service.get("metadata", {})
            spec = service.get("spec", {})
            
            # Format ports
            ports = []
            for port in spec.get("ports", []):
                port_str = f"{port.get('port', '')}"
                if "targetPort" in port:
                    port_str += f":{port.get('targetPort', '')}"
                if "nodePort" in port:
                    port_str += f":{port.get('nodePort', '')}"
                port_str += f"/{port.get('protocol', 'TCP')}"
                ports.append(port_str)
            
            # Calculate age
            creation_timestamp = metadata.get("creationTimestamp", 0)
            age = self._format_age(creation_timestamp)
            
            row = [
                metadata.get("name", ""),
                spec.get("type", "ClusterIP"),
                spec.get("clusterIP", ""),
                spec.get("externalIP", ""),
                ", ".join(ports),
                age
            ]
            
            if wide:
                selector = spec.get("selector", {})
                selector_str = ",".join(f"{k}={v}" for k, v in selector.items())
                row.append(selector_str)
            
            rows.append(row)
        
        return self._format_table_output(headers, rows)
    
    def _format_controller_table(self, controllers: List[Dict], wide: bool = False) -> str:
        """
        Format controllers as a table.
        
        Args:
            controllers: List of controller resources
            wide: Whether to use wide format
            
        Returns:
            Formatted table string
        """
        headers = ["NAME", "READY", "UP-TO-DATE", "AVAILABLE", "AGE"]
        
        if wide:
            headers.extend(["CONTAINERS", "IMAGES", "SELECTOR"])
        
        rows = []
        
        for controller in controllers:
            metadata = controller.get("metadata", {})
            spec = controller.get("spec", {})
            status = controller.get("status", {})
            
            # Calculate age
            creation_timestamp = metadata.get("creationTimestamp", 0)
            age = self._format_age(creation_timestamp)
            
            row = [
                metadata.get("name", ""),
                f"{status.get('readyReplicas', 0)}/{spec.get('replicas', 0)}",
                str(status.get("updatedReplicas", 0)),
                str(status.get("availableReplicas", 0)),
                age
            ]
            
            if wide:
                # Get containers and images from template
                template = spec.get("template", {}).get("spec", {})
                containers = template.get("containers", [])
                container_names = [c.get("name", "") for c in containers]
                container_images = [c.get("image", "") for c in containers]
                
                # Get selector
                selector = spec.get("selector", {})
                selector_str = ",".join(f"{k}={v}" for k, v in selector.items())
                
                row.extend([
                    ", ".join(container_names),
                    ", ".join(container_images),
                    selector_str
                ])
            
            rows.append(row)
        
        return self._format_table_output(headers, rows)
    
    def _format_generic_table(self, resources: List[Dict], wide: bool = False) -> str:
        """
        Format generic resources as a table.
        
        Args:
            resources: List of resources
            wide: Whether to use wide format
            
        Returns:
            Formatted table string
        """
        headers = ["NAME", "AGE"]
        
        rows = []
        
        for resource in resources:
            metadata = resource.get("metadata", {})
            
            # Calculate age
            creation_timestamp = metadata.get("creationTimestamp", 0)
            age = self._format_age(creation_timestamp)
            
            row = [
                metadata.get("name", ""),
                age
            ]
            
            rows.append(row)
        
        return self._format_table_output(headers, rows)
    
    def _format_table_output(self, headers: List[str], rows: List[List[str]]) -> str:
        """
        Format table output.
        
        Args:
            headers: Table headers
            rows: Table rows
            
        Returns:
            Formatted table string
        """
        if not rows:
            return "No resources found."
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(cell))
        
        # Format headers
        header_row = " ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        separator = " ".join("-" * w for w in col_widths)
        
        # Format rows
        formatted_rows = []
        for row in rows:
            formatted_row = " ".join(
                str(cell).ljust(col_widths[i]) if i < len(col_widths) else str(cell)
                for i, cell in enumerate(row)
            )
            formatted_rows.append(formatted_row)
        
        # Combine all parts
        return "\n".join([header_row, separator] + formatted_rows)
    
    def _format_age(self, timestamp: Union[int, float]) -> str:
        """
        Format age from timestamp.
        
        Args:
            timestamp: Creation timestamp
            
        Returns:
            Formatted age string
        """
        if not timestamp:
            return "Unknown"
        
        import time
        
        now = time.time()
        age_seconds = now - timestamp
        
        if age_seconds < 60:
            return f"{int(age_seconds)}s"
        elif age_seconds < 3600:
            return f"{int(age_seconds / 60)}m"
        elif age_seconds < 86400:
            return f"{int(age_seconds / 3600)}h"
        else:
            return f"{int(age_seconds / 86400)}d"


# Common resource helpers

def get_resource_by_name(resource_type: str, name: str, namespace: str = "default") -> Optional[Dict]:
    """
    Get a resource by name.
    
    Args:
        resource_type: Resource type (pod, service, etc.)
        name: Resource name
        namespace: Namespace
        
    Returns:
        Resource dict or None if not found
    """
    if resource_type == "pod":
        pod = Pod.load(name, namespace)
        return pod.to_dict() if pod else None
    elif resource_type == "service":
        service = Service.load(name, namespace)
        return service.to_dict() if service else None
    elif resource_type == "replicaset":
        rs = ReplicaSet.load(name, namespace)
        return rs.to_dict() if rs else None
    elif resource_type == "deployment":
        deployment = Deployment.load(name, namespace)
        return deployment.to_dict() if deployment else None
    elif resource_type == "statefulset":
        statefulset = StatefulSet.load(name, namespace)
        return statefulset.to_dict() if statefulset else None
    else:
        return None


def list_resources(resource_type: str, namespace: Optional[str] = None, selector: Optional[Dict[str, str]] = None) -> List[Dict]:
    """
    List resources.
    
    Args:
        resource_type: Resource type (pod, service, etc.)
        namespace: Namespace, or None for all namespaces
        selector: Label selector
        
    Returns:
        List of resources
    """
    resources = []
    
    if resource_type == "pod":
        pods = Pod.list_pods(namespace)
        resources = [pod.to_dict() for pod in pods]
    elif resource_type == "service":
        services = Service.list_services(namespace)
        resources = [service.to_dict() for service in services]
    elif resource_type == "replicaset":
        replicasets = ReplicaSet.list_controllers(namespace, ControllerType.REPLICA_SET)
        resources = [rs.to_dict() for rs in replicasets]
    elif resource_type == "deployment":
        deployments = Deployment.list_controllers(namespace, ControllerType.DEPLOYMENT)
        resources = [deployment.to_dict() for deployment in deployments]
    elif resource_type == "statefulset":
        statefulsets = StatefulSet.list_controllers(namespace, ControllerType.STATEFUL_SET)
        resources = [statefulset.to_dict() for statefulset in statefulsets]
    elif resource_type == "all":
        # List all resource types
        pods = Pod.list_pods(namespace)
        services = Service.list_services(namespace)
        replicasets = ReplicaSet.list_controllers(namespace, ControllerType.REPLICA_SET)
        deployments = Deployment.list_controllers(namespace, ControllerType.DEPLOYMENT)
        statefulsets = StatefulSet.list_controllers(namespace, ControllerType.STATEFUL_SET)
        
        resources = [pod.to_dict() for pod in pods]
        resources.extend([service.to_dict() for service in services])
        resources.extend([rs.to_dict() for rs in replicasets])
        resources.extend([deployment.to_dict() for deployment in deployments])
        resources.extend([statefulset.to_dict() for statefulset in statefulsets])
    
    # Filter by selector if provided
    if selector:
        filtered_resources = []
        for resource in resources:
            resource_labels = resource.get("metadata", {}).get("labels", {})
            if all(resource_labels.get(key) == value for key, value in selector.items()):
                filtered_resources.append(resource)
        resources = filtered_resources
    
    return resources


def delete_resource(resource_type: str, name: str, namespace: str = "default") -> bool:
    """
    Delete a resource.
    
    Args:
        resource_type: Resource type (pod, service, etc.)
        name: Resource name
        namespace: Namespace
        
    Returns:
        bool: Success or failure
    """
    if resource_type == "pod":
        pod = Pod.load(name, namespace)
        return pod.delete() if pod else False
    elif resource_type == "service":
        service = Service.load(name, namespace)
        return service.delete() if service else False
    elif resource_type == "replicaset":
        rs = ReplicaSet.load(name, namespace, ControllerType.REPLICA_SET)
        return rs.delete() if rs else False
    elif resource_type == "deployment":
        deployment = Deployment.load(name, namespace, ControllerType.DEPLOYMENT)
        return deployment.delete() if deployment else False
    elif resource_type == "statefulset":
        statefulset = StatefulSet.load(name, namespace, ControllerType.STATEFUL_SET)
        return statefulset.delete() if statefulset else False
    else:
        return False


def apply_resource(resource: Dict) -> bool:
    """
    Apply a resource configuration.
    
    Args:
        resource: Resource configuration
        
    Returns:
        bool: Success or failure
    """
    kind = resource.get("kind", "").lower()
    metadata = resource.get("metadata", {})
    name = metadata.get("name")
    namespace = metadata.get("namespace", "default")
    
    if not name:
        logger.error("Resource must have a name")
        return False
    
    try:
        if kind == "pod":
            # Load existing pod or create new one
            pod = Pod.load(name, namespace) or Pod(name, namespace)
            
            # Update pod with new configuration
            pod.labels = metadata.get("labels", {})
            pod.annotations = metadata.get("annotations", {})
            pod.spec = PodSpec.from_dict(resource.get("spec", {}))
            
            # Save pod
            return pod.save()
            
        elif kind == "service":
            # Load existing service or create new one
            service = Service.load(name, namespace) or Service(name, namespace)
            
            # Update service with new configuration
            service.labels = metadata.get("labels", {})
            service.annotations = metadata.get("annotations", {})
            service.spec = ServiceSpec.from_dict(resource.get("spec", {}))
            
            # Save service
            return service.save()
            
        elif kind == "replicaset":
            # Load existing ReplicaSet or create new one
            rs = ReplicaSet.load(name, namespace, ControllerType.REPLICA_SET) or ReplicaSet(
                name=name,
                namespace=namespace
            )
            
            # Update ReplicaSet with new configuration
            spec = resource.get("spec", {})
            rs.labels = metadata.get("labels", {})
            rs.annotations = metadata.get("annotations", {})
            rs.selector = spec.get("selector", {})
            rs.template = spec.get("template", {})
            rs.replicas = spec.get("replicas", 1)
            
            # Save ReplicaSet
            return rs.save()
            
        elif kind == "deployment":
            # Load existing Deployment or create new one
            deployment = Deployment.load(name, namespace, ControllerType.DEPLOYMENT) or Deployment(
                name=name,
                namespace=namespace
            )
            
            # Update Deployment with new configuration
            spec = resource.get("spec", {})
            deployment.labels = metadata.get("labels", {})
            deployment.annotations = metadata.get("annotations", {})
            deployment.selector = spec.get("selector", {})
            deployment.template = spec.get("template", {})
            deployment.replicas = spec.get("replicas", 1)
            
            # Save Deployment
            return deployment.save()
            
        elif kind == "statefulset":
            # Load existing StatefulSet or create new one
            statefulset = StatefulSet.load(name, namespace, ControllerType.STATEFUL_SET) or StatefulSet(
                name=name,
                namespace=namespace
            )
            
            # Update StatefulSet with new configuration
            spec = resource.get("spec", {})
            statefulset.labels = metadata.get("labels", {})
            statefulset.annotations = metadata.get("annotations", {})
            statefulset.selector = spec.get("selector", {})
            statefulset.template = spec.get("template", {})
            statefulset.replicas = spec.get("replicas", 1)
            statefulset.service_name = spec.get("serviceName", "")
            
            # Save StatefulSet
            return statefulset.save()
            
        else:
            logger.error(f"Unsupported resource kind: {kind}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to apply resource: {e}")
        return False

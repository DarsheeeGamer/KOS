"""
Service Management for KOS Orchestration

This module implements services for the KOS container orchestration system,
providing load balancing and stable networking for pods.

A Service is an abstraction which defines a logical set of Pods and a policy
by which to access them, similar to Kubernetes services.
"""

import os
import uuid
import json
import time
import logging
import ipaddress
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

from .pod import Pod

# Import core modules
from ..network import NetworkManager

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
SERVICES_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration/services')

# Ensure directories exist
os.makedirs(SERVICES_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Service types."""
    CLUSTER_IP = "ClusterIP"
    NODE_PORT = "NodePort"
    LOAD_BALANCER = "LoadBalancer"
    EXTERNAL_NAME = "ExternalName"


class ServicePort:
    """Service port mapping."""
    
    def __init__(self, name: str, port: int, target_port: int, 
                node_port: Optional[int] = None, protocol: str = "TCP"):
        """
        Initialize a service port.
        
        Args:
            name: Port name
            port: Service port
            target_port: Target port on pods
            node_port: External port on nodes (for NodePort)
            protocol: Port protocol (TCP, UDP)
        """
        self.name = name
        self.port = port
        self.target_port = target_port
        self.node_port = node_port
        self.protocol = protocol
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the service port to a dictionary.
        
        Returns:
            Dict representation of the service port
        """
        return {
            "name": self.name,
            "port": self.port,
            "target_port": self.target_port,
            "node_port": self.node_port,
            "protocol": self.protocol
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ServicePort':
        """
        Create a service port from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ServicePort object
        """
        return ServicePort(
            name=data.get("name", ""),
            port=data.get("port", 0),
            target_port=data.get("target_port", 0),
            node_port=data.get("node_port"),
            protocol=data.get("protocol", "TCP")
        )


class ServiceSpec:
    """
    Specification for a Service, defining its desired state.
    
    This is similar to the Kubernetes ServiceSpec.
    """
    
    def __init__(self, selector: Dict[str, str],
                 ports: List[Union[ServicePort, Dict[str, Any]]],
                 type: ServiceType = ServiceType.CLUSTER_IP,
                 cluster_ip: Optional[str] = None,
                 external_name: Optional[str] = None,
                 session_affinity: bool = False,
                 load_balancer_ip: Optional[str] = None):
        """
        Initialize a service specification.
        
        Args:
            selector: Label selector for pods
            ports: List of service ports
            type: Service type
            cluster_ip: Cluster IP address
            external_name: External DNS name
            session_affinity: Enable session affinity
            load_balancer_ip: Load balancer IP address
        """
        self.selector = selector
        self.ports = []
        
        # Convert ports to ServicePort objects
        for port in ports:
            if isinstance(port, ServicePort):
                self.ports.append(port)
            else:
                self.ports.append(ServicePort(
                    name=port.get("name", ""),
                    port=port.get("port", 0),
                    target_port=port.get("target_port", 0),
                    node_port=port.get("node_port"),
                    protocol=port.get("protocol", "TCP")
                ))
        
        self.type = type
        self.cluster_ip = cluster_ip
        self.external_name = external_name
        self.session_affinity = session_affinity
        self.load_balancer_ip = load_balancer_ip
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the service spec to a dictionary.
        
        Returns:
            Dict representation of the service spec
        """
        return {
            "selector": self.selector,
            "ports": [port.to_dict() for port in self.ports],
            "type": self.type,
            "cluster_ip": self.cluster_ip,
            "external_name": self.external_name,
            "session_affinity": self.session_affinity,
            "load_balancer_ip": self.load_balancer_ip
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ServiceSpec':
        """
        Create a service spec from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ServiceSpec object
        """
        ports = [ServicePort.from_dict(p) for p in data.get("ports", [])]
        
        return ServiceSpec(
            selector=data.get("selector", {}),
            ports=ports,
            type=data.get("type", ServiceType.CLUSTER_IP),
            cluster_ip=data.get("cluster_ip"),
            external_name=data.get("external_name"),
            session_affinity=data.get("session_affinity", False),
            load_balancer_ip=data.get("load_balancer_ip")
        )


class ServiceStatus:
    """Status information for a service."""
    
    def __init__(self, load_balancer: Dict[str, Any] = None):
        """
        Initialize service status.
        
        Args:
            load_balancer: Load balancer status
        """
        self.load_balancer = load_balancer or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the service status to a dictionary.
        
        Returns:
            Dict representation of the service status
        """
        return {
            "load_balancer": self.load_balancer
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ServiceStatus':
        """
        Create a service status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ServiceStatus object
        """
        return ServiceStatus(
            load_balancer=data.get("load_balancer", {})
        )


class Service:
    """
    Represents a service in the KOS orchestration system.
    
    A service provides stable networking and load balancing for a set of pods.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[ServiceSpec] = None,
                 status: Optional[ServiceStatus] = None,
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 uid: Optional[str] = None):
        """
        Initialize a service.
        
        Args:
            name: Service name
            namespace: Namespace
            spec: Service specification
            status: Service status
            labels: Service labels
            annotations: Service annotations
            uid: Unique ID
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or ServiceSpec({}, [])
        self.status = status or ServiceStatus()
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.uid = uid or str(uuid.uuid4())
        self.creation_timestamp = time.time()
        
        # Runtime-specific fields (not serialized)
        self._endpoints = {}  # port -> list of pod IPs
        self._update_lock = threading.Lock()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the service to a dictionary.
        
        Returns:
            Dict representation of the service
        """
        return {
            "kind": "Service",
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "labels": self.labels,
                "annotations": self.annotations
            },
            "spec": self.spec.to_dict(),
            "status": self.status.to_dict()
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Service':
        """
        Create a service from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Service object
        """
        metadata = data.get("metadata", {})
        
        return Service(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            spec=ServiceSpec.from_dict(data.get("spec", {})),
            status=ServiceStatus.from_dict(data.get("status", {})),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            uid=metadata.get("uid", str(uuid.uuid4()))
        )
    
    def save(self) -> bool:
        """
        Save the service state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            namespace_dir = os.path.join(SERVICES_DIR, self.namespace)
            os.makedirs(namespace_dir, exist_ok=True)
            
            service_file = os.path.join(namespace_dir, f"{self.name}.json")
            with open(service_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved service {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save service {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str, namespace: str = "default") -> Optional['Service']:
        """
        Load a service from disk.
        
        Args:
            name: Service name
            namespace: Namespace
            
        Returns:
            Service object or None if not found
        """
        service_file = os.path.join(SERVICES_DIR, namespace, f"{name}.json")
        if not os.path.exists(service_file):
            logger.error(f"Service not found: {namespace}/{name}")
            return None
        
        try:
            with open(service_file, 'r') as f:
                data = json.load(f)
            
            return Service.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load service {namespace}/{name}: {e}")
            return None
    
    @staticmethod
    def list_services(namespace: Optional[str] = None) -> List['Service']:
        """
        List services.
        
        Args:
            namespace: Namespace to list services from, or None for all namespaces
            
        Returns:
            List of Service objects
        """
        services = []
        
        if namespace:
            # List services in a specific namespace
            namespace_dir = os.path.join(SERVICES_DIR, namespace)
            if not os.path.exists(namespace_dir):
                return []
            
            namespaces = [namespace]
        else:
            # List services in all namespaces
            if not os.path.exists(SERVICES_DIR):
                return []
            
            namespaces = os.listdir(SERVICES_DIR)
        
        for ns in namespaces:
            namespace_dir = os.path.join(SERVICES_DIR, ns)
            if not os.path.isdir(namespace_dir):
                continue
            
            for filename in os.listdir(namespace_dir):
                if not filename.endswith('.json'):
                    continue
                
                service_file = os.path.join(namespace_dir, filename)
                try:
                    with open(service_file, 'r') as f:
                        data = json.load(f)
                    
                    services.append(Service.from_dict(data))
                except Exception as e:
                    logger.error(f"Failed to load service from {service_file}: {e}")
        
        return services
    
    def delete(self) -> bool:
        """
        Delete the service from disk.
        
        Returns:
            bool: Success or failure
        """
        service_file = os.path.join(SERVICES_DIR, self.namespace, f"{self.name}.json")
        if not os.path.exists(service_file):
            logger.warning(f"Service not found for deletion: {self.namespace}/{self.name}")
            return False
        
        try:
            os.remove(service_file)
            logger.info(f"Deleted service {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete service {self.namespace}/{self.name}: {e}")
            return False
    
    def create(self) -> bool:
        """
        Create the service resources.
        
        This allocates a ClusterIP, sets up load balancing, and more,
        depending on the service type.
        
        Returns:
            bool: Success or failure
        """
        try:
            # For ClusterIP and LoadBalancer, allocate an IP
            if self.spec.type in [ServiceType.CLUSTER_IP, ServiceType.LOAD_BALANCER]:
                if not self.spec.cluster_ip:
                    # Allocate a cluster IP from the service CIDR
                    network_manager = NetworkManager()
                    service_cidr = network_manager.get_service_cidr()
                    if service_cidr:
                        self.spec.cluster_ip = self._allocate_ip_from_cidr(service_cidr)
                    else:
                        # Default to a private IP range if no service CIDR is defined
                        self.spec.cluster_ip = self._allocate_ip_from_cidr("10.96.0.0/12")
            
            # For LoadBalancer, allocate an external IP
            if self.spec.type == ServiceType.LOAD_BALANCER and not self.spec.load_balancer_ip:
                # Allocate a load balancer IP
                network_manager = NetworkManager()
                external_cidr = network_manager.get_external_cidr()
                if external_cidr:
                    self.spec.load_balancer_ip = self._allocate_ip_from_cidr(external_cidr)
                else:
                    # Default to a private IP range if no external CIDR is defined
                    self.spec.load_balancer_ip = self._allocate_ip_from_cidr("192.168.0.0/16")
                
                # Update status
                self.status.load_balancer = {
                    "ingress": [
                        {"ip": self.spec.load_balancer_ip}
                    ]
                }
            
            # For NodePort, allocate node ports
            if self.spec.type == ServiceType.NODE_PORT:
                for port in self.spec.ports:
                    if not port.node_port:
                        # Allocate a node port in the range 30000-32767
                        port.node_port = self._allocate_node_port()
            
            # Set up port forwarding and load balancing
            self._setup_networking()
            
            # Save the service
            self.save()
            
            # Update endpoints based on pod selector
            self.update_endpoints()
            
            logger.info(f"Created service {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create service {self.namespace}/{self.name}: {e}")
            return False
    
    def _allocate_ip_from_cidr(self, cidr: str) -> str:
        """
        Allocate an IP address from a CIDR range.
        
        Args:
            cidr: CIDR range
            
        Returns:
            Allocated IP address
        """
        try:
            # Parse the CIDR
            network = ipaddress.ip_network(cidr)
            
            # Get a list of all services
            all_services = Service.list_services()
            
            # Collect all allocated IPs
            allocated_ips = set()
            for service in all_services:
                if service.spec.cluster_ip:
                    allocated_ips.add(service.spec.cluster_ip)
                if service.spec.load_balancer_ip:
                    allocated_ips.add(service.spec.load_balancer_ip)
            
            # Find an available IP
            for ip in network.hosts():
                ip_str = str(ip)
                if ip_str not in allocated_ips:
                    return ip_str
            
            raise ValueError(f"No available IPs in {cidr}")
        except Exception as e:
            logger.error(f"Failed to allocate IP from CIDR {cidr}: {e}")
            # Return a dummy IP for simulation
            return f"10.{hash(self.name) % 255}.{hash(self.namespace) % 255}.{hash(self.uid) % 255}"
    
    def _allocate_node_port(self) -> int:
        """
        Allocate a node port.
        
        Returns:
            Allocated node port
        """
        # Get a list of all services
        all_services = Service.list_services()
        
        # Collect all allocated node ports
        allocated_ports = set()
        for service in all_services:
            for port in service.spec.ports:
                if port.node_port:
                    allocated_ports.add(port.node_port)
        
        # Find an available port in the range 30000-32767
        for port in range(30000, 32768):
            if port not in allocated_ports:
                return port
        
        raise ValueError("No available node ports")
    
    def _setup_networking(self) -> bool:
        """
        Set up networking for the service.
        
        This sets up port forwarding, load balancing, and firewall rules.
        
        Returns:
            bool: Success or failure
        """
        try:
            network_manager = NetworkManager()
            
            # Get service IP
            service_ip = self.spec.cluster_ip
            
            # Set up port forwarding for each port
            for port in self.spec.ports:
                # For ClusterIP services, set up internal load balancing
                if self.spec.type == ServiceType.CLUSTER_IP:
                    # In a real implementation, this would configure the service proxy
                    # For simulation, we'll just log it
                    logger.info(f"Set up ClusterIP service {service_ip}:{port.port} -> pods:{port.target_port}")
                
                # For NodePort services, set up port forwarding on each node
                elif self.spec.type == ServiceType.NODE_PORT:
                    # In a real implementation, this would configure port forwarding on each node
                    # For simulation, we'll just log it
                    logger.info(f"Set up NodePort service *:{port.node_port} -> {service_ip}:{port.port}")
                
                # For LoadBalancer services, set up external load balancing
                elif self.spec.type == ServiceType.LOAD_BALANCER:
                    # In a real implementation, this would configure the load balancer
                    # For simulation, we'll just log it
                    logger.info(f"Set up LoadBalancer service {self.spec.load_balancer_ip}:{port.port} -> {service_ip}:{port.port}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to set up networking for service {self.namespace}/{self.name}: {e}")
            return False
    
    def update_endpoints(self) -> bool:
        """
        Update the service endpoints based on pod selectors.
        
        This finds all pods matching the service selector and updates
        the service endpoints.
        
        Returns:
            bool: Whether the endpoints changed
        """
        with self._update_lock:
            old_endpoints = self._endpoints.copy()
            
            # Reset endpoints
            self._endpoints = {port.port: [] for port in self.spec.ports}
            
            # Find matching pods
            matching_pods = []
            for pod in Pod.list_pods(self.namespace):
                # Check if pod labels match service selector
                matches = True
                for key, value in self.spec.selector.items():
                    if pod.labels.get(key) != value:
                        matches = False
                        break
                
                # Check if pod is running
                if matches and pod.status.phase == "Running" and pod.status.pod_ip:
                    matching_pods.append(pod)
            
            # Update endpoints for each port
            for port in self.spec.ports:
                for pod in matching_pods:
                    self._endpoints[port.port].append(pod.status.pod_ip)
            
            # Check if endpoints changed
            changed = (old_endpoints != self._endpoints)
            
            if changed:
                logger.info(f"Updated endpoints for service {self.namespace}/{self.name}")
                
                # Update the networking configuration
                self._update_networking()
            
            return changed
    
    def _update_networking(self) -> bool:
        """
        Update the networking configuration based on endpoints.
        
        This updates load balancing, port forwarding, and firewall rules.
        
        Returns:
            bool: Success or failure
        """
        try:
            # In a real implementation, this would update the service proxy configuration
            # For simulation, we'll just log it
            logger.info(f"Updated networking for service {self.namespace}/{self.name}")
            
            for port in self.spec.ports:
                endpoints = self._endpoints.get(port.port, [])
                logger.info(f"Port {port.port} -> {', '.join(endpoints)}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to update networking for service {self.namespace}/{self.name}: {e}")
            return False
    
    def get_endpoints(self) -> Dict[int, List[str]]:
        """
        Get the service endpoints.
        
        Returns:
            Dict mapping port numbers to lists of pod IPs
        """
        return self._endpoints.copy()
    
    def get_cluster_ip(self) -> Optional[str]:
        """
        Get the service cluster IP.
        
        Returns:
            Cluster IP address or None
        """
        return self.spec.cluster_ip
    
    def get_node_ports(self) -> Dict[int, int]:
        """
        Get the service node ports.
        
        Returns:
            Dict mapping service ports to node ports
        """
        node_ports = {}
        for port in self.spec.ports:
            if port.node_port:
                node_ports[port.port] = port.node_port
        
        return node_ports
    
    def get_load_balancer_ip(self) -> Optional[str]:
        """
        Get the service load balancer IP.
        
        Returns:
            Load balancer IP address or None
        """
        return self.spec.load_balancer_ip

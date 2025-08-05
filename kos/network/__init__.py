"""
KOS Network System

This module provides advanced networking capabilities for KOS, including
virtual networks, routing, and integration with the container system.
"""

import os
import sys
import time
import logging
import threading
import uuid
import json
import ipaddress
from typing import Dict, List, Any, Optional, Union, Tuple

# Import KOS components
from kos.container import ContainerManager

# Set up logging
logger = logging.getLogger('KOS.network')

# Network registry
NETWORKS = {}
NETWORK_LOCK = threading.Lock()

class NetworkInterface:
    """Network interface class representing a virtual network interface"""
    
    def __init__(self, name: str, mac_address: str, ipv4_address: str = None, ipv6_address: str = None):
        """Initialize a new network interface"""
        self.name = name
        self.mac_address = mac_address
        self.ipv4_address = ipv4_address
        self.ipv6_address = ipv6_address
        self.status = "up"  # up, down
        self.mtu = 1500
        self.tx_bytes = 0
        self.rx_bytes = 0
        self.tx_packets = 0
        self.rx_packets = 0
        self.connected_to = None  # Network ID this interface is connected to
    
    def connect(self, network_id: str):
        """Connect interface to a network"""
        self.connected_to = network_id
        return True
    
    def disconnect(self):
        """Disconnect interface from its network"""
        self.connected_to = None
        return True
    
    def to_dict(self):
        """Convert interface to dictionary representation"""
        return {
            "name": self.name,
            "mac_address": self.mac_address,
            "ipv4_address": self.ipv4_address,
            "ipv6_address": self.ipv6_address,
            "status": self.status,
            "mtu": self.mtu,
            "tx_bytes": self.tx_bytes,
            "rx_bytes": self.rx_bytes,
            "tx_packets": self.tx_packets,
            "rx_packets": self.rx_packets,
            "connected_to": self.connected_to
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create interface from dictionary"""
        interface = cls(data["name"], data["mac_address"], data["ipv4_address"], data["ipv6_address"])
        interface.status = data["status"]
        interface.mtu = data["mtu"]
        interface.tx_bytes = data["tx_bytes"]
        interface.rx_bytes = data["rx_bytes"]
        interface.tx_packets = data["tx_packets"]
        interface.rx_packets = data["rx_packets"]
        interface.connected_to = data["connected_to"]
        return interface

class Network:
    """Network class representing a virtual network"""
    
    def __init__(self, network_id: str, name: str, subnet: str, gateway: str = None, driver: str = "bridge"):
        """Initialize a new network"""
        self.id = network_id
        self.name = name
        self.subnet = subnet
        self.gateway = gateway
        self.driver = driver  # bridge, overlay, host, etc.
        self.created_at = time.time()
        self.interfaces = {}  # Map of interface name to container ID
        self.options = {}
        self.internal = False
        self.ipam_options = {}
    
    def connect_container(self, container_id: str, interface_name: str = None, ipv4_address: str = None):
        """Connect a container to this network"""
        # Generate interface name if not provided
        if not interface_name:
            interface_name = f"eth{len(self.interfaces)}"
        
        # Check if container exists
        container = ContainerManager.get_container(container_id)
        if not container:
            return False, f"Container {container_id} not found"
        
        # Check if container is already connected
        if container_id in self.interfaces.values():
            return False, f"Container {container_id} already connected to network {self.name}"
        
        # Add interface to network
        self.interfaces[interface_name] = container_id
        
        # Create virtual interface in container
        try:
            from ..container.runtime import get_container_runtime
            runtime = get_container_runtime()
            
            # Create network namespace if it doesn't exist
            runtime.create_network_namespace(container_id)
            
            # Create veth pair
            host_veth = f"veth_{container_id[:8]}"
            container_veth = interface_name
            
            # Create the veth pair
            import subprocess
            subprocess.run([
                "ip", "link", "add", host_veth, 
                "type", "veth", "peer", "name", container_veth
            ], check=True)
            
            # Move container end to container namespace
            subprocess.run([
                "ip", "link", "set", container_veth, 
                "netns", container_id
            ], check=True)
            
            # Configure interface in container
            subprocess.run([
                "ip", "netns", "exec", container_id,
                "ip", "addr", "add", f"{self._allocate_ip()}/{self._get_subnet_mask()}", 
                "dev", container_veth
            ], check=True)
            
            # Bring up interfaces
            subprocess.run(["ip", "link", "set", host_veth, "up"], check=True)
            subprocess.run([
                "ip", "netns", "exec", container_id,
                "ip", "link", "set", container_veth, "up"
            ], check=True)
            
            # Add to bridge if using bridge driver
            if self.driver == "bridge" and hasattr(self, 'bridge_name'):
                subprocess.run([
                    "ip", "link", "set", host_veth, 
                    "master", self.bridge_name
                ], check=True)
                
        except Exception as e:
            logger.warning(f"Failed to create virtual interface: {e}")
            # Continue anyway - interface tracking is still valid
        
        return True, f"Container {container_id} connected to network {self.name} with interface {interface_name}"
    
    def disconnect_container(self, container_id: str):
        """Disconnect a container from this network"""
        # Check if container is connected
        if container_id not in self.interfaces.values():
            return False, f"Container {container_id} not connected to network {self.name}"
        
        # Find and remove interface
        interface_name = None
        for name, cid in list(self.interfaces.items()):
            if cid == container_id:
                interface_name = name
                del self.interfaces[name]
        
        # Remove virtual interface from container
        try:
            host_veth = f"veth_{container_id[:8]}"
            
            # Delete the veth pair (deleting one end deletes both)
            import subprocess
            subprocess.run(["ip", "link", "delete", host_veth], check=True)
            
        except Exception as e:
            logger.warning(f"Failed to remove virtual interface: {e}")
            # Continue anyway - interface tracking is still valid
        
        return True, f"Container {container_id} disconnected from network {self.name}"
    
    def _allocate_ip(self) -> str:
        """Allocate an IP address from the subnet"""
        import ipaddress
        network = ipaddress.ip_network(self.subnet)
        
        # Skip network address, gateway, and broadcast
        used_ips = {self.gateway}
        
        # Find first available IP
        for ip in network.hosts():
            if str(ip) not in used_ips:
                return str(ip)
                
        raise ValueError(f"No available IPs in subnet {self.subnet}")
    
    def _get_subnet_mask(self) -> int:
        """Get subnet mask bits from CIDR notation"""
        return int(self.subnet.split('/')[1])
    
    def to_dict(self):
        """Convert network to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "subnet": self.subnet,
            "gateway": self.gateway,
            "driver": self.driver,
            "created_at": self.created_at,
            "interfaces": self.interfaces,
            "options": self.options,
            "internal": self.internal,
            "ipam_options": self.ipam_options
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create network from dictionary"""
        network = cls(data["id"], data["name"], data["subnet"], data["gateway"], data["driver"])
        network.created_at = data["created_at"]
        network.interfaces = data["interfaces"]
        network.options = data["options"]
        network.internal = data["internal"]
        network.ipam_options = data["ipam_options"]
        return network

class NetworkManager:
    """Manager for network operations"""
    
    @staticmethod
    def create_network(name: str, subnet: str, gateway: str = None, driver: str = "bridge", 
                       options: Dict[str, str] = None, internal: bool = False, 
                       ipam_options: Dict[str, Any] = None) -> Tuple[bool, str, Optional[Network]]:
        """Create a new network"""
        # Generate network ID
        network_id = str(uuid.uuid4())[:12]
        
        # Validate name uniqueness
        with NETWORK_LOCK:
            for n in NETWORKS.values():
                if n.name == name:
                    return False, f"Network name '{name}' already exists", None
        
        # Validate subnet
        try:
            ipaddress.ip_network(subnet)
        except ValueError:
            return False, f"Invalid subnet: {subnet}", None
        
        # Validate gateway if provided
        if gateway:
            try:
                ip = ipaddress.ip_address(gateway)
                network = ipaddress.ip_network(subnet)
                if ip not in network:
                    return False, f"Gateway {gateway} is not in subnet {subnet}", None
            except ValueError:
                return False, f"Invalid gateway: {gateway}", None
        
        # Create network
        network = Network(network_id, name, subnet, gateway, driver)
        
        # Set options
        if options:
            network.options = options
        
        # Set internal flag
        network.internal = internal
        
        # Set IPAM options
        if ipam_options:
            network.ipam_options = ipam_options
        
        # Add to registry
        with NETWORK_LOCK:
            NETWORKS[network_id] = network
        
        return True, f"Network {network_id} created", network
    
    @staticmethod
    def get_network(network_id: str) -> Optional[Network]:
        """Get network by ID"""
        with NETWORK_LOCK:
            return NETWORKS.get(network_id)
    
    @staticmethod
    def get_network_by_name(name: str) -> Optional[Network]:
        """Get network by name"""
        with NETWORK_LOCK:
            for network in NETWORKS.values():
                if network.name == name:
                    return network
        return None
    
    @staticmethod
    def list_networks() -> List[Network]:
        """List networks"""
        with NETWORK_LOCK:
            return list(NETWORKS.values())
    
    @staticmethod
    def remove_network(network_id: str) -> Tuple[bool, str]:
        """Remove a network"""
        with NETWORK_LOCK:
            if network_id not in NETWORKS:
                return False, f"Network {network_id} not found"
            
            network = NETWORKS[network_id]
            
            # Check if network has connected containers
            if network.interfaces:
                return False, f"Network {network_id} has connected containers"
            
            # Remove network
            del NETWORKS[network_id]
            
            return True, f"Network {network_id} removed"
    
    @staticmethod
    def connect_container(network_id: str, container_id: str, interface_name: str = None, 
                         ipv4_address: str = None) -> Tuple[bool, str]:
        """Connect a container to a network"""
        # Get network
        network = NetworkManager.get_network(network_id)
        if not network:
            network = NetworkManager.get_network_by_name(network_id)
        
        if not network:
            return False, f"Network {network_id} not found"
        
        # Connect container
        return network.connect_container(container_id, interface_name, ipv4_address)
    
    @staticmethod
    def disconnect_container(network_id: str, container_id: str) -> Tuple[bool, str]:
        """Disconnect a container from a network"""
        # Get network
        network = NetworkManager.get_network(network_id)
        if not network:
            network = NetworkManager.get_network_by_name(network_id)
        
        if not network:
            return False, f"Network {network_id} not found"
        
        # Disconnect container
        return network.disconnect_container(container_id)
    
    @staticmethod
    def save_networks(filepath: str) -> Tuple[bool, str]:
        """Save networks to file"""
        try:
            with NETWORK_LOCK:
                data = {nid: network.to_dict() for nid, network in NETWORKS.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Networks saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save networks: {str(e)}"
    
    @staticmethod
    def load_networks(filepath: str) -> Tuple[bool, str]:
        """Load networks from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with NETWORK_LOCK:
                NETWORKS.clear()
                for nid, network_data in data.items():
                    NETWORKS[nid] = Network.from_dict(network_data)
            
            return True, f"Networks loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load networks: {str(e)}"

class Route:
    """Route class representing a network route"""
    
    def __init__(self, destination: str, gateway: str, interface: str, metric: int = 0):
        """Initialize a new route"""
        self.destination = destination
        self.gateway = gateway
        self.interface = interface
        self.metric = metric
        self.flags = "UG"  # U = up, G = gateway
    
    def to_dict(self):
        """Convert route to dictionary representation"""
        return {
            "destination": self.destination,
            "gateway": self.gateway,
            "interface": self.interface,
            "metric": self.metric,
            "flags": self.flags
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create route from dictionary"""
        route = cls(data["destination"], data["gateway"], data["interface"], data["metric"])
        route.flags = data["flags"]
        return route

class RouteManager:
    """Manager for route operations"""
    
    _routes = []
    _routes_lock = threading.Lock()
    
    @staticmethod
    def add_route(destination: str, gateway: str, interface: str, metric: int = 0) -> Tuple[bool, str]:
        """Add a new route"""
        # Validate destination
        try:
            ipaddress.ip_network(destination)
        except ValueError:
            return False, f"Invalid destination: {destination}"
        
        # Validate gateway
        try:
            ipaddress.ip_address(gateway)
        except ValueError:
            return False, f"Invalid gateway: {gateway}"
        
        # Create route
        route = Route(destination, gateway, interface, metric)
        
        # Add to registry
        with RouteManager._routes_lock:
            RouteManager._routes.append(route)
        
        return True, f"Route to {destination} via {gateway} added"
    
    @staticmethod
    def remove_route(destination: str) -> Tuple[bool, str]:
        """Remove a route"""
        with RouteManager._routes_lock:
            for i, route in enumerate(RouteManager._routes):
                if route.destination == destination:
                    del RouteManager._routes[i]
                    return True, f"Route to {destination} removed"
        
        return False, f"Route to {destination} not found"
    
    @staticmethod
    def list_routes() -> List[Route]:
        """List routes"""
        with RouteManager._routes_lock:
            return list(RouteManager._routes)
    
    @staticmethod
    def save_routes(filepath: str) -> Tuple[bool, str]:
        """Save routes to file"""
        try:
            with RouteManager._routes_lock:
                data = [route.to_dict() for route in RouteManager._routes]
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Routes saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save routes: {str(e)}"
    
    @staticmethod
    def load_routes(filepath: str) -> Tuple[bool, str]:
        """Load routes from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with RouteManager._routes_lock:
                RouteManager._routes = [Route.from_dict(route_data) for route_data in data]
            
            return True, f"Routes loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load routes: {str(e)}"

# Initialize network system
def initialize():
    """Initialize the network system"""
    logger.info("Initializing KOS network system")
    
    # Create network directory
    network_dir = os.path.join(os.path.expanduser('~'), '.kos', 'networks')
    os.makedirs(network_dir, exist_ok=True)
    
    # Create default networks
    with NETWORK_LOCK:
        if not NETWORKS:
            # Create default bridge network
            bridge_id = "kos_bridge"
            bridge_network = Network(bridge_id, "bridge", "172.17.0.0/16", "172.17.0.1", "bridge")
            NETWORKS[bridge_id] = bridge_network
            
            # Create host network
            host_id = "kos_host"
            host_network = Network(host_id, "host", "127.0.0.0/8", "127.0.0.1", "host")
            NETWORKS[host_id] = host_network
            
            # Create none network
            none_id = "kos_none"
            none_network = Network(none_id, "none", "0.0.0.0/0", None, "null")
            NETWORKS[none_id] = none_network
    
    # Load networks if they exist
    network_db = os.path.join(network_dir, 'networks.json')
    if os.path.exists(network_db):
        NetworkManager.load_networks(network_db)
    else:
        # Save default networks
        NetworkManager.save_networks(network_db)
    
    # Load routes if they exist
    route_db = os.path.join(network_dir, 'routes.json')
    if os.path.exists(route_db):
        RouteManager.load_routes(route_db)
    
    logger.info("KOS network system initialized")

# Initialize on import
initialize()

"""
KOS Network Module
=================

Network utilities and services for KOS including:
- SSH/SCP management
- Firewall configuration
- Network monitoring
- Protocol implementations
- Security management
"""

from .ssh_manager import get_ssh_manager, SSHManager

__all__ = ['get_ssh_manager', 'SSHManager']

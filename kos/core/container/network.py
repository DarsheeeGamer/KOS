"""
KOS Container Network Management

Provides container networking capabilities:
- Network creation and management
- Container network interface setup
- DNS and service discovery
- Integration with KOS network subsystem
"""

import os
import time
import json
import uuid
import ipaddress
import logging
import subprocess
from typing import Dict, List, Any, Optional, Tuple

# Initialize logging
logger = logging.getLogger('KOS.container.network')

class ContainerNetwork:
    """
    Container network manager
    """
    def __init__(self, networks_dir: str):
        """
        Initialize the network manager
        
        Args:
            networks_dir: Directory for storing network metadata
        """
        self.networks_dir = networks_dir
        os.makedirs(networks_dir, exist_ok=True)
        
        # Network metadata file
        self.metadata_file = os.path.join(networks_dir, 'networks.json')
        
        # Network registry
        self.networks = {}  # name -> network info
        
        # Default networks
        self.default_networks = {
            'bridge': {
                'id': 'bridge',
                'name': 'bridge',
                'type': 'bridge',
                'subnet': '172.17.0.0/16',
                'gateway': '172.17.0.1',
                'interface': 'kos-bridge0',
                'created': time.time(),
                'containers': {}
            },
            'host': {
                'id': 'host',
                'name': 'host',
                'type': 'host',
                'created': time.time(),
                'containers': {}
            },
            'none': {
                'id': 'none',
                'name': 'none',
                'type': 'null',
                'created': time.time(),
                'containers': {}
            }
        }
        
        # Load networks
        self.load_networks()
    
    def load_networks(self):
        """Load networks from metadata file"""
        # Start with default networks
        self.networks = self.default_networks.copy()
        
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    networks = json.load(f)
                
                # Add custom networks, don't overwrite defaults
                for name, network in networks.items():
                    if name not in self.default_networks:
                        self.networks[name] = network
                
                logger.info(f"Loaded {len(self.networks)} networks")
            
            except Exception as e:
                logger.error(f"Error loading networks: {e}")
    
    def save_networks(self):
        """Save networks to metadata file"""
        try:
            # Only save custom networks
            custom_networks = {name: network for name, network in self.networks.items() 
                              if name not in self.default_networks}
            
            with open(self.metadata_file, 'w') as f:
                json.dump(custom_networks, f, indent=2)
            
            logger.info(f"Saved {len(custom_networks)} custom networks")
        
        except Exception as e:
            logger.error(f"Error saving networks: {e}")
    
    def create_network(self, name: str, subnet: Optional[str] = None, gateway: Optional[str] = None) -> bool:
        """
        Create a new network
        
        Args:
            name: Network name
            subnet: Network subnet CIDR
            gateway: Gateway IP address
        """
        if name in self.networks:
            logger.warning(f"Network {name} already exists")
            return False
        
        try:
            # Generate default subnet and gateway if not provided
            if not subnet:
                # Find an unused subnet in 172.18.0.0/16 - 172.31.0.0/16 range
                for i in range(18, 32):
                    candidate = f"172.{i}.0.0/16"
                    if not self._is_subnet_in_use(candidate):
                        subnet = candidate
                        break
                
                if not subnet:
                    # Try 192.168.0.0/24 - 192.168.255.0/24 range
                    for i in range(0, 256):
                        candidate = f"192.168.{i}.0/24"
                        if not self._is_subnet_in_use(candidate):
                            subnet = candidate
                            break
                
                if not subnet:
                    logger.error("Failed to allocate subnet for network")
                    return False
            
            # Generate default gateway if not provided
            if not gateway:
                network = ipaddress.IPv4Network(subnet)
                gateway = str(network.network_address + 1)
            
            # Generate network ID and interface name
            network_id = str(uuid.uuid4())[:12]
            interface = f"kos-{name[:6]}{network_id[:6]}"
            
            # Create network metadata
            network = {
                'id': network_id,
                'name': name,
                'type': 'bridge',
                'subnet': subnet,
                'gateway': gateway,
                'interface': interface,
                'created': time.time(),
                'containers': {}
            }
            
            # Create the network interface
            try:
                # In a real implementation, this would create a bridge interface
                # For this implementation, we'll integrate with the KOS network subsystem
                
                # Try to use the KOS network module
                try:
                    from ..network import create_interface, NetworkInterfaceType
                    
                    create_interface(
                        interface,
                        NetworkInterfaceType.BRIDGE,
                        gateway,
                        self._get_netmask_from_cidr(subnet)
                    )
                    
                    logger.info(f"Created bridge interface {interface} with KOS network module")
                
                except ImportError:
                    # Fall back to direct bridge creation
                    logger.info(f"Would create bridge interface {interface} with IP {gateway}")
            
            except Exception as e:
                logger.warning(f"Failed to create bridge interface: {e}")
                # Continue anyway, as we're primarily tracking the network in our registry
            
            # Add to registry
            self.networks[name] = network
            self.save_networks()
            
            logger.info(f"Created network: {name} ({subnet})")
            return True
        
        except Exception as e:
            logger.error(f"Error creating network {name}: {e}")
            return False
    
    def remove_network(self, name: str) -> bool:
        """
        Remove a network
        
        Args:
            name: Network name
        """
        if name not in self.networks:
            logger.warning(f"Network {name} does not exist")
            return False
        
        if name in self.default_networks:
            logger.warning(f"Cannot remove default network: {name}")
            return False
        
        network = self.networks[name]
        
        if network['containers']:
            logger.warning(f"Network {name} is in use by containers")
            return False
        
        try:
            # Remove the network interface
            interface = network['interface']
            
            try:
                # Try to use the KOS network module
                try:
                    from ..network import delete_interface
                    
                    delete_interface(interface)
                    logger.info(f"Removed bridge interface {interface} with KOS network module")
                
                except ImportError:
                    # Fall back to direct bridge removal
                    logger.info(f"Would remove bridge interface {interface}")
            
            except Exception as e:
                logger.warning(f"Failed to remove bridge interface: {e}")
            
            # Remove from registry
            del self.networks[name]
            self.save_networks()
            
            logger.info(f"Removed network: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing network {name}: {e}")
            return False
    
    def list_networks(self) -> List[Dict[str, Any]]:
        """List all networks"""
        networks = []
        for name, network in self.networks.items():
            networks.append({
                'id': network['id'],
                'name': name,
                'type': network['type'],
                'subnet': network.get('subnet'),
                'gateway': network.get('gateway'),
                'interface': network.get('interface'),
                'created': network['created'],
                'container_count': len(network['containers'])
            })
        
        return networks
    
    def setup_container_network(self, container) -> bool:
        """
        Set up networking for a container
        
        Args:
            container: Container object
        """
        try:
            network_name = container.network
            
            if network_name not in self.networks:
                logger.warning(f"Network {network_name} does not exist, using bridge")
                network_name = 'bridge'
            
            network = self.networks[network_name]
            
            # If using host or none network, nothing to do
            if network['type'] == 'host':
                container.ip_address = '127.0.0.1'
                
                # Add container to network registry
                network['containers'][container.id] = {
                    'id': container.id,
                    'name': container.name,
                    'ip_address': container.ip_address,
                    'network_interface': None
                }
                
                self.save_networks()
                return True
            
            if network['type'] == 'null':
                container.ip_address = None
                
                # Add container to network registry
                network['containers'][container.id] = {
                    'id': container.id,
                    'name': container.name,
                    'ip_address': None,
                    'network_interface': None
                }
                
                self.save_networks()
                return True
            
            # For bridge network, assign an IP address
            subnet = network['subnet']
            ip_address = self._allocate_ip_address(network)
            
            if not ip_address:
                logger.error(f"Failed to allocate IP address for container {container.name}")
                return False
            
            # Create veth pair for container
            container_if = container.network_interface
            host_if = f"veth{container.id[:8]}"
            
            # In a real implementation, this would create a veth pair, move one end to the container namespace,
            # and attach the other end to the bridge
            
            # Try to use the KOS network module
            try:
                from ..network import create_interface, NetworkInterfaceType
                
                # Create the host end of the veth pair
                create_interface(
                    host_if,
                    NetworkInterfaceType.TAP,
                    None,  # No IP for the host end
                    None
                )
                
                logger.info(f"Created host interface {host_if} with KOS network module")
            
            except ImportError:
                # Fall back to logging what we would do
                logger.info(f"Would create veth pair {container_if} <-> {host_if}")
            
            # Set container IP address
            container.ip_address = ip_address
            
            # Add container to network registry
            network['containers'][container.id] = {
                'id': container.id,
                'name': container.name,
                'ip_address': ip_address,
                'network_interface': container_if,
                'host_interface': host_if
            }
            
            self.save_networks()
            
            # Create /etc/hosts and /etc/resolv.conf in container
            if container.rootfs:
                self._setup_container_dns(container, network)
            
            logger.info(f"Set up network for container {container.name}: {ip_address} on {network_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error setting up network for container {container.name}: {e}")
            return False
    
    def cleanup_container_network(self, container) -> bool:
        """
        Clean up networking for a container
        
        Args:
            container: Container object
        """
        try:
            network_name = container.network
            
            if network_name not in self.networks:
                logger.warning(f"Network {network_name} does not exist")
                return False
            
            network = self.networks[network_name]
            
            # Remove container from network registry
            if container.id in network['containers']:
                container_net = network['containers'][container.id]
                
                # Release IP address
                ip_address = container_net.get('ip_address')
                
                # Remove veth pair if bridge network
                if network['type'] == 'bridge':
                    host_if = container_net.get('host_interface')
                    
                    if host_if:
                        # Try to use the KOS network module
                        try:
                            from ..network import delete_interface
                            
                            delete_interface(host_if)
                            logger.info(f"Removed host interface {host_if} with KOS network module")
                        
                        except ImportError:
                            # Fall back to logging what we would do
                            logger.info(f"Would remove veth pair for {container.name}")
                
                # Remove from network registry
                del network['containers'][container.id]
                self.save_networks()
            
            logger.info(f"Cleaned up network for container {container.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error cleaning up network for container {container.name}: {e}")
            return False
    
    def get_interfaces(self) -> List[str]:
        """Get all container network interfaces"""
        interfaces = []
        
        for network in self.networks.values():
            if 'interface' in network and network['interface']:
                interfaces.append(network['interface'])
            
            for container_id, container_net in network.get('containers', {}).items():
                if 'host_interface' in container_net and container_net['host_interface']:
                    interfaces.append(container_net['host_interface'])
        
        return interfaces
    
    def create_interface(self, name: str, type_name: str, ip_address: Optional[str] = None, netmask: Optional[str] = None) -> bool:
        """
        Create a network interface
        
        Args:
            name: Interface name
            type_name: Interface type
            ip_address: IP address
            netmask: Netmask
        """
        # In a real implementation, this would create a network interface
        logger.info(f"Would create {type_name} interface {name} with IP {ip_address}/{netmask}")
        return True
    
    def delete_interface(self, name: str) -> bool:
        """
        Delete a network interface
        
        Args:
            name: Interface name
        """
        # In a real implementation, this would delete a network interface
        logger.info(f"Would delete interface {name}")
        return True
    
    def _is_subnet_in_use(self, subnet: str) -> bool:
        """Check if a subnet is already in use"""
        target_network = ipaddress.IPv4Network(subnet)
        
        for network in self.networks.values():
            if 'subnet' in network and network['subnet']:
                existing_network = ipaddress.IPv4Network(network['subnet'])
                if target_network.overlaps(existing_network):
                    return True
        
        return False
    
    def _get_netmask_from_cidr(self, cidr: str) -> str:
        """Convert CIDR notation to netmask"""
        network = ipaddress.IPv4Network(cidr)
        return str(network.netmask)
    
    def _allocate_ip_address(self, network: Dict[str, Any]) -> Optional[str]:
        """
        Allocate an IP address from a network
        
        Args:
            network: Network configuration
        """
        try:
            ip_network = ipaddress.IPv4Network(network['subnet'])
            gateway_ip = ipaddress.IPv4Address(network['gateway'])
            
            # Create a list of used IPs
            used_ips = {gateway_ip}
            for container_id, container_net in network['containers'].items():
                if 'ip_address' in container_net and container_net['ip_address']:
                    used_ips.add(ipaddress.IPv4Address(container_net['ip_address']))
            
            # Find an available IP
            for ip in ip_network.hosts():
                if ip not in used_ips:
                    return str(ip)
            
            return None
        
        except Exception as e:
            logger.error(f"Error allocating IP address: {e}")
            return None
    
    def _setup_container_dns(self, container, network: Dict[str, Any]):
        """
        Set up DNS configuration in container
        
        Args:
            container: Container object
            network: Network configuration
        """
        try:
            # Create /etc/hosts file
            hosts_path = os.path.join(container.rootfs, 'etc', 'hosts')
            os.makedirs(os.path.dirname(hosts_path), exist_ok=True)
            
            with open(hosts_path, 'w') as f:
                f.write("127.0.0.1 localhost\n")
                
                if container.ip_address:
                    f.write(f"{container.ip_address} {container.name}\n")
                
                # Add other containers in the same network
                for container_id, container_net in network['containers'].items():
                    if container_id != container.id and 'ip_address' in container_net and container_net['ip_address']:
                        f.write(f"{container_net['ip_address']} {container_net['name']}\n")
            
            # Create /etc/resolv.conf file
            resolv_path = os.path.join(container.rootfs, 'etc', 'resolv.conf')
            
            with open(resolv_path, 'w') as f:
                # Use KOS DNS servers if available, otherwise use default
                try:
                    from ..network import list_dns_servers
                    dns_servers = list_dns_servers()
                except ImportError:
                    dns_servers = ['8.8.8.8', '8.8.4.4']  # Google DNS as fallback
                
                for server in dns_servers:
                    f.write(f"nameserver {server}\n")
                
                f.write("options ndots:1\n")
        
        except Exception as e:
            logger.error(f"Error setting up DNS for container {container.name}: {e}")
            # Continue anyway, as this is not critical

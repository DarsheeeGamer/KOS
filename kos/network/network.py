"""
Network management for KOS
"""

import socket
import struct
import time
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum

class InterfaceState(Enum):
    """Network interface states"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"

@dataclass
class NetworkInterface:
    """Network interface representation"""
    name: str
    mac_address: str = "00:00:00:00:00:00"
    ip_address: str = "0.0.0.0"
    netmask: str = "255.255.255.0"
    gateway: str = ""
    state: InterfaceState = InterfaceState.DOWN
    mtu: int = 1500
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'mac_address': self.mac_address,
            'ip_address': self.ip_address,
            'netmask': self.netmask,
            'gateway': self.gateway,
            'state': self.state.value,
            'mtu': self.mtu,
            'statistics': {
                'rx_bytes': self.rx_bytes,
                'tx_bytes': self.tx_bytes,
                'rx_packets': self.rx_packets,
                'tx_packets': self.tx_packets,
                'rx_errors': self.rx_errors,
                'tx_errors': self.tx_errors
            }
        }

@dataclass
class Route:
    """Network route"""
    destination: str
    gateway: str
    netmask: str
    interface: str
    metric: int = 0
    
    def matches(self, ip: str) -> bool:
        """Check if IP matches this route"""
        # Simple implementation
        if self.destination == "0.0.0.0":  # Default route
            return True
        # More complex matching would go here
        return False

class NetworkManager:
    """Manages network configuration and operations"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.interfaces: Dict[str, NetworkInterface] = {}
        self.routes: List[Route] = []
        self.hostname = "kos"
        self.domain = "local"
        
        # Configuration file
        self.config_file = "/etc/network/interfaces"
        
        # Initialize default interfaces
        self._init_interfaces()
        self._load_config()
    
    def _init_interfaces(self):
        """Initialize default network interfaces"""
        # Loopback interface
        lo = NetworkInterface(
            name="lo",
            mac_address="00:00:00:00:00:00",
            ip_address="127.0.0.1",
            netmask="255.0.0.0",
            state=InterfaceState.UP,
            mtu=65536
        )
        self.interfaces["lo"] = lo
        
        # Default ethernet interface (simulated)
        eth0 = NetworkInterface(
            name="eth0",
            mac_address="52:54:00:12:34:56",
            ip_address="192.168.1.100",
            netmask="255.255.255.0",
            gateway="192.168.1.1",
            state=InterfaceState.UP,
            mtu=1500
        )
        self.interfaces["eth0"] = eth0
        
        # Default route
        self.routes.append(Route(
            destination="0.0.0.0",
            gateway="192.168.1.1",
            netmask="0.0.0.0",
            interface="eth0"
        ))
    
    def _load_config(self):
        """Load network configuration from VFS"""
        if not self.vfs or not self.vfs.exists(self.config_file):
            return
        
        try:
            with self.vfs.open(self.config_file, 'r') as f:
                config = json.loads(f.read().decode())
            
            # Load interfaces
            for iface_data in config.get('interfaces', []):
                iface = NetworkInterface(**iface_data)
                self.interfaces[iface.name] = iface
            
            # Load routes
            for route_data in config.get('routes', []):
                route = Route(**route_data)
                self.routes.append(route)
            
            # Load hostname
            self.hostname = config.get('hostname', 'kos')
            self.domain = config.get('domain', 'local')
            
        except Exception as e:
            pass  # Use defaults
    
    def _save_config(self):
        """Save network configuration to VFS"""
        if not self.vfs:
            return
        
        try:
            # Ensure directory exists
            config_dir = "/etc/network"
            if not self.vfs.exists(config_dir):
                self.vfs.mkdir(config_dir)
            
            # Prepare config
            config = {
                'hostname': self.hostname,
                'domain': self.domain,
                'interfaces': [iface.to_dict() for iface in self.interfaces.values()],
                'routes': [
                    {
                        'destination': route.destination,
                        'gateway': route.gateway,
                        'netmask': route.netmask,
                        'interface': route.interface,
                        'metric': route.metric
                    }
                    for route in self.routes
                ]
            }
            
            # Save to file
            with self.vfs.open(self.config_file, 'w') as f:
                f.write(json.dumps(config, indent=2).encode())
        
        except Exception as e:
            pass
    
    def get_interface(self, name: str) -> Optional[NetworkInterface]:
        """Get interface by name"""
        return self.interfaces.get(name)
    
    def list_interfaces(self) -> List[NetworkInterface]:
        """List all network interfaces"""
        return list(self.interfaces.values())
    
    def bring_up(self, interface_name: str) -> bool:
        """Bring interface up"""
        if interface_name in self.interfaces:
            self.interfaces[interface_name].state = InterfaceState.UP
            self._save_config()
            return True
        return False
    
    def bring_down(self, interface_name: str) -> bool:
        """Bring interface down"""
        if interface_name in self.interfaces:
            self.interfaces[interface_name].state = InterfaceState.DOWN
            self._save_config()
            return True
        return False
    
    def set_ip(self, interface_name: str, ip: str, netmask: str = "255.255.255.0") -> bool:
        """Set IP address for interface"""
        if interface_name in self.interfaces:
            self.interfaces[interface_name].ip_address = ip
            self.interfaces[interface_name].netmask = netmask
            self._save_config()
            return True
        return False
    
    def add_route(self, destination: str, gateway: str, netmask: str = "255.255.255.0",
                  interface: str = "eth0", metric: int = 0) -> bool:
        """Add a route"""
        route = Route(destination, gateway, netmask, interface, metric)
        self.routes.append(route)
        self._save_config()
        return True
    
    def delete_route(self, destination: str) -> bool:
        """Delete a route"""
        self.routes = [r for r in self.routes if r.destination != destination]
        self._save_config()
        return True
    
    def get_routes(self) -> List[Route]:
        """Get all routes"""
        return self.routes
    
    def ping(self, host: str, count: int = 4, timeout: float = 1.0) -> Tuple[bool, List[float]]:
        """Ping a host (simulated)"""
        # In a real implementation, would use ICMP
        # For now, simulate based on whether we can resolve the host
        
        times = []
        success = False
        
        try:
            # Try to resolve hostname
            if host == "localhost" or host == "127.0.0.1":
                # Always succeed for localhost
                success = True
                for i in range(count):
                    times.append(0.001)  # 1ms for localhost
                    time.sleep(0.1)
            elif host in ["google.com", "8.8.8.8", "1.1.1.1"]:
                # Simulate successful ping to known hosts
                success = True
                for i in range(count):
                    times.append(0.020 + (i * 0.002))  # 20-26ms
                    time.sleep(0.1)
            else:
                # Simulate timeout
                for i in range(count):
                    time.sleep(timeout)
                success = False
        
        except Exception:
            success = False
        
        return success, times
    
    def resolve_hostname(self, hostname: str) -> Optional[str]:
        """Resolve hostname to IP (simulated)"""
        # Simple hostname resolution
        if hostname == "localhost":
            return "127.0.0.1"
        elif hostname == self.hostname:
            return self.interfaces.get("eth0", NetworkInterface("eth0")).ip_address
        
        # Simulate some known hosts
        known_hosts = {
            "google.com": "142.250.185.46",
            "github.com": "140.82.112.3",
            "cloudflare.com": "104.16.132.229"
        }
        
        return known_hosts.get(hostname)
    
    def get_hostname(self) -> str:
        """Get system hostname"""
        return f"{self.hostname}.{self.domain}"
    
    def set_hostname(self, hostname: str, domain: str = None) -> bool:
        """Set system hostname"""
        self.hostname = hostname
        if domain:
            self.domain = domain
        self._save_config()
        return True
    
    def get_stats(self, interface_name: str) -> Optional[dict]:
        """Get interface statistics"""
        iface = self.interfaces.get(interface_name)
        if iface:
            return {
                'rx_bytes': iface.rx_bytes,
                'tx_bytes': iface.tx_bytes,
                'rx_packets': iface.rx_packets,
                'tx_packets': iface.tx_packets,
                'rx_errors': iface.rx_errors,
                'tx_errors': iface.tx_errors
            }
        return None
    
    def simulate_traffic(self, interface_name: str, rx_bytes: int = 0, tx_bytes: int = 0):
        """Simulate network traffic for testing"""
        if interface_name in self.interfaces:
            iface = self.interfaces[interface_name]
            iface.rx_bytes += rx_bytes
            iface.tx_bytes += tx_bytes
            iface.rx_packets += rx_bytes // 1500  # Approximate packets
            iface.tx_packets += tx_bytes // 1500
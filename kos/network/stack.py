"""
KOS Network Stack - Python-based networking simulation
"""

import socket
import threading
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class InterfaceState(Enum):
    """Network interface states"""
    DOWN = "down"
    UP = "up"
    DORMANT = "dormant"

class ProtocolType(Enum):
    """Network protocol types"""
    IPv4 = "ipv4"
    IPv6 = "ipv6"
    ARP = "arp"
    ICMP = "icmp"
    TCP = "tcp"
    UDP = "udp"

@dataclass
class NetworkInterface:
    """Network interface representation"""
    name: str
    ip: str
    netmask: str = "255.255.255.0"
    gateway: str = ""
    mac: str = "00:00:00:00:00:00"
    mtu: int = 1500
    state: InterfaceState = InterfaceState.DOWN
    rx_packets: int = 0
    tx_packets: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_errors: int = 0
    tx_errors: int = 0

@dataclass
class Route:
    """Network route entry"""
    destination: str
    gateway: str
    netmask: str
    interface: str
    metric: int = 0

@dataclass
class Connection:
    """Network connection tracking"""
    local_addr: Tuple[str, int]
    remote_addr: Tuple[str, int]
    protocol: ProtocolType
    state: str
    pid: int = 0

class KOSNetworkStack:
    """
    KOS Network Stack - simulates Linux networking
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.interfaces = {}  # name -> NetworkInterface
        self.routes = []  # Route entries
        self.connections = []  # Active connections
        self.arp_table = {}  # IP -> MAC mapping
        self.dns_servers = ["8.8.8.8", "8.8.4.4"]
        self.hostname = "localhost"
        self.domain = "localdomain"
        
        # Packet processing
        self.packet_queue = []
        self.packet_thread = None
        self.running = False
        
        # Socket simulation
        self.socket_counter = 1000
        self.sockets = {}  # fd -> socket info
        
        # Firewall rules (iptables simulation)
        self.firewall_rules = {
            'filter': {'INPUT': [], 'OUTPUT': [], 'FORWARD': []},
            'nat': {'PREROUTING': [], 'OUTPUT': [], 'POSTROUTING': []},
            'mangle': {'PREROUTING': [], 'INPUT': [], 'FORWARD': [], 'OUTPUT': [], 'POSTROUTING': []}
        }
        
    def start(self):
        """Start network stack"""
        self.running = True
        self.packet_thread = threading.Thread(
            target=self._packet_processor,
            name="kos-network",
            daemon=True
        )
        self.packet_thread.start()
        
    def stop(self):
        """Stop network stack"""
        self.running = False
        if self.packet_thread:
            self.packet_thread.join(timeout=1.0)
            
    def create_interface(self, name: str, ip: str, netmask: str = "255.255.255.0"):
        """Create network interface"""
        # Generate MAC address based on interface name
        mac_suffix = hash(name) % 0xFFFFFF
        mac = f"02:00:00:{(mac_suffix >> 16) & 0xFF:02x}:{(mac_suffix >> 8) & 0xFF:02x}:{mac_suffix & 0xFF:02x}"
        
        interface = NetworkInterface(
            name=name,
            ip=ip,
            netmask=netmask,
            mac=mac
        )
        self.interfaces[name] = interface
        
        # Add local route for interface subnet
        if ip != "127.0.0.1":  # Not for loopback
            network = self._calculate_network(ip, netmask)
            self.add_route(network, "0.0.0.0", netmask, name)
            
        return interface
        
    def delete_interface(self, name: str):
        """Delete network interface"""
        if name in self.interfaces:
            # Remove associated routes
            self.routes = [r for r in self.routes if r.interface != name]
            del self.interfaces[name]
            
    def interface_up(self, name: str):
        """Bring interface up"""
        if name in self.interfaces:
            self.interfaces[name].state = InterfaceState.UP
            
    def interface_down(self, name: str):
        """Bring interface down"""
        if name in self.interfaces:
            self.interfaces[name].state = InterfaceState.DOWN
            
    def set_ip(self, interface: str, ip: str, netmask: str = "255.255.255.0"):
        """Set interface IP address"""
        if interface in self.interfaces:
            self.interfaces[interface].ip = ip
            self.interfaces[interface].netmask = netmask
            
    def add_route(self, destination: str, gateway: str, netmask: str, interface: str, metric: int = 0):
        """Add route to routing table"""
        route = Route(destination, gateway, netmask, interface, metric)
        self.routes.append(route)
        
    def delete_route(self, destination: str, gateway: str = None):
        """Delete route from routing table"""
        self.routes = [r for r in self.routes 
                      if not (r.destination == destination and 
                             (gateway is None or r.gateway == gateway))]
                             
    def get_routes(self) -> List[Route]:
        """Get routing table"""
        return sorted(self.routes, key=lambda r: r.metric)
        
    def get_interfaces(self) -> Dict[str, NetworkInterface]:
        """Get all interfaces"""
        return self.interfaces.copy()
        
    def get_interface(self, name: str) -> Optional[NetworkInterface]:
        """Get specific interface"""
        return self.interfaces.get(name)
        
    def ping(self, target: str, count: int = 4, timeout: float = 1.0) -> Dict[str, any]:
        """Simulate ping command"""
        results = {
            'target': target,
            'packets_sent': count,
            'packets_received': 0,
            'packets_lost': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'avg_time': 0,
            'times': []
        }
        
        for i in range(count):
            # Simulate ping time (faster for local, slower for remote)
            if target.startswith('127.') or target == 'localhost':
                ping_time = 0.1 + (hash(str(i)) % 100) / 10000  # 0.1-0.11ms
            else:
                ping_time = 10 + (hash(str(i)) % 500) / 10  # 10-60ms
                
            # Simulate 5% packet loss
            if hash(f"{target}-{i}") % 20 == 0:
                continue  # Packet lost
                
            results['packets_received'] += 1
            results['times'].append(ping_time)
            results['min_time'] = min(results['min_time'], ping_time)
            results['max_time'] = max(results['max_time'], ping_time)
            
        if results['packets_received'] > 0:
            results['avg_time'] = sum(results['times']) / len(results['times'])
        else:
            results['min_time'] = 0
            
        results['packets_lost'] = results['packets_sent'] - results['packets_received']
        results['loss_percent'] = (results['packets_lost'] / results['packets_sent']) * 100
        
        return results
        
    def netstat(self, options: str = "") -> List[Connection]:
        """Simulate netstat command"""
        # Return simulated connections
        simulated_connections = [
            Connection(("127.0.0.1", 22), ("0.0.0.0", 0), ProtocolType.TCP, "LISTEN", 1234),
            Connection(("0.0.0.0", 80), ("0.0.0.0", 0), ProtocolType.TCP, "LISTEN", 5678),
            Connection(("127.0.0.1", 53), ("0.0.0.0", 0), ProtocolType.UDP, "LISTEN", 9012),
        ]
        
        return simulated_connections + self.connections
        
    def arp(self, action: str = "show", ip: str = "", mac: str = "") -> Dict[str, str]:
        """Simulate ARP table operations"""
        if action == "show":
            return self.arp_table.copy()
        elif action == "add" and ip and mac:
            self.arp_table[ip] = mac
        elif action == "delete" and ip:
            self.arp_table.pop(ip, None)
        return self.arp_table.copy()
        
    def resolve_hostname(self, hostname: str) -> str:
        """Simulate DNS resolution"""
        # Common hostnames
        dns_map = {
            "localhost": "127.0.0.1",
            "google.com": "172.217.14.14",
            "github.com": "140.82.113.4",
            "stackoverflow.com": "151.101.1.69",
            "python.org": "138.197.63.241"
        }
        
        return dns_map.get(hostname.lower(), f"203.0.113.{hash(hostname) % 254 + 1}")
        
    def traceroute(self, target: str, max_hops: int = 30) -> List[Dict[str, any]]:
        """Simulate traceroute"""
        hops = []
        
        # Simulate route through several hops
        for hop in range(1, min(max_hops + 1, 8)):
            if hop == 1:
                # Local gateway
                hop_ip = "192.168.1.1"
                hop_name = "gateway.local"
                time_ms = 1.0
            elif hop < 4:
                # ISP hops
                hop_ip = f"10.{hop}.{hop}.1"
                hop_name = f"isp-hop-{hop}.example.com"
                time_ms = hop * 5.0
            else:
                # Internet hops
                hop_ip = f"203.0.113.{hop * 10}"
                hop_name = f"hop{hop}.internet.example"
                time_ms = hop * 8.0
                
            # Last hop is the target
            if hop == 7 or target.startswith('127.'):
                hop_ip = target if target != 'localhost' else '127.0.0.1'
                hop_name = target
                time_ms = 50.0 if not target.startswith('127.') else 0.1
                
            hops.append({
                'hop': hop,
                'ip': hop_ip,
                'hostname': hop_name,
                'time_ms': time_ms
            })
            
            # Stop at target
            if hop_ip == target or (target == 'localhost' and hop_ip == '127.0.0.1'):
                break
                
        return hops
        
    def get_network_stats(self) -> Dict[str, any]:
        """Get network statistics"""
        stats = {
            'interfaces': {},
            'total_rx_packets': 0,
            'total_tx_packets': 0,
            'total_rx_bytes': 0,
            'total_tx_bytes': 0,
            'connections': len(self.connections),
            'routes': len(self.routes)
        }
        
        for name, iface in self.interfaces.items():
            stats['interfaces'][name] = {
                'rx_packets': iface.rx_packets,
                'tx_packets': iface.tx_packets,
                'rx_bytes': iface.rx_bytes,
                'tx_bytes': iface.tx_bytes,
                'rx_errors': iface.rx_errors,
                'tx_errors': iface.tx_errors,
                'state': iface.state.value
            }
            stats['total_rx_packets'] += iface.rx_packets
            stats['total_tx_packets'] += iface.tx_packets
            stats['total_rx_bytes'] += iface.rx_bytes
            stats['total_tx_bytes'] += iface.tx_bytes
            
        return stats
        
    def _calculate_network(self, ip: str, netmask: str) -> str:
        """Calculate network address from IP and netmask"""
        ip_parts = [int(x) for x in ip.split('.')]
        mask_parts = [int(x) for x in netmask.split('.')]
        network_parts = [ip_parts[i] & mask_parts[i] for i in range(4)]
        return '.'.join(map(str, network_parts))
        
    def _packet_processor(self):
        """Background packet processing thread"""
        while self.running:
            # Simulate packet processing
            if self.packet_queue:
                packet = self.packet_queue.pop(0)
                # Process packet (placeholder)
                
            # Update interface statistics periodically
            for iface in self.interfaces.values():
                if iface.state == InterfaceState.UP:
                    # Simulate some network activity
                    iface.rx_packets += hash(time.time()) % 3
                    iface.tx_packets += hash(time.time() + 1) % 2
                    iface.rx_bytes += iface.rx_packets * 64
                    iface.tx_bytes += iface.tx_packets * 64
                    
            time.sleep(0.1)
            
    def __str__(self) -> str:
        """String representation"""
        lines = ["KOS Network Stack Status:"]
        lines.append(f"Hostname: {self.hostname}.{self.domain}")
        lines.append(f"Interfaces: {len(self.interfaces)}")
        lines.append(f"Routes: {len(self.routes)}")
        lines.append(f"Connections: {len(self.connections)}")
        return '\n'.join(lines)
"""
KOS Real Network Stack Implementation
Direct network operations using Linux kernel interfaces
"""

import os
import socket
import struct
import fcntl
import array
import subprocess
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger('kos.network.real_stack')


# Network interface flags
class IFF(IntEnum):
    """Interface flags"""
    UP = 0x1            # Interface is up
    BROADCAST = 0x2     # Broadcast address valid
    DEBUG = 0x4         # Turn on debugging
    LOOPBACK = 0x8      # Is a loopback net
    POINTOPOINT = 0x10  # Interface is point-to-point
    NOTRAILERS = 0x20   # Avoid use of trailers
    RUNNING = 0x40      # Resources allocated
    NOARP = 0x80        # No address resolution protocol
    PROMISC = 0x100     # Receive all packets
    ALLMULTI = 0x200    # Receive all multicast packets
    MASTER = 0x400      # Master of a load balancer
    SLAVE = 0x800       # Slave of a load balancer
    MULTICAST = 0x1000  # Supports multicast
    PORTSEL = 0x2000    # Can set media type
    AUTOMEDIA = 0x4000  # Auto media select active
    DYNAMIC = 0x8000    # Dialup device with changing addresses
    LOWER_UP = 0x10000  # Driver signals L1 up
    DORMANT = 0x20000   # Driver signals dormant
    ECHO = 0x40000      # Echo sent packets


# Socket ioctl commands
class SIOC(IntEnum):
    """Socket ioctl commands"""
    SIOCGIFNAME = 0x8910     # Get interface name
    SIOCSIFLINK = 0x8911     # Set interface channel
    SIOCGIFCONF = 0x8912     # Get interface list
    SIOCGIFFLAGS = 0x8913    # Get flags
    SIOCSIFFLAGS = 0x8914    # Set flags
    SIOCGIFADDR = 0x8915     # Get PA address
    SIOCSIFADDR = 0x8916     # Set PA address
    SIOCGIFDSTADDR = 0x8917  # Get remote PA address
    SIOCSIFDSTADDR = 0x8918  # Set remote PA address
    SIOCGIFBRDADDR = 0x8919  # Get broadcast PA address
    SIOCSIFBRDADDR = 0x891a  # Set broadcast PA address
    SIOCGIFNETMASK = 0x891b  # Get network PA mask
    SIOCSIFNETMASK = 0x891c  # Set network PA mask
    SIOCGIFMETRIC = 0x891d   # Get metric
    SIOCSIFMETRIC = 0x891e   # Set metric
    SIOCGIFMEM = 0x891f      # Get memory address (BSD)
    SIOCSIFMEM = 0x8920      # Set memory address (BSD)
    SIOCGIFMTU = 0x8921      # Get MTU size
    SIOCSIFMTU = 0x8922      # Set MTU size
    SIOCSIFNAME = 0x8923     # Set interface name
    SIOCSIFHWADDR = 0x8924   # Set hardware address
    SIOCGIFENCAP = 0x8925    # Get/set encapsulations
    SIOCSIFENCAP = 0x8926
    SIOCGIFHWADDR = 0x8927   # Get hardware address
    SIOCGIFSLAVE = 0x8929    # Driver slaving support
    SIOCSIFSLAVE = 0x8930
    SIOCADDMULTI = 0x8931    # Multicast address lists
    SIOCDELMULTI = 0x8932
    SIOCGIFINDEX = 0x8933    # Name -> if_index mapping
    SIOGIFINDEX = SIOCGIFINDEX # Misprint compatibility
    SIOCSIFPFLAGS = 0x8934   # Set/get extended flags
    SIOCGIFPFLAGS = 0x8935
    SIOCDIFADDR = 0x8936     # Delete PA address
    SIOCSIFHWBROADCAST = 0x8937 # Set hardware broadcast address
    SIOCGIFCOUNT = 0x8938    # Get number of devices
    SIOCGIFBR = 0x8940       # Bridging support
    SIOCSIFBR = 0x8941       # Set bridging options
    SIOCGIFTXQLEN = 0x8942   # Get the tx queue length
    SIOCSIFTXQLEN = 0x8943   # Set the tx queue length


@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    index: int
    flags: int
    mtu: int
    mac_address: str
    ip_addresses: List[str]
    ip6_addresses: List[str]
    state: str
    speed: int = 0
    duplex: str = "unknown"
    
    @property
    def is_up(self) -> bool:
        return bool(self.flags & IFF.UP)
        
    @property
    def is_running(self) -> bool:
        return bool(self.flags & IFF.RUNNING)
        
    @property
    def is_loopback(self) -> bool:
        return bool(self.flags & IFF.LOOPBACK)


class RealNetworkStack:
    """Real network stack implementation"""
    
    def __init__(self):
        self.sock = None
        self._create_control_socket()
        
    def _create_control_socket(self):
        """Create control socket for ioctls"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
    def __del__(self):
        """Cleanup control socket"""
        if self.sock:
            self.sock.close()
            
    def get_interfaces(self) -> List[NetworkInterface]:
        """Get all network interfaces"""
        interfaces = []
        
        # Get interface list using SIOCGIFCONF
        max_interfaces = 128
        bytes_needed = max_interfaces * 40  # struct ifreq size
        names = array.array('B', b'\0' * bytes_needed)
        
        outbytes = struct.unpack('iL', fcntl.ioctl(
            self.sock.fileno(),
            SIOC.SIOCGIFCONF,
            struct.pack('iL', bytes_needed, names.buffer_info()[0])
        ))[0]
        
        # Parse interface names
        namestr = names.tobytes()
        interface_names = []
        
        for i in range(0, outbytes, 40):
            name = namestr[i:i+16].split(b'\0', 1)[0].decode('utf-8')
            if name and name not in interface_names:
                interface_names.append(name)
                
        # Get details for each interface
        for name in interface_names:
            try:
                iface = self.get_interface_info(name)
                if iface:
                    interfaces.append(iface)
            except Exception as e:
                logger.debug(f"Failed to get info for {name}: {e}")
                
        return interfaces
        
    def get_interface_info(self, ifname: str) -> Optional[NetworkInterface]:
        """Get detailed interface information"""
        try:
            # Get interface index
            ifr = struct.pack('16sI', ifname.encode('utf-8'), 0)
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFINDEX, ifr)
            index = struct.unpack('16sI', res)[1]
            
            # Get flags
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFFLAGS, ifr)
            flags = struct.unpack('16sh', res[:18])[1]
            
            # Get MTU
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFMTU, ifr)
            mtu = struct.unpack('16si', res[:20])[1]
            
            # Get MAC address
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            try:
                res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFHWADDR, ifr)
                mac = ':'.join(['%02x' % b for b in res[18:24]])
            except:
                mac = '00:00:00:00:00:00'
                
            # Get IP addresses
            ip_addresses = []
            try:
                ifr = struct.pack('256s', ifname.encode('utf-8'))
                res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFADDR, ifr)
                ip = socket.inet_ntoa(res[20:24])
                ip_addresses.append(ip)
            except:
                pass
                
            # Get IPv6 addresses from /proc/net/if_inet6
            ip6_addresses = []
            try:
                with open('/proc/net/if_inet6', 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 6 and parts[5] == ifname:
                            # Convert hex address to standard notation
                            addr_hex = parts[0]
                            addr = ':'.join([addr_hex[i:i+4] for i in range(0, 32, 4)])
                            ip6_addresses.append(addr)
            except:
                pass
                
            # Determine state
            if flags & IFF.UP:
                if flags & IFF.RUNNING:
                    state = "UP"
                else:
                    state = "DOWN"
            else:
                state = "DISABLED"
                
            # Get speed and duplex from ethtool if available
            speed = 0
            duplex = "unknown"
            try:
                result = subprocess.run(
                    ['ethtool', ifname],
                    capture_output=True,
                    text=True,
                    timeout=1
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Speed:' in line:
                            speed_str = line.split(':')[1].strip()
                            if 'Mb/s' in speed_str:
                                speed = int(speed_str.replace('Mb/s', ''))
                        elif 'Duplex:' in line:
                            duplex = line.split(':')[1].strip().lower()
            except:
                pass
                
            return NetworkInterface(
                name=ifname,
                index=index,
                flags=flags,
                mtu=mtu,
                mac_address=mac,
                ip_addresses=ip_addresses,
                ip6_addresses=ip6_addresses,
                state=state,
                speed=speed,
                duplex=duplex
            )
            
        except Exception as e:
            logger.error(f"Failed to get interface info for {ifname}: {e}")
            return None
            
    def set_interface_up(self, ifname: str) -> bool:
        """Bring interface up"""
        try:
            # Get current flags
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFFLAGS, ifr)
            flags = struct.unpack('16sh', res[:18])[1]
            
            # Set UP flag
            flags |= IFF.UP
            ifr = struct.pack('16sh', ifname.encode('utf-8'), flags)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFFLAGS, ifr)
            
            return True
        except Exception as e:
            logger.error(f"Failed to bring up {ifname}: {e}")
            return False
            
    def set_interface_down(self, ifname: str) -> bool:
        """Bring interface down"""
        try:
            # Get current flags
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFFLAGS, ifr)
            flags = struct.unpack('16sh', res[:18])[1]
            
            # Clear UP flag
            flags &= ~IFF.UP
            ifr = struct.pack('16sh', ifname.encode('utf-8'), flags)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFFLAGS, ifr)
            
            return True
        except Exception as e:
            logger.error(f"Failed to bring down {ifname}: {e}")
            return False
            
    def set_interface_address(self, ifname: str, ip_address: str, netmask: str) -> bool:
        """Set interface IP address"""
        try:
            # Set IP address
            addr = socket.inet_aton(ip_address)
            ifr = struct.pack('16sH2s4s8s', ifname.encode('utf-8'), socket.AF_INET, b'\x00'*2, addr, b'\x00'*8)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFADDR, ifr)
            
            # Set netmask
            mask = socket.inet_aton(netmask)
            ifr = struct.pack('16sH2s4s8s', ifname.encode('utf-8'), socket.AF_INET, b'\x00'*2, mask, b'\x00'*8)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFNETMASK, ifr)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set address on {ifname}: {e}")
            return False
            
    def set_interface_mtu(self, ifname: str, mtu: int) -> bool:
        """Set interface MTU"""
        try:
            ifr = struct.pack('16si', ifname.encode('utf-8'), mtu)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFMTU, ifr)
            return True
        except Exception as e:
            logger.error(f"Failed to set MTU on {ifname}: {e}")
            return False
            
    def add_route(self, destination: str, netmask: str, gateway: str, ifname: str) -> bool:
        """Add route using ip command"""
        try:
            if destination == "0.0.0.0":
                # Default route
                subprocess.run(
                    ['ip', 'route', 'add', 'default', 'via', gateway, 'dev', ifname],
                    check=True,
                    capture_output=True
                )
            else:
                # Specific route
                import ipaddress
                network = ipaddress.ip_network(f"{destination}/{netmask}")
                subprocess.run(
                    ['ip', 'route', 'add', str(network), 'via', gateway, 'dev', ifname],
                    check=True,
                    capture_output=True
                )
            return True
        except Exception as e:
            logger.error(f"Failed to add route: {e}")
            return False
            
    def delete_route(self, destination: str, netmask: str) -> bool:
        """Delete route using ip command"""
        try:
            if destination == "0.0.0.0":
                # Default route
                subprocess.run(
                    ['ip', 'route', 'del', 'default'],
                    check=True,
                    capture_output=True
                )
            else:
                # Specific route
                import ipaddress
                network = ipaddress.ip_network(f"{destination}/{netmask}")
                subprocess.run(
                    ['ip', 'route', 'del', str(network)],
                    check=True,
                    capture_output=True
                )
            return True
        except Exception as e:
            logger.error(f"Failed to delete route: {e}")
            return False
            
    def get_routing_table(self) -> List[Dict[str, Any]]:
        """Get routing table"""
        routes = []
        
        try:
            # Read from /proc/net/route
            with open('/proc/net/route', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 8:
                    route = {
                        'interface': parts[0],
                        'destination': socket.inet_ntoa(struct.pack('<I', int(parts[1], 16))),
                        'gateway': socket.inet_ntoa(struct.pack('<I', int(parts[2], 16))),
                        'flags': int(parts[3], 16),
                        'refcnt': int(parts[4]),
                        'use': int(parts[5]),
                        'metric': int(parts[6]),
                        'mask': socket.inet_ntoa(struct.pack('<I', int(parts[7], 16)))
                    }
                    routes.append(route)
                    
        except Exception as e:
            logger.error(f"Failed to read routing table: {e}")
            
        return routes
        
    def get_arp_table(self) -> List[Dict[str, str]]:
        """Get ARP table"""
        arp_entries = []
        
        try:
            # Read from /proc/net/arp
            with open('/proc/net/arp', 'r') as f:
                lines = f.readlines()[1:]  # Skip header
                
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 6:
                    entry = {
                        'ip_address': parts[0],
                        'hw_type': parts[1],
                        'flags': parts[2],
                        'mac_address': parts[3],
                        'mask': parts[4],
                        'interface': parts[5]
                    }
                    arp_entries.append(entry)
                    
        except Exception as e:
            logger.error(f"Failed to read ARP table: {e}")
            
        return arp_entries
        
    def add_arp_entry(self, ip_address: str, mac_address: str, ifname: str) -> bool:
        """Add static ARP entry"""
        try:
            subprocess.run(
                ['arp', '-s', ip_address, mac_address, '-i', ifname],
                check=True,
                capture_output=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to add ARP entry: {e}")
            return False
            
    def delete_arp_entry(self, ip_address: str) -> bool:
        """Delete ARP entry"""
        try:
            subprocess.run(
                ['arp', '-d', ip_address],
                check=True,
                capture_output=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete ARP entry: {e}")
            return False
            
    def create_socket(self, family: int, sock_type: int, protocol: int = 0) -> socket.socket:
        """Create network socket"""
        return socket.socket(family, sock_type, protocol)
        
    def bind_socket(self, sock: socket.socket, address: Tuple[str, int]):
        """Bind socket to address"""
        sock.bind(address)
        
    def listen_socket(self, sock: socket.socket, backlog: int = 5):
        """Listen on socket"""
        sock.listen(backlog)
        
    def accept_connection(self, sock: socket.socket) -> Tuple[socket.socket, Tuple[str, int]]:
        """Accept connection on socket"""
        return sock.accept()
        
    def connect_socket(self, sock: socket.socket, address: Tuple[str, int]):
        """Connect socket to address"""
        sock.connect(address)
        
    def send_data(self, sock: socket.socket, data: bytes, flags: int = 0) -> int:
        """Send data on socket"""
        return sock.send(data, flags)
        
    def receive_data(self, sock: socket.socket, size: int, flags: int = 0) -> bytes:
        """Receive data from socket"""
        return sock.recv(size, flags)
        
    def create_raw_socket(self, protocol: int = socket.IPPROTO_RAW) -> socket.socket:
        """Create raw socket (requires root)"""
        return socket.socket(socket.AF_INET, socket.SOCK_RAW, protocol)
        
    def send_raw_packet(self, sock: socket.socket, packet: bytes, dest: Tuple[str, int]):
        """Send raw packet"""
        sock.sendto(packet, dest)
        
    def receive_raw_packet(self, sock: socket.socket, size: int = 65535) -> Tuple[bytes, Tuple[str, int]]:
        """Receive raw packet"""
        return sock.recvfrom(size)
        
    def set_promiscuous_mode(self, ifname: str, enable: bool = True) -> bool:
        """Set interface promiscuous mode"""
        try:
            # Get current flags
            ifr = struct.pack('256s', ifname.encode('utf-8'))
            res = fcntl.ioctl(self.sock.fileno(), SIOC.SIOCGIFFLAGS, ifr)
            flags = struct.unpack('16sh', res[:18])[1]
            
            # Set or clear PROMISC flag
            if enable:
                flags |= IFF.PROMISC
            else:
                flags &= ~IFF.PROMISC
                
            ifr = struct.pack('16sh', ifname.encode('utf-8'), flags)
            fcntl.ioctl(self.sock.fileno(), SIOC.SIOCSIFFLAGS, ifr)
            
            return True
        except Exception as e:
            logger.error(f"Failed to set promiscuous mode on {ifname}: {e}")
            return False


# Global network stack instance
_network_stack = None

def get_network_stack() -> RealNetworkStack:
    """Get global network stack instance"""
    global _network_stack
    if _network_stack is None:
        _network_stack = RealNetworkStack()
    return _network_stack
"""
Network Device Driver for KOS
Implements actual hardware access for network interfaces (Ethernet, WiFi)
"""

import os
import stat
import struct
import fcntl
import socket
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple, Union
from pathlib import Path

logger = logging.getLogger('kos.devices.network')

# ioctl commands for Linux network interfaces
SIOCGIFNAME = 0x8910      # Get interface name
SIOCGIFCONF = 0x8912      # Get interface list
SIOCGIFFLAGS = 0x8913     # Get interface flags
SIOCSIFFLAGS = 0x8914     # Set interface flags
SIOCGIFADDR = 0x8915      # Get interface address
SIOCSIFADDR = 0x8916      # Set interface address
SIOCGIFNETMASK = 0x891b   # Get netmask
SIOCSIFNETMASK = 0x891c   # Set netmask
SIOCGIFMTU = 0x8921       # Get MTU
SIOCSIFMTU = 0x8922       # Set MTU
SIOCGIFHWADDR = 0x8927    # Get hardware address
SIOCSIFHWADDR = 0x8924    # Set hardware address
SIOCGIFSLAVE = 0x8929     # Get slave device
SIOCGIFINDEX = 0x8933     # Get interface index
SIOCGIFCOUNT = 0x8938     # Get number of interfaces
SIOCGIFBR = 0x8940        # Get bridge info
SIOCGIFTXQLEN = 0x8942    # Get transmit queue length
SIOCSIFTXQLEN = 0x8943    # Set transmit queue length

# Interface flags
IFF_UP = 0x1              # Interface is up
IFF_BROADCAST = 0x2       # Broadcast address valid
IFF_DEBUG = 0x4           # Turn on debugging
IFF_LOOPBACK = 0x8        # Is a loopback net
IFF_POINTOPOINT = 0x10    # Interface is point-to-point
IFF_NOTRAILERS = 0x20     # Avoid use of trailers
IFF_RUNNING = 0x40        # Resources allocated
IFF_NOARP = 0x80          # No ARP protocol
IFF_PROMISC = 0x100       # Promiscuous mode
IFF_ALLMULTI = 0x200      # Receive all multicast
IFF_MASTER = 0x400        # Master of a load balancer
IFF_SLAVE = 0x800         # Slave of a load balancer
IFF_MULTICAST = 0x1000    # Supports multicast

# Ethtool commands
ETHTOOL_GSET = 0x00000001 # Get settings
ETHTOOL_SSET = 0x00000002 # Set settings
ETHTOOL_GDRVINFO = 0x00000003 # Get driver info
ETHTOOL_GLINK = 0x0000000a # Get link status
ETHTOOL_GSTATS = 0x0000001d # Get statistics


class NetworkInterface:
    """Base class for network interfaces"""
    
    def __init__(self, name: str):
        self.name = name
        self.index = self._get_index()
        self._sock = None
        self._lock = threading.RLock()
        self.info = self._detect_interface()
    
    def _get_socket(self) -> socket.socket:
        """Get or create socket for ioctl operations"""
        if self._sock is None:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._sock
    
    def _get_index(self) -> int:
        """Get interface index"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), 0, b'\x00' * 14)
            result = fcntl.ioctl(sock.fileno(), SIOCGIFINDEX, ifreq)
            sock.close()
            return struct.unpack('16sH14s', result)[1]
        except:
            return -1
    
    def _detect_interface(self) -> Dict[str, Any]:
        """Detect interface type and capabilities"""
        info = {
            'name': self.name,
            'index': self.index,
            'type': 'unknown',
            'exists': False
        }
        
        # Check sysfs
        sysfs_path = f"/sys/class/net/{self.name}"
        if os.path.exists(sysfs_path):
            info['exists'] = True
            
            # Read type
            type_path = f"{sysfs_path}/type"
            if os.path.exists(type_path):
                with open(type_path) as f:
                    arp_type = int(f.read().strip())
                    # ARPHRD types from if_arp.h
                    if arp_type == 1:
                        info['type'] = 'ethernet'
                    elif arp_type == 801:
                        info['type'] = 'wifi'
                    elif arp_type == 772:
                        info['type'] = 'loopback'
                    elif arp_type == 65534:
                        info['type'] = 'none'
            
            # Read device info
            for attr in ['address', 'mtu', 'speed', 'duplex', 'operstate']:
                attr_path = f"{sysfs_path}/{attr}"
                if os.path.exists(attr_path):
                    try:
                        with open(attr_path) as f:
                            info[attr] = f.read().strip()
                    except:
                        pass
        
        return info
    
    def get_flags(self) -> int:
        """Get interface flags"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), 0, b'\x00' * 14)
                result = fcntl.ioctl(sock.fileno(), SIOCGIFFLAGS, ifreq)
                flags = struct.unpack('16sH14s', result)[1]
                return flags
            except Exception as e:
                logger.error(f"Failed to get flags for {self.name}: {e}")
                return 0
    
    def set_flags(self, flags: int) -> bool:
        """Set interface flags"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), flags, b'\x00' * 14)
                fcntl.ioctl(sock.fileno(), SIOCSIFFLAGS, ifreq)
                return True
            except Exception as e:
                logger.error(f"Failed to set flags for {self.name}: {e}")
                return False
    
    def is_up(self) -> bool:
        """Check if interface is up"""
        return bool(self.get_flags() & IFF_UP)
    
    def bring_up(self) -> bool:
        """Bring interface up"""
        flags = self.get_flags()
        return self.set_flags(flags | IFF_UP)
    
    def bring_down(self) -> bool:
        """Bring interface down"""
        flags = self.get_flags()
        return self.set_flags(flags & ~IFF_UP)
    
    def get_address(self) -> Optional[str]:
        """Get IP address"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), 0, b'\x00' * 14)
                result = fcntl.ioctl(sock.fileno(), SIOCGIFADDR, ifreq)
                addr = socket.inet_ntoa(result[20:24])
                return addr
            except:
                return None
    
    def set_address(self, address: str) -> bool:
        """Set IP address"""
        with self._lock:
            try:
                sock = self._get_socket()
                addr_bytes = socket.inet_aton(address)
                ifreq = struct.pack('16sH2s4s8s', 
                                  self.name.encode('utf-8'), 
                                  socket.AF_INET,
                                  b'\x00' * 2,
                                  addr_bytes,
                                  b'\x00' * 8)
                fcntl.ioctl(sock.fileno(), SIOCSIFADDR, ifreq)
                return True
            except Exception as e:
                logger.error(f"Failed to set address for {self.name}: {e}")
                return False
    
    def get_netmask(self) -> Optional[str]:
        """Get netmask"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), 0, b'\x00' * 14)
                result = fcntl.ioctl(sock.fileno(), SIOCGIFNETMASK, ifreq)
                mask = socket.inet_ntoa(result[20:24])
                return mask
            except:
                return None
    
    def set_netmask(self, netmask: str) -> bool:
        """Set netmask"""
        with self._lock:
            try:
                sock = self._get_socket()
                mask_bytes = socket.inet_aton(netmask)
                ifreq = struct.pack('16sH2s4s8s',
                                  self.name.encode('utf-8'),
                                  socket.AF_INET,
                                  b'\x00' * 2,
                                  mask_bytes,
                                  b'\x00' * 8)
                fcntl.ioctl(sock.fileno(), SIOCSIFNETMASK, ifreq)
                return True
            except Exception as e:
                logger.error(f"Failed to set netmask for {self.name}: {e}")
                return False
    
    def get_mtu(self) -> int:
        """Get MTU"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), 0, b'\x00' * 14)
                result = fcntl.ioctl(sock.fileno(), SIOCGIFMTU, ifreq)
                mtu = struct.unpack('16sH14s', result)[1]
                return mtu
            except:
                return 1500  # Default MTU
    
    def set_mtu(self, mtu: int) -> bool:
        """Set MTU"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16sH14s', self.name.encode('utf-8'), mtu, b'\x00' * 14)
                fcntl.ioctl(sock.fileno(), SIOCSIFMTU, ifreq)
                return True
            except Exception as e:
                logger.error(f"Failed to set MTU for {self.name}: {e}")
                return False
    
    def get_mac_address(self) -> Optional[str]:
        """Get MAC address"""
        with self._lock:
            try:
                sock = self._get_socket()
                ifreq = struct.pack('16s14s', self.name.encode('utf-8'), b'\x00' * 14)
                result = fcntl.ioctl(sock.fileno(), SIOCGIFHWADDR, ifreq)
                mac_bytes = result[18:24]
                mac = ':'.join(f'{b:02x}' for b in mac_bytes)
                return mac
            except:
                return None
    
    def get_statistics(self) -> Dict[str, int]:
        """Get interface statistics"""
        stats = {}
        
        # Read from sysfs
        stats_dir = f"/sys/class/net/{self.name}/statistics"
        if os.path.exists(stats_dir):
            for stat_name in ['rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped',
                            'tx_bytes', 'tx_packets', 'tx_errors', 'tx_dropped',
                            'collisions', 'multicast']:
                stat_path = f"{stats_dir}/{stat_name}"
                if os.path.exists(stat_path):
                    try:
                        with open(stat_path) as f:
                            stats[stat_name] = int(f.read().strip())
                    except:
                        stats[stat_name] = 0
        
        return stats
    
    def set_promiscuous(self, enable: bool) -> bool:
        """Enable/disable promiscuous mode"""
        flags = self.get_flags()
        if enable:
            flags |= IFF_PROMISC
        else:
            flags &= ~IFF_PROMISC
        return self.set_flags(flags)
    
    def __del__(self):
        """Cleanup socket on destruction"""
        if self._sock:
            self._sock.close()


class EthernetInterface(NetworkInterface):
    """Ethernet interface driver"""
    
    def get_link_status(self) -> bool:
        """Get link status using ethtool"""
        try:
            # Try sysfs first
            carrier_path = f"/sys/class/net/{self.name}/carrier"
            if os.path.exists(carrier_path):
                with open(carrier_path) as f:
                    return f.read().strip() == '1'
            
            # Fallback to ethtool ioctl
            with self._lock:
                sock = self._get_socket()
                
                # struct ethtool_value
                ecmd = struct.pack('II', ETHTOOL_GLINK, 0)
                ifreq = struct.pack('16sP', self.name.encode('utf-8'), id(ecmd))
                
                try:
                    fcntl.ioctl(sock.fileno(), 0x8946, ifreq)  # SIOCETHTOOL
                    _, link = struct.unpack('II', ecmd)
                    return bool(link)
                except:
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to get link status: {e}")
            return False
    
    def get_speed_duplex(self) -> Tuple[int, str]:
        """Get speed and duplex settings"""
        speed = -1
        duplex = 'unknown'
        
        # Read from sysfs
        speed_path = f"/sys/class/net/{self.name}/speed"
        if os.path.exists(speed_path):
            try:
                with open(speed_path) as f:
                    speed = int(f.read().strip())
            except:
                pass
        
        duplex_path = f"/sys/class/net/{self.name}/duplex"
        if os.path.exists(duplex_path):
            try:
                with open(duplex_path) as f:
                    duplex = f.read().strip()
            except:
                pass
        
        return speed, duplex
    
    def set_speed_duplex(self, speed: int, duplex: str) -> bool:
        """Set speed and duplex (requires ethtool)"""
        # This would use ETHTOOL_SSET ioctl
        # Simplified for demonstration
        logger.warning(f"Setting speed/duplex requires ethtool support")
        return False


class WiFiInterface(NetworkInterface):
    """WiFi interface driver"""
    
    def __init__(self, name: str):
        super().__init__(name)
        self.wireless_extensions = self._check_wireless_extensions()
    
    def _check_wireless_extensions(self) -> bool:
        """Check if interface supports wireless extensions"""
        wireless_path = f"/sys/class/net/{self.name}/wireless"
        return os.path.exists(wireless_path)
    
    def scan_networks(self) -> List[Dict[str, Any]]:
        """Scan for WiFi networks"""
        networks = []
        
        if not self.wireless_extensions:
            return networks
        
        # This would use wireless extensions or nl80211
        # Simplified - read from wpa_supplicant if available
        try:
            # Try using iw command output parsing
            import subprocess
            result = subprocess.run(['iw', 'dev', self.name, 'scan'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse scan results
                current_network = {}
                for line in result.stdout.split('\n'):
                    if line.startswith('BSS'):
                        if current_network:
                            networks.append(current_network)
                        bssid = line.split()[1].replace('(on', '')
                        current_network = {'bssid': bssid}
                    elif 'SSID:' in line:
                        current_network['ssid'] = line.split(':', 1)[1].strip()
                    elif 'signal:' in line:
                        signal = line.split(':')[1].strip().split()[0]
                        current_network['signal'] = int(signal)
                    elif 'DS Parameter set:' in line:
                        channel = line.split(':')[1].strip()
                        current_network['channel'] = int(channel)
                
                if current_network:
                    networks.append(current_network)
                    
        except Exception as e:
            logger.error(f"Failed to scan networks: {e}")
        
        return networks
    
    def get_current_network(self) -> Optional[Dict[str, Any]]:
        """Get currently connected network info"""
        if not self.wireless_extensions:
            return None
        
        # Read from sysfs/procfs or use wireless extensions
        # Simplified implementation
        return None
    
    def connect_network(self, ssid: str, password: Optional[str] = None) -> bool:
        """Connect to a WiFi network"""
        # This would interface with wpa_supplicant
        logger.warning("WiFi connection requires wpa_supplicant integration")
        return False


class NetworkDriverManager:
    """Manages network device drivers"""
    
    def __init__(self):
        self.interfaces: Dict[str, NetworkInterface] = {}
        self._lock = threading.RLock()
        self._scan_interfaces()
    
    def _scan_interfaces(self):
        """Scan for network interfaces"""
        try:
            # Get all network interfaces
            for iface in os.listdir('/sys/class/net'):
                self._register_interface(iface)
        except Exception as e:
            logger.error(f"Failed to scan interfaces: {e}")
    
    def _register_interface(self, name: str):
        """Register a network interface"""
        with self._lock:
            if name in self.interfaces:
                return
            
            try:
                # Determine interface type
                type_path = f"/sys/class/net/{name}/type"
                wireless_path = f"/sys/class/net/{name}/wireless"
                
                if os.path.exists(wireless_path):
                    driver = WiFiInterface(name)
                else:
                    driver = EthernetInterface(name)
                
                self.interfaces[name] = driver
                logger.info(f"Registered network interface: {name}")
                
            except Exception as e:
                logger.error(f"Failed to register interface {name}: {e}")
    
    def get_interface(self, name: str) -> Optional[NetworkInterface]:
        """Get a network interface driver"""
        with self._lock:
            return self.interfaces.get(name)
    
    def list_interfaces(self) -> List[str]:
        """List all registered interfaces"""
        with self._lock:
            return list(self.interfaces.keys())
    
    def get_interface_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive interface information"""
        iface = self.get_interface(name)
        if not iface:
            return None
        
        info = iface.info.copy()
        
        # Add runtime information
        info['flags'] = iface.get_flags()
        info['is_up'] = iface.is_up()
        info['ip_address'] = iface.get_address()
        info['netmask'] = iface.get_netmask()
        info['mac_address'] = iface.get_mac_address()
        info['mtu'] = iface.get_mtu()
        info['statistics'] = iface.get_statistics()
        
        # Add type-specific info
        if isinstance(iface, EthernetInterface):
            info['link_status'] = iface.get_link_status()
            speed, duplex = iface.get_speed_duplex()
            info['speed'] = speed
            info['duplex'] = duplex
        
        elif isinstance(iface, WiFiInterface):
            info['wireless'] = True
            info['current_network'] = iface.get_current_network()
        
        return info
    
    def configure_interface(self, name: str, config: Dict[str, Any]) -> bool:
        """Configure a network interface"""
        iface = self.get_interface(name)
        if not iface:
            return False
        
        try:
            # Apply configuration
            if 'up' in config:
                if config['up']:
                    iface.bring_up()
                else:
                    iface.bring_down()
            
            if 'address' in config:
                iface.set_address(config['address'])
            
            if 'netmask' in config:
                iface.set_netmask(config['netmask'])
            
            if 'mtu' in config:
                iface.set_mtu(config['mtu'])
            
            if 'promiscuous' in config:
                iface.set_promiscuous(config['promiscuous'])
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure interface {name}: {e}")
            return False


# Global instance
_network_manager = None

def get_network_manager() -> NetworkDriverManager:
    """Get global network manager instance"""
    global _network_manager
    if _network_manager is None:
        _network_manager = NetworkDriverManager()
    return _network_manager
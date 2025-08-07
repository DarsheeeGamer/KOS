"""
Network Device Handler for KOS Hardware Pool
Handles all network interfaces and bandwidth aggregation
"""

import os
import sys
import subprocess
import platform
import socket
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .base import (
    HardwareDevice, HardwareAbstractionLayer, DeviceType,
    DeviceCapabilities, ComputeCapability, MemoryType
)

logger = logging.getLogger(__name__)

@dataclass
class NetworkCapabilities:
    """Network-specific capabilities"""
    max_speed: float  # Mbps
    current_speed: float  # Mbps
    duplex: str  # full, half
    interface_type: str  # ethernet, wifi, infiniband, etc.
    protocol: str  # TCP, UDP, RDMA, etc.
    mtu: int  # Maximum transmission unit
    supports_offload: bool  # Hardware offloading
    supports_rdma: bool  # Remote Direct Memory Access
    supports_sr_iov: bool  # Single Root I/O Virtualization

class NetworkDevice(HardwareAbstractionLayer):
    """Network device handler for bandwidth pooling"""
    
    def __init__(self):
        self.devices = []
        self.active_connections = {}
        self.bandwidth_pool = 0.0
    
    def discover_devices(self) -> List[HardwareDevice]:
        """Discover all network devices"""
        devices = []
        
        try:
            if platform.system() == "Linux":
                devices.extend(self._discover_linux_network())
            elif platform.system() == "Darwin":  # macOS
                devices.extend(self._discover_macos_network())
            elif platform.system() == "Windows":
                devices.extend(self._discover_windows_network())
        
        except Exception as e:
            logger.error(f"Error discovering network devices: {e}")
        
        return devices
    
    def _discover_linux_network(self) -> List[HardwareDevice]:
        """Discover network devices on Linux"""
        devices = []
        
        try:
            # Get network interfaces
            interfaces = self._get_linux_interfaces()
            
            for interface in interfaces:
                device = self._create_linux_network_device(interface)
                if device:
                    devices.append(device)
        
        except Exception as e:
            logger.error(f"Error discovering Linux network: {e}")
        
        return devices
    
    def _get_linux_interfaces(self) -> List[str]:
        """Get list of network interfaces on Linux"""
        interfaces = []
        
        try:
            # Use /sys/class/net
            net_path = "/sys/class/net"
            if os.path.exists(net_path):
                interfaces = [
                    name for name in os.listdir(net_path)
                    if name != 'lo'  # Skip loopback
                ]
        except:
            # Fallback to ip command
            try:
                result = subprocess.run(['ip', 'link', 'show'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if ':' in line and 'state' in line:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                interface = parts[1].strip()
                                if interface != 'lo':
                                    interfaces.append(interface)
            except:
                pass
        
        return interfaces
    
    def _create_linux_network_device(self, interface: str) -> Optional[HardwareDevice]:
        """Create network device from Linux interface"""
        try:
            # Get interface information
            info = self._get_linux_interface_info(interface)
            
            if not info:
                return None
            
            # Get capabilities
            capabilities = self._get_linux_network_capabilities(interface, info)
            
            return HardwareDevice(
                device_id=f"network_{interface}",
                device_type=DeviceType.NETWORK,
                name=f"{interface} ({info.get('driver', 'Unknown')})",
                vendor=self._extract_network_vendor(info.get('driver', '')),
                model=info.get('driver', 'Unknown'),
                compute_units=1,  # Network processing units (simplified)
                clock_speed=0.0,
                capabilities=self._network_to_device_capabilities(capabilities),
                memory_size=info.get('buffer_size', 1024 * 1024),  # Buffer size
                memory_type=MemoryType.SYSTEM_RAM,
                memory_bandwidth=capabilities.max_speed / 8,  # Mbps to MB/s
                node_id=os.uname().nodename,
                pci_bus=info.get('pci_bus'),
                numa_node=info.get('numa_node', 0),
                temperature=0.0,
                power_usage=info.get('power_usage', 0.0),
                utilization=self._get_interface_utilization(interface),
                available=info.get('state') == 'UP',
                features={
                    'interface_type': capabilities.interface_type,
                    'max_speed': capabilities.max_speed,
                    'mtu': capabilities.mtu,
                    'mac_address': info.get('mac_address'),
                    'ip_addresses': info.get('ip_addresses', []),
                    'supports_offload': capabilities.supports_offload,
                    'supports_rdma': capabilities.supports_rdma
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating Linux network device {interface}: {e}")
            return None
    
    def _get_linux_interface_info(self, interface: str) -> Optional[Dict]:
        """Get detailed interface information on Linux"""
        info = {}
        
        try:
            # Get basic info from /sys/class/net
            sys_path = f"/sys/class/net/{interface}"
            
            # State
            state_path = f"{sys_path}/operstate"
            if os.path.exists(state_path):
                with open(state_path, 'r') as f:
                    info['state'] = f.read().strip().upper()
            
            # MAC address
            address_path = f"{sys_path}/address"
            if os.path.exists(address_path):
                with open(address_path, 'r') as f:
                    info['mac_address'] = f.read().strip()
            
            # MTU
            mtu_path = f"{sys_path}/mtu"
            if os.path.exists(mtu_path):
                with open(mtu_path, 'r') as f:
                    info['mtu'] = int(f.read().strip())
            
            # Speed
            speed_path = f"{sys_path}/speed"
            if os.path.exists(speed_path):
                try:
                    with open(speed_path, 'r') as f:
                        info['speed'] = int(f.read().strip())  # Mbps
                except:
                    pass
            
            # Duplex
            duplex_path = f"{sys_path}/duplex"
            if os.path.exists(duplex_path):
                try:
                    with open(duplex_path, 'r') as f:
                        info['duplex'] = f.read().strip()
                except:
                    pass
            
            # Driver information
            device_path = f"{sys_path}/device"
            if os.path.exists(device_path):
                # Get driver name
                driver_path = f"{device_path}/driver"
                if os.path.exists(driver_path):
                    driver_real = os.path.realpath(driver_path)
                    info['driver'] = os.path.basename(driver_real)
                
                # Get PCI bus
                device_real = os.path.realpath(device_path)
                if 'pci' in device_real:
                    import re
                    match = re.search(r'([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9])', device_real)
                    if match:
                        info['pci_bus'] = match.group(1)
            
            # Get IP addresses
            info['ip_addresses'] = self._get_interface_ips(interface)
            
            return info
        
        except Exception as e:
            logger.error(f"Error getting interface info for {interface}: {e}")
            return None
    
    def _get_interface_ips(self, interface: str) -> List[str]:
        """Get IP addresses for interface"""
        ips = []
        
        try:
            result = subprocess.run([
                'ip', 'addr', 'show', interface
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'inet ' in line:
                        parts = line.strip().split()
                        for i, part in enumerate(parts):
                            if part == 'inet' and i + 1 < len(parts):
                                ip = parts[i + 1].split('/')[0]
                                ips.append(ip)
        except:
            pass
        
        return ips
    
    def _get_linux_network_capabilities(self, interface: str, info: Dict) -> NetworkCapabilities:
        """Get network capabilities for Linux interface"""
        # Determine interface type
        interface_type = "ethernet"  # Default
        
        if interface.startswith('wl') or interface.startswith('wifi'):
            interface_type = "wifi"
        elif interface.startswith('ib'):
            interface_type = "infiniband"
        elif interface.startswith('usb'):
            interface_type = "usb"
        elif 'bond' in interface:
            interface_type = "bonded"
        
        # Get speed
        max_speed = info.get('speed', 1000)  # Default 1 Gbps
        if max_speed <= 0:
            # Estimate based on interface type and driver
            driver = info.get('driver', '').lower()
            if 'ixgbe' in driver or '10g' in driver:
                max_speed = 10000  # 10 Gbps
            elif 'mlx' in driver:  # Mellanox (InfiniBand/Ethernet)
                max_speed = 100000  # 100 Gbps
            elif interface_type == "wifi":
                max_speed = 867  # WiFi 5/6 estimate
            else:
                max_speed = 1000  # 1 Gbps default
        
        # Check for advanced features
        supports_rdma = self._check_rdma_support(interface)
        supports_offload = self._check_offload_support(interface)
        
        return NetworkCapabilities(
            max_speed=max_speed,
            current_speed=max_speed,  # Assume running at max
            duplex=info.get('duplex', 'full'),
            interface_type=interface_type,
            protocol="TCP/UDP",  # Default protocols
            mtu=info.get('mtu', 1500),
            supports_offload=supports_offload,
            supports_rdma=supports_rdma,
            supports_sr_iov=False  # Would need to check PCI device
        )
    
    def _check_rdma_support(self, interface: str) -> bool:
        """Check if interface supports RDMA"""
        try:
            # Check for RDMA devices
            rdma_path = "/sys/class/infiniband"
            if os.path.exists(rdma_path):
                rdma_devices = os.listdir(rdma_path)
                # Would need to map RDMA devices to network interfaces
                return len(rdma_devices) > 0
        except:
            pass
        return False
    
    def _check_offload_support(self, interface: str) -> bool:
        """Check if interface supports hardware offload"""
        try:
            # Check ethtool features
            result = subprocess.run([
                'ethtool', '-k', interface
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Look for offload features
                offload_features = [
                    'tx-checksumming', 'rx-checksumming',
                    'scatter-gather', 'tcp-segmentation-offload',
                    'generic-segmentation-offload'
                ]
                
                for feature in offload_features:
                    if f"{feature}: on" in result.stdout:
                        return True
        except:
            pass
        return False
    
    def _discover_macos_network(self) -> List[HardwareDevice]:
        """Discover network devices on macOS"""
        devices = []
        
        try:
            # Use networksetup to list interfaces
            result = subprocess.run([
                'networksetup', '-listallhardwareports'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                interfaces = self._parse_macos_interfaces(result.stdout)
                
                for interface_info in interfaces:
                    device = self._create_macos_network_device(interface_info)
                    if device:
                        devices.append(device)
        
        except Exception as e:
            logger.error(f"Error discovering macOS network: {e}")
        
        return devices
    
    def _parse_macos_interfaces(self, output: str) -> List[Dict]:
        """Parse macOS networksetup output"""
        interfaces = []
        current_interface = {}
        
        lines = output.strip().split('\n')
        for line in lines:
            line = line.strip()
            
            if line.startswith('Hardware Port:'):
                if current_interface:
                    interfaces.append(current_interface)
                current_interface = {
                    'name': line.split(':', 1)[1].strip()
                }
            elif line.startswith('Device:'):
                current_interface['device'] = line.split(':', 1)[1].strip()
            elif line.startswith('Ethernet Address:'):
                current_interface['mac'] = line.split(':', 1)[1].strip()
        
        if current_interface:
            interfaces.append(current_interface)
        
        return interfaces
    
    def _create_macos_network_device(self, interface_info: Dict) -> Optional[HardwareDevice]:
        """Create network device for macOS"""
        try:
            name = interface_info.get('name', 'Unknown')
            device = interface_info.get('device', 'unknown')
            
            # Skip certain interfaces
            if any(skip in name.lower() for skip in ['bluetooth', 'bridge', 'loopback']):
                return None
            
            # Estimate capabilities
            capabilities = self._estimate_macos_capabilities(name, device)
            
            return HardwareDevice(
                device_id=f"network_{device}",
                device_type=DeviceType.NETWORK,
                name=name,
                vendor=self._extract_network_vendor(name),
                model=name,
                compute_units=1,
                clock_speed=0.0,
                capabilities=self._network_to_device_capabilities(capabilities),
                memory_size=1024 * 1024,  # 1MB buffer estimate
                memory_type=MemoryType.SYSTEM_RAM,
                memory_bandwidth=capabilities.max_speed / 8,
                node_id=os.uname().nodename,
                pci_bus=None,
                numa_node=0,
                temperature=0.0,
                power_usage=0.0,
                utilization=0.0,
                available=True,
                features={
                    'interface_type': capabilities.interface_type,
                    'max_speed': capabilities.max_speed,
                    'mac_address': interface_info.get('mac')
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating macOS network device: {e}")
            return None
    
    def _estimate_macos_capabilities(self, name: str, device: str) -> NetworkCapabilities:
        """Estimate network capabilities on macOS"""
        name_lower = name.lower()
        
        if 'wi-fi' in name_lower or 'wireless' in name_lower:
            # WiFi interface
            return NetworkCapabilities(
                max_speed=1200,  # WiFi 6 estimate
                current_speed=867,
                duplex="full",
                interface_type="wifi",
                protocol="TCP/UDP",
                mtu=1500,
                supports_offload=True,
                supports_rdma=False,
                supports_sr_iov=False
            )
        
        elif 'thunderbolt' in name_lower:
            # Thunderbolt Ethernet
            return NetworkCapabilities(
                max_speed=10000,  # 10 Gbps
                current_speed=10000,
                duplex="full",
                interface_type="ethernet",
                protocol="TCP/UDP",
                mtu=1500,
                supports_offload=True,
                supports_rdma=False,
                supports_sr_iov=False
            )
        
        else:
            # Standard Ethernet
            return NetworkCapabilities(
                max_speed=1000,  # 1 Gbps
                current_speed=1000,
                duplex="full",
                interface_type="ethernet",
                protocol="TCP/UDP",
                mtu=1500,
                supports_offload=True,
                supports_rdma=False,
                supports_sr_iov=False
            )
    
    def _discover_windows_network(self) -> List[HardwareDevice]:
        """Discover network devices on Windows"""
        devices = []
        
        try:
            # Use wmic to get network adapters
            result = subprocess.run([
                'wmic', 'path', 'win32_networkadapter',
                'where', 'NetConnectionStatus=2',  # Connected
                'get', 'Name,Speed,MACAddress,PNPDeviceID',
                '/format:csv'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    headers = lines[0].split(',')
                    
                    for line in lines[1:]:
                        if line.strip():
                            values = line.split(',')
                            if len(values) >= len(headers):
                                adapter_info = dict(zip(headers, values))
                                device = self._create_windows_network_device(adapter_info)
                                if device:
                                    devices.append(device)
        
        except Exception as e:
            logger.error(f"Error discovering Windows network: {e}")
        
        return devices
    
    def _create_windows_network_device(self, adapter_info: Dict) -> Optional[HardwareDevice]:
        """Create network device for Windows"""
        try:
            name = adapter_info.get('Name', 'Unknown').strip()
            speed_str = adapter_info.get('Speed', '0').strip()
            mac = adapter_info.get('MACAddress', '').strip()
            
            # Skip virtual adapters
            if any(skip in name.lower() for skip in [
                'virtual', 'loopback', 'teredo', 'isatap', 'hyper-v'
            ]):
                return None
            
            # Parse speed
            speed_bps = int(speed_str) if speed_str.isdigit() else 100000000  # 100 Mbps default
            speed_mbps = speed_bps / 1000000
            
            # Estimate capabilities
            capabilities = self._estimate_windows_capabilities(name, speed_mbps)
            
            return HardwareDevice(
                device_id=f"network_{hash(name) % 10000}",
                device_type=DeviceType.NETWORK,
                name=name,
                vendor=self._extract_network_vendor(name),
                model=name,
                compute_units=1,
                clock_speed=0.0,
                capabilities=self._network_to_device_capabilities(capabilities),
                memory_size=1024 * 1024,
                memory_type=MemoryType.SYSTEM_RAM,
                memory_bandwidth=capabilities.max_speed / 8,
                node_id=platform.node(),
                pci_bus=None,
                numa_node=0,
                temperature=0.0,
                power_usage=0.0,
                utilization=0.0,
                available=True,
                features={
                    'interface_type': capabilities.interface_type,
                    'max_speed': capabilities.max_speed,
                    'mac_address': mac
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating Windows network device: {e}")
            return None
    
    def _estimate_windows_capabilities(self, name: str, speed_mbps: float) -> NetworkCapabilities:
        """Estimate capabilities for Windows adapter"""
        name_lower = name.lower()
        
        # Determine interface type
        if 'wi-fi' in name_lower or 'wireless' in name_lower:
            interface_type = "wifi"
        elif 'bluetooth' in name_lower:
            interface_type = "bluetooth"
        else:
            interface_type = "ethernet"
        
        return NetworkCapabilities(
            max_speed=speed_mbps,
            current_speed=speed_mbps,
            duplex="full",
            interface_type=interface_type,
            protocol="TCP/UDP",
            mtu=1500,
            supports_offload=True,  # Assume modern adapters support it
            supports_rdma=False,
            supports_sr_iov=False
        )
    
    def _network_to_device_capabilities(self, net_caps: NetworkCapabilities) -> DeviceCapabilities:
        """Convert network capabilities to device capabilities"""
        return DeviceCapabilities(
            compute_capabilities=[],  # Network doesn't compute
            memory_bandwidth=net_caps.max_speed / 8,  # Mbps to MB/s
            compute_power=0.0,
            max_threads=0,
            max_blocks=0,
            warp_size=0,
            shared_memory_size=0,
            register_count=0,
            tensor_cores=0,
            rt_cores=0,
            special_functions=[
                'packet_processing',
                'checksum_offload' if net_caps.supports_offload else '',
                'rdma' if net_caps.supports_rdma else '',
                'sr_iov' if net_caps.supports_sr_iov else ''
            ]
        )
    
    def _extract_network_vendor(self, name_or_driver: str) -> str:
        """Extract vendor from adapter name or driver"""
        name_lower = name_or_driver.lower()
        
        vendors = [
            ('intel', 'Intel'),
            ('realtek', 'Realtek'), 
            ('broadcom', 'Broadcom'),
            ('qualcomm', 'Qualcomm'),
            ('marvell', 'Marvell'),
            ('nvidia', 'NVIDIA'),
            ('mellanox', 'Mellanox'),
            ('cisco', 'Cisco'),
            ('apple', 'Apple'),
            ('microsoft', 'Microsoft')
        ]
        
        for keyword, vendor in vendors:
            if keyword in name_lower:
                return vendor
        
        return "Unknown"
    
    def _get_interface_utilization(self, interface: str) -> float:
        """Get current interface utilization"""
        try:
            # Would read from /proc/net/dev or use sar/iostat
            # For now, return 0
            return 0.0
        except:
            return 0.0
    
    def get_total_bandwidth(self) -> float:
        """Get total available bandwidth across all interfaces"""
        devices = self.discover_devices()
        total_bandwidth = 0.0
        
        for device in devices:
            if device.available:
                total_bandwidth += device.memory_bandwidth  # Already in MB/s
        
        return total_bandwidth
    
    def allocate_bandwidth(self, required_mbps: float) -> List[str]:
        """Allocate bandwidth across multiple interfaces"""
        devices = self.discover_devices()
        available_devices = [d for d in devices if d.available]
        
        # Sort by bandwidth (highest first)
        available_devices.sort(key=lambda d: d.memory_bandwidth, reverse=True)
        
        allocated = []
        remaining = required_mbps
        
        for device in available_devices:
            if remaining <= 0:
                break
            
            device_bandwidth = device.memory_bandwidth * 8  # MB/s to Mbps
            if device_bandwidth > 0:
                allocated.append(device.device_id)
                remaining -= device_bandwidth
        
        return allocated if remaining <= 0 else []
    
    def get_device_info(self, device_id: str) -> HardwareDevice:
        """Get current network device information"""
        devices = self.discover_devices()
        for device in devices:
            if device.device_id == device_id:
                # Update utilization
                interface = device_id.replace('network_', '')
                device.utilization = self._get_interface_utilization(interface)
                return device
        return None
    
    def allocate_memory(self, device_id: str, size: int) -> Optional[int]:
        """Allocate network buffer"""
        # Network devices use buffers for packet processing
        try:
            buffer = bytearray(size)
            return id(buffer)
        except:
            return None
    
    def free_memory(self, device_id: str, ptr: int):
        """Free network buffer"""
        pass
    
    def transfer_data(self, src_device: str, dst_device: str,
                     src_ptr: int, dst_ptr: int, size: int):
        """Transfer data over network"""
        # Would implement network transfer protocols
        pass
    
    def execute_kernel(self, device_id: str, kernel: Any, args: List):
        """Network devices don't execute kernels"""
        return None
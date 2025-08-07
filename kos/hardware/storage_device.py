"""
Storage Device Handler for KOS Hardware Pool
Handles all storage devices (NVMe, SSD, HDD, etc.)
"""

import os
import sys
import subprocess
import platform
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from .base import (
    HardwareDevice, HardwareAbstractionLayer, DeviceType,
    DeviceCapabilities, ComputeCapability, MemoryType
)

logger = logging.getLogger(__name__)

@dataclass
class StorageCapabilities:
    """Storage-specific capabilities"""
    read_speed: float  # MB/s
    write_speed: float  # MB/s
    random_read_iops: int
    random_write_iops: int
    interface: str  # NVMe, SATA, etc.
    protocol: str  # PCIe, SATA, USB, etc.
    form_factor: str  # M.2, 2.5", 3.5", etc.

class StorageDevice(HardwareAbstractionLayer):
    """Storage device handler"""
    
    def __init__(self):
        self.devices = []
        self.mount_points = {}
    
    def discover_devices(self) -> List[HardwareDevice]:
        """Discover all storage devices"""
        devices = []
        
        try:
            if platform.system() == "Linux":
                devices.extend(self._discover_linux_storage())
            elif platform.system() == "Darwin":  # macOS
                devices.extend(self._discover_macos_storage())
            elif platform.system() == "Windows":
                devices.extend(self._discover_windows_storage())
        
        except Exception as e:
            logger.error(f"Error discovering storage devices: {e}")
        
        return devices
    
    def _discover_linux_storage(self) -> List[HardwareDevice]:
        """Discover storage devices on Linux"""
        devices = []
        
        try:
            # Use lsblk to get block devices
            result = subprocess.run([
                'lsblk', '-J', '-o', 
                'NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,MODEL,SERIAL,TRAN'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                
                for device in data.get('blockdevices', []):
                    if device.get('type') == 'disk':
                        storage_device = self._create_linux_storage_device(device)
                        if storage_device:
                            devices.append(storage_device)
        
        except Exception as e:
            logger.error(f"Error discovering Linux storage: {e}")
        
        return devices
    
    def _create_linux_storage_device(self, device_info: Dict) -> Optional[HardwareDevice]:
        """Create storage device from Linux lsblk info"""
        try:
            name = device_info.get('name', 'unknown')
            size_str = device_info.get('size', '0B')
            model = device_info.get('model', 'Unknown')
            transport = device_info.get('tran', 'unknown')
            
            # Parse size
            size_bytes = self._parse_size(size_str)
            
            # Get detailed device info
            device_path = f"/dev/{name}"
            capabilities = self._get_linux_storage_capabilities(device_path, transport)
            
            return HardwareDevice(
                device_id=f"storage_{name}",
                device_type=DeviceType.STORAGE,
                name=f"{model} ({name})",
                vendor=self._extract_vendor(model),
                model=model,
                compute_units=1,  # Storage devices don't have compute units
                clock_speed=0.0,
                capabilities=self._storage_to_device_capabilities(capabilities),
                memory_size=size_bytes,
                memory_type=MemoryType.SYSTEM_RAM,  # Not really applicable
                memory_bandwidth=capabilities.read_speed,
                node_id=os.uname().nodename,
                pci_bus=self._get_linux_pci_bus(name),
                numa_node=0,
                temperature=self._get_storage_temperature(device_path),
                power_usage=0.0,  # Hard to measure for storage
                utilization=0.0,  # Would need iostat
                available=True,
                features={
                    'interface': capabilities.interface,
                    'protocol': capabilities.protocol,
                    'form_factor': capabilities.form_factor,
                    'mount_point': device_info.get('mountpoint'),
                    'filesystem': device_info.get('fstype')
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating Linux storage device: {e}")
            return None
    
    def _get_linux_storage_capabilities(self, device_path: str, transport: str) -> StorageCapabilities:
        """Get storage capabilities on Linux"""
        # Default capabilities
        capabilities = StorageCapabilities(
            read_speed=500.0,   # MB/s
            write_speed=500.0,  # MB/s
            random_read_iops=10000,
            random_write_iops=10000,
            interface=transport or "unknown",
            protocol=transport or "unknown",
            form_factor="unknown"
        )
        
        try:
            # Try to get real performance data
            # This would require running benchmarks or reading from
            # /sys/block/*/queue/* files
            
            # For NVMe, estimate based on interface
            if transport == 'nvme':
                capabilities.read_speed = 3500.0   # Typical NVMe speeds
                capabilities.write_speed = 3000.0
                capabilities.random_read_iops = 500000
                capabilities.random_write_iops = 450000
                capabilities.interface = "NVMe"
                capabilities.protocol = "PCIe"
                capabilities.form_factor = "M.2"
            
            elif transport == 'sata':
                capabilities.read_speed = 550.0    # SATA SSD speeds
                capabilities.write_speed = 520.0
                capabilities.random_read_iops = 95000
                capabilities.random_write_iops = 90000
                capabilities.interface = "SATA"
                capabilities.protocol = "SATA"
                capabilities.form_factor = "2.5\""
            
            elif transport == 'usb':
                capabilities.read_speed = 100.0    # USB storage
                capabilities.write_speed = 50.0
                capabilities.random_read_iops = 1000
                capabilities.random_write_iops = 500
                capabilities.interface = "USB"
                capabilities.protocol = "USB"
                capabilities.form_factor = "External"
        
        except Exception as e:
            logger.debug(f"Could not get detailed storage capabilities: {e}")
        
        return capabilities
    
    def _discover_macos_storage(self) -> List[HardwareDevice]:
        """Discover storage devices on macOS"""
        devices = []
        
        try:
            # Use diskutil list
            result = subprocess.run(['diskutil', 'list', '-plist'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                import plistlib
                data = plistlib.loads(result.stdout.encode())
                
                for disk_info in data.get('AllDisksAndPartitions', []):
                    if 'DeviceIdentifier' in disk_info:
                        storage_device = self._create_macos_storage_device(disk_info)
                        if storage_device:
                            devices.append(storage_device)
        
        except Exception as e:
            logger.error(f"Error discovering macOS storage: {e}")
        
        return devices
    
    def _create_macos_storage_device(self, disk_info: Dict) -> Optional[HardwareDevice]:
        """Create storage device from macOS diskutil info"""
        try:
            device_id = disk_info.get('DeviceIdentifier', 'unknown')
            
            # Get more detailed info
            result = subprocess.run([
                'diskutil', 'info', '-plist', device_id
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                import plistlib
                detailed_info = plistlib.loads(result.stdout.encode())
                
                name = detailed_info.get('MediaName', 'Unknown')
                size_bytes = detailed_info.get('TotalSize', 0)
                
                # Determine capabilities based on media type
                capabilities = self._estimate_macos_capabilities(detailed_info)
                
                return HardwareDevice(
                    device_id=f"storage_{device_id}",
                    device_type=DeviceType.STORAGE,
                    name=name,
                    vendor=self._extract_vendor(name),
                    model=name,
                    compute_units=1,
                    clock_speed=0.0,
                    capabilities=self._storage_to_device_capabilities(capabilities),
                    memory_size=size_bytes,
                    memory_type=MemoryType.SYSTEM_RAM,
                    memory_bandwidth=capabilities.read_speed,
                    node_id=os.uname().nodename,
                    pci_bus=None,
                    numa_node=0,
                    temperature=0.0,
                    power_usage=0.0,
                    utilization=0.0,
                    available=True,
                    features={
                        'interface': capabilities.interface,
                        'protocol': capabilities.protocol,
                        'internal': detailed_info.get('Internal', False),
                        'removable': detailed_info.get('Removable', False)
                    }
                )
        
        except Exception as e:
            logger.error(f"Error creating macOS storage device: {e}")
        
        return None
    
    def _estimate_macos_capabilities(self, info: Dict) -> StorageCapabilities:
        """Estimate storage capabilities on macOS"""
        # Check if it's internal SSD (likely NVMe)
        is_internal = info.get('Internal', False)
        is_ssd = info.get('SolidState', False)
        
        if is_internal and is_ssd:
            # Likely NVMe SSD
            return StorageCapabilities(
                read_speed=2500.0,
                write_speed=2000.0,
                random_read_iops=400000,
                random_write_iops=350000,
                interface="NVMe",
                protocol="PCIe",
                form_factor="Internal"
            )
        elif is_ssd:
            # External or SATA SSD
            return StorageCapabilities(
                read_speed=500.0,
                write_speed=450.0,
                random_read_iops=80000,
                random_write_iops=75000,
                interface="SATA" if is_internal else "USB",
                protocol="SATA" if is_internal else "USB",
                form_factor="External" if not is_internal else "Internal"
            )
        else:
            # HDD
            return StorageCapabilities(
                read_speed=120.0,
                write_speed=100.0,
                random_read_iops=150,
                random_write_iops=120,
                interface="SATA",
                protocol="SATA",
                form_factor="3.5\"" if is_internal else "External"
            )
    
    def _discover_windows_storage(self) -> List[HardwareDevice]:
        """Discover storage devices on Windows"""
        devices = []
        
        try:
            # Use wmic to get disk drives
            result = subprocess.run([
                'wmic', 'diskdrive', 'get', 
                'DeviceID,Model,Size,InterfaceType,MediaType',
                '/format:csv'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                headers = lines[0].split(',')
                
                for line in lines[1:]:
                    if line.strip():
                        values = line.split(',')
                        if len(values) >= len(headers):
                            device_info = dict(zip(headers, values))
                            storage_device = self._create_windows_storage_device(device_info)
                            if storage_device:
                                devices.append(storage_device)
        
        except Exception as e:
            logger.error(f"Error discovering Windows storage: {e}")
        
        return devices
    
    def _create_windows_storage_device(self, device_info: Dict) -> Optional[HardwareDevice]:
        """Create storage device from Windows wmic info"""
        try:
            device_id = device_info.get('DeviceID', 'unknown')
            model = device_info.get('Model', 'Unknown')
            size_str = device_info.get('Size', '0')
            interface = device_info.get('InterfaceType', 'unknown')
            media_type = device_info.get('MediaType', 'unknown')
            
            size_bytes = int(size_str) if size_str.isdigit() else 0
            
            # Estimate capabilities
            capabilities = self._estimate_windows_capabilities(interface, media_type)
            
            return HardwareDevice(
                device_id=f"storage_{device_id.replace('\\\\', '_')}",
                device_type=DeviceType.STORAGE,
                name=model,
                vendor=self._extract_vendor(model),
                model=model,
                compute_units=1,
                clock_speed=0.0,
                capabilities=self._storage_to_device_capabilities(capabilities),
                memory_size=size_bytes,
                memory_type=MemoryType.SYSTEM_RAM,
                memory_bandwidth=capabilities.read_speed,
                node_id=platform.node(),
                pci_bus=None,
                numa_node=0,
                temperature=0.0,
                power_usage=0.0,
                utilization=0.0,
                available=True,
                features={
                    'interface': capabilities.interface,
                    'protocol': capabilities.protocol,
                    'media_type': media_type
                }
            )
        
        except Exception as e:
            logger.error(f"Error creating Windows storage device: {e}")
        
        return None
    
    def _estimate_windows_capabilities(self, interface: str, media_type: str) -> StorageCapabilities:
        """Estimate capabilities on Windows"""
        interface_lower = interface.lower()
        media_lower = media_type.lower()
        
        # NVMe
        if 'nvme' in interface_lower:
            return StorageCapabilities(
                read_speed=3000.0,
                write_speed=2500.0,
                random_read_iops=450000,
                random_write_iops=400000,
                interface="NVMe",
                protocol="PCIe",
                form_factor="M.2"
            )
        
        # SSD
        elif 'ssd' in media_lower or 'solid' in media_lower:
            return StorageCapabilities(
                read_speed=500.0,
                write_speed=450.0,
                random_read_iops=85000,
                random_write_iops=80000,
                interface="SATA",
                protocol="SATA",
                form_factor="2.5\""
            )
        
        # HDD
        else:
            return StorageCapabilities(
                read_speed=150.0,
                write_speed=130.0,
                random_read_iops=200,
                random_write_iops=180,
                interface="SATA",
                protocol="SATA",
                form_factor="3.5\""
            )
    
    def _storage_to_device_capabilities(self, storage_caps: StorageCapabilities) -> DeviceCapabilities:
        """Convert storage capabilities to device capabilities"""
        return DeviceCapabilities(
            compute_capabilities=[],  # Storage doesn't compute
            memory_bandwidth=storage_caps.read_speed,
            compute_power=0.0,
            max_threads=0,
            max_blocks=0,
            warp_size=0,
            shared_memory_size=0,
            register_count=0,
            tensor_cores=0,
            rt_cores=0,
            special_functions=[
                'sequential_read',
                'sequential_write', 
                'random_read',
                'random_write'
            ]
        )
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string to bytes"""
        if not size_str:
            return 0
        
        # Remove spaces and convert to uppercase
        size_str = size_str.replace(' ', '').upper()
        
        # Extract number and unit
        import re
        match = re.match(r'([0-9.]+)([A-Z]*)', size_str)
        if not match:
            return 0
        
        number = float(match.group(1))
        unit = match.group(2)
        
        # Convert to bytes
        multipliers = {
            'B': 1,
            'K': 1024, 'KB': 1024,
            'M': 1024**2, 'MB': 1024**2,
            'G': 1024**3, 'GB': 1024**3,
            'T': 1024**4, 'TB': 1024**4,
            'P': 1024**5, 'PB': 1024**5
        }
        
        return int(number * multipliers.get(unit, 1))
    
    def _extract_vendor(self, model: str) -> str:
        """Extract vendor from model string"""
        model_lower = model.lower()
        
        vendors = [
            'samsung', 'western digital', 'wd', 'seagate', 'toshiba',
            'intel', 'crucial', 'micron', 'kingston', 'corsair',
            'sandisk', 'sk hynix', 'sabrent', 'adata', 'apple'
        ]
        
        for vendor in vendors:
            if vendor in model_lower:
                return vendor.title()
        
        return "Unknown"
    
    def _get_linux_pci_bus(self, device_name: str) -> Optional[str]:
        """Get PCI bus for Linux storage device"""
        try:
            # For NVMe devices, check /sys/block/*/device
            sys_path = f"/sys/block/{device_name}/device"
            if os.path.exists(sys_path):
                # Read the device path
                real_path = os.path.realpath(sys_path)
                if 'pci' in real_path:
                    # Extract PCI address
                    import re
                    match = re.search(r'([0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9])', real_path)
                    if match:
                        return match.group(1)
        except:
            pass
        return None
    
    def _get_storage_temperature(self, device_path: str) -> float:
        """Get storage device temperature"""
        try:
            # For NVMe drives, try to get temperature
            if 'nvme' in device_path:
                result = subprocess.run([
                    'nvme', 'smart-log', device_path
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if 'temperature' in line.lower():
                            # Extract temperature value
                            import re
                            match = re.search(r'(\d+)', line)
                            if match:
                                return float(match.group(1))
        except:
            pass
        return 0.0
    
    def get_device_info(self, device_id: str) -> HardwareDevice:
        """Get current storage device information"""
        # Would update dynamic info like utilization
        devices = self.discover_devices()
        for device in devices:
            if device.device_id == device_id:
                return device
        return None
    
    def allocate_memory(self, device_id: str, size: int) -> Optional[int]:
        """Allocate storage space (create file)"""
        try:
            # For storage, allocation means creating a file
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.truncate(size)
            temp_file.close()
            
            return hash(temp_file.name)  # Return file handle
        except Exception as e:
            logger.error(f"Storage allocation failed: {e}")
        return None
    
    def free_memory(self, device_id: str, ptr: int):
        """Free storage space (delete file)"""
        # Would delete the associated file
        pass
    
    def transfer_data(self, src_device: str, dst_device: str,
                     src_ptr: int, dst_ptr: int, size: int):
        """Transfer data between storage devices"""
        # Would implement efficient file copying
        pass
    
    def execute_kernel(self, device_id: str, kernel: Any, args: List):
        """Storage devices don't execute kernels"""
        return None
"""
Device management for KOS
"""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class DeviceType(Enum):
    """Device types"""
    BLOCK = "block"
    CHARACTER = "char"
    NETWORK = "net"
    VIRTUAL = "virtual"

@dataclass
class Device:
    """Device representation"""
    name: str
    path: str
    type: DeviceType
    major: int
    minor: int
    size: Optional[int] = None
    mounted: bool = False
    mount_point: Optional[str] = None
    filesystem: Optional[str] = None
    readonly: bool = False

class DeviceManager:
    """Manages system devices"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.devices: Dict[str, Device] = {}
        self.mounts: Dict[str, Device] = {}  # mount_point -> device
        
        self._init_devices()
    
    def _init_devices(self):
        """Initialize default devices"""
        # Loop devices
        for i in range(8):
            self.devices[f"loop{i}"] = Device(
                name=f"loop{i}",
                path=f"/dev/loop{i}",
                type=DeviceType.BLOCK,
                major=7,
                minor=i,
                size=0
            )
        
        # Disk devices
        self.devices["sda"] = Device(
            name="sda",
            path="/dev/sda",
            type=DeviceType.BLOCK,
            major=8,
            minor=0,
            size=10737418240,  # 10GB
            filesystem="ext4"
        )
        
        self.devices["sda1"] = Device(
            name="sda1",
            path="/dev/sda1",
            type=DeviceType.BLOCK,
            major=8,
            minor=1,
            size=10737418240,
            filesystem="ext4"
        )
        
        # Character devices
        self.devices["null"] = Device(
            name="null",
            path="/dev/null",
            type=DeviceType.CHARACTER,
            major=1,
            minor=3
        )
        
        self.devices["zero"] = Device(
            name="zero",
            path="/dev/zero",
            type=DeviceType.CHARACTER,
            major=1,
            minor=5
        )
        
        self.devices["random"] = Device(
            name="random",
            path="/dev/random",
            type=DeviceType.CHARACTER,
            major=1,
            minor=8
        )
        
        self.devices["urandom"] = Device(
            name="urandom",
            path="/dev/urandom",
            type=DeviceType.CHARACTER,
            major=1,
            minor=9
        )
        
        # TTY devices
        for i in range(4):
            self.devices[f"tty{i}"] = Device(
                name=f"tty{i}",
                path=f"/dev/tty{i}",
                type=DeviceType.CHARACTER,
                major=4,
                minor=i
            )
        
        # Network devices (virtual)
        self.devices["lo"] = Device(
            name="lo",
            path="/sys/class/net/lo",
            type=DeviceType.NETWORK,
            major=0,
            minor=0
        )
        
        self.devices["eth0"] = Device(
            name="eth0",
            path="/sys/class/net/eth0",
            type=DeviceType.NETWORK,
            major=0,
            minor=1
        )
    
    def mount(self, device_name: str, mount_point: str, 
              filesystem: str = "auto", options: str = "") -> bool:
        """Mount a device"""
        if device_name not in self.devices:
            return False
        
        device = self.devices[device_name]
        
        # Check if already mounted
        if device.mounted:
            return False
        
        # Check if mount point is in use
        if mount_point in self.mounts:
            return False
        
        # Create mount point if needed
        if self.vfs and not self.vfs.exists(mount_point):
            try:
                self.vfs.mkdir(mount_point)
            except:
                pass
        
        # Perform mount (simulated)
        device.mounted = True
        device.mount_point = mount_point
        if filesystem != "auto":
            device.filesystem = filesystem
        
        if "ro" in options:
            device.readonly = True
        
        self.mounts[mount_point] = device
        
        # Update /proc/mounts
        self._update_proc_mounts()
        
        return True
    
    def umount(self, target: str) -> bool:
        """Unmount a device or mount point"""
        # Find device
        device = None
        
        if target in self.devices:
            device = self.devices[target]
        elif target in self.mounts:
            device = self.mounts[target]
        else:
            # Search by mount point
            for dev in self.devices.values():
                if dev.mount_point == target:
                    device = dev
                    break
        
        if not device or not device.mounted:
            return False
        
        # Unmount
        if device.mount_point in self.mounts:
            del self.mounts[device.mount_point]
        
        device.mounted = False
        device.mount_point = None
        device.readonly = False
        
        self._update_proc_mounts()
        
        return True
    
    def _update_proc_mounts(self):
        """Update /proc/mounts file"""
        if not self.vfs:
            return
        
        # Create /proc if needed
        if not self.vfs.exists("/proc"):
            try:
                self.vfs.mkdir("/proc")
            except:
                pass
        
        # Generate mounts content
        content = ""
        for mount_point, device in self.mounts.items():
            options = "ro" if device.readonly else "rw"
            content += f"{device.path} {mount_point} {device.filesystem or 'none'} {options} 0 0\n"
        
        # Add special filesystems
        content += "proc /proc proc rw 0 0\n"
        content += "sysfs /sys sysfs rw 0 0\n"
        content += "devtmpfs /dev devtmpfs rw 0 0\n"
        
        # Write to /proc/mounts
        try:
            with self.vfs.open("/proc/mounts", 'w') as f:
                f.write(content.encode())
        except:
            pass
    
    def list_devices(self) -> List[Device]:
        """List all devices"""
        return list(self.devices.values())
    
    def list_mounts(self) -> List[Dict]:
        """List mounted filesystems"""
        mounts = []
        for mount_point, device in self.mounts.items():
            mounts.append({
                'device': device.name,
                'mount_point': mount_point,
                'filesystem': device.filesystem or 'none',
                'options': 'ro' if device.readonly else 'rw',
                'size': device.size
            })
        return mounts
    
    def get_device(self, name: str) -> Optional[Device]:
        """Get device by name"""
        return self.devices.get(name)
    
    def create_loop_device(self, file_path: str) -> Optional[str]:
        """Create loop device from file"""
        # Find free loop device
        for i in range(8):
            loop_name = f"loop{i}"
            loop_dev = self.devices[loop_name]
            
            if not loop_dev.mounted and loop_dev.size == 0:
                # Attach file to loop device
                if self.vfs and self.vfs.exists(file_path):
                    try:
                        # Get file size
                        with self.vfs.open(file_path, 'rb') as f:
                            f.seek(0, 2)
                            size = f.tell()
                        
                        loop_dev.size = size
                        return loop_name
                    except:
                        pass
        
        return None
    
    def detach_loop_device(self, loop_name: str) -> bool:
        """Detach loop device"""
        if loop_name not in self.devices:
            return False
        
        loop_dev = self.devices[loop_name]
        
        if loop_dev.mounted:
            self.umount(loop_name)
        
        loop_dev.size = 0
        return True
    
    def get_disk_usage(self, path: str = "/") -> Dict:
        """Get disk usage for path"""
        # Find mounted device for path
        device = None
        mount_point = "/"
        
        for mp, dev in sorted(self.mounts.items(), key=lambda x: len(x[0]), reverse=True):
            if path.startswith(mp):
                device = dev
                mount_point = mp
                break
        
        if not device:
            # Use root filesystem
            device = self.devices.get("sda1")
        
        # Calculate usage (simulated)
        total = device.size if device else 10737418240
        used = int(total * 0.3)  # Simulate 30% usage
        free = total - used
        
        return {
            'filesystem': device.path if device else 'rootfs',
            'total': total,
            'used': used,
            'free': free,
            'percent': (used * 100) // total if total > 0 else 0,
            'mount_point': mount_point
        }

class LoopbackManager:
    """Manages loopback devices"""
    
    def __init__(self, device_manager: DeviceManager):
        self.device_manager = device_manager
    
    def create_image(self, vfs, path: str, size: int) -> bool:
        """Create disk image file"""
        try:
            # Create file with zeros
            data = b'\x00' * size
            with vfs.open(path, 'wb') as f:
                f.write(data)
            return True
        except:
            return False
    
    def mount_image(self, image_path: str, mount_point: str) -> bool:
        """Mount disk image"""
        # Create loop device
        loop_dev = self.device_manager.create_loop_device(image_path)
        if not loop_dev:
            return False
        
        # Mount loop device
        return self.device_manager.mount(loop_dev, mount_point, "ext4")
    
    def unmount_image(self, mount_point: str) -> bool:
        """Unmount disk image"""
        # Find loop device
        if mount_point not in self.device_manager.mounts:
            return False
        
        device = self.device_manager.mounts[mount_point]
        
        # Unmount
        if not self.device_manager.umount(mount_point):
            return False
        
        # Detach loop device
        if device.name.startswith("loop"):
            self.device_manager.detach_loop_device(device.name)
        
        return True
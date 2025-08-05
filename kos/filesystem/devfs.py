"""
DevFS - Device Filesystem Implementation
Provides device nodes and character/block device interfaces
"""

import os
import stat
import time
import threading
import random
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime

from kos.filesystem.base import FileSystem, FileNode, DirectoryNode


class DeviceNode(FileNode):
    """Base class for device nodes"""
    
    def __init__(self, name: str, major: int, minor: int, device_type: str = 'c'):
        super().__init__(name)
        self.major = major
        self.minor = minor
        self.device_type = device_type  # 'c' for character, 'b' for block
        self._open_count = 0
        self._lock = threading.Lock()
        
        # Set proper mode bits
        if device_type == 'c':
            self.mode = stat.S_IFCHR | 0o666
        else:
            self.mode = stat.S_IFBLK | 0o666
    
    def get_device_info(self) -> tuple:
        """Get device major and minor numbers"""
        return (self.major, self.minor)
    
    def open(self, flags: int = os.O_RDONLY) -> int:
        """Open device"""
        with self._lock:
            self._open_count += 1
            return 0  # Success
    
    def close(self):
        """Close device"""
        with self._lock:
            if self._open_count > 0:
                self._open_count -= 1
    
    def ioctl(self, cmd: int, arg: Any) -> Any:
        """Device-specific control operations"""
        # Default implementation - return 0 for unknown commands
        logger.debug(f"ioctl command 0x{cmd:x} not implemented for {self.name}")
        return 0


class NullDevice(DeviceNode):
    """Null device - discards all writes, returns EOF on reads"""
    
    def __init__(self):
        super().__init__('null', 1, 3)
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Always return empty (EOF)"""
        return b''
    
    def write(self, data: bytes) -> int:
        """Discard all data"""
        return len(data)


class ZeroDevice(DeviceNode):
    """Zero device - returns zeros on read, discards writes"""
    
    def __init__(self):
        super().__init__('zero', 1, 5)
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Return zeros"""
        if size == -1:
            size = 4096  # Default chunk
        return b'\0' * size
    
    def write(self, data: bytes) -> int:
        """Discard all data"""
        return len(data)


class RandomDevice(DeviceNode):
    """Random device - returns random bytes"""
    
    def __init__(self, name: str = 'random', major: int = 1, minor: int = 8):
        super().__init__(name, major, minor)
        self._random = random.Random()
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Return random bytes"""
        if size == -1:
            size = 256
        return bytes(self._random.randint(0, 255) for _ in range(size))
    
    def write(self, data: bytes) -> int:
        """Accept entropy input"""
        # In real implementation, would add to entropy pool
        return len(data)


class UrandomDevice(RandomDevice):
    """Non-blocking random device"""
    
    def __init__(self):
        super().__init__('urandom', 1, 9)


class FullDevice(DeviceNode):
    """Full device - returns ENOSPC on write, zeros on read"""
    
    def __init__(self):
        super().__init__('full', 1, 7)
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Return zeros like /dev/zero"""
        if size == -1:
            size = 4096
        return b'\0' * size
    
    def write(self, data: bytes) -> int:
        """Always fail with disk full"""
        raise OSError(28, "No space left on device")


class MemDevice(DeviceNode):
    """Memory device - access to system memory (restricted)"""
    
    def __init__(self):
        super().__init__('mem', 1, 1)
        self.mode = stat.S_IFCHR | 0o600  # Root only
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Read from memory - restricted"""
        raise PermissionError("Direct memory access not permitted")
    
    def write(self, data: bytes) -> int:
        """Write to memory - restricted"""
        raise PermissionError("Direct memory access not permitted")


class KmsgDevice(DeviceNode):
    """Kernel message buffer device"""
    
    def __init__(self):
        super().__init__('kmsg', 1, 11)
        self.messages: List[str] = []
        self._lock = threading.Lock()
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Read kernel messages"""
        with self._lock:
            if not self.messages:
                return b''
            
            # Return oldest message
            msg = self.messages.pop(0)
            return msg.encode('utf-8')
    
    def write(self, data: bytes) -> int:
        """Write to kernel log"""
        with self._lock:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg = f"[{timestamp}] {data.decode('utf-8', errors='replace')}"
            self.messages.append(msg)
            
            # Keep only last 1000 messages
            if len(self.messages) > 1000:
                self.messages = self.messages[-1000:]
            
            return len(data)


class TTYDevice(DeviceNode):
    """TTY device base class"""
    
    def __init__(self, name: str, major: int, minor: int):
        super().__init__(name, major, minor)
        self.input_buffer = bytearray()
        self.output_buffer = bytearray()
        self._lock = threading.Lock()
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Read from TTY input"""
        with self._lock:
            if not self.input_buffer:
                return b''
            
            if size == -1:
                data = bytes(self.input_buffer)
                self.input_buffer.clear()
            else:
                data = bytes(self.input_buffer[:size])
                self.input_buffer = self.input_buffer[size:]
            
            return data
    
    def write(self, data: bytes) -> int:
        """Write to TTY output"""
        with self._lock:
            self.output_buffer.extend(data)
            # In real implementation, would output to terminal
            return len(data)
    
    def ioctl(self, cmd: int, arg: Any) -> Any:
        """TTY-specific ioctls"""
        # Common TTY ioctls
        TCGETS = 0x5401
        TCSETS = 0x5402
        TIOCGWINSZ = 0x5413
        
        if cmd == TIOCGWINSZ:
            # Return window size
            return (24, 80, 0, 0)  # rows, cols, xpixel, ypixel
        
        return None


class ConsoleDevice(TTYDevice):
    """System console device"""
    
    def __init__(self):
        super().__init__('console', 5, 1)


class PTYMasterDevice(DeviceNode):
    """PTY master device"""
    
    def __init__(self, pty_num: int):
        super().__init__(f'ptmx', 5, 2)
        self.pty_num = pty_num
        self.slave = None
    
    def open(self, flags: int = os.O_RDONLY) -> int:
        """Open PTY master"""
        # Would allocate a PTY pair
        return super().open(flags)


class LoopDevice(DeviceNode):
    """Loop device for mounting files as block devices"""
    
    def __init__(self, num: int):
        super().__init__(f'loop{num}', 7, num, 'b')
        self.backing_file = None
        self.offset = 0
        self.size_limit = 0
    
    def attach(self, file_path: str, offset: int = 0, size_limit: int = 0):
        """Attach file to loop device"""
        self.backing_file = file_path
        self.offset = offset
        self.size_limit = size_limit
    
    def detach(self):
        """Detach file from loop device"""
        self.backing_file = None
        self.offset = 0
        self.size_limit = 0
    
    def ioctl(self, cmd: int, arg: Any) -> Any:
        """Loop device ioctls"""
        LOOP_SET_FD = 0x4C00
        LOOP_CLR_FD = 0x4C01
        LOOP_GET_STATUS = 0x4C03
        
        if cmd == LOOP_GET_STATUS:
            return {
                'backing_file': self.backing_file,
                'offset': self.offset,
                'size_limit': self.size_limit
            }
        
        return None


class DevFS(FileSystem):
    """Device filesystem implementation"""
    
    def __init__(self):
        super().__init__()
        self._init_standard_devices()
        self._device_registry: Dict[str, DeviceNode] = {}
        self._next_pty = 0
        self._lock = threading.RLock()
    
    def _init_standard_devices(self):
        """Initialize standard device nodes"""
        # Create standard devices
        devices = [
            NullDevice(),
            ZeroDevice(),
            FullDevice(),
            RandomDevice(),
            UrandomDevice(),
            MemDevice(),
            KmsgDevice(),
            ConsoleDevice(),
        ]
        
        # Add devices to root
        for device in devices:
            self.root.add_child(device)
            self._device_registry[device.name] = device
        
        # Create standard symlinks
        self._create_symlink('stdin', '/proc/self/fd/0')
        self._create_symlink('stdout', '/proc/self/fd/1')
        self._create_symlink('stderr', '/proc/self/fd/2')
        
        # Create directories
        self._create_directory('pts')  # Pseudo-terminals
        self._create_directory('shm')  # Shared memory
        self._create_directory('disk')  # Disk devices
        self._create_directory('input')  # Input devices
        self._create_directory('net')  # Network devices
        
        # Create loop devices
        for i in range(8):
            loop = LoopDevice(i)
            disk_dir = self.root.get_child('disk')
            if disk_dir:
                disk_dir.add_child(loop)
            self._device_registry[f'loop{i}'] = loop
        
        # Create standard TTYs
        for i in range(1, 7):
            tty = TTYDevice(f'tty{i}', 4, i)
            self.root.add_child(tty)
            self._device_registry[tty.name] = tty
        
        # Create current TTY symlink
        self._create_symlink('tty', '/dev/console')
    
    def _create_directory(self, name: str):
        """Create a directory in devfs"""
        dir_node = DirectoryNode(name)
        self.root.add_child(dir_node)
    
    def _create_symlink(self, name: str, target: str):
        """Create a symbolic link"""
        # For now, create as a special file node
        link = FileNode(name)
        link.symlink_target = target
        link.mode = stat.S_IFLNK | 0o777
        self.root.add_child(link)
    
    def register_device(self, device: DeviceNode, path: Optional[str] = None):
        """Register a new device"""
        with self._lock:
            if path:
                # Navigate to parent directory
                parts = path.strip('/').split('/')
                parent = self.root
                
                for part in parts[:-1]:
                    child = parent.get_child(part)
                    if not child:
                        # Create directory if it doesn't exist
                        child = DirectoryNode(part)
                        parent.add_child(child)
                    parent = child
                
                parent.add_child(device)
            else:
                self.root.add_child(device)
            
            self._device_registry[device.name] = device
    
    def unregister_device(self, name: str):
        """Remove a device"""
        with self._lock:
            if name in self._device_registry:
                device = self._device_registry[name]
                # Find and remove from tree
                self._remove_device_from_tree(self.root, device)
                del self._device_registry[name]
    
    def _remove_device_from_tree(self, node: DirectoryNode, device: DeviceNode) -> bool:
        """Recursively remove device from tree"""
        if device.name in node.children:
            node.remove_child(device.name)
            return True
        
        for child in node.children.values():
            if isinstance(child, DirectoryNode):
                if self._remove_device_from_tree(child, device):
                    return True
        
        return False
    
    def get_device(self, name: str) -> Optional[DeviceNode]:
        """Get a device by name"""
        return self._device_registry.get(name)
    
    def create_pty_pair(self) -> tuple:
        """Create a new PTY master/slave pair"""
        with self._lock:
            pty_num = self._next_pty
            self._next_pty += 1
            
            # Create master
            master = PTYMasterDevice(pty_num)
            self.register_device(master, f'pts/{pty_num}')
            
            # Create slave
            slave = TTYDevice(f'pts/{pty_num}', 136, pty_num)
            master.slave = slave
            
            pts_dir = self.root.get_child('pts')
            if pts_dir:
                pts_dir.add_child(slave)
            
            return (master, slave)
    
    def mknod(self, path: str, mode: int, device: int) -> bool:
        """Create a device node"""
        # Extract device type, major, and minor
        if stat.S_ISCHR(mode):
            device_type = 'c'
        elif stat.S_ISBLK(mode):
            device_type = 'b'
        else:
            return False
        
        major = os.major(device)
        minor = os.minor(device)
        
        # Create device node
        name = os.path.basename(path)
        dev_node = DeviceNode(name, major, minor, device_type)
        dev_node.mode = mode
        
        # Register it
        self.register_device(dev_node, path)
        return True
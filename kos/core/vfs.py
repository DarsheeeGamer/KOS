"""
KOS Virtual File System
Complete custom VFS implementation without pickle dependency
"""

import os
import json
import time
import stat
import struct
import hashlib
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Union, BinaryIO, Tuple
from pathlib import Path
import io
import logging

from .errors import VFSError

logger = logging.getLogger(__name__)

# VFS Format Constants
VFS_MAGIC = b'KVFS'  # KOS VFS Magic Number
VFS_VERSION = 1
BLOCK_SIZE = 4096  # 4KB blocks
INODE_SIZE = 256   # Fixed inode size
MAX_FILENAME = 255
MAX_PATH = 4096

# File types
S_IFREG = 0o100000  # Regular file
S_IFDIR = 0o040000  # Directory
S_IFLNK = 0o120000  # Symbolic link

@dataclass
class StatResult:
    """File/directory statistics"""
    st_mode: int
    st_size: int
    st_uid: int = 0
    st_gid: int = 0
    st_atime: float = field(default_factory=time.time)
    st_mtime: float = field(default_factory=time.time)
    st_ctime: float = field(default_factory=time.time)
    st_nlink: int = 1
    st_blocks: int = 0

@dataclass
class Superblock:
    """VFS Superblock containing filesystem metadata"""
    magic: bytes = VFS_MAGIC
    version: int = VFS_VERSION
    block_size: int = BLOCK_SIZE
    total_blocks: int = 0
    free_blocks: int = 0
    total_inodes: int = 0
    free_inodes: int = 0
    root_inode: int = 1  # Root directory inode number
    first_data_block: int = 0
    mount_time: float = 0
    last_write_time: float = 0
    mount_count: int = 0
    max_mount_count: int = 100
    state: int = 0  # 0=clean, 1=dirty
    
    def to_bytes(self) -> bytes:
        """Serialize superblock to bytes"""
        return struct.pack(
            '<4sIIQQQQQQddHHH',
            self.magic,
            self.version,
            self.block_size,
            self.total_blocks,
            self.free_blocks,
            self.total_inodes,
            self.free_inodes,
            self.root_inode,
            self.first_data_block,
            self.mount_time,
            self.last_write_time,
            self.mount_count,
            self.max_mount_count,
            self.state
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Superblock':
        """Deserialize superblock from bytes"""
        unpacked = struct.unpack('<4sIIQQQQQQddHHH', data[:struct.calcsize('<4sIIQQQQQQddHHH')])
        return cls(
            magic=unpacked[0],
            version=unpacked[1],
            block_size=unpacked[2],
            total_blocks=unpacked[3],
            free_blocks=unpacked[4],
            total_inodes=unpacked[5],
            free_inodes=unpacked[6],
            root_inode=unpacked[7],
            first_data_block=unpacked[8],
            mount_time=unpacked[9],
            last_write_time=unpacked[10],
            mount_count=unpacked[11],
            max_mount_count=unpacked[12],
            state=unpacked[13]
        )

@dataclass
class Inode:
    """File system inode"""
    inode_number: int
    mode: int  # File type and permissions
    uid: int = 0
    gid: int = 0
    size: int = 0
    atime: float = field(default_factory=time.time)
    mtime: float = field(default_factory=time.time)
    ctime: float = field(default_factory=time.time)
    nlinks: int = 1
    blocks: List[int] = field(default_factory=list)  # Block numbers
    
    # For directories
    entries: Dict[str, int] = field(default_factory=dict)  # name -> inode_number
    
    def is_directory(self) -> bool:
        return (self.mode & S_IFDIR) != 0
    
    def is_file(self) -> bool:
        return (self.mode & S_IFREG) != 0
    
    def to_bytes(self) -> bytes:
        """Serialize inode to bytes"""
        # Serialize entries as JSON for directories
        entries_json = json.dumps(self.entries) if self.entries else ""
        entries_bytes = entries_json.encode('utf-8')
        
        # Pack basic fields
        header = struct.pack(
            '<QIIIQdddI',
            self.inode_number,
            self.mode,
            self.uid,
            self.gid,
            self.size,
            self.atime,
            self.mtime,
            self.ctime,
            self.nlinks
        )
        
        # Pack blocks count and blocks
        blocks_data = struct.pack('<I', len(self.blocks))
        for block in self.blocks:
            blocks_data += struct.pack('<I', block)
        
        # Pack entries
        entries_data = struct.pack('<I', len(entries_bytes)) + entries_bytes
        
        return header + blocks_data + entries_data
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'Inode':
        """Deserialize inode from bytes"""
        offset = 0
        header_size = struct.calcsize('<QIIIQdddI')
        header = struct.unpack('<QIIIQdddI', data[offset:offset+header_size])
        offset += header_size
        
        inode = cls(
            inode_number=header[0],
            mode=header[1],
            uid=header[2],
            gid=header[3],
            size=header[4],
            atime=header[5],
            mtime=header[6],
            ctime=header[7],
            nlinks=header[8]
        )
        
        # Unpack blocks
        blocks_count = struct.unpack('<I', data[offset:offset+4])[0]
        offset += 4
        
        for _ in range(blocks_count):
            block = struct.unpack('<I', data[offset:offset+4])[0]
            inode.blocks.append(block)
            offset += 4
        
        # Unpack entries
        if offset < len(data):
            entries_len = struct.unpack('<I', data[offset:offset+4])[0]
            offset += 4
            
            if entries_len > 0:
                entries_json = data[offset:offset+entries_len].decode('utf-8')
                inode.entries = json.loads(entries_json)
        
        return inode

class BlockDevice:
    """Block device abstraction for VFS storage"""
    
    def __init__(self, path: str, size: int = 100 * 1024 * 1024):  # 100MB default
        self.path = path
        self.size = size
        self.file = None
        self.lock = threading.RLock()
        
    def open(self, create: bool = False):
        """Open the block device"""
        mode = 'r+b' if os.path.exists(self.path) else 'w+b'
        if create or mode == 'w+b':
            self.file = open(self.path, 'w+b')
            # Initialize with zeros
            self.file.write(b'\x00' * self.size)
            self.file.seek(0)
            self.file = open(self.path, 'r+b')
        else:
            self.file = open(self.path, 'r+b')
    
    def close(self):
        """Close the block device"""
        if self.file:
            self.file.close()
            self.file = None
    
    def read_block(self, block_number: int, block_size: int = BLOCK_SIZE) -> bytes:
        """Read a block from device"""
        with self.lock:
            offset = block_number * block_size
            self.file.seek(offset)
            return self.file.read(block_size)
    
    def write_block(self, block_number: int, data: bytes, block_size: int = BLOCK_SIZE):
        """Write a block to device"""
        with self.lock:
            if len(data) > block_size:
                data = data[:block_size]
            elif len(data) < block_size:
                data = data + b'\x00' * (block_size - len(data))
            
            offset = block_number * block_size
            self.file.seek(offset)
            self.file.write(data)
            self.file.flush()

class VFSFileHandle(io.BytesIO):
    """File handle for VFS files"""
    
    def __init__(self, vfs: 'VFS', path: str, mode: str, inode_number: int, initial_content: bytes = b''):
        super().__init__(initial_content)
        self.vfs = vfs
        self.path = path
        self.mode = mode
        self.inode_number = inode_number
        self._closed = False
        
        if 'a' in mode:
            self.seek(0, 2)  # Seek to end
    
    @property
    def closed(self):
        return self._closed
    
    def close(self):
        if not self._closed:
            if 'w' in self.mode or 'a' in self.mode or '+' in self.mode:
                # Save content back to VFS
                self.vfs._write_file_data(self.inode_number, self.getvalue())
            self._closed = True
            super().close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

class VFS(ABC):
    """Abstract base class for Virtual File System"""
    
    @abstractmethod
    def mount(self, source: str = None, read_only: bool = False):
        """Mount the filesystem from source"""
        pass
    
    @abstractmethod
    def unmount(self):
        """Unmount and save the filesystem"""
        pass
    
    @abstractmethod
    def mkdir(self, path: str, mode: int = 0o755):
        """Create a directory"""
        pass
    
    @abstractmethod
    def rmdir(self, path: str):
        """Remove an empty directory"""
        pass
    
    @abstractmethod
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        pass
    
    @abstractmethod
    def stat(self, path: str) -> Dict:
        """Get file/directory statistics"""
        pass
    
    @abstractmethod
    def unlink(self, path: str):
        """Delete a file"""
        pass
    
    @abstractmethod
    def open(self, path: str, mode: str = 'r') -> BinaryIO:
        """Open a file, returns file-like object"""
        pass
    
    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        pass
    
    @abstractmethod
    def isfile(self, path: str) -> bool:
        """Check if path is a file"""
        pass
    
    @abstractmethod
    def isdir(self, path: str) -> bool:
        """Check if path is a directory"""
        pass

class CustomVFS(VFS):
    """Custom VFS implementation without pickle"""
    
    def __init__(self, disk_path: str = "kos.vfs", size: int = 100 * 1024 * 1024):
        self.disk_path = disk_path
        self.size = size
        self.device = BlockDevice(disk_path, size)
        self.superblock = None
        self.mounted = False
        self.dirty = False
        
        # Caches
        self.inode_cache = {}  # inode_number -> Inode
        self.block_cache = {}  # block_number -> data
        self.free_blocks = set()
        self.free_inodes = set()
        
        # Locks
        self.lock = threading.RLock()
        
        # Configuration
        self.cache_size = 100  # Maximum cached blocks
        self.sync_interval = 30  # Sync to disk every 30 seconds
        
        # Start background sync thread
        self.sync_thread = None
        self.running = False
    
    def mount(self, source: str = None, read_only: bool = False, create: bool = False):
        """Mount the VFS"""
        with self.lock:
            if self.mounted:
                return  # Already mounted
            
            # Use provided source or default disk path
            if source:
                self.disk_path = source
                self.device = BlockDevice(source, self.size)
            
            # Open block device
            self.device.open(create or not os.path.exists(self.disk_path))
            
            if create or not self._has_valid_superblock():
                self._format()
            else:
                self._load_superblock()
            
            self.mounted = True
            self.running = True
            
            # Start background sync
            self.sync_thread = threading.Thread(target=self._background_sync, daemon=True)
            self.sync_thread.start()
            
            logger.info(f"VFS mounted from {self.disk_path}")
    
    def unmount(self):
        """Unmount the VFS"""
        with self.lock:
            if not self.mounted:
                return
            
            self.running = False
            
            # Final sync
            self._sync()
            
            # Update superblock
            self.superblock.state = 0  # Clean
            self.superblock.last_write_time = time.time()
            self._write_superblock()
            
            # Close device
            self.device.close()
            
            self.mounted = False
            logger.info("VFS unmounted")
    
    def _format(self):
        """Format the VFS with initial structure"""
        logger.info("Formatting new VFS...")
        
        # Calculate filesystem parameters
        total_blocks = self.size // BLOCK_SIZE
        
        # Reserve blocks: superblock(1) + inode table + bitmap
        inode_table_blocks = 100  # Support up to 100 * (BLOCK_SIZE/INODE_SIZE) inodes
        bitmap_blocks = (total_blocks + 8*BLOCK_SIZE - 1) // (8*BLOCK_SIZE)  # 1 bit per block
        
        first_data_block = 1 + inode_table_blocks + bitmap_blocks
        
        # Create superblock
        self.superblock = Superblock(
            total_blocks=total_blocks,
            free_blocks=total_blocks - first_data_block,
            total_inodes=inode_table_blocks * (BLOCK_SIZE // INODE_SIZE),
            free_inodes=inode_table_blocks * (BLOCK_SIZE // INODE_SIZE) - 1,  # -1 for root
            first_data_block=first_data_block,
            mount_time=time.time(),
            last_write_time=time.time()
        )
        
        # Write superblock
        self._write_superblock()
        
        # Initialize bitmap (all blocks free except reserved)
        self.free_blocks = set(range(first_data_block, total_blocks))
        self._write_bitmap()
        
        # Initialize inode bitmap
        self.free_inodes = set(range(2, self.superblock.total_inodes))  # 0 is reserved, 1 is root
        
        # Create root directory inode
        root_inode = Inode(
            inode_number=1,
            mode=S_IFDIR | 0o755,
            entries={'.': 1, '..': 1}  # Self and parent references
        )
        self._write_inode(root_inode)
        
        # Create basic directory structure
        self._create_basic_structure()
        
        logger.info(f"VFS formatted: {total_blocks} blocks, {self.superblock.total_inodes} inodes")
    
    def _create_basic_structure(self):
        """Create basic Unix-like directory structure"""
        dirs = [
            '/bin', '/boot', '/dev', '/etc', '/home',
            '/lib', '/media', '/mnt', '/opt', '/proc',
            '/root', '/run', '/sbin', '/srv', '/sys',
            '/tmp', '/usr', '/var'
        ]
        
        for dir_path in dirs:
            try:
                self.mkdir(dir_path)
            except:
                pass  # Ignore if already exists
        
        # Create subdirectories
        subdirs = [
            '/home/user', '/usr/bin', '/usr/lib', '/usr/local',
            '/var/log', '/var/lib', '/etc/kos',
            '/usr/lib/python', '/usr/lib/python/site-packages',
            '/var/cache', '/var/cache/pip'
        ]
        
        for dir_path in subdirs:
            try:
                self.makedirs(dir_path)
            except:
                pass
    
    def _has_valid_superblock(self) -> bool:
        """Check if device has valid superblock"""
        try:
            data = self.device.read_block(0)
            if data[:4] == VFS_MAGIC:
                return True
        except:
            pass
        return False
    
    def _load_superblock(self):
        """Load superblock from device"""
        data = self.device.read_block(0)
        self.superblock = Superblock.from_bytes(data)
        
        # Update mount info
        self.superblock.mount_count += 1
        self.superblock.mount_time = time.time()
        self.superblock.state = 1  # Dirty
        
        # Load free block bitmap
        self._load_bitmap()
        
        # Load free inode list
        self._load_free_inodes()
    
    def _write_superblock(self):
        """Write superblock to device"""
        data = self.superblock.to_bytes()
        self.device.write_block(0, data)
    
    def _load_bitmap(self):
        """Load free block bitmap"""
        # Simplified: track free blocks in memory
        self.free_blocks = set(range(self.superblock.first_data_block, self.superblock.total_blocks))
        
        # Mark used blocks by scanning inodes
        for inode_num in range(1, min(100, self.superblock.total_inodes)):
            try:
                inode = self._read_inode(inode_num)
                if inode:
                    for block in inode.blocks:
                        self.free_blocks.discard(block)
            except:
                pass
    
    def _write_bitmap(self):
        """Write free block bitmap"""
        # Simplified implementation
        pass
    
    def _load_free_inodes(self):
        """Load free inode list"""
        self.free_inodes = set()
        for i in range(2, self.superblock.total_inodes):
            try:
                inode = self._read_inode(i)
                if not inode or inode.nlinks == 0:
                    self.free_inodes.add(i)
            except:
                self.free_inodes.add(i)
    
    def _allocate_inode(self) -> int:
        """Allocate a new inode number"""
        if not self.free_inodes:
            raise VFSError("No free inodes")
        
        inode_num = min(self.free_inodes)
        self.free_inodes.remove(inode_num)
        self.superblock.free_inodes -= 1
        return inode_num
    
    def _free_inode(self, inode_number: int):
        """Free an inode"""
        self.free_inodes.add(inode_number)
        self.superblock.free_inodes += 1
        
        # Clear from cache
        if inode_number in self.inode_cache:
            del self.inode_cache[inode_number]
    
    def _allocate_block(self) -> int:
        """Allocate a new data block"""
        if not self.free_blocks:
            raise VFSError("No free blocks")
        
        block_num = min(self.free_blocks)
        self.free_blocks.remove(block_num)
        self.superblock.free_blocks -= 1
        return block_num
    
    def _free_block(self, block_number: int):
        """Free a data block"""
        self.free_blocks.add(block_number)
        self.superblock.free_blocks += 1
        
        # Clear from cache
        if block_number in self.block_cache:
            del self.block_cache[block_number]
    
    def _read_inode(self, inode_number: int) -> Optional[Inode]:
        """Read inode from device"""
        if inode_number in self.inode_cache:
            return self.inode_cache[inode_number]
        
        # Calculate inode position
        inode_block = 1 + (inode_number * INODE_SIZE) // BLOCK_SIZE
        inode_offset = (inode_number * INODE_SIZE) % BLOCK_SIZE
        
        # Read inode data
        block_data = self.device.read_block(inode_block)
        inode_data = block_data[inode_offset:inode_offset + INODE_SIZE]
        
        # Check if inode is allocated
        if inode_data[:8] == b'\x00' * 8:
            return None
        
        try:
            inode = Inode.from_bytes(inode_data)
            self.inode_cache[inode_number] = inode
            return inode
        except:
            return None
    
    def _write_inode(self, inode: Inode):
        """Write inode to device"""
        # Calculate inode position
        inode_block = 1 + (inode.inode_number * INODE_SIZE) // BLOCK_SIZE
        inode_offset = (inode.inode_number * INODE_SIZE) % BLOCK_SIZE
        
        # Read block
        block_data = bytearray(self.device.read_block(inode_block))
        
        # Update inode data
        inode_bytes = inode.to_bytes()
        if len(inode_bytes) > INODE_SIZE:
            inode_bytes = inode_bytes[:INODE_SIZE]
        elif len(inode_bytes) < INODE_SIZE:
            inode_bytes = inode_bytes + b'\x00' * (INODE_SIZE - len(inode_bytes))
        
        block_data[inode_offset:inode_offset + INODE_SIZE] = inode_bytes
        
        # Write block back
        self.device.write_block(inode_block, bytes(block_data))
        
        # Update cache
        self.inode_cache[inode.inode_number] = inode
        self.dirty = True
    
    def _resolve_path(self, path: str) -> Tuple[Optional[Inode], str]:
        """Resolve path to parent inode and filename"""
        path = os.path.normpath(path)
        
        if path == '/':
            return None, '/'
        
        parts = path.strip('/').split('/')
        filename = parts[-1]
        
        # Start from root
        current_inode = self._read_inode(self.superblock.root_inode)
        
        # Traverse path
        for part in parts[:-1]:
            if not current_inode or not current_inode.is_directory():
                raise VFSError(f"Not a directory: {part}")
            
            if part not in current_inode.entries:
                raise VFSError(f"Path not found: {path}")
            
            current_inode = self._read_inode(current_inode.entries[part])
        
        return current_inode, filename
    
    def _get_inode_by_path(self, path: str) -> Optional[Inode]:
        """Get inode for a given path"""
        if path == '/':
            return self._read_inode(self.superblock.root_inode)
        
        parent, name = self._resolve_path(path)
        if parent and name in parent.entries:
            return self._read_inode(parent.entries[name])
        
        return None
    
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        try:
            return self._get_inode_by_path(path) is not None
        except:
            return False
    
    def isfile(self, path: str) -> bool:
        """Check if path is a file"""
        inode = self._get_inode_by_path(path)
        return inode is not None and inode.is_file()
    
    def isdir(self, path: str) -> bool:
        """Check if path is a directory"""
        inode = self._get_inode_by_path(path)
        return inode is not None and inode.is_directory()
    
    def mkdir(self, path: str, mode: int = 0o755):
        """Create a directory"""
        with self.lock:
            if self.exists(path):
                raise VFSError(f"Path already exists: {path}")
            
            parent, name = self._resolve_path(path)
            if not parent:
                return  # Root already exists
            
            # Allocate new inode
            inode_num = self._allocate_inode()
            
            # Create directory inode
            new_dir = Inode(
                inode_number=inode_num,
                mode=S_IFDIR | mode,
                entries={'.': inode_num, '..': parent.inode_number}
            )
            
            # Write inode
            self._write_inode(new_dir)
            
            # Update parent directory
            parent.entries[name] = inode_num
            parent.mtime = time.time()
            self._write_inode(parent)
    
    def makedirs(self, path: str, mode: int = 0o755, exist_ok: bool = False):
        """Create directory tree"""
        parts = path.strip('/').split('/')
        current_path = ''
        
        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else f"/{part}"
            
            if self.exists(current_path):
                if not self.isdir(current_path):
                    raise VFSError(f"Not a directory: {current_path}")
                continue
            
            self.mkdir(current_path, mode)
    
    def rmdir(self, path: str):
        """Remove empty directory"""
        with self.lock:
            inode = self._get_inode_by_path(path)
            if not inode:
                raise VFSError(f"Path not found: {path}")
            
            if not inode.is_directory():
                raise VFSError(f"Not a directory: {path}")
            
            # Check if empty (only . and ..)
            if len(inode.entries) > 2:
                raise VFSError(f"Directory not empty: {path}")
            
            parent, name = self._resolve_path(path)
            
            # Remove from parent
            del parent.entries[name]
            parent.mtime = time.time()
            self._write_inode(parent)
            
            # Free inode
            self._free_inode(inode.inode_number)
    
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        inode = self._get_inode_by_path(path)
        if not inode:
            raise VFSError(f"Path not found: {path}")
        
        if not inode.is_directory():
            raise VFSError(f"Not a directory: {path}")
        
        # Return entries except . and ..
        return [name for name in inode.entries.keys() if name not in ['.', '..']]
    
    def open(self, path: str, mode: str = 'r') -> VFSFileHandle:
        """Open a file"""
        if 'b' not in mode:
            mode += 'b'
        
        inode = self._get_inode_by_path(path)
        
        if 'r' in mode:
            if not inode:
                raise VFSError(f"File not found: {path}")
            if not inode.is_file():
                raise VFSError(f"Not a file: {path}")
            
            # Read file data
            data = self._read_file_data(inode)
            return VFSFileHandle(self, path, mode, inode.inode_number, initial_content=data)
        
        elif 'w' in mode or 'a' in mode:
            if not inode or 'w' in mode:
                # Create new file
                parent, name = self._resolve_path(path)
                if not parent:
                    raise VFSError("Cannot create file at root")
                
                # Allocate inode
                inode_num = self._allocate_inode()
                
                # Create file inode
                new_file = Inode(
                    inode_number=inode_num,
                    mode=S_IFREG | 0o644
                )
                
                self._write_inode(new_file)
                
                # Update parent
                parent.entries[name] = inode_num
                parent.mtime = time.time()
                self._write_inode(parent)
                
                inode = new_file
            
            initial_data = self._read_file_data(inode) if 'a' in mode else b''
            return VFSFileHandle(self, path, mode, inode.inode_number, initial_content=initial_data)
        
        else:
            raise VFSError(f"Invalid mode: {mode}")
    
    def _read_file_data(self, inode: Inode) -> bytes:
        """Read all data from file inode"""
        if not inode.blocks:
            return b''
        
        data = b''
        for block_num in inode.blocks:
            block_data = self.device.read_block(block_num)
            data += block_data
        
        # Trim to actual size
        return data[:inode.size]
    
    def _write_file_data(self, inode_number: int, data: bytes):
        """Write data to file inode"""
        with self.lock:
            inode = self._read_inode(inode_number)
            if not inode:
                raise VFSError("Invalid inode")
            
            # Free old blocks
            for block_num in inode.blocks:
                self._free_block(block_num)
            
            inode.blocks = []
            inode.size = len(data)
            
            # Allocate new blocks
            offset = 0
            while offset < len(data):
                block_num = self._allocate_block()
                inode.blocks.append(block_num)
                
                chunk = data[offset:offset + BLOCK_SIZE]
                self.device.write_block(block_num, chunk)
                
                offset += BLOCK_SIZE
            
            # Update inode
            inode.mtime = time.time()
            self._write_inode(inode)
    
    def unlink(self, path: str):
        """Delete a file"""
        with self.lock:
            inode = self._get_inode_by_path(path)
            if not inode:
                raise VFSError(f"File not found: {path}")
            
            if not inode.is_file():
                raise VFSError(f"Not a file: {path}")
            
            parent, name = self._resolve_path(path)
            
            # Remove from parent
            del parent.entries[name]
            parent.mtime = time.time()
            self._write_inode(parent)
            
            # Free blocks
            for block_num in inode.blocks:
                self._free_block(block_num)
            
            # Free inode
            self._free_inode(inode.inode_number)
    
    def stat(self, path: str) -> Dict:
        """Get file/directory statistics"""
        inode = self._get_inode_by_path(path)
        if not inode:
            raise VFSError(f"Path not found: {path}")
        
        return {
            'st_mode': inode.mode,
            'st_ino': inode.inode_number,
            'st_uid': inode.uid,
            'st_gid': inode.gid,
            'st_size': inode.size if inode.is_file() else 4096,
            'st_atime': inode.atime,
            'st_mtime': inode.mtime,
            'st_ctime': inode.ctime,
            'st_nlink': inode.nlinks,
            'st_blocks': len(inode.blocks)
        }
    
    def _sync(self):
        """Sync cached data to disk"""
        if self.dirty:
            self.superblock.last_write_time = time.time()
            self._write_superblock()
            self._write_bitmap()
            self.dirty = False
    
    def _background_sync(self):
        """Background sync thread"""
        while self.running:
            time.sleep(self.sync_interval)
            if self.mounted and self.dirty:
                with self.lock:
                    self._sync()

# Backward compatibility alias
PickleVFS = CustomVFS

# Global VFS instance
_vfs_instance = None

def get_vfs(disk_path: str = "kos.vfs") -> VFS:
    """Get or create the global VFS instance"""
    global _vfs_instance
    if _vfs_instance is None:
        _vfs_instance = CustomVFS(disk_path)
        _vfs_instance.mount(create=not os.path.exists(disk_path))
    return _vfs_instance

# Export for compatibility
def get_custom_vfs(disk_path: str = "kos.vfs", size: int = 100 * 1024 * 1024) -> CustomVFS:
    """Get or create custom VFS instance"""
    return get_vfs(disk_path)
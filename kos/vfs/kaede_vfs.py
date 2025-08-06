"""
KaedeVFS - The ONE Virtual File System for KOS
===============================================
Clean, simple, and actually works. Everything stored in kaede.kdsk.
No tech debt. No competing implementations. Just works.
"""

import os
import json
import time
import pickle
import threading
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
import logging

logger = logging.getLogger('KOS.KaedeVFS')

@dataclass
class VFSFile:
    """A file in the VFS"""
    content: bytes = b''
    mode: int = 0o644
    uid: int = 0
    gid: int = 0
    atime: float = field(default_factory=time.time)
    mtime: float = field(default_factory=time.time)
    ctime: float = field(default_factory=time.time)

@dataclass
class VFSDirectory:
    """A directory in the VFS"""
    children: Dict[str, Any] = field(default_factory=dict)
    mode: int = 0o755
    uid: int = 0
    gid: int = 0
    atime: float = field(default_factory=time.time)
    mtime: float = field(default_factory=time.time)
    ctime: float = field(default_factory=time.time)

class KaedeVFS:
    """
    The Kaede Virtual File System
    
    Everything is stored in kaede.kdsk. No host filesystem access.
    Simple, clean, and actually works.
    """
    
    def __init__(self, disk_path: str = "kaede.kdsk"):
        """Initialize KaedeVFS
        
        Args:
            disk_path: Path to the VFS disk image
        """
        self.disk_path = disk_path
        self.lock = threading.RLock()
        self.filesystem = None
        self.open_files = {}
        self.fd_counter = 3
        
        # Load or create filesystem
        self._load_or_create()
        
        # Initialize if empty
        if len(self.filesystem) == 1:  # Only root exists
            self._initialize_filesystem()
        
        logger.info(f"KaedeVFS initialized: {disk_path}")
    
    def _load_or_create(self):
        """Load existing filesystem or create new one"""
        if os.path.exists(self.disk_path):
            try:
                with open(self.disk_path, 'rb') as f:
                    self.filesystem = pickle.load(f)
                logger.info("Loaded existing VFS")
            except:
                logger.warning("Could not load VFS, creating new")
                self._create_new_filesystem()
        else:
            self._create_new_filesystem()
    
    def _create_new_filesystem(self):
        """Create a new empty filesystem"""
        self.filesystem = {
            '/': VFSDirectory()
        }
        self._save()
        logger.info("Created new VFS")
    
    def _save(self):
        """Save filesystem to disk"""
        try:
            with self.lock:
                with open(self.disk_path, 'wb') as f:
                    pickle.dump(self.filesystem, f)
        except Exception as e:
            logger.error(f"Could not save VFS: {e}")
    
    def _initialize_filesystem(self):
        """Initialize with basic filesystem structure"""
        logger.info("Initializing filesystem structure...")
        
        # Create essential directories
        essential_dirs = [
            '/bin', '/boot', '/dev', '/etc', '/home', '/lib', '/media',
            '/mnt', '/opt', '/proc', '/root', '/run', '/sbin', '/srv',
            '/sys', '/tmp', '/usr', '/var',
            '/etc/kos', '/home/user', '/usr/bin', '/usr/lib', '/usr/local',
            '/var/log', '/var/lib', '/var/cache', '/opt/kos',
            '/home/user/Desktop', '/home/user/Documents', '/home/user/Downloads'
        ]
        
        for dir_path in essential_dirs:
            try:
                self.mkdir(dir_path)
            except:
                pass  # Ignore if exists
        
        # Create basic files
        self._create_file('/etc/hostname', b'kos\n')
        self._create_file('/etc/os-release', b'''NAME="KOS"
VERSION="1.0"
ID=kos
PRETTY_NAME="Kaede OS 1.0"
''')
        self._create_file('/home/user/Documents/readme.txt', 
                         b'Welcome to KOS!\n\nEverything is stored in kaede.kdsk.\n')
        
        self._save()
        logger.info("Filesystem initialized")
    
    def _create_file(self, path: str, content: bytes):
        """Helper to create a file with content"""
        try:
            with self.open(path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC) as f:
                f.write(content)
        except:
            pass
    
    def _get_parent_and_name(self, path: str):
        """Split path into parent directory and name"""
        path = path.rstrip('/')
        if path == '':
            path = '/'
        
        if path == '/':
            return None, '/'
        
        parent = os.path.dirname(path)
        name = os.path.basename(path)
        
        if parent == '':
            parent = '/'
        
        return parent, name
    
    def _get_node(self, path: str):
        """Get a node from the filesystem"""
        with self.lock:
            if path == '/':
                return self.filesystem['/']
            
            parts = path.strip('/').split('/')
            current = self.filesystem['/']
            
            for part in parts:
                if isinstance(current, VFSDirectory) and part in current.children:
                    current = current.children[part]
                else:
                    return None
            
            return current
    
    # === Public API ===
    
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        return self._get_node(path) is not None
    
    def is_dir(self, path: str) -> bool:
        """Check if path is a directory"""
        node = self._get_node(path)
        return isinstance(node, VFSDirectory)
    
    def is_file(self, path: str) -> bool:
        """Check if path is a file"""
        node = self._get_node(path)
        return isinstance(node, VFSFile)
    
    def mkdir(self, path: str, mode: int = 0o755, **kwargs):
        """Create a directory"""
        with self.lock:
            if self.exists(path):
                raise FileExistsError(f"{path}: File exists")
            
            parent_path, name = self._get_parent_and_name(path)
            
            if parent_path:
                parent = self._get_node(parent_path)
                if not isinstance(parent, VFSDirectory):
                    raise NotADirectoryError(f"{parent_path}: Not a directory")
                
                parent.children[name] = VFSDirectory(mode=mode)
                parent.mtime = time.time()
            
            self._save()
    
    def rmdir(self, path: str):
        """Remove a directory"""
        with self.lock:
            if path == '/':
                raise PermissionError("Cannot remove root directory")
            
            node = self._get_node(path)
            if not isinstance(node, VFSDirectory):
                raise NotADirectoryError(f"{path}: Not a directory")
            
            if node.children:
                raise OSError(f"{path}: Directory not empty")
            
            parent_path, name = self._get_parent_and_name(path)
            parent = self._get_node(parent_path)
            del parent.children[name]
            parent.mtime = time.time()
            
            self._save()
    
    def open(self, path: str, flags: int, mode: int = 0o644, **kwargs):
        """Open a file"""
        with self.lock:
            node = self._get_node(path)
            
            # Create file if needed
            if node is None:
                if flags & os.O_CREAT:
                    parent_path, name = self._get_parent_and_name(path)
                    parent = self._get_node(parent_path)
                    
                    if not isinstance(parent, VFSDirectory):
                        raise NotADirectoryError(f"{parent_path}: Not a directory")
                    
                    node = VFSFile(mode=mode)
                    parent.children[name] = node
                    parent.mtime = time.time()
                    self._save()
                else:
                    raise FileNotFoundError(f"{path}: No such file")
            
            if not isinstance(node, VFSFile):
                raise IsADirectoryError(f"{path}: Is a directory")
            
            # Truncate if needed
            if flags & os.O_TRUNC:
                node.content = b''
                node.mtime = time.time()
                self._save()
            
            # Create file handle
            fd = self.fd_counter
            self.fd_counter += 1
            self.open_files[fd] = {
                'path': path,
                'node': node,
                'position': 0,
                'flags': flags
            }
            
            return KaedeVFSFile(self, fd)
    
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        node = self._get_node(path)
        
        if node is None:
            raise FileNotFoundError(f"{path}: No such directory")
        
        if not isinstance(node, VFSDirectory):
            raise NotADirectoryError(f"{path}: Not a directory")
        
        return list(node.children.keys())
    
    def stat(self, path: str):
        """Get file statistics"""
        node = self._get_node(path)
        
        if node is None:
            raise FileNotFoundError(f"{path}: No such file or directory")
        
        class StatResult:
            pass
        
        stat = StatResult()
        stat.st_mode = node.mode
        stat.st_uid = node.uid
        stat.st_gid = node.gid
        stat.st_atime = node.atime
        stat.st_mtime = node.mtime
        stat.st_ctime = node.ctime
        stat.st_nlink = 1
        
        if isinstance(node, VFSFile):
            stat.st_size = len(node.content)
            stat.st_mode |= 0o100000  # S_IFREG
        else:
            stat.st_size = 4096
            stat.st_mode |= 0o040000  # S_IFDIR
        
        return stat
    
    def unlink(self, path: str):
        """Delete a file"""
        with self.lock:
            node = self._get_node(path)
            
            if node is None:
                raise FileNotFoundError(f"{path}: No such file")
            
            if isinstance(node, VFSDirectory):
                raise IsADirectoryError(f"{path}: Is a directory")
            
            parent_path, name = self._get_parent_and_name(path)
            parent = self._get_node(parent_path)
            del parent.children[name]
            parent.mtime = time.time()
            
            self._save()
    
    def rename(self, old_path: str, new_path: str):
        """Rename/move a file or directory"""
        with self.lock:
            node = self._get_node(old_path)
            if node is None:
                raise FileNotFoundError(f"{old_path}: No such file or directory")
            
            # Remove from old location
            old_parent_path, old_name = self._get_parent_and_name(old_path)
            old_parent = self._get_node(old_parent_path)
            
            # Add to new location
            new_parent_path, new_name = self._get_parent_and_name(new_path)
            new_parent = self._get_node(new_parent_path)
            
            if not isinstance(new_parent, VFSDirectory):
                raise NotADirectoryError(f"{new_parent_path}: Not a directory")
            
            # Move the node
            new_parent.children[new_name] = old_parent.children[old_name]
            del old_parent.children[old_name]
            
            old_parent.mtime = time.time()
            new_parent.mtime = time.time()
            
            self._save()
    
    # File operations
    def read(self, fd: int, size: int = -1) -> bytes:
        """Read from a file"""
        with self.lock:
            if fd not in self.open_files:
                raise ValueError("Invalid file descriptor")
            
            finfo = self.open_files[fd]
            node = finfo['node']
            pos = finfo['position']
            
            if size == -1:
                data = node.content[pos:]
            else:
                data = node.content[pos:pos + size]
            
            finfo['position'] += len(data)
            node.atime = time.time()
            
            return data
    
    def write(self, fd: int, data: bytes) -> int:
        """Write to a file"""
        with self.lock:
            if fd not in self.open_files:
                raise ValueError("Invalid file descriptor")
            
            finfo = self.open_files[fd]
            node = finfo['node']
            pos = finfo['position']
            
            # Write data
            if pos == len(node.content):
                node.content += data
            else:
                node.content = node.content[:pos] + data + node.content[pos + len(data):]
            
            finfo['position'] += len(data)
            node.mtime = time.time()
            
            self._save()
            return len(data)
    
    def seek(self, fd: int, offset: int, whence: int = 0):
        """Seek in a file"""
        with self.lock:
            if fd not in self.open_files:
                raise ValueError("Invalid file descriptor")
            
            finfo = self.open_files[fd]
            node = finfo['node']
            
            if whence == 0:  # SEEK_SET
                finfo['position'] = offset
            elif whence == 1:  # SEEK_CUR
                finfo['position'] += offset
            elif whence == 2:  # SEEK_END
                finfo['position'] = len(node.content) + offset
    
    def close(self, fd: int):
        """Close a file"""
        with self.lock:
            if fd in self.open_files:
                del self.open_files[fd]

class KaedeVFSFile:
    """File handle for KaedeVFS"""
    
    def __init__(self, vfs: KaedeVFS, fd: int):
        self.vfs = vfs
        self.fd = fd
    
    def read(self, size: int = -1) -> bytes:
        return self.vfs.read(self.fd, size)
    
    def write(self, data: Union[str, bytes]) -> int:
        if isinstance(data, str):
            data = data.encode('utf-8')
        return self.vfs.write(self.fd, data)
    
    def seek(self, offset: int, whence: int = 0):
        self.vfs.seek(self.fd, offset, whence)
    
    def close(self):
        self.vfs.close(self.fd)
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

# Global instance
_kaede_vfs = None

def get_vfs() -> KaedeVFS:
    """Get the global KaedeVFS instance"""
    global _kaede_vfs
    if _kaede_vfs is None:
        _kaede_vfs = KaedeVFS()
        
        # Initialize with full filesystem if needed
        try:
            from kos.vfs.vfs_init import initialize_vfs
            if not _kaede_vfs.exists("/.vfs_initialized"):
                initialize_vfs(_kaede_vfs)
        except:
            pass  # Initialization is optional
    
    return _kaede_vfs

# Compatibility exports
VirtualFileSystem = KaedeVFS  # For backward compatibility
"""
KOS Virtual File System
Clean VFS implementation with proper abstraction
"""

import os
import pickle
import time
import stat
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union, BinaryIO
from pathlib import Path
import io

from .errors import VFSError

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
class VFSNode:
    """Base node in the VFS tree"""
    name: str
    mode: int
    uid: int = 0
    gid: int = 0
    atime: float = field(default_factory=time.time)
    mtime: float = field(default_factory=time.time)
    ctime: float = field(default_factory=time.time)

@dataclass
class VFSFile(VFSNode):
    """File node in VFS"""
    content: bytes = b''
    
    @property
    def size(self) -> int:
        return len(self.content)

@dataclass
class VFSDirectory(VFSNode):
    """Directory node in VFS"""
    children: Dict[str, VFSNode] = field(default_factory=dict)
    
    def __post_init__(self):
        # Ensure it's a directory mode
        self.mode = self.mode | stat.S_IFDIR

class VFS(ABC):
    """Abstract base class for Virtual File System"""
    
    @abstractmethod
    def mount(self, source: str, read_only: bool = False):
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
    def stat(self, path: str) -> StatResult:
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

class VFSFileHandle(io.BytesIO):
    """File handle for VFS files"""
    
    def __init__(self, vfs: 'PickleVFS', path: str, mode: str, initial_content: bytes = b''):
        super().__init__(initial_content)
        self.vfs = vfs
        self.path = path
        self.mode = mode
        self._closed = False
        
        if 'a' in mode:
            self.seek(0, 2)  # Seek to end for append
    
    @property
    def closed(self):
        return self._closed
    
    def close(self):
        if not self._closed:
            if 'w' in self.mode or 'a' in self.mode or '+' in self.mode:
                # Save content back to VFS
                self.vfs._write_file_content(self.path, self.getvalue())
            self._closed = True
            super().close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()

class PickleVFS(VFS):
    """Simple VFS implementation using pickle for persistence"""
    
    def __init__(self, disk_path: str = "kaede.kdsk"):
        self.disk_path = disk_path
        self.root = None
        self.read_only = False
        self.mounted = False
    
    def mount(self, source: str = None, read_only: bool = False):
        """Mount the VFS from disk"""
        if self.mounted:
            raise VFSError("VFS already mounted")
        
        self.disk_path = source or self.disk_path
        self.read_only = read_only
        
        if os.path.exists(self.disk_path):
            try:
                with open(self.disk_path, 'rb') as f:
                    self.root = pickle.load(f)
            except Exception as e:
                print(f"Creating new VFS (could not load existing: {e})")
                self._create_new_vfs()
        else:
            self._create_new_vfs()
        
        self.mounted = True
    
    def unmount(self):
        """Save and unmount VFS"""
        if not self.mounted:
            return
        
        if not self.read_only:
            self._save()
        
        self.mounted = False
        self.root = None
    
    def _create_new_vfs(self):
        """Create a new empty VFS with basic structure"""
        self.root = VFSDirectory(
            name='/',
            mode=0o755 | stat.S_IFDIR
        )
        
        # Create basic Unix-like structure
        basic_dirs = [
            '/bin', '/boot', '/dev', '/etc', '/home',
            '/lib', '/media', '/mnt', '/opt', '/proc',
            '/root', '/run', '/sbin', '/srv', '/sys',
            '/tmp', '/usr', '/var'
        ]
        
        for dir_path in basic_dirs:
            self.mkdir(dir_path)
        
        # Create some useful subdirectories
        self.mkdir('/home/user')
        self.mkdir('/usr/bin')
        self.mkdir('/usr/lib')
        self.mkdir('/usr/local')
        self.mkdir('/var/log')
        self.mkdir('/var/lib')
        self.mkdir('/etc/kos')
        
        self._save()
    
    def _save(self):
        """Save VFS to disk"""
        if self.read_only:
            return
        
        try:
            with open(self.disk_path, 'wb') as f:
                pickle.dump(self.root, f)
        except Exception as e:
            raise VFSError(f"Failed to save VFS: {e}")
    
    def _resolve_path(self, path: str) -> tuple[VFSDirectory, str]:
        """Resolve a path to its parent directory and name"""
        path = os.path.normpath(path)
        if path == '/':
            return None, '/'
        
        parts = path.strip('/').split('/')
        name = parts[-1]
        parent_parts = parts[:-1]
        
        current = self.root
        for part in parent_parts:
            if part not in current.children:
                raise VFSError(f"Path not found: {path}")
            current = current.children[part]
            if not isinstance(current, VFSDirectory):
                raise VFSError(f"Not a directory: {part}")
        
        return current, name
    
    def _get_node(self, path: str) -> Optional[VFSNode]:
        """Get a node by path"""
        if path == '/':
            return self.root
        
        try:
            parent, name = self._resolve_path(path)
            return parent.children.get(name)
        except VFSError:
            return None
    
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        return self._get_node(path) is not None
    
    def isfile(self, path: str) -> bool:
        """Check if path is a file"""
        node = self._get_node(path)
        return isinstance(node, VFSFile)
    
    def isdir(self, path: str) -> bool:
        """Check if path is a directory"""
        node = self._get_node(path)
        return isinstance(node, VFSDirectory)
    
    def mkdir(self, path: str, mode: int = 0o755):
        """Create a directory"""
        if self.exists(path):
            raise VFSError(f"Path already exists: {path}")
        
        parent, name = self._resolve_path(path)
        if parent is None and name == '/':
            return  # Root already exists
        
        new_dir = VFSDirectory(
            name=name,
            mode=mode | stat.S_IFDIR
        )
        parent.children[name] = new_dir
        parent.mtime = time.time()
        
        if not self.read_only:
            self._save()
    
    def rmdir(self, path: str):
        """Remove empty directory"""
        if path == '/':
            raise VFSError("Cannot remove root directory")
        
        node = self._get_node(path)
        if not isinstance(node, VFSDirectory):
            raise VFSError(f"Not a directory: {path}")
        
        if node.children:
            raise VFSError(f"Directory not empty: {path}")
        
        parent, name = self._resolve_path(path)
        del parent.children[name]
        parent.mtime = time.time()
        
        if not self.read_only:
            self._save()
    
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        node = self._get_node(path)
        if not isinstance(node, VFSDirectory):
            raise VFSError(f"Not a directory: {path}")
        
        return list(node.children.keys())
    
    def stat(self, path: str) -> StatResult:
        """Get file/directory statistics"""
        node = self._get_node(path)
        if node is None:
            raise VFSError(f"Path not found: {path}")
        
        size = 0
        if isinstance(node, VFSFile):
            size = node.size
        elif isinstance(node, VFSDirectory):
            size = 4096  # Standard directory size
        
        return StatResult(
            st_mode=node.mode,
            st_size=size,
            st_uid=node.uid,
            st_gid=node.gid,
            st_atime=node.atime,
            st_mtime=node.mtime,
            st_ctime=node.ctime
        )
    
    def unlink(self, path: str):
        """Delete a file"""
        node = self._get_node(path)
        if not isinstance(node, VFSFile):
            raise VFSError(f"Not a file: {path}")
        
        parent, name = self._resolve_path(path)
        del parent.children[name]
        parent.mtime = time.time()
        
        if not self.read_only:
            self._save()
    
    def open(self, path: str, mode: str = 'r') -> BinaryIO:
        """Open a file"""
        if 'b' not in mode:
            mode += 'b'  # Always binary mode internally
        
        node = self._get_node(path)
        
        if 'r' in mode:
            if node is None:
                raise VFSError(f"File not found: {path}")
            if not isinstance(node, VFSFile):
                raise VFSError(f"Not a file: {path}")
            
            return VFSFileHandle(self, path, mode, node.content)
        
        elif 'w' in mode or 'a' in mode:
            if self.read_only:
                raise VFSError("VFS is read-only")
            
            if node is None or 'w' in mode:
                # Create new file
                parent, name = self._resolve_path(path)
                new_file = VFSFile(
                    name=name,
                    mode=0o644 | stat.S_IFREG,
                    content=b''
                )
                parent.children[name] = new_file
                parent.mtime = time.time()
                node = new_file
            
            initial_content = node.content if 'a' in mode else b''
            return VFSFileHandle(self, path, mode, initial_content)
        
        else:
            raise VFSError(f"Invalid mode: {mode}")
    
    def _write_file_content(self, path: str, content: bytes):
        """Internal method to write file content"""
        node = self._get_node(path)
        if isinstance(node, VFSFile):
            node.content = content
            node.mtime = time.time()
            if not self.read_only:
                self._save()

# Global VFS instance (singleton pattern)
_vfs_instance = None

def get_vfs(disk_path: str = "kaede.kdsk") -> PickleVFS:
    """Get or create the global VFS instance"""
    global _vfs_instance
    if _vfs_instance is None:
        _vfs_instance = PickleVFS(disk_path)
        _vfs_instance.mount()
    return _vfs_instance
"""
KOS Virtual Filesystem - Unix-like VFS implementation
"""

import os
import stat
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from ..core.performance import LRUCache, memoize, ObjectPool

class FileType(Enum):
    """File type constants"""
    REGULAR = stat.S_IFREG
    DIRECTORY = stat.S_IFDIR
    SYMLINK = stat.S_IFLNK
    CHAR_DEVICE = stat.S_IFCHR
    BLOCK_DEVICE = stat.S_IFBLK
    FIFO = stat.S_IFIFO
    SOCKET = stat.S_IFSOCK

@dataclass
class VFSNode:
    """Virtual filesystem node (inode)"""
    inode: int
    name: str
    file_type: FileType
    mode: int
    uid: int
    gid: int
    size: int
    atime: float
    mtime: float
    ctime: float
    content: Any = None  # File content or device info
    children: Dict[str, 'VFSNode'] = None  # For directories
    target: str = None  # For symlinks
    
    def __post_init__(self):
        if self.children is None and self.file_type == FileType.DIRECTORY:
            self.children = {}

class MountPoint:
    """Represents a mounted filesystem"""
    def __init__(self, fs_type: str, fs_instance: Any, mountpoint: str, options: Dict[str, Any]):
        self.fs_type = fs_type
        self.fs_instance = fs_instance
        self.mountpoint = mountpoint
        self.options = options
        
class KOSVirtualFilesystem:
    """
    Unix-like Virtual Filesystem implementation for KOS
    """
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.filesystem_types = {}  # name -> class mapping
        self.mounts = {}  # mountpoint -> MountPoint
        self.next_inode = 1
        self.inodes = {}  # inode -> VFSNode
        self.root = None
        
        # Performance optimizations
        self._path_cache = LRUCache(max_size=1000, ttl=60.0)  # Cache path resolutions
        self._stat_cache = LRUCache(max_size=500, ttl=30.0)   # Cache stat results
        self._node_pool = ObjectPool(
            factory=lambda: VFSNode(0, "", FileType.REGULAR, 0, 0, 0, 0, 0, 0, 0),
            max_size=100
        )
        
        # Create root directory
        self._create_root()
        
    def _create_root(self):
        """Create root directory"""
        now = time.time()
        self.root = VFSNode(
            inode=self.next_inode,
            name="/",
            file_type=FileType.DIRECTORY,
            mode=0o755,
            uid=0,
            gid=0,
            size=4096,
            atime=now,
            mtime=now,
            ctime=now,
            children={}
        )
        self.inodes[self.next_inode] = self.root
        self.next_inode += 1
        
    def register_filesystem_type(self, name: str, fs_class):
        """Register a filesystem type"""
        self.filesystem_types[name] = fs_class
        
    def mount(self, fs_type: str, mountpoint: str, options: Dict[str, Any]):
        """Mount a filesystem at the given mountpoint"""
        if fs_type not in self.filesystem_types:
            raise ValueError(f"Unknown filesystem type: {fs_type}")
            
        # Create mountpoint if it doesn't exist
        if not self.exists(mountpoint):
            self.makedirs(mountpoint)
            
        # Create filesystem instance
        fs_instance = self.filesystem_types[fs_type]()
        if hasattr(fs_instance, 'mount'):
            fs_instance.mount(mountpoint, options)
            
        # Record mount
        mount = MountPoint(fs_type, fs_instance, mountpoint, options)
        self.mounts[mountpoint] = mount
        
    def umount(self, mountpoint: str):
        """Unmount filesystem"""
        if mountpoint in self.mounts:
            mount = self.mounts[mountpoint]
            if hasattr(mount.fs_instance, 'unmount'):
                mount.fs_instance.unmount()
            del self.mounts[mountpoint]
            
    def _resolve_path(self, path: str) -> VFSNode:
        """Resolve path to VFS node with caching"""
        if path == "/":
            return self.root
        
        # Check cache first
        cached_node = self._path_cache.get(path)
        if cached_node is not None:
            return cached_node
            
        # Normalize path
        normalized_path = os.path.normpath(path)
        if normalized_path.startswith('/'):
            normalized_path = normalized_path[1:]
            
        # Split path components
        components = normalized_path.split('/')
        current = self.root
        
        for component in components:
            if not component:  # Empty component
                continue
                
            if current.file_type != FileType.DIRECTORY:
                raise FileNotFoundError(f"Not a directory: {current.name}")
                
            if component not in current.children:
                raise FileNotFoundError(f"No such file or directory: {path}")
                
            current = current.children[component]
            
            # Follow symlinks
            if current.file_type == FileType.SYMLINK:
                target_path = current.target
                if target_path.startswith('/'):
                    current = self._resolve_path(target_path)
                else:
                    # Relative symlink
                    parent_path = '/'.join(components[:-1])
                    if parent_path:
                        target_path = f"/{parent_path}/{target_path}"
                    else:
                        target_path = f"/{target_path}"
                    current = self._resolve_path(target_path)
        
        # Cache the resolved node
        self._path_cache.put(path, current)
        return current
        
    def _create_node(self, parent: VFSNode, name: str, file_type: FileType, 
                    mode: int, uid: int = 0, gid: int = 0) -> VFSNode:
        """Create a new VFS node"""
        now = time.time()
        node = VFSNode(
            inode=self.next_inode,
            name=name,
            file_type=file_type,
            mode=mode,
            uid=uid,
            gid=gid,
            size=0,
            atime=now,
            mtime=now,
            ctime=now
        )
        
        self.inodes[self.next_inode] = node
        self.next_inode += 1
        
        if parent.file_type == FileType.DIRECTORY:
            parent.children[name] = node
            
        return node
        
    def mkdir(self, path: str, mode: int = 0o755):
        """Create directory"""
        parent_path, name = os.path.split(path)
        if parent_path == "":
            parent_path = "/"
            
        try:
            parent = self._resolve_path(parent_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file or directory: {parent_path}")
            
        if parent.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {parent_path}")
            
        if name in parent.children:
            existing = parent.children[name]
            if existing.file_type == FileType.DIRECTORY:
                # Directory already exists, just return
                return
            else:
                raise FileExistsError(f"File exists: {path}")
            
        self._create_node(parent, name, FileType.DIRECTORY, mode)
        
    def makedirs(self, path: str, mode: int = 0o755):
        """Create directory recursively"""
        if self.exists(path):
            return
            
        parent_path, name = os.path.split(path)
        if parent_path != "/" and not self.exists(parent_path):
            self.makedirs(parent_path, mode)
            
        self.mkdir(path, mode)
        
    def create_file(self, path: str, content: str = "", mode: int = 0o644):
        """Create a regular file"""
        parent_path, name = os.path.split(path)
        if parent_path == "":
            parent_path = "/"
            
        try:
            parent = self._resolve_path(parent_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file or directory: {parent_path}")
            
        if parent.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {parent_path}")
            
        if name in parent.children:
            # Overwrite existing file
            node = parent.children[name]
            node.content = content
            node.size = len(content)
            node.mtime = time.time()
        else:
            # Create new file
            node = self._create_node(parent, name, FileType.REGULAR, mode)
            node.content = content
            node.size = len(content)
            
    def read_file(self, path: str) -> str:
        """Read file content"""
        node = self._resolve_path(path)
        if node.file_type != FileType.REGULAR:
            raise IsADirectoryError(f"Is a directory: {path}")
        return node.content or ""
        
    def write_file(self, path: str, content: str):
        """Write file content"""
        node = self._resolve_path(path)
        if node.file_type != FileType.REGULAR:
            raise IsADirectoryError(f"Is a directory: {path}")
        node.content = content
        node.size = len(content)
        node.mtime = time.time()
        
    def symlink(self, target: str, path: str):
        """Create symbolic link"""
        parent_path, name = os.path.split(path)
        if parent_path == "":
            parent_path = "/"
            
        try:
            parent = self._resolve_path(parent_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"No such file or directory: {parent_path}")
            
        if parent.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {parent_path}")
            
        if name in parent.children:
            raise FileExistsError(f"File exists: {path}")
            
        node = self._create_node(parent, name, FileType.SYMLINK, 0o777)
        node.target = target
        node.size = len(target)
        
    def unlink(self, path: str):
        """Remove file or symlink"""
        parent_path, name = os.path.split(path)
        if parent_path == "":
            parent_path = "/"
            
        parent = self._resolve_path(parent_path)
        if name not in parent.children:
            raise FileNotFoundError(f"No such file or directory: {path}")
            
        node = parent.children[name]
        if node.file_type == FileType.DIRECTORY:
            raise IsADirectoryError(f"Is a directory: {path}")
            
        del parent.children[name]
        del self.inodes[node.inode]
        
    def rmdir(self, path: str):
        """Remove empty directory"""
        parent_path, name = os.path.split(path)
        if parent_path == "":
            parent_path = "/"
            
        parent = self._resolve_path(parent_path)
        if name not in parent.children:
            raise FileNotFoundError(f"No such file or directory: {path}")
            
        node = parent.children[name]
        if node.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {path}")
            
        if node.children:
            raise OSError(f"Directory not empty: {path}")
            
        del parent.children[name]
        del self.inodes[node.inode]
        
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        node = self._resolve_path(path)
        if node.file_type != FileType.DIRECTORY:
            raise NotADirectoryError(f"Not a directory: {path}")
        return list(node.children.keys())
        
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        try:
            self._resolve_path(path)
            return True
        except (FileNotFoundError, NotADirectoryError):
            return False
            
    def isdir(self, path: str) -> bool:
        """Check if path is directory"""
        try:
            node = self._resolve_path(path)
            return node.file_type == FileType.DIRECTORY
        except (FileNotFoundError, NotADirectoryError):
            return False
            
    def isfile(self, path: str) -> bool:
        """Check if path is regular file"""
        try:
            node = self._resolve_path(path)
            return node.file_type == FileType.REGULAR
        except (FileNotFoundError, NotADirectoryError):
            return False
            
    def stat(self, path: str) -> VFSNode:
        """Get file statistics"""
        return self._resolve_path(path)
        
    def chmod(self, path: str, mode: int):
        """Change file permissions"""
        node = self._resolve_path(path)
        node.mode = mode
        node.ctime = time.time()
        
    def chown(self, path: str, uid: int, gid: int):
        """Change file ownership"""
        node = self._resolve_path(path)
        node.uid = uid
        node.gid = gid
        node.ctime = time.time()
        
    def lchown(self, path: str, uid: int, gid: int):
        """Change symlink ownership (don't follow symlinks)"""
        # For our simple implementation, treat same as chown
        self.chown(path, uid, gid)
        
    def sync(self):
        """Sync all filesystems"""
        for mount in self.mounts.values():
            if hasattr(mount.fs_instance, 'sync'):
                mount.fs_instance.sync()
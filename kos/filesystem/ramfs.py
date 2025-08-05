"""
RamFS - RAM Filesystem Implementation
In-memory filesystem for temporary storage
"""

import os
import stat
import time
import threading
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from kos.filesystem.base import FileSystem, FileNode, DirectoryNode


class RamFileNode(FileNode):
    """File node that stores data in RAM"""
    
    def __init__(self, name: str):
        super().__init__(name)
        self._data = bytearray()
        self._lock = threading.RLock()
        self.atime = time.time()
        self.mtime = time.time()
        self.ctime = time.time()
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Read data from file"""
        with self._lock:
            self.atime = time.time()
            
            if offset >= len(self._data):
                return b''
            
            if size == -1:
                return bytes(self._data[offset:])
            else:
                return bytes(self._data[offset:offset + size])
    
    def write(self, data: bytes, offset: int = 0) -> int:
        """Write data to file"""
        with self._lock:
            self.mtime = time.time()
            self.atime = time.time()
            
            # Extend data if necessary
            if offset > len(self._data):
                self._data.extend(b'\0' * (offset - len(self._data)))
            
            # Write data
            end_pos = offset + len(data)
            if end_pos > len(self._data):
                self._data[offset:] = data[:len(self._data) - offset]
                self._data.extend(data[len(self._data) - offset:])
            else:
                self._data[offset:end_pos] = data
            
            return len(data)
    
    def truncate(self, size: int = 0):
        """Truncate file to specified size"""
        with self._lock:
            self.mtime = time.time()
            if size < len(self._data):
                self._data = self._data[:size]
            elif size > len(self._data):
                self._data.extend(b'\0' * (size - len(self._data)))
    
    def append(self, data: bytes) -> int:
        """Append data to file"""
        with self._lock:
            return self.write(data, len(self._data))
    
    @property
    def size(self) -> int:
        """Get file size"""
        with self._lock:
            return len(self._data)


class RamFS(FileSystem):
    """RAM-based filesystem implementation"""
    
    def __init__(self, max_size: Optional[int] = None):
        super().__init__()
        self.max_size = max_size or (512 * 1024 * 1024)  # 512MB default
        self._used_space = 0
        self._lock = threading.RLock()
        self._inode_counter = 1000
        self._open_files: Dict[int, RamFileNode] = {}
        self._fd_counter = 100
    
    def create_file(self, path: str, mode: int = 0o644) -> Optional[RamFileNode]:
        """Create a new file"""
        with self._lock:
            # Parse path
            parts = path.strip('/').split('/')
            filename = parts[-1]
            
            # Navigate to parent directory
            parent = self._navigate_to_parent(parts[:-1])
            if not parent:
                return None
            
            # Check if file already exists
            if parent.get_child(filename):
                return None
            
            # Create file
            file_node = RamFileNode(filename)
            file_node.mode = stat.S_IFREG | mode
            file_node.uid = os.getuid() if hasattr(os, 'getuid') else 1000
            file_node.gid = os.getgid() if hasattr(os, 'getgid') else 1000
            file_node.inode = self._get_next_inode()
            
            parent.add_child(file_node)
            return file_node
    
    def create_directory(self, path: str, mode: int = 0o755) -> Optional[DirectoryNode]:
        """Create a new directory"""
        with self._lock:
            # Parse path
            parts = path.strip('/').split('/')
            dirname = parts[-1]
            
            # Navigate to parent directory
            parent = self._navigate_to_parent(parts[:-1])
            if not parent:
                return None
            
            # Check if directory already exists
            if parent.get_child(dirname):
                return None
            
            # Create directory
            dir_node = DirectoryNode(dirname)
            dir_node.mode = stat.S_IFDIR | mode
            dir_node.uid = os.getuid() if hasattr(os, 'getuid') else 1000
            dir_node.gid = os.getgid() if hasattr(os, 'getgid') else 1000
            dir_node.inode = self._get_next_inode()
            
            parent.add_child(dir_node)
            return dir_node
    
    def open_file(self, path: str, flags: int = os.O_RDONLY, mode: int = 0o644) -> int:
        """Open a file and return file descriptor"""
        with self._lock:
            node = self.get_node(path)
            
            # Create file if O_CREAT is set
            if not node and (flags & os.O_CREAT):
                node = self.create_file(path, mode)
            
            if not node or not isinstance(node, RamFileNode):
                return -1
            
            # Generate file descriptor
            fd = self._fd_counter
            self._fd_counter += 1
            self._open_files[fd] = node
            
            # Truncate if O_TRUNC is set
            if flags & os.O_TRUNC:
                node.truncate(0)
            
            return fd
    
    def close_file(self, fd: int) -> bool:
        """Close a file descriptor"""
        with self._lock:
            if fd in self._open_files:
                del self._open_files[fd]
                return True
            return False
    
    def read_fd(self, fd: int, size: int = -1, offset: int = 0) -> bytes:
        """Read from file descriptor"""
        with self._lock:
            if fd not in self._open_files:
                raise OSError(9, "Bad file descriptor")
            
            file_node = self._open_files[fd]
            return file_node.read(size, offset)
    
    def write_fd(self, fd: int, data: bytes, offset: int = 0) -> int:
        """Write to file descriptor"""
        with self._lock:
            if fd not in self._open_files:
                raise OSError(9, "Bad file descriptor")
            
            file_node = self._open_files[fd]
            
            # Check space
            new_size = max(file_node.size, offset + len(data))
            space_needed = new_size - file_node.size
            
            if self._used_space + space_needed > self.max_size:
                raise OSError(28, "No space left on device")
            
            bytes_written = file_node.write(data, offset)
            self._used_space += space_needed
            
            return bytes_written
    
    def delete_file(self, path: str) -> bool:
        """Delete a file"""
        with self._lock:
            # Parse path
            parts = path.strip('/').split('/')
            filename = parts[-1]
            
            # Navigate to parent directory
            parent = self._navigate_to_parent(parts[:-1])
            if not parent:
                return False
            
            # Get file node
            node = parent.get_child(filename)
            if not node or not isinstance(node, RamFileNode):
                return False
            
            # Update used space
            self._used_space -= node.size
            
            # Remove file
            parent.remove_child(filename)
            return True
    
    def delete_directory(self, path: str) -> bool:
        """Delete a directory"""
        with self._lock:
            # Parse path
            parts = path.strip('/').split('/')
            dirname = parts[-1]
            
            # Navigate to parent directory
            parent = self._navigate_to_parent(parts[:-1])
            if not parent:
                return False
            
            # Get directory node
            node = parent.get_child(dirname)
            if not node or not isinstance(node, DirectoryNode):
                return False
            
            # Check if empty
            if node.children:
                raise OSError(39, "Directory not empty")
            
            # Remove directory
            parent.remove_child(dirname)
            return True
    
    def rename(self, old_path: str, new_path: str) -> bool:
        """Rename/move a file or directory"""
        with self._lock:
            # Get source node
            old_parts = old_path.strip('/').split('/')
            old_name = old_parts[-1]
            old_parent = self._navigate_to_parent(old_parts[:-1])
            
            if not old_parent:
                return False
            
            node = old_parent.get_child(old_name)
            if not node:
                return False
            
            # Get destination parent
            new_parts = new_path.strip('/').split('/')
            new_name = new_parts[-1]
            new_parent = self._navigate_to_parent(new_parts[:-1])
            
            if not new_parent:
                return False
            
            # Check if destination exists
            if new_parent.get_child(new_name):
                return False
            
            # Move node
            old_parent.remove_child(old_name)
            node.name = new_name
            new_parent.add_child(node)
            
            return True
    
    def get_node(self, path: str) -> Optional[Union[FileNode, DirectoryNode]]:
        """Get a node by path"""
        if not path or path == '/':
            return self.root
        
        parts = path.strip('/').split('/')
        current = self.root
        
        for part in parts:
            if isinstance(current, DirectoryNode):
                current = current.get_child(part)
                if not current:
                    return None
            else:
                return None
        
        return current
    
    def _navigate_to_parent(self, parts: List[str]) -> Optional[DirectoryNode]:
        """Navigate to parent directory"""
        current = self.root
        
        for part in parts:
            if isinstance(current, DirectoryNode):
                child = current.get_child(part)
                if child and isinstance(child, DirectoryNode):
                    current = child
                else:
                    return None
            else:
                return None
        
        return current
    
    def _get_next_inode(self) -> int:
        """Get next available inode number"""
        self._inode_counter += 1
        return self._inode_counter
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filesystem statistics"""
        with self._lock:
            return {
                'total_space': self.max_size,
                'used_space': self._used_space,
                'free_space': self.max_size - self._used_space,
                'total_inodes': self._inode_counter - 1000,
                'open_files': len(self._open_files),
                'mount_point': '/tmp'  # Typical mount point
            }
    
    def sync(self):
        """Sync filesystem (no-op for RAM)"""
        # RAM filesystem doesn't need syncing
        pass
    
    def fsck(self) -> List[str]:
        """File system check"""
        issues = []
        
        with self._lock:
            # Check used space calculation
            actual_used = self._calculate_used_space(self.root)
            if actual_used != self._used_space:
                issues.append(f"Used space mismatch: reported={self._used_space}, actual={actual_used}")
                self._used_space = actual_used
            
            # Check for orphaned file descriptors
            for fd, node in list(self._open_files.items()):
                if not self._node_exists(self.root, node):
                    issues.append(f"Orphaned file descriptor: {fd}")
                    del self._open_files[fd]
        
        return issues
    
    def _calculate_used_space(self, node: Union[FileNode, DirectoryNode]) -> int:
        """Recursively calculate used space"""
        if isinstance(node, RamFileNode):
            return node.size
        elif isinstance(node, DirectoryNode):
            total = 0
            for child in node.children.values():
                total += self._calculate_used_space(child)
            return total
        return 0
    
    def _node_exists(self, root: DirectoryNode, target: Union[FileNode, DirectoryNode]) -> bool:
        """Check if a node exists in the tree"""
        if root == target:
            return True
        
        for child in root.children.values():
            if child == target:
                return True
            if isinstance(child, DirectoryNode):
                if self._node_exists(child, target):
                    return True
        
        return False
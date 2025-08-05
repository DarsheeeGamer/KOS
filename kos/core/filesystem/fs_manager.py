"""
KOS Filesystem Manager

This module provides the filesystem manager for KOS, handling filesystem
registration, mounting, and management.
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple, Set, Callable, Union

from .fs_types import FileSystemType, FileType, FileInfo, FilesystemError, FilesystemNotFoundError
from .path_utils import normalize_path, is_absolute_path, join_path, split_path

# Set up logging
logger = logging.getLogger('KOS.core.filesystem.fs_manager')

# Global state
_fs_state = {
    'initialized': False,
    'registered_filesystems': {},  # type -> implementation
    'mounted_filesystems': {},     # mount_point -> filesystem_instance
    'mount_points': [],           # list of mount points in order of specificity
    'fs_callbacks': {},           # event -> callbacks
    'default_fs': None,           # default filesystem type
    'root_fs': None               # root filesystem instance
}

# Locks
_fs_lock = threading.RLock()
_mount_lock = threading.RLock()


class FilesystemBase:
    """Base class for filesystem implementations"""
    
    def __init__(self, fs_type: FileSystemType, name: str, config: Dict = None):
        """
        Initialize filesystem
        
        Args:
            fs_type: Filesystem type
            name: Filesystem name
            config: Configuration parameters
        """
        self.fs_type = fs_type
        self.name = name
        self.config = config or {}
        self.mount_point = None
        self.initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the filesystem
        
        Returns:
            Success status
        """
        self.initialized = True
        return True
    
    def shutdown(self) -> bool:
        """
        Shutdown the filesystem
        
        Returns:
            Success status
        """
        self.initialized = False
        return True
    
    def mount(self, mount_point: str) -> bool:
        """
        Mount the filesystem at a mount point
        
        Args:
            mount_point: Mount point path
        
        Returns:
            Success status
        """
        self.mount_point = mount_point
        return True
    
    def unmount(self) -> bool:
        """
        Unmount the filesystem
        
        Returns:
            Success status
        """
        self.mount_point = None
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get filesystem information
        
        Returns:
            Filesystem information
        """
        return {
            'type': self.fs_type.value,
            'name': self.name,
            'mount_point': self.mount_point,
            'initialized': self.initialized,
            'config': self.config
        }
    
    # File operations - to be implemented by subclasses
    def create_file(self, path: str) -> bool:
        """Create a new file"""
        logger.warning(f"{self.__class__.__name__} does not implement create_file")
        return False
    
    def delete_file(self, path: str) -> bool:
        """Delete a file"""
        logger.warning(f"{self.__class__.__name__} does not implement delete_file")
        return False
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Rename a file"""
        logger.warning(f"{self.__class__.__name__} does not implement rename_file")
        return False
    
    def get_file_info(self, path: str) -> FileInfo:
        """Get file information"""
        logger.warning(f"{self.__class__.__name__} does not implement get_file_info")
        raise FileNotFoundError(f"File not found: {path}")
    
    def set_file_info(self, path: str, info: Dict[str, Any]) -> bool:
        """Set file information"""
        logger.warning(f"{self.__class__.__name__} does not implement set_file_info")
        return False
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists"""
        logger.warning(f"{self.__class__.__name__} does not implement file_exists")
        return False
    
    def open_file(self, path: str, mode: str) -> Any:
        """Open a file"""
        logger.warning(f"{self.__class__.__name__} does not implement open_file")
        raise FileNotFoundError(f"File not found: {path}")
    
    def close_file(self, file_handle: Any) -> bool:
        """Close a file"""
        logger.warning(f"{self.__class__.__name__} does not implement close_file")
        return False
    
    def read_file(self, file_handle: Any, size: int = -1) -> bytes:
        """Read from a file"""
        logger.warning(f"{self.__class__.__name__} does not implement read_file")
        return b''
    
    def write_file(self, file_handle: Any, data: bytes) -> int:
        """Write to a file"""
        logger.warning(f"{self.__class__.__name__} does not implement write_file")
        return 0
    
    def seek_file(self, file_handle: Any, offset: int, whence: int = 0) -> int:
        """Seek within a file"""
        logger.warning(f"{self.__class__.__name__} does not implement seek_file")
        return 0
    
    def flush_file(self, file_handle: Any) -> bool:
        """Flush file buffers"""
        logger.warning(f"{self.__class__.__name__} does not implement flush_file")
        return True
    
    def list_directory(self, path: str) -> List[FileInfo]:
        """List directory contents"""
        logger.warning(f"{self.__class__.__name__} does not implement list_directory")
        return []
    
    def create_directory(self, path: str) -> bool:
        """Create a directory"""
        logger.warning(f"{self.__class__.__name__} does not implement create_directory")
        return False
    
    def delete_directory(self, path: str) -> bool:
        """Delete a directory"""
        logger.warning(f"{self.__class__.__name__} does not implement delete_directory")
        return False


class MemoryFilesystem(FilesystemBase):
    """In-memory filesystem implementation"""
    
    def __init__(self, name: str, config: Dict = None):
        """
        Initialize memory filesystem
        
        Args:
            name: Filesystem name
            config: Configuration parameters
        """
        super().__init__(FileSystemType.MEMORY, name, config)
        self.files = {}  # path -> file_info
        self.file_data = {}  # path -> data
        self.open_files = {}  # handle -> file_info
        self.next_handle = 1
    
    def create_file(self, path: str) -> bool:
        """Create a new file"""
        path = normalize_path(path)
        
        # Check if the file already exists
        if path in self.files:
            return False
        
        # Create parent directories if needed
        parent_dir = os.path.dirname(path)
        if parent_dir and parent_dir != '/' and not self.file_exists(parent_dir):
            self.create_directory(parent_dir)
        
        # Create file info
        now = time.time()
        file_info = FileInfo(
            name=os.path.basename(path),
            path=path,
            type=FileType.REGULAR,
            size=0,
            created=now,
            modified=now,
            accessed=now,
            owner='root',
            group='root',
            permissions=0o644,
            is_hidden=os.path.basename(path).startswith('.')
        )
        
        self.files[path] = file_info
        self.file_data[path] = bytearray()
        
        return True
    
    def delete_file(self, path: str) -> bool:
        """Delete a file"""
        path = normalize_path(path)
        
        # Check if the file exists
        if path not in self.files:
            return False
        
        # Check if it's a directory
        if self.files[path].type == FileType.DIRECTORY:
            return False
        
        # Delete the file
        del self.files[path]
        if path in self.file_data:
            del self.file_data[path]
        
        return True
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        """Rename a file"""
        old_path = normalize_path(old_path)
        new_path = normalize_path(new_path)
        
        # Check if the source file exists
        if old_path not in self.files:
            return False
        
        # Check if the destination already exists
        if new_path in self.files:
            return False
        
        # Rename the file
        self.files[new_path] = self.files[old_path]
        self.files[new_path].path = new_path
        self.files[new_path].name = os.path.basename(new_path)
        
        if old_path in self.file_data:
            self.file_data[new_path] = self.file_data[old_path]
            del self.file_data[old_path]
        
        del self.files[old_path]
        
        return True
    
    def get_file_info(self, path: str) -> FileInfo:
        """Get file information"""
        path = normalize_path(path)
        
        # Check if the file exists
        if path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        
        return self.files[path]
    
    def set_file_info(self, path: str, info: Dict[str, Any]) -> bool:
        """Set file information"""
        path = normalize_path(path)
        
        # Check if the file exists
        if path not in self.files:
            return False
        
        # Update file info
        file_info = self.files[path]
        
        if 'permissions' in info:
            file_info.permissions = info['permissions']
        
        if 'owner' in info:
            file_info.owner = info['owner']
        
        if 'group' in info:
            file_info.group = info['group']
        
        if 'modified' in info:
            file_info.modified = info['modified']
        
        if 'accessed' in info:
            file_info.accessed = info['accessed']
        
        if 'metadata' in info:
            if file_info.metadata is None:
                file_info.metadata = {}
            file_info.metadata.update(info['metadata'])
        
        return True
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists"""
        path = normalize_path(path)
        return path in self.files
    
    def open_file(self, path: str, mode: str) -> Any:
        """Open a file"""
        path = normalize_path(path)
        
        # Check if the file exists for read modes
        if 'r' in mode and path not in self.files:
            raise FileNotFoundError(f"File not found: {path}")
        
        # Create file if it doesn't exist for write modes
        if ('w' in mode or 'a' in mode) and path not in self.files:
            self.create_file(path)
        
        # Check if it's a directory
        if path in self.files and self.files[path].type == FileType.DIRECTORY:
            raise IsADirectoryError(f"Is a directory: {path}")
        
        # Create file handle
        handle = self.next_handle
        self.next_handle += 1
        
        self.open_files[handle] = {
            'path': path,
            'mode': mode,
            'position': 0,
            'info': self.files[path]
        }
        
        # Update access time
        self.files[path].accessed = time.time()
        
        # Truncate file if 'w' mode
        if 'w' in mode and path in self.file_data:
            self.file_data[path] = bytearray()
            self.files[path].size = 0
            self.files[path].modified = time.time()
        
        return handle
    
    def close_file(self, file_handle: Any) -> bool:
        """Close a file"""
        if file_handle not in self.open_files:
            return False
        
        del self.open_files[file_handle]
        return True
    
    def read_file(self, file_handle: Any, size: int = -1) -> bytes:
        """Read from a file"""
        if file_handle not in self.open_files:
            raise ValueError("Invalid file handle")
        
        file_info = self.open_files[file_handle]
        
        # Check if file is opened for reading
        if 'r' not in file_info['mode'] and '+' not in file_info['mode']:
            raise IOError("File not opened for reading")
        
        path = file_info['path']
        position = file_info['position']
        
        # Read data
        if path not in self.file_data:
            return b''
        
        data = self.file_data[path]
        
        if size < 0:
            # Read until the end
            result = bytes(data[position:])
            file_info['position'] = len(data)
        else:
            # Read specified number of bytes
            result = bytes(data[position:position + size])
            file_info['position'] += len(result)
        
        # Update access time
        self.files[path].accessed = time.time()
        
        return result
    
    def write_file(self, file_handle: Any, data: bytes) -> int:
        """Write to a file"""
        if file_handle not in self.open_files:
            raise ValueError("Invalid file handle")
        
        file_info = self.open_files[file_handle]
        
        # Check if file is opened for writing
        if 'w' not in file_info['mode'] and 'a' not in file_info['mode'] and '+' not in file_info['mode']:
            raise IOError("File not opened for writing")
        
        path = file_info['path']
        position = file_info['position']
        
        # Ensure file data exists
        if path not in self.file_data:
            self.file_data[path] = bytearray()
        
        # Adjust position for append mode
        if 'a' in file_info['mode']:
            position = len(self.file_data[path])
            file_info['position'] = position
        
        # Write data
        file_data = self.file_data[path]
        
        # Ensure the file is large enough
        if position > len(file_data):
            file_data.extend(b'\0' * (position - len(file_data)))
        
        # Write at position
        if position == len(file_data):
            file_data.extend(data)
        else:
            file_data[position:position + len(data)] = data
        
        # Update position
        file_info['position'] += len(data)
        
        # Update file size and modification time
        self.files[path].size = len(file_data)
        self.files[path].modified = time.time()
        
        return len(data)
    
    def seek_file(self, file_handle: Any, offset: int, whence: int = 0) -> int:
        """Seek within a file"""
        if file_handle not in self.open_files:
            raise ValueError("Invalid file handle")
        
        file_info = self.open_files[file_handle]
        path = file_info['path']
        
        # Calculate new position
        if whence == 0:  # SEEK_SET
            new_position = offset
        elif whence == 1:  # SEEK_CUR
            new_position = file_info['position'] + offset
        elif whence == 2:  # SEEK_END
            new_position = len(self.file_data.get(path, b'')) + offset
        else:
            raise ValueError("Invalid whence value")
        
        # Ensure position is not negative
        if new_position < 0:
            new_position = 0
        
        file_info['position'] = new_position
        return new_position
    
    def flush_file(self, file_handle: Any) -> bool:
        """Flush file buffers"""
        if file_handle not in self.open_files:
            return False
        
        # Memory filesystem doesn't need explicit flushing
        return True
    
    def list_directory(self, path: str) -> List[FileInfo]:
        """List directory contents"""
        path = normalize_path(path)
        
        # Ensure path ends with a separator for matching
        if not path.endswith('/'):
            path += '/'
        
        # Special case for root directory
        if path == '/':
            path = ''
        
        # Find all files that are direct children of this path
        result = []
        
        for file_path, file_info in self.files.items():
            # Skip the directory itself
            if file_path == path:
                continue
            
            # Check if this is a direct child
            if file_path.startswith(path):
                # Extract the relative path
                rel_path = file_path[len(path):]
                
                # Only include direct children (no slashes in rel_path)
                if '/' not in rel_path:
                    result.append(file_info)
        
        return result
    
    def create_directory(self, path: str) -> bool:
        """Create a directory"""
        path = normalize_path(path)
        
        # Check if the directory already exists
        if path in self.files:
            return False
        
        # Create parent directories if needed
        parent_dir = os.path.dirname(path)
        if parent_dir and parent_dir != '/' and not self.file_exists(parent_dir):
            self.create_directory(parent_dir)
        
        # Create directory info
        now = time.time()
        dir_info = FileInfo(
            name=os.path.basename(path) or path,
            path=path,
            type=FileType.DIRECTORY,
            size=0,
            created=now,
            modified=now,
            accessed=now,
            owner='root',
            group='root',
            permissions=0o755,
            is_hidden=os.path.basename(path).startswith('.')
        )
        
        self.files[path] = dir_info
        
        return True
    
    def delete_directory(self, path: str) -> bool:
        """Delete a directory"""
        path = normalize_path(path)
        
        # Check if the directory exists
        if path not in self.files:
            return False
        
        # Check if it's a directory
        if self.files[path].type != FileType.DIRECTORY:
            return False
        
        # Check if the directory is empty
        for file_path in self.files:
            if file_path != path and file_path.startswith(path + '/'):
                return False
        
        # Delete the directory
        del self.files[path]
        
        return True


def register_fs(fs_type: FileSystemType, fs_class: type) -> bool:
    """
    Register a filesystem implementation
    
    Args:
        fs_type: Filesystem type
        fs_class: Filesystem implementation class
    
    Returns:
        Success status
    """
    with _fs_lock:
        if fs_type in _fs_state['registered_filesystems']:
            logger.warning(f"Filesystem type already registered: {fs_type}")
            return False
        
        _fs_state['registered_filesystems'][fs_type] = fs_class
        logger.info(f"Registered filesystem type: {fs_type}")
        return True


def unregister_fs(fs_type: FileSystemType) -> bool:
    """
    Unregister a filesystem implementation
    
    Args:
        fs_type: Filesystem type
    
    Returns:
        Success status
    """
    with _fs_lock:
        if fs_type not in _fs_state['registered_filesystems']:
            logger.warning(f"Filesystem type not registered: {fs_type}")
            return False
        
        # Check if any mounted filesystems are of this type
        for mount_point, fs in _fs_state['mounted_filesystems'].items():
            if fs.fs_type == fs_type:
                logger.warning(f"Cannot unregister filesystem type with active mounts: {fs_type}")
                return False
        
        del _fs_state['registered_filesystems'][fs_type]
        logger.info(f"Unregistered filesystem type: {fs_type}")
        return True


def mount(fs_type: FileSystemType, mount_point: str, name: str = None, config: Dict = None) -> bool:
    """
    Mount a filesystem at a mount point
    
    Args:
        fs_type: Filesystem type
        mount_point: Mount point path
        name: Filesystem name
        config: Filesystem configuration
    
    Returns:
        Success status
    """
    with _mount_lock:
        # Check if the filesystem type is registered
        if fs_type not in _fs_state['registered_filesystems']:
            logger.error(f"Filesystem type not registered: {fs_type}")
            return False
        
        # Normalize mount point
        mount_point = normalize_path(mount_point)
        
        # Check if the mount point is already in use
        if mount_point in _fs_state['mounted_filesystems']:
            logger.warning(f"Mount point already in use: {mount_point}")
            return False
        
        # Create a filesystem instance
        fs_class = _fs_state['registered_filesystems'][fs_type]
        fs_instance = fs_class(name or f"fs_{mount_point}", config)
        
        # Initialize the filesystem
        if not fs_instance.initialize():
            logger.error(f"Failed to initialize filesystem: {mount_point}")
            return False
        
        # Mount the filesystem
        if not fs_instance.mount(mount_point):
            logger.error(f"Failed to mount filesystem: {mount_point}")
            fs_instance.shutdown()
            return False
        
        # Add to mounted filesystems
        _fs_state['mounted_filesystems'][mount_point] = fs_instance
        
        # Update mount points list (sorted by length, longest first)
        _fs_state['mount_points'].append(mount_point)
        _fs_state['mount_points'].sort(key=len, reverse=True)
        
        logger.info(f"Mounted {fs_type} filesystem at {mount_point}")
        
        # Set root filesystem if this is the root mount
        if mount_point == '/':
            _fs_state['root_fs'] = fs_instance
        
        return True


def unmount(mount_point: str) -> bool:
    """
    Unmount a filesystem
    
    Args:
        mount_point: Mount point path
    
    Returns:
        Success status
    """
    with _mount_lock:
        # Normalize mount point
        mount_point = normalize_path(mount_point)
        
        # Check if the mount point exists
        if mount_point not in _fs_state['mounted_filesystems']:
            logger.warning(f"Mount point not found: {mount_point}")
            return False
        
        # Get the filesystem instance
        fs_instance = _fs_state['mounted_filesystems'][mount_point]
        
        # Unmount the filesystem
        if not fs_instance.unmount():
            logger.error(f"Failed to unmount filesystem: {mount_point}")
            return False
        
        # Shutdown the filesystem
        fs_instance.shutdown()
        
        # Remove from mounted filesystems
        del _fs_state['mounted_filesystems'][mount_point]
        
        # Update mount points list
        _fs_state['mount_points'].remove(mount_point)
        
        logger.info(f"Unmounted filesystem at {mount_point}")
        
        # Clear root filesystem if this was the root mount
        if mount_point == '/' and _fs_state['root_fs'] == fs_instance:
            _fs_state['root_fs'] = None
        
        return True


def get_mount_points() -> List[str]:
    """
    Get all mount points
    
    Returns:
        List of mount points
    """
    with _mount_lock:
        return list(_fs_state['mount_points'])


def get_mounted_filesystems() -> Dict[str, Any]:
    """
    Get all mounted filesystems
    
    Returns:
        Dictionary of mount_point -> filesystem_info
    """
    with _mount_lock:
        result = {}
        for mount_point, fs in _fs_state['mounted_filesystems'].items():
            result[mount_point] = fs.get_info()
        return result


def _find_filesystem_for_path(path: str) -> Tuple[FilesystemBase, str]:
    """
    Find the filesystem and relative path for a given path
    
    Args:
        path: Absolute path
    
    Returns:
        Tuple of (filesystem, relative_path)
    """
    # Normalize the path
    path = normalize_path(path)
    
    # Ensure the path is absolute
    if not is_absolute_path(path):
        raise ValueError(f"Path must be absolute: {path}")
    
    # Find the longest matching mount point
    for mount_point in _fs_state['mount_points']:
        if path == mount_point or path.startswith(mount_point + '/'):
            fs = _fs_state['mounted_filesystems'][mount_point]
            rel_path = path[len(mount_point):]
            if not rel_path:
                rel_path = '/'
            return fs, rel_path
    
    # No matching mount point
    raise FilesystemNotFoundError(f"No filesystem mounted for path: {path}")


def initialize() -> bool:
    """
    Initialize the filesystem manager
    
    Returns:
        Success status
    """
    global _fs_state
    
    with _fs_lock:
        if _fs_state['initialized']:
            logger.warning("Filesystem manager already initialized")
            return True
        
        logger.info("Initializing filesystem manager")
        
        # Register built-in filesystem types
        register_fs(FileSystemType.MEMORY, MemoryFilesystem)
        
        # Set default filesystem type
        _fs_state['default_fs'] = FileSystemType.MEMORY
        
        # Mount root filesystem
        mount(FileSystemType.MEMORY, '/', 'root_fs')
        
        # Mark as initialized
        _fs_state['initialized'] = True
        
        logger.info("Filesystem manager initialized")
        
        return True

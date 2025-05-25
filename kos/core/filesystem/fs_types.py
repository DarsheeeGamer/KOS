"""
KOS Filesystem Types

This module defines filesystem types, constants, and data structures used
throughout the filesystem management system.
"""

import os
import time
from enum import Enum, auto
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set, Union


class FileSystemType(Enum):
    """Filesystem types supported by KOS"""
    MEMORY = "memory"     # In-memory filesystem
    DISK = "disk"         # Physical disk filesystem
    NETWORK = "network"   # Network filesystem
    VIRTUAL = "virtual"   # Virtual filesystem (procfs, sysfs, etc.)
    USER = "user"         # User-defined filesystem


class FileType(Enum):
    """File types"""
    REGULAR = "regular"   # Regular file
    DIRECTORY = "directory"  # Directory
    SYMLINK = "symlink"   # Symbolic link
    PIPE = "pipe"         # Named pipe
    SOCKET = "socket"     # Socket
    DEVICE = "device"     # Device file
    UNKNOWN = "unknown"   # Unknown file type


class FileMode(Enum):
    """File access modes"""
    READ = "r"            # Read mode
    WRITE = "w"           # Write mode (truncate if exists)
    APPEND = "a"          # Append mode
    READ_PLUS = "r+"      # Read and write mode
    WRITE_PLUS = "w+"     # Read and write mode (truncate if exists)
    APPEND_PLUS = "a+"    # Read and append mode
    BINARY = "b"          # Binary mode (can be combined with others)


class FilePermission:
    """File permission constants"""
    NONE = 0
    EXECUTE = 1
    WRITE = 2
    WRITE_EXECUTE = 3
    READ = 4
    READ_EXECUTE = 5
    READ_WRITE = 6
    READ_WRITE_EXECUTE = 7


@dataclass
class FileInfo:
    """File information"""
    name: str             # File name
    path: str             # File path
    type: FileType        # File type
    size: int             # File size in bytes
    created: float        # Creation time
    modified: float       # Last modification time
    accessed: float       # Last access time
    owner: str            # Owner user ID
    group: str            # Owner group ID
    permissions: int      # File permissions (octal)
    is_hidden: bool       # Whether the file is hidden
    metadata: Dict[str, Any] = None  # Additional metadata
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'name': self.name,
            'path': self.path,
            'type': self.type.value,
            'size': self.size,
            'created': self.created,
            'modified': self.modified,
            'accessed': self.accessed,
            'owner': self.owner,
            'group': self.group,
            'permissions': self.permissions,
            'is_hidden': self.is_hidden,
            'metadata': self.metadata or {}
        }
    
    @staticmethod
    def from_dict(data):
        """Create from dictionary"""
        return FileInfo(
            name=data['name'],
            path=data['path'],
            type=FileType(data['type']),
            size=data['size'],
            created=data['created'],
            modified=data['modified'],
            accessed=data['accessed'],
            owner=data['owner'],
            group=data['group'],
            permissions=data['permissions'],
            is_hidden=data['is_hidden'],
            metadata=data.get('metadata', {})
        )
    
    @staticmethod
    def from_os_stat(path, name=None):
        """Create from os.stat() result"""
        stat = os.stat(path)
        if name is None:
            name = os.path.basename(path)
        
        # Determine file type
        if os.path.isdir(path):
            file_type = FileType.DIRECTORY
        elif os.path.islink(path):
            file_type = FileType.SYMLINK
        elif os.path.isfile(path):
            file_type = FileType.REGULAR
        else:
            file_type = FileType.UNKNOWN
        
        # Create file info
        return FileInfo(
            name=name,
            path=path,
            type=file_type,
            size=stat.st_size,
            created=stat.st_ctime,
            modified=stat.st_mtime,
            accessed=stat.st_atime,
            owner=str(stat.st_uid),
            group=str(stat.st_gid),
            permissions=stat.st_mode & 0o777,  # Extract permission bits
            is_hidden=name.startswith('.') if name else False
        )


class FilesystemError(Exception):
    """Base exception for filesystem errors"""
    pass


class FileNotFoundError(FilesystemError):
    """File not found error"""
    pass


class PermissionError(FilesystemError):
    """Permission denied error"""
    pass


class FileExistsError(FilesystemError):
    """File already exists error"""
    pass


class NotADirectoryError(FilesystemError):
    """Not a directory error"""
    pass


class IsADirectoryError(FilesystemError):
    """Is a directory error"""
    pass


class FilesystemNotFoundError(FilesystemError):
    """Filesystem not found error"""
    pass

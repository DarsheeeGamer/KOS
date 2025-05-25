"""
KOS Filesystem Management

This package provides filesystem management capabilities for KOS, offering a unified
interface for file operations, filesystem mounting, and path handling.
"""

import os
import sys
import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

# Import filesystem components
from .fs_types import FileSystemType, FileType, FileMode, FileInfo
from .fs_types import FilesystemError, FileNotFoundError, PermissionError
from .fs_types import FileExistsError, NotADirectoryError, IsADirectoryError

from .path_utils import normalize_path, resolve_path, join_path, split_path
from .path_utils import is_absolute_path, is_relative_path, get_absolute_path
from .path_utils import get_parent_directory, get_path_components, get_path_depth
from .path_utils import is_subpath

from .fs_manager import initialize, register_fs, unregister_fs, mount, unmount
from .fs_manager import get_mount_points, get_mounted_filesystems, FilesystemBase
from .fs_manager import MemoryFilesystem

from .file_ops import open_file, close_file, read_file, write_file, seek_file, flush_file
from .file_ops import create_file, delete_file, rename_file, copy_file, move_file
from .file_ops import get_file_info, set_file_info, list_directory, file_exists
from .file_ops import create_directory, delete_directory, is_directory
from .file_ops import read_entire_file, write_entire_file, append_to_file

# Set up logging
logger = logging.getLogger('KOS.core.filesystem')

# Module exports
__all__ = [
    # Types
    'FileSystemType', 'FileType', 'FileMode', 'FileInfo',
    'FilesystemError', 'FileNotFoundError', 'PermissionError',
    'FileExistsError', 'NotADirectoryError', 'IsADirectoryError',
    
    # Path utilities
    'normalize_path', 'resolve_path', 'join_path', 'split_path',
    'is_absolute_path', 'is_relative_path', 'get_absolute_path',
    'get_parent_directory', 'get_path_components', 'get_path_depth',
    'is_subpath',
    
    # Filesystem manager
    'initialize', 'register_fs', 'unregister_fs', 'mount', 'unmount',
    'get_mount_points', 'get_mounted_filesystems', 'FilesystemBase',
    'MemoryFilesystem',
    
    # File operations
    'open_file', 'close_file', 'read_file', 'write_file', 'seek_file', 'flush_file',
    'create_file', 'delete_file', 'rename_file', 'copy_file', 'move_file',
    'get_file_info', 'set_file_info', 'list_directory', 'file_exists',
    'create_directory', 'delete_directory', 'is_directory',
    'read_entire_file', 'write_entire_file', 'append_to_file'
]

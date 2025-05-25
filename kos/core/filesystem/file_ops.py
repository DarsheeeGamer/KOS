"""
KOS Filesystem Operations

This module provides file operation functions for the KOS filesystem,
offering a unified API for working with files and directories.
"""

import os
import logging
import threading
from typing import Dict, List, Any, Optional, Tuple, Set, Callable, Union, BinaryIO

from .fs_types import FileSystemType, FileType, FileMode, FileInfo, FilesystemError
from .fs_types import FileNotFoundError, PermissionError, FileExistsError
from .fs_types import NotADirectoryError, IsADirectoryError
from .path_utils import normalize_path, resolve_path, join_path, split_path
from .path_utils import is_absolute_path, get_absolute_path
from .fs_manager import _find_filesystem_for_path

# Set up logging
logger = logging.getLogger('KOS.core.filesystem.file_ops')

# Global state
_file_state = {
    'open_files': {},   # file_handle -> file_info
    'next_handle': 1,
    'callbacks': {}     # event -> callbacks
}

# Locks
_file_lock = threading.RLock()


def open_file(path: str, mode: str = 'r', cwd: str = None) -> int:
    """
    Open a file
    
    Args:
        path: File path
        mode: File mode ('r', 'w', 'a', 'r+', 'w+', 'a+', with optional 'b')
        cwd: Current working directory (for relative paths)
    
    Returns:
        File handle
    
    Raises:
        FileNotFoundError: If the file does not exist and mode is 'r'
        PermissionError: If the file cannot be accessed with the requested mode
        IsADirectoryError: If the path points to a directory
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Open the file on the filesystem
        fs_handle = fs.open_file(rel_path, mode)
        
        # Create a file handle
        with _file_lock:
            handle = _file_state['next_handle']
            _file_state['next_handle'] += 1
            
            _file_state['open_files'][handle] = {
                'fs': fs,
                'fs_handle': fs_handle,
                'path': path,
                'mode': mode
            }
        
        return handle
    
    except Exception as e:
        logger.error(f"Error opening file {path}: {e}")
        raise


def close_file(file_handle: int) -> bool:
    """
    Close a file
    
    Args:
        file_handle: File handle
    
    Returns:
        Success status
    """
    with _file_lock:
        if file_handle not in _file_state['open_files']:
            logger.warning(f"Invalid file handle: {file_handle}")
            return False
        
        file_info = _file_state['open_files'][file_handle]
        fs = file_info['fs']
        fs_handle = file_info['fs_handle']
        
        try:
            # Close the file on the filesystem
            result = fs.close_file(fs_handle)
            
            # Remove the file handle
            del _file_state['open_files'][file_handle]
            
            return result
        
        except Exception as e:
            logger.error(f"Error closing file handle {file_handle}: {e}")
            return False


def read_file(file_handle: int, size: int = -1) -> bytes:
    """
    Read from a file
    
    Args:
        file_handle: File handle
        size: Number of bytes to read (-1 for all remaining)
    
    Returns:
        Data read
    
    Raises:
        ValueError: If the file handle is invalid
        IOError: If the file is not opened for reading
    """
    with _file_lock:
        if file_handle not in _file_state['open_files']:
            raise ValueError(f"Invalid file handle: {file_handle}")
        
        file_info = _file_state['open_files'][file_handle]
        fs = file_info['fs']
        fs_handle = file_info['fs_handle']
    
    try:
        # Read from the file on the filesystem
        return fs.read_file(fs_handle, size)
    
    except Exception as e:
        logger.error(f"Error reading from file handle {file_handle}: {e}")
        raise


def write_file(file_handle: int, data: bytes) -> int:
    """
    Write to a file
    
    Args:
        file_handle: File handle
        data: Data to write
    
    Returns:
        Number of bytes written
    
    Raises:
        ValueError: If the file handle is invalid
        IOError: If the file is not opened for writing
    """
    with _file_lock:
        if file_handle not in _file_state['open_files']:
            raise ValueError(f"Invalid file handle: {file_handle}")
        
        file_info = _file_state['open_files'][file_handle]
        fs = file_info['fs']
        fs_handle = file_info['fs_handle']
    
    try:
        # Write to the file on the filesystem
        return fs.write_file(fs_handle, data)
    
    except Exception as e:
        logger.error(f"Error writing to file handle {file_handle}: {e}")
        raise


def seek_file(file_handle: int, offset: int, whence: int = 0) -> int:
    """
    Seek within a file
    
    Args:
        file_handle: File handle
        offset: Byte offset
        whence: Reference position (0=start, 1=current, 2=end)
    
    Returns:
        New file position
    
    Raises:
        ValueError: If the file handle is invalid
    """
    with _file_lock:
        if file_handle not in _file_state['open_files']:
            raise ValueError(f"Invalid file handle: {file_handle}")
        
        file_info = _file_state['open_files'][file_handle]
        fs = file_info['fs']
        fs_handle = file_info['fs_handle']
    
    try:
        # Seek within the file on the filesystem
        return fs.seek_file(fs_handle, offset, whence)
    
    except Exception as e:
        logger.error(f"Error seeking in file handle {file_handle}: {e}")
        raise


def flush_file(file_handle: int) -> bool:
    """
    Flush file buffers
    
    Args:
        file_handle: File handle
    
    Returns:
        Success status
    
    Raises:
        ValueError: If the file handle is invalid
    """
    with _file_lock:
        if file_handle not in _file_state['open_files']:
            raise ValueError(f"Invalid file handle: {file_handle}")
        
        file_info = _file_state['open_files'][file_handle]
        fs = file_info['fs']
        fs_handle = file_info['fs_handle']
    
    try:
        # Flush the file on the filesystem
        return fs.flush_file(fs_handle)
    
    except Exception as e:
        logger.error(f"Error flushing file handle {file_handle}: {e}")
        raise


def create_file(path: str, cwd: str = None) -> bool:
    """
    Create a new file
    
    Args:
        path: File path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileExistsError: If the file already exists
        PermissionError: If the file cannot be created
        NotADirectoryError: If a component of the path is not a directory
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Create the file on the filesystem
        return fs.create_file(rel_path)
    
    except Exception as e:
        logger.error(f"Error creating file {path}: {e}")
        raise


def delete_file(path: str, cwd: str = None) -> bool:
    """
    Delete a file
    
    Args:
        path: File path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be deleted
        IsADirectoryError: If the path points to a directory
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Delete the file on the filesystem
        return fs.delete_file(rel_path)
    
    except Exception as e:
        logger.error(f"Error deleting file {path}: {e}")
        raise


def rename_file(old_path: str, new_path: str, cwd: str = None) -> bool:
    """
    Rename a file
    
    Args:
        old_path: Old file path
        new_path: New file path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the source file does not exist
        FileExistsError: If the destination file already exists
        PermissionError: If the file cannot be renamed
    """
    # Resolve paths
    if not is_absolute_path(old_path):
        if cwd is None:
            cwd = '/'
        old_path = resolve_path(cwd, old_path)
    
    if not is_absolute_path(new_path):
        if cwd is None:
            cwd = '/'
        new_path = resolve_path(cwd, new_path)
    
    # Check if the paths are on the same filesystem
    old_fs, old_rel_path = _find_filesystem_for_path(old_path)
    new_fs, new_rel_path = _find_filesystem_for_path(new_path)
    
    if old_fs != new_fs:
        # Cross-filesystem rename requires copy and delete
        return copy_file(old_path, new_path, cwd) and delete_file(old_path, cwd)
    
    try:
        # Rename the file on the filesystem
        return old_fs.rename_file(old_rel_path, new_rel_path)
    
    except Exception as e:
        logger.error(f"Error renaming file {old_path} to {new_path}: {e}")
        raise


def copy_file(src_path: str, dst_path: str, cwd: str = None) -> bool:
    """
    Copy a file
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the source file does not exist
        FileExistsError: If the destination file already exists
        PermissionError: If the file cannot be copied
    """
    # Resolve paths
    if not is_absolute_path(src_path):
        if cwd is None:
            cwd = '/'
        src_path = resolve_path(cwd, src_path)
    
    if not is_absolute_path(dst_path):
        if cwd is None:
            cwd = '/'
        dst_path = resolve_path(cwd, dst_path)
    
    try:
        # Open source file
        src_handle = open_file(src_path, 'rb', cwd)
        
        try:
            # Create destination file
            create_file(dst_path, cwd)
            
            # Open destination file
            dst_handle = open_file(dst_path, 'wb', cwd)
            
            try:
                # Copy data in chunks
                while True:
                    data = read_file(src_handle, 4096)
                    if not data:
                        break
                    write_file(dst_handle, data)
                
                return True
            
            finally:
                close_file(dst_handle)
        
        finally:
            close_file(src_handle)
    
    except Exception as e:
        logger.error(f"Error copying file {src_path} to {dst_path}: {e}")
        raise


def move_file(src_path: str, dst_path: str, cwd: str = None) -> bool:
    """
    Move a file
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the source file does not exist
        FileExistsError: If the destination file already exists
        PermissionError: If the file cannot be moved
    """
    return rename_file(src_path, dst_path, cwd)


def get_file_info(path: str, cwd: str = None) -> FileInfo:
    """
    Get file information
    
    Args:
        path: File path
        cwd: Current working directory (for relative paths)
    
    Returns:
        File information
    
    Raises:
        FileNotFoundError: If the file does not exist
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Get file info from the filesystem
        return fs.get_file_info(rel_path)
    
    except Exception as e:
        logger.error(f"Error getting file info for {path}: {e}")
        raise


def set_file_info(path: str, info: Dict[str, Any], cwd: str = None) -> bool:
    """
    Set file information
    
    Args:
        path: File path
        info: File information to set
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file information cannot be set
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Set file info on the filesystem
        return fs.set_file_info(rel_path, info)
    
    except Exception as e:
        logger.error(f"Error setting file info for {path}: {e}")
        raise


def list_directory(path: str, cwd: str = None) -> List[FileInfo]:
    """
    List directory contents
    
    Args:
        path: Directory path
        cwd: Current working directory (for relative paths)
    
    Returns:
        List of file information
    
    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path is not a directory
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # List directory on the filesystem
        return fs.list_directory(rel_path)
    
    except Exception as e:
        logger.error(f"Error listing directory {path}: {e}")
        raise


def create_directory(path: str, cwd: str = None) -> bool:
    """
    Create a directory
    
    Args:
        path: Directory path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileExistsError: If the directory already exists
        PermissionError: If the directory cannot be created
        NotADirectoryError: If a component of the path is not a directory
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Create directory on the filesystem
        return fs.create_directory(rel_path)
    
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        raise


def delete_directory(path: str, cwd: str = None) -> bool:
    """
    Delete a directory
    
    Args:
        path: Directory path
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        FileNotFoundError: If the directory does not exist
        NotADirectoryError: If the path is not a directory
        PermissionError: If the directory cannot be deleted
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    # Find the filesystem for this path
    fs, rel_path = _find_filesystem_for_path(path)
    
    try:
        # Delete directory on the filesystem
        return fs.delete_directory(rel_path)
    
    except Exception as e:
        logger.error(f"Error deleting directory {path}: {e}")
        raise


def file_exists(path: str, cwd: str = None) -> bool:
    """
    Check if a file exists
    
    Args:
        path: File path
        cwd: Current working directory (for relative paths)
    
    Returns:
        True if the file exists, False otherwise
    """
    # Resolve path
    if not is_absolute_path(path):
        if cwd is None:
            cwd = '/'
        path = resolve_path(cwd, path)
    
    try:
        # Find the filesystem for this path
        fs, rel_path = _find_filesystem_for_path(path)
        
        # Check if the file exists
        return fs.file_exists(rel_path)
    
    except Exception:
        return False


def is_directory(path: str, cwd: str = None) -> bool:
    """
    Check if a path is a directory
    
    Args:
        path: Path to check
        cwd: Current working directory (for relative paths)
    
    Returns:
        True if the path is a directory, False otherwise
    """
    try:
        # Get file info
        info = get_file_info(path, cwd)
        
        # Check if it's a directory
        return info.type == FileType.DIRECTORY
    
    except Exception:
        return False


def read_entire_file(path: str, cwd: str = None) -> bytes:
    """
    Read the entire contents of a file
    
    Args:
        path: File path
        cwd: Current working directory (for relative paths)
    
    Returns:
        File contents
    
    Raises:
        FileNotFoundError: If the file does not exist
        PermissionError: If the file cannot be read
    """
    # Open the file
    handle = open_file(path, 'rb', cwd)
    
    try:
        # Read the entire file
        return read_file(handle)
    
    finally:
        # Close the file
        close_file(handle)


def write_entire_file(path: str, data: bytes, cwd: str = None) -> bool:
    """
    Write data to a file, creating or overwriting it
    
    Args:
        path: File path
        data: Data to write
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        PermissionError: If the file cannot be written
    """
    # Open the file
    handle = open_file(path, 'wb', cwd)
    
    try:
        # Write the data
        bytes_written = write_file(handle, data)
        
        # Check if all data was written
        return bytes_written == len(data)
    
    finally:
        # Close the file
        close_file(handle)


def append_to_file(path: str, data: bytes, cwd: str = None) -> bool:
    """
    Append data to a file
    
    Args:
        path: File path
        data: Data to append
        cwd: Current working directory (for relative paths)
    
    Returns:
        Success status
    
    Raises:
        PermissionError: If the file cannot be written
    """
    # Open the file
    handle = open_file(path, 'ab', cwd)
    
    try:
        # Write the data
        bytes_written = write_file(handle, data)
        
        # Check if all data was written
        return bytes_written == len(data)
    
    finally:
        # Close the file
        close_file(handle)

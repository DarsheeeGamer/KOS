"""
KOS Filesystem System Calls

This module provides system calls for filesystem operations, including file and
directory manipulation, file I/O, and filesystem management.
"""

import logging
import os
from typing import Dict, List, Any, Optional, Union, BinaryIO

from . import syscall, SyscallCategory, SyscallResult, SyscallError
from .. import filesystem
from ..filesystem import FileSystemType, FileType, FileInfo

logger = logging.getLogger('KOS.syscall.filesystem')

@syscall(SyscallCategory.FILESYSTEM)
def mount_filesystem(fs_type: FileSystemType, mount_point: str, 
                    name: str = None, config: Dict = None) -> bool:
    """
    Mount a filesystem
    
    Args:
        fs_type: Filesystem type
        mount_point: Mount point path
        name: Filesystem name
        config: Filesystem configuration
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not mount_point:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Mount point cannot be empty")
        
        # Check if mount point already exists
        if mount_point in filesystem.get_mounted_filesystems():
            return SyscallResult(False, SyscallError.ALREADY_EXISTS, 
                               message=f"Mount point {mount_point} already in use")
        
        # Mount the filesystem
        result = filesystem.mount(fs_type, mount_point, name, config)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to mount {fs_type.name} at {mount_point}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error mounting filesystem: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def unmount_filesystem(mount_point: str) -> bool:
    """
    Unmount a filesystem
    
    Args:
        mount_point: Mount point path
    
    Returns:
        Success status or error
    """
    try:
        # Check if mount point exists
        if mount_point not in filesystem.get_mounted_filesystems():
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"No filesystem mounted at {mount_point}")
        
        # Unmount the filesystem
        result = filesystem.unmount(mount_point)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to unmount filesystem at {mount_point}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error unmounting filesystem: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def get_mounted_filesystems() -> Dict[str, Dict[str, Any]]:
    """
    Get information about mounted filesystems
    
    Returns:
        Dictionary of mounted filesystem information indexed by mount point or error
    """
    try:
        # Get mounted filesystems
        mounted_fs = filesystem.get_mounted_filesystems()
        return mounted_fs
    
    except Exception as e:
        logger.error(f"Error getting mounted filesystems: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def create_file(path: str, cwd: str = None) -> bool:
    """
    Create a new empty file
    
    Args:
        path: Path to the file
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="File path cannot be empty")
        
        # Check if file already exists
        try:
            if filesystem.file_exists(path, cwd):
                return SyscallResult(False, SyscallError.ALREADY_EXISTS, 
                                   message=f"File {path} already exists")
        except Exception:
            # If file_exists fails, continue and let create_file handle it
            pass
        
        # Create the file
        result = filesystem.create_file(path, cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to create file {path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating file {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def delete_file(path: str, cwd: str = None) -> bool:
    """
    Delete a file
    
    Args:
        path: Path to the file
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="File path cannot be empty")
        
        # Check if file exists
        if not filesystem.file_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"File {path} not found")
        
        # Delete the file
        result = filesystem.delete_file(path, cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to delete file {path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting file {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def create_directory(path: str, cwd: str = None) -> bool:
    """
    Create a directory
    
    Args:
        path: Path to the directory
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Directory path cannot be empty")
        
        # Create the directory
        result = filesystem.create_directory(path, cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to create directory {path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating directory {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def delete_directory(path: str, recursive: bool = False, cwd: str = None) -> bool:
    """
    Delete a directory
    
    Args:
        path: Path to the directory
        recursive: Whether to recursively delete subdirectories and files
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Directory path cannot be empty")
        
        # Check if directory exists
        if not filesystem.directory_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Directory {path} not found")
        
        # Delete the directory
        result = filesystem.delete_directory(path, recursive, cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to delete directory {path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting directory {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def list_directory(path: str, cwd: str = None) -> List[FileInfo]:
    """
    List the contents of a directory
    
    Args:
        path: Path to the directory
        cwd: Current working directory
    
    Returns:
        List of FileInfo objects or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Directory path cannot be empty")
        
        # Check if directory exists
        if not filesystem.directory_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Directory {path} not found")
        
        # List the directory
        contents = filesystem.list_directory(path, cwd)
        
        if contents is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to list directory {path}")
        
        return contents
    
    except Exception as e:
        logger.error(f"Error listing directory {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def get_file_info(path: str, cwd: str = None) -> FileInfo:
    """
    Get information about a file or directory
    
    Args:
        path: Path to the file or directory
        cwd: Current working directory
    
    Returns:
        FileInfo object or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Path cannot be empty")
        
        # Check if file exists
        if not filesystem.file_exists(path, cwd) and not filesystem.directory_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"File or directory {path} not found")
        
        # Get file info
        info = filesystem.get_file_info(path, cwd)
        
        if info is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to get information for {path}")
        
        return info
    
    except Exception as e:
        logger.error(f"Error getting information for {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def read_file(path: str, offset: int = 0, size: int = -1, cwd: str = None) -> bytes:
    """
    Read data from a file
    
    Args:
        path: Path to the file
        offset: Offset in the file
        size: Number of bytes to read (-1 for all)
        cwd: Current working directory
    
    Returns:
        File data or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="File path cannot be empty")
        
        if offset < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Offset cannot be negative")
        
        # Check if file exists
        if not filesystem.file_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"File {path} not found")
        
        # Read the file
        if size == -1:
            data = filesystem.read_entire_file(path, cwd)
        else:
            file_handle = filesystem.open_file(path, 'rb', cwd)
            if file_handle < 0:
                return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                                   message=f"Failed to open file {path}")
            
            try:
                filesystem.seek_file(file_handle, offset)
                data = filesystem.read_file(file_handle, size)
            finally:
                filesystem.close_file(file_handle)
        
        if data is None:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to read file {path}")
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def write_file(path: str, data: bytes, offset: int = 0, cwd: str = None) -> bool:
    """
    Write data to a file
    
    Args:
        path: Path to the file
        data: Data to write
        offset: Offset in the file
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="File path cannot be empty")
        
        if offset < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Offset cannot be negative")
        
        # Create file if it doesn't exist
        if not filesystem.file_exists(path, cwd):
            create_result = filesystem.create_file(path, cwd)
            if not create_result:
                return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                                   message=f"Failed to create file {path}")
        
        # Write to the file
        if offset == 0 and offset + len(data) == filesystem.get_file_size(path, cwd):
            # Can use write_entire_file for a complete overwrite
            result = filesystem.write_entire_file(path, data, cwd)
        else:
            # Open, seek, write, close
            file_handle = filesystem.open_file(path, 'wb', cwd)
            if file_handle < 0:
                return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                                   message=f"Failed to open file {path}")
            
            try:
                if offset > 0:
                    filesystem.seek_file(file_handle, offset)
                
                bytes_written = filesystem.write_file(file_handle, data)
                result = bytes_written == len(data)
            finally:
                filesystem.close_file(file_handle)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to write to file {path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error writing to file {path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def copy_file(src_path: str, dst_path: str, src_cwd: str = None, dst_cwd: str = None) -> bool:
    """
    Copy a file
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        src_cwd: Source current working directory
        dst_cwd: Destination current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not src_path or not dst_path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Source and destination paths cannot be empty")
        
        # Check if source file exists
        if not filesystem.file_exists(src_path, src_cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Source file {src_path} not found")
        
        # Copy the file
        result = filesystem.copy_file(src_path, dst_path, src_cwd, dst_cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to copy file from {src_path} to {dst_path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error copying file from {src_path} to {dst_path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def move_file(src_path: str, dst_path: str, src_cwd: str = None, dst_cwd: str = None) -> bool:
    """
    Move a file
    
    Args:
        src_path: Source file path
        dst_path: Destination file path
        src_cwd: Source current working directory
        dst_cwd: Destination current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not src_path or not dst_path:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Source and destination paths cannot be empty")
        
        # Check if source file exists
        if not filesystem.file_exists(src_path, src_cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Source file {src_path} not found")
        
        # Move the file
        result = filesystem.move_file(src_path, dst_path, src_cwd, dst_cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to move file from {src_path} to {dst_path}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error moving file from {src_path} to {dst_path}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.FILESYSTEM)
def rename(path: str, new_name: str, cwd: str = None) -> bool:
    """
    Rename a file or directory
    
    Args:
        path: Path to the file or directory
        new_name: New name (not full path)
        cwd: Current working directory
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not path or not new_name:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Path and new name cannot be empty")
        
        # Check if file or directory exists
        if not filesystem.file_exists(path, cwd) and not filesystem.directory_exists(path, cwd):
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"File or directory {path} not found")
        
        # Get directory and base name of the path
        parent_dir = filesystem.path_utils.get_parent_dir(path)
        
        # Create the new path
        if parent_dir:
            new_path = filesystem.path_utils.join_path(parent_dir, new_name)
        else:
            new_path = new_name
        
        # Rename (move) the file or directory
        if filesystem.file_exists(path, cwd):
            result = filesystem.move_file(path, new_path, cwd, cwd)
        else:  # Directory
            result = filesystem.move_directory(path, new_path, cwd, cwd)
        
        if not result:
            return SyscallResult(False, SyscallError.INTERNAL_ERROR, 
                               message=f"Failed to rename {path} to {new_name}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error renaming {path} to {new_name}: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

"""
FileSystemInterface Component for KLayer

This module provides file system access capabilities for KOS applications,
allowing them to interact with the KOS file system in a controlled manner.
"""

import os
import sys
import shutil
import logging
import threading
import json
from typing import Dict, List, Any, Optional, Union, BinaryIO, TextIO

logger = logging.getLogger('KOS.layer.file_system')

class FileSystemInterface:
    """
    Provides controlled file system access for KOS applications
    
    This class provides methods for applications to interact with the
    KOS file system while enforcing permissions and sandboxing.
    """
    
    def __init__(self):
        """Initialize the FileSystemInterface component"""
        self.lock = threading.RLock()
        
        # Load configuration
        self.kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
        self.app_data_dir = os.path.join(self.kos_home, 'app_data')
        self.shared_data_dir = os.path.join(self.kos_home, 'shared')
        
        # Ensure directories exist
        os.makedirs(self.app_data_dir, exist_ok=True)
        os.makedirs(self.shared_data_dir, exist_ok=True)
        
        logger.debug("FileSystemInterface component initialized")
    
    def _get_app_data_path(self, app_id: str) -> str:
        """
        Get application data directory path
        
        Args:
            app_id: Application ID
            
        Returns:
            Path to application data directory
        """
        app_dir = os.path.join(self.app_data_dir, app_id)
        os.makedirs(app_dir, exist_ok=True)
        return app_dir
    
    def _validate_path(self, app_id: str, path: str, for_write: bool = False) -> Dict[str, Any]:
        """
        Validate and resolve a file path
        
        Args:
            app_id: Application ID
            path: File path
            for_write: Whether the path is for write access
            
        Returns:
            Dictionary with validation result
        """
        # Check if path is absolute or relative
        if os.path.isabs(path):
            # Check if path is within allowed directories
            if path.startswith(self._get_app_data_path(app_id)):
                # Path is in app's data directory
                return {
                    "valid": True,
                    "resolved_path": path,
                    "access": "private"
                }
            elif path.startswith(self.shared_data_dir):
                # Path is in shared data directory
                # Check permissions for write access to shared data
                if for_write:
                    # Get permissions manager
                    from kos.layer import klayer
                    permissions = klayer.get_permissions()
                    
                    if permissions and not permissions.check_permission(app_id, "shared_data.write"):
                        return {
                            "valid": False,
                            "error": "Permission denied: App does not have write access to shared data"
                        }
                
                return {
                    "valid": True,
                    "resolved_path": path,
                    "access": "shared"
                }
            else:
                # Path is outside of allowed directories
                
                # Get permissions manager to check for unrestricted file access
                from kos.layer import klayer
                permissions = klayer.get_permissions()
                
                if permissions and permissions.check_permission(app_id, "file.unrestricted"):
                    # App has unrestricted file access
                    return {
                        "valid": True,
                        "resolved_path": path,
                        "access": "unrestricted"
                    }
                
                return {
                    "valid": False,
                    "error": "Permission denied: Path outside of allowed directories"
                }
        else:
            # Relative path, resolve relative to app's data directory
            resolved_path = os.path.join(self._get_app_data_path(app_id), path)
            
            return {
                "valid": True,
                "resolved_path": resolved_path,
                "access": "private"
            }
    
    def read_file(self, app_id: str, path: str, binary: bool = False) -> Dict[str, Any]:
        """
        Read a file
        
        Args:
            app_id: Application ID
            path: File path
            binary: Whether to read in binary mode
            
        Returns:
            Dictionary with file content
        """
        # Validate path
        validation = self._validate_path(app_id, path)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Check if file exists
            if not os.path.exists(resolved_path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Check if path is a file
            if not os.path.isfile(resolved_path):
                return {
                    "success": False,
                    "error": f"Path is not a file: {path}"
                }
            
            # Read file
            mode = "rb" if binary else "r"
            with open(resolved_path, mode) as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "size": len(content),
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def write_file(self, app_id: str, path: str, content: Union[str, bytes], binary: bool = False) -> Dict[str, Any]:
        """
        Write to a file
        
        Args:
            app_id: Application ID
            path: File path
            content: File content
            binary: Whether to write in binary mode
            
        Returns:
            Dictionary with write status
        """
        # Validate path
        validation = self._validate_path(app_id, path, for_write=True)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
            
            # Write file
            mode = "wb" if binary else "w"
            with open(resolved_path, mode) as f:
                f.write(content)
            
            return {
                "success": True,
                "size": len(content),
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def append_file(self, app_id: str, path: str, content: Union[str, bytes], binary: bool = False) -> Dict[str, Any]:
        """
        Append to a file
        
        Args:
            app_id: Application ID
            path: File path
            content: Content to append
            binary: Whether to append in binary mode
            
        Returns:
            Dictionary with append status
        """
        # Validate path
        validation = self._validate_path(app_id, path, for_write=True)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
            
            # Append to file
            mode = "ab" if binary else "a"
            with open(resolved_path, mode) as f:
                f.write(content)
            
            return {
                "success": True,
                "size": len(content),
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error appending to file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_file(self, app_id: str, path: str) -> Dict[str, Any]:
        """
        Delete a file
        
        Args:
            app_id: Application ID
            path: File path
            
        Returns:
            Dictionary with delete status
        """
        # Validate path
        validation = self._validate_path(app_id, path, for_write=True)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Check if file exists
            if not os.path.exists(resolved_path):
                return {
                    "success": False,
                    "error": f"File not found: {path}"
                }
            
            # Check if path is a file
            if not os.path.isfile(resolved_path):
                return {
                    "success": False,
                    "error": f"Path is not a file: {path}"
                }
            
            # Delete file
            os.remove(resolved_path)
            
            return {
                "success": True,
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_directory(self, app_id: str, path: str) -> Dict[str, Any]:
        """
        List directory contents
        
        Args:
            app_id: Application ID
            path: Directory path
            
        Returns:
            Dictionary with directory contents
        """
        # Validate path
        validation = self._validate_path(app_id, path)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Check if directory exists
            if not os.path.exists(resolved_path):
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }
            
            # Check if path is a directory
            if not os.path.isdir(resolved_path):
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}"
                }
            
            # List directory contents
            contents = []
            
            for item in os.listdir(resolved_path):
                item_path = os.path.join(resolved_path, item)
                
                contents.append({
                    "name": item,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None,
                    "modified": os.path.getmtime(item_path)
                })
            
            return {
                "success": True,
                "contents": contents,
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error listing directory: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_directory(self, app_id: str, path: str) -> Dict[str, Any]:
        """
        Create a directory
        
        Args:
            app_id: Application ID
            path: Directory path
            
        Returns:
            Dictionary with create status
        """
        # Validate path
        validation = self._validate_path(app_id, path, for_write=True)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Create directory
            os.makedirs(resolved_path, exist_ok=True)
            
            return {
                "success": True,
                "path": path,
                "access": validation["access"]
            }
        except Exception as e:
            logger.error(f"Error creating directory: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def delete_directory(self, app_id: str, path: str, recursive: bool = False) -> Dict[str, Any]:
        """
        Delete a directory
        
        Args:
            app_id: Application ID
            path: Directory path
            recursive: Whether to delete recursively
            
        Returns:
            Dictionary with delete status
        """
        # Validate path
        validation = self._validate_path(app_id, path, for_write=True)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Check if directory exists
            if not os.path.exists(resolved_path):
                return {
                    "success": False,
                    "error": f"Directory not found: {path}"
                }
            
            # Check if path is a directory
            if not os.path.isdir(resolved_path):
                return {
                    "success": False,
                    "error": f"Path is not a directory: {path}"
                }
            
            # Delete directory
            if recursive:
                shutil.rmtree(resolved_path)
            else:
                os.rmdir(resolved_path)
            
            return {
                "success": True,
                "path": path,
                "access": validation["access"],
                "recursive": recursive
            }
        except OSError as e:
            if "Directory not empty" in str(e):
                return {
                    "success": False,
                    "error": f"Directory not empty: {path}. Use recursive=True to delete non-empty directories."
                }
            
            logger.error(f"Error deleting directory: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Error deleting directory: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_file_info(self, app_id: str, path: str) -> Dict[str, Any]:
        """
        Get file information
        
        Args:
            app_id: Application ID
            path: File path
            
        Returns:
            Dictionary with file information
        """
        # Validate path
        validation = self._validate_path(app_id, path)
        
        if not validation["valid"]:
            return {
                "success": False,
                "error": validation["error"]
            }
        
        resolved_path = validation["resolved_path"]
        
        try:
            # Check if path exists
            if not os.path.exists(resolved_path):
                return {
                    "success": False,
                    "error": f"Path not found: {path}"
                }
            
            # Get file information
            is_file = os.path.isfile(resolved_path)
            is_dir = os.path.isdir(resolved_path)
            
            info = {
                "name": os.path.basename(resolved_path),
                "path": path,
                "type": "file" if is_file else "directory" if is_dir else "unknown",
                "size": os.path.getsize(resolved_path) if is_file else None,
                "created": os.path.getctime(resolved_path),
                "modified": os.path.getmtime(resolved_path),
                "accessed": os.path.getatime(resolved_path),
                "access": validation["access"]
            }
            
            return {
                "success": True,
                "info": info
            }
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def copy_file(self, app_id: str, source_path: str, target_path: str) -> Dict[str, Any]:
        """
        Copy a file
        
        Args:
            app_id: Application ID
            source_path: Source file path
            target_path: Target file path
            
        Returns:
            Dictionary with copy status
        """
        # Validate source path
        source_validation = self._validate_path(app_id, source_path)
        
        if not source_validation["valid"]:
            return {
                "success": False,
                "error": f"Source: {source_validation['error']}"
            }
        
        # Validate target path
        target_validation = self._validate_path(app_id, target_path, for_write=True)
        
        if not target_validation["valid"]:
            return {
                "success": False,
                "error": f"Target: {target_validation['error']}"
            }
        
        resolved_source = source_validation["resolved_path"]
        resolved_target = target_validation["resolved_path"]
        
        try:
            # Check if source exists
            if not os.path.exists(resolved_source):
                return {
                    "success": False,
                    "error": f"Source file not found: {source_path}"
                }
            
            # Check if source is a file
            if not os.path.isfile(resolved_source):
                return {
                    "success": False,
                    "error": f"Source path is not a file: {source_path}"
                }
            
            # Create target parent directory if it doesn't exist
            os.makedirs(os.path.dirname(resolved_target), exist_ok=True)
            
            # Copy file
            shutil.copy2(resolved_source, resolved_target)
            
            return {
                "success": True,
                "source_path": source_path,
                "target_path": target_path,
                "source_access": source_validation["access"],
                "target_access": target_validation["access"]
            }
        except Exception as e:
            logger.error(f"Error copying file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def move_file(self, app_id: str, source_path: str, target_path: str) -> Dict[str, Any]:
        """
        Move a file
        
        Args:
            app_id: Application ID
            source_path: Source file path
            target_path: Target file path
            
        Returns:
            Dictionary with move status
        """
        # Validate source path
        source_validation = self._validate_path(app_id, source_path, for_write=True)
        
        if not source_validation["valid"]:
            return {
                "success": False,
                "error": f"Source: {source_validation['error']}"
            }
        
        # Validate target path
        target_validation = self._validate_path(app_id, target_path, for_write=True)
        
        if not target_validation["valid"]:
            return {
                "success": False,
                "error": f"Target: {target_validation['error']}"
            }
        
        resolved_source = source_validation["resolved_path"]
        resolved_target = target_validation["resolved_path"]
        
        try:
            # Check if source exists
            if not os.path.exists(resolved_source):
                return {
                    "success": False,
                    "error": f"Source file not found: {source_path}"
                }
            
            # Check if source is a file
            if not os.path.isfile(resolved_source):
                return {
                    "success": False,
                    "error": f"Source path is not a file: {source_path}"
                }
            
            # Create target parent directory if it doesn't exist
            os.makedirs(os.path.dirname(resolved_target), exist_ok=True)
            
            # Move file
            shutil.move(resolved_source, resolved_target)
            
            return {
                "success": True,
                "source_path": source_path,
                "target_path": target_path,
                "source_access": source_validation["access"],
                "target_access": target_validation["access"]
            }
        except Exception as e:
            logger.error(f"Error moving file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_app_data_dir(self, app_id: str) -> Dict[str, Any]:
        """
        Get application data directory
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with app data directory
        """
        app_data_dir = self._get_app_data_path(app_id)
        
        return {
            "success": True,
            "app_data_dir": app_data_dir
        }
    
    def get_shared_data_dir(self) -> Dict[str, Any]:
        """
        Get shared data directory
        
        Returns:
            Dictionary with shared data directory
        """
        return {
            "success": True,
            "shared_data_dir": self.shared_data_dir
        }

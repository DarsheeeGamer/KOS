"""
FileSystemInterface Component for KLayer

This module provides file system access capabilities for KOS applications,
allowing them to interact with the KOS VFS in a controlled manner.
All operations are performed on the KOS Virtual File System (kaede.kdsk).
"""

import os
import logging
import threading
from typing import Dict, List, Any, Optional, Union, BinaryIO

logger = logging.getLogger('KOS.layer.file_system')

class FileSystemInterface:
    """
    Provides controlled VFS access for KOS applications
    
    This class wraps KaedeVFS to provide file system operations
    entirely within the KOS Virtual File System (kaede.kdsk).
    """
    
    def __init__(self):
        """Initialize the FileSystemInterface component"""
        self.lock = threading.RLock()
        
        # Get the KaedeVFS instance
        from kos.vfs import get_vfs
        self.vfs = get_vfs()
        
        if not self.vfs:
            raise RuntimeError("KaedeVFS not initialized")
        
        # VFS paths (all inside kaede.kdsk)
        self.app_data_dir = "/var/lib/kos/app_data"
        self.shared_data_dir = "/var/lib/kos/shared"
        
        # Ensure VFS directories exist
        self._ensure_vfs_dirs()
        
        logger.debug("FileSystemInterface component initialized with KaedeVFS")
    
    def _ensure_vfs_dirs(self):
        """Ensure required VFS directories exist"""
        dirs = [
            "/var",
            "/var/lib",
            "/var/lib/kos",
            self.app_data_dir,
            self.shared_data_dir
        ]
        
        for dir_path in dirs:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path, 0o755)
                except FileExistsError:
                    pass
    
    def _get_app_data_path(self, app_id: str) -> str:
        """
        Get application data directory path in VFS
        
        Args:
            app_id: Application ID
            
        Returns:
            VFS path to application data directory
        """
        return os.path.join(self.app_data_dir, app_id)
    
    def create_app_data_dir(self, app_id: str) -> bool:
        """
        Create application data directory in VFS
        
        Args:
            app_id: Application ID
            
        Returns:
            True if successful
        """
        with self.lock:
            try:
                app_dir = self._get_app_data_path(app_id)
                if not self.vfs.exists(app_dir):
                    self.vfs.mkdir(app_dir, 0o755)
                    logger.info(f"Created VFS app data directory: {app_dir}")
                return True
            except Exception as e:
                logger.error(f"Failed to create app data dir in VFS: {e}")
                return False
    
    def read_file(self, app_id: str, filepath: str) -> Optional[bytes]:
        """
        Read file from VFS
        
        Args:
            app_id: Application ID
            filepath: Relative file path
            
        Returns:
            File contents or None if error
        """
        with self.lock:
            try:
                # Construct VFS path
                if filepath.startswith('/'):
                    # Absolute VFS path
                    vfs_path = filepath
                else:
                    # Relative to app data dir
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, filepath)
                
                # Read from VFS
                with self.vfs.open(vfs_path, os.O_RDONLY) as f:
                    return f.read()
                    
            except FileNotFoundError:
                logger.debug(f"File not found in VFS: {vfs_path}")
                return None
            except Exception as e:
                logger.error(f"Error reading from VFS: {e}")
                return None
    
    def write_file(self, app_id: str, filepath: str, content: bytes) -> bool:
        """
        Write file to VFS
        
        Args:
            app_id: Application ID
            filepath: Relative file path
            content: File content
            
        Returns:
            True if successful
        """
        with self.lock:
            try:
                # Construct VFS path
                if filepath.startswith('/'):
                    vfs_path = filepath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, filepath)
                
                # Ensure parent directory exists
                parent_dir = os.path.dirname(vfs_path)
                if not self.vfs.exists(parent_dir):
                    self._create_dirs_recursive(parent_dir)
                
                # Write to VFS
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                with self.vfs.open(vfs_path, flags, 0o644) as f:
                    f.write(content)
                
                logger.debug(f"Wrote {len(content)} bytes to VFS: {vfs_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error writing to VFS: {e}")
                return False
    
    def _create_dirs_recursive(self, path: str):
        """Recursively create directories in VFS"""
        if not path or path == '/':
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current = f"/{part}" if not current else f"{current}/{part}"
            if not self.vfs.exists(current):
                try:
                    self.vfs.mkdir(current, 0o755)
                except FileExistsError:
                    pass
    
    def delete_file(self, app_id: str, filepath: str) -> bool:
        """
        Delete file from VFS
        
        Args:
            app_id: Application ID
            filepath: Relative file path
            
        Returns:
            True if successful
        """
        with self.lock:
            try:
                if filepath.startswith('/'):
                    vfs_path = filepath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, filepath)
                
                if self.vfs.exists(vfs_path):
                    self.vfs.unlink(vfs_path)
                    logger.debug(f"Deleted from VFS: {vfs_path}")
                    return True
                return False
                
            except Exception as e:
                logger.error(f"Error deleting from VFS: {e}")
                return False
    
    def list_directory(self, app_id: str, dirpath: str = '') -> Optional[List[str]]:
        """
        List directory contents in VFS
        
        Args:
            app_id: Application ID
            dirpath: Directory path
            
        Returns:
            List of filenames or None if error
        """
        with self.lock:
            try:
                if dirpath.startswith('/'):
                    vfs_path = dirpath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, dirpath) if dirpath else app_dir
                
                if self.vfs.exists(vfs_path):
                    entries = self.vfs.listdir(vfs_path)
                    # Filter out . and ..
                    return [e for e in entries if e not in ['.', '..']]
                return []
                
            except Exception as e:
                logger.error(f"Error listing VFS directory: {e}")
                return None
    
    def file_exists(self, app_id: str, filepath: str) -> bool:
        """
        Check if file exists in VFS
        
        Args:
            app_id: Application ID
            filepath: File path
            
        Returns:
            True if file exists
        """
        with self.lock:
            try:
                if filepath.startswith('/'):
                    vfs_path = filepath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, filepath)
                
                return self.vfs.exists(vfs_path)
                
            except Exception as e:
                logger.error(f"Error checking VFS file existence: {e}")
                return False
    
    def get_file_info(self, app_id: str, filepath: str) -> Optional[Dict[str, Any]]:
        """
        Get file information from VFS
        
        Args:
            app_id: Application ID
            filepath: File path
            
        Returns:
            File info dict or None if error
        """
        with self.lock:
            try:
                if filepath.startswith('/'):
                    vfs_path = filepath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, filepath)
                
                if self.vfs.exists(vfs_path):
                    stat = self.vfs.stat(vfs_path)
                    
                    return {
                        'path': vfs_path,
                        'size': stat.st_size,
                        'mode': stat.st_mode,
                        'uid': stat.st_uid,
                        'gid': stat.st_gid,
                        'atime': stat.st_atime,
                        'mtime': stat.st_mtime,
                        'ctime': stat.st_ctime,
                        'is_file': stat.st_mode & 0o100000 != 0,
                        'is_dir': stat.st_mode & 0o040000 != 0
                    }
                return None
                
            except Exception as e:
                logger.error(f"Error getting VFS file info: {e}")
                return None
    
    def create_directory(self, app_id: str, dirpath: str) -> bool:
        """
        Create directory in VFS
        
        Args:
            app_id: Application ID
            dirpath: Directory path
            
        Returns:
            True if successful
        """
        with self.lock:
            try:
                if dirpath.startswith('/'):
                    vfs_path = dirpath
                else:
                    app_dir = self._get_app_data_path(app_id)
                    vfs_path = os.path.join(app_dir, dirpath)
                
                self._create_dirs_recursive(vfs_path)
                return True
                
            except Exception as e:
                logger.error(f"Error creating VFS directory: {e}")
                return False
    
    def cleanup_app_data(self, app_id: str) -> bool:
        """
        Clean up application data from VFS
        
        Args:
            app_id: Application ID
            
        Returns:
            True if successful
        """
        with self.lock:
            try:
                app_dir = self._get_app_data_path(app_id)
                
                if self.vfs.exists(app_dir):
                    # Recursively delete app directory
                    self._delete_recursive(app_dir)
                    logger.info(f"Cleaned up VFS app data: {app_dir}")
                
                return True
                
            except Exception as e:
                logger.error(f"Error cleaning up VFS app data: {e}")
                return False
    
    def _delete_recursive(self, path: str):
        """Recursively delete directory from VFS"""
        try:
            # List directory contents
            entries = self.vfs.listdir(path)
            
            for entry in entries:
                if entry in ['.', '..']:
                    continue
                
                entry_path = os.path.join(path, entry)
                
                # Check if it's a directory
                stat = self.vfs.stat(entry_path)
                if stat.st_mode & 0o040000:  # S_IFDIR
                    # Recursive deletion
                    self._delete_recursive(entry_path)
                else:
                    # Delete file
                    self.vfs.unlink(entry_path)
            
            # Delete the directory itself
            self.vfs.rmdir(path)
            
        except Exception as e:
            logger.warning(f"Could not delete {path}: {e}")
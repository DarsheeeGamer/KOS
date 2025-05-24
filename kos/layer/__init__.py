"""
KLayer - KOS Application Layer

This module provides the interface between KOS applications and the KOS system,
enabling applications to control and manipulate KOS functionality.
"""

import os
import sys
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Callable

# Setup logging
logger = logging.getLogger('KOS.layer')

class KLayer:
    """
    Main class for the KOS Application Layer (KLayer)
    
    This class provides the interface between KOS applications and the KOS system,
    enabling applications to control and utilize KOS functionality.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls) -> 'KLayer':
        """Get singleton instance of KLayer"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """Initialize the KLayer"""
        # Initialize components
        self.app_manager = None
        self.package_manager = None
        self.file_system = None
        self.virtual_fs = None
        self.memory_manager = None
        self.shell = None
        self.permissions = None
        self.app_registry = None
        
        # Initialize immediately if possible
        self._init_components()
        
        logger.info("KLayer initialized")
    
    def _init_components(self):
        """Initialize KLayer components"""
        # Initialize components when needed
        try:
            from .app_manager import AppManager
            self.app_manager = AppManager()
        except ImportError:
            logger.warning("AppManager component not available")
        
        try:
            from .package_manager import PackageManager
            self.package_manager = PackageManager()
        except ImportError:
            logger.warning("PackageManager component not available")
        
        try:
            from .file_system import FileSystemInterface
            self.file_system = FileSystemInterface()
        except ImportError:
            logger.warning("FileSystemInterface component not available")
        
        try:
            from .virtual_fs import virtual_fs
            self.virtual_fs = virtual_fs
        except ImportError:
            logger.warning("Virtual FileSystem component not available")
        
        try:
            from .memory_manager import memory_manager
            self.memory_manager = memory_manager
        except ImportError:
            logger.warning("Memory Manager component not available")
        
        try:
            from .shell import ShellInterface
            self.shell = ShellInterface()
        except ImportError:
            logger.warning("ShellInterface component not available")
        
        try:
            from .permissions import PermissionsManager
            self.permissions = PermissionsManager()
        except ImportError:
            logger.warning("PermissionsManager component not available")
        
        try:
            from .app_registry import AppRegistry
            self.app_registry = AppRegistry()
        except ImportError:
            logger.warning("AppRegistry component not available")
    
    def get_app_manager(self) -> Any:
        """Get the AppManager component"""
        if not self.app_manager:
            try:
                from .app_manager import AppManager
                self.app_manager = AppManager()
            except ImportError:
                logger.error("AppManager component not available")
                return None
        return self.app_manager
    
    def get_package_manager(self) -> Any:
        """Get the PackageManager component"""
        if not self.package_manager:
            try:
                from .package_manager import PackageManager
                self.package_manager = PackageManager()
            except ImportError:
                logger.error("PackageManager component not available")
                return None
        return self.package_manager
    
    def get_file_system(self) -> Any:
        """Get the FileSystemInterface component"""
        if not self.file_system:
            try:
                from .file_system import FileSystemInterface
                self.file_system = FileSystemInterface()
            except ImportError:
                logger.error("FileSystemInterface component not available")
                return None
        return self.file_system
    
    def get_shell(self) -> Any:
        """Get the ShellInterface component"""
        if not self.shell:
            try:
                from .shell import ShellInterface
                self.shell = ShellInterface()
            except ImportError:
                logger.error("ShellInterface component not available")
                return None
        return self.shell
    
    def get_permissions(self) -> Any:
        """Get the PermissionsManager component"""
        if not self.permissions:
            try:
                from .permissions import PermissionsManager
                self.permissions = PermissionsManager()
            except ImportError:
                logger.error("PermissionsManager component not available")
                return None
        return self.permissions
    
    def get_app_registry(self) -> Any:
        """Get the AppRegistry component"""
        if not self.app_registry:
            try:
                from .app_registry import AppRegistry
                self.app_registry = AppRegistry()
            except ImportError:
                logger.error("AppRegistry component not available")
                return None
        return self.app_registry
    
    def get_virtual_fs(self) -> Any:
        """Get the Virtual FileSystem component"""
        if not self.virtual_fs:
            try:
                from .virtual_fs import virtual_fs
                self.virtual_fs = virtual_fs
            except ImportError:
                logger.error("Virtual FileSystem component not available")
                return None
        return self.virtual_fs
    
    def get_memory_manager(self) -> Any:
        """Get the Memory Manager component"""
        if not self.memory_manager:
            try:
                from .memory_manager import memory_manager
                self.memory_manager = memory_manager
            except ImportError:
                logger.error("Memory Manager component not available")
                return None
        return self.memory_manager
    
    def register_app(self, app_id: str, app_info: Dict[str, Any]) -> bool:
        """
        Register an application with KOS
        
        Args:
            app_id: Application ID
            app_info: Application information
            
        Returns:
            Success status
        """
        if self.app_registry:
            return self.app_registry.register_app(app_id, app_info)
        return False
    
    def execute_shell_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a shell command in KOS
        
        Args:
            command: Command to execute
            
        Returns:
            Dictionary with execution results
        """
        if self.shell:
            return self.shell.execute_command(command)
        return {"success": False, "error": "ShellInterface not available"}
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Install a package in KOS
        
        Args:
            package_name: Package name
            version: Package version
            
        Returns:
            Dictionary with installation results
        """
        if self.package_manager:
            return self.package_manager.install_package(package_name, version)
        return {"success": False, "error": "PackageManager not available"}
    
    def get_app_info(self, app_id: str) -> Dict[str, Any]:
        """
        Get information about an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with application information
        """
        if self.app_registry:
            return self.app_registry.get_app_info(app_id)
        return {"success": False, "error": "AppRegistry not available"}
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """
        Read a file from KOS file system
        
        Args:
            path: File path
            
        Returns:
            Dictionary with file content
        """
        if self.file_system:
            return self.file_system.read_file(path)
        return {"success": False, "error": "FileSystemInterface not available"}
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """
        Write to a file in KOS file system
        
        Args:
            path: File path
            content: File content
            
        Returns:
            Dictionary with write status
        """
        if self.file_system:
            return self.file_system.write_file(path, content)
        return {"success": False, "error": "FileSystemInterface not available"}
    
    def check_permission(self, app_id: str, permission: str) -> bool:
        """
        Check if an application has a permission
        
        Args:
            app_id: Application ID
            permission: Permission to check
            
        Returns:
            Whether the application has the permission
        """
        if self.permissions:
            return self.permissions.check_permission(app_id, permission)
        return False
    
    def request_permission(self, app_id: str, permission: str, reason: str) -> Dict[str, Any]:
        """
        Request a permission for an application
        
        Args:
            app_id: Application ID
            permission: Permission to request
            reason: Reason for requesting the permission
            
        Returns:
            Dictionary with request status
        """
        if self.permissions:
            return self.permissions.request_permission(app_id, permission, reason)
        return {"success": False, "error": "PermissionsManager not available"}

# Create default instance
try:
    klayer = KLayer.get_instance()
except Exception as e:
    logger.error(f"Failed to initialize KLayer: {e}")
    klayer = None

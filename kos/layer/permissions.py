"""
PermissionsManager Component for KLayer

This module provides permission management capabilities for KOS applications,
enforcing security policies and access control for application interactions.
"""

import os
import sys
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Set, Callable

logger = logging.getLogger('KOS.layer.permissions')

class Permission:
    """Permission definition and metadata"""
    
    def __init__(self, name: str, description: str, critical: bool = False):
        """
        Initialize a permission
        
        Args:
            name: Permission name
            description: Permission description
            critical: Whether this is a critical permission
        """
        self.name = name
        self.description = description
        self.critical = critical
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "critical": self.critical
        }

class PermissionsManager:
    """
    Manages permissions for KOS applications
    
    This class provides methods to manage and enforce permissions for
    applications running within the KOS environment.
    """
    
    def __init__(self):
        """Initialize the PermissionsManager component"""
        self.lock = threading.RLock()
        
        # Permission definitions
        self.permission_defs = {}  # name -> Permission
        
        # App permissions
        self.app_permissions = {}  # app_id -> {permission_name: granted}
        
        # Permission groups
        self.permission_groups = {}  # group_name -> [permission_name]
        
        # Pending permission requests
        self.pending_requests = {}  # request_id -> request_info
        
        # Permission request handlers
        self.request_handlers = []
        
        # Initialize default permissions
        self._init_default_permissions()
        
        # Load saved permissions
        self._load_permissions()
        
        logger.debug("PermissionsManager component initialized")
    
    def _init_default_permissions(self):
        """Initialize default permission definitions"""
        # File system permissions
        self.register_permission("file.read", "Read files in app's data directory", False)
        self.register_permission("file.write", "Write files in app's data directory", False)
        self.register_permission("file.delete", "Delete files in app's data directory", False)
        self.register_permission("file.unrestricted", "Access files outside of app's data directory", True)
        
        # Shared data permissions
        self.register_permission("shared_data.read", "Read files in shared data directory", False)
        self.register_permission("shared_data.write", "Write files in shared data directory", True)
        
        # Network permissions
        self.register_permission("network.connect", "Connect to network resources", False)
        self.register_permission("network.listen", "Listen for incoming network connections", True)
        
        # Process permissions
        self.register_permission("process.execute", "Execute system commands", True)
        self.register_permission("process.kill", "Terminate other processes", True)
        
        # System permissions
        self.register_permission("system.info", "Access system information", False)
        self.register_permission("system.monitor", "Monitor system resources", False)
        self.register_permission("system.modify", "Modify system settings", True)
        
        # App interaction permissions
        self.register_permission("app.launch", "Launch other applications", True)
        self.register_permission("app.terminate", "Terminate other applications", True)
        self.register_permission("app.message", "Send messages to other applications", False)
        
        # Define permission groups
        self.permission_groups["basic"] = [
            "file.read", "file.write", "file.delete",
            "shared_data.read", "network.connect",
            "system.info", "app.message"
        ]
        
        self.permission_groups["advanced"] = [
            "shared_data.write", "network.listen",
            "system.monitor", "app.launch"
        ]
        
        self.permission_groups["system"] = [
            "file.unrestricted", "process.execute", "process.kill",
            "system.modify", "app.terminate"
        ]
    
    def _load_permissions(self):
        """Load permissions from disk"""
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Load from permissions file
            permissions_file = os.path.join(kos_home, 'settings', 'permissions.json')
            
            if os.path.exists(permissions_file):
                with open(permissions_file, 'r') as f:
                    permissions_data = json.load(f)
                    
                    # Load app permissions
                    if "app_permissions" in permissions_data:
                        with self.lock:
                            self.app_permissions = permissions_data["app_permissions"]
                    
                    logger.debug(f"Loaded permissions for {len(self.app_permissions)} applications")
        except Exception as e:
            logger.error(f"Error loading permissions: {e}")
    
    def _save_permissions(self):
        """Save permissions to disk"""
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Create settings directory if it doesn't exist
            settings_dir = os.path.join(kos_home, 'settings')
            os.makedirs(settings_dir, exist_ok=True)
            
            # Save to permissions file
            permissions_file = os.path.join(settings_dir, 'permissions.json')
            
            with self.lock:
                permissions_data = {
                    "app_permissions": self.app_permissions
                }
                
                with open(permissions_file, 'w') as f:
                    json.dump(permissions_data, f, indent=2)
            
            logger.debug("Saved permissions to disk")
        except Exception as e:
            logger.error(f"Error saving permissions: {e}")
    
    def register_permission(self, name: str, description: str, critical: bool = False) -> bool:
        """
        Register a permission definition
        
        Args:
            name: Permission name
            description: Permission description
            critical: Whether this is a critical permission
            
        Returns:
            Success status
        """
        with self.lock:
            if name in self.permission_defs:
                # Update existing permission
                self.permission_defs[name].description = description
                self.permission_defs[name].critical = critical
                logger.debug(f"Updated permission definition: {name}")
            else:
                # Add new permission
                self.permission_defs[name] = Permission(name, description, critical)
                logger.debug(f"Registered permission definition: {name}")
            
            return True
    
    def register_permission_group(self, group_name: str, permissions: List[str]) -> bool:
        """
        Register a permission group
        
        Args:
            group_name: Group name
            permissions: List of permission names
            
        Returns:
            Success status
        """
        # Validate permissions
        for permission in permissions:
            if permission not in self.permission_defs:
                logger.error(f"Invalid permission in group: {permission}")
                return False
        
        with self.lock:
            self.permission_groups[group_name] = permissions
            logger.debug(f"Registered permission group: {group_name} with {len(permissions)} permissions")
            return True
    
    def check_permission(self, app_id: str, permission_name: str) -> bool:
        """
        Check if an application has a specific permission
        
        Args:
            app_id: Application ID
            permission_name: Permission name
            
        Returns:
            Whether the permission is granted
        """
        # Check app permissions
        with self.lock:
            if app_id not in self.app_permissions:
                return False
            
            app_perms = self.app_permissions[app_id]
            
            # Check specific permission
            if permission_name in app_perms:
                return app_perms[permission_name]
            
            # Check for wildcard permission
            parts = permission_name.split('.')
            if len(parts) > 1:
                wildcard = f"{parts[0]}.*"
                if wildcard in app_perms:
                    return app_perms[wildcard]
            
            return False
    
    def grant_permission(self, app_id: str, permission_name: str) -> bool:
        """
        Grant a permission to an application
        
        Args:
            app_id: Application ID
            permission_name: Permission name
            
        Returns:
            Success status
        """
        # Validate permission
        if permission_name not in self.permission_defs and not permission_name.endswith('.*'):
            logger.error(f"Invalid permission: {permission_name}")
            return False
        
        with self.lock:
            if app_id not in self.app_permissions:
                self.app_permissions[app_id] = {}
            
            # Grant permission
            self.app_permissions[app_id][permission_name] = True
            
            # Save permissions
            self._save_permissions()
            
            logger.debug(f"Granted permission {permission_name} to {app_id}")
            return True
    
    def revoke_permission(self, app_id: str, permission_name: str) -> bool:
        """
        Revoke a permission from an application
        
        Args:
            app_id: Application ID
            permission_name: Permission name
            
        Returns:
            Success status
        """
        with self.lock:
            if app_id not in self.app_permissions:
                return False
            
            # Remove permission
            if permission_name in self.app_permissions[app_id]:
                self.app_permissions[app_id][permission_name] = False
                
                # Save permissions
                self._save_permissions()
                
                logger.debug(f"Revoked permission {permission_name} from {app_id}")
                return True
            
            return False
    
    def grant_permission_group(self, app_id: str, group_name: str) -> Dict[str, Any]:
        """
        Grant a permission group to an application
        
        Args:
            app_id: Application ID
            group_name: Permission group name
            
        Returns:
            Dictionary with grant status
        """
        if group_name not in self.permission_groups:
            return {
                "success": False,
                "error": f"Invalid permission group: {group_name}"
            }
        
        permissions = self.permission_groups[group_name]
        granted = []
        failed = []
        
        for permission in permissions:
            if self.grant_permission(app_id, permission):
                granted.append(permission)
            else:
                failed.append(permission)
        
        return {
            "success": len(failed) == 0,
            "group": group_name,
            "granted": granted,
            "failed": failed
        }
    
    def request_permission(self, app_id: str, permission_name: str, reason: str) -> Dict[str, Any]:
        """
        Request a permission for an application
        
        Args:
            app_id: Application ID
            permission_name: Permission name
            reason: Reason for requesting the permission
            
        Returns:
            Dictionary with request status
        """
        # Check if permission already granted
        if self.check_permission(app_id, permission_name):
            return {
                "success": True,
                "granted": True,
                "permission": permission_name
            }
        
        # Validate permission
        if permission_name not in self.permission_defs and not permission_name.endswith('.*'):
            return {
                "success": False,
                "error": f"Invalid permission: {permission_name}"
            }
        
        # Create request
        request_id = f"{app_id}:{permission_name}:{int(time.time())}"
        
        request_info = {
            "id": request_id,
            "app_id": app_id,
            "permission": permission_name,
            "reason": reason,
            "timestamp": time.time(),
            "status": "pending"
        }
        
        # Add permission definition
        if permission_name in self.permission_defs:
            perm_def = self.permission_defs[permission_name]
            request_info["critical"] = perm_def.critical
            request_info["description"] = perm_def.description
        
        with self.lock:
            self.pending_requests[request_id] = request_info
        
        # Process request
        self._process_permission_request(request_id)
        
        return {
            "success": True,
            "request_id": request_id,
            "status": "pending"
        }
    
    def _process_permission_request(self, request_id: str):
        """
        Process a permission request
        
        Args:
            request_id: Request ID
        """
        with self.lock:
            if request_id not in self.pending_requests:
                return
            
            request = self.pending_requests[request_id]
        
        # Check if we have handlers
        if self.request_handlers:
            # Call handlers
            for handler in self.request_handlers:
                try:
                    result = handler(request)
                    
                    if result is not None and isinstance(result, bool):
                        if result:
                            self._approve_request(request_id)
                        else:
                            self._deny_request(request_id)
                        return
                except Exception as e:
                    logger.error(f"Error in permission request handler: {e}")
        
        # No automatic decision, request needs manual approval
        logger.info(f"Permission request {request_id} requires manual approval")
    
    def register_request_handler(self, handler: Callable) -> bool:
        """
        Register a permission request handler
        
        Args:
            handler: Handler function
            
        Returns:
            Success status
        """
        with self.lock:
            self.request_handlers.append(handler)
            logger.debug("Registered permission request handler")
            return True
    
    def unregister_request_handler(self, handler: Callable) -> bool:
        """
        Unregister a permission request handler
        
        Args:
            handler: Handler function
            
        Returns:
            Success status
        """
        with self.lock:
            if handler in self.request_handlers:
                self.request_handlers.remove(handler)
                logger.debug("Unregistered permission request handler")
                return True
            else:
                logger.warning("Handler not found")
                return False
    
    def approve_request(self, request_id: str) -> Dict[str, Any]:
        """
        Approve a permission request
        
        Args:
            request_id: Request ID
            
        Returns:
            Dictionary with approval status
        """
        return self._approve_request(request_id)
    
    def _approve_request(self, request_id: str) -> Dict[str, Any]:
        """
        Internal method to approve a permission request
        
        Args:
            request_id: Request ID
            
        Returns:
            Dictionary with approval status
        """
        with self.lock:
            if request_id not in self.pending_requests:
                return {
                    "success": False,
                    "error": f"Request not found: {request_id}"
                }
            
            request = self.pending_requests[request_id]
            
            # Grant permission
            if self.grant_permission(request["app_id"], request["permission"]):
                # Update request status
                request["status"] = "approved"
                
                logger.info(f"Approved permission request {request_id}")
                
                return {
                    "success": True,
                    "request_id": request_id,
                    "app_id": request["app_id"],
                    "permission": request["permission"],
                    "status": "approved"
                }
            else:
                # Update request status
                request["status"] = "failed"
                
                logger.error(f"Failed to grant permission for request {request_id}")
                
                return {
                    "success": False,
                    "error": "Failed to grant permission",
                    "request_id": request_id
                }
    
    def deny_request(self, request_id: str) -> Dict[str, Any]:
        """
        Deny a permission request
        
        Args:
            request_id: Request ID
            
        Returns:
            Dictionary with denial status
        """
        return self._deny_request(request_id)
    
    def _deny_request(self, request_id: str) -> Dict[str, Any]:
        """
        Internal method to deny a permission request
        
        Args:
            request_id: Request ID
            
        Returns:
            Dictionary with denial status
        """
        with self.lock:
            if request_id not in self.pending_requests:
                return {
                    "success": False,
                    "error": f"Request not found: {request_id}"
                }
            
            request = self.pending_requests[request_id]
            
            # Update request status
            request["status"] = "denied"
            
            logger.info(f"Denied permission request {request_id}")
            
            return {
                "success": True,
                "request_id": request_id,
                "app_id": request["app_id"],
                "permission": request["permission"],
                "status": "denied"
            }
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """
        Get pending permission requests
        
        Returns:
            List of pending requests
        """
        with self.lock:
            return [request for request in self.pending_requests.values() if request["status"] == "pending"]
    
    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a permission request
        
        Args:
            request_id: Request ID
            
        Returns:
            Request information or None if not found
        """
        with self.lock:
            return self.pending_requests.get(request_id)
    
    def get_app_permissions(self, app_id: str) -> Dict[str, Any]:
        """
        Get permissions for an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with app permissions
        """
        with self.lock:
            permissions = {}
            
            if app_id in self.app_permissions:
                app_perms = self.app_permissions[app_id]
                
                # Add each permission with its definition
                for perm_name, granted in app_perms.items():
                    if granted:
                        permissions[perm_name] = {
                            "granted": True
                        }
                        
                        # Add permission definition if available
                        if perm_name in self.permission_defs:
                            perm_def = self.permission_defs[perm_name]
                            permissions[perm_name]["description"] = perm_def.description
                            permissions[perm_name]["critical"] = perm_def.critical
            
            return {
                "success": True,
                "app_id": app_id,
                "permissions": permissions
            }
    
    def get_permission_groups(self) -> Dict[str, List[str]]:
        """
        Get permission groups
        
        Returns:
            Dictionary with permission groups
        """
        with self.lock:
            return self.permission_groups.copy()
    
    def get_permission_definitions(self) -> Dict[str, Dict[str, Any]]:
        """
        Get permission definitions
        
        Returns:
            Dictionary with permission definitions
        """
        with self.lock:
            return {name: perm.to_dict() for name, perm in self.permission_defs.items()}

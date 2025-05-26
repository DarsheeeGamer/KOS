"""
Permission Management for KOS

This module implements Unix-style file permissions, Access Control Lists (ACLs),
and capability-based security features for KOS.

Features:
- File permission management (rwx for user/group/other)
- Extended ACL support for more granular permissions
- SetUID/SetGID functionality
- Fine-grained capability system
"""

import os
import json
import stat
import time
import logging
from enum import Enum, IntFlag
from typing import Dict, List, Optional, Set, Tuple, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ACL_DB_PATH = os.path.join(KOS_ROOT, 'security/acls.json')
CAPABILITY_DB_PATH = os.path.join(KOS_ROOT, 'security/capabilities.json')

# Ensure directories exist
os.makedirs(os.path.dirname(ACL_DB_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class FilePermission(IntFlag):
    """Unix-style file permissions."""
    # User permissions
    OWNER_READ = 0o400
    OWNER_WRITE = 0o200
    OWNER_EXEC = 0o100
    
    # Group permissions
    GROUP_READ = 0o040
    GROUP_WRITE = 0o020
    GROUP_EXEC = 0o010
    
    # Other permissions
    OTHER_READ = 0o004
    OTHER_WRITE = 0o002
    OTHER_EXEC = 0o001
    
    # Special permissions
    SETUID = 0o4000
    SETGID = 0o2000
    STICKY = 0o1000
    
    # Common permission sets
    OWNER_ALL = OWNER_READ | OWNER_WRITE | OWNER_EXEC
    GROUP_ALL = GROUP_READ | GROUP_WRITE | GROUP_EXEC
    OTHER_ALL = OTHER_READ | OTHER_WRITE | OTHER_EXEC
    
    # Default permissions
    DEFAULT_FILE = OWNER_READ | OWNER_WRITE | GROUP_READ | OTHER_READ  # 0o644
    DEFAULT_DIR = OWNER_ALL | GROUP_READ | GROUP_EXEC | OTHER_READ | OTHER_EXEC  # 0o755


class ACLType(str, Enum):
    """Types of ACL entries."""
    USER = "user"
    GROUP = "group"
    MASK = "mask"
    OTHER = "other"


class ACLPermission(IntFlag):
    """ACL-specific permission flags."""
    READ = 0o4
    WRITE = 0o2
    EXECUTE = 0o1
    ALL = READ | WRITE | EXECUTE


class Capability(str, Enum):
    """Linux-like capabilities for fine-grained privilege control."""
    # Process capabilities
    CAP_CHOWN = "chown"
    CAP_DAC_OVERRIDE = "dac_override"
    CAP_DAC_READ_SEARCH = "dac_read_search"
    CAP_FOWNER = "fowner"
    CAP_FSETID = "fsetid"
    CAP_KILL = "kill"
    CAP_SETGID = "setgid"
    CAP_SETUID = "setuid"
    CAP_SETPCAP = "setpcap"
    CAP_NET_BIND_SERVICE = "net_bind_service"
    CAP_NET_BROADCAST = "net_broadcast"
    CAP_NET_ADMIN = "net_admin"
    CAP_NET_RAW = "net_raw"
    CAP_IPC_LOCK = "ipc_lock"
    CAP_IPC_OWNER = "ipc_owner"
    CAP_SYS_MODULE = "sys_module"
    CAP_SYS_RAWIO = "sys_rawio"
    CAP_SYS_CHROOT = "sys_chroot"
    CAP_SYS_PTRACE = "sys_ptrace"
    CAP_SYS_ADMIN = "sys_admin"
    CAP_SYS_BOOT = "sys_boot"
    CAP_SYS_NICE = "sys_nice"
    CAP_SYS_RESOURCE = "sys_resource"
    CAP_SYS_TIME = "sys_time"
    CAP_MKNOD = "mknod"
    CAP_AUDIT_WRITE = "audit_write"
    CAP_AUDIT_CONTROL = "audit_control"
    
    # Custom KOS capabilities
    CAP_CONTAINER_ADMIN = "container_admin"
    CAP_SERVICE_ADMIN = "service_admin"
    CAP_NETWORK_ADMIN = "network_admin"
    CAP_SECURITY_ADMIN = "security_admin"
    CAP_STORAGE_ADMIN = "storage_admin"


class PermissionManager:
    """
    Manages file permissions for KOS, implementing Unix-style permission checks.
    
    This class provides an abstraction over the basic file permission system,
    including support for owner/group/other permissions, setuid/setgid, and
    the sticky bit.
    """
    
    def __init__(self):
        """Initialize the PermissionManager."""
        from .users import UserManager, GroupManager
        self.user_manager = UserManager()
        self.group_manager = GroupManager()
    
    def get_file_owner(self, path: str) -> Tuple[int, int]:
        """
        Get the owner and group of a file.
        
        Args:
            path: Path to the file
            
        Returns:
            Tuple[int, int]: (UID, GID) of the file owner
        """
        # In a real implementation, this would use os.stat
        # For now, we'll use a simulated implementation
        if not os.path.exists(path):
            return (-1, -1)
        
        # For simulation, we'll check if it's in a user's home directory
        # and assume it's owned by that user
        home_base = os.path.join(KOS_ROOT, 'home')
        if path.startswith(home_base):
            parts = path[len(home_base)+1:].split(os.sep)
            if parts:
                username = parts[0]
                user = self.user_manager.get_user(username)
                if user:
                    return (user['uid'], user['gid'])
        
        # Default to root for system files
        return (0, 0)
    
    def get_file_mode(self, path: str) -> int:
        """
        Get the permission mode of a file.
        
        Args:
            path: Path to the file
            
        Returns:
            int: Permission mode as an integer
        """
        # In a real implementation, this would use os.stat
        # For now, return default permissions based on file type
        if not os.path.exists(path):
            return 0
        
        if os.path.isdir(path):
            return int(FilePermission.DEFAULT_DIR)
        else:
            return int(FilePermission.DEFAULT_FILE)
    
    def chmod(self, path: str, mode: int) -> bool:
        """
        Change the permissions of a file.
        
        Args:
            path: Path to the file
            mode: New permission mode
            
        Returns:
            bool: Success or failure
        """
        # In a real implementation, this would use os.chmod
        # For now, log the intended change
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        
        # Check if the current user has permission to change file modes
        # (would need user context)
        
        logger.info(f"Would chmod {path} to {mode:o}")
        return True
    
    def chown(self, path: str, uid: int, gid: int) -> bool:
        """
        Change the owner and group of a file.
        
        Args:
            path: Path to the file
            uid: New owner UID (-1 to leave unchanged)
            gid: New group GID (-1 to leave unchanged)
            
        Returns:
            bool: Success or failure
        """
        # In a real implementation, this would use os.chown
        # For now, log the intended change
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        
        # Check if the current user has permission to change ownership
        # (would need user context and likely CAP_CHOWN)
        
        user_str = str(uid) if uid == -1 else self.user_manager.get_user_by_uid(uid)['username']
        group_str = str(gid) if gid == -1 else self.group_manager.get_group_by_gid(gid)['groupname']
        
        logger.info(f"Would chown {path} to {user_str}:{group_str}")
        return True
    
    def check_permission(self, path: str, uid: int, requested_perm: int) -> bool:
        """
        Check if a user has the requested permissions on a file.
        
        Args:
            path: Path to the file
            uid: User ID to check permissions for
            requested_perm: Requested permissions (e.g., R_OK, W_OK, X_OK)
            
        Returns:
            bool: Whether the user has the requested permissions
        """
        if not os.path.exists(path):
            return False
        
        # Get file metadata
        owner_uid, owner_gid = self.get_file_owner(path)
        mode = self.get_file_mode(path)
        
        # Root can do anything
        if uid == 0:
            return True
        
        # Calculate the permissions for this user
        if uid == owner_uid:
            # User is the owner
            shift = 6
        else:
            # Check if user is in the file's group
            user = self.user_manager.get_user_by_uid(uid)
            user_groups = self.group_manager.get_user_groups(user['username']) if user else []
            group_gids = [self.group_manager.get_group(g)['gid'] for g in user_groups]
            
            if owner_gid in group_gids:
                # User is in the file's group
                shift = 3
            else:
                # User is not in the file's group
                shift = 0
        
        # Extract the relevant permission bits
        allowed = (mode >> shift) & 0o7
        requested = requested_perm & 0o7
        
        return (allowed & requested) == requested
    
    def umask(self, mask: Optional[int] = None) -> int:
        """
        Get or set the file creation mask.
        
        Args:
            mask: New umask value or None to get current value
            
        Returns:
            int: Previous umask value
        """
        # In a real implementation, this would use os.umask
        # For now, we'll use a simulated value
        # We'd ideally store this in thread-local storage or process state
        
        old_umask = 0o022  # Default umask
        
        if mask is not None:
            logger.info(f"Would set umask to {mask:o}")
        
        return old_umask


class ACLManager:
    """
    Manages Access Control Lists (ACLs) for KOS.
    
    This class provides extended access control beyond the basic Unix permissions,
    allowing per-user and per-group permissions on files.
    """
    
    def __init__(self):
        """Initialize the ACLManager."""
        self.acls = self._load_acls()
        from .users import UserManager, GroupManager
        self.user_manager = UserManager()
        self.group_manager = GroupManager()
    
    def _load_acls(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load ACLs database from disk."""
        if os.path.exists(ACL_DB_PATH):
            try:
                with open(ACL_DB_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted ACLs database. Creating new one.")
        return {}
    
    def _save_acls(self):
        """Save ACLs database to disk."""
        os.makedirs(os.path.dirname(ACL_DB_PATH), exist_ok=True)
        with open(ACL_DB_PATH, 'w') as f:
            json.dump(self.acls, f, indent=2)
    
    def get_acl(self, path: str) -> List[Dict[str, Any]]:
        """
        Get the ACL entries for a file.
        
        Args:
            path: Path to the file
            
        Returns:
            List[Dict[str, Any]]: List of ACL entries
        """
        norm_path = os.path.normpath(path)
        return self.acls.get(norm_path, [])
    
    def set_acl(self, path: str, entries: List[Dict[str, Any]]) -> bool:
        """
        Set the ACL entries for a file.
        
        Args:
            path: Path to the file
            entries: List of ACL entries
            
        Returns:
            bool: Success or failure
        """
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        
        norm_path = os.path.normpath(path)
        self.acls[norm_path] = entries
        self._save_acls()
        
        logger.info(f"Set ACL for {path}")
        return True
    
    def add_acl_entry(self, path: str, type: ACLType, 
                     qualifier: str, permissions: int) -> bool:
        """
        Add an ACL entry to a file.
        
        Args:
            path: Path to the file
            type: Type of ACL entry (user, group, mask, other)
            qualifier: User or group name (or None for mask/other)
            permissions: Permission bits (read, write, execute)
            
        Returns:
            bool: Success or failure
        """
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        
        # Validate the qualifier
        if type == ACLType.USER and qualifier != "":
            if not self.user_manager.get_user(qualifier):
                logger.error(f"User not found: {qualifier}")
                return False
        elif type == ACLType.GROUP and qualifier != "":
            if not self.group_manager.get_group(qualifier):
                logger.error(f"Group not found: {qualifier}")
                return False
        
        # Get existing ACL
        norm_path = os.path.normpath(path)
        acl = self.acls.get(norm_path, [])
        
        # Check if this entry already exists
        for entry in acl:
            if entry['type'] == type and entry.get('qualifier', "") == qualifier:
                entry['permissions'] = permissions
                self._save_acls()
                logger.info(f"Updated ACL entry for {path}: {type} {qualifier}")
                return True
        
        # Add new entry
        acl.append({
            'type': type,
            'qualifier': qualifier,
            'permissions': permissions
        })
        
        self.acls[norm_path] = acl
        self._save_acls()
        
        logger.info(f"Added ACL entry for {path}: {type} {qualifier}")
        return True
    
    def remove_acl_entry(self, path: str, type: ACLType, qualifier: str) -> bool:
        """
        Remove an ACL entry from a file.
        
        Args:
            path: Path to the file
            type: Type of ACL entry (user, group, mask, other)
            qualifier: User or group name (or None for mask/other)
            
        Returns:
            bool: Success or failure
        """
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            return False
        
        norm_path = os.path.normpath(path)
        acl = self.acls.get(norm_path, [])
        
        # Find and remove the entry
        new_acl = [entry for entry in acl 
                  if not (entry['type'] == type and 
                         entry.get('qualifier', "") == qualifier)]
        
        if len(new_acl) == len(acl):
            logger.warning(f"ACL entry not found: {type} {qualifier}")
            return False
        
        self.acls[norm_path] = new_acl
        self._save_acls()
        
        logger.info(f"Removed ACL entry from {path}: {type} {qualifier}")
        return True
    
    def check_acl_permission(self, path: str, uid: int, 
                            requested_perm: int) -> bool:
        """
        Check if a user has the requested permissions via ACL.
        
        Args:
            path: Path to the file
            uid: User ID to check permissions for
            requested_perm: Requested permissions
            
        Returns:
            bool: Whether the user has the requested permissions
        """
        if not os.path.exists(path):
            return False
        
        # Root can do anything
        if uid == 0:
            return True
        
        norm_path = os.path.normpath(path)
        acl = self.acls.get(norm_path, [])
        
        if not acl:
            # Fall back to standard permission check
            perm_manager = PermissionManager()
            return perm_manager.check_permission(path, uid, requested_perm)
        
        # Get user and their groups
        user = self.user_manager.get_user_by_uid(uid)
        if not user:
            return False
        
        username = user['username']
        user_groups = self.group_manager.get_user_groups(username)
        
        # Calculate effective permissions from ACL
        mask_perm = 0o7  # Default to all permissions if no mask entry
        user_perm = 0
        group_perm = 0
        other_perm = 0
        
        # First pass: get mask and other entries
        for entry in acl:
            if entry['type'] == ACLType.MASK:
                mask_perm = entry['permissions']
            elif entry['type'] == ACLType.OTHER:
                other_perm = entry['permissions']
        
        # Second pass: get specific user and group entries
        for entry in acl:
            if entry['type'] == ACLType.USER:
                if entry.get('qualifier', "") == username:
                    user_perm = entry['permissions'] & mask_perm
            elif entry['type'] == ACLType.GROUP:
                qualifier = entry.get('qualifier', "")
                if qualifier in user_groups:
                    # Take the most permissive group permission
                    group_perm |= entry['permissions'] & mask_perm
        
        # Calculate effective permission
        if user_perm > 0:
            # Specific user entry exists
            effective_perm = user_perm
        elif group_perm > 0:
            # User is in at least one group with an entry
            effective_perm = group_perm
        else:
            # Fall back to "other" permissions
            effective_perm = other_perm
        
        # Check if the requested permissions are granted
        return (effective_perm & requested_perm) == requested_perm


class CapabilityManager:
    """
    Manages capabilities for KOS.
    
    This class provides a fine-grained privilege system similar to Linux capabilities,
    allowing specific privileged operations without full root access.
    """
    
    def __init__(self):
        """Initialize the CapabilityManager."""
        self.capabilities = self._load_capabilities()
    
    def _load_capabilities(self) -> Dict[str, List[str]]:
        """Load capabilities database from disk."""
        if os.path.exists(CAPABILITY_DB_PATH):
            try:
                with open(CAPABILITY_DB_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted capabilities database. Creating new one.")
        return {'root': [cap.value for cap in Capability]}
    
    def _save_capabilities(self):
        """Save capabilities database to disk."""
        os.makedirs(os.path.dirname(CAPABILITY_DB_PATH), exist_ok=True)
        with open(CAPABILITY_DB_PATH, 'w') as f:
            json.dump(self.capabilities, f, indent=2)
    
    def get_user_capabilities(self, username: str) -> List[str]:
        """
        Get the capabilities for a user.
        
        Args:
            username: Username to get capabilities for
            
        Returns:
            List[str]: List of capability names
        """
        return self.capabilities.get(username, [])
    
    def add_capability(self, username: str, capability: Union[Capability, str]) -> bool:
        """
        Add a capability to a user.
        
        Args:
            username: Username to add capability to
            capability: Capability to add
            
        Returns:
            bool: Success or failure
        """
        from .users import UserManager
        user_manager = UserManager()
        
        if not user_manager.get_user(username):
            logger.error(f"User not found: {username}")
            return False
        
        cap_value = capability.value if isinstance(capability, Capability) else capability
        
        # Validate capability
        try:
            if not isinstance(capability, Capability):
                cap_value = Capability(capability).value
        except ValueError:
            logger.error(f"Invalid capability: {capability}")
            return False
        
        # Initialize user capabilities if not exist
        if username not in self.capabilities:
            self.capabilities[username] = []
        
        # Add capability if not already present
        if cap_value not in self.capabilities[username]:
            self.capabilities[username].append(cap_value)
            self._save_capabilities()
            logger.info(f"Added capability {cap_value} to user {username}")
        
        return True
    
    def remove_capability(self, username: str, capability: Union[Capability, str]) -> bool:
        """
        Remove a capability from a user.
        
        Args:
            username: Username to remove capability from
            capability: Capability to remove
            
        Returns:
            bool: Success or failure
        """
        if username not in self.capabilities:
            logger.warning(f"User {username} has no capabilities")
            return False
        
        cap_value = capability.value if isinstance(capability, Capability) else capability
        
        if cap_value not in self.capabilities[username]:
            logger.warning(f"User {username} does not have capability {cap_value}")
            return False
        
        self.capabilities[username].remove(cap_value)
        self._save_capabilities()
        
        logger.info(f"Removed capability {cap_value} from user {username}")
        return True
    
    def has_capability(self, username: str, capability: Union[Capability, str]) -> bool:
        """
        Check if a user has a capability.
        
        Args:
            username: Username to check
            capability: Capability to check for
            
        Returns:
            bool: Whether the user has the capability
        """
        from .users import UserManager
        user_manager = UserManager()
        
        # Root has all capabilities
        user = user_manager.get_user(username)
        if user and user['uid'] == 0:
            return True
        
        cap_value = capability.value if isinstance(capability, Capability) else capability
        
        user_caps = self.capabilities.get(username, [])
        return cap_value in user_caps

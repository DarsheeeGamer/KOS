"""
KOS Access Control Lists (ACL) Module

This module provides POSIX-like Access Control Lists for KOS,
allowing fine-grained permission control beyond the basic Unix permissions model.
"""

import os
import sys
import logging
import threading
import json
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager, GroupManager
from kos.security.permissions import FileMetadata, check_permission

# Set up logging
logger = logging.getLogger('KOS.security.acl')

# Lock for ACL operations
_acl_lock = threading.RLock()

# ACL storage
_acl_entries = {}  # path -> ACL entries

# Constants
ACL_TYPE_ACCESS = "access"
ACL_TYPE_DEFAULT = "default"

# Permissions
ACL_READ = "r"
ACL_WRITE = "w"
ACL_EXECUTE = "x"

# ACL tags
ACL_USER = "user"
ACL_GROUP = "group"
ACL_MASK = "mask"
ACL_OTHER = "other"


class ACLEntry:
    """Class representing an ACL entry for a file"""
    
    def __init__(self, tag: str, qualifier: Optional[str], permissions: str, acl_type: str = ACL_TYPE_ACCESS):
        """
        Initialize an ACL entry
        
        Args:
            tag: ACL tag (user, group, mask, other)
            qualifier: User or group name (None for mask/other)
            permissions: Permission string (e.g., "rwx", "r--", etc.)
            acl_type: ACL type (access or default)
        """
        self.tag = tag
        self.qualifier = qualifier
        self.permissions = self._normalize_permissions(permissions)
        self.acl_type = acl_type
    
    def _normalize_permissions(self, permissions: str) -> str:
        """Normalize permissions string to rwx format"""
        result = ""
        result += ACL_READ if ACL_READ in permissions else "-"
        result += ACL_WRITE if ACL_WRITE in permissions else "-"
        result += ACL_EXECUTE if ACL_EXECUTE in permissions else "-"
        return result
    
    def has_permission(self, permission: str) -> bool:
        """
        Check if entry has a specific permission
        
        Args:
            permission: Permission to check (r, w, x)
        
        Returns:
            True if permission is granted
        """
        return permission in self.permissions
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "tag": self.tag,
            "qualifier": self.qualifier,
            "permissions": self.permissions,
            "acl_type": self.acl_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ACLEntry':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            ACLEntry instance
        """
        return cls(
            tag=data["tag"],
            qualifier=data.get("qualifier"),
            permissions=data["permissions"],
            acl_type=data.get("acl_type", ACL_TYPE_ACCESS)
        )
    
    def __str__(self) -> str:
        """String representation in getfacl format"""
        if self.acl_type == ACL_TYPE_DEFAULT:
            prefix = "default:"
        else:
            prefix = ""
        
        if self.qualifier is not None:
            return f"{prefix}{self.tag}:{self.qualifier}:{self.permissions}"
        else:
            return f"{prefix}{self.tag}::{self.permissions}"


class ACL:
    """Class representing a complete ACL for a file"""
    
    def __init__(self, path: str):
        """
        Initialize an ACL
        
        Args:
            path: File path
        """
        self.path = path
        self.entries = []  # List of ACLEntry objects
    
    def add_entry(self, entry: ACLEntry) -> bool:
        """
        Add an ACL entry
        
        Args:
            entry: ACL entry to add
        
        Returns:
            Success status
        """
        # Check for duplicate entry
        for i, existing in enumerate(self.entries):
            if (existing.tag == entry.tag and 
                existing.qualifier == entry.qualifier and
                existing.acl_type == entry.acl_type):
                # Replace existing entry
                self.entries[i] = entry
                return True
        
        # Add new entry
        self.entries.append(entry)
        return True
    
    def remove_entry(self, tag: str, qualifier: Optional[str] = None, acl_type: str = ACL_TYPE_ACCESS) -> bool:
        """
        Remove an ACL entry
        
        Args:
            tag: ACL tag
            qualifier: User or group name (None for mask/other)
            acl_type: ACL type
        
        Returns:
            Success status
        """
        for i, entry in enumerate(self.entries):
            if (entry.tag == tag and 
                entry.qualifier == qualifier and
                entry.acl_type == acl_type):
                del self.entries[i]
                return True
        
        return False
    
    def get_entry(self, tag: str, qualifier: Optional[str] = None, acl_type: str = ACL_TYPE_ACCESS) -> Optional[ACLEntry]:
        """
        Get an ACL entry
        
        Args:
            tag: ACL tag
            qualifier: User or group name (None for mask/other)
            acl_type: ACL type
        
        Returns:
            ACLEntry or None if not found
        """
        for entry in self.entries:
            if (entry.tag == tag and 
                entry.qualifier == qualifier and
                entry.acl_type == acl_type):
                return entry
        
        return None
    
    def get_permissions(self, uid: int, gid: int, groups: List[str]) -> str:
        """
        Get effective permissions for a user
        
        Args:
            uid: User ID
            gid: Group ID
            groups: Group memberships
        
        Returns:
            Permission string (e.g., "rwx", "r--", etc.)
        """
        # Start with empty permissions
        effective_perms = ""
        
        # Get user entry if it exists
        user = UserManager.get_user_by_uid(uid)
        user_entry = None
        if user:
            user_entry = self.get_entry(ACL_USER, user.username)
        
        if user_entry:
            effective_perms = user_entry.permissions
        else:
            # Try groups
            group_perms = []
            
            # Check primary group
            group = GroupManager.get_group_by_gid(gid)
            if group:
                group_entry = self.get_entry(ACL_GROUP, group.name)
                if group_entry:
                    group_perms.append(group_entry.permissions)
            
            # Check supplementary groups
            for group_name in groups:
                group_entry = self.get_entry(ACL_GROUP, group_name)
                if group_entry:
                    group_perms.append(group_entry.permissions)
            
            if group_perms:
                # Combine group permissions (most permissive)
                for perm in [ACL_READ, ACL_WRITE, ACL_EXECUTE]:
                    if any(perm in gp for gp in group_perms):
                        effective_perms += perm
                    else:
                        effective_perms += "-"
            else:
                # Use "other" permissions
                other_entry = self.get_entry(ACL_OTHER)
                if other_entry:
                    effective_perms = other_entry.permissions
                else:
                    effective_perms = "---"
        
        # Apply mask if it exists
        mask_entry = self.get_entry(ACL_MASK)
        if mask_entry and (user_entry or group_perms):
            masked_perms = ""
            for i, perm in enumerate(effective_perms):
                if perm != "-" and mask_entry.permissions[i] == "-":
                    masked_perms += "-"
                else:
                    masked_perms += perm
            return masked_perms
        
        return effective_perms
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "path": self.path,
            "entries": [entry.to_dict() for entry in self.entries]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ACL':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            ACL instance
        """
        acl = cls(data["path"])
        acl.entries = [ACLEntry.from_dict(entry) for entry in data.get("entries", [])]
        return acl
    
    def __str__(self) -> str:
        """String representation in getfacl format"""
        output = [f"# file: {self.path}"]
        
        # Add regular entries first
        for entry in self.entries:
            if entry.acl_type == ACL_TYPE_ACCESS:
                output.append(str(entry))
        
        # Then add default entries
        default_entries = [e for e in self.entries if e.acl_type == ACL_TYPE_DEFAULT]
        if default_entries:
            output.append("")
            for entry in default_entries:
                output.append(str(entry))
        
        return "\n".join(output)


class ACLManager:
    """Manager for ACL operations"""
    
    @classmethod
    def set_acl(cls, path: str, acl: ACL) -> Tuple[bool, str]:
        """
        Set ACL for a file
        
        Args:
            path: File path
            acl: ACL object
        
        Returns:
            (success, message)
        """
        with _acl_lock:
            # Verify file exists
            if not os.path.exists(path):
                return False, f"No such file or directory: {path}"
            
            # Store ACL
            _acl_entries[path] = acl
            return True, f"ACL set for {path}"
    
    @classmethod
    def get_acl(cls, path: str) -> Optional[ACL]:
        """
        Get ACL for a file
        
        Args:
            path: File path
        
        Returns:
            ACL object or None if not found
        """
        with _acl_lock:
            if path in _acl_entries:
                return _acl_entries[path]
            
            # Create a new ACL based on file permissions
            try:
                stat_result = os.stat(path)
                metadata = FileMetadata.from_stat(path, stat_result)
                
                acl = ACL(path)
                
                # Add owner entry
                owner = UserManager.get_user_by_uid(metadata.uid)
                if owner:
                    perms = ""
                    perms += ACL_READ if metadata.mode & 0o400 else "-"
                    perms += ACL_WRITE if metadata.mode & 0o200 else "-"
                    perms += ACL_EXECUTE if metadata.mode & 0o100 else "-"
                    acl.add_entry(ACLEntry(ACL_USER, owner.username, perms))
                
                # Add group entry
                group = GroupManager.get_group_by_gid(metadata.gid)
                if group:
                    perms = ""
                    perms += ACL_READ if metadata.mode & 0o040 else "-"
                    perms += ACL_WRITE if metadata.mode & 0o020 else "-"
                    perms += ACL_EXECUTE if metadata.mode & 0o010 else "-"
                    acl.add_entry(ACLEntry(ACL_GROUP, group.name, perms))
                
                # Add other entry
                perms = ""
                perms += ACL_READ if metadata.mode & 0o004 else "-"
                perms += ACL_WRITE if metadata.mode & 0o002 else "-"
                perms += ACL_EXECUTE if metadata.mode & 0o001 else "-"
                acl.add_entry(ACLEntry(ACL_OTHER, None, perms))
                
                # Add mask entry (same as group initially)
                if group:
                    perms = ""
                    perms += ACL_READ if metadata.mode & 0o040 else "-"
                    perms += ACL_WRITE if metadata.mode & 0o020 else "-"
                    perms += ACL_EXECUTE if metadata.mode & 0o010 else "-"
                    acl.add_entry(ACLEntry(ACL_MASK, None, perms))
                
                return acl
            
            except (FileNotFoundError, PermissionError):
                return None
    
    @classmethod
    def modify_acl(cls, path: str, tag: str, qualifier: Optional[str],
                 permissions: str, acl_type: str = ACL_TYPE_ACCESS) -> Tuple[bool, str]:
        """
        Modify an ACL entry
        
        Args:
            path: File path
            tag: ACL tag
            qualifier: User or group name (None for mask/other)
            permissions: Permission string
            acl_type: ACL type
        
        Returns:
            (success, message)
        """
        with _acl_lock:
            # Get ACL
            acl = cls.get_acl(path)
            if not acl:
                return False, f"Cannot get ACL for {path}"
            
            # Create entry
            entry = ACLEntry(tag, qualifier, permissions, acl_type)
            
            # Add entry to ACL
            if acl.add_entry(entry):
                # Store updated ACL
                cls.set_acl(path, acl)
                return True, f"Modified {tag}:{qualifier or ''} permissions to {permissions}"
            else:
                return False, f"Failed to modify ACL entry"
    
    @classmethod
    def remove_acl_entry(cls, path: str, tag: str, qualifier: Optional[str] = None,
                       acl_type: str = ACL_TYPE_ACCESS) -> Tuple[bool, str]:
        """
        Remove an ACL entry
        
        Args:
            path: File path
            tag: ACL tag
            qualifier: User or group name (None for mask/other)
            acl_type: ACL type
        
        Returns:
            (success, message)
        """
        with _acl_lock:
            # Get ACL
            acl = cls.get_acl(path)
            if not acl:
                return False, f"Cannot get ACL for {path}"
            
            # Remove entry
            if acl.remove_entry(tag, qualifier, acl_type):
                # Store updated ACL
                cls.set_acl(path, acl)
                return True, f"Removed {tag}:{qualifier or ''} entry"
            else:
                return False, f"Entry not found"
    
    @classmethod
    def check_permission(cls, path: str, uid: int, permission: str) -> bool:
        """
        Check if user has permission on file using ACL
        
        Args:
            path: File path
            uid: User ID
            permission: Permission to check (read, write, execute)
        
        Returns:
            True if user has permission
        """
        # Map permission string to ACL permission
        perm_map = {
            "read": ACL_READ,
            "write": ACL_WRITE,
            "execute": ACL_EXECUTE
        }
        
        if permission not in perm_map:
            return False
        
        acl_perm = perm_map[permission]
        
        # Get ACL
        acl = cls.get_acl(path)
        if not acl:
            # Fall back to standard permission check
            metadata = None
            try:
                stat_result = os.stat(path)
                metadata = FileMetadata.from_stat(path, stat_result)
            except (FileNotFoundError, PermissionError):
                return False
            
            return check_permission(metadata, permission)
        
        # Get user information
        user = UserManager.get_user_by_uid(uid)
        if not user:
            return False
        
        # Root can do anything
        if uid == 0:
            return True
        
        # Get primary group
        gid = user.gid
        
        # Get groups
        groups = user.groups or []
        
        # Get permissions from ACL
        perms = acl.get_permissions(uid, gid, groups)
        
        # Check if permission is granted
        return acl_perm in perms
    
    @classmethod
    def save_acls(cls, acl_file: str) -> Tuple[bool, str]:
        """
        Save ACLs to file
        
        Args:
            acl_file: File path
        
        Returns:
            (success, message)
        """
        with _acl_lock:
            try:
                data = {}
                for path, acl in _acl_entries.items():
                    data[path] = acl.to_dict()
                
                with open(acl_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, "ACLs saved"
            except Exception as e:
                return False, str(e)
    
    @classmethod
    def load_acls(cls, acl_file: str) -> Tuple[bool, str]:
        """
        Load ACLs from file
        
        Args:
            acl_file: File path
        
        Returns:
            (success, message)
        """
        with _acl_lock:
            try:
                if not os.path.exists(acl_file):
                    return False, "ACL file not found"
                
                with open(acl_file, 'r') as f:
                    data = json.load(f)
                
                _acl_entries.clear()
                for path, acl_data in data.items():
                    _acl_entries[path] = ACL.from_dict(acl_data)
                
                return True, "ACLs loaded"
            except Exception as e:
                return False, str(e)


def initialize():
    """Initialize ACL system"""
    logger.info("Initializing ACL system")
    
    # Create ACL directory
    acl_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(acl_dir, exist_ok=True)
    
    # Load ACLs if they exist
    acl_file = os.path.join(acl_dir, 'acls.json')
    if os.path.exists(acl_file):
        ACLManager.load_acls(acl_file)
    
    logger.info("ACL system initialized")


# Initialize on module load
initialize()

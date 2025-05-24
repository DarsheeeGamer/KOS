"""
KOS User Management System

This module provides user and group management capabilities for KOS,
similar to Linux's user management system.
"""

import os
import sys
import time
import json
import logging
import threading
import hashlib
import uuid
import random
import string
import pwd
import grp
from typing import Dict, List, Any, Optional, Union, Tuple

# Set up logging
logger = logging.getLogger('KOS.security.users')

# User and group registries
USERS = {}
GROUPS = {}
USER_LOCK = threading.RLock()
GROUP_LOCK = threading.RLock()

# Constants
DEFAULT_SHELL = "/bin/kosh"  # KOS shell
DEFAULT_HOME_PREFIX = "/home"
MIN_UID = 1000
MIN_GID = 1000
MAX_ID = 60000
ROOT_UID = 0
ROOT_GID = 0
SYSTEM_UID_RANGE = (1, 999)
SYSTEM_GID_RANGE = (1, 999)

class User:
    """User class representing a system user"""
    
    def __init__(self, username: str, uid: int, gid: int, full_name: str = "",
                password_hash: str = None, home_dir: str = None, 
                shell: str = DEFAULT_SHELL, groups: List[str] = None):
        """
        Initialize a new user
        
        Args:
            username: Username
            uid: User ID
            gid: Primary group ID
            full_name: Full name
            password_hash: Password hash (None for no password)
            home_dir: Home directory
            shell: Login shell
            groups: Additional groups
        """
        self.username = username
        self.uid = uid
        self.gid = gid
        self.full_name = full_name
        self.password_hash = password_hash
        self.home_dir = home_dir or f"{DEFAULT_HOME_PREFIX}/{username}"
        self.shell = shell
        self.groups = groups or []
        
        # Additional fields
        self.last_password_change = time.time()
        self.account_expires = None  # None for never
        self.locked = False
    
    def check_password(self, password: str) -> bool:
        """
        Check if password matches
        
        Args:
            password: Password to check
            
        Returns:
            True if password matches
        """
        if self.password_hash is None:
            return False
        
        if self.locked:
            return False
        
        # Check password hash
        hash_parts = self.password_hash.split('$')
        if len(hash_parts) != 4:
            return False
        
        _, algo, salt, stored_hash = hash_parts
        
        if algo == "6":  # SHA-512
            new_hash = hashlib.sha512((salt + password).encode()).hexdigest()
            return new_hash == stored_hash
        elif algo == "5":  # SHA-256
            new_hash = hashlib.sha256((salt + password).encode()).hexdigest()
            return new_hash == stored_hash
        else:
            return False
    
    def set_password(self, password: str) -> bool:
        """
        Set password
        
        Args:
            password: New password
            
        Returns:
            Success status
        """
        if not password:
            self.password_hash = None
            return True
        
        # Generate salt
        salt = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
        
        # Hash password with SHA-512
        hash_value = hashlib.sha512((salt + password).encode()).hexdigest()
        self.password_hash = f"$6${salt}${hash_value}"
        self.last_password_change = time.time()
        
        return True
    
    def lock(self) -> bool:
        """
        Lock user account
        
        Returns:
            Success status
        """
        self.locked = True
        return True
    
    def unlock(self) -> bool:
        """
        Unlock user account
        
        Returns:
            Success status
        """
        self.locked = False
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "username": self.username,
            "uid": self.uid,
            "gid": self.gid,
            "full_name": self.full_name,
            "password_hash": self.password_hash,
            "home_dir": self.home_dir,
            "shell": self.shell,
            "groups": self.groups,
            "last_password_change": self.last_password_change,
            "account_expires": self.account_expires,
            "locked": self.locked
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
            
        Returns:
            User instance
        """
        user = cls(
            username=data["username"],
            uid=data["uid"],
            gid=data["gid"],
            full_name=data["full_name"],
            password_hash=data["password_hash"],
            home_dir=data["home_dir"],
            shell=data["shell"],
            groups=data["groups"]
        )
        
        user.last_password_change = data.get("last_password_change", time.time())
        user.account_expires = data.get("account_expires")
        user.locked = data.get("locked", False)
        
        return user

class Group:
    """Group class representing a system group"""
    
    def __init__(self, name: str, gid: int, members: List[str] = None):
        """
        Initialize a new group
        
        Args:
            name: Group name
            gid: Group ID
            members: Group members
        """
        self.name = name
        self.gid = gid
        self.members = members or []
    
    def add_member(self, username: str) -> bool:
        """
        Add member to group
        
        Args:
            username: Username to add
            
        Returns:
            Success status
        """
        if username not in self.members:
            self.members.append(username)
            return True
        
        return False
    
    def remove_member(self, username: str) -> bool:
        """
        Remove member from group
        
        Args:
            username: Username to remove
            
        Returns:
            Success status
        """
        if username in self.members:
            self.members.remove(username)
            return True
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "gid": self.gid,
            "members": self.members
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Group':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
            
        Returns:
            Group instance
        """
        return cls(
            name=data["name"],
            gid=data["gid"],
            members=data["members"]
        )

class UserManager:
    """Manager for user operations"""
    
    @staticmethod
    def create_user(username: str, password: str = None, uid: int = None, 
                   gid: int = None, full_name: str = "", home_dir: str = None,
                   shell: str = DEFAULT_SHELL, groups: List[str] = None,
                   system_user: bool = False) -> Tuple[bool, str, Optional[User]]:
        """
        Create a new user
        
        Args:
            username: Username
            password: Password (None for no password)
            uid: User ID (None for auto-assign)
            gid: Primary group ID (None for same as UID)
            full_name: Full name
            home_dir: Home directory
            shell: Login shell
            groups: Additional groups
            system_user: Whether user is a system user
            
        Returns:
            (success, message, user)
        """
        # Validate username
        if not username or not username.isalnum():
            return False, "Invalid username", None
        
        with USER_LOCK:
            # Check if username already exists
            for user in USERS.values():
                if user.username == username:
                    return False, f"User '{username}' already exists", None
            
            # Auto-assign UID if not provided
            if uid is None:
                if system_user:
                    uid = UserManager._find_next_id(SYSTEM_UID_RANGE[0], SYSTEM_UID_RANGE[1], 
                                                  [u.uid for u in USERS.values()])
                else:
                    uid = UserManager._find_next_id(MIN_UID, MAX_ID, 
                                                  [u.uid for u in USERS.values()])
            
            # Check if UID already exists
            for user in USERS.values():
                if user.uid == uid:
                    return False, f"UID {uid} already exists", None
            
            # Auto-assign GID if not provided (create group with same name)
            if gid is None:
                # Try to create a group with the same name
                success, msg, group = GroupManager.create_group(username, None, system_user)
                if success:
                    gid = group.gid
                else:
                    # If that fails, use the same as UID
                    gid = uid
            
            # Create user
            user = User(
                username=username,
                uid=uid,
                gid=gid,
                full_name=full_name,
                home_dir=home_dir,
                shell=shell,
                groups=groups
            )
            
            # Set password if provided
            if password is not None:
                user.set_password(password)
            
            # Add to registry
            USERS[uid] = user
            
            # Add user to additional groups
            if groups:
                for group_name in groups:
                    group = GroupManager.get_group_by_name(group_name)
                    if group:
                        group.add_member(username)
            
            return True, f"User '{username}' created", user
    
    @staticmethod
    def delete_user(username: str, remove_home: bool = False) -> Tuple[bool, str]:
        """
        Delete a user
        
        Args:
            username: Username
            remove_home: Whether to remove home directory
            
        Returns:
            (success, message)
        """
        with USER_LOCK:
            # Find user
            user = None
            uid = None
            for u_id, u in USERS.items():
                if u.username == username:
                    user = u
                    uid = u_id
                    break
            
            if not user:
                return False, f"User '{username}' not found"
            
            # Remove user from groups
            with GROUP_LOCK:
                for group in GROUPS.values():
                    if username in group.members:
                        group.remove_member(username)
            
            # Remove user
            del USERS[uid]
            
            # TODO: In a real implementation, we would remove the home directory
            # if remove_home is True
            
            return True, f"User '{username}' deleted"
    
    @staticmethod
    def modify_user(username: str, password: str = None, uid: int = None,
                   gid: int = None, full_name: str = None, home_dir: str = None,
                   shell: str = None, groups: List[str] = None) -> Tuple[bool, str]:
        """
        Modify a user
        
        Args:
            username: Username
            password: New password (None to keep current)
            uid: New UID (None to keep current)
            gid: New GID (None to keep current)
            full_name: New full name (None to keep current)
            home_dir: New home directory (None to keep current)
            shell: New login shell (None to keep current)
            groups: New additional groups (None to keep current)
            
        Returns:
            (success, message)
        """
        with USER_LOCK:
            # Find user
            user = None
            old_uid = None
            for u_id, u in USERS.items():
                if u.username == username:
                    user = u
                    old_uid = u_id
                    break
            
            if not user:
                return False, f"User '{username}' not found"
            
            # Change UID if requested
            if uid is not None and uid != old_uid:
                # Check if new UID already exists
                if uid in USERS:
                    return False, f"UID {uid} already exists"
                
                # Update UID
                USERS[uid] = user
                del USERS[old_uid]
                user.uid = uid
            
            # Change GID if requested
            if gid is not None:
                user.gid = gid
            
            # Change full name if requested
            if full_name is not None:
                user.full_name = full_name
            
            # Change home directory if requested
            if home_dir is not None:
                user.home_dir = home_dir
            
            # Change shell if requested
            if shell is not None:
                user.shell = shell
            
            # Change password if requested
            if password is not None:
                user.set_password(password)
            
            # Change groups if requested
            if groups is not None:
                # Remove from old groups
                with GROUP_LOCK:
                    for group in GROUPS.values():
                        if username in group.members:
                            group.remove_member(username)
                
                # Add to new groups
                for group_name in groups:
                    group = GroupManager.get_group_by_name(group_name)
                    if group:
                        group.add_member(username)
                
                user.groups = groups
            
            return True, f"User '{username}' modified"
    
    @staticmethod
    def get_user_by_name(username: str) -> Optional[User]:
        """
        Get user by username
        
        Args:
            username: Username
            
        Returns:
            User or None if not found
        """
        with USER_LOCK:
            for user in USERS.values():
                if user.username == username:
                    return user
            
            return None
    
    @staticmethod
    def get_user_by_uid(uid: int) -> Optional[User]:
        """
        Get user by UID
        
        Args:
            uid: User ID
            
        Returns:
            User or None if not found
        """
        with USER_LOCK:
            return USERS.get(uid)
    
    @staticmethod
    def list_users() -> List[User]:
        """
        List all users
        
        Returns:
            List of users
        """
        with USER_LOCK:
            return list(USERS.values())
    
    @staticmethod
    def save_users(filepath: str) -> Tuple[bool, str]:
        """
        Save users to file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            with USER_LOCK:
                data = {uid: user.to_dict() for uid, user in USERS.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Users saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save users: {str(e)}"
    
    @staticmethod
    def load_users(filepath: str) -> Tuple[bool, str]:
        """
        Load users from file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with USER_LOCK:
                USERS.clear()
                for uid, user_data in data.items():
                    USERS[int(uid)] = User.from_dict(user_data)
            
            return True, f"Users loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load users: {str(e)}"
    
    @staticmethod
    def _find_next_id(min_id: int, max_id: int, existing_ids: List[int]) -> int:
        """
        Find next available ID
        
        Args:
            min_id: Minimum ID
            max_id: Maximum ID
            existing_ids: List of existing IDs
            
        Returns:
            Next available ID
        """
        for i in range(min_id, max_id + 1):
            if i not in existing_ids:
                return i
        
        raise ValueError(f"No available IDs in range {min_id}-{max_id}")

class GroupManager:
    """Manager for group operations"""
    
    @staticmethod
    def create_group(name: str, gid: int = None, system_group: bool = False) -> Tuple[bool, str, Optional[Group]]:
        """
        Create a new group
        
        Args:
            name: Group name
            gid: Group ID (None for auto-assign)
            system_group: Whether group is a system group
            
        Returns:
            (success, message, group)
        """
        # Validate name
        if not name or not name.isalnum():
            return False, "Invalid group name", None
        
        with GROUP_LOCK:
            # Check if name already exists
            for group in GROUPS.values():
                if group.name == name:
                    return False, f"Group '{name}' already exists", None
            
            # Auto-assign GID if not provided
            if gid is None:
                if system_group:
                    gid = GroupManager._find_next_id(SYSTEM_GID_RANGE[0], SYSTEM_GID_RANGE[1], 
                                                    [g.gid for g in GROUPS.values()])
                else:
                    gid = GroupManager._find_next_id(MIN_GID, MAX_ID, 
                                                    [g.gid for g in GROUPS.values()])
            
            # Check if GID already exists
            for group in GROUPS.values():
                if group.gid == gid:
                    return False, f"GID {gid} already exists", None
            
            # Create group
            group = Group(
                name=name,
                gid=gid
            )
            
            # Add to registry
            GROUPS[gid] = group
            
            return True, f"Group '{name}' created", group
    
    @staticmethod
    def delete_group(name: str) -> Tuple[bool, str]:
        """
        Delete a group
        
        Args:
            name: Group name
            
        Returns:
            (success, message)
        """
        with GROUP_LOCK:
            # Find group
            group = None
            gid = None
            for g_id, g in GROUPS.items():
                if g.name == name:
                    group = g
                    gid = g_id
                    break
            
            if not group:
                return False, f"Group '{name}' not found"
            
            # Check if any user has this as primary group
            with USER_LOCK:
                for user in USERS.values():
                    if user.gid == gid:
                        return False, f"Cannot delete group: used as primary group for user '{user.username}'"
            
            # Remove group
            del GROUPS[gid]
            
            # Remove from users' additional groups
            with USER_LOCK:
                for user in USERS.values():
                    if name in user.groups:
                        user.groups.remove(name)
            
            return True, f"Group '{name}' deleted"
    
    @staticmethod
    def modify_group(name: str, new_name: str = None, gid: int = None, 
                    members: List[str] = None) -> Tuple[bool, str]:
        """
        Modify a group
        
        Args:
            name: Group name
            new_name: New group name (None to keep current)
            gid: New GID (None to keep current)
            members: New members list (None to keep current)
            
        Returns:
            (success, message)
        """
        with GROUP_LOCK:
            # Find group
            group = None
            old_gid = None
            for g_id, g in GROUPS.items():
                if g.name == name:
                    group = g
                    old_gid = g_id
                    break
            
            if not group:
                return False, f"Group '{name}' not found"
            
            # Change name if requested
            if new_name is not None:
                # Check if new name already exists
                for g in GROUPS.values():
                    if g.name == new_name and g.gid != old_gid:
                        return False, f"Group '{new_name}' already exists"
                
                # Update name
                group.name = new_name
                
                # Update in users' additional groups
                with USER_LOCK:
                    for user in USERS.values():
                        if name in user.groups:
                            user.groups.remove(name)
                            user.groups.append(new_name)
            
            # Change GID if requested
            if gid is not None and gid != old_gid:
                # Check if new GID already exists
                if gid in GROUPS:
                    return False, f"GID {gid} already exists"
                
                # Update GID
                GROUPS[gid] = group
                del GROUPS[old_gid]
                group.gid = gid
                
                # Update users' primary groups
                with USER_LOCK:
                    for user in USERS.values():
                        if user.gid == old_gid:
                            user.gid = gid
            
            # Change members if requested
            if members is not None:
                group.members = members
            
            return True, f"Group '{name}' modified"
    
    @staticmethod
    def get_group_by_name(name: str) -> Optional[Group]:
        """
        Get group by name
        
        Args:
            name: Group name
            
        Returns:
            Group or None if not found
        """
        with GROUP_LOCK:
            for group in GROUPS.values():
                if group.name == name:
                    return group
            
            return None
    
    @staticmethod
    def get_group_by_gid(gid: int) -> Optional[Group]:
        """
        Get group by GID
        
        Args:
            gid: Group ID
            
        Returns:
            Group or None if not found
        """
        with GROUP_LOCK:
            return GROUPS.get(gid)
    
    @staticmethod
    def list_groups() -> List[Group]:
        """
        List all groups
        
        Returns:
            List of groups
        """
        with GROUP_LOCK:
            return list(GROUPS.values())
    
    @staticmethod
    def save_groups(filepath: str) -> Tuple[bool, str]:
        """
        Save groups to file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            with GROUP_LOCK:
                data = {gid: group.to_dict() for gid, group in GROUPS.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Groups saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save groups: {str(e)}"
    
    @staticmethod
    def load_groups(filepath: str) -> Tuple[bool, str]:
        """
        Load groups from file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with GROUP_LOCK:
                GROUPS.clear()
                for gid, group_data in data.items():
                    GROUPS[int(gid)] = Group.from_dict(group_data)
            
            return True, f"Groups loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load groups: {str(e)}"
    
    @staticmethod
    def _find_next_id(min_id: int, max_id: int, existing_ids: List[int]) -> int:
        """
        Find next available ID
        
        Args:
            min_id: Minimum ID
            max_id: Maximum ID
            existing_ids: List of existing IDs
            
        Returns:
            Next available ID
        """
        for i in range(min_id, max_id + 1):
            if i not in existing_ids:
                return i
        
        raise ValueError(f"No available IDs in range {min_id}-{max_id}")

def initialize():
    """Initialize user and group management system"""
    logger.info("Initializing user and group management system")
    
    # Create security directory
    security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(security_dir, exist_ok=True)
    
    # Create default users and groups if not already loaded
    with USER_LOCK, GROUP_LOCK:
        if not USERS and not GROUPS:
            # Create root group
            GroupManager.create_group("root", ROOT_GID, True)
            
            # Create system groups
            GroupManager.create_group("wheel", 10, True)  # Admin group
            GroupManager.create_group("daemon", 2, True)
            GroupManager.create_group("sys", 3, True)
            
            # Create root user
            UserManager.create_user(
                username="root",
                uid=ROOT_UID,
                gid=ROOT_GID,
                full_name="Root User",
                home_dir="/root",
                groups=["wheel"],
                system_user=True
            )
    
    # Load users and groups if they exist
    users_db = os.path.join(security_dir, 'users.json')
    if os.path.exists(users_db):
        UserManager.load_users(users_db)
    else:
        UserManager.save_users(users_db)
    
    groups_db = os.path.join(security_dir, 'groups.json')
    if os.path.exists(groups_db):
        GroupManager.load_groups(groups_db)
    else:
        GroupManager.save_groups(groups_db)
    
    logger.info("User and group management system initialized")

# Initialize system
initialize()

# Patch Python's built-in pwd and grp modules to use our user/group database
# This allows standard libraries to use our user/group database
class PwdPatch:
    @staticmethod
    def getpwnam(name):
        user = UserManager.get_user_by_name(name)
        if not user:
            raise KeyError(f"getpwnam(): name not found: {name}")
        
        return pwd.struct_passwd((
            user.username,
            'x',  # Password placeholder
            user.uid,
            user.gid,
            user.full_name,
            user.home_dir,
            user.shell
        ))
    
    @staticmethod
    def getpwuid(uid):
        user = UserManager.get_user_by_uid(uid)
        if not user:
            raise KeyError(f"getpwuid(): uid not found: {uid}")
        
        return pwd.struct_passwd((
            user.username,
            'x',  # Password placeholder
            user.uid,
            user.gid,
            user.full_name,
            user.home_dir,
            user.shell
        ))
    
    @staticmethod
    def getpwall():
        return [PwdPatch.getpwuid(user.uid) for user in UserManager.list_users()]

class GrpPatch:
    @staticmethod
    def getgrnam(name):
        group = GroupManager.get_group_by_name(name)
        if not group:
            raise KeyError(f"getgrnam(): name not found: {name}")
        
        return grp.struct_group((
            group.name,
            'x',  # Password placeholder
            group.gid,
            group.members
        ))
    
    @staticmethod
    def getgrgid(gid):
        group = GroupManager.get_group_by_gid(gid)
        if not group:
            raise KeyError(f"getgrgid(): gid not found: {gid}")
        
        return grp.struct_group((
            group.name,
            'x',  # Password placeholder
            group.gid,
            group.members
        ))
    
    @staticmethod
    def getgrall():
        return [GrpPatch.getgrgid(group.gid) for group in GroupManager.list_groups()]

# Apply patches
pwd.getpwnam = PwdPatch.getpwnam
pwd.getpwuid = PwdPatch.getpwuid
pwd.getpwall = PwdPatch.getpwall

grp.getgrnam = GrpPatch.getgrnam
grp.getgrgid = GrpPatch.getgrgid
grp.getgrall = GrpPatch.getgrall

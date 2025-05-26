"""
User and Group Management for KOS

This module provides Unix-like user and group management features including:
- User account creation, modification, and deletion
- Group management and membership
- Password management with secure hashing
- Home directory management
- User metadata and configuration
"""

import os
import json
import time
import uuid
import shutil
import bcrypt
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
USERS_DB_PATH = os.path.join(KOS_ROOT, 'security/users.json')
GROUPS_DB_PATH = os.path.join(KOS_ROOT, 'security/groups.json')
SHADOW_DB_PATH = os.path.join(KOS_ROOT, 'security/shadow.json')
HOME_BASE_PATH = os.path.join(KOS_ROOT, 'home')

# Ensure directories exist
os.makedirs(os.path.dirname(USERS_DB_PATH), exist_ok=True)
os.makedirs(HOME_BASE_PATH, exist_ok=True)

# Default configuration
DEFAULT_SHELL = '/bin/kosh'
MIN_UID = 1000
MIN_GID = 1000
SYSTEM_USERS_MAX_UID = 999
SYSTEM_GROUPS_MAX_GID = 999

# Logging setup
logger = logging.getLogger(__name__)


class UserManager:
    """Manages user accounts in KOS, providing Unix-like user management features."""
    
    def __init__(self):
        """Initialize the UserManager."""
        self.users = self._load_users()
        self.shadow = self._load_shadow()
        self._ensure_system_users()
    
    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load users database from disk."""
        if os.path.exists(USERS_DB_PATH):
            try:
                with open(USERS_DB_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted users database. Creating new one.")
        return {}
    
    def _load_shadow(self) -> Dict[str, Dict[str, Any]]:
        """Load shadow password database from disk."""
        if os.path.exists(SHADOW_DB_PATH):
            try:
                with open(SHADOW_DB_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted shadow database. Creating new one.")
        return {}
    
    def _save_users(self):
        """Save users database to disk."""
        os.makedirs(os.path.dirname(USERS_DB_PATH), exist_ok=True)
        with open(USERS_DB_PATH, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def _save_shadow(self):
        """Save shadow password database to disk."""
        os.makedirs(os.path.dirname(SHADOW_DB_PATH), exist_ok=True)
        with open(SHADOW_DB_PATH, 'w') as f:
            json.dump(self.shadow, f, indent=2)
    
    def _ensure_system_users(self):
        """Ensure that system users exist."""
        system_users = {
            'root': {'uid': 0, 'gid': 0, 'home': '/root', 'shell': DEFAULT_SHELL, 
                     'gecos': 'root', 'password': 'x'},
            'nobody': {'uid': 65534, 'gid': 65534, 'home': '/nonexistent', 
                       'shell': '/bin/false', 'gecos': 'nobody', 'password': '*'}
        }
        
        for username, data in system_users.items():
            if username not in self.users:
                self.users[username] = data
                if username == 'root' and username not in self.shadow:
                    # Set a locked password for root initially
                    self.shadow[username] = {
                        'password': '!',
                        'last_changed': int(time.time() // 86400),
                        'min_days': 0,
                        'max_days': 99999,
                        'warn_days': 7,
                        'inactive_days': -1,
                        'expiration': -1
                    }
        
        self._save_users()
        self._save_shadow()
    
    def get_next_uid(self) -> int:
        """Get the next available UID."""
        uids = [user['uid'] for user in self.users.values()]
        if not uids:
            return MIN_UID
        return max([uid for uid in uids if uid >= MIN_UID], default=MIN_UID - 1) + 1
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user information by username."""
        return self.users.get(username)
    
    def get_user_by_uid(self, uid: int) -> Optional[Dict[str, Any]]:
        """Get user information by UID."""
        for username, data in self.users.items():
            if data['uid'] == uid:
                return {**data, 'username': username}
        return None
    
    def create_user(self, username: str, password: Optional[str] = None, 
                   uid: Optional[int] = None, gid: Optional[int] = None,
                   gecos: str = '', home: Optional[str] = None, 
                   shell: str = DEFAULT_SHELL, system_user: bool = False) -> bool:
        """
        Create a new user account.
        
        Args:
            username: The username for the new account
            password: The password (plaintext, will be hashed)
            uid: User ID (optional, will be auto-assigned)
            gid: Primary group ID (optional, will create a group with same name)
            gecos: GECOS information (name, contact, etc.)
            home: Home directory (optional, will be auto-created)
            shell: Login shell
            system_user: Whether this is a system user (UID < 1000)
            
        Returns:
            bool: Success or failure
        """
        # Validation
        if username in self.users:
            logger.error(f"User '{username}' already exists")
            return False
        
        if not username.isalnum() and '_' not in username and '-' not in username:
            logger.error(f"Invalid username '{username}'")
            return False
        
        # Assign UID
        if uid is None:
            if system_user:
                uids = [u['uid'] for u in self.users.values() 
                       if u['uid'] <= SYSTEM_USERS_MAX_UID]
                uid = max(uids, default=0) + 1 if uids else 100
            else:
                uid = self.get_next_uid()
        elif self.get_user_by_uid(uid):
            logger.error(f"UID {uid} is already in use")
            return False
        
        # Create primary group if needed
        group_manager = GroupManager()
        if gid is None:
            # Create a group with the same name
            if not group_manager.create_group(username, gid=uid):
                logger.error(f"Failed to create primary group for '{username}'")
                return False
            gid = uid
        
        # Set home directory
        if home is None:
            home = f"{HOME_BASE_PATH}/{username}"
        
        # Create user record
        self.users[username] = {
            'uid': uid,
            'gid': gid,
            'gecos': gecos,
            'home': home,
            'shell': shell,
            'password': 'x'  # Shadow password indicator
        }
        
        # Create shadow record
        self.shadow[username] = {
            'password': '!' if password is None else self._hash_password(password),
            'last_changed': int(time.time() // 86400),
            'min_days': 0,
            'max_days': 99999,
            'warn_days': 7,
            'inactive_days': -1,
            'expiration': -1
        }
        
        # Create home directory
        try:
            if not os.path.exists(home):
                os.makedirs(home, exist_ok=True)
                # Copy skeleton files
                skel_dir = os.path.join(KOS_ROOT, 'etc/skel')
                if os.path.exists(skel_dir):
                    for item in os.listdir(skel_dir):
                        s = os.path.join(skel_dir, item)
                        d = os.path.join(home, item)
                        if os.path.isdir(s):
                            shutil.copytree(s, d, dirs_exist_ok=True)
                        else:
                            shutil.copy2(s, d)
                
                # Set ownership
                # In a real system, we'd use os.chown here
                logger.info(f"Would set ownership of {home} to {uid}:{gid}")
        except Exception as e:
            logger.error(f"Failed to create home directory: {e}")
        
        # Save changes
        self._save_users()
        self._save_shadow()
        
        logger.info(f"Created user '{username}' (UID: {uid}, GID: {gid})")
        return True
    
    def modify_user(self, username: str, **kwargs) -> bool:
        """
        Modify a user account.
        
        Args:
            username: The username to modify
            **kwargs: Attributes to modify (uid, gid, gecos, home, shell, password)
            
        Returns:
            bool: Success or failure
        """
        if username not in self.users:
            logger.error(f"User '{username}' does not exist")
            return False
        
        user = self.users[username]
        
        # Handle special attributes
        if 'password' in kwargs:
            password = kwargs.pop('password')
            self.shadow[username]['password'] = self._hash_password(password)
            self.shadow[username]['last_changed'] = int(time.time() // 86400)
        
        if 'home' in kwargs and kwargs['home'] != user['home']:
            old_home = user['home']
            new_home = kwargs['home']
            move_files = kwargs.pop('move_files', False)
            
            if move_files and os.path.exists(old_home):
                try:
                    os.makedirs(os.path.dirname(new_home), exist_ok=True)
                    shutil.move(old_home, new_home)
                except Exception as e:
                    logger.error(f"Failed to move home directory: {e}")
            elif not os.path.exists(new_home):
                try:
                    os.makedirs(new_home, exist_ok=True)
                except Exception as e:
                    logger.error(f"Failed to create new home directory: {e}")
        
        # Update user attributes
        for key, value in kwargs.items():
            if key in user:
                user[key] = value
        
        # Save changes
        self._save_users()
        self._save_shadow()
        
        logger.info(f"Modified user '{username}'")
        return True
    
    def delete_user(self, username: str, remove_home: bool = False) -> bool:
        """
        Delete a user account.
        
        Args:
            username: The username to delete
            remove_home: Whether to remove the user's home directory
            
        Returns:
            bool: Success or failure
        """
        if username not in self.users:
            logger.error(f"User '{username}' does not exist")
            return False
        
        if username == 'root':
            logger.error("Cannot delete the root user")
            return False
        
        user = self.users[username]
        
        # Remove home directory if requested
        if remove_home and os.path.exists(user['home']):
            try:
                shutil.rmtree(user['home'])
            except Exception as e:
                logger.error(f"Failed to remove home directory: {e}")
        
        # Remove user from groups
        group_manager = GroupManager()
        for group_name, group_data in group_manager.groups.items():
            if 'members' in group_data and username in group_data['members']:
                group_data['members'].remove(username)
        
        group_manager._save_groups()
        
        # Delete user record
        del self.users[username]
        if username in self.shadow:
            del self.shadow[username]
        
        # Save changes
        self._save_users()
        self._save_shadow()
        
        logger.info(f"Deleted user '{username}'")
        return True
    
    def set_password(self, username: str, password: str) -> bool:
        """
        Set or change a user's password.
        
        Args:
            username: The username to modify
            password: The new password (plaintext, will be hashed)
            
        Returns:
            bool: Success or failure
        """
        if username not in self.users:
            logger.error(f"User '{username}' does not exist")
            return False
        
        if username not in self.shadow:
            self.shadow[username] = {
                'last_changed': int(time.time() // 86400),
                'min_days': 0,
                'max_days': 99999,
                'warn_days': 7,
                'inactive_days': -1,
                'expiration': -1
            }
        
        self.shadow[username]['password'] = self._hash_password(password)
        self.shadow[username]['last_changed'] = int(time.time() // 86400)
        
        self._save_shadow()
        
        logger.info(f"Password changed for user '{username}'")
        return True
    
    def verify_password(self, username: str, password: str) -> bool:
        """
        Verify a user's password.
        
        Args:
            username: The username to check
            password: The password to verify
            
        Returns:
            bool: Whether the password is correct
        """
        if username not in self.users or username not in self.shadow:
            return False
        
        shadow_entry = self.shadow[username]
        hashed = shadow_entry['password']
        
        # Check for locked accounts
        if hashed.startswith('!') or hashed == '*':
            return False
        
        # Check password
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed.encode('utf-8')
            )
        except Exception:
            return False
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    def lock_account(self, username: str) -> bool:
        """
        Lock a user account.
        
        Args:
            username: The username to lock
            
        Returns:
            bool: Success or failure
        """
        if username not in self.users or username not in self.shadow:
            logger.error(f"User '{username}' does not exist")
            return False
        
        shadow_entry = self.shadow[username]
        if not shadow_entry['password'].startswith('!'):
            shadow_entry['password'] = '!' + shadow_entry['password']
        
        self._save_shadow()
        
        logger.info(f"Locked account for user '{username}'")
        return True
    
    def unlock_account(self, username: str) -> bool:
        """
        Unlock a user account.
        
        Args:
            username: The username to unlock
            
        Returns:
            bool: Success or failure
        """
        if username not in self.users or username not in self.shadow:
            logger.error(f"User '{username}' does not exist")
            return False
        
        shadow_entry = self.shadow[username]
        if shadow_entry['password'].startswith('!'):
            shadow_entry['password'] = shadow_entry['password'][1:]
        
        self._save_shadow()
        
        logger.info(f"Unlocked account for user '{username}'")
        return True


class GroupManager:
    """Manages groups in KOS, providing Unix-like group management features."""
    
    def __init__(self):
        """Initialize the GroupManager."""
        self.groups = self._load_groups()
        self._ensure_system_groups()
    
    def _load_groups(self) -> Dict[str, Dict[str, Any]]:
        """Load groups database from disk."""
        if os.path.exists(GROUPS_DB_PATH):
            try:
                with open(GROUPS_DB_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted groups database. Creating new one.")
        return {}
    
    def _save_groups(self):
        """Save groups database to disk."""
        os.makedirs(os.path.dirname(GROUPS_DB_PATH), exist_ok=True)
        with open(GROUPS_DB_PATH, 'w') as f:
            json.dump(self.groups, f, indent=2)
    
    def _ensure_system_groups(self):
        """Ensure that system groups exist."""
        system_groups = {
            'root': {'gid': 0, 'members': []},
            'daemon': {'gid': 1, 'members': []},
            'bin': {'gid': 2, 'members': []},
            'sys': {'gid': 3, 'members': []},
            'adm': {'gid': 4, 'members': []},
            'wheel': {'gid': 10, 'members': []},
            'nogroup': {'gid': 65534, 'members': []}
        }
        
        for groupname, data in system_groups.items():
            if groupname not in self.groups:
                self.groups[groupname] = data
        
        self._save_groups()
    
    def get_next_gid(self) -> int:
        """Get the next available GID."""
        gids = [group['gid'] for group in self.groups.values()]
        if not gids:
            return MIN_GID
        return max([gid for gid in gids if gid >= MIN_GID], default=MIN_GID - 1) + 1
    
    def get_group(self, groupname: str) -> Optional[Dict[str, Any]]:
        """Get group information by group name."""
        return self.groups.get(groupname)
    
    def get_group_by_gid(self, gid: int) -> Optional[Dict[str, Any]]:
        """Get group information by GID."""
        for groupname, data in self.groups.items():
            if data['gid'] == gid:
                return {**data, 'groupname': groupname}
        return None
    
    def create_group(self, groupname: str, gid: Optional[int] = None, 
                    system_group: bool = False) -> bool:
        """
        Create a new group.
        
        Args:
            groupname: The group name
            gid: Group ID (optional, will be auto-assigned)
            system_group: Whether this is a system group (GID < 1000)
            
        Returns:
            bool: Success or failure
        """
        # Validation
        if groupname in self.groups:
            logger.error(f"Group '{groupname}' already exists")
            return False
        
        if not groupname.isalnum() and '_' not in groupname and '-' not in groupname:
            logger.error(f"Invalid group name '{groupname}'")
            return False
        
        # Assign GID
        if gid is None:
            if system_group:
                gids = [g['gid'] for g in self.groups.values() 
                       if g['gid'] <= SYSTEM_GROUPS_MAX_GID]
                gid = max(gids, default=0) + 1 if gids else 100
            else:
                gid = self.get_next_gid()
        elif self.get_group_by_gid(gid):
            logger.error(f"GID {gid} is already in use")
            return False
        
        # Create group record
        self.groups[groupname] = {
            'gid': gid,
            'members': []
        }
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Created group '{groupname}' (GID: {gid})")
        return True
    
    def delete_group(self, groupname: str) -> bool:
        """
        Delete a group.
        
        Args:
            groupname: The group name to delete
            
        Returns:
            bool: Success or failure
        """
        if groupname not in self.groups:
            logger.error(f"Group '{groupname}' does not exist")
            return False
        
        if groupname in ['root', 'nogroup']:
            logger.error(f"Cannot delete system group '{groupname}'")
            return False
        
        # Check if any user has this as their primary group
        user_manager = UserManager()
        for username, user_data in user_manager.users.items():
            if user_data['gid'] == self.groups[groupname]['gid']:
                logger.error(f"Cannot delete group '{groupname}' - it is the primary group for user '{username}'")
                return False
        
        # Delete group record
        del self.groups[groupname]
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Deleted group '{groupname}'")
        return True
    
    def add_user_to_group(self, username: str, groupname: str) -> bool:
        """
        Add a user to a group.
        
        Args:
            username: The username to add
            groupname: The group name to add the user to
            
        Returns:
            bool: Success or failure
        """
        if groupname not in self.groups:
            logger.error(f"Group '{groupname}' does not exist")
            return False
        
        user_manager = UserManager()
        if username not in user_manager.users:
            logger.error(f"User '{username}' does not exist")
            return False
        
        group = self.groups[groupname]
        if 'members' not in group:
            group['members'] = []
        
        if username in group['members']:
            logger.info(f"User '{username}' is already a member of group '{groupname}'")
            return True
        
        group['members'].append(username)
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Added user '{username}' to group '{groupname}'")
        return True
    
    def remove_user_from_group(self, username: str, groupname: str) -> bool:
        """
        Remove a user from a group.
        
        Args:
            username: The username to remove
            groupname: The group name to remove the user from
            
        Returns:
            bool: Success or failure
        """
        if groupname not in self.groups:
            logger.error(f"Group '{groupname}' does not exist")
            return False
        
        group = self.groups[groupname]
        if 'members' not in group or username not in group['members']:
            logger.info(f"User '{username}' is not a member of group '{groupname}'")
            return True
        
        group['members'].remove(username)
        
        # Save changes
        self._save_groups()
        
        logger.info(f"Removed user '{username}' from group '{groupname}'")
        return True
    
    def get_user_groups(self, username: str) -> List[str]:
        """
        Get all groups a user belongs to.
        
        Args:
            username: The username to check
            
        Returns:
            List[str]: List of group names the user belongs to
        """
        result = []
        for groupname, group_data in self.groups.items():
            if 'members' in group_data and username in group_data['members']:
                result.append(groupname)
        
        # Add primary group
        user_manager = UserManager()
        user = user_manager.get_user(username)
        if user:
            primary_gid = user['gid']
            for groupname, group_data in self.groups.items():
                if group_data['gid'] == primary_gid and groupname not in result:
                    result.append(groupname)
        
        return result

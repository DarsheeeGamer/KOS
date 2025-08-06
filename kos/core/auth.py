"""
User authentication and management for KOS
"""

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set
from enum import Enum

class UserRole(Enum):
    """User roles in the system"""
    ROOT = "root"
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

@dataclass
class User:
    """User account information"""
    username: str
    uid: int
    gid: int
    role: UserRole
    home_dir: str
    shell: str = "/bin/ksh"
    password_hash: str = ""
    groups: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_login: Optional[float] = None
    locked: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['role'] = self.role.value
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        """Create from dictionary"""
        data['role'] = UserRole(data['role'])
        return cls(**data)

@dataclass
class Group:
    """User group information"""
    name: str
    gid: int
    members: List[str] = field(default_factory=list)
    
class AuthManager:
    """Manages user authentication and authorization"""
    
    def __init__(self, vfs):
        self.vfs = vfs
        self.current_user: Optional[User] = None
        self.users: Dict[str, User] = {}
        self.groups: Dict[str, Group] = {}
        self.sessions: Dict[str, dict] = {}  # session_id -> session_data
        
        # File paths
        self.passwd_file = "/etc/passwd"
        self.shadow_file = "/etc/shadow"
        self.group_file = "/etc/group"
        
        self._init_auth_system()
        self._load_users()
    
    def _init_auth_system(self):
        """Initialize authentication system files"""
        # Create /etc directory if needed
        if self.vfs and not self.vfs.exists("/etc"):
            self.vfs.mkdir("/etc")
        
        # Create default root user if no users exist
        if self.vfs and not self.vfs.exists(self.passwd_file):
            root_user = User(
                username="root",
                uid=0,
                gid=0,
                role=UserRole.ROOT,
                home_dir="/root",
                password_hash=self._hash_password("root"),
                groups=["wheel", "root"]
            )
            
            default_user = User(
                username="user",
                uid=1000,
                gid=1000,
                role=UserRole.USER,
                home_dir="/home/user",
                password_hash=self._hash_password("user"),
                groups=["users"]
            )
            
            self.users = {
                "root": root_user,
                "user": default_user
            }
            
            # Create default groups
            self.groups = {
                "root": Group("root", 0, ["root"]),
                "wheel": Group("wheel", 10, ["root"]),
                "users": Group("users", 100, ["user"])
            }
            
            self._save_users()
            
            # Set default user as current
            self.current_user = default_user
    
    def _hash_password(self, password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def _load_users(self):
        """Load users from VFS"""
        if not self.vfs or not self.vfs.exists(self.passwd_file):
            return
        
        try:
            # Load passwd file
            with self.vfs.open(self.passwd_file, 'r') as f:
                passwd_data = json.loads(f.read().decode())
                
            # Load users
            for user_data in passwd_data.get('users', []):
                user = User.from_dict(user_data)
                self.users[user.username] = user
            
            # Load groups
            for group_data in passwd_data.get('groups', []):
                group = Group(**group_data)
                self.groups[group.name] = group
                
        except Exception as e:
            print(f"Warning: Could not load users: {e}")
    
    def _save_users(self):
        """Save users to VFS"""
        if not self.vfs:
            return
        
        try:
            # Prepare data
            passwd_data = {
                'users': [user.to_dict() for user in self.users.values()],
                'groups': [asdict(group) for group in self.groups.values()]
            }
            
            # Save to passwd file
            with self.vfs.open(self.passwd_file, 'w') as f:
                f.write(json.dumps(passwd_data, indent=2).encode())
                
        except Exception as e:
            print(f"Warning: Could not save users: {e}")
    
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        # Check if account is locked
        if user.locked:
            return False
        
        # Verify password
        if user.password_hash != self._hash_password(password):
            return False
        
        # Update last login
        user.last_login = time.time()
        self.current_user = user
        self._save_users()
        
        return True
    
    def logout(self):
        """Logout current user"""
        self.current_user = None
    
    def create_user(self, username: str, password: str, role: UserRole = UserRole.USER,
                   home_dir: Optional[str] = None, groups: Optional[List[str]] = None) -> Optional[User]:
        """Create a new user"""
        # Check if current user has permission
        if not self.current_user or self.current_user.role not in [UserRole.ROOT, UserRole.ADMIN]:
            raise PermissionError("Only root or admin can create users")
        
        # Check if user already exists
        if username in self.users:
            raise ValueError(f"User {username} already exists")
        
        # Generate UID (simple increment)
        max_uid = max([u.uid for u in self.users.values()], default=999)
        uid = max_uid + 1
        
        # Create user
        user = User(
            username=username,
            uid=uid,
            gid=uid,  # Primary group same as UID
            role=role,
            home_dir=home_dir or f"/home/{username}",
            password_hash=self._hash_password(password),
            groups=groups or ["users"]
        )
        
        self.users[username] = user
        
        # Create home directory
        if self.vfs and not self.vfs.exists(user.home_dir):
            self.vfs.mkdir(user.home_dir)
        
        self._save_users()
        return user
    
    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        # Check permissions
        if not self.current_user or self.current_user.role != UserRole.ROOT:
            raise PermissionError("Only root can delete users")
        
        # Don't delete root
        if username == "root":
            raise ValueError("Cannot delete root user")
        
        if username in self.users:
            del self.users[username]
            self._save_users()
            return True
        
        return False
    
    def change_password(self, username: str, old_password: str, new_password: str) -> bool:
        """Change user password"""
        if username not in self.users:
            return False
        
        user = self.users[username]
        
        # Verify old password (unless current user is root)
        if self.current_user and self.current_user.role != UserRole.ROOT:
            if user.password_hash != self._hash_password(old_password):
                return False
        
        # Set new password
        user.password_hash = self._hash_password(new_password)
        self._save_users()
        return True
    
    def add_to_group(self, username: str, group_name: str) -> bool:
        """Add user to a group"""
        if not self.current_user or self.current_user.role not in [UserRole.ROOT, UserRole.ADMIN]:
            raise PermissionError("Only root or admin can modify groups")
        
        if username not in self.users:
            return False
        
        user = self.users[username]
        if group_name not in user.groups:
            user.groups.append(group_name)
            
        if group_name in self.groups:
            group = self.groups[group_name]
            if username not in group.members:
                group.members.append(username)
        
        self._save_users()
        return True
    
    def has_permission(self, permission: str) -> bool:
        """Check if current user has a permission"""
        if not self.current_user:
            return False
        
        # Root has all permissions
        if self.current_user.role == UserRole.ROOT:
            return True
        
        # Check specific permissions based on role
        admin_perms = ["create_user", "modify_user", "install_package", "manage_services"]
        user_perms = ["read_files", "write_own_files", "run_commands"]
        
        if self.current_user.role == UserRole.ADMIN:
            return permission in admin_perms + user_perms
        elif self.current_user.role == UserRole.USER:
            return permission in user_perms
        else:  # GUEST
            return permission in ["read_files"]
    
    def get_current_user(self) -> Optional[User]:
        """Get current logged in user"""
        return self.current_user
    
    def list_users(self) -> List[User]:
        """List all users"""
        return list(self.users.values())
    
    def switch_user(self, username: str, password: Optional[str] = None) -> bool:
        """Switch to another user (su command)"""
        # Root can switch without password
        if self.current_user and self.current_user.role == UserRole.ROOT:
            if username in self.users:
                self.current_user = self.users[username]
                return True
        
        # Others need password
        if password and self.authenticate(username, password):
            return True
        
        return False
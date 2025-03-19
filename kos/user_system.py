"""KOS User System"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from .auth_manager import AuthenticationManager
from .filesystem import FileSystem
import logging

logger = logging.getLogger(__name__)

class UserSystem:
    ROOT_USERNAME = "kaede"
    ROOT_PASSWORD = "k123"  # Updated root password for sudo operations

    def __init__(self, filesystem: FileSystem = None, auth_manager: AuthenticationManager = None):
        self.users_file = "users.json"
        self.hostname = "kos"
        self.users: Dict = {}
        self.current_user: Optional[str] = None
        self.current_session: Optional[str] = None
        self.sudoers = set()
        self.filesystem = filesystem
        self.auth_manager = auth_manager or AuthenticationManager()
        self._initialize_system()

    def _initialize_system(self):
        """Initialize the user system with root user"""
        # Load existing users
        self.users = self._load_users()

        # Create basic filesystem structure if filesystem is available
        if self.filesystem:
            try:
                # Create /home directory if it doesn't exist
                if not self._get_node("/home"):
                    logger.debug("Creating /home directory")
                    self.filesystem.mkdir("/home")

                # Create /root directory if it doesn't exist
                if not self._get_node("/root"):
                    logger.debug("Creating /root directory")
                    self.filesystem.mkdir("/root")
            except Exception as e:
                logger.error(f"Failed to create basic directory structure: {e}")

        if not self.users:
            # Create root user if no users exist
            self.users = {
                self.ROOT_USERNAME: {
                    "password": self.auth_manager.hash_password(self.ROOT_PASSWORD),
                    "uid": 0,
                    "gid": 0,
                    "fullname": "Kaede Root",
                    "home": "/root",
                    "shell": "/bin/ksh",
                    "created_at": datetime.now().isoformat(),
                    "groups": ["root", "sudo", "admin"],
                    "is_root": True
                }
            }
            self._save_users()

        # Always ensure root has the correct password
        self.users[self.ROOT_USERNAME]["password"] = self.auth_manager.hash_password(self.ROOT_PASSWORD)
        self._save_users()

        # Create home directories for all existing users
        if self.filesystem:
            for username, user_info in self.users.items():
                if username != self.ROOT_USERNAME:  # Skip root user as it uses /root
                    home_dir = f"/home/{username}"
                    try:
                        if not self._get_node(home_dir):
                            logger.debug(f"Creating home directory for user {username}: {home_dir}")
                            self.filesystem.mkdir(home_dir)
                    except Exception as e:
                        logger.error(f"Failed to create home directory for {username}: {e}")

        # Set up initial root session
        self.current_user = self.ROOT_USERNAME
        self.current_session = self.auth_manager.create_session(self.ROOT_USERNAME)
        self.sudoers.add(self.ROOT_USERNAME)

    def _load_users(self) -> Dict:
        """Load users from file or return empty dict"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_users(self):
        """Save users to file"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)

    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate a user and create a session"""
        if username not in self.users:
            return False

        if not self.auth_manager.verify_password(self.users[username]["password"], password):
            return False

        self.current_session = self.auth_manager.create_session(username)
        self.current_user = username
        return True

    def switch_user(self, username: str, password: str = None) -> bool:
        """Switch to another user (su command)"""
        if username not in self.users:
            print(f"User {username} does not exist")
            return False

        # Root can switch to any user without password
        if self.current_user_is_root():
            self.current_session = self.auth_manager.create_session(username)
            self.current_user = username
            return True

        # Regular users need to authenticate
        if not password or not self.authenticate(username, password):
            print("Authentication failed")
            return False

        return True

    def logout(self) -> bool:
        """Log out current user"""
        if self.current_session:
            self.auth_manager.end_session(self.current_session)
            self.current_session = None
            self.current_user = None
            return True
        return False

    def current_user_is_root(self) -> bool:
        """Check if current user is root"""
        is_root = (self.current_user == self.ROOT_USERNAME or 
                  self.users.get(self.current_user, {}).get("is_root", False))
        logger.debug(f"Checking root privileges for {self.current_user}: {is_root}")
        return is_root

    def get_user_info(self, username: str = None) -> Dict:
        """Get user information"""
        username = username or self.current_user
        if not username or username not in self.users:
            return {
                "home": "/home/user",
                "groups": ["users"],
                "uid": 1000,
                "gid": 1000
            }
        return self.users[username]

    def get_prompt(self) -> str:
        """Get Linux-style prompt"""
        user = self.current_user or "user"
        cwd = self.get_current_directory()
        return f"{user}@{self.hostname}:{cwd}$ "

    def get_current_directory(self) -> str:
        """Get current working directory for prompt"""
        cwd = self.filesystem.pwd() if self.filesystem else "/"
        home = self.get_user_info().get("home", "/home/user")

        # Replace home directory with ~
        if cwd.startswith(home):
            cwd = "~" + cwd[len(home):]
        return cwd

    def get_groups(self, username: str = None) -> List[str]:
        """Get user's groups"""
        info = self.get_user_info(username)
        return info.get("groups", [])

    def can_sudo(self, username: str) -> bool:
        """Check if user has sudo privileges"""
        if not username:
            return False
        return username in self.sudoers or self.users.get(username, {}).get("is_root", False)

    def verify_sudo_password(self, username: str, password: str) -> bool:
        """Verify user's password for sudo"""
        if not username or username not in self.users:
            return False
        return self.auth_manager.verify_password(self.users[username]["password"], password)

    def add_user(self, username: str, password: str, groups: List[str] = None) -> bool:
        """Add a new user"""
        logger.debug(f"Adding user {username}, current user: {self.current_user}, is_root: {self.current_user_is_root()}")

        if username in self.users:
            # If user exists, check if their home directory exists
            if self.filesystem:
                home_dir = f"/home/{username}"
                if not self._get_node(home_dir):
                    try:
                        logger.debug(f"Creating missing home directory for existing user {username}: {home_dir}")
                        self.filesystem.mkdir(home_dir)
                    except Exception as e:
                        logger.error(f"Failed to create home directory for {username}: {e}")
            raise ValueError(f"User {username} already exists")

        if not self.current_user_is_root():
            raise PermissionError("Only root can add users")

        # Create new user
        next_uid = max([u.get('uid', 0) for u in self.users.values()]) + 1
        home_dir = f"/home/{username}"

        self.users[username] = {
            "password": self.auth_manager.hash_password(password),
            "uid": next_uid,
            "gid": next_uid,
            "fullname": username.capitalize(),
            "home": home_dir,
            "shell": "/bin/ksh",
            "created_at": datetime.now().isoformat(),
            "groups": groups or ["users"],
            "is_root": False
        }

        # Create user's home directory
        if self.filesystem:
            try:
                if not self._get_node(home_dir):
                    logger.debug(f"Creating home directory for new user {username}: {home_dir}")
                    self.filesystem.mkdir(home_dir)
            except Exception as e:
                logger.error(f"Failed to create home directory for {username}: {e}")

        self._save_users()
        logger.debug(f"Successfully added user {username}")
        return True

    def delete_user(self, username: str) -> bool:
        """Delete a user"""
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")

        if username == self.ROOT_USERNAME:
            raise ValueError("Cannot delete root user")

        if not self.current_user_is_root():
            raise PermissionError("Only root can delete users")

        del self.users[username]
        self._save_users()
        return True

    def set_hostname(self, new_hostname: str) -> bool:
        """Set system hostname"""
        if not self.current_user_is_root():
            raise PermissionError("Only root can change hostname")
        self.hostname = new_hostname
        return True

    def add_sudoer(self, username: str) -> bool:
        """Add user to sudoers"""
        if not self.current_user_is_root():
            raise PermissionError("Only root can modify sudoers")
        if username not in self.users:
            raise ValueError(f"User {username} does not exist")
        self.sudoers.add(username)
        return True

    def remove_sudoer(self, username: str) -> bool:
        """Remove user from sudoers"""
        if not self.current_user_is_root():
            raise PermissionError("Only root can modify sudoers")
        if username == self.ROOT_USERNAME:
            raise ValueError("Cannot remove root from sudoers")
        self.sudoers.discard(username)
        return True

    def _get_node(self, path):
        if self.filesystem:
            return self.filesystem.exists(path)
        return False
"""
Security for KOS Container Registry

This module implements security for the KOS container registry,
including authentication, authorization, and access control.
"""

import os
import json
import time
import uuid
import hashlib
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Optional, Any, Union, Callable

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
REGISTRY_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/registry')
REGISTRY_SECURITY_PATH = os.path.join(REGISTRY_ROOT, 'security')
REGISTRY_USERS_PATH = os.path.join(REGISTRY_SECURITY_PATH, 'users')
REGISTRY_TOKENS_PATH = os.path.join(REGISTRY_SECURITY_PATH, 'tokens')

# Ensure directories exist
for directory in [REGISTRY_SECURITY_PATH, REGISTRY_USERS_PATH, REGISTRY_TOKENS_PATH]:
    os.makedirs(directory, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class AccessLevel(str, Enum):
    """Access levels for registry resources."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class RegistrySecurity:
    """
    Security for the KOS container registry.
    
    This class provides methods for authentication, authorization, and
    access control for registry resources.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RegistrySecurity, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize registry security."""
        if self._initialized:
            return
        
        self._initialized = True
        self._token_cache = {}  # token -> (user, expiry)
        self._user_cache = {}   # username -> user_data
        self._acl_cache = {}    # resource -> user -> access_level
        
        # Create admin user if it doesn't exist
        if not os.path.exists(os.path.join(REGISTRY_USERS_PATH, 'admin.json')):
            self.create_user('admin', 'admin', AccessLevel.ADMIN)
    
    def create_user(self, username: str, password: str, access_level: AccessLevel = AccessLevel.READ) -> bool:
        """
        Create a new user.
        
        Args:
            username: Username
            password: Password
            access_level: Default access level
            
        Returns:
            bool: Success or failure
        """
        user_file = os.path.join(REGISTRY_USERS_PATH, f"{username}.json")
        
        if os.path.exists(user_file):
            logger.error(f"User already exists: {username}")
            return False
        
        try:
            # Hash password
            salt = os.urandom(16).hex()
            password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
            
            # Create user data
            user_data = {
                "username": username,
                "password_hash": password_hash,
                "salt": salt,
                "access_level": access_level,
                "created": time.time(),
                "last_login": 0,
                "acl": {}  # resource -> access_level
            }
            
            # Save user data
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=2)
            
            # Update cache
            with self._lock:
                self._user_cache[username] = user_data
            
            logger.info(f"Created user: {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to create user {username}: {e}")
            return False
    
    def delete_user(self, username: str) -> bool:
        """
        Delete a user.
        
        Args:
            username: Username
            
        Returns:
            bool: Success or failure
        """
        user_file = os.path.join(REGISTRY_USERS_PATH, f"{username}.json")
        
        if not os.path.exists(user_file):
            logger.error(f"User not found: {username}")
            return False
        
        try:
            # Delete user file
            os.remove(user_file)
            
            # Update cache
            with self._lock:
                if username in self._user_cache:
                    del self._user_cache[username]
                
                # Remove user from ACL cache
                for resource, user_acl in self._acl_cache.items():
                    if username in user_acl:
                        del user_acl[username]
            
            logger.info(f"Deleted user: {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {username}: {e}")
            return False
    
    def update_user(self, username: str, password: Optional[str] = None,
                    access_level: Optional[AccessLevel] = None) -> bool:
        """
        Update a user.
        
        Args:
            username: Username
            password: New password, or None to keep current
            access_level: New access level, or None to keep current
            
        Returns:
            bool: Success or failure
        """
        user_file = os.path.join(REGISTRY_USERS_PATH, f"{username}.json")
        
        if not os.path.exists(user_file):
            logger.error(f"User not found: {username}")
            return False
        
        try:
            # Load user data
            with open(user_file, 'r') as f:
                user_data = json.load(f)
            
            # Update password if provided
            if password:
                salt = os.urandom(16).hex()
                password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
                user_data["password_hash"] = password_hash
                user_data["salt"] = salt
            
            # Update access level if provided
            if access_level:
                user_data["access_level"] = access_level
            
            # Save user data
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=2)
            
            # Update cache
            with self._lock:
                self._user_cache[username] = user_data
            
            logger.info(f"Updated user: {username}")
            return True
        except Exception as e:
            logger.error(f"Failed to update user {username}: {e}")
            return False
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate a user and return a token.
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Token or None if authentication failed
        """
        # Load user data
        user_data = self._get_user(username)
        if not user_data:
            logger.error(f"User not found: {username}")
            return None
        
        # Check password
        salt = user_data.get("salt", "")
        password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        
        if password_hash != user_data.get("password_hash", ""):
            logger.error(f"Invalid password for user: {username}")
            return None
        
        # Generate token
        token = uuid.uuid4().hex
        expiry = time.time() + 3600  # 1 hour
        
        # Save token
        token_file = os.path.join(REGISTRY_TOKENS_PATH, f"{token}.json")
        token_data = {
            "token": token,
            "username": username,
            "created": time.time(),
            "expiry": expiry
        }
        
        try:
            with open(token_file, 'w') as f:
                json.dump(token_data, f, indent=2)
            
            # Update cache
            with self._lock:
                self._token_cache[token] = (username, expiry)
                
                # Update last login
                if username in self._user_cache:
                    self._user_cache[username]["last_login"] = time.time()
            
            logger.info(f"Authenticated user: {username}")
            return token
        except Exception as e:
            logger.error(f"Failed to save token for user {username}: {e}")
            return None
    
    def validate_token(self, token: str) -> Optional[str]:
        """
        Validate a token and return the username.
        
        Args:
            token: Token to validate
            
        Returns:
            Username or None if token is invalid
        """
        # Check cache first
        with self._lock:
            if token in self._token_cache:
                username, expiry = self._token_cache[token]
                
                if time.time() < expiry:
                    return username
                
                # Token expired, remove from cache
                del self._token_cache[token]
        
        # Check token file
        token_file = os.path.join(REGISTRY_TOKENS_PATH, f"{token}.json")
        if not os.path.exists(token_file):
            logger.error(f"Token not found: {token}")
            return None
        
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            username = token_data.get("username", "")
            expiry = token_data.get("expiry", 0)
            
            if time.time() >= expiry:
                # Token expired, delete file
                os.remove(token_file)
                logger.error(f"Token expired: {token}")
                return None
            
            # Update cache
            with self._lock:
                self._token_cache[token] = (username, expiry)
            
            return username
        except Exception as e:
            logger.error(f"Failed to validate token: {e}")
            return None
    
    def invalidate_token(self, token: str) -> bool:
        """
        Invalidate a token.
        
        Args:
            token: Token to invalidate
            
        Returns:
            bool: Success or failure
        """
        token_file = os.path.join(REGISTRY_TOKENS_PATH, f"{token}.json")
        
        try:
            # Remove from cache
            with self._lock:
                if token in self._token_cache:
                    del self._token_cache[token]
            
            # Delete token file
            if os.path.exists(token_file):
                os.remove(token_file)
            
            logger.info(f"Invalidated token: {token}")
            return True
        except Exception as e:
            logger.error(f"Failed to invalidate token: {e}")
            return False
    
    def invalidate_user_tokens(self, username: str) -> int:
        """
        Invalidate all tokens for a user.
        
        Args:
            username: Username
            
        Returns:
            Number of tokens invalidated
        """
        invalidated = 0
        
        try:
            # Remove from cache
            with self._lock:
                for token, (token_username, _) in list(self._token_cache.items()):
                    if token_username == username:
                        del self._token_cache[token]
                        invalidated += 1
            
            # Delete token files
            for filename in os.listdir(REGISTRY_TOKENS_PATH):
                if not filename.endswith('.json'):
                    continue
                
                token_file = os.path.join(REGISTRY_TOKENS_PATH, filename)
                try:
                    with open(token_file, 'r') as f:
                        token_data = json.load(f)
                    
                    if token_data.get("username") == username:
                        os.remove(token_file)
                        invalidated += 1
                except Exception:
                    continue
            
            logger.info(f"Invalidated {invalidated} tokens for user: {username}")
            return invalidated
        except Exception as e:
            logger.error(f"Failed to invalidate tokens for user {username}: {e}")
            return invalidated
    
    def set_acl(self, resource: str, username: str, access_level: AccessLevel) -> bool:
        """
        Set access control for a resource.
        
        Args:
            resource: Resource name (e.g., "image/nginx")
            username: Username
            access_level: Access level
            
        Returns:
            bool: Success or failure
        """
        # Load user data
        user_data = self._get_user(username)
        if not user_data:
            logger.error(f"User not found: {username}")
            return False
        
        try:
            # Update ACL
            if "acl" not in user_data:
                user_data["acl"] = {}
            
            user_data["acl"][resource] = access_level
            
            # Save user data
            user_file = os.path.join(REGISTRY_USERS_PATH, f"{username}.json")
            with open(user_file, 'w') as f:
                json.dump(user_data, f, indent=2)
            
            # Update cache
            with self._lock:
                self._user_cache[username] = user_data
                
                if resource not in self._acl_cache:
                    self._acl_cache[resource] = {}
                
                self._acl_cache[resource][username] = access_level
            
            logger.info(f"Set ACL for {resource}: {username} -> {access_level}")
            return True
        except Exception as e:
            logger.error(f"Failed to set ACL: {e}")
            return False
    
    def get_access_level(self, resource: str, username: str) -> AccessLevel:
        """
        Get access level for a resource.
        
        Args:
            resource: Resource name (e.g., "image/nginx")
            username: Username
            
        Returns:
            Access level
        """
        # Check cache first
        with self._lock:
            if resource in self._acl_cache and username in self._acl_cache[resource]:
                return self._acl_cache[resource][username]
        
        # Load user data
        user_data = self._get_user(username)
        if not user_data:
            logger.error(f"User not found: {username}")
            return AccessLevel.NONE
        
        # Check if user is admin
        if user_data.get("access_level") == AccessLevel.ADMIN:
            return AccessLevel.ADMIN
        
        # Check resource-specific ACL
        acl = user_data.get("acl", {})
        
        # Handle wildcard resources
        parts = resource.split('/')
        for i in range(len(parts), 0, -1):
            prefix = '/'.join(parts[:i])
            wildcard = f"{prefix}/*"
            
            if wildcard in acl:
                # Update cache
                with self._lock:
                    if resource not in self._acl_cache:
                        self._acl_cache[resource] = {}
                    
                    self._acl_cache[resource][username] = acl[wildcard]
                
                return acl[wildcard]
        
        # Check exact resource
        if resource in acl:
            # Update cache
            with self._lock:
                if resource not in self._acl_cache:
                    self._acl_cache[resource] = {}
                
                self._acl_cache[resource][username] = acl[resource]
            
            return acl[resource]
        
        # Fall back to user's default access level
        default_level = user_data.get("access_level", AccessLevel.NONE)
        
        # Update cache
        with self._lock:
            if resource not in self._acl_cache:
                self._acl_cache[resource] = {}
            
            self._acl_cache[resource][username] = default_level
        
        return default_level
    
    def check_access(self, resource: str, username: str, required_level: AccessLevel) -> bool:
        """
        Check if a user has the required access level for a resource.
        
        Args:
            resource: Resource name
            username: Username
            required_level: Required access level
            
        Returns:
            bool: True if access is allowed
        """
        # Get access level
        access_level = self.get_access_level(resource, username)
        
        # Check access
        if access_level == AccessLevel.ADMIN:
            return True
        
        if access_level == AccessLevel.WRITE and required_level in [AccessLevel.READ, AccessLevel.WRITE]:
            return True
        
        if access_level == AccessLevel.READ and required_level == AccessLevel.READ:
            return True
        
        return False
    
    def _get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user data.
        
        Args:
            username: Username
            
        Returns:
            User data or None if not found
        """
        # Check cache first
        with self._lock:
            if username in self._user_cache:
                return self._user_cache[username]
        
        # Load from file
        user_file = os.path.join(REGISTRY_USERS_PATH, f"{username}.json")
        if not os.path.exists(user_file):
            return None
        
        try:
            with open(user_file, 'r') as f:
                user_data = json.load(f)
            
            # Update cache
            with self._lock:
                self._user_cache[username] = user_data
            
            return user_data
        except Exception as e:
            logger.error(f"Failed to load user {username}: {e}")
            return None
    
    def list_users(self) -> List[Dict[str, Any]]:
        """
        List all users.
        
        Returns:
            List of user data
        """
        users = []
        
        for filename in os.listdir(REGISTRY_USERS_PATH):
            if not filename.endswith('.json'):
                continue
            
            user_file = os.path.join(REGISTRY_USERS_PATH, filename)
            try:
                with open(user_file, 'r') as f:
                    user_data = json.load(f)
                
                # Remove sensitive data
                if "password_hash" in user_data:
                    del user_data["password_hash"]
                if "salt" in user_data:
                    del user_data["salt"]
                
                users.append(user_data)
            except Exception as e:
                logger.error(f"Failed to load user from {filename}: {e}")
        
        return users
    
    def clean_expired_tokens(self) -> int:
        """
        Clean expired tokens.
        
        Returns:
            Number of tokens removed
        """
        removed = 0
        current_time = time.time()
        
        # Clean cache
        with self._lock:
            for token, (_, expiry) in list(self._token_cache.items()):
                if current_time >= expiry:
                    del self._token_cache[token]
                    removed += 1
        
        # Clean files
        for filename in os.listdir(REGISTRY_TOKENS_PATH):
            if not filename.endswith('.json'):
                continue
            
            token_file = os.path.join(REGISTRY_TOKENS_PATH, filename)
            try:
                with open(token_file, 'r') as f:
                    token_data = json.load(f)
                
                expiry = token_data.get("expiry", 0)
                if current_time >= expiry:
                    os.remove(token_file)
                    removed += 1
            except Exception:
                continue
        
        logger.info(f"Cleaned {removed} expired tokens")
        return removed

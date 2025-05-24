"""
KOS Authentication Module

This module provides authentication and session management
for the KOS user management system.
"""

import os
import sys
import time
import logging
import threading
import hashlib
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager, User

# Set up logging
logger = logging.getLogger('KOS.security.auth')

# Current session info
_current_user = None
_current_uid = 0  # Default to root
_current_gid = 0
_session_id = None
_session_lock = threading.RLock()

# Session registry
_active_sessions = {}  # session_id -> Session


class Session:
    """Class representing a user session"""
    
    def __init__(self, user: User, session_id: str = None):
        """
        Initialize a new session
        
        Args:
            user: User object
            session_id: Session ID (generated if None)
        """
        self.user = user
        self.session_id = session_id or str(uuid.uuid4())
        self.start_time = time.time()
        self.last_activity = self.start_time
        self.terminal = os.environ.get('TERM', 'unknown')
        self.remote_host = os.environ.get('SSH_CLIENT', '').split(' ')[0] if 'SSH_CLIENT' in os.environ else 'localhost'
        self.env = {}  # Environment variables specific to this session
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "session_id": self.session_id,
            "username": self.user.username,
            "uid": self.user.uid,
            "start_time": self.start_time,
            "last_activity": self.last_activity,
            "terminal": self.terminal,
            "remote_host": self.remote_host,
            "env": self.env
        }


def login(username: str, password: str) -> Tuple[bool, str, Optional[Session]]:
    """
    Authenticate user and create session
    
    Args:
        username: Username
        password: Password
    
    Returns:
        (success, message, session)
    """
    # Get user
    user = UserManager.get_user_by_name(username)
    if not user:
        return False, f"User '{username}' does not exist", None
    
    # Check password
    if not user.check_password(password):
        return False, "Invalid password", None
    
    # Create session
    session = Session(user)
    
    # Register session
    with _session_lock:
        _active_sessions[session.session_id] = session
    
    return True, "Authentication successful", session


def logout(session_id: str) -> Tuple[bool, str]:
    """
    End user session
    
    Args:
        session_id: Session ID
    
    Returns:
        (success, message)
    """
    with _session_lock:
        if session_id in _active_sessions:
            del _active_sessions[session_id]
            return True, "Logged out successfully"
        else:
            return False, "Session not found"


def get_session(session_id: str) -> Optional[Session]:
    """
    Get session by ID
    
    Args:
        session_id: Session ID
    
    Returns:
        Session object or None
    """
    with _session_lock:
        return _active_sessions.get(session_id)


def list_sessions() -> List[Session]:
    """
    List all active sessions
    
    Returns:
        List of sessions
    """
    with _session_lock:
        return list(_active_sessions.values())


def get_current_user() -> Optional[User]:
    """
    Get current user
    
    Returns:
        Current user or None
    """
    global _current_user
    
    if _current_user is None:
        # Initialize with root user
        _current_user = UserManager.get_user_by_uid(0)  # root
    
    return _current_user


def get_current_uid() -> int:
    """
    Get current user ID
    
    Returns:
        Current UID
    """
    global _current_uid
    return _current_uid


def get_current_gid() -> int:
    """
    Get current group ID
    
    Returns:
        Current GID
    """
    global _current_gid
    return _current_gid


def set_current_user(user: User) -> bool:
    """
    Set current user
    
    Args:
        user: User object
    
    Returns:
        Success status
    """
    global _current_user, _current_uid, _current_gid
    
    if user is None:
        return False
    
    _current_user = user
    _current_uid = user.uid
    _current_gid = user.gid
    
    return True


def switch_user(username: str, password: str = None) -> Tuple[bool, str]:
    """
    Switch to another user (similar to su)
    
    Args:
        username: Username to switch to
        password: Password (not required for root)
    
    Returns:
        (success, message)
    """
    # Check if current user is root (can switch without password)
    current_user = get_current_user()
    if current_user.uid != 0 and password is None:
        return False, "Password required"
    
    # Get target user
    target_user = UserManager.get_user_by_name(username)
    if not target_user:
        return False, f"User '{username}' does not exist"
    
    # Check password if not root
    if current_user.uid != 0 and not target_user.check_password(password):
        return False, "Invalid password"
    
    # Switch user
    if set_current_user(target_user):
        return True, f"Switched to user '{username}'"
    else:
        return False, "Failed to switch user"


def has_capability(capability: str) -> bool:
    """
    Check if current user has a capability
    
    Args:
        capability: Capability name
    
    Returns:
        True if user has capability
    """
    current_user = get_current_user()
    
    # Root has all capabilities
    if current_user.uid == 0:
        return True
    
    # TODO: Implement capability checking based on groups
    return False


def initialize():
    """Initialize authentication module"""
    logger.info("Initializing authentication module")
    
    # Set current user to root
    root_user = UserManager.get_user_by_uid(0)
    if root_user:
        set_current_user(root_user)
    
    logger.info("Authentication module initialized")


# Initialize module
initialize()

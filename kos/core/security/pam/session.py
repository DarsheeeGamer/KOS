"""
PAM Session Management for KOS

This module implements session management for PAM authentication, tracking
user sessions and providing session state for authenticated users.
"""

import os
import time
import uuid
import json
import logging
from typing import Dict, List, Optional, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
SESSION_DIR = os.path.join(KOS_ROOT, 'var/run/pam_sessions')

# Ensure directories exist
os.makedirs(SESSION_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class PAMSession:
    """
    Represents a PAM authentication session.
    
    This class tracks session state for authenticated users, including
    creation time, service information, and any session-specific data.
    """
    
    def __init__(self, username: str, service: str):
        """
        Initialize a new PAM session.
        
        Args:
            username: The authenticated username
            service: The PAM service used for authentication
        """
        self.id = str(uuid.uuid4())
        self.username = username
        self.service = service
        self.created_at = time.time()
        self.data = {}
        self.active = True
        self._save()
    
    def _save(self):
        """Save session to disk."""
        session_file = os.path.join(SESSION_DIR, f"{self.id}.json")
        session_data = {
            "id": self.id,
            "username": self.username,
            "service": self.service,
            "created_at": self.created_at,
            "data": self.data,
            "active": self.active
        }
        
        try:
            with open(session_file, 'w') as f:
                json.dump(session_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save session: {e}")
    
    def set_data(self, key: str, value: Any):
        """
        Set session data.
        
        Args:
            key: Data key
            value: Data value
        """
        self.data[key] = value
        self._save()
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """
        Get session data.
        
        Args:
            key: Data key
            default: Default value if key doesn't exist
            
        Returns:
            The data value or default
        """
        return self.data.get(key, default)
    
    def close(self):
        """Close the session."""
        self.active = False
        self._save()
        
        # Remove the session file
        session_file = os.path.join(SESSION_DIR, f"{self.id}.json")
        try:
            if os.path.exists(session_file):
                os.remove(session_file)
        except Exception as e:
            logger.error(f"Failed to remove session file: {e}")


class SessionManager:
    """
    Manages PAM sessions across the system.
    
    This class provides utilities for loading, querying, and cleaning up
    PAM sessions.
    """
    
    @staticmethod
    def load_session(session_id: str) -> Optional[PAMSession]:
        """
        Load a session by ID.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            PAMSession or None if not found
        """
        session_file = os.path.join(SESSION_DIR, f"{session_id}.json")
        if not os.path.exists(session_file):
            return None
        
        try:
            with open(session_file, 'r') as f:
                data = json.load(f)
            
            session = PAMSession(data["username"], data["service"])
            session.id = data["id"]
            session.created_at = data["created_at"]
            session.data = data["data"]
            session.active = data["active"]
            
            return session
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return None
    
    @staticmethod
    def get_user_sessions(username: str) -> List[PAMSession]:
        """
        Get all active sessions for a user.
        
        Args:
            username: Username to get sessions for
            
        Returns:
            List of active sessions
        """
        sessions = []
        
        if not os.path.exists(SESSION_DIR):
            return sessions
        
        for filename in os.listdir(SESSION_DIR):
            if not filename.endswith('.json'):
                continue
            
            session_file = os.path.join(SESSION_DIR, filename)
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                if data["username"] == username and data["active"]:
                    session = PAMSession(data["username"], data["service"])
                    session.id = data["id"]
                    session.created_at = data["created_at"]
                    session.data = data["data"]
                    session.active = data["active"]
                    sessions.append(session)
            except Exception as e:
                logger.error(f"Failed to load session file {filename}: {e}")
        
        return sessions
    
    @staticmethod
    def clean_inactive_sessions(max_age: int = 86400):
        """
        Clean up inactive or expired sessions.
        
        Args:
            max_age: Maximum age in seconds for inactive sessions
        """
        if not os.path.exists(SESSION_DIR):
            return
        
        current_time = time.time()
        for filename in os.listdir(SESSION_DIR):
            if not filename.endswith('.json'):
                continue
            
            session_file = os.path.join(SESSION_DIR, filename)
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                # Remove inactive or expired sessions
                if not data["active"] or (current_time - data["created_at"]) > max_age:
                    os.remove(session_file)
                    logger.info(f"Removed expired session: {data['id']}")
            except Exception as e:
                logger.error(f"Failed to process session file {filename}: {e}")
    
    @staticmethod
    def get_all_sessions() -> List[PAMSession]:
        """
        Get all active sessions.
        
        Returns:
            List of all active sessions
        """
        sessions = []
        
        if not os.path.exists(SESSION_DIR):
            return sessions
        
        for filename in os.listdir(SESSION_DIR):
            if not filename.endswith('.json'):
                continue
            
            session_file = os.path.join(SESSION_DIR, filename)
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                if data["active"]:
                    session = PAMSession(data["username"], data["service"])
                    session.id = data["id"]
                    session.created_at = data["created_at"]
                    session.data = data["data"]
                    session.active = data["active"]
                    sessions.append(session)
            except Exception as e:
                logger.error(f"Failed to load session file {filename}: {e}")
        
        return sessions

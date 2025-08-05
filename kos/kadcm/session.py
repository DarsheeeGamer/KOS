"""
Session management for KADCM connections
"""

import time
import uuid
import threading
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class Session:
    """KADCM session information"""
    session_id: str
    entity_id: str
    entity_type: str  # host, user, service
    fingerprint: str
    permissions: Dict[str, bool]
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 300)
    metadata: Dict = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return time.time() > self.expires_at
    
    def is_active(self) -> bool:
        """Check if session is active"""
        return not self.is_expired() and time.time() - self.last_activity < 300
    
    def touch(self):
        """Update last activity time"""
        self.last_activity = time.time()


class SessionManager:
    """Manage KADCM sessions"""
    
    def __init__(self, default_timeout: int = 300):
        self.sessions: Dict[str, Session] = {}
        self.default_timeout = default_timeout
        self.lock = threading.RLock()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def create_session(self, entity_id: str, entity_type: str,
                      fingerprint: str, permissions: Dict[str, bool]) -> str:
        """Create new session"""
        session_id = str(uuid.uuid4())
        
        with self.lock:
            session = Session(
                session_id=session_id,
                entity_id=entity_id,
                entity_type=entity_type,
                fingerprint=fingerprint,
                permissions=permissions,
                expires_at=time.time() + self.default_timeout
            )
            
            self.sessions[session_id] = session
            
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        with self.lock:
            session = self.sessions.get(session_id)
            
            if session and not session.is_expired():
                return session
                
            # Remove expired session
            if session:
                del self.sessions[session_id]
                
            return None
    
    def update_activity(self, session_id: str):
        """Update session activity timestamp"""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.touch()
    
    def end_session(self, session_id: str):
        """End session"""
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs"""
        with self.lock:
            active = []
            for session_id, session in list(self.sessions.items()):
                if session.is_active():
                    active.append(session_id)
                elif session.is_expired():
                    del self.sessions[session_id]
                    
            return active
    
    def get_sessions_by_entity(self, entity_id: str) -> List[Session]:
        """Get all sessions for an entity"""
        with self.lock:
            return [
                session for session in self.sessions.values()
                if session.entity_id == entity_id and not session.is_expired()
            ]
    
    def extend_session(self, session_id: str, duration: int = None):
        """Extend session expiration"""
        duration = duration or self.default_timeout
        
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session.expires_at = time.time() + duration
                session.touch()
    
    def _cleanup_loop(self):
        """Periodic cleanup of expired sessions"""
        while True:
            time.sleep(60)  # Check every minute
            
            with self.lock:
                expired = []
                for session_id, session in self.sessions.items():
                    if session.is_expired():
                        expired.append(session_id)
                
                for session_id in expired:
                    del self.sessions[session_id]
                    
                if expired:
                    print(f"Cleaned up {len(expired)} expired sessions")
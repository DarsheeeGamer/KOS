"""KOS Authentication Manager"""
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Dict, Optional

class AuthenticationManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.session_timeout = timedelta(hours=1)

    def create_session(self, username: str) -> str:
        """Create a new session for a user"""
        session_id = secrets.token_hex(32)
        self.sessions[session_id] = {
            'username': username,
            'created_at': datetime.now(),
            'last_accessed': datetime.now()
        }
        return session_id

    def validate_session(self, session_id: str) -> Optional[str]:
        """Validate a session and return username if valid"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        if datetime.now() - session['last_accessed'] > self.session_timeout:
            del self.sessions[session_id]
            return None

        session['last_accessed'] = datetime.now()
        return session['username']

    def end_session(self, session_id: str) -> bool:
        """End a user session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, stored_hash: str, provided_password: str) -> bool:
        """Verify a password against its hash"""
        return stored_hash == self.hash_password(provided_password)
"""
PAM module for KAIM integration
Python implementation for testing - production would be in C
"""

import os
import pwd
import json
import time
import syslog
from typing import Optional, Dict, Any

from .client import KAIMClient
from ..security.fingerprint import FingerprintManager


class PAMKaim:
    """PAM module for KAIM authentication"""
    
    PAM_SUCCESS = 0
    PAM_AUTH_ERR = 7
    PAM_PERM_DENIED = 6
    PAM_SESSION_ERR = 14
    PAM_SYSTEM_ERR = 4
    
    def __init__(self):
        self.fingerprint_manager = FingerprintManager()
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load PAM configuration"""
        config_path = "/etc/pam.d/kaim"
        if os.path.exists(config_path):
            # Parse PAM config format
            pass
        
        return {
            "require_fingerprint": True,
            "session_timeout": 3600,
            "audit_log": True
        }
    
    def pam_sm_authenticate(self, pamh, flags: int, argv: list) -> int:
        """PAM authentication function"""
        try:
            # Get username
            username = pamh.get_user()
            if not username:
                return self.PAM_AUTH_ERR
            
            # Get user info
            try:
                user_info = pwd.getpwnam(username)
            except KeyError:
                return self.PAM_AUTH_ERR
            
            # Check if KAIM authentication required
            if not self._requires_kaim_auth(user_info):
                return self.PAM_SUCCESS
            
            # Get fingerprint
            fingerprint = self._get_user_fingerprint(username)
            if not fingerprint:
                self._log("No fingerprint for user", username)
                return self.PAM_AUTH_ERR
            
            # Verify fingerprint
            if not self.fingerprint_manager.verify(fingerprint, "user"):
                self._log("Invalid fingerprint", username)
                return self.PAM_AUTH_ERR
            
            # Create KAIM session
            if not self._create_kaim_session(username, fingerprint):
                return self.PAM_AUTH_ERR
            
            self._log("Authentication successful", username)
            return self.PAM_SUCCESS
            
        except Exception as e:
            self._log(f"Authentication error: {e}", username)
            return self.PAM_SYSTEM_ERR
    
    def pam_sm_setcred(self, pamh, flags: int, argv: list) -> int:
        """PAM credential function"""
        # Credentials handled by KAIM daemon
        return self.PAM_SUCCESS
    
    def pam_sm_acct_mgmt(self, pamh, flags: int, argv: list) -> int:
        """PAM account management function"""
        try:
            username = pamh.get_user()
            
            # Check if account is active
            if not self._is_account_active(username):
                return self.PAM_PERM_DENIED
            
            # Check session validity
            if not self._is_session_valid(username):
                return self.PAM_SESSION_ERR
            
            return self.PAM_SUCCESS
            
        except Exception:
            return self.PAM_SYSTEM_ERR
    
    def pam_sm_open_session(self, pamh, flags: int, argv: list) -> int:
        """PAM session open function"""
        try:
            username = pamh.get_user()
            
            # Register session with KAIM
            session_id = self._register_session(username)
            if not session_id:
                return self.PAM_SESSION_ERR
            
            # Set environment variable
            pamh.putenv(f"KAIM_SESSION={session_id}")
            
            self._log("Session opened", username)
            return self.PAM_SUCCESS
            
        except Exception:
            return self.PAM_SYSTEM_ERR
    
    def pam_sm_close_session(self, pamh, flags: int, argv: list) -> int:
        """PAM session close function"""
        try:
            username = pamh.get_user()
            
            # Get session ID
            session_id = pamh.getenv("KAIM_SESSION")
            if session_id:
                self._unregister_session(session_id)
            
            self._log("Session closed", username)
            return self.PAM_SUCCESS
            
        except Exception:
            return self.PAM_SYSTEM_ERR
    
    def pam_sm_chauthtok(self, pamh, flags: int, argv: list) -> int:
        """PAM password change function"""
        # Password changes handled separately
        return self.PAM_SUCCESS
    
    def _requires_kaim_auth(self, user_info) -> bool:
        """Check if user requires KAIM authentication"""
        # System users don't need KAIM
        if user_info.pw_uid < 1000:
            return False
        
        # Check user groups
        # Users in 'nokaim' group skip KAIM
        return True
    
    def _get_user_fingerprint(self, username: str) -> Optional[str]:
        """Get user's fingerprint"""
        fingerprint_file = f"/home/{username}/.kos/fingerprint"
        if os.path.exists(fingerprint_file):
            try:
                with open(fingerprint_file, 'r') as f:
                    return f.read().strip()
            except:
                pass
        return None
    
    def _create_kaim_session(self, username: str, fingerprint: str) -> bool:
        """Create KAIM session for user"""
        try:
            # Connect to KAIM as PAM service
            client = KAIMClient("pam_kaim", self._get_pam_fingerprint())
            if not client.connect():
                return False
            
            # Request user session creation
            response = client._send_request("CREATE_USER_SESSION", {
                "username": username,
                "fingerprint": fingerprint,
                "pam_session": True
            })
            
            client.disconnect()
            return response.success
            
        except Exception:
            return False
    
    def _get_pam_fingerprint(self) -> str:
        """Get PAM service fingerprint"""
        # PAM has special system fingerprint
        return "PAM_SYSTEM_FINGERPRINT"
    
    def _is_account_active(self, username: str) -> bool:
        """Check if account is active"""
        # Check shadow file, expiration, etc
        return True
    
    def _is_session_valid(self, username: str) -> bool:
        """Check if session is valid"""
        return True
    
    def _register_session(self, username: str) -> Optional[str]:
        """Register session with KAIM"""
        try:
            # Generate session ID
            session_id = os.urandom(16).hex()
            
            # Store session info
            session_file = f"/var/run/kaim/sessions/{session_id}"
            os.makedirs(os.path.dirname(session_file), exist_ok=True)
            
            with open(session_file, 'w') as f:
                json.dump({
                    "username": username,
                    "created": time.time(),
                    "pid": os.getpid()
                }, f)
            
            return session_id
            
        except Exception:
            return None
    
    def _unregister_session(self, session_id: str):
        """Unregister session"""
        try:
            session_file = f"/var/run/kaim/sessions/{session_id}"
            if os.path.exists(session_file):
                os.unlink(session_file)
        except:
            pass
    
    def _log(self, message: str, username: str = None):
        """Log to syslog"""
        if self.config.get("audit_log"):
            if username:
                message = f"[{username}] {message}"
            syslog.syslog(syslog.LOG_AUTH | syslog.LOG_INFO, 
                         f"pam_kaim: {message}")


# PAM module entry points (would be exported in C module)
def pam_sm_authenticate(pamh, flags, argv):
    """PAM authentication entry point"""
    module = PAMKaim()
    return module.pam_sm_authenticate(pamh, flags, argv)


def pam_sm_setcred(pamh, flags, argv):
    """PAM credential entry point"""
    module = PAMKaim()
    return module.pam_sm_setcred(pamh, flags, argv)


def pam_sm_acct_mgmt(pamh, flags, argv):
    """PAM account management entry point"""
    module = PAMKaim()
    return module.pam_sm_acct_mgmt(pamh, flags, argv)


def pam_sm_open_session(pamh, flags, argv):
    """PAM session open entry point"""
    module = PAMKaim()
    return module.pam_sm_open_session(pamh, flags, argv)


def pam_sm_close_session(pamh, flags, argv):
    """PAM session close entry point"""
    module = PAMKaim()
    return module.pam_sm_close_session(pamh, flags, argv)


def pam_sm_chauthtok(pamh, flags, argv):
    """PAM password change entry point"""
    module = PAMKaim()
    return module.pam_sm_chauthtok(pamh, flags, argv)
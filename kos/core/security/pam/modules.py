"""
PAM Modules for KOS

This module implements various PAM modules for different authentication methods.
Each module follows a standard interface and can be plugged into the PAM system.
"""

import os
import logging
from enum import Enum, auto
from typing import Dict, List, Optional, Any, Union

# Logging setup
logger = logging.getLogger(__name__)


class PAMResult(Enum):
    """Result codes for PAM operations."""
    SUCCESS = auto()
    AUTH_FAILED = auto()
    ACCOUNT_EXPIRED = auto()
    ACCOUNT_LOCKED = auto()
    PASSWORD_EXPIRED = auto()
    PERMISSION_DENIED = auto()
    SESSION_ERROR = auto()
    GENERAL_FAILURE = auto()
    MODULE_NOT_FOUND = auto()
    UNKNOWN_SERVICE = auto()
    INVALID_ARGUMENT = auto()
    INSUFFICIENT_DATA = auto()


class PAMModule:
    """Base class for PAM modules."""
    
    def authenticate(self, username: str, auth_data: Dict[str, Any], 
                   args: List[str]) -> PAMResult:
        """
        Authenticate a user.
        
        Args:
            username: Username to authenticate
            auth_data: Authentication data
            args: Module arguments
            
        Returns:
            PAMResult: Authentication result
        """
        return PAMResult.GENERAL_FAILURE
    
    def account(self, username: str, auth_data: Dict[str, Any], 
               args: List[str]) -> PAMResult:
        """
        Check account validity.
        
        Args:
            username: Username to check
            auth_data: Authentication data
            args: Module arguments
            
        Returns:
            PAMResult: Account check result
        """
        return PAMResult.SUCCESS
    
    def password(self, username: str, auth_data: Dict[str, Any], 
                args: List[str]) -> PAMResult:
        """
        Change a password.
        
        Args:
            username: Username
            auth_data: Authentication data including old and new passwords
            args: Module arguments
            
        Returns:
            PAMResult: Password change result
        """
        return PAMResult.GENERAL_FAILURE
    
    def session(self, username: str, auth_data: Dict[str, Any], 
               args: List[str]) -> PAMResult:
        """
        Manage a session.
        
        Args:
            username: Username
            auth_data: Session data
            args: Module arguments
            
        Returns:
            PAMResult: Session operation result
        """
        return PAMResult.SUCCESS


class PasswordModule(PAMModule):
    """PAM module for password-based authentication."""
    
    def authenticate(self, username: str, auth_data: Dict[str, Any], 
                   args: List[str]) -> PAMResult:
        """
        Authenticate a user with a password.
        
        Args:
            username: Username to authenticate
            auth_data: Authentication data with password
            args: Module arguments
            
        Returns:
            PAMResult: Authentication result
        """
        if "password" not in auth_data:
            return PAMResult.INSUFFICIENT_DATA
        
        password = auth_data["password"]
        
        # Get the user manager
        from ..users import UserManager
        user_manager = UserManager()
        
        # Check if the user exists
        user = user_manager.get_user(username)
        if not user:
            logger.warning(f"User not found: {username}")
            return PAMResult.AUTH_FAILED
        
        # Check if null passwords are allowed
        allow_null = "nullok" in args
        if not password and not allow_null:
            logger.warning(f"Empty password not allowed for user: {username}")
            return PAMResult.AUTH_FAILED
        
        # Verify the password
        if user_manager.verify_password(username, password):
            logger.info(f"Password authentication successful for user: {username}")
            return PAMResult.SUCCESS
        else:
            logger.warning(f"Password authentication failed for user: {username}")
            return PAMResult.AUTH_FAILED
    
    def account(self, username: str, auth_data: Dict[str, Any], 
               args: List[str]) -> PAMResult:
        """
        Check if an account is valid (not expired, not locked).
        
        Args:
            username: Username to check
            auth_data: Authentication data
            args: Module arguments
            
        Returns:
            PAMResult: Account check result
        """
        from ..users import UserManager
        user_manager = UserManager()
        
        # Check if the user exists
        user = user_manager.get_user(username)
        if not user:
            logger.warning(f"User not found: {username}")
            return PAMResult.AUTH_FAILED
        
        # Check if the account is locked
        if username in user_manager.shadow and user_manager.shadow[username]["password"].startswith("!"):
            logger.warning(f"Account locked: {username}")
            return PAMResult.ACCOUNT_LOCKED
        
        # Check account expiration
        if username in user_manager.shadow:
            shadow_entry = user_manager.shadow[username]
            if shadow_entry.get("expiration", -1) > 0:
                import time
                current_days = int(time.time() // 86400)
                if current_days > shadow_entry["expiration"]:
                    logger.warning(f"Account expired: {username}")
                    return PAMResult.ACCOUNT_EXPIRED
        
        return PAMResult.SUCCESS
    
    def password(self, username: str, auth_data: Dict[str, Any], 
                args: List[str]) -> PAMResult:
        """
        Change a user's password.
        
        Args:
            username: Username
            auth_data: Authentication data with old and new passwords
            args: Module arguments
            
        Returns:
            PAMResult: Password change result
        """
        if "old_password" not in auth_data or "new_password" not in auth_data:
            return PAMResult.INSUFFICIENT_DATA
        
        old_password = auth_data["old_password"]
        new_password = auth_data["new_password"]
        
        from ..users import UserManager
        user_manager = UserManager()
        
        # Verify the old password
        if not user_manager.verify_password(username, old_password):
            logger.warning(f"Old password verification failed for user: {username}")
            return PAMResult.AUTH_FAILED
        
        # Set the new password
        if user_manager.set_password(username, new_password):
            logger.info(f"Password changed for user: {username}")
            return PAMResult.SUCCESS
        else:
            logger.error(f"Failed to change password for user: {username}")
            return PAMResult.GENERAL_FAILURE


class TokenModule(PAMModule):
    """PAM module for token-based authentication."""
    
    def __init__(self, token_file: str = None):
        """
        Initialize the token module.
        
        Args:
            token_file: Path to the token file
        """
        self.token_file = token_file or os.path.join(
            os.environ.get('KOS_ROOT', '/tmp/kos'),
            'security/tokens.json'
        )
        self._tokens = self._load_tokens()
    
    def _load_tokens(self) -> Dict[str, Dict[str, str]]:
        """Load tokens from the token file."""
        if os.path.exists(self.token_file):
            try:
                import json
                with open(self.token_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")
        return {}
    
    def _save_tokens(self):
        """Save tokens to the token file."""
        try:
            import json
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as f:
                json.dump(self._tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
    
    def authenticate(self, username: str, auth_data: Dict[str, Any], 
                   args: List[str]) -> PAMResult:
        """
        Authenticate a user with a token.
        
        Args:
            username: Username to authenticate
            auth_data: Authentication data with token
            args: Module arguments
            
        Returns:
            PAMResult: Authentication result
        """
        if "token" not in auth_data:
            return PAMResult.INSUFFICIENT_DATA
        
        token = auth_data["token"]
        
        # Check if the user has tokens
        if username not in self._tokens:
            logger.warning(f"No tokens for user: {username}")
            return PAMResult.AUTH_FAILED
        
        # Check if the token is valid
        user_tokens = self._tokens[username]
        if token in user_tokens.values():
            logger.info(f"Token authentication successful for user: {username}")
            return PAMResult.SUCCESS
        else:
            logger.warning(f"Token authentication failed for user: {username}")
            return PAMResult.AUTH_FAILED
    
    def add_token(self, username: str, token_name: str, token: str) -> bool:
        """
        Add a token for a user.
        
        Args:
            username: Username
            token_name: Name of the token
            token: Token value
            
        Returns:
            bool: Success or failure
        """
        from ..users import UserManager
        user_manager = UserManager()
        
        # Check if the user exists
        if not user_manager.get_user(username):
            logger.error(f"User not found: {username}")
            return False
        
        # Initialize user tokens if not exist
        if username not in self._tokens:
            self._tokens[username] = {}
        
        # Add the token
        self._tokens[username][token_name] = token
        self._save_tokens()
        
        logger.info(f"Added token '{token_name}' for user: {username}")
        return True
    
    def remove_token(self, username: str, token_name: str) -> bool:
        """
        Remove a token for a user.
        
        Args:
            username: Username
            token_name: Name of the token
            
        Returns:
            bool: Success or failure
        """
        if username not in self._tokens or token_name not in self._tokens[username]:
            logger.warning(f"Token not found: {username}/{token_name}")
            return False
        
        del self._tokens[username][token_name]
        if not self._tokens[username]:
            del self._tokens[username]
        
        self._save_tokens()
        
        logger.info(f"Removed token '{token_name}' for user: {username}")
        return True


class BiometricModule(PAMModule):
    """PAM module for biometric authentication (simulation)."""
    
    def __init__(self, bio_db_file: str = None):
        """
        Initialize the biometric module.
        
        Args:
            bio_db_file: Path to the biometric database file
        """
        self.bio_db_file = bio_db_file or os.path.join(
            os.environ.get('KOS_ROOT', '/tmp/kos'),
            'security/biometrics.json'
        )
        self._biometrics = self._load_biometrics()
    
    def _load_biometrics(self) -> Dict[str, Dict[str, Any]]:
        """Load biometric data from the database file."""
        if os.path.exists(self.bio_db_file):
            try:
                import json
                with open(self.bio_db_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load biometric data: {e}")
        return {}
    
    def _save_biometrics(self):
        """Save biometric data to the database file."""
        try:
            import json
            os.makedirs(os.path.dirname(self.bio_db_file), exist_ok=True)
            with open(self.bio_db_file, 'w') as f:
                json.dump(self._biometrics, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save biometric data: {e}")
    
    def authenticate(self, username: str, auth_data: Dict[str, Any], 
                   args: List[str]) -> PAMResult:
        """
        Authenticate a user with biometric data.
        
        Args:
            username: Username to authenticate
            auth_data: Authentication data with biometric data
            args: Module arguments
            
        Returns:
            PAMResult: Authentication result
        """
        if "biometric" not in auth_data:
            return PAMResult.INSUFFICIENT_DATA
        
        biometric = auth_data["biometric"]
        
        # Check if the user has biometric data
        if username not in self._biometrics:
            logger.warning(f"No biometric data for user: {username}")
            return PAMResult.AUTH_FAILED
        
        # In a real system, this would do actual biometric matching
        # For simulation, we'll just check if the data matches exactly
        user_bio = self._biometrics[username]
        if user_bio.get("data") == biometric:
            logger.info(f"Biometric authentication successful for user: {username}")
            return PAMResult.SUCCESS
        else:
            logger.warning(f"Biometric authentication failed for user: {username}")
            return PAMResult.AUTH_FAILED
    
    def enroll_biometric(self, username: str, biometric_data: str, 
                        bio_type: str = "fingerprint") -> bool:
        """
        Enroll biometric data for a user.
        
        Args:
            username: Username
            biometric_data: Biometric data
            bio_type: Type of biometric (fingerprint, face, etc.)
            
        Returns:
            bool: Success or failure
        """
        from ..users import UserManager
        user_manager = UserManager()
        
        # Check if the user exists
        if not user_manager.get_user(username):
            logger.error(f"User not found: {username}")
            return False
        
        # Add the biometric data
        self._biometrics[username] = {
            "type": bio_type,
            "data": biometric_data,
            "enrolled_at": import_time().time()
        }
        self._save_biometrics()
        
        logger.info(f"Enrolled {bio_type} biometric for user: {username}")
        return True

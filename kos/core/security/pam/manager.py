"""
PAM Manager for KOS

This module implements the core PAM manager that handles authentication
requests, loads authentication modules, and manages authentication stacks.
"""

import os
import json
import logging
import importlib
from enum import Enum
from typing import Dict, List, Optional, Callable, Any, Type, Union

from .modules import PAMModule, PAMResult, PasswordModule
from .session import PAMSession

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
PAM_CONFIG_DIR = os.path.join(KOS_ROOT, 'etc/pam.d')

# Ensure directories exist
os.makedirs(PAM_CONFIG_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class PAMServiceType(str, Enum):
    """PAM service types similar to Linux PAM."""
    AUTH = "auth"
    ACCOUNT = "account"
    PASSWORD = "password"
    SESSION = "session"


class PAMControlFlag(str, Enum):
    """Control flags for PAM modules."""
    REQUIRED = "required"      # Must succeed, always executes all modules
    REQUISITE = "requisite"    # Must succeed, stops on failure
    SUFFICIENT = "sufficient"  # If succeeds, stops processing
    OPTIONAL = "optional"      # Success/failure doesn't matter unless it's the only module
    INCLUDE = "include"        # Include another config file


class PAMManager:
    """
    Main PAM manager for KOS.
    
    This class handles authentication requests, loads PAM modules, and manages
    authentication stacks for different services.
    """
    
    def __init__(self):
        """Initialize the PAM manager."""
        self.modules = {}
        self.services = self._load_services()
        self.sessions = {}  # Active sessions
        self._register_default_modules()
        self._ensure_default_configs()
    
    def _register_default_modules(self):
        """Register built-in PAM modules."""
        from .modules import PasswordModule, TokenModule, BiometricModule
        
        self.register_module("pam_unix", PasswordModule())
        self.register_module("pam_token", TokenModule())
        self.register_module("pam_bio", BiometricModule())
    
    def _ensure_default_configs(self):
        """Ensure default PAM configuration files exist."""
        default_configs = {
            "login": [
                {"type": PAMServiceType.AUTH.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []},
                {"type": PAMServiceType.ACCOUNT.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []},
                {"type": PAMServiceType.PASSWORD.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": ["nullok"]},
                {"type": PAMServiceType.SESSION.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []}
            ],
            "sudo": [
                {"type": PAMServiceType.AUTH.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []},
                {"type": PAMServiceType.ACCOUNT.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []}
            ],
            "sshd": [
                {"type": PAMServiceType.AUTH.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []},
                {"type": PAMServiceType.ACCOUNT.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []},
                {"type": PAMServiceType.SESSION.value, "control": PAMControlFlag.REQUIRED.value, 
                 "module": "pam_unix", "args": []}
            ]
        }
        
        for service, config in default_configs.items():
            config_path = os.path.join(PAM_CONFIG_DIR, service)
            if not os.path.exists(config_path):
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
    
    def _load_services(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load all PAM service configurations."""
        services = {}
        
        if os.path.exists(PAM_CONFIG_DIR):
            for filename in os.listdir(PAM_CONFIG_DIR):
                path = os.path.join(PAM_CONFIG_DIR, filename)
                if os.path.isfile(path):
                    try:
                        with open(path, 'r') as f:
                            services[filename] = json.load(f)
                    except json.JSONDecodeError:
                        logger.error(f"Corrupted PAM config: {filename}")
        
        return services
    
    def register_module(self, name: str, module: PAMModule):
        """
        Register a PAM module.
        
        Args:
            name: Name of the module
            module: PAM module instance
        """
        self.modules[name] = module
        logger.info(f"Registered PAM module: {name}")
    
    def authenticate(self, service: str, username: str, 
                    auth_data: Dict[str, Any]) -> PAMResult:
        """
        Authenticate a user using the specified service's PAM stack.
        
        Args:
            service: Name of the PAM service to use
            username: Username to authenticate
            auth_data: Authentication data (e.g., password, token)
            
        Returns:
            PAMResult: Authentication result
        """
        if service not in self.services:
            logger.error(f"PAM service not found: {service}")
            return PAMResult.UNKNOWN_SERVICE
        
        # Process AUTH modules
        auth_result = self._process_modules(
            service, PAMServiceType.AUTH, username, auth_data
        )
        if auth_result != PAMResult.SUCCESS:
            return auth_result
        
        # Process ACCOUNT modules
        account_result = self._process_modules(
            service, PAMServiceType.ACCOUNT, username, auth_data
        )
        if account_result != PAMResult.SUCCESS:
            return account_result
        
        # Create a session if authentication succeeded
        session_id = self._create_session(username, service)
        
        return PAMResult.SUCCESS
    
    def _process_modules(self, service: str, service_type: PAMServiceType, 
                        username: str, auth_data: Dict[str, Any]) -> PAMResult:
        """
        Process PAM modules for a specific service type.
        
        Args:
            service: PAM service name
            service_type: Type of service (auth, account, etc.)
            username: Username
            auth_data: Authentication data
            
        Returns:
            PAMResult: Result of processing modules
        """
        service_type_str = service_type.value if isinstance(service_type, PAMServiceType) else service_type
        
        # Find modules for this service type
        modules = [
            m for m in self.services[service] 
            if m["type"] == service_type_str
        ]
        
        if not modules:
            logger.warning(f"No {service_type_str} modules for service {service}")
            return PAMResult.SUCCESS
        
        result = PAMResult.GENERAL_FAILURE
        for module_config in modules:
            module_name = module_config["module"]
            control_flag = module_config["control"]
            args = module_config.get("args", [])
            
            # Handle INCLUDE flag
            if control_flag == PAMControlFlag.INCLUDE.value:
                included_service = module_name
                if included_service in self.services:
                    include_result = self._process_modules(
                        included_service, service_type, username, auth_data
                    )
                    if include_result != PAMResult.SUCCESS:
                        if control_flag == PAMControlFlag.REQUIRED.value:
                            result = include_result
                            continue
                        elif control_flag == PAMControlFlag.REQUISITE.value:
                            return include_result
                continue
            
            # Get the module
            if module_name not in self.modules:
                logger.error(f"PAM module not found: {module_name}")
                if control_flag == PAMControlFlag.REQUIRED.value or control_flag == PAMControlFlag.REQUISITE.value:
                    return PAMResult.MODULE_NOT_FOUND
                continue
            
            module = self.modules[module_name]
            
            # Call the appropriate method based on service type
            if service_type == PAMServiceType.AUTH:
                module_result = module.authenticate(username, auth_data, args)
            elif service_type == PAMServiceType.ACCOUNT:
                module_result = module.account(username, auth_data, args)
            elif service_type == PAMServiceType.PASSWORD:
                module_result = module.password(username, auth_data, args)
            elif service_type == PAMServiceType.SESSION:
                module_result = module.session(username, auth_data, args)
            else:
                logger.error(f"Unknown PAM service type: {service_type}")
                continue
            
            # Process result based on control flag
            if module_result == PAMResult.SUCCESS:
                if control_flag == PAMControlFlag.SUFFICIENT.value:
                    return PAMResult.SUCCESS
                result = PAMResult.SUCCESS
            else:
                if control_flag == PAMControlFlag.REQUIRED.value:
                    result = module_result
                elif control_flag == PAMControlFlag.REQUISITE.value:
                    return module_result
        
        return result
    
    def _create_session(self, username: str, service: str) -> str:
        """
        Create a new PAM session.
        
        Args:
            username: Username
            service: PAM service name
            
        Returns:
            str: Session ID
        """
        session = PAMSession(username, service)
        self.sessions[session.id] = session
        
        # Process SESSION modules
        self._process_modules(
            service, PAMServiceType.SESSION, username, {"session_id": session.id}
        )
        
        return session.id
    
    def close_session(self, session_id: str) -> bool:
        """
        Close a PAM session.
        
        Args:
            session_id: Session ID to close
            
        Returns:
            bool: Success or failure
        """
        if session_id not in self.sessions:
            logger.warning(f"Session not found: {session_id}")
            return False
        
        session = self.sessions[session_id]
        
        # Process SESSION modules for close
        self._process_modules(
            session.service, PAMServiceType.SESSION, session.username, 
            {"session_id": session.id, "close": True}
        )
        
        del self.sessions[session_id]
        return True
    
    def change_password(self, service: str, username: str, 
                       old_password: str, new_password: str) -> PAMResult:
        """
        Change a user's password.
        
        Args:
            service: PAM service name
            username: Username
            old_password: Current password
            new_password: New password
            
        Returns:
            PAMResult: Result of password change
        """
        if service not in self.services:
            logger.error(f"PAM service not found: {service}")
            return PAMResult.UNKNOWN_SERVICE
        
        # First authenticate with old password
        auth_result = self.authenticate(
            service, username, {"password": old_password}
        )
        if auth_result != PAMResult.SUCCESS:
            return auth_result
        
        # Process PASSWORD modules
        auth_data = {
            "old_password": old_password,
            "new_password": new_password
        }
        
        return self._process_modules(
            service, PAMServiceType.PASSWORD, username, auth_data
        )
    
    def add_service(self, service: str, config: List[Dict[str, Any]]) -> bool:
        """
        Add or update a PAM service configuration.
        
        Args:
            service: Service name
            config: PAM configuration
            
        Returns:
            bool: Success or failure
        """
        # Validate config
        for entry in config:
            if "type" not in entry or "control" not in entry or "module" not in entry:
                logger.error(f"Invalid PAM config entry: {entry}")
                return False
            
            # Validate type and control values
            try:
                PAMServiceType(entry["type"])
            except ValueError:
                logger.error(f"Invalid PAM service type: {entry['type']}")
                return False
            
            try:
                PAMControlFlag(entry["control"])
            except ValueError:
                logger.error(f"Invalid PAM control flag: {entry['control']}")
                return False
        
        # Save configuration
        self.services[service] = config
        config_path = os.path.join(PAM_CONFIG_DIR, service)
        
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save PAM config: {e}")
            return False
    
    def remove_service(self, service: str) -> bool:
        """
        Remove a PAM service configuration.
        
        Args:
            service: Service name
            
        Returns:
            bool: Success or failure
        """
        if service not in self.services:
            logger.warning(f"PAM service not found: {service}")
            return False
        
        config_path = os.path.join(PAM_CONFIG_DIR, service)
        if os.path.exists(config_path):
            try:
                os.remove(config_path)
            except Exception as e:
                logger.error(f"Failed to remove PAM config file: {e}")
                return False
        
        del self.services[service]
        return True

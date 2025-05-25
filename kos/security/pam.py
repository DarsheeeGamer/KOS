"""
KOS Pluggable Authentication Modules (PAM) Implementation

This module provides a simplified PAM-like implementation for KOS,
allowing modular authentication, account management, and session handling.
"""

import os
import sys
import logging
import threading
import json
import importlib
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

from kos.security.users import UserManager

# Set up logging
logger = logging.getLogger('KOS.security.pam')

# Lock for PAM operations
_pam_lock = threading.RLock()

# PAM configuration
_pam_configs = {}  # service_name -> list of module configs

# PAM return codes
PAM_SUCCESS = 0
PAM_ERROR_SYSTEM = 1
PAM_AUTH_ERR = 2
PAM_CRED_INSUFFICIENT = 3
PAM_AUTHINFO_UNAVAIL = 4
PAM_USER_UNKNOWN = 5
PAM_MAXTRIES = 6
PAM_PERM_DENIED = 7
PAM_ABORT = 8
PAM_AUTHTOK_ERR = 9
PAM_SESSION_ERR = 10
PAM_CRED_UNAVAIL = 11
PAM_CRED_EXPIRED = 12
PAM_CRED_ERR = 13
PAM_ACCT_EXPIRED = 14
PAM_AUTHTOK_EXPIRED = 15
PAM_AUTHTOK_RECOVERY_ERR = 16
PAM_AUTHTOK_LOCK_BUSY = 17
PAM_AUTHTOK_DISABLE_AGING = 18
PAM_TRY_AGAIN = 19
PAM_IGNORE = 20
PAM_MODULE_UNKNOWN = 21
PAM_CONV_ERR = 22
PAM_SERVICE_ERR = 23

# PAM module types
PAM_AUTH = "auth"
PAM_ACCOUNT = "account"
PAM_SESSION = "session"
PAM_PASSWORD = "password"

# PAM control flags
PAM_REQUIRED = "required"
PAM_REQUISITE = "requisite"
PAM_SUFFICIENT = "sufficient"
PAM_OPTIONAL = "optional"

# Built-in PAM modules
_pam_modules = {}


class PAMItem:
    """Class representing a PAM configuration item"""
    
    def __init__(self, module_type: str, control_flag: str, module_path: str, module_args: str = ""):
        """
        Initialize a PAM configuration item
        
        Args:
            module_type: Module type (auth, account, session, password)
            control_flag: Control flag (required, requisite, sufficient, optional)
            module_path: Module path
            module_args: Module arguments
        """
        self.module_type = module_type
        self.control_flag = control_flag
        self.module_path = module_path
        self.module_args = module_args
    
    def to_dict(self) -> Dict[str, str]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "module_type": self.module_type,
            "control_flag": self.control_flag,
            "module_path": self.module_path,
            "module_args": self.module_args
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'PAMItem':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            PAMItem instance
        """
        return cls(
            module_type=data.get("module_type", PAM_AUTH),
            control_flag=data.get("control_flag", PAM_REQUIRED),
            module_path=data.get("module_path", ""),
            module_args=data.get("module_args", "")
        )
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.module_type} {self.control_flag} {self.module_path} {self.module_args}"


class PAMHandle:
    """Class representing a PAM transaction handle"""
    
    def __init__(self, service: str, username: str = None):
        """
        Initialize a PAM handle
        
        Args:
            service: Service name
            username: Username (if known)
        """
        self.service = service
        self.username = username
        self.authtok = None
        self.oldauthtok = None
        self.rhost = None
        self.ruser = None
        self.tty = None
        self.data = {}  # Module-specific data
        self.env = {}  # Environment variables
    
    def set_item(self, key: str, value: Any) -> None:
        """
        Set a data item
        
        Args:
            key: Item key
            value: Item value
        """
        self.data[key] = value
    
    def get_item(self, key: str, default: Any = None) -> Any:
        """
        Get a data item
        
        Args:
            key: Item key
            default: Default value
        
        Returns:
            Item value or default
        """
        return self.data.get(key, default)


class PAMConv:
    """Class representing a PAM conversation function"""
    
    def __init__(self, conv_func: Callable[[str, int], str]):
        """
        Initialize a PAM conversation
        
        Args:
            conv_func: Conversation function
        """
        self.conv_func = conv_func
    
    def prompt(self, msg: str, msg_type: int) -> str:
        """
        Prompt user for input
        
        Args:
            msg: Message
            msg_type: Message type
        
        Returns:
            User response
        """
        return self.conv_func(msg, msg_type)


class PAMModule:
    """Base class for PAM modules"""
    
    def __init__(self, args: str = ""):
        """
        Initialize a PAM module
        
        Args:
            args: Module arguments
        """
        self.args = args
        self.args_dict = {}
        
        # Parse arguments
        if args:
            for arg in args.split():
                if "=" in arg:
                    key, value = arg.split("=", 1)
                    self.args_dict[key] = value
                else:
                    self.args_dict[arg] = True
    
    def authenticate(self, pamh: PAMHandle, flags: int) -> int:
        """
        Authenticate user
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_SERVICE_ERR
    
    def setcred(self, pamh: PAMHandle, flags: int) -> int:
        """
        Set credentials
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_SUCCESS
    
    def acct_mgmt(self, pamh: PAMHandle, flags: int) -> int:
        """
        Account management
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_SUCCESS
    
    def open_session(self, pamh: PAMHandle, flags: int) -> int:
        """
        Open session
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_SUCCESS
    
    def close_session(self, pamh: PAMHandle, flags: int) -> int:
        """
        Close session
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_SUCCESS
    
    def chauthtok(self, pamh: PAMHandle, flags: int) -> int:
        """
        Change authentication token
        
        Args:
            pamh: PAM handle
            flags: Flags
        
        Returns:
            PAM return code
        """
        return PAM_AUTHTOK_ERR


class PAMUnix(PAMModule):
    """Unix-style authentication module"""
    
    def authenticate(self, pamh: PAMHandle, flags: int) -> int:
        """Authenticate using Unix-style authentication"""
        if not pamh.username:
            try:
                # Get username
                username = pamh.conv.prompt("Username: ", 1)
                if not username:
                    return PAM_USER_UNKNOWN
                pamh.username = username
            except Exception:
                return PAM_CONV_ERR
        
        # Get user
        user = UserManager.get_user_by_name(pamh.username)
        if not user:
            return PAM_USER_UNKNOWN
        
        # Check if locked
        if hasattr(user, 'locked') and user.locked:
            return PAM_ACCT_EXPIRED
        
        if not pamh.authtok:
            try:
                # Get password
                password = pamh.conv.prompt("Password: ", 0)
                if not password:
                    return PAM_AUTH_ERR
                pamh.authtok = password
            except Exception:
                return PAM_CONV_ERR
        
        # Check password
        if user.check_password(pamh.authtok):
            return PAM_SUCCESS
        else:
            return PAM_AUTH_ERR
    
    def acct_mgmt(self, pamh: PAMHandle, flags: int) -> int:
        """Account management using Unix-style authentication"""
        # Get user
        user = UserManager.get_user_by_name(pamh.username)
        if not user:
            return PAM_USER_UNKNOWN
        
        # Check if locked
        if hasattr(user, 'locked') and user.locked:
            return PAM_ACCT_EXPIRED
        
        return PAM_SUCCESS


class PAMDeny(PAMModule):
    """Always deny access"""
    
    def authenticate(self, pamh: PAMHandle, flags: int) -> int:
        """Always deny authentication"""
        return PAM_AUTH_ERR
    
    def acct_mgmt(self, pamh: PAMHandle, flags: int) -> int:
        """Always deny account management"""
        return PAM_PERM_DENIED


class PAMPermit(PAMModule):
    """Always permit access"""
    
    def authenticate(self, pamh: PAMHandle, flags: int) -> int:
        """Always permit authentication"""
        return PAM_SUCCESS
    
    def acct_mgmt(self, pamh: PAMHandle, flags: int) -> int:
        """Always permit account management"""
        return PAM_SUCCESS


class PAMTime(PAMModule):
    """Time-based access control"""
    
    def acct_mgmt(self, pamh: PAMHandle, flags: int) -> int:
        """Check if access is allowed at current time"""
        # Check for time restrictions in arguments
        current_time = time.localtime()
        
        # Check day of week
        if "days" in self.args_dict:
            allowed_days = self.args_dict["days"].lower()
            day_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
            current_day = current_time.tm_wday
            
            day_allowed = False
            for day in allowed_days.split(","):
                if day in day_map and day_map[day] == current_day:
                    day_allowed = True
                    break
            
            if not day_allowed:
                return PAM_PERM_DENIED
        
        # Check time range
        if "times" in self.args_dict:
            time_ranges = self.args_dict["times"].split(",")
            current_hour = current_time.tm_hour
            current_minute = current_time.tm_min
            current_minutes = current_hour * 60 + current_minute
            
            time_allowed = False
            for time_range in time_ranges:
                if "-" in time_range:
                    start, end = time_range.split("-")
                    
                    # Parse times (format: HHMM)
                    if len(start) == 4 and len(end) == 4:
                        start_hour = int(start[:2])
                        start_minute = int(start[2:])
                        end_hour = int(end[:2])
                        end_minute = int(end[2:])
                        
                        start_minutes = start_hour * 60 + start_minute
                        end_minutes = end_hour * 60 + end_minute
                        
                        if start_minutes <= current_minutes <= end_minutes:
                            time_allowed = True
                            break
            
            if not time_allowed:
                return PAM_PERM_DENIED
        
        return PAM_SUCCESS


# Register built-in modules
_pam_modules["pam_unix.so"] = PAMUnix
_pam_modules["pam_deny.so"] = PAMDeny
_pam_modules["pam_permit.so"] = PAMPermit
_pam_modules["pam_time.so"] = PAMTime


class PAMManager:
    """Manager for PAM operations"""
    
    @classmethod
    def load_module(cls, module_path: str) -> Optional[PAMModule]:
        """
        Load a PAM module
        
        Args:
            module_path: Module path
        
        Returns:
            PAM module class or None if not found
        """
        # Check built-in modules
        if module_path in _pam_modules:
            return _pam_modules[module_path]
        
        # Try to load external module
        # In a real implementation, this would load a shared library
        # For now, just return None
        return None
    
    @classmethod
    def add_service(cls, service: str, config_items: List[PAMItem]) -> Tuple[bool, str]:
        """
        Add a PAM service configuration
        
        Args:
            service: Service name
            config_items: List of configuration items
        
        Returns:
            (success, message)
        """
        with _pam_lock:
            _pam_configs[service] = config_items
            return True, f"Service {service} configured"
    
    @classmethod
    def remove_service(cls, service: str) -> Tuple[bool, str]:
        """
        Remove a PAM service configuration
        
        Args:
            service: Service name
        
        Returns:
            (success, message)
        """
        with _pam_lock:
            if service in _pam_configs:
                del _pam_configs[service]
                return True, f"Service {service} removed"
            else:
                return False, f"Service {service} not found"
    
    @classmethod
    def get_service_config(cls, service: str) -> List[PAMItem]:
        """
        Get PAM service configuration
        
        Args:
            service: Service name
        
        Returns:
            List of configuration items
        """
        with _pam_lock:
            return _pam_configs.get(service, [])
    
    @classmethod
    def authenticate(cls, service: str, username: str, password: str, 
                   conv_func: Optional[Callable[[str, int], str]] = None) -> Tuple[bool, str]:
        """
        Authenticate user
        
        Args:
            service: Service name
            username: Username
            password: Password
            conv_func: Conversation function
        
        Returns:
            (success, message)
        """
        # Create PAM handle
        pamh = PAMHandle(service, username)
        pamh.authtok = password
        
        # Set conversation function
        if conv_func:
            pamh.conv = PAMConv(conv_func)
        else:
            # Default conversation function
            def default_conv(msg: str, msg_type: int) -> str:
                if msg_type == 0:  # Hidden input
                    return password
                else:
                    return username
            pamh.conv = PAMConv(default_conv)
        
        # Get service configuration
        config_items = cls.get_service_config(service)
        if not config_items:
            return False, f"Service {service} not configured"
        
        # Process authentication modules
        auth_items = [item for item in config_items if item.module_type == PAM_AUTH]
        
        auth_success = False
        required_success = True
        
        for item in auth_items:
            # Load module
            module_class = cls.load_module(item.module_path)
            if not module_class:
                if item.control_flag == PAM_REQUIRED or item.control_flag == PAM_REQUISITE:
                    required_success = False
                continue
            
            # Instantiate module
            module = module_class(item.module_args)
            
            # Call module's authenticate function
            result = module.authenticate(pamh, 0)
            
            # Process result based on control flag
            if item.control_flag == PAM_REQUIRED:
                if result != PAM_SUCCESS:
                    required_success = False
            elif item.control_flag == PAM_REQUISITE:
                if result != PAM_SUCCESS:
                    return False, "Authentication failed"
            elif item.control_flag == PAM_SUFFICIENT:
                if result == PAM_SUCCESS:
                    auth_success = True
                    break
        
        # Process account management modules
        if auth_success or required_success:
            acct_items = [item for item in config_items if item.module_type == PAM_ACCOUNT]
            
            for item in acct_items:
                # Load module
                module_class = cls.load_module(item.module_path)
                if not module_class:
                    if item.control_flag == PAM_REQUIRED or item.control_flag == PAM_REQUISITE:
                        required_success = False
                    continue
                
                # Instantiate module
                module = module_class(item.module_args)
                
                # Call module's acct_mgmt function
                result = module.acct_mgmt(pamh, 0)
                
                # Process result based on control flag
                if item.control_flag == PAM_REQUIRED:
                    if result != PAM_SUCCESS:
                        required_success = False
                elif item.control_flag == PAM_REQUISITE:
                    if result != PAM_SUCCESS:
                        return False, "Account validation failed"
                elif item.control_flag == PAM_SUFFICIENT:
                    if result == PAM_SUCCESS:
                        auth_success = True
                        break
        
        if auth_success or required_success:
            return True, "Authentication successful"
        else:
            return False, "Authentication failed"
    
    @classmethod
    def open_session(cls, service: str, username: str) -> Tuple[bool, str]:
        """
        Open a session
        
        Args:
            service: Service name
            username: Username
        
        Returns:
            (success, message)
        """
        # Create PAM handle
        pamh = PAMHandle(service, username)
        
        # Get service configuration
        config_items = cls.get_service_config(service)
        if not config_items:
            return False, f"Service {service} not configured"
        
        # Process session modules
        session_items = [item for item in config_items if item.module_type == PAM_SESSION]
        
        session_success = True
        
        for item in session_items:
            # Load module
            module_class = cls.load_module(item.module_path)
            if not module_class:
                continue
            
            # Instantiate module
            module = module_class(item.module_args)
            
            # Call module's open_session function
            result = module.open_session(pamh, 0)
            
            # Process result based on control flag
            if (item.control_flag == PAM_REQUIRED or item.control_flag == PAM_REQUISITE) and result != PAM_SUCCESS:
                session_success = False
                break
        
        if session_success:
            return True, "Session opened"
        else:
            return False, "Failed to open session"
    
    @classmethod
    def close_session(cls, service: str, username: str) -> Tuple[bool, str]:
        """
        Close a session
        
        Args:
            service: Service name
            username: Username
        
        Returns:
            (success, message)
        """
        # Create PAM handle
        pamh = PAMHandle(service, username)
        
        # Get service configuration
        config_items = cls.get_service_config(service)
        if not config_items:
            return False, f"Service {service} not configured"
        
        # Process session modules
        session_items = [item for item in config_items if item.module_type == PAM_SESSION]
        
        session_success = True
        
        for item in session_items:
            # Load module
            module_class = cls.load_module(item.module_path)
            if not module_class:
                continue
            
            # Instantiate module
            module = module_class(item.module_args)
            
            # Call module's close_session function
            result = module.close_session(pamh, 0)
            
            # Process result based on control flag
            if (item.control_flag == PAM_REQUIRED or item.control_flag == PAM_REQUISITE) and result != PAM_SUCCESS:
                session_success = False
                break
        
        if session_success:
            return True, "Session closed"
        else:
            return False, "Failed to close session"
    
    @classmethod
    def change_password(cls, service: str, username: str, old_password: str, new_password: str) -> Tuple[bool, str]:
        """
        Change user password
        
        Args:
            service: Service name
            username: Username
            old_password: Old password
            new_password: New password
        
        Returns:
            (success, message)
        """
        # Create PAM handle
        pamh = PAMHandle(service, username)
        pamh.authtok = new_password
        pamh.oldauthtok = old_password
        
        # Get service configuration
        config_items = cls.get_service_config(service)
        if not config_items:
            return False, f"Service {service} not configured"
        
        # Process password modules
        password_items = [item for item in config_items if item.module_type == PAM_PASSWORD]
        
        password_success = False
        required_success = True
        
        for item in password_items:
            # Load module
            module_class = cls.load_module(item.module_path)
            if not module_class:
                if item.control_flag == PAM_REQUIRED or item.control_flag == PAM_REQUISITE:
                    required_success = False
                continue
            
            # Instantiate module
            module = module_class(item.module_args)
            
            # Call module's chauthtok function
            result = module.chauthtok(pamh, 0)
            
            # Process result based on control flag
            if item.control_flag == PAM_REQUIRED:
                if result != PAM_SUCCESS:
                    required_success = False
            elif item.control_flag == PAM_REQUISITE:
                if result != PAM_SUCCESS:
                    return False, "Password change failed"
            elif item.control_flag == PAM_SUFFICIENT:
                if result == PAM_SUCCESS:
                    password_success = True
                    break
        
        if password_success or required_success:
            return True, "Password changed"
        else:
            return False, "Password change failed"
    
    @classmethod
    def save_config(cls, config_file: str) -> Tuple[bool, str]:
        """
        Save PAM configuration to file
        
        Args:
            config_file: Config file path
        
        Returns:
            (success, message)
        """
        with _pam_lock:
            try:
                data = {}
                for service, items in _pam_configs.items():
                    data[service] = [item.to_dict() for item in items]
                
                with open(config_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"PAM configuration saved to {config_file}"
            except Exception as e:
                logger.error(f"Error saving PAM configuration: {e}")
                return False, str(e)
    
    @classmethod
    def load_config(cls, config_file: str) -> Tuple[bool, str]:
        """
        Load PAM configuration from file
        
        Args:
            config_file: Config file path
        
        Returns:
            (success, message)
        """
        with _pam_lock:
            try:
                if not os.path.exists(config_file):
                    return False, f"Config file {config_file} not found"
                
                with open(config_file, 'r') as f:
                    data = json.load(f)
                
                _pam_configs.clear()
                for service, items_data in data.items():
                    _pam_configs[service] = [PAMItem.from_dict(item_data) for item_data in items_data]
                
                return True, "PAM configuration loaded"
            except Exception as e:
                logger.error(f"Error loading PAM configuration: {e}")
                return False, str(e)
    
    @classmethod
    def create_default_config(cls) -> Tuple[bool, str]:
        """
        Create default PAM configuration
        
        Returns:
            (success, message)
        """
        with _pam_lock:
            # Create login service
            login_items = [
                PAMItem(PAM_AUTH, PAM_REQUIRED, "pam_unix.so", "nullok"),
                PAMItem(PAM_ACCOUNT, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_SESSION, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_PASSWORD, PAM_REQUIRED, "pam_unix.so", "nullok")
            ]
            
            _pam_configs["login"] = login_items
            
            # Create ssh service
            ssh_items = [
                PAMItem(PAM_AUTH, PAM_REQUIRED, "pam_unix.so", "nullok"),
                PAMItem(PAM_ACCOUNT, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_ACCOUNT, PAM_REQUIRED, "pam_time.so"),
                PAMItem(PAM_SESSION, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_PASSWORD, PAM_REQUIRED, "pam_unix.so", "nullok")
            ]
            
            _pam_configs["ssh"] = ssh_items
            
            # Create sudo service
            sudo_items = [
                PAMItem(PAM_AUTH, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_ACCOUNT, PAM_REQUIRED, "pam_unix.so"),
                PAMItem(PAM_SESSION, PAM_REQUIRED, "pam_unix.so")
            ]
            
            _pam_configs["sudo"] = sudo_items
            
            return True, "Default PAM configuration created"


def initialize():
    """Initialize PAM system"""
    logger.info("Initializing PAM system")
    
    # Create PAM directory
    pam_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(pam_dir, exist_ok=True)
    
    # Load config if it exists
    config_file = os.path.join(pam_dir, 'pam.json')
    if os.path.exists(config_file):
        PAMManager.load_config(config_file)
    else:
        # Create default config
        PAMManager.create_default_config()
        PAMManager.save_config(config_file)
    
    logger.info("PAM system initialized")


# Initialize on module load
initialize()

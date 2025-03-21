"""
kLayer Module: Controlled Interaction for KOS Applications

The kLayer module in Kaede OS (KOS) serves as a comprehensive interface
that enables seamless integration between KOS applications and the core OS. 
It provides a C++ compatible translation layer that allows applications to 
interact with the kernel while maintaining isolation boundaries.

Key features:
- Application lifecycle management without affecting KOS core
- Secure API boundaries for filesystem, process, package, and user systems
- Translation layer for C++ and other language bindings
- Controlled resource access and permissions

This module is the primary interface for KOS application developers.
"""
import logging
import ctypes
import json
import sys
import traceback
from typing import Dict, Any, List, Optional, Union, Callable, Type
from datetime import datetime
import os
import threading
import queue

logger = logging.getLogger('KOS.klayer')

class KOSIntegrationError(Exception):
    """Base exception for KOS integration errors"""
    pass

class CTypeTranslationError(KOSIntegrationError):
    """Error during C/C++ type translation"""
    pass

# Thread-safe singleton instance management
_instance_lock = threading.RLock()
_initialized_components = set()

# C++ Translation Layer Classes
class CPPTypeTranslator:
    """Translates between Python and C/C++ data types"""
    
    # Type mapping between Python and C++ types
    TYPE_MAPPING = {
        'int': ctypes.c_int,
        'float': ctypes.c_float,
        'double': ctypes.c_double,
        'bool': ctypes.c_bool,
        'char': ctypes.c_char,
        'char*': ctypes.c_char_p,
        'void*': ctypes.c_void_p,
        'unsigned int': ctypes.c_uint,
        'long': ctypes.c_long,
        'unsigned long': ctypes.c_ulong,
        'short': ctypes.c_short,
        'unsigned short': ctypes.c_ushort,
        'long long': ctypes.c_longlong,
        'unsigned long long': ctypes.c_ulonglong
    }
    
    @classmethod
    def to_c_type(cls, py_value, c_type_name: str) -> Any:
        """Convert Python value to C type"""
        if c_type_name not in cls.TYPE_MAPPING:
            raise CTypeTranslationError(f"Unsupported C type: {c_type_name}")
            
        c_type = cls.TYPE_MAPPING[c_type_name]
        try:
            return c_type(py_value)
        except Exception as e:
            raise CTypeTranslationError(f"Failed to convert {py_value} to {c_type_name}: {e}")
    
    @classmethod
    def from_c_type(cls, c_value, py_type: Type) -> Any:
        """Convert C type to Python value"""
        try:
            return py_type(c_value.value)
        except Exception as e:
            raise CTypeTranslationError(f"Failed to convert C value to {py_type.__name__}: {e}")
    
    @classmethod
    def create_c_struct(cls, struct_fields: List[tuple]) -> Type:
        """Dynamically create a C struct type"""
        try:
            class DynamicStruct(ctypes.Structure):
                _fields_ = struct_fields
            return DynamicStruct
        except Exception as e:
            raise CTypeTranslationError(f"Failed to create C struct: {e}")
    
    @classmethod
    def struct_to_dict(cls, struct) -> Dict[str, Any]:
        """Convert C struct to Python dictionary"""
        try:
            result = {}
            for field_name, _ in struct._fields_:
                result[field_name] = getattr(struct, field_name)
            return result
        except Exception as e:
            raise CTypeTranslationError(f"Failed to convert struct to dict: {e}")
    
    @classmethod
    def dict_to_struct(cls, data: Dict[str, Any], struct_type: Type) -> Any:
        """Convert Python dictionary to C struct"""
        try:
            struct = struct_type()
            for key, value in data.items():
                if hasattr(struct, key):
                    setattr(struct, key, value)
            return struct
        except Exception as e:
            raise CTypeTranslationError(f"Failed to convert dict to struct: {e}")


class KOSCInterface:
    """Base class for KOS C interface wrappers"""
    
    def __init__(self):
        self.error_code = 0
        self.error_message = ""
    
    def clear_error(self):
        """Clear the last error"""
        self.error_code = 0
        self.error_message = ""
    
    def set_error(self, code: int, message: str):
        """Set an error code and message"""
        self.error_code = code
        self.error_message = message
        logger.error(f"KOS C Interface error {code}: {message}")
    
    def wrap_call(self, func: Callable, *args, **kwargs) -> Any:
        """Wrap a function call with error handling"""
        self.clear_error()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.set_error(1, str(e))
            logger.error(f"Error in C interface: {e}")
            logger.debug(traceback.format_exc())
            return None

# Core KOS integration interfaces
class klayer_fs:
    """Enhanced filesystem interface for KOS applications"""
    _filesystem_instance = None
    _initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        return cls._initialized and cls._filesystem_instance is not None

    @classmethod
    def set_filesystem(cls, filesystem):
        cls._filesystem_instance = filesystem
        cls._initialized = True
        logger.info("Enhanced kLayer filesystem interface initialized")

    @classmethod
    def get_file_info(cls, kos_path: str) -> Dict[str, Any]:
        """Get detailed file information"""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.get_file_info(kos_path)

    @classmethod
    def read_file(cls, kos_path: str) -> str:
        """Read content of a file from the KOS file system."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.read_file(kos_path)

    @classmethod
    def write_file(cls, kos_path: str, content: str):
        """Write content to a file in the KOS file system."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.write_file(kos_path, content)

    @classmethod
    def list_directory(cls, kos_path: str, long_format: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """List directory contents in the KOS file system."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.list_dir(kos_path, long_format)

    @classmethod
    def change_directory(cls, kos_path: str):
        """Change current working directory."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.change_directory(kos_path)

    @classmethod
    def get_current_path(cls) -> str:
        """Get current working directory path."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.current_path

    @classmethod
    def create_directory(cls, kos_path: str, mode: int = 0o755):
        """Create a new directory."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.mkdir(kos_path, mode)

    @classmethod
    def remove(cls, kos_path: str, recursive: bool = False):
        """Remove a file or directory."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.remove(kos_path, recursive)

    @classmethod
    def copy(cls, source: str, dest: str, recursive: bool = False):
        """Copy a file or directory."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.copy(source, dest, recursive)

    @classmethod
    def move(cls, source: str, dest: str):
        """Move/rename a file or directory."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.move(source, dest)

    @classmethod
    def chmod(cls, kos_path: str, mode: int):
        """Change file/directory permissions."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.chmod(kos_path, mode)

    @classmethod
    def find(cls, path: str, pattern: Optional[str] = None, file_type: Optional[str] = None) -> List[str]:
        """Find files/directories matching criteria."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.find(path, pattern, file_type)

    @classmethod
    def touch(cls, kos_path: str):
        """Update file timestamps."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        cls._filesystem_instance.touch(kos_path)

    @classmethod
    def get_directory_tree(cls, path: str) -> Dict[str, Any]:
        """Get directory structure as a tree."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS FileSystem not initialized")
        return cls._filesystem_instance.get_directory_tree(path)

class klayer_process:
    """Enhanced process management interface for KOS applications"""
    _process_manager_instance = None
    _initialized = False

    @classmethod
    def set_process_manager(cls, process_manager):
        cls._process_manager_instance = process_manager
        cls._initialized = True
        logger.info("Enhanced kLayer process management interface initialized")

    @classmethod
    def create_process(cls, command: str, args: List[str] = None) -> Dict[str, Any]:
        """Create a new KOS process"""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ProcessManager not initialized")
        return cls._process_manager_instance.create_process(command, args)

    @classmethod
    def get_system_resources(cls) -> Dict[str, Any]:
        """Get detailed system resource usage."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ProcessManager not initialized in kLayer.")
        return cls._process_manager_instance.get_system_resources()

    @classmethod
    def list_processes(cls, refresh: bool = False) -> List[Any]:
        """List all running processes."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ProcessManager not initialized in kLayer.")
        return cls._process_manager_instance.list_processes(refresh)

    @classmethod
    def get_process_tree(cls) -> Dict[int, List[Any]]:
        """Get process hierarchy tree."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ProcessManager not initialized in kLayer.")
        return cls._process_manager_instance.get_process_tree()

    @classmethod
    def get_process(cls, pid: int) -> Optional[Any]:
        """Get information about a specific process."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ProcessManager not initialized in kLayer.")
        return cls._process_manager_instance.get_process(pid)

class klayer_package:
    """Enhanced package management interface for KOS applications"""
    _package_manager_instance = None
    _initialized = False

    @classmethod
    def set_package_manager(cls, package_manager):
        cls._package_manager_instance = package_manager
        cls._initialized = True
        logger.info("Enhanced kLayer package management interface initialized")

    @classmethod
    def get_package_info(cls, package_name: str) -> Dict[str, Any]:
        """Get detailed package information"""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS Package Manager not initialized")
        return cls._package_manager_instance.get_package_info(package_name)

    @classmethod
    def install_package(cls, package_name: str) -> bool:
        """Install a package."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS Package Manager not initialized in kLayer.")
        return cls._package_manager_instance.install(package_name)

    @classmethod
    def remove_package(cls, package_name: str) -> bool:
        """Remove an installed package."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS Package Manager not initialized in kLayer.")
        return cls._package_manager_instance.remove(package_name)

    @classmethod
    def list_installed_packages(cls) -> List[Dict[str, Any]]:
        """List installed packages."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS Package Manager not initialized in kLayer.")
        return cls._package_manager_instance.list_packages()

class klayer_user:
    """Enhanced user management interface for KOS applications"""
    _user_system_instance = None
    _initialized = False

    @classmethod
    def set_user_system(cls, user_system):
        cls._user_system_instance = user_system
        cls._initialized = True
        logger.info("Enhanced kLayer user management interface initialized")

    @classmethod
    def get_user_info(cls) -> Dict[str, Any]:
        """Get detailed user information"""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS User System not initialized")
        return cls._user_system_instance.get_user_info()


# KOS environment integration
_kos_env_vars: Dict[str, str] = {}

def set_env_vars(env_vars: Dict[str, str]):
    """Set KOS environment variables"""
    global _kos_env_vars
    _kos_env_vars = env_vars
    logger.info("KOS environment variables updated")

def get_env_var(var_name: str, default: Optional[str] = None) -> Optional[str]:
    """Get KOS environment variable"""
    return _kos_env_vars.get(var_name, default)

def get_env_vars() -> Dict[str, str]:
    """Get all KOS environment variables"""
    return _kos_env_vars.copy()

# Safe application termination
def kos_app_exit(code: int = 0):
    """Safely exit KOS application without terminating KOS itself"""
    logger.info(f"KOS application exiting with code {code}")
    raise SystemExit(code)

def exit_app(code: int = 0):
    """Legacy exit function - redirects to kos_app_exit"""
    return kos_app_exit(code)

class klayer_manual:
    """Provides access to the KOS Manual System."""

    _manual_system_instance = None
    _initialized = False

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if the manual system is initialized."""
        return cls._initialized and cls._manual_system_instance is not None

    @classmethod
    def set_manual_system(cls, manual_system):
        """Set the KOS ManualSystem instance."""
        cls._manual_system_instance = manual_system
        cls._initialized = True
        logger.info("kLayer manual system interface initialized")

    @classmethod
    def get_manual_page(cls, command_name: str) -> Optional[str]:
        """Retrieve the manual page content for a KOS command."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ManualSystem not initialized in kLayer.")
        return cls._manual_system_instance.get_page(command_name)

    @classmethod
    def list_manual_topics(cls) -> List[str]:
        """List available topics in the KOS Manual System."""
        if not cls.is_initialized():
            raise KOSIntegrationError("KOS ManualSystem not initialized in kLayer.")
        return cls._manual_system_instance.list_topics()

# Initialize the kLayer subsystem 
def initialize_klayer(filesystem=None, package_manager=None, user_system=None, process_manager=None):
    """Initialize kLayer with all KOS core components
    
    This function provides a single point of initialization for all kLayer interfaces,
    making it easy to integrate applications with KOS core components.
    
    Args:
        filesystem: FileSystem instance for file operations
        package_manager: PackageManager instance for package management
        user_system: UserSystem instance for user authentication and management
        process_manager: ProcessManager instance for process control
    
    Returns:
        bool: True if initialization successful
    """
    with _instance_lock:
        if filesystem:
            klayer_fs.set_filesystem(filesystem)
            _initialized_components.add('filesystem')
            
        if package_manager:
            klayer_package.set_package_manager(package_manager)
            _initialized_components.add('package_manager')
            
        if user_system:
            klayer_user.set_user_system(user_system)
            _initialized_components.add('user_system')
            
        if process_manager:
            klayer_process.set_process_manager(process_manager)
            _initialized_components.add('process_manager')
    
    # Set default environment variables
    set_env_vars({
        'KOS_VERSION': '1.0.0',
        'KOS_HOME': os.path.expanduser('~/.kos'),
        'KOS_CONF': os.path.expanduser('~/.kos/conf'),
        'KOS_TEMP': '/tmp/kos'
    })
    
    initialized_count = len(_initialized_components)
    logger.info(f"kLayer initialized with {initialized_count} components: {', '.join(_initialized_components)}")
    return True

# --- User Information ---
_kos_user_system = None

def set_user_system(user_system):
    """Set the KOS UserSystem instance."""
    global _kos_user_system
    _kos_user_system = user_system

def get_current_user() -> Optional[str]:
    """Get the current KOS username."""
    if not _kos_user_system:
        raise KOSIntegrationError("KOS UserSystem not initialized in kLayer.")
    return _kos_user_system.current_user

def get_user_info() -> Dict[str, Any]:
    """Get user information for the current KOS user."""
    if not _kos_user_system:
        raise KOSIntegrationError("KOS UserSystem not initialized in kLayer.")
    return _kos_user_system.get_user_info()
"""
KOS System System Calls

This module provides system calls for core system functionality, including
system information, time, and environment management.
"""

import logging
import time
import os
import sys
import platform
from typing import Dict, List, Any, Optional

from . import syscall, SyscallCategory, SyscallResult, SyscallError
from .. import process
from ..hal import get_hardware_info

logger = logging.getLogger('KOS.syscall.system')

# System environment variables
_env_vars = {}

@syscall(SyscallCategory.SYSTEM)
def get_system_info() -> Dict[str, Any]:
    """
    Get system information
    
    Returns:
        System information or error
    """
    try:
        # Get hardware information
        hw_info = get_hardware_info()
        
        # Get process information
        process_count = len(process.get_all_processes())
        
        # Build system information
        sys_info = {
            'hostname': platform.node(),
            'os': {
                'name': 'KOS',
                'version': '0.1.0',
                'build': '20250525',
                'platform': platform.system(),
                'platform_version': platform.version(),
                'platform_release': platform.release(),
                'platform_machine': platform.machine(),
                'platform_processor': platform.processor()
            },
            'hardware': hw_info,
            'process_count': process_count,
            'uptime': time.time() - process.get_boot_time(),
            'current_time': time.time()
        }
        
        return sys_info
    
    except Exception as e:
        logger.error(f"Error getting system information: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_environment_variable(name: str) -> str:
    """
    Get an environment variable
    
    Args:
        name: Environment variable name
    
    Returns:
        Environment variable value or error
    """
    try:
        # Validate arguments
        if not name:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Environment variable name cannot be empty")
        
        # Check if the environment variable exists
        if name in _env_vars:
            return _env_vars[name]
        elif name in os.environ:
            return os.environ[name]
        else:
            return SyscallResult(False, SyscallError.NOT_FOUND, 
                               message=f"Environment variable '{name}' not found")
    
    except Exception as e:
        logger.error(f"Error getting environment variable '{name}': {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def set_environment_variable(name: str, value: str) -> bool:
    """
    Set an environment variable
    
    Args:
        name: Environment variable name
        value: Environment variable value
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not name:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Environment variable name cannot be empty")
        
        # Set the environment variable
        _env_vars[name] = value
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting environment variable '{name}': {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_all_environment_variables() -> Dict[str, str]:
    """
    Get all environment variables
    
    Returns:
        Dictionary of environment variables or error
    """
    try:
        # Combine OS environment variables with KOS environment variables
        env = dict(os.environ)
        env.update(_env_vars)
        
        return env
    
    except Exception as e:
        logger.error(f"Error getting environment variables: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_current_time() -> float:
    """
    Get current system time
    
    Returns:
        Current time (seconds since epoch) or error
    """
    try:
        return time.time()
    
    except Exception as e:
        logger.error(f"Error getting current time: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def sleep(seconds: float) -> bool:
    """
    Sleep for the specified number of seconds
    
    Args:
        seconds: Number of seconds to sleep
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if seconds < 0:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Sleep time cannot be negative")
        
        # Sleep
        time.sleep(seconds)
        
        return True
    
    except Exception as e:
        logger.error(f"Error sleeping: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_system_load() -> Dict[str, Any]:
    """
    Get system load information
    
    Returns:
        System load information or error
    """
    try:
        # Get hardware information for CPU and memory usage
        hw_info = get_hardware_info()
        
        # Build system load information
        load_info = {
            'cpu': hw_info.get('cpu', {}).get('percent', 0),
            'memory': {
                'percent': hw_info.get('memory', {}).get('virtual', {}).get('percent', 0),
                'available': hw_info.get('memory', {}).get('virtual', {}).get('available', 0),
                'used': hw_info.get('memory', {}).get('virtual', {}).get('used', 0),
                'total': hw_info.get('memory', {}).get('virtual', {}).get('total', 0)
            },
            'process_count': len(process.get_all_processes()),
            'timestamp': time.time()
        }
        
        return load_info
    
    except Exception as e:
        logger.error(f"Error getting system load: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def shutdown_system(reboot: bool = False) -> bool:
    """
    Shutdown or reboot the system
    
    Args:
        reboot: Whether to reboot the system
    
    Returns:
        Success status or error
    """
    try:
        # This is a privileged operation
        # In a real OS, this would check if the caller has permission
        
        # Log the shutdown/reboot request
        if reboot:
            logger.info("System reboot requested")
        else:
            logger.info("System shutdown requested")
        
        # In a real OS, this would actually shut down or reboot the system
        # For now, just return success
        
        return True
    
    except Exception as e:
        logger.error(f"Error shutting down system: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_system_uptime() -> float:
    """
    Get system uptime
    
    Returns:
        System uptime in seconds or error
    """
    try:
        return time.time() - process.get_boot_time()
    
    except Exception as e:
        logger.error(f"Error getting system uptime: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def get_hostname() -> str:
    """
    Get system hostname
    
    Returns:
        Hostname or error
    """
    try:
        return platform.node()
    
    except Exception as e:
        logger.error(f"Error getting hostname: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

@syscall(SyscallCategory.SYSTEM)
def set_hostname(hostname: str) -> bool:
    """
    Set system hostname
    
    Args:
        hostname: New hostname
    
    Returns:
        Success status or error
    """
    try:
        # Validate arguments
        if not hostname:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT, 
                               message="Hostname cannot be empty")
        
        # Validate hostname format
        if len(hostname) > 63:
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Hostname cannot exceed 63 characters")
            
        # Check for valid hostname characters (alphanumeric and hyphen)
        if not all(c.isalnum() or c == '-' for c in hostname):
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Hostname can only contain alphanumeric characters and hyphens")
        
        # Cannot start or end with hyphen
        if hostname.startswith('-') or hostname.endswith('-'):
            return SyscallResult(False, SyscallError.INVALID_ARGUMENT,
                               message="Hostname cannot start or end with a hyphen")
        
        # This is a privileged operation requiring root access
        try:
            # Use platform-specific methods to set hostname
            if sys.platform.startswith('linux'):
                # Use hostnamectl on Linux systems
                import subprocess
                result = subprocess.run(['hostnamectl', 'set-hostname', hostname], 
                                       capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return SyscallResult(False, SyscallError.PERMISSION_DENIED,
                                       message=f"Failed to set hostname: {result.stderr.strip()}")
            elif sys.platform == 'darwin':
                # macOS implementation
                import subprocess
                result = subprocess.run(['scutil', '--set', 'HostName', hostname],
                                       capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return SyscallResult(False, SyscallError.PERMISSION_DENIED,
                                       message=f"Failed to set hostname: {result.stderr.strip()}")
            elif sys.platform == 'win32':
                # Windows implementation
                import subprocess
                result = subprocess.run(['powershell', '-Command', 
                                       f"Rename-Computer -NewName '{hostname}' -Force"],
                                       capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    return SyscallResult(False, SyscallError.PERMISSION_DENIED,
                                       message=f"Failed to set hostname: {result.stderr.strip()}")
            else:
                # Fallback for other platforms
                os.environ['HOSTNAME'] = hostname
                
            logger.info(f"System hostname set to '{hostname}'")
            return True
        except OSError as e:
            logger.error(f"Failed to set hostname: {e}")
            return SyscallResult(False, SyscallError.PERMISSION_DENIED, 
                               message=f"Permission denied: {e}")
    
    except Exception as e:
        logger.error(f"Error setting hostname: {e}")
        return SyscallResult(False, SyscallError.INTERNAL_ERROR, message=str(e))

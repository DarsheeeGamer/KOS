"""
Kaede Operating System (KOS) - Core Package
"""

from .filesystem.base import FileSystem
from .user_system import UserSystem
from .package_manager import PackageManager as KpmManager  # Alias for backward compatibility
from .commands import KaedeShell
from .auth_manager import AuthenticationManager

__all__ = [
    'FileSystem',
    'UserSystem',
    'KpmManager',
    'KaedeShell',
    'AuthenticationManager'
]
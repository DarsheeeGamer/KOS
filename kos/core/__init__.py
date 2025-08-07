"""
KOS Core Components
Clean, modular architecture
"""

from .vfs import VFS, PickleVFS, get_vfs
from .config import ConfigManager, EnvironmentManager
from .errors import KOSError, VFSError, ShellError

__all__ = [
    'VFS', 'PickleVFS', 'get_vfs',
    'ConfigManager', 'EnvironmentManager',
    'KOSError', 'VFSError', 'ShellError'
]
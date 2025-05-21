"""
Enhanced filesystem implementation with disk and inode management
"""
from .filesystem.base import FileSystem

# Re-export FileSystem from base
__all__ = ['FileSystem']
"""
KOS Virtual File System
========================
The ONE and ONLY VFS implementation - KaedeVFS
Everything stored in kaede.kdsk
"""

from .kaede_vfs import KaedeVFS, get_vfs

__all__ = ['KaedeVFS', 'get_vfs']
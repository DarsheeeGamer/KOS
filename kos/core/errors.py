"""
KOS Exception Hierarchy
Clean error handling
"""

class KOSError(Exception):
    """Base exception for all KOS errors"""
    pass

class VFSError(KOSError):
    """Virtual File System errors"""
    pass

class ShellError(KOSError):
    """Shell command errors"""
    pass

class PackageError(KOSError):
    """Package management errors"""
    pass

class LayerError(KOSError):
    """System layer errors"""
    pass
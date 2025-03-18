class KaedeOSError(Exception):
    """Base exception for Kaede OS"""
    pass

class InvalidDiskFormat(KaedeOSError):
    """Raised when disk format is invalid or corrupted"""
    pass

class DiskFullError(KaedeOSError):
    """Raised when disk is full"""
    pass

class FileNotFound(KaedeOSError):
    """Raised when file is not found"""
    pass

class InodeLimitReached(KaedeOSError):
    """Raised when inode limit is reached"""
    pass

class IOError(KaedeOSError):
    """Raised when I/O operation fails"""
    pass

class DiskRepairFailed(KaedeOSError):
    """Raised when disk repair fails"""
    pass

class PermissionDenied(KaedeOSError):
    """Raised when permission is denied"""
    pass

class NotADirectory(KaedeOSError):
    """Raised when path is not a directory"""
    pass

class IsADirectory(KaedeOSError):
    """Raised when path is a directory but file operation is attempted"""
    pass

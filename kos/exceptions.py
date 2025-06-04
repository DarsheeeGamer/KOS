class KaedeOSError(Exception):
    """Base exception for Kaede OS"""
    pass

# Alias for backwards compatibility and consistency
KOSError = KaedeOSError

class FileSystemError(KaedeOSError):
    """Base exception for filesystem operations"""
    pass

class InvalidDiskFormat(FileSystemError):
    """Raised when disk format is invalid or corrupted"""
    pass

class DiskFullError(FileSystemError):
    """Raised when disk is full"""
    pass

class FileNotFound(FileSystemError):
    """Raised when file is not found"""
    pass

class InodeLimitReached(FileSystemError):
    """Raised when inode limit is reached"""
    pass

class IOError(FileSystemError):
    """Raised when I/O operation fails"""
    pass

class DiskRepairFailed(FileSystemError):
    """Raised when disk repair fails"""
    pass

class PermissionDenied(FileSystemError):
    """Raised when permission is denied"""
    pass

class NotADirectory(FileSystemError):
    """Raised when path is not a directory"""
    pass

class IsADirectory(FileSystemError):
    """Raised when path is a directory but file operation is attempted"""
    pass

# Authentication related exceptions
class AuthenticationError(KaedeOSError):
    """Base exception for authentication related errors"""
    pass

class UserNotFound(AuthenticationError):
    """Raised when user is not found"""
    pass

class InvalidCredentials(AuthenticationError):
    """Raised when credentials are invalid"""
    pass

# Package management related exceptions
class PackageError(KaedeOSError):
    """Base exception for package management related errors"""
    pass

class PackageNotFound(PackageError):
    """Raised when package is not found"""
    pass

class PackageInstallError(PackageError):
    """Raised when package installation fails"""
    pass

class PackageRemoveError(PackageError):
    """Raised when package removal fails"""
    pass
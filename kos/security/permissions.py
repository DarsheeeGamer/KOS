"""
KOS Permissions and Access Control Module

This module provides Unix-like file and resource permissions for KOS.
"""

import os
import sys
import stat
import logging
import threading
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager, GroupManager
from kos.security.auth import get_current_uid, get_current_gid, get_current_user

# Set up logging
logger = logging.getLogger('KOS.security.permissions')

# Permission bits (same as Unix)
S_IRUSR = 0o400  # Owner has read permission
S_IWUSR = 0o200  # Owner has write permission
S_IXUSR = 0o100  # Owner has execute permission
S_IRGRP = 0o040  # Group has read permission
S_IWGRP = 0o020  # Group has write permission
S_IXGRP = 0o010  # Group has execute permission
S_IROTH = 0o004  # Others have read permission
S_IWOTH = 0o002  # Others have write permission
S_IXOTH = 0o001  # Others have execute permission

# Special bits
S_ISUID = 0o4000  # Set user ID on execution
S_ISGID = 0o2000  # Set group ID on execution
S_ISVTX = 0o1000  # Sticky bit

# Default permission modes
DEFAULT_FILE_MODE = 0o644      # rw-r--r--
DEFAULT_DIR_MODE = 0o755       # rwxr-xr-x
DEFAULT_EXEC_MODE = 0o755      # rwxr-xr-x
DEFAULT_SYSFILE_MODE = 0o644   # rw-r--r--
DEFAULT_SYSDIR_MODE = 0o755    # rwxr-xr-x

# File type bits
S_IFDIR = 0o40000  # Directory
S_IFREG = 0o100000  # Regular file
S_IFLNK = 0o120000  # Symbolic link

# Lock for permission operations
_permission_lock = threading.RLock()


class FileMetadata:
    """Class to store file metadata including permissions"""
    
    def __init__(self, path: str, uid: int = 0, gid: int = 0, mode: int = DEFAULT_FILE_MODE,
                 is_dir: bool = False, size: int = 0, atime: float = 0, mtime: float = 0,
                 ctime: float = 0):
        """
        Initialize file metadata
        
        Args:
            path: File path
            uid: Owner user ID
            gid: Owner group ID
            mode: Permission mode
            is_dir: Is this a directory
            size: File size in bytes
            atime: Access time
            mtime: Modification time
            ctime: Creation time
        """
        self.path = path
        self.uid = uid
        self.gid = gid
        self.mode = mode
        self.is_dir = is_dir
        self.size = size
        self.atime = atime
        self.mtime = mtime
        self.ctime = ctime
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "path": self.path,
            "uid": self.uid,
            "gid": self.gid,
            "mode": self.mode,
            "is_dir": self.is_dir,
            "size": self.size,
            "atime": self.atime,
            "mtime": self.mtime,
            "ctime": self.ctime
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileMetadata':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            FileMetadata instance
        """
        return cls(
            path=data["path"],
            uid=data["uid"],
            gid=data["gid"],
            mode=data["mode"],
            is_dir=data["is_dir"],
            size=data["size"],
            atime=data["atime"],
            mtime=data["mtime"],
            ctime=data["ctime"]
        )
    
    @classmethod
    def from_stat(cls, path: str, stat_result) -> 'FileMetadata':
        """
        Create from os.stat result
        
        Args:
            path: File path
            stat_result: Result from os.stat
        
        Returns:
            FileMetadata instance
        """
        return cls(
            path=path,
            uid=stat_result.st_uid,
            gid=stat_result.st_gid,
            mode=stat_result.st_mode,
            is_dir=stat.S_ISDIR(stat_result.st_mode),
            size=stat_result.st_size,
            atime=stat_result.st_atime,
            mtime=stat_result.st_mtime,
            ctime=stat_result.st_ctime
        )


def check_permission(metadata: FileMetadata, permission_type: str) -> bool:
    """
    Check if current user has specified permission on file
    
    Args:
        metadata: File metadata
        permission_type: Permission type (read, write, execute)
    
    Returns:
        True if user has permission
    """
    # Get current user and group
    uid = get_current_uid()
    gid = get_current_gid()
    user = get_current_user()
    
    # Root can do anything
    if uid == 0:
        return True
    
    # Convert permission type to bits
    if permission_type == "read":
        user_bit = S_IRUSR
        group_bit = S_IRGRP
        other_bit = S_IROTH
    elif permission_type == "write":
        user_bit = S_IWUSR
        group_bit = S_IWGRP
        other_bit = S_IWOTH
    elif permission_type == "execute":
        user_bit = S_IXUSR
        group_bit = S_IXGRP
        other_bit = S_IXOTH
    else:
        return False
    
    # Check owner permission
    if metadata.uid == uid:
        return bool(metadata.mode & user_bit)
    
    # Check group permission
    if metadata.gid == gid:
        return bool(metadata.mode & group_bit)
    
    # Check if user is in the file's group
    if user and user.groups:
        file_group = GroupManager.get_group_by_gid(metadata.gid)
        if file_group and file_group.name in user.groups:
            return bool(metadata.mode & group_bit)
    
    # Check other permission
    return bool(metadata.mode & other_bit)


def can_read(metadata: FileMetadata) -> bool:
    """
    Check if current user can read file
    
    Args:
        metadata: File metadata
    
    Returns:
        True if user can read
    """
    return check_permission(metadata, "read")


def can_write(metadata: FileMetadata) -> bool:
    """
    Check if current user can write to file
    
    Args:
        metadata: File metadata
    
    Returns:
        True if user can write
    """
    return check_permission(metadata, "write")


def can_execute(metadata: FileMetadata) -> bool:
    """
    Check if current user can execute file
    
    Args:
        metadata: File metadata
    
    Returns:
        True if user can execute
    """
    return check_permission(metadata, "execute")


def chmod(path: str, mode: int) -> Tuple[bool, str]:
    """
    Change file mode
    
    Args:
        path: File path
        mode: New permission mode
    
    Returns:
        (success, message)
    """
    # Get current user
    uid = get_current_uid()
    
    try:
        # Get file metadata
        stat_result = os.stat(path)
        metadata = FileMetadata.from_stat(path, stat_result)
        
        # Check if user is owner or root
        if uid != 0 and metadata.uid != uid:
            return False, "Permission denied"
        
        # Change mode
        os.chmod(path, mode)
        return True, f"Changed mode of {path} to {mode:o}"
    except FileNotFoundError:
        return False, f"No such file or directory: {path}"
    except PermissionError:
        return False, "Permission denied"
    except Exception as e:
        return False, str(e)


def chown(path: str, uid: int = None, gid: int = None) -> Tuple[bool, str]:
    """
    Change file owner and group
    
    Args:
        path: File path
        uid: New user ID (None to leave unchanged)
        gid: New group ID (None to leave unchanged)
    
    Returns:
        (success, message)
    """
    # Get current user
    current_uid = get_current_uid()
    
    # Only root can change owner
    if current_uid != 0:
        return False, "Operation not permitted"
    
    try:
        # Verify uid and gid
        if uid is not None and UserManager.get_user_by_uid(uid) is None:
            return False, f"Invalid user ID: {uid}"
        
        if gid is not None and GroupManager.get_group_by_gid(gid) is None:
            return False, f"Invalid group ID: {gid}"
        
        # Get current ownership
        stat_result = os.stat(path)
        current_uid_value = stat_result.st_uid
        current_gid_value = stat_result.st_gid
        
        # Set new ownership
        os.chown(path, uid if uid is not None else current_uid_value,
                  gid if gid is not None else current_gid_value)
        
        return True, f"Changed owner of {path} to {uid}:{gid}"
    except FileNotFoundError:
        return False, f"No such file or directory: {path}"
    except PermissionError:
        return False, "Permission denied"
    except Exception as e:
        return False, str(e)


def get_umask() -> int:
    """
    Get current umask
    
    Returns:
        Current umask value
    """
    # This is a bit tricky because getting the umask changes it
    # We need to set it back after reading
    current_umask = os.umask(0)
    os.umask(current_umask)  # Restore it
    return current_umask


def set_umask(mask: int) -> int:
    """
    Set umask
    
    Args:
        mask: New umask value
    
    Returns:
        Previous umask value
    """
    return os.umask(mask)


def format_mode(mode: int) -> str:
    """
    Format permission mode as string (like ls -l)
    
    Args:
        mode: Permission mode
    
    Returns:
        Formatted string
    """
    result = ""
    
    # File type
    if stat.S_ISDIR(mode):
        result += "d"
    elif stat.S_ISLNK(mode):
        result += "l"
    else:
        result += "-"
    
    # Owner permissions
    result += "r" if mode & S_IRUSR else "-"
    result += "w" if mode & S_IWUSR else "-"
    if mode & S_ISUID:
        result += "s" if mode & S_IXUSR else "S"
    else:
        result += "x" if mode & S_IXUSR else "-"
    
    # Group permissions
    result += "r" if mode & S_IRGRP else "-"
    result += "w" if mode & S_IWGRP else "-"
    if mode & S_ISGID:
        result += "s" if mode & S_IXGRP else "S"
    else:
        result += "x" if mode & S_IXGRP else "-"
    
    # Other permissions
    result += "r" if mode & S_IROTH else "-"
    result += "w" if mode & S_IWOTH else "-"
    if mode & S_ISVTX:
        result += "t" if mode & S_IXOTH else "T"
    else:
        result += "x" if mode & S_IXOTH else "-"
    
    return result


def parse_mode(mode_str: str) -> int:
    """
    Parse mode string (like chmod)
    
    Args:
        mode_str: Mode string (e.g., "u+x", "644", "a=rwx")
    
    Returns:
        Permission mode
    """
    # Numeric mode
    if mode_str.isdigit():
        return int(mode_str, 8)
    
    # Get current mode (default to a regular file)
    current_mode = 0o644
    
    # Handle symbolic mode
    who = {"u": S_IRUSR | S_IWUSR | S_IXUSR,
           "g": S_IRGRP | S_IWGRP | S_IXGRP,
           "o": S_IROTH | S_IWOTH | S_IXOTH,
           "a": S_IRUSR | S_IWUSR | S_IXUSR | S_IRGRP | S_IWGRP | S_IXGRP | S_IROTH | S_IWOTH | S_IXOTH}
    
    perm = {"r": {"u": S_IRUSR, "g": S_IRGRP, "o": S_IROTH},
            "w": {"u": S_IWUSR, "g": S_IWGRP, "o": S_IWOTH},
            "x": {"u": S_IXUSR, "g": S_IXGRP, "o": S_IXOTH},
            "s": {"u": S_ISUID, "g": S_ISGID},
            "t": {"o": S_ISVTX}}
    
    # Parse symbolic mode
    parts = mode_str.split(",")
    for part in parts:
        # Find operator
        for op in "+-=":
            if op in part:
                break
        else:
            return current_mode  # Invalid format
        
        who_part, perm_part = part.split(op)
        
        # Determine who
        if not who_part:
            who_part = "a"
        
        # Apply permissions
        for w in who_part:
            if w not in who:
                continue
            
            for p in perm_part:
                if p not in perm or w not in perm[p]:
                    continue
                
                if op == "+":
                    current_mode |= perm[p][w]
                elif op == "-":
                    current_mode &= ~perm[p][w]
                elif op == "=":
                    # Clear all permissions for this 'who'
                    current_mode &= ~who[w]
                    # Then add the specified ones
                    for p2 in perm_part:
                        if p2 in perm and w in perm[p2]:
                            current_mode |= perm[p2][w]
    
    return current_mode


def initialize():
    """Initialize permissions module"""
    logger.info("Initializing permissions module")
    
    # Set default umask (022 - rwxr-xr-x for directories, rw-r--r-- for files)
    os.umask(0o022)
    
    logger.info("Permissions module initialized")


# Initialize module
initialize()

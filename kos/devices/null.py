"""
Null Device Implementation

The null device discards all data written to it and returns EOF on read.
Similar to /dev/null on Unix systems.
"""

import os
import logging
from typing import Optional, Any

logger = logging.getLogger('KOS.devices.null')


class NullDevice:
    """
    Null device implementation
    
    Discards all writes and returns empty data on reads.
    """
    
    def __init__(self, name: str = "null"):
        self.name = name
        self.major = 1  # Standard major number for null device
        self.minor = 3  # Standard minor number for null device
        self.mode = 0o666  # World readable/writable
        self.device_type = 'c'  # Character device
        
    def open(self, flags: int = os.O_RDWR) -> 'NullDevice':
        """Open the null device"""
        logger.debug(f"Opening null device with flags {flags}")
        return self
        
    def close(self) -> None:
        """Close the null device"""
        logger.debug("Closing null device")
        
    def read(self, size: int = -1) -> bytes:
        """
        Read from null device - always returns empty bytes
        
        Args:
            size: Number of bytes to read (ignored)
            
        Returns:
            Empty bytes (EOF)
        """
        return b''
        
    def write(self, data: bytes) -> int:
        """
        Write to null device - discards all data
        
        Args:
            data: Data to write (will be discarded)
            
        Returns:
            Number of bytes "written" (length of data)
        """
        return len(data)
        
    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """
        Seek in null device - always succeeds
        
        Args:
            offset: Seek offset
            whence: Seek origin (SEEK_SET, SEEK_CUR, SEEK_END)
            
        Returns:
            Always returns 0
        """
        return 0
        
    def tell(self) -> int:
        """Get current position - always 0"""
        return 0
        
    def truncate(self, size: Optional[int] = None) -> int:
        """Truncate null device - no-op"""
        return 0
        
    def flush(self) -> None:
        """Flush null device - no-op"""
        pass
        
    def fileno(self) -> int:
        """Get file descriptor - returns -1 (not a real fd)"""
        return -1
        
    def isatty(self) -> bool:
        """Check if device is a TTY - always False"""
        return False
        
    def readable(self) -> bool:
        """Check if device is readable - always True"""
        return True
        
    def writable(self) -> bool:
        """Check if device is writable - always True"""
        return True
        
    def seekable(self) -> bool:
        """Check if device is seekable - always True"""
        return True
        
    def ioctl(self, request: int, arg: Any = 0) -> Any:
        """
        Perform ioctl operation
        
        Args:
            request: ioctl request code
            arg: ioctl argument
            
        Returns:
            Always returns 0 (success)
        """
        logger.debug(f"ioctl request {request} on null device")
        return 0
        
    def stat(self) -> dict:
        """Get device statistics"""
        import time
        current_time = time.time()
        
        return {
            'st_mode': 0o020666,  # Character device with 666 permissions
            'st_ino': 0,
            'st_dev': (self.major << 8) | self.minor,
            'st_nlink': 1,
            'st_uid': 0,
            'st_gid': 0,
            'st_size': 0,
            'st_atime': current_time,
            'st_mtime': current_time,
            'st_ctime': current_time,
            'st_blksize': 4096,
            'st_blocks': 0,
            'st_rdev': (self.major << 8) | self.minor,
        }
        
    def __repr__(self) -> str:
        return f"<NullDevice name='{self.name}' major={self.major} minor={self.minor}>"
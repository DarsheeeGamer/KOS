"""
Random Device Implementation

Provides cryptographically secure random data similar to /dev/random and /dev/urandom.
"""

import os
import logging
import secrets
from typing import Optional, Any

logger = logging.getLogger('KOS.devices.random')


class RandomDevice:
    """
    Random device implementation (/dev/random)
    
    Provides cryptographically secure random data.
    May block if entropy pool is depleted (simulated).
    """
    
    def __init__(self, name: str = "random"):
        self.name = name
        self.major = 1  # Standard major number
        self.minor = 8  # Standard minor number for /dev/random
        self.mode = 0o666  # World readable
        self.device_type = 'c'  # Character device
        self.entropy_pool = 4096  # Simulated entropy pool size
        
    def open(self, flags: int = os.O_RDONLY) -> 'RandomDevice':
        """Open the random device"""
        logger.debug(f"Opening random device with flags {flags}")
        return self
        
    def close(self) -> None:
        """Close the random device"""
        logger.debug("Closing random device")
        
    def read(self, size: int = -1) -> bytes:
        """
        Read random data from device
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Random bytes
        """
        if size == -1 or size > 4096:
            size = 4096  # Limit single read size
            
        # Simulate entropy depletion
        if size > self.entropy_pool:
            available = self.entropy_pool
            self.entropy_pool = 0
            # In real implementation, would block here
            logger.warning(f"Entropy pool depleted, only {available} bytes available")
            size = available
        else:
            self.entropy_pool -= size
            
        # Slowly replenish entropy pool
        self.entropy_pool = min(4096, self.entropy_pool + 16)
        
        # Generate cryptographically secure random bytes
        return secrets.token_bytes(size)
        
    def write(self, data: bytes) -> int:
        """
        Write to random device - adds to entropy pool
        
        Args:
            data: Data to add to entropy pool
            
        Returns:
            Number of bytes written
        """
        # Add to entropy pool (simulated)
        self.entropy_pool = min(4096, self.entropy_pool + len(data))
        logger.debug(f"Added {len(data)} bytes to entropy pool")
        return len(data)
        
    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """Seek not supported on random device"""
        raise OSError("Random device does not support seeking")
        
    def tell(self) -> int:
        """Tell not supported on random device"""
        raise OSError("Random device does not support position queries")
        
    def truncate(self, size: Optional[int] = None) -> int:
        """Truncate not supported on random device"""
        raise OSError("Random device does not support truncation")
        
    def flush(self) -> None:
        """Flush random device - no-op"""
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
        """Check if device is seekable - always False"""
        return False
        
    def ioctl(self, request: int, arg: Any = 0) -> Any:
        """
        Perform ioctl operation
        
        Args:
            request: ioctl request code
            arg: ioctl argument
            
        Returns:
            Result depends on request
        """
        # RNDGETENTCNT - Get entropy count
        if request == 0x80045200:
            return self.entropy_pool
        # RNDADDENTROPY - Add entropy
        elif request == 0x40085203:
            if isinstance(arg, bytes):
                self.write(arg)
            return 0
        else:
            logger.debug(f"Unknown ioctl request {request} on random device")
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
        return f"<RandomDevice name='{self.name}' entropy={self.entropy_pool}>"


class URandomDevice:
    """
    Urandom device implementation (/dev/urandom)
    
    Provides cryptographically secure random data without blocking.
    """
    
    def __init__(self, name: str = "urandom"):
        self.name = name
        self.major = 1  # Standard major number
        self.minor = 9  # Standard minor number for /dev/urandom
        self.mode = 0o666  # World readable
        self.device_type = 'c'  # Character device
        
    def open(self, flags: int = os.O_RDONLY) -> 'URandomDevice':
        """Open the urandom device"""
        logger.debug(f"Opening urandom device with flags {flags}")
        return self
        
    def close(self) -> None:
        """Close the urandom device"""
        logger.debug("Closing urandom device")
        
    def read(self, size: int = -1) -> bytes:
        """
        Read random data from device
        
        Args:
            size: Number of bytes to read
            
        Returns:
            Random bytes
        """
        if size == -1 or size > 65536:
            size = 65536  # Limit single read size
            
        # Generate cryptographically secure random bytes
        # urandom never blocks
        return secrets.token_bytes(size)
        
    def write(self, data: bytes) -> int:
        """
        Write to urandom device - adds to entropy pool
        
        Args:
            data: Data to add to entropy pool
            
        Returns:
            Number of bytes written
        """
        # Simulated - in real implementation would add to kernel entropy
        logger.debug(f"Added {len(data)} bytes to entropy pool")
        return len(data)
        
    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        """Seek not supported on urandom device"""
        raise OSError("Urandom device does not support seeking")
        
    def tell(self) -> int:
        """Tell not supported on urandom device"""
        raise OSError("Urandom device does not support position queries")
        
    def truncate(self, size: Optional[int] = None) -> int:
        """Truncate not supported on urandom device"""
        raise OSError("Urandom device does not support truncation")
        
    def flush(self) -> None:
        """Flush urandom device - no-op"""
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
        """Check if device is seekable - always False"""
        return False
        
    def ioctl(self, request: int, arg: Any = 0) -> Any:
        """
        Perform ioctl operation
        
        Args:
            request: ioctl request code
            arg: ioctl argument
            
        Returns:
            Result depends on request
        """
        # RNDGETENTCNT - Get entropy count (always full for urandom)
        if request == 0x80045200:
            return 4096
        # RNDADDENTROPY - Add entropy
        elif request == 0x40085203:
            if isinstance(arg, bytes):
                self.write(arg)
            return 0
        else:
            logger.debug(f"Unknown ioctl request {request} on urandom device")
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
        return f"<URandomDevice name='{self.name}'>"
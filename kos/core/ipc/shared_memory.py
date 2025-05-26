"""
KOS Shared Memory IPC Implementation

Provides a shared memory mechanism for efficient data sharing between processes.
Uses memory-mapped files with proper synchronization and protection.
"""

import os
import mmap
import time
import json
import fcntl
import struct
import threading
import uuid
import logging
import errno
from typing import Dict, Any, Optional, Union, Tuple, List

# Get module logger
logger = logging.getLogger('KOS.ipc.shared_memory')

# Base directory for shared memory files
_SHM_BASE_DIR = "/tmp/kos_ipc/shared_memory"

# Shared memory registry
_shared_memory = {}

class KOSSharedMemory:
    """
    KOS Shared Memory implementation
    
    Provides a shared memory region that can be accessed by multiple processes
    with proper protection and synchronization.
    """
    
    # Shared memory header format:
    # 0-3: Magic number (KSHM)
    # 4-7: Version (1)
    # 8-11: Flags (bit 0: in use, bit 1: locked)
    # 12-15: Size
    # 16-19: User count
    # 20-23: Creator PID
    # 24-27: Last access time (seconds)
    # 28-31: Last access time (microseconds)
    # 32-35: Permissions
    # 36-39: Reserved
    # 40-127: Padding to 128 bytes
    # 128+: Data buffer
    
    HEADER_SIZE = 128
    MAGIC = b'KSHM'
    VERSION = 1
    
    def __init__(self, shm_id=None, name=None, size=4096, permissions=0o644, load_existing=False):
        """
        Initialize a KOS shared memory segment
        
        Args:
            shm_id: Unique shared memory ID (generated if None)
            name: Friendly name for the shared memory
            size: Size of the shared memory region in bytes
            permissions: Unix-style permissions for the shared memory
            load_existing: Whether to load an existing shared memory segment
        """
        self.shm_id = shm_id or str(uuid.uuid4())
        self.name = name or f"shm_{self.shm_id}"
        self.size = size
        self.permissions = permissions
        self.shm_path = os.path.join(_SHM_BASE_DIR, f"{self.shm_id}.shm")
        self.meta_path = os.path.join(_SHM_BASE_DIR, f"{self.shm_id}.meta")
        self.lock_path = os.path.join(_SHM_BASE_DIR, f"{self.shm_id}.lock")
        
        # Ensure shared memory directory exists
        os.makedirs(_SHM_BASE_DIR, exist_ok=True)
        
        self.fd = None
        self.buffer = None
        self.closed = False
        self.error = False
        
        # For synchronization
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        
        # External lock file for cross-process synchronization
        self.lock_file = None
        
        # Track user count
        self.user_count = 0
        
        if load_existing:
            self._load()
        else:
            self._create()
        
        # Register the shared memory segment
        _shared_memory[self.shm_id] = self
    
    def _create(self):
        """Create a new shared memory segment"""
        try:
            # Create the metadata file
            metadata = {
                'shm_id': self.shm_id,
                'name': self.name,
                'size': self.size,
                'permissions': self.permissions,
                'created': time.time(),
                'creator_pid': os.getpid()
            }
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            # Create the lock file
            with open(self.lock_path, 'w') as f:
                f.write('')
            
            # Create and initialize the shared memory file
            total_size = self.HEADER_SIZE + self.size
            self.fd = os.open(self.shm_path, os.O_CREAT | os.O_RDWR)
            os.ftruncate(self.fd, total_size)
            
            # Set permissions
            os.chmod(self.shm_path, self.permissions)
            
            # Memory-map the file
            self.buffer = mmap.mmap(self.fd, total_size)
            
            # Initialize the header
            self._write_header(
                magic=self.MAGIC,
                version=self.VERSION,
                flags=0,
                size=self.size,
                user_count=1,
                creator_pid=os.getpid(),
                access_time_s=int(time.time()),
                access_time_us=int((time.time() % 1) * 1000000),
                permissions=self.permissions
            )
            
            # Set user count
            self.user_count = 1
            
            logger.debug(f"Created shared memory {self.shm_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error creating shared memory {self.shm_id}: {e}")
            self.error = True
            raise
    
    def _load(self):
        """Load an existing shared memory segment"""
        try:
            # Load metadata
            with open(self.meta_path, 'r') as f:
                metadata = json.load(f)
            
            self.name = metadata['name']
            self.size = metadata['size']
            self.permissions = metadata['permissions']
            
            # Open the shared memory file
            self.fd = os.open(self.shm_path, os.O_RDWR)
            
            # Memory-map the file
            total_size = self.HEADER_SIZE + self.size
            self.buffer = mmap.mmap(self.fd, total_size)
            
            # Validate header
            header = self._read_header()
            if header['magic'] != self.MAGIC:
                raise ValueError(f"Invalid shared memory magic: {header['magic']}")
            
            if header['version'] != self.VERSION:
                raise ValueError(f"Unsupported shared memory version: {header['version']}")
            
            # Update user count
            user_count = header['user_count']
            self._update_header_field(16, user_count + 1)
            self.user_count = user_count + 1
            
            # Update access time
            now = time.time()
            self._update_header_field(24, int(now))
            self._update_header_field(28, int((now % 1) * 1000000))
            
            logger.debug(f"Loaded shared memory {self.shm_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error loading shared memory {self.shm_id}: {e}")
            self.error = True
            raise
    
    def _write_header(self, magic, version, flags, size, user_count, creator_pid,
                     access_time_s, access_time_us, permissions):
        """Write shared memory header values"""
        with self.lock:
            self.buffer.seek(0)
            self.buffer.write(magic)  # 0-3: Magic
            self.buffer.write(struct.pack('<I', version))  # 4-7: Version
            self.buffer.write(struct.pack('<I', flags))  # 8-11: Flags
            self.buffer.write(struct.pack('<I', size))  # 12-15: Size
            self.buffer.write(struct.pack('<I', user_count))  # 16-19: User count
            self.buffer.write(struct.pack('<I', creator_pid))  # 20-23: Creator PID
            self.buffer.write(struct.pack('<I', access_time_s))  # 24-27: Access time (s)
            self.buffer.write(struct.pack('<I', access_time_us))  # 28-31: Access time (μs)
            self.buffer.write(struct.pack('<I', permissions))  # 32-35: Permissions
            self.buffer.write(struct.pack('<I', 0))  # 36-39: Reserved
            # Padding up to HEADER_SIZE
            self.buffer.write(b'\0' * (self.HEADER_SIZE - 40))
    
    def _read_header(self):
        """Read shared memory header values"""
        with self.lock:
            self.buffer.seek(0)
            return {
                'magic': self.buffer.read(4),
                'version': struct.unpack('<I', self.buffer.read(4))[0],
                'flags': struct.unpack('<I', self.buffer.read(4))[0],
                'size': struct.unpack('<I', self.buffer.read(4))[0],
                'user_count': struct.unpack('<I', self.buffer.read(4))[0],
                'creator_pid': struct.unpack('<I', self.buffer.read(4))[0],
                'access_time_s': struct.unpack('<I', self.buffer.read(4))[0],
                'access_time_us': struct.unpack('<I', self.buffer.read(4))[0],
                'permissions': struct.unpack('<I', self.buffer.read(4))[0],
                'reserved': struct.unpack('<I', self.buffer.read(4))[0]
            }
    
    def _update_header_field(self, offset, value, format_char='I'):
        """Update a specific header field"""
        with self.lock:
            self.buffer.seek(offset)
            self.buffer.write(struct.pack(f'<{format_char}', value))
    
    def _read_header_field(self, offset, format_char='I'):
        """Read a specific header field"""
        with self.lock:
            self.buffer.seek(offset)
            return struct.unpack(f'<{format_char}', self.buffer.read(struct.calcsize(f'<{format_char}')))[0]
    
    def _acquire_lock(self, blocking=True):
        """
        Acquire external lock for cross-process synchronization
        
        Args:
            blocking: Whether to wait if the lock is not available
        
        Returns:
            Success status
        """
        try:
            if not self.lock_file:
                self.lock_file = open(self.lock_path, 'r+')
            
            # Use fcntl to get an advisory lock
            op = fcntl.LOCK_EX
            if not blocking:
                op |= fcntl.LOCK_NB
            
            try:
                fcntl.flock(self.lock_file.fileno(), op)
                return True
            except IOError as e:
                if e.errno == errno.EAGAIN and not blocking:
                    # Lock is held by someone else and we're non-blocking
                    return False
                raise
        except Exception as e:
            logger.error(f"Error acquiring lock for shared memory {self.shm_id}: {e}")
            return False
    
    def _release_lock(self):
        """Release external lock"""
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.error(f"Error releasing lock for shared memory {self.shm_id}: {e}")
            return False
    
    def read(self, offset=0, size=None):
        """
        Read data from the shared memory segment
        
        Args:
            offset: Offset within the data region
            size: Number of bytes to read (None for all available data)
        
        Returns:
            Data read from the shared memory
        """
        if self.closed:
            return b''
        
        # Validate offset
        if offset < 0 or offset >= self.size:
            logger.error(f"Invalid offset {offset} for shared memory {self.shm_id}")
            return b''
        
        # Calculate maximum readable size
        max_size = self.size - offset
        if size is None:
            size = max_size
        else:
            size = min(size, max_size)
        
        if size <= 0:
            return b''
        
        with self.lock:
            try:
                # Get external lock
                if not self._acquire_lock():
                    return b''
                
                # Update access time
                now = time.time()
                self._update_header_field(24, int(now))
                self._update_header_field(28, int((now % 1) * 1000000))
                
                # Read data
                self.buffer.seek(self.HEADER_SIZE + offset)
                data = self.buffer.read(size)
                
                # Release external lock
                self._release_lock()
                
                return data
            
            except Exception as e:
                logger.error(f"Error reading from shared memory {self.shm_id}: {e}")
                if self.lock_file:
                    try:
                        self._release_lock()
                    except:
                        pass
                return b''
    
    def write(self, data, offset=0):
        """
        Write data to the shared memory segment
        
        Args:
            data: Data to write
            offset: Offset within the data region
        
        Returns:
            Number of bytes written
        """
        if self.closed:
            return 0
        
        if not data:
            return 0
        
        # Validate offset
        if offset < 0 or offset >= self.size:
            logger.error(f"Invalid offset {offset} for shared memory {self.shm_id}")
            return 0
        
        # Calculate maximum writable size
        max_size = self.size - offset
        write_size = min(len(data), max_size)
        
        if write_size <= 0:
            return 0
        
        with self.lock:
            try:
                # Get external lock
                if not self._acquire_lock():
                    return 0
                
                # Update access time
                now = time.time()
                self._update_header_field(24, int(now))
                self._update_header_field(28, int((now % 1) * 1000000))
                
                # Set in-use flag
                flags = self._read_header_field(8)
                self._update_header_field(8, flags | 1)
                
                # Write data
                self.buffer.seek(self.HEADER_SIZE + offset)
                self.buffer.write(data[:write_size])
                
                # Clear in-use flag
                flags = self._read_header_field(8)
                self._update_header_field(8, flags & ~1)
                
                # Release external lock
                self._release_lock()
                
                # Notify waiters
                self.condition.notify_all()
                
                return write_size
            
            except Exception as e:
                logger.error(f"Error writing to shared memory {self.shm_id}: {e}")
                if self.lock_file:
                    try:
                        self._release_lock()
                    except:
                        pass
                return 0
    
    def lock(self, blocking=True):
        """
        Lock the shared memory for exclusive access
        
        Args:
            blocking: Whether to wait if the lock is not available
            
        Returns:
            Success status
        """
        if self.closed:
            return False
        
        with self.lock:
            try:
                # Get external lock
                if not self._acquire_lock(blocking):
                    return False
                
                # Set locked flag
                flags = self._read_header_field(8)
                self._update_header_field(8, flags | 2)
                
                return True
            
            except Exception as e:
                logger.error(f"Error locking shared memory {self.shm_id}: {e}")
                if self.lock_file:
                    try:
                        self._release_lock()
                    except:
                        pass
                return False
    
    def unlock(self):
        """
        Unlock the shared memory
        
        Returns:
            Success status
        """
        if self.closed:
            return False
        
        with self.lock:
            try:
                # Clear locked flag
                flags = self._read_header_field(8)
                self._update_header_field(8, flags & ~2)
                
                # Release external lock
                if not self._release_lock():
                    return False
                
                # Notify waiters
                self.condition.notify_all()
                
                return True
            
            except Exception as e:
                logger.error(f"Error unlocking shared memory {self.shm_id}: {e}")
                return False
    
    def close(self):
        """Close the shared memory segment"""
        if self.closed:
            return
        
        try:
            with self.lock:
                # Update user count
                if self.buffer:
                    user_count = self._read_header_field(16)
                    if user_count > 0:
                        self._update_header_field(16, user_count - 1)
                
                # Signal any waiting threads
                self.condition.notify_all()
                
                # Close resources
                if self.buffer:
                    self.buffer.close()
                    self.buffer = None
                
                if self.fd:
                    os.close(self.fd)
                    self.fd = None
                
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                
                self.closed = True
                
                logger.debug(f"Closed shared memory {self.shm_id} ({self.name})")
        
        except Exception as e:
            logger.error(f"Error closing shared memory {self.shm_id}: {e}")
            self.error = True
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        try:
            self.close()
        except:
            pass


def create_shared_memory(name: str = None, size: int = 4096, permissions: int = 0o644) -> str:
    """
    Create a new shared memory segment
    
    Args:
        name: Optional name for the shared memory
        size: Size of the shared memory in bytes
        permissions: Unix-style permissions for the shared memory
    
    Returns:
        Shared memory ID
    """
    try:
        # Create the shared memory
        shm = KOSSharedMemory(name=name, size=size, permissions=permissions)
        
        logger.info(f"Created shared memory {shm.shm_id} ({shm.name})")
        
        return shm.shm_id
    
    except Exception as e:
        logger.error(f"Error creating shared memory: {e}")
        raise


def delete_shared_memory(shm_id: str) -> bool:
    """
    Delete a shared memory segment
    
    Args:
        shm_id: Shared memory ID
    
    Returns:
        Success status
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return False
        
        # Close the shared memory
        shm = _shared_memory[shm_id]
        shm.close()
        
        # Remove from registry
        del _shared_memory[shm_id]
        
        # Delete shared memory files if no users
        shm_path = os.path.join(_SHM_BASE_DIR, f"{shm_id}.shm")
        meta_path = os.path.join(_SHM_BASE_DIR, f"{shm_id}.meta")
        lock_path = os.path.join(_SHM_BASE_DIR, f"{shm_id}.lock")
        
        try:
            os.unlink(shm_path)
            os.unlink(meta_path)
            os.unlink(lock_path)
        except:
            # Files may still be in use by other processes
            pass
        
        logger.info(f"Deleted shared memory {shm_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting shared memory {shm_id}: {e}")
        return False


def attach_shared_memory(shm_id: str) -> bool:
    """
    Attach to an existing shared memory segment
    
    Args:
        shm_id: Shared memory ID
    
    Returns:
        Success status
    """
    try:
        # Check if already attached
        if shm_id in _shared_memory:
            return True
        
        # Attach to the shared memory
        shm = KOSSharedMemory(shm_id=shm_id, load_existing=True)
        
        logger.info(f"Attached to shared memory {shm_id} ({shm.name})")
        
        return True
    
    except Exception as e:
        logger.error(f"Error attaching to shared memory {shm_id}: {e}")
        return False


def detach_shared_memory(shm_id: str) -> bool:
    """
    Detach from a shared memory segment
    
    Args:
        shm_id: Shared memory ID
    
    Returns:
        Success status
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return False
        
        # Close the shared memory
        shm = _shared_memory[shm_id]
        shm.close()
        
        # Remove from registry
        del _shared_memory[shm_id]
        
        logger.info(f"Detached from shared memory {shm_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error detaching from shared memory {shm_id}: {e}")
        return False


def read_shared_memory(shm_id: str, offset: int = 0, size: int = None) -> bytes:
    """
    Read data from a shared memory segment
    
    Args:
        shm_id: Shared memory ID
        offset: Offset within the shared memory
        size: Number of bytes to read (None for all available)
    
    Returns:
        Data read from the shared memory
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return b''
        
        # Read from the shared memory
        shm = _shared_memory[shm_id]
        data = shm.read(offset, size)
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading from shared memory {shm_id}: {e}")
        return b''


def write_shared_memory(shm_id: str, data: bytes, offset: int = 0) -> int:
    """
    Write data to a shared memory segment
    
    Args:
        shm_id: Shared memory ID
        data: Data to write
        offset: Offset within the shared memory
    
    Returns:
        Number of bytes written
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return 0
        
        # Write to the shared memory
        shm = _shared_memory[shm_id]
        bytes_written = shm.write(data, offset)
        
        return bytes_written
    
    except Exception as e:
        logger.error(f"Error writing to shared memory {shm_id}: {e}")
        return 0


def lock_shared_memory(shm_id: str, blocking: bool = True) -> bool:
    """
    Lock a shared memory segment for exclusive access
    
    Args:
        shm_id: Shared memory ID
        blocking: Whether to wait if the lock is not available
    
    Returns:
        Success status
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return False
        
        # Lock the shared memory
        shm = _shared_memory[shm_id]
        result = shm.lock(blocking)
        
        return result
    
    except Exception as e:
        logger.error(f"Error locking shared memory {shm_id}: {e}")
        return False


def unlock_shared_memory(shm_id: str) -> bool:
    """
    Unlock a shared memory segment
    
    Args:
        shm_id: Shared memory ID
    
    Returns:
        Success status
    """
    try:
        # Check if the shared memory exists
        if shm_id not in _shared_memory:
            logger.warning(f"Shared memory {shm_id} not found")
            return False
        
        # Unlock the shared memory
        shm = _shared_memory[shm_id]
        result = shm.unlock()
        
        return result
    
    except Exception as e:
        logger.error(f"Error unlocking shared memory {shm_id}: {e}")
        return False

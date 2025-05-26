"""
KOS Pipe IPC Implementation

Provides a pipe mechanism for unidirectional data flow between processes.
Uses memory-mapped files for efficient data transfer with proper synchronization.
"""

import os
import mmap
import time
import json
import threading
import uuid
import struct
import logging
import fcntl
import errno
from typing import Dict, Any, Optional, Union, Tuple, List

# Get module logger
logger = logging.getLogger('KOS.ipc.pipe')

# Base directory for pipe files
_PIPE_BASE_DIR = "/tmp/kos_ipc/pipe"

# Pipe registry
_pipes = {}

class KOSPipe:
    """
    KOS Pipe implementation using memory-mapped files
    
    This provides real IPC through shared memory regions with proper locking
    and synchronization mechanisms.
    """
    
    # Pipe header format:
    # 0-3: Magic number (KPIP)
    # 4-7: Version (1)
    # 8-11: Flags (bit 0: closed, bit 1: error)
    # 12-15: Buffer size
    # 16-19: Read position
    # 20-23: Write position
    # 24-27: Reader count
    # 28-31: Writer count
    # 32-35: Last error code
    # 36-39: Reserved
    # 40-43: Reserved
    # 44-47: Reserved
    # 48-127: Padding to 128 bytes
    # 128+: Data buffer
    
    HEADER_SIZE = 128
    MAGIC = b'KPIP'
    VERSION = 1
    
    def __init__(self, pipe_id=None, name=None, buffer_size=4096, load_existing=False):
        """
        Initialize a KOS pipe
        
        Args:
            pipe_id: Unique pipe ID (generated if None)
            name: Friendly name for the pipe
            buffer_size: Size of the pipe buffer in bytes
            load_existing: Whether to load an existing pipe
        """
        self.pipe_id = pipe_id or str(uuid.uuid4())
        self.name = name or f"pipe_{self.pipe_id}"
        self.buffer_size = buffer_size
        self.pipe_path = os.path.join(_PIPE_BASE_DIR, f"{self.pipe_id}.pipe")
        self.meta_path = os.path.join(_PIPE_BASE_DIR, f"{self.pipe_id}.meta")
        self.lock_path = os.path.join(_PIPE_BASE_DIR, f"{self.pipe_id}.lock")
        
        # Ensure pipe directory exists
        os.makedirs(_PIPE_BASE_DIR, exist_ok=True)
        
        self.fd = None
        self.buffer = None
        self.closed = False
        self.error = False
        
        # For reader/writer tracking
        self.readers = set()
        self.writers = set()
        
        # For synchronization
        self.lock = threading.RLock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        
        # External lock file for cross-process synchronization
        self.lock_file = None
        
        if load_existing:
            self._load()
        else:
            self._create()
        
        # Register the pipe
        _pipes[self.pipe_id] = self
    
    def _create(self):
        """Create a new pipe"""
        try:
            # Create the metadata file
            metadata = {
                'pipe_id': self.pipe_id,
                'name': self.name,
                'buffer_size': self.buffer_size,
                'created': time.time(),
                'creator_pid': os.getpid()
            }
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            # Create the lock file
            with open(self.lock_path, 'w') as f:
                f.write('')
            
            # Create and initialize the pipe file
            total_size = self.HEADER_SIZE + self.buffer_size
            self.fd = os.open(self.pipe_path, os.O_CREAT | os.O_RDWR)
            os.ftruncate(self.fd, total_size)
            
            # Memory-map the file
            self.buffer = mmap.mmap(self.fd, total_size)
            
            # Initialize the header
            self._write_header(
                magic=self.MAGIC,
                version=self.VERSION,
                flags=0,
                buffer_size=self.buffer_size,
                read_pos=0,
                write_pos=0,
                reader_count=0,
                writer_count=0,
                error_code=0
            )
            
            logger.debug(f"Created pipe {self.pipe_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error creating pipe {self.pipe_id}: {e}")
            self.error = True
            raise
    
    def _load(self):
        """Load an existing pipe"""
        try:
            # Load metadata
            with open(self.meta_path, 'r') as f:
                metadata = json.load(f)
            
            self.name = metadata['name']
            self.buffer_size = metadata['buffer_size']
            
            # Open the pipe file
            self.fd = os.open(self.pipe_path, os.O_RDWR)
            
            # Memory-map the file
            total_size = self.HEADER_SIZE + self.buffer_size
            self.buffer = mmap.mmap(self.fd, total_size)
            
            # Validate header
            header = self._read_header()
            if header['magic'] != self.MAGIC:
                raise ValueError(f"Invalid pipe magic: {header['magic']}")
            
            if header['version'] != self.VERSION:
                raise ValueError(f"Unsupported pipe version: {header['version']}")
            
            # Set state from header
            self.closed = bool(header['flags'] & 1)
            self.error = bool(header['flags'] & 2)
            
            logger.debug(f"Loaded pipe {self.pipe_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error loading pipe {self.pipe_id}: {e}")
            self.error = True
            raise
    
    def _write_header(self, magic, version, flags, buffer_size, read_pos, write_pos,
                     reader_count, writer_count, error_code):
        """Write pipe header values"""
        with self.lock:
            self.buffer.seek(0)
            self.buffer.write(magic)  # 0-3: Magic
            self.buffer.write(struct.pack('<I', version))  # 4-7: Version
            self.buffer.write(struct.pack('<I', flags))  # 8-11: Flags
            self.buffer.write(struct.pack('<I', buffer_size))  # 12-15: Buffer size
            self.buffer.write(struct.pack('<I', read_pos))  # 16-19: Read position
            self.buffer.write(struct.pack('<I', write_pos))  # 20-23: Write position
            self.buffer.write(struct.pack('<I', reader_count))  # 24-27: Reader count
            self.buffer.write(struct.pack('<I', writer_count))  # 28-31: Writer count
            self.buffer.write(struct.pack('<I', error_code))  # 32-35: Last error code
            # Padding up to HEADER_SIZE
            self.buffer.write(b'\0' * (self.HEADER_SIZE - 36))
    
    def _read_header(self):
        """Read pipe header values"""
        with self.lock:
            self.buffer.seek(0)
            return {
                'magic': self.buffer.read(4),
                'version': struct.unpack('<I', self.buffer.read(4))[0],
                'flags': struct.unpack('<I', self.buffer.read(4))[0],
                'buffer_size': struct.unpack('<I', self.buffer.read(4))[0],
                'read_pos': struct.unpack('<I', self.buffer.read(4))[0],
                'write_pos': struct.unpack('<I', self.buffer.read(4))[0],
                'reader_count': struct.unpack('<I', self.buffer.read(4))[0],
                'writer_count': struct.unpack('<I', self.buffer.read(4))[0],
                'error_code': struct.unpack('<I', self.buffer.read(4))[0]
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
    
    def _acquire_lock(self):
        """Acquire external lock for cross-process synchronization"""
        try:
            if not self.lock_file:
                self.lock_file = open(self.lock_path, 'r+')
            
            # Use fcntl to get an advisory lock
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
            return True
        except Exception as e:
            logger.error(f"Error acquiring lock for pipe {self.pipe_id}: {e}")
            return False
    
    def _release_lock(self):
        """Release external lock"""
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.error(f"Error releasing lock for pipe {self.pipe_id}: {e}")
            return False
    
    def _get_available_data(self):
        """Get the amount of data available to read"""
        read_pos = self._read_header_field(16)
        write_pos = self._read_header_field(20)
        
        if write_pos >= read_pos:
            return write_pos - read_pos
        else:
            return self.buffer_size - read_pos + write_pos
    
    def _get_available_space(self):
        """Get the amount of space available to write"""
        read_pos = self._read_header_field(16)
        write_pos = self._read_header_field(20)
        
        # Keep one byte free to distinguish empty from full
        if read_pos > write_pos:
            return read_pos - write_pos - 1
        elif read_pos == 0:
            return self.buffer_size - write_pos - 1
        else:
            return self.buffer_size - write_pos + read_pos - 1
    
    def read(self, size, nonblocking=False):
        """
        Read data from the pipe
        
        Args:
            size: Maximum number of bytes to read
            nonblocking: Whether to return immediately if no data is available
        
        Returns:
            Data read from the pipe
        """
        if self.closed:
            return b''
        
        if size <= 0:
            return b''
        
        with self.lock:
            # Get current positions
            read_pos = self._read_header_field(16)
            write_pos = self._read_header_field(20)
            flags = self._read_header_field(8)
            
            # Check if pipe is closed and empty
            if (flags & 1) and read_pos == write_pos:
                return b''
            
            # Wait for data if empty and blocking
            while read_pos == write_pos and not (flags & 1):
                if nonblocking:
                    return b''
                
                if not self.not_empty.wait(1.0):  # Wait with timeout
                    # Recheck conditions after timeout
                    read_pos = self._read_header_field(16)
                    write_pos = self._read_header_field(20)
                    flags = self._read_header_field(8)
                    
                    if read_pos == write_pos and not (flags & 1):
                        # Still no data, return empty for non-blocking
                        if nonblocking:
                            return b''
                        # Otherwise continue waiting
                        continue
                    else:
                        # Data available or pipe closed, break out
                        break
            
            # Calculate available data
            if write_pos >= read_pos:
                available = write_pos - read_pos
            else:
                available = self.buffer_size - read_pos + write_pos
            
            bytes_to_read = min(size, available)
            
            if bytes_to_read == 0:
                return b''
            
            # Read data
            result = bytearray(bytes_to_read)
            for i in range(bytes_to_read):
                buffer_pos = (read_pos + i) % self.buffer_size
                self.buffer.seek(self.HEADER_SIZE + buffer_pos)
                result[i] = self.buffer[self.buffer.tell()]
            
            # Update read position
            new_read_pos = (read_pos + bytes_to_read) % self.buffer_size
            self._update_header_field(16, new_read_pos)
            
            # Signal not full
            self.not_full.notify_all()
            
            return bytes(result)
    
    def write(self, data, nonblocking=False):
        """
        Write data to the pipe
        
        Args:
            data: Data to write
            nonblocking: Whether to return immediately if the pipe is full
        
        Returns:
            Number of bytes written
        """
        if self.closed:
            return 0
        
        if not data:
            return 0
        
        with self.lock:
            # Get current positions
            read_pos = self._read_header_field(16)
            write_pos = self._read_header_field(20)
            
            # Calculate available space
            if read_pos > write_pos:
                available = read_pos - write_pos - 1
            elif read_pos == 0:
                available = self.buffer_size - write_pos - 1
            else:
                available = self.buffer_size - write_pos + read_pos - 1
            
            # Wait for space if full and blocking
            while available == 0:
                if nonblocking:
                    return 0
                
                if not self.not_full.wait(1.0):  # Wait with timeout
                    # Recheck conditions after timeout
                    read_pos = self._read_header_field(16)
                    write_pos = self._read_header_field(20)
                    
                    # Recalculate available space
                    if read_pos > write_pos:
                        available = read_pos - write_pos - 1
                    elif read_pos == 0:
                        available = self.buffer_size - write_pos - 1
                    else:
                        available = self.buffer_size - write_pos + read_pos - 1
                    
                    if available == 0:
                        # Still no space, return 0 for non-blocking
                        if nonblocking:
                            return 0
                        # Otherwise continue waiting
                        continue
                    else:
                        # Space available, break out
                        break
            
            bytes_to_write = min(len(data), available)
            
            # Write data
            for i in range(bytes_to_write):
                buffer_pos = (write_pos + i) % self.buffer_size
                self.buffer.seek(self.HEADER_SIZE + buffer_pos)
                self.buffer[self.buffer.tell()] = data[i]
            
            # Update write position
            new_write_pos = (write_pos + bytes_to_write) % self.buffer_size
            self._update_header_field(20, new_write_pos)
            
            # Signal not empty
            self.not_empty.notify_all()
            
            return bytes_to_write
    
    def close(self):
        """Close the pipe"""
        if self.closed:
            return
        
        try:
            with self.lock:
                # Set closed flag
                flags = self._read_header_field(8)
                self._update_header_field(8, flags | 1)
                
                # Signal any waiting readers/writers
                self.not_empty.notify_all()
                self.not_full.notify_all()
                
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
                
                logger.debug(f"Closed pipe {self.pipe_id} ({self.name})")
        
        except Exception as e:
            logger.error(f"Error closing pipe {self.pipe_id}: {e}")
            self.error = True
            raise
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        try:
            self.close()
        except:
            pass


def create_pipe(name: str = None, buffer_size: int = 4096) -> str:
    """
    Create a new pipe for inter-process communication
    
    Args:
        name: Optional pipe name
        buffer_size: Pipe buffer size in bytes
    
    Returns:
        Pipe ID
    """
    try:
        # Create the pipe
        pipe = KOSPipe(name=name, buffer_size=buffer_size)
        
        logger.info(f"Created pipe {pipe.pipe_id} ({pipe.name})")
        
        return pipe.pipe_id
    
    except Exception as e:
        logger.error(f"Error creating pipe: {e}")
        raise


def open_pipe(pipe_id: str) -> bool:
    """
    Open an existing pipe
    
    Args:
        pipe_id: Pipe ID
    
    Returns:
        Success status
    """
    try:
        # Check if already open
        if pipe_id in _pipes:
            return True
        
        # Open the pipe
        pipe = KOSPipe(pipe_id=pipe_id, load_existing=True)
        
        logger.info(f"Opened pipe {pipe_id} ({pipe.name})")
        
        return True
    
    except Exception as e:
        logger.error(f"Error opening pipe {pipe_id}: {e}")
        return False


def close_pipe(pipe_id: str) -> bool:
    """
    Close a pipe
    
    Args:
        pipe_id: Pipe ID
    
    Returns:
        Success status
    """
    try:
        # Check if the pipe exists
        if pipe_id not in _pipes:
            logger.warning(f"Pipe {pipe_id} not found")
            return False
        
        # Close the pipe
        pipe = _pipes[pipe_id]
        pipe.close()
        
        # Remove from registry
        del _pipes[pipe_id]
        
        logger.info(f"Closed pipe {pipe_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error closing pipe {pipe_id}: {e}")
        return False


def write_pipe(pipe_id: str, data: bytes, nonblocking: bool = False) -> int:
    """
    Write data to a pipe
    
    Args:
        pipe_id: Pipe ID
        data: Data to write
        nonblocking: Whether to return immediately if the pipe is full
    
    Returns:
        Number of bytes written
    """
    try:
        # Check if the pipe exists
        if pipe_id not in _pipes:
            logger.warning(f"Pipe {pipe_id} not found")
            return 0
        
        # Write to the pipe
        pipe = _pipes[pipe_id]
        bytes_written = pipe.write(data, nonblocking)
        
        return bytes_written
    
    except Exception as e:
        logger.error(f"Error writing to pipe {pipe_id}: {e}")
        return 0


def read_pipe(pipe_id: str, size: int, nonblocking: bool = False) -> bytes:
    """
    Read data from a pipe
    
    Args:
        pipe_id: Pipe ID
        size: Maximum number of bytes to read
        nonblocking: Whether to return immediately if no data is available
    
    Returns:
        Data read
    """
    try:
        # Check if the pipe exists
        if pipe_id not in _pipes:
            logger.warning(f"Pipe {pipe_id} not found")
            return b''
        
        # Read from the pipe
        pipe = _pipes[pipe_id]
        data = pipe.read(size, nonblocking)
        
        return data
    
    except Exception as e:
        logger.error(f"Error reading from pipe {pipe_id}: {e}")
        return b''

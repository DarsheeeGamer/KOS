# Filesystem API

Comprehensive API documentation for KOS filesystem subsystem including VFS layer, file operations, and mounting capabilities.

## Overview

The KOS filesystem provides a Virtual File System (VFS) layer that supports multiple filesystem types, file operations, permissions management, and advanced features like memory-mapped files and file locking.

## Core Classes

### VirtualFileSystem

Main VFS interface providing unified access to all mounted filesystems.

```python
from kos.filesystem.vfs import VirtualFileSystem

class VirtualFileSystem:
    """
    Virtual File System providing unified interface to multiple filesystems.
    
    The VFS layer abstracts different filesystem implementations and provides
    a common interface for file operations, mounting, and path resolution.
    """
    
    def __init__(self):
        """Initialize VFS with empty mount table."""
        
    def mount(self, filesystem: 'FileSystem', mount_point: str, 
              options: Dict[str, Any] = None) -> bool:
        """
        Mount filesystem at specified mount point.
        
        Args:
            filesystem: Filesystem instance to mount
            mount_point: Path where filesystem should be mounted
            options: Mount options (ro, rw, noexec, etc.)
            
        Returns:
            bool: True if mount successful
            
        Raises:
            MountError: If mount operation fails
            
        Example:
            >>> vfs = VirtualFileSystem()
            >>> ramfs = RAMFileSystem()
            >>> vfs.mount(ramfs, '/tmp', {'rw': True})
            True
        """
        
    def unmount(self, mount_point: str, force: bool = False) -> bool:
        """
        Unmount filesystem from mount point.
        
        Args:
            mount_point: Path to unmount
            force: Force unmount even if busy
            
        Returns:
            bool: True if unmount successful
        """
        
    def open(self, path: str, mode: str = 'r', create_dirs: bool = False) -> int:
        """
        Open file and return file descriptor.
        
        Args:
            path: File path to open
            mode: Open mode ('r', 'w', 'a', 'r+', 'w+', 'a+')
            create_dirs: Create parent directories if needed
            
        Returns:
            int: File descriptor (> 0) or -1 on error
            
        Example:
            >>> fd = vfs.open('/tmp/test.txt', 'w')
            >>> if fd > 0:
            ...     vfs.write(fd, b'Hello World')
            ...     vfs.close(fd)
        """
        
    def close(self, fd: int) -> bool:
        """
        Close file descriptor.
        
        Args:
            fd: File descriptor to close
            
        Returns:
            bool: True if close successful
        """
        
    def read(self, fd: int, size: int = -1) -> bytes:
        """
        Read data from file descriptor.
        
        Args:
            fd: File descriptor to read from
            size: Number of bytes to read (-1 for all)
            
        Returns:
            bytes: Data read from file
        """
        
    def write(self, fd: int, data: bytes) -> int:
        """
        Write data to file descriptor.
        
        Args:
            fd: File descriptor to write to
            data: Data to write
            
        Returns:
            int: Number of bytes written
        """
        
    def seek(self, fd: int, offset: int, whence: int = 0) -> int:
        """
        Seek to position in file.
        
        Args:
            fd: File descriptor
            offset: Offset to seek to
            whence: Seek mode (0=SEEK_SET, 1=SEEK_CUR, 2=SEEK_END)
            
        Returns:
            int: New file position
        """
        
    def stat(self, path: str) -> Dict[str, Any]:
        """
        Get file/directory statistics.
        
        Args:
            path: Path to stat
            
        Returns:
            dict: File statistics
            {
                'size': int,           # File size in bytes
                'mode': int,           # File mode/permissions
                'uid': int,            # Owner user ID
                'gid': int,            # Owner group ID
                'atime': float,        # Access time
                'mtime': float,        # Modification time
                'ctime': float,        # Creation time
                'nlink': int,          # Number of hard links
                'dev': int,            # Device ID
                'ino': int             # Inode number
            }
        """
        
    def mkdir(self, path: str, mode: int = 0o755, parents: bool = False) -> bool:
        """
        Create directory.
        
        Args:
            path: Directory path to create
            mode: Directory permissions
            parents: Create parent directories if needed
            
        Returns:
            bool: True if directory created
        """
        
    def rmdir(self, path: str) -> bool:
        """
        Remove empty directory.
        
        Args:
            path: Directory path to remove
            
        Returns:
            bool: True if directory removed
        """
        
    def unlink(self, path: str) -> bool:
        """
        Remove file.
        
        Args:
            path: File path to remove
            
        Returns:
            bool: True if file removed
        """
        
    def rename(self, old_path: str, new_path: str) -> bool:
        """
        Rename/move file or directory.
        
        Args:
            old_path: Current path
            new_path: New path
            
        Returns:
            bool: True if rename successful
        """
        
    def chmod(self, path: str, mode: int) -> bool:
        """
        Change file permissions.
        
        Args:
            path: File path
            mode: New permissions (octal)
            
        Returns:
            bool: True if permissions changed
        """
        
    def chown(self, path: str, uid: int, gid: int) -> bool:
        """
        Change file ownership.
        
        Args:
            path: File path
            uid: New owner user ID
            gid: New owner group ID
            
        Returns:
            bool: True if ownership changed
        """
        
    def listdir(self, path: str) -> List[str]:
        """
        List directory contents.
        
        Args:
            path: Directory path to list
            
        Returns:
            List[str]: List of filenames in directory
        """
        
    def resolve_path(self, path: str, safe: bool = True) -> str:
        """
        Resolve path to absolute form, handling symlinks and '..' components.
        
        Args:
            path: Path to resolve
            safe: Enable path traversal protection
            
        Returns:
            str: Resolved absolute path
            
        Raises:
            ValueError: If path contains dangerous traversal patterns (when safe=True)
        """
        
    def get_mount_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all mounted filesystems.
        
        Returns:
            List[dict]: Mount information
            [
                {
                    'mount_point': str,
                    'filesystem_type': str,
                    'options': dict,
                    'device': str
                }
            ]
        """
```

### FileSystem

Base filesystem implementation that can be extended for specific filesystem types.

```python
from kos.filesystem.base import FileSystem

class FileSystem:
    """
    Base filesystem implementation.
    
    Provides common filesystem operations that can be overridden
    by specific filesystem implementations.
    """
    
    def __init__(self, device: str = None):
        """
        Initialize filesystem.
        
        Args:
            device: Block device or backing store
        """
        
    def create_file(self, path: str, content: bytes = b'') -> bool:
        """
        Create new file with optional initial content.
        
        Args:
            path: File path to create
            content: Initial file content
            
        Returns:
            bool: True if file created successfully
        """
        
    def read_file(self, path: str) -> bytes:
        """
        Read entire file content.
        
        Args:
            path: File path to read
            
        Returns:
            bytes: File content
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If read permission denied
        """
        
    def write_file(self, path: str, content: bytes, append: bool = False) -> bool:
        """
        Write content to file.
        
        Args:
            path: File path to write
            content: Content to write
            append: Append to existing content if True
            
        Returns:
            bool: True if write successful
        """
        
    def delete_file(self, path: str) -> bool:
        """
        Delete file.
        
        Args:
            path: File path to delete
            
        Returns:
            bool: True if deletion successful
        """
        
    def create_directory(self, path: str) -> bool:
        """
        Create directory.
        
        Args:
            path: Directory path to create
            
        Returns:
            bool: True if directory created
        """
        
    def remove_directory(self, path: str) -> bool:
        """
        Remove directory (must be empty).
        
        Args:
            path: Directory path to remove
            
        Returns:
            bool: True if directory removed
        """
        
    def list_directory(self, path: str) -> List[str]:
        """
        List directory contents.
        
        Args:
            path: Directory path to list
            
        Returns:
            List[str]: List of entry names
        """
        
    def get_metadata(self, path: str) -> Dict[str, Any]:
        """
        Get file/directory metadata.
        
        Args:
            path: Path to examine
            
        Returns:
            dict: Metadata including size, timestamps, permissions
        """
        
    def set_permissions(self, path: str, mode: int) -> bool:
        """
        Set file/directory permissions.
        
        Args:
            path: Path to modify
            mode: New permission mode
            
        Returns:
            bool: True if permissions set
        """
        
    def get_permissions(self, path: str) -> int:
        """
        Get file/directory permissions.
        
        Args:
            path: Path to examine
            
        Returns:
            int: Permission mode
        """
```

### RAMFileSystem

In-memory filesystem implementation for temporary storage.

```python
from kos.filesystem.ramfs import RAMFileSystem

class RAMFileSystem(FileSystem):
    """
    RAM-based filesystem for temporary storage.
    
    Stores all files and directories in system memory.
    Data is lost when system shuts down.
    """
    
    def __init__(self, max_size: int = None):
        """
        Initialize RAM filesystem.
        
        Args:
            max_size: Maximum filesystem size in bytes (None for unlimited)
        """
        
    def get_memory_usage(self) -> int:
        """
        Get current memory usage of filesystem.
        
        Returns:
            int: Memory usage in bytes
        """
        
    def get_capacity(self) -> int:
        """
        Get filesystem capacity.
        
        Returns:
            int: Total capacity in bytes
        """
        
    def get_free_space(self) -> int:
        """
        Get available free space.
        
        Returns:
            int: Free space in bytes
        """
        
    def compact(self) -> int:
        """
        Compact filesystem to reclaim fragmented space.
        
        Returns:
            int: Bytes reclaimed
        """
```

## Kernel VFS Interface

### Low-Level VFS Operations

```python
from kos.vfs.vfs_wrapper import (
    vfs_open, vfs_close, vfs_read, vfs_write, vfs_seek,
    vfs_stat, vfs_mkdir, vfs_unlink
)

def vfs_open(path: str, flags: str) -> int:
    """
    Open file at kernel level.
    
    Args:
        path: File path
        flags: Open flags (O_RDONLY, O_WRONLY, O_RDWR, etc.)
        
    Returns:
        int: File descriptor or negative error code
    """

def vfs_close(fd: int) -> int:
    """
    Close file descriptor at kernel level.
    
    Args:
        fd: File descriptor
        
    Returns:
        int: 0 on success, negative error code on failure
    """

def vfs_read(fd: int, size: int) -> int:
    """
    Read from file at kernel level.
    
    Args:
        fd: File descriptor
        size: Number of bytes to read
        
    Returns:
        int: Number of bytes read or negative error code
    """

def vfs_write(fd: int, data: bytes, size: int) -> int:
    """
    Write to file at kernel level.
    
    Args:
        fd: File descriptor
        data: Data to write
        size: Number of bytes to write
        
    Returns:
        int: Number of bytes written or negative error code
    """

def vfs_seek(fd: int, offset: int, whence: int) -> int:
    """
    Seek in file at kernel level.
    
    Args:
        fd: File descriptor
        offset: Seek offset
        whence: Seek origin (SEEK_SET, SEEK_CUR, SEEK_END)
        
    Returns:
        int: New file position or negative error code
    """
```

## File Locking

### Advisory File Locking

```python
from kos.filesystem.locks import FileLock, LockType

class FileLock:
    """
    Advisory file locking mechanism.
    
    Provides process coordination through file locks without
    enforcing access restrictions at the kernel level.
    """
    
    def __init__(self, fd: int):
        """
        Initialize file lock for file descriptor.
        
        Args:
            fd: File descriptor to lock
        """
        
    def acquire(self, lock_type: LockType, start: int = 0, 
                length: int = 0, blocking: bool = True) -> bool:
        """
        Acquire file lock.
        
        Args:
            lock_type: Type of lock (SHARED or EXCLUSIVE)
            start: Start offset for lock
            length: Length of lock (0 for entire file)
            blocking: Block until lock acquired if True
            
        Returns:
            bool: True if lock acquired
        """
        
    def release(self) -> bool:
        """
        Release file lock.
        
        Returns:
            bool: True if lock released
        """
        
    def is_locked(self) -> bool:
        """
        Check if file is currently locked.
        
        Returns:
            bool: True if file is locked
        """

class LockType(Enum):
    """File lock types."""
    SHARED = 'shared'        # Multiple readers allowed
    EXCLUSIVE = 'exclusive'  # Single writer only
```

## Memory Mapping

### Memory-Mapped Files

```python
from kos.filesystem.mmap import MemoryMappedFile

class MemoryMappedFile:
    """
    Memory-mapped file interface.
    
    Allows direct memory access to file contents for high-performance
    file I/O operations.
    """
    
    def __init__(self, fd: int, length: int = None, 
                 offset: int = 0, protection: int = None):
        """
        Create memory mapping for file.
        
        Args:
            fd: File descriptor
            length: Length to map (None for entire file)
            offset: File offset to start mapping
            protection: Memory protection flags
        """
        
    def map(self) -> int:
        """
        Create memory mapping.
        
        Returns:
            int: Memory address of mapping (0 if failed)
        """
        
    def unmap(self) -> bool:
        """
        Remove memory mapping.
        
        Returns:
            bool: True if unmapping successful
        """
        
    def sync(self, async_sync: bool = False) -> bool:
        """
        Synchronize memory mapping with file.
        
        Args:
            async_sync: Perform asynchronous sync if True
            
        Returns:
            bool: True if sync initiated successfully
        """
        
    def get_address(self) -> int:
        """
        Get memory address of mapping.
        
        Returns:
            int: Memory address
        """
        
    def get_size(self) -> int:
        """
        Get size of mapping.
        
        Returns:
            int: Mapping size in bytes
        """
```

## File System Types

### Supported Filesystem Types

```python
from kos.filesystem.types import FileSystemType

class FileSystemType(Enum):
    """Supported filesystem types."""
    RAMFS = 'ramfs'        # RAM-based filesystem
    TMPFS = 'tmpfs'        # Temporary filesystem
    PROCFS = 'procfs'      # Process information filesystem
    SYSFS = 'sysfs'        # System information filesystem
    DEVFS = 'devfs'        # Device filesystem
    EXT4 = 'ext4'          # Extended filesystem v4
    BTRFS = 'btrfs'        # B-tree filesystem
    XFS = 'xfs'            # XFS filesystem
    ZFS = 'zfs'            # ZFS filesystem
    NTFS = 'ntfs'          # NTFS filesystem
    FAT32 = 'fat32'        # FAT32 filesystem
```

### Filesystem Manager

```python
from kos.core.filesystem.fs_manager import FileSystemManager

class FileSystemManager:
    """
    Manager for filesystem types and mounting.
    
    Handles registration of filesystem drivers and provides
    unified mounting interface.
    """
    
    def __init__(self):
        """Initialize filesystem manager."""
        
    def register_filesystem(self, fs_type: str, fs_class: type) -> bool:
        """
        Register filesystem driver.
        
        Args:
            fs_type: Filesystem type name
            fs_class: Filesystem implementation class
            
        Returns:
            bool: True if registration successful
        """
        
    def unregister_filesystem(self, fs_type: str) -> bool:
        """
        Unregister filesystem driver.
        
        Args:
            fs_type: Filesystem type name
            
        Returns:
            bool: True if unregistration successful
        """
        
    def create_filesystem(self, fs_type: str, device: str = None, 
                         **kwargs) -> FileSystem:
        """
        Create filesystem instance.
        
        Args:
            fs_type: Type of filesystem to create
            device: Block device or backing store
            **kwargs: Filesystem-specific parameters
            
        Returns:
            FileSystem: Filesystem instance
        """
        
    def mount(self, fs_type: str, device: str, mount_point: str,
              options: Dict[str, Any] = None) -> bool:
        """
        Mount filesystem.
        
        Args:
            fs_type: Filesystem type
            device: Device to mount
            mount_point: Where to mount
            options: Mount options
            
        Returns:
            bool: True if mount successful
        """
        
    def unmount(self, mount_point: str, force: bool = False) -> bool:
        """
        Unmount filesystem.
        
        Args:
            mount_point: Mount point to unmount
            force: Force unmount if busy
            
        Returns:
            bool: True if unmount successful
        """
        
    def is_mounted(self, mount_point: str) -> bool:
        """
        Check if filesystem is mounted at point.
        
        Args:
            mount_point: Mount point to check
            
        Returns:
            bool: True if mounted
        """
        
    def get_mounted_fs(self, mount_point: str) -> FileSystem:
        """
        Get filesystem mounted at point.
        
        Args:
            mount_point: Mount point
            
        Returns:
            FileSystem: Mounted filesystem (None if not mounted)
        """
```

## File Permissions

### Permission Constants

```python
# File type constants
S_IFMT = 0o170000    # File type mask
S_IFSOCK = 0o140000  # Socket
S_IFLNK = 0o120000   # Symbolic link
S_IFREG = 0o100000   # Regular file
S_IFBLK = 0o060000   # Block device
S_IFDIR = 0o040000   # Directory
S_IFCHR = 0o020000   # Character device
S_IFIFO = 0o010000   # FIFO (named pipe)

# Permission constants
S_ISUID = 0o4000     # Set user ID on execution
S_ISGID = 0o2000     # Set group ID on execution
S_ISVTX = 0o1000     # Sticky bit

S_IRWXU = 0o0700     # Owner read/write/execute
S_IRUSR = 0o0400     # Owner read
S_IWUSR = 0o0200     # Owner write
S_IXUSR = 0o0100     # Owner execute

S_IRWXG = 0o0070     # Group read/write/execute
S_IRGRP = 0o0040     # Group read
S_IWGRP = 0o0020     # Group write
S_IXGRP = 0o0010     # Group execute

S_IRWXO = 0o0007     # Others read/write/execute
S_IROTH = 0o0004     # Others read
S_IWOTH = 0o0002     # Others write
S_IXOTH = 0o0001     # Others execute
```

### Permission Helper Functions

```python
def is_readable(mode: int, uid: int, gid: int, file_uid: int, file_gid: int) -> bool:
    """
    Check if file is readable by user.
    
    Args:
        mode: File permission mode
        uid: User ID checking permission
        gid: Group ID checking permission
        file_uid: File owner user ID
        file_gid: File owner group ID
        
    Returns:
        bool: True if readable
    """

def is_writable(mode: int, uid: int, gid: int, file_uid: int, file_gid: int) -> bool:
    """Check if file is writable by user."""

def is_executable(mode: int, uid: int, gid: int, file_uid: int, file_gid: int) -> bool:
    """Check if file is executable by user."""

def mode_to_string(mode: int) -> str:
    """
    Convert numeric mode to string representation.
    
    Args:
        mode: Numeric permission mode
        
    Returns:
        str: String representation (e.g., 'rwxr-xr-x')
    """
```

## Error Handling

### Exception Types

```python
from kos.exceptions import FileSystemError

class FileSystemError(KOSError):
    """Base filesystem error."""
    pass

class MountError(FileSystemError):
    """Filesystem mount/unmount error."""
    pass

class PermissionError(FileSystemError):
    """File permission error."""
    pass

class FileNotFoundError(FileSystemError):
    """File or directory not found."""
    pass

class DirectoryNotEmptyError(FileSystemError):
    """Attempt to remove non-empty directory."""
    pass

class DiskFullError(FileSystemError):
    """Filesystem is full."""
    pass

class CorruptionError(FileSystemError):
    """Filesystem corruption detected."""
    pass
```

### Error Codes

```python
# Common filesystem error codes
ENOENT = -2      # No such file or directory
EACCES = -13     # Permission denied
EEXIST = -17     # File exists
ENOTDIR = -20    # Not a directory
EISDIR = -21     # Is a directory
EINVAL = -22     # Invalid argument
ENOSPC = -28     # No space left on device
EROFS = -30      # Read-only file system
ENAMETOOLONG = -36  # File name too long
ENOTEMPTY = -39  # Directory not empty
```

## Usage Examples

### Basic File Operations

```python
from kos.filesystem.vfs import VirtualFileSystem
from kos.filesystem.ramfs import RAMFileSystem

# Initialize VFS and mount RAM filesystem
vfs = VirtualFileSystem()
ramfs = RAMFileSystem(max_size=10*1024*1024)  # 10MB limit
vfs.mount(ramfs, '/tmp')

# Create and write to file
fd = vfs.open('/tmp/test.txt', 'w')
if fd > 0:
    bytes_written = vfs.write(fd, b'Hello, KOS filesystem!')
    vfs.close(fd)
    print(f"Wrote {bytes_written} bytes")

# Read file back
fd = vfs.open('/tmp/test.txt', 'r')
if fd > 0:
    content = vfs.read(fd)
    vfs.close(fd)
    print(f"Read: {content.decode()}")

# Get file statistics
stats = vfs.stat('/tmp/test.txt')
print(f"File size: {stats['size']} bytes")
print(f"Modified: {stats['mtime']}")
```

### Directory Operations

```python
# Create directory structure
vfs.mkdir('/tmp/projects', parents=True)
vfs.mkdir('/tmp/projects/kos')
vfs.mkdir('/tmp/projects/kos/src')

# List directory contents
files = vfs.listdir('/tmp/projects')
print(f"Projects: {files}")

# Create files in directory
for i in range(5):
    fd = vfs.open(f'/tmp/projects/kos/src/file_{i}.txt', 'w')
    vfs.write(fd, f'Content of file {i}'.encode())
    vfs.close(fd)

# List source files
src_files = vfs.listdir('/tmp/projects/kos/src')
print(f"Source files: {src_files}")
```

### File Permissions

```python
# Create file with specific permissions
fd = vfs.open('/tmp/secure.txt', 'w')
vfs.write(fd, b'Sensitive data')
vfs.close(fd)

# Set restrictive permissions (owner read/write only)
vfs.chmod('/tmp/secure.txt', 0o600)

# Check permissions
stats = vfs.stat('/tmp/secure.txt')
mode = stats['mode'] & 0o777
print(f"Permissions: {oct(mode)}")

# Change ownership (if permitted)
vfs.chown('/tmp/secure.txt', 1000, 1000)  # uid=1000, gid=1000
```

### File Locking

```python
from kos.filesystem.locks import FileLock, LockType

# Open file for shared access
fd1 = vfs.open('/tmp/shared.txt', 'r')
fd2 = vfs.open('/tmp/shared.txt', 'r')

# Acquire shared locks (multiple readers allowed)
lock1 = FileLock(fd1)
lock2 = FileLock(fd2)

if lock1.acquire(LockType.SHARED) and lock2.acquire(LockType.SHARED):
    print("Both shared locks acquired")
    
    # Read from both file descriptors
    vfs.seek(fd1, 0)
    vfs.seek(fd2, 0)
    data1 = vfs.read(fd1)
    data2 = vfs.read(fd2)
    
    # Release locks
    lock1.release()
    lock2.release()

vfs.close(fd1)
vfs.close(fd2)
```

### Memory Mapping

```python
from kos.filesystem.mmap import MemoryMappedFile

# Create large file for mapping
fd = vfs.open('/tmp/large_file.dat', 'w')
large_data = b'x' * (1024 * 1024)  # 1MB of data
vfs.write(fd, large_data)
vfs.close(fd)

# Open for memory mapping
fd = vfs.open('/tmp/large_file.dat', 'r+')
mmap_file = MemoryMappedFile(fd)

# Create memory mapping
addr = mmap_file.map()
if addr:
    print(f"File mapped at address: 0x{addr:x}")
    
    # Access mapped memory directly (conceptual - would use ctypes in practice)
    # mapped_data = (ctypes.c_char * mmap_file.get_size()).from_address(addr)
    
    # Synchronize changes
    mmap_file.sync()
    
    # Clean up
    mmap_file.unmap()

vfs.close(fd)
```

### Filesystem Monitoring

```python
# Monitor filesystem usage
mount_info = vfs.get_mount_info()
for mount in mount_info:
    print(f"Mount: {mount['mount_point']} ({mount['filesystem_type']})")
    
    if mount['filesystem_type'] == 'ramfs':
        # Get RAM filesystem specific stats
        fs = mount['filesystem']
        usage = fs.get_memory_usage()
        capacity = fs.get_capacity()
        free = fs.get_free_space()
        
        print(f"  Usage: {usage / (1024*1024):.1f}MB")
        print(f"  Capacity: {capacity / (1024*1024):.1f}MB")
        print(f"  Free: {free / (1024*1024):.1f}MB")
        print(f"  Utilization: {(usage/capacity)*100:.1f}%")
```

### Advanced VFS Operations

```python
# Path resolution with security
try:
    safe_path = vfs.resolve_path('/tmp/../etc/passwd', safe=True)
except ValueError as e:
    print(f"Dangerous path detected: {e}")

# Safe path resolution
safe_path = vfs.resolve_path('/tmp/./projects/../test.txt', safe=True)
print(f"Resolved path: {safe_path}")

# Rename/move operations
vfs.rename('/tmp/test.txt', '/tmp/renamed_test.txt')

# Atomic file operations (create temporary, then rename)
temp_fd = vfs.open('/tmp/atomic_write.tmp', 'w')
vfs.write(temp_fd, b'Atomic write content')
vfs.close(temp_fd)
vfs.rename('/tmp/atomic_write.tmp', '/tmp/atomic_write.txt')
```

## Performance Considerations

### Optimizations

1. **Batch Operations**: Group multiple file operations together
2. **Memory Mapping**: Use memory mapping for large files
3. **Buffer Sizes**: Use appropriate buffer sizes for I/O operations
4. **Asynchronous I/O**: Use async operations for concurrent access
5. **Caching**: Leverage filesystem caching mechanisms

### Best Practices

```python
# Use context managers for automatic cleanup
from contextlib import contextmanager

@contextmanager
def open_file(vfs, path, mode):
    fd = vfs.open(path, mode)
    try:
        yield fd
    finally:
        if fd > 0:
            vfs.close(fd)

# Usage
with open_file(vfs, '/tmp/data.txt', 'w') as fd:
    vfs.write(fd, b'Data with automatic cleanup')
```

## Integration with Other Subsystems

### Process Integration

```python
# Process-specific file descriptors
from kos.process.manager import ProcessManager

proc_mgr = ProcessManager()
process = proc_mgr.create_process('file_app', ['/bin/file_processor'])

# Each process has its own file descriptor table
# File operations are performed in process context
```

### Security Integration

```python
# Filesystem operations respect security policies
from kos.security.manager import SecurityManager

security_mgr = SecurityManager()

# Check permissions before file operations
if security_mgr.check_file_access(user_id, '/etc/passwd', 'read'):
    fd = vfs.open('/etc/passwd', 'r')
    # ... perform operation
else:
    raise PermissionError("Access denied")
```

### Memory Integration

```python
# Filesystem caching uses system memory
from kos.memory.manager import MemoryManager

memory_mgr = MemoryManager()

# VFS can use memory manager for caching
vfs.set_cache_size(memory_mgr.get_available_memory() // 4)  # Use 25% for cache
```
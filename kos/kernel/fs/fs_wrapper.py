#!/usr/bin/env python3
"""
KOS Filesystem Python Bindings

This module provides Python bindings for the KOS filesystem operations,
including VFS layer, inode operations, directory cache, file operations,
and path name resolution.

Author: KOS Development Team
"""

import os
import sys
import ctypes
import ctypes.util
from ctypes import (
    Structure, POINTER, pointer, byref, c_char, c_char_p, c_void_p,
    c_int, c_uint, c_long, c_ulong, c_uint64, c_int64, c_size_t,
    c_ssize_t, c_off_t, c_mode_t, c_uid_t, c_gid_t, c_dev_t,
    c_time_t, c_blksize_t, c_blkcnt_t, CFUNCTYPE
)
from threading import Lock
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Union, Callable
import stat

# Load the filesystem library
def _load_fs_library():
    """Load the KOS filesystem library"""
    lib_paths = [
        './libkos_fs.so',
        '/usr/local/lib/libkos_fs.so',
        '/usr/lib/libkos_fs.so',
        os.path.join(os.path.dirname(__file__), 'libkos_fs.so')
    ]
    
    for lib_path in lib_paths:
        try:
            return ctypes.CDLL(lib_path)
        except OSError:
            continue
    
    # If no library found, create a mock for development
    print("Warning: KOS filesystem library not found, using mock implementation")
    return None

# Global library instance
_fs_lib = _load_fs_library()

# Constants from fs.h
KOS_MAX_FILENAME = 255
KOS_MAX_PATH = 4096

# File system types
KOS_FS_TYPE_RAMFS = 1
KOS_FS_TYPE_DEVFS = 2
KOS_FS_TYPE_PROCFS = 3
KOS_FS_TYPE_SYSFS = 4
KOS_FS_TYPE_EXT4 = 5

# File types
KOS_S_IFMT = 0o170000
KOS_S_IFREG = 0o100000
KOS_S_IFDIR = 0o040000
KOS_S_IFCHR = 0o020000
KOS_S_IFBLK = 0o060000
KOS_S_IFIFO = 0o010000
KOS_S_IFLNK = 0o120000
KOS_S_IFSOCK = 0o140000

# File permissions
KOS_S_ISUID = 0o4000
KOS_S_ISGID = 0o2000
KOS_S_ISVTX = 0o1000
KOS_S_IRUSR = 0o400
KOS_S_IWUSR = 0o200
KOS_S_IXUSR = 0o100
KOS_S_IRGRP = 0o040
KOS_S_IWGRP = 0o020
KOS_S_IXGRP = 0o010
KOS_S_IROTH = 0o004
KOS_S_IWOTH = 0o002
KOS_S_IXOTH = 0o001

# File flags
KOS_O_RDONLY = 0o0000000
KOS_O_WRONLY = 0o0000001
KOS_O_RDWR = 0o0000002
KOS_O_CREAT = 0o0000100
KOS_O_EXCL = 0o0000200
KOS_O_NOCTTY = 0o0000400
KOS_O_TRUNC = 0o0001000
KOS_O_APPEND = 0o0002000
KOS_O_NONBLOCK = 0o0004000
KOS_O_SYNC = 0o4010000
KOS_O_DIRECTORY = 0o0200000

# Seek operations
KOS_SEEK_SET = 0
KOS_SEEK_CUR = 1
KOS_SEEK_END = 2

# Lock types
KOS_F_RDLCK = 0
KOS_F_WRLCK = 1
KOS_F_UNLCK = 2

# C Structures
class KosXattr(Structure):
    """Extended attribute structure"""
    _fields_ = [
        ('name', c_char * 256),
        ('value', c_void_p),
        ('size', c_size_t),
        ('next', c_void_p)
    ]

class KosAclEntry(Structure):
    """ACL entry structure"""
    _fields_ = [
        ('tag', c_uint),
        ('perm', c_uint),
        ('id', c_uint)
    ]

class KosAcl(Structure):
    """ACL structure"""
    _fields_ = [
        ('count', c_int),
        ('entries', POINTER(KosAclEntry))
    ]

class KosFileLock(Structure):
    """File lock structure"""
    _fields_ = [
        ('type', c_int),
        ('start', c_off_t),
        ('len', c_off_t),
        ('pid', c_int),
        ('next', c_void_p)
    ]

class KosInode(Structure):
    """Inode structure"""
    _fields_ = [
        ('ino', c_uint64),
        ('mode', c_mode_t),
        ('nlink', c_uint),
        ('uid', c_uid_t),
        ('gid', c_gid_t),
        ('rdev', c_dev_t),
        ('size', c_off_t),
        ('atime', c_time_t),
        ('mtime', c_time_t),
        ('ctime', c_time_t),
        ('blksize', c_blksize_t),
        ('blocks', c_blkcnt_t),
        ('private_data', c_void_p),
        ('i_op', c_void_p),
        ('i_fop', c_void_p),
        ('xattrs', POINTER(KosXattr)),
        ('acl_access', POINTER(KosAcl)),
        ('acl_default', POINTER(KosAcl)),
        ('locks', POINTER(KosFileLock)),
        ('ref_count', c_int),
        ('i_hash_next', c_void_p),
        ('i_hash_prev', c_void_p),
        ('i_sb', c_void_p)
    ]

class KosDentry(Structure):
    """Directory entry structure"""
    _fields_ = [
        ('name', c_char * (KOS_MAX_FILENAME + 1)),
        ('inode', POINTER(KosInode)),
        ('parent', c_void_p),
        ('child', c_void_p),
        ('sibling', c_void_p),
        ('d_hash_next', c_void_p),
        ('d_hash_prev', c_void_p),
        ('ref_count', c_int),
        ('flags', c_uint),
        ('cache_time', c_time_t)
    ]

class KosFile(Structure):
    """File structure"""
    _fields_ = [
        ('dentry', POINTER(KosDentry)),
        ('f_op', c_void_p),
        ('position', c_off_t),
        ('flags', c_uint),
        ('mode', c_mode_t),
        ('locks', POINTER(KosFileLock)),
        ('ref_count', c_int),
        ('private_data', c_void_p)
    ]

class KosStat(Structure):
    """Stat structure for file information"""
    _fields_ = [
        ('st_ino', c_uint64),
        ('st_mode', c_mode_t),
        ('st_nlink', c_uint),
        ('st_uid', c_uid_t),
        ('st_gid', c_gid_t),
        ('st_rdev', c_dev_t),
        ('st_size', c_off_t),
        ('st_atime', c_time_t),
        ('st_mtime', c_time_t),
        ('st_ctime', c_time_t),
        ('st_blksize', c_blksize_t),
        ('st_blocks', c_blkcnt_t)
    ]

# Exception classes
class KosFilesystemError(Exception):
    """Base class for KOS filesystem errors"""
    pass

class KosPermissionError(KosFilesystemError):
    """Permission denied error"""
    pass

class KosNotFoundError(KosFilesystemError):
    """File or directory not found error"""
    pass

class KosExistsError(KosFilesystemError):
    """File or directory already exists error"""
    pass

class KosIsDirectoryError(KosFilesystemError):
    """Is a directory error"""
    pass

class KosNotDirectoryError(KosFilesystemError):
    """Not a directory error"""
    pass

# Helper functions
def _handle_error(errno: int) -> None:
    """Convert errno to appropriate exception"""
    if errno == 0:
        return
    
    error_map = {
        1: KosPermissionError("Operation not permitted"),
        2: KosNotFoundError("No such file or directory"),
        13: KosPermissionError("Permission denied"),
        17: KosExistsError("File exists"),
        20: KosNotDirectoryError("Not a directory"),
        21: KosIsDirectoryError("Is a directory"),
    }
    
    if errno in error_map:
        raise error_map[errno]
    else:
        raise KosFilesystemError(f"Filesystem error: {errno}")

def _setup_library_functions():
    """Setup C library function signatures"""
    if not _fs_lib:
        return
    
    # VFS functions
    _fs_lib.kos_sys_open.argtypes = [c_char_p, c_int, c_mode_t]
    _fs_lib.kos_sys_open.restype = c_int
    
    _fs_lib.kos_sys_close.argtypes = [c_int]
    _fs_lib.kos_sys_close.restype = c_int
    
    _fs_lib.kos_sys_read.argtypes = [c_int, c_void_p, c_size_t]
    _fs_lib.kos_sys_read.restype = c_ssize_t
    
    _fs_lib.kos_sys_write.argtypes = [c_int, c_void_p, c_size_t]
    _fs_lib.kos_sys_write.restype = c_ssize_t
    
    _fs_lib.kos_sys_lseek.argtypes = [c_int, c_off_t, c_int]
    _fs_lib.kos_sys_lseek.restype = c_off_t
    
    _fs_lib.kos_sys_stat.argtypes = [c_char_p, POINTER(KosStat)]
    _fs_lib.kos_sys_stat.restype = c_int
    
    _fs_lib.kos_sys_mkdir.argtypes = [c_char_p, c_mode_t]
    _fs_lib.kos_sys_mkdir.restype = c_int
    
    # Mount functions
    _fs_lib.kos_mount.argtypes = [c_char_p, c_char_p, c_char_p, c_ulong, c_void_p]
    _fs_lib.kos_mount.restype = c_int
    
    _fs_lib.kos_umount.argtypes = [c_char_p]
    _fs_lib.kos_umount.restype = c_int

# Setup library functions
_setup_library_functions()

# Mock implementations for development
class MockFilesystem:
    """Mock filesystem implementation for development"""
    
    def __init__(self):
        self._files = {}
        self._next_fd = 3  # Start after stdin, stdout, stderr
        self._open_files = {}
        self._lock = Lock()
    
    def open(self, path: str, flags: int, mode: int = 0o644) -> int:
        """Mock open implementation"""
        with self._lock:
            fd = self._next_fd
            self._next_fd += 1
            
            # Create mock file data
            file_data = {
                'path': path,
                'flags': flags,
                'mode': mode,
                'position': 0,
                'content': b'',
                'size': 0
            }
            
            # Handle creation
            if flags & KOS_O_CREAT:
                if path not in self._files:
                    self._files[path] = {
                        'content': b'',
                        'mode': mode,
                        'size': 0,
                        'atime': int(time.time()),
                        'mtime': int(time.time()),
                        'ctime': int(time.time())
                    }
                elif flags & KOS_O_EXCL:
                    raise KosExistsError(f"File exists: {path}")
            
            if path in self._files:
                file_data['content'] = self._files[path]['content']
                file_data['size'] = self._files[path]['size']
                
                # Handle truncation
                if flags & KOS_O_TRUNC:
                    file_data['content'] = b''
                    file_data['size'] = 0
                    self._files[path]['content'] = b''
                    self._files[path]['size'] = 0
            
            self._open_files[fd] = file_data
            return fd
    
    def close(self, fd: int) -> int:
        """Mock close implementation"""
        with self._lock:
            if fd not in self._open_files:
                return -1
            
            file_data = self._open_files[fd]
            if file_data['path'] in self._files:
                self._files[file_data['path']]['content'] = file_data['content']
                self._files[file_data['path']]['size'] = file_data['size']
            
            del self._open_files[fd]
            return 0
    
    def read(self, fd: int, size: int) -> bytes:
        """Mock read implementation"""
        with self._lock:
            if fd not in self._open_files:
                raise KosFilesystemError("Bad file descriptor")
            
            file_data = self._open_files[fd]
            pos = file_data['position']
            data = file_data['content'][pos:pos + size]
            file_data['position'] += len(data)
            
            return data
    
    def write(self, fd: int, data: bytes) -> int:
        """Mock write implementation"""
        with self._lock:
            if fd not in self._open_files:
                raise KosFilesystemError("Bad file descriptor")
            
            file_data = self._open_files[fd]
            pos = file_data['position']
            
            # Handle append mode
            if file_data['flags'] & KOS_O_APPEND:
                pos = len(file_data['content'])
            
            # Update content
            content = bytearray(file_data['content'])
            if pos + len(data) > len(content):
                content.extend(b'\x00' * (pos + len(data) - len(content)))
            
            content[pos:pos + len(data)] = data
            file_data['content'] = bytes(content)
            file_data['size'] = len(content)
            file_data['position'] = pos + len(data)
            
            return len(data)
    
    def lseek(self, fd: int, offset: int, whence: int) -> int:
        """Mock lseek implementation"""
        with self._lock:
            if fd not in self._open_files:
                raise KosFilesystemError("Bad file descriptor")
            
            file_data = self._open_files[fd]
            
            if whence == KOS_SEEK_SET:
                new_pos = offset
            elif whence == KOS_SEEK_CUR:
                new_pos = file_data['position'] + offset
            elif whence == KOS_SEEK_END:
                new_pos = file_data['size'] + offset
            else:
                raise KosFilesystemError("Invalid whence")
            
            if new_pos < 0:
                raise KosFilesystemError("Invalid seek position")
            
            file_data['position'] = new_pos
            return new_pos
    
    def stat(self, path: str) -> Dict[str, Any]:
        """Mock stat implementation"""
        with self._lock:
            if path not in self._files:
                raise KosNotFoundError(f"No such file: {path}")
            
            file_info = self._files[path]
            return {
                'st_size': file_info['size'],
                'st_mode': file_info['mode'],
                'st_atime': file_info['atime'],
                'st_mtime': file_info['mtime'],
                'st_ctime': file_info['ctime']
            }

# Global mock filesystem instance
_mock_fs = MockFilesystem()

# High-level Python API
class KosFile:
    """High-level file object for KOS filesystem"""
    
    def __init__(self, path: str, mode: str = 'r'):
        self.path = path
        self.mode = mode
        self._fd = None
        self._closed = False
        
        # Convert Python mode to KOS flags
        flags = 0
        if 'r' in mode:
            if '+' in mode:
                flags |= KOS_O_RDWR
            else:
                flags |= KOS_O_RDONLY
        elif 'w' in mode:
            if '+' in mode:
                flags |= KOS_O_RDWR
            else:
                flags |= KOS_O_WRONLY
            flags |= KOS_O_CREAT | KOS_O_TRUNC
        elif 'a' in mode:
            if '+' in mode:
                flags |= KOS_O_RDWR
            else:
                flags |= KOS_O_WRONLY
            flags |= KOS_O_CREAT | KOS_O_APPEND
        
        self._flags = flags
        self._open()
    
    def _open(self):
        """Open the file"""
        if _fs_lib:
            self._fd = _fs_lib.kos_sys_open(self.path.encode(), self._flags, 0o644)
            if self._fd < 0:
                _handle_error(-self._fd)
        else:
            self._fd = _mock_fs.open(self.path, self._flags, 0o644)
    
    def read(self, size: int = -1) -> bytes:
        """Read data from file"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if size == -1:
            # Read all
            data = b''
            while True:
                chunk = self.read(8192)
                if not chunk:
                    break
                data += chunk
            return data
        
        if _fs_lib:
            buffer = ctypes.create_string_buffer(size)
            result = _fs_lib.kos_sys_read(self._fd, buffer, size)
            if result < 0:
                _handle_error(-result)
            return buffer.raw[:result]
        else:
            return _mock_fs.read(self._fd, size)
    
    def write(self, data: Union[str, bytes]) -> int:
        """Write data to file"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if isinstance(data, str):
            data = data.encode()
        
        if _fs_lib:
            result = _fs_lib.kos_sys_write(self._fd, data, len(data))
            if result < 0:
                _handle_error(-result)
            return result
        else:
            return _mock_fs.write(self._fd, data)
    
    def seek(self, offset: int, whence: int = KOS_SEEK_SET) -> int:
        """Seek to position in file"""
        if self._closed:
            raise ValueError("I/O operation on closed file")
        
        if _fs_lib:
            result = _fs_lib.kos_sys_lseek(self._fd, offset, whence)
            if result < 0:
                _handle_error(-result)
            return result
        else:
            return _mock_fs.lseek(self._fd, offset, whence)
    
    def tell(self) -> int:
        """Get current position in file"""
        return self.seek(0, KOS_SEEK_CUR)
    
    def close(self):
        """Close the file"""
        if not self._closed and self._fd is not None:
            if _fs_lib:
                result = _fs_lib.kos_sys_close(self._fd)
                if result < 0:
                    _handle_error(-result)
            else:
                _mock_fs.close(self._fd)
            
            self._closed = True
            self._fd = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __del__(self):
        if not self._closed:
            self.close()

class KosPath:
    """Path operations for KOS filesystem"""
    
    @staticmethod
    def exists(path: str) -> bool:
        """Check if path exists"""
        try:
            KosPath.stat(path)
            return True
        except KosNotFoundError:
            return False
    
    @staticmethod
    def stat(path: str) -> Dict[str, Any]:
        """Get file statistics"""
        if _fs_lib:
            stat_buf = KosStat()
            result = _fs_lib.kos_sys_stat(path.encode(), byref(stat_buf))
            if result < 0:
                _handle_error(-result)
            
            return {
                'st_ino': stat_buf.st_ino,
                'st_mode': stat_buf.st_mode,
                'st_nlink': stat_buf.st_nlink,
                'st_uid': stat_buf.st_uid,
                'st_gid': stat_buf.st_gid,
                'st_size': stat_buf.st_size,
                'st_atime': stat_buf.st_atime,
                'st_mtime': stat_buf.st_mtime,
                'st_ctime': stat_buf.st_ctime,
                'st_blksize': stat_buf.st_blksize,
                'st_blocks': stat_buf.st_blocks
            }
        else:
            return _mock_fs.stat(path)
    
    @staticmethod
    def mkdir(path: str, mode: int = 0o755):
        """Create directory"""
        if _fs_lib:
            result = _fs_lib.kos_sys_mkdir(path.encode(), mode)
            if result < 0:
                _handle_error(-result)
        else:
            # Mock implementation
            _mock_fs._files[path] = {
                'content': b'',
                'mode': mode | KOS_S_IFDIR,
                'size': 0,
                'atime': int(time.time()),
                'mtime': int(time.time()),
                'ctime': int(time.time())
            }
    
    @staticmethod
    def isdir(path: str) -> bool:
        """Check if path is a directory"""
        try:
            stat_info = KosPath.stat(path)
            return stat.S_ISDIR(stat_info['st_mode'])
        except KosNotFoundError:
            return False
    
    @staticmethod
    def isfile(path: str) -> bool:
        """Check if path is a regular file"""
        try:
            stat_info = KosPath.stat(path)
            return stat.S_ISREG(stat_info['st_mode'])
        except KosNotFoundError:
            return False

class KosFilesystem:
    """Main KOS filesystem interface"""
    
    def __init__(self):
        self._mounted = {}
        self._lock = Lock()
    
    def mount(self, source: str, target: str, fstype: str, flags: int = 0, data: Optional[bytes] = None):
        """Mount a filesystem"""
        if _fs_lib:
            result = _fs_lib.kos_mount(
                source.encode() if source else None,
                target.encode(),
                fstype.encode(),
                flags,
                data
            )
            if result < 0:
                _handle_error(-result)
        
        with self._lock:
            self._mounted[target] = {
                'source': source,
                'fstype': fstype,
                'flags': flags
            }
    
    def umount(self, target: str):
        """Unmount a filesystem"""
        if _fs_lib:
            result = _fs_lib.kos_umount(target.encode())
            if result < 0:
                _handle_error(-result)
        
        with self._lock:
            if target in self._mounted:
                del self._mounted[target]
    
    def get_mounts(self) -> Dict[str, Dict[str, Any]]:
        """Get list of mounted filesystems"""
        with self._lock:
            return self._mounted.copy()
    
    def open(self, path: str, mode: str = 'r') -> KosFile:
        """Open a file"""
        return KosFile(path, mode)
    
    def stat(self, path: str) -> Dict[str, Any]:
        """Get file statistics"""
        return KosPath.stat(path)
    
    def exists(self, path: str) -> bool:
        """Check if path exists"""
        return KosPath.exists(path)
    
    def mkdir(self, path: str, mode: int = 0o755):
        """Create directory"""
        KosPath.mkdir(path, mode)
    
    def isdir(self, path: str) -> bool:
        """Check if path is a directory"""
        return KosPath.isdir(path)
    
    def isfile(self, path: str) -> bool:
        """Check if path is a regular file"""
        return KosPath.isfile(path)

# Global filesystem instance
kos_fs = KosFilesystem()

# Convenience functions
def open(path: str, mode: str = 'r') -> KosFile:
    """Open a file (convenience function)"""
    return kos_fs.open(path, mode)

def stat(path: str) -> Dict[str, Any]:
    """Get file statistics (convenience function)"""
    return kos_fs.stat(path)

def exists(path: str) -> bool:
    """Check if path exists (convenience function)"""
    return kos_fs.exists(path)

def mkdir(path: str, mode: int = 0o755):
    """Create directory (convenience function)"""
    kos_fs.mkdir(path, mode)

def isdir(path: str) -> bool:
    """Check if path is a directory (convenience function)"""
    return kos_fs.isdir(path)

def isfile(path: str) -> bool:
    """Check if path is a regular file (convenience function)"""
    return kos_fs.isfile(path)

def mount(source: str, target: str, fstype: str, flags: int = 0, data: Optional[bytes] = None):
    """Mount a filesystem (convenience function)"""
    kos_fs.mount(source, target, fstype, flags, data)

def umount(target: str):
    """Unmount a filesystem (convenience function)"""
    kos_fs.umount(target)

# Extended attributes support
class KosXattrs:
    """Extended attributes interface"""
    
    @staticmethod
    def set(path: str, name: str, value: bytes, flags: int = 0):
        """Set extended attribute"""
        # This would call the C function if available
        pass
    
    @staticmethod
    def get(path: str, name: str) -> bytes:
        """Get extended attribute"""
        # This would call the C function if available
        return b''
    
    @staticmethod
    def list(path: str) -> List[str]:
        """List extended attributes"""
        # This would call the C function if available
        return []
    
    @staticmethod
    def remove(path: str, name: str):
        """Remove extended attribute"""
        # This would call the C function if available
        pass

# ACL support
class KosAcls:
    """Access Control Lists interface"""
    
    @staticmethod
    def get(path: str) -> Dict[str, Any]:
        """Get ACL for path"""
        # This would call the C function if available
        return {}
    
    @staticmethod
    def set(path: str, acl: Dict[str, Any]):
        """Set ACL for path"""
        # This would call the C function if available
        pass

# Module initialization
def initialize():
    """Initialize the KOS filesystem module"""
    if _fs_lib:
        # Call any necessary initialization functions
        pass
    print("KOS Filesystem Python bindings initialized")

def cleanup():
    """Cleanup the KOS filesystem module"""
    if _fs_lib:
        # Call any necessary cleanup functions
        pass

# Initialize when module is imported
initialize()

# Export public API
__all__ = [
    'KosFile', 'KosPath', 'KosFilesystem', 'KosXattrs', 'KosAcls',
    'KosFilesystemError', 'KosPermissionError', 'KosNotFoundError',
    'KosExistsError', 'KosIsDirectoryError', 'KosNotDirectoryError',
    'open', 'stat', 'exists', 'mkdir', 'isdir', 'isfile', 'mount', 'umount',
    'kos_fs', 'initialize', 'cleanup'
]

if __name__ == "__main__":
    # Simple test
    print("KOS Filesystem Python Bindings Test")
    
    # Test file operations
    try:
        with open("/tmp/test.txt", "w") as f:
            f.write("Hello, KOS Filesystem!")
        
        with open("/tmp/test.txt", "r") as f:
            content = f.read()
            print(f"File content: {content}")
        
        if exists("/tmp/test.txt"):
            stat_info = stat("/tmp/test.txt")
            print(f"File size: {stat_info['st_size']} bytes")
        
        print("Test completed successfully!")
        
    except Exception as e:
        print(f"Test failed: {e}")
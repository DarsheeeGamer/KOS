"""
KOS VFS Python Wrapper

Provides Python interface to the C++ VFS implementation
"""

import ctypes
import os
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Union
import logging

logger = logging.getLogger('KOS.vfs')

# VFS Error codes
VFS_SUCCESS = 0
VFS_ERROR = -1
VFS_ENOENT = -2
VFS_EACCES = -3
VFS_EEXIST = -4
VFS_ENOTDIR = -5
VFS_EISDIR = -6
VFS_ENOMEM = -7
VFS_ENOSPC = -8
VFS_EINVAL = -9
VFS_EBUSY = -10

# File types
VFS_TYPE_FILE = 1
VFS_TYPE_DIR = 2
VFS_TYPE_LINK = 3
VFS_TYPE_DEVICE = 4
VFS_TYPE_PIPE = 5
VFS_TYPE_SOCKET = 6

# Open flags
VFS_O_RDONLY = 0x0001
VFS_O_WRONLY = 0x0002
VFS_O_RDWR = 0x0003
VFS_O_CREAT = 0x0040
VFS_O_EXCL = 0x0080
VFS_O_TRUNC = 0x0200
VFS_O_APPEND = 0x0400


class VFSHandle(ctypes.Structure):
    _fields_ = [
        ("fd", ctypes.c_int),
        ("private_data", ctypes.c_void_p)
    ]


class VFSStat(ctypes.Structure):
    _fields_ = [
        ("st_dev", ctypes.c_uint32),
        ("st_ino", ctypes.c_uint32),
        ("st_mode", ctypes.c_uint16),
        ("st_nlink", ctypes.c_uint16),
        ("st_uid", ctypes.c_uint32),
        ("st_gid", ctypes.c_uint32),
        ("st_size", ctypes.c_uint64),
        ("st_atime_sec", ctypes.c_uint64),
        ("st_mtime_sec", ctypes.c_uint64),
        ("st_ctime_sec", ctypes.c_uint64),
        ("st_blksize", ctypes.c_uint32),
        ("st_blocks", ctypes.c_uint64)
    ]


class VFSDirent(ctypes.Structure):
    _fields_ = [
        ("d_ino", ctypes.c_uint32),
        ("d_type", ctypes.c_uint16),
        ("d_name", ctypes.c_char * 256)
    ]


class VFSContext(ctypes.Structure):
    _fields_ = [
        ("uid", ctypes.c_uint32),
        ("gid", ctypes.c_uint32),
        ("umask", ctypes.c_uint32),
        ("cwd", ctypes.c_char_p)
    ]


class VFSException(Exception):
    """Base VFS exception"""
    pass


class FileNotFoundError(VFSException):
    """File not found"""
    pass


class PermissionError(VFSException):
    """Permission denied"""
    pass


class FileExistsError(VFSException):
    """File already exists"""
    pass


class NotADirectoryError(VFSException):
    """Not a directory"""
    pass


class IsADirectoryError(VFSException):
    """Is a directory"""
    pass


class VirtualFileSystem:
    """Python wrapper for KOS VFS"""
    
    def __init__(self):
        self.lib = None
        self.context = None
        self._load_library()
        self._init_vfs()
        
    def _load_library(self):
        """Load the VFS shared library"""
        # Try to compile if not exists
        lib_path = Path(__file__).parent / "libkosvfs.so"
        
        if not lib_path.exists():
            self._compile_library()
            
        try:
            self.lib = ctypes.CDLL(str(lib_path))
            self._setup_functions()
        except Exception as e:
            logger.error(f"Failed to load VFS library: {e}")
            raise VFSException(f"Cannot load VFS library: {e}")
            
    def _compile_library(self):
        """Compile the C++ VFS library"""
        import subprocess
        
        vfs_dir = Path(__file__).parent
        
        # Create simple Makefile
        makefile_content = """
CXX = g++
CXXFLAGS = -std=c++17 -fPIC -Wall -O2
LDFLAGS = -shared

SOURCES = vfs_api.cpp vfs_core.cpp
OBJECTS = $(SOURCES:.cpp=.o)
TARGET = libkosvfs.so

all: $(TARGET)

$(TARGET): $(OBJECTS)
\t$(CXX) $(LDFLAGS) -o $@ $^

%.o: %.cpp
\t$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
\trm -f $(OBJECTS) $(TARGET)

.PHONY: all clean
"""
        
        makefile_path = vfs_dir / "Makefile"
        makefile_path.write_text(makefile_content)
        
        # Compile
        try:
            subprocess.run(["make", "-C", str(vfs_dir)], check=True, 
                          capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to compile VFS library: {e.stderr}")
            raise VFSException(f"Cannot compile VFS library: {e.stderr}")
            
    def _setup_functions(self):
        """Setup C function signatures"""
        # vfs_init
        self.lib.vfs_init.argtypes = []
        self.lib.vfs_init.restype = ctypes.c_int
        
        # vfs_shutdown
        self.lib.vfs_shutdown.argtypes = []
        self.lib.vfs_shutdown.restype = ctypes.c_int
        
        # vfs_open
        self.lib.vfs_open.argtypes = [ctypes.c_char_p, ctypes.c_int, 
                                      ctypes.c_uint16, ctypes.POINTER(VFSContext)]
        self.lib.vfs_open.restype = ctypes.POINTER(VFSHandle)
        
        # vfs_close
        self.lib.vfs_close.argtypes = [ctypes.POINTER(VFSHandle)]
        self.lib.vfs_close.restype = ctypes.c_int
        
        # vfs_read
        self.lib.vfs_read.argtypes = [ctypes.POINTER(VFSHandle), 
                                      ctypes.c_void_p, ctypes.c_size_t]
        self.lib.vfs_read.restype = ctypes.c_ssize_t
        
        # vfs_write
        self.lib.vfs_write.argtypes = [ctypes.POINTER(VFSHandle),
                                       ctypes.c_void_p, ctypes.c_size_t]
        self.lib.vfs_write.restype = ctypes.c_ssize_t
        
        # vfs_mkdir
        self.lib.vfs_mkdir.argtypes = [ctypes.c_char_p, ctypes.c_uint16,
                                       ctypes.POINTER(VFSContext)]
        self.lib.vfs_mkdir.restype = ctypes.c_int
        
        # vfs_rmdir
        self.lib.vfs_rmdir.argtypes = [ctypes.c_char_p, ctypes.POINTER(VFSContext)]
        self.lib.vfs_rmdir.restype = ctypes.c_int
        
        # vfs_stat
        self.lib.vfs_stat.argtypes = [ctypes.c_char_p, ctypes.POINTER(VFSStat),
                                      ctypes.POINTER(VFSContext)]
        self.lib.vfs_stat.restype = ctypes.c_int
        
        # vfs_unlink
        self.lib.vfs_unlink.argtypes = [ctypes.c_char_p, ctypes.POINTER(VFSContext)]
        self.lib.vfs_unlink.restype = ctypes.c_int
        
        # vfs_rename
        self.lib.vfs_rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                                        ctypes.POINTER(VFSContext)]
        self.lib.vfs_rename.restype = ctypes.c_int
        
        # Context management
        self.lib.vfs_context_create.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        self.lib.vfs_context_create.restype = ctypes.POINTER(VFSContext)
        
        self.lib.vfs_context_destroy.argtypes = [ctypes.POINTER(VFSContext)]
        self.lib.vfs_context_destroy.restype = None
        
        # Error handling
        self.lib.vfs_errno.argtypes = []
        self.lib.vfs_errno.restype = ctypes.c_int
        
        self.lib.vfs_strerror.argtypes = [ctypes.c_int]
        self.lib.vfs_strerror.restype = ctypes.c_char_p
        
    def _init_vfs(self):
        """Initialize the VFS"""
        ret = self.lib.vfs_init()
        if ret != VFS_SUCCESS:
            raise VFSException("Failed to initialize VFS")
            
        # Create default context
        self.context = self.lib.vfs_context_create(os.getuid(), os.getgid())
        
    def _check_error(self, ret: int, path: str = ""):
        """Check return value and raise appropriate exception"""
        if ret == VFS_SUCCESS:
            return
            
        errno = self.lib.vfs_errno()
        error_msg = self.lib.vfs_strerror(errno).decode('utf-8')
        
        if errno == VFS_ENOENT:
            raise FileNotFoundError(f"{path}: {error_msg}")
        elif errno == VFS_EACCES:
            raise PermissionError(f"{path}: {error_msg}")
        elif errno == VFS_EEXIST:
            raise FileExistsError(f"{path}: {error_msg}")
        elif errno == VFS_ENOTDIR:
            raise NotADirectoryError(f"{path}: {error_msg}")
        elif errno == VFS_EISDIR:
            raise IsADirectoryError(f"{path}: {error_msg}")
        else:
            raise VFSException(f"{path}: {error_msg}")
            
    def mkdir(self, path: str, mode: int = 0o755, uid: Optional[int] = None,
              gid: Optional[int] = None) -> None:
        """Create a directory"""
        # Create context for this operation
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            gid if gid is not None else os.getgid()
        )
        
        try:
            ret = self.lib.vfs_mkdir(path.encode('utf-8'), mode, ctx)
            self._check_error(ret, path)
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def rmdir(self, path: str, uid: Optional[int] = None) -> None:
        """Remove a directory"""
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            os.getgid()
        )
        
        try:
            ret = self.lib.vfs_rmdir(path.encode('utf-8'), ctx)
            self._check_error(ret, path)
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def open(self, path: str, flags: int = VFS_O_RDONLY, mode: int = 0o644,
             uid: Optional[int] = None, gid: Optional[int] = None):
        """Open a file and return a handle"""
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            gid if gid is not None else os.getgid()
        )
        
        try:
            handle = self.lib.vfs_open(path.encode('utf-8'), flags, mode, ctx)
            if not handle:
                errno = self.lib.vfs_errno()
                self._check_error(errno, path)
                
            return VFSFile(self, handle, path)
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def stat(self, path: str, uid: Optional[int] = None) -> dict:
        """Get file information"""
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            os.getgid()
        )
        
        try:
            stat = VFSStat()
            ret = self.lib.vfs_stat(path.encode('utf-8'), ctypes.byref(stat), ctx)
            self._check_error(ret, path)
            
            return {
                'dev': stat.st_dev,
                'ino': stat.st_ino,
                'mode': stat.st_mode,
                'nlink': stat.st_nlink,
                'uid': stat.st_uid,
                'gid': stat.st_gid,
                'size': stat.st_size,
                'atime': stat.st_atime_sec,
                'mtime': stat.st_mtime_sec,
                'ctime': stat.st_ctime_sec,
                'blksize': stat.st_blksize,
                'blocks': stat.st_blocks
            }
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def unlink(self, path: str, uid: Optional[int] = None) -> None:
        """Remove a file"""
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            os.getgid()
        )
        
        try:
            ret = self.lib.vfs_unlink(path.encode('utf-8'), ctx)
            self._check_error(ret, path)
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def rename(self, oldpath: str, newpath: str, uid: Optional[int] = None) -> None:
        """Rename a file or directory"""
        ctx = self.lib.vfs_context_create(
            uid if uid is not None else os.getuid(),
            os.getgid()
        )
        
        try:
            ret = self.lib.vfs_rename(oldpath.encode('utf-8'), 
                                      newpath.encode('utf-8'), ctx)
            self._check_error(ret, oldpath)
        finally:
            self.lib.vfs_context_destroy(ctx)
            
    def exists(self, path: str, uid: Optional[int] = None) -> bool:
        """Check if a path exists"""
        try:
            self.stat(path, uid)
            return True
        except FileNotFoundError:
            return False
            
    def makedirs(self, path: str, mode: int = 0o755, exist_ok: bool = False,
                 uid: Optional[int] = None, gid: Optional[int] = None) -> None:
        """Create directories recursively"""
        parts = path.strip('/').split('/')
        current_path = '/'
        
        for part in parts:
            current_path = os.path.join(current_path, part)
            
            try:
                self.mkdir(current_path, mode, uid, gid)
            except FileExistsError:
                if not exist_ok:
                    raise
                    
    def write_file(self, path: str, data: Union[str, bytes], 
                   uid: Optional[int] = None, gid: Optional[int] = None) -> None:
        """Write data to a file"""
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        with self.open(path, VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC, 
                      0o644, uid, gid) as f:
            f.write(data)
            
    def read_file(self, path: str, uid: Optional[int] = None) -> bytes:
        """Read entire file contents"""
        with self.open(path, VFS_O_RDONLY, uid=uid) as f:
            return f.read()
            
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, 'context') and self.context:
            self.lib.vfs_context_destroy(self.context)
        if hasattr(self, 'lib') and self.lib:
            self.lib.vfs_shutdown()


class VFSFile:
    """File handle wrapper"""
    
    def __init__(self, vfs: VirtualFileSystem, handle: ctypes.POINTER(VFSHandle), 
                 path: str):
        self.vfs = vfs
        self.handle = handle
        self.path = path
        self.closed = False
        
    def read(self, size: int = -1) -> bytes:
        """Read from file"""
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if size == -1:
            # Read entire file
            stat = self.vfs.stat(self.path)
            size = stat['size']
            
        buffer = ctypes.create_string_buffer(size)
        bytes_read = self.vfs.lib.vfs_read(self.handle, buffer, size)
        
        if bytes_read < 0:
            self.vfs._check_error(bytes_read, self.path)
            
        return buffer.raw[:bytes_read]
        
    def write(self, data: Union[str, bytes]) -> int:
        """Write to file"""
        if self.closed:
            raise ValueError("I/O operation on closed file")
            
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        bytes_written = self.vfs.lib.vfs_write(self.handle, data, len(data))
        
        if bytes_written < 0:
            self.vfs._check_error(bytes_written, self.path)
            
        return bytes_written
        
    def close(self) -> None:
        """Close the file"""
        if not self.closed:
            self.vfs.lib.vfs_close(self.handle)
            self.closed = True
            
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def __del__(self):
        self.close()


# Global VFS instance
_vfs_instance = None


def get_vfs() -> VirtualFileSystem:
    """Get the global VFS instance"""
    global _vfs_instance
    if _vfs_instance is None:
        _vfs_instance = VirtualFileSystem()
    return _vfs_instance
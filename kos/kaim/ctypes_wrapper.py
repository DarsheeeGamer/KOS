"""
KAIM Python ctypes wrapper for C++ library
Production-ready implementation with full kernel integration
"""

import os
import ctypes
import ctypes.util
import json
import struct
import fcntl
import errno
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from dataclasses import dataclass
import threading

logger = logging.getLogger('kaim.ctypes')

# Find and load the KAIM library
def _find_kaim_lib():
    """Find the KAIM shared library"""
    # Look in standard locations
    lib_paths = [
        "/usr/lib/libkaim.so",
        "/usr/local/lib/libkaim.so",
        str(Path(__file__).parent / "kernel" / "libkaim.so"),
        "./libkaim.so"
    ]
    
    for path in lib_paths:
        if os.path.exists(path):
            return path
    
    # Try system search
    lib = ctypes.util.find_library("kaim")
    if lib:
        return lib
    
    raise ImportError("Cannot find libkaim.so")

# Load library
try:
    _lib_path = _find_kaim_lib()
    _kaim_lib = ctypes.CDLL(_lib_path)
    logger.info(f"Loaded KAIM library from {_lib_path}")
except Exception as e:
    logger.warning(f"Failed to load C++ library: {e}, using kernel interface directly")
    _kaim_lib = None

# Define C structures
class KaimElevateReq(ctypes.Structure):
    _fields_ = [
        ("target_pid", ctypes.c_int),
        ("flags", ctypes.c_uint32),
        ("duration", ctypes.c_uint32)
    ]

class KaimStatus(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_char * 32),
        ("process_count", ctypes.c_uint32),
        ("device_count", ctypes.c_uint32),
        ("elevations", ctypes.c_uint64),
        ("device_opens", ctypes.c_uint64),
        ("permission_checks", ctypes.c_uint64),
        ("denials", ctypes.c_uint64)
    ]

class KaimDeviceReq(ctypes.Structure):
    _fields_ = [
        ("device", ctypes.c_char * 64),
        ("mode", ctypes.c_char * 4),
        ("fd", ctypes.c_int)
    ]

class KaimPermCheck(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("flag", ctypes.c_uint32),
        ("result", ctypes.c_int)
    ]

class KaimPermDrop(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("flag", ctypes.c_uint32)
    ]

class KaimAuditReq(ctypes.Structure):
    _fields_ = [
        ("count", ctypes.c_uint32),
        ("buffer", ctypes.c_char * 4096)
    ]

# ioctl numbers (must match kernel module)
KAIM_IOCTL_MAGIC = ord('K')

def _IOC(dir, type, nr, size):
    return (dir << 30) | (size << 16) | (type << 8) | nr

def _IOW(type, nr, size):
    return _IOC(1, type, nr, ctypes.sizeof(size))

def _IOR(type, nr, size):
    return _IOC(2, type, nr, ctypes.sizeof(size))

def _IOWR(type, nr, size):
    return _IOC(3, type, nr, ctypes.sizeof(size))

# ioctl commands
KAIM_IOCTL_ELEVATE = _IOW(KAIM_IOCTL_MAGIC, 1, KaimElevateReq)
KAIM_IOCTL_STATUS = _IOR(KAIM_IOCTL_MAGIC, 2, KaimStatus)
KAIM_IOCTL_DEVICE = _IOWR(KAIM_IOCTL_MAGIC, 4, KaimDeviceReq)
KAIM_IOCTL_CHECK_PERM = _IOR(KAIM_IOCTL_MAGIC, 5, KaimPermCheck)
KAIM_IOCTL_DROP_PERM = _IOW(KAIM_IOCTL_MAGIC, 6, KaimPermDrop)
KAIM_IOCTL_AUDIT = _IOR(KAIM_IOCTL_MAGIC, 7, KaimAuditReq)

# Permission flags
class PermissionFlags:
    KROOT = 0x00000001
    KSYSTEM = 0x00000002
    KUSR = 0x00000004
    KAM = 0x00000008
    KNET = 0x00000010
    KDEV = 0x00000020
    KPROC = 0x00000040
    KFILE_R = 0x00000080
    KFILE_W = 0x00000100
    KFILE_X = 0x00000200
    KMEM = 0x00000400
    KLOG = 0x00000800
    KSEC = 0x00001000
    KAUD = 0x00002000
    KCFG = 0x00004000
    KUPD = 0x00008000
    KSRV = 0x00010000
    KDBG = 0x00020000

# Flag name mapping
FLAG_NAMES = {
    "KROOT": PermissionFlags.KROOT,
    "KSYSTEM": PermissionFlags.KSYSTEM,
    "KUSR": PermissionFlags.KUSR,
    "KAM": PermissionFlags.KAM,
    "KNET": PermissionFlags.KNET,
    "KDEV": PermissionFlags.KDEV,
    "KPROC": PermissionFlags.KPROC,
    "KFILE_R": PermissionFlags.KFILE_R,
    "KFILE_W": PermissionFlags.KFILE_W,
    "KFILE_X": PermissionFlags.KFILE_X,
    "KMEM": PermissionFlags.KMEM,
    "KLOG": PermissionFlags.KLOG,
    "KSEC": PermissionFlags.KSEC,
    "KAUD": PermissionFlags.KAUD,
    "KCFG": PermissionFlags.KCFG,
    "KUPD": PermissionFlags.KUPD,
    "KSRV": PermissionFlags.KSRV,
    "KDBG": PermissionFlags.KDBG
}

class KAIMKernelInterface:
    """Direct kernel interface using ioctl"""
    
    def __init__(self):
        self.device_fd = -1
        self._lock = threading.Lock()
        
    def open_device(self):
        """Open /dev/kaim"""
        if self.device_fd >= 0:
            return True
            
        try:
            self.device_fd = os.open("/dev/kaim", os.O_RDWR)
            return True
        except OSError as e:
            logger.error(f"Failed to open /dev/kaim: {e}")
            return False
    
    def close_device(self):
        """Close device"""
        if self.device_fd >= 0:
            os.close(self.device_fd)
            self.device_fd = -1
    
    def elevate_process(self, target_pid: int, flags: List[str], duration: int = 900) -> bool:
        """Elevate process privileges"""
        if not self.open_device():
            return False
        
        # Convert flag names to bitmask
        flag_bits = 0
        for flag in flags:
            flag_bits |= FLAG_NAMES.get(flag, 0)
        
        req = KaimElevateReq()
        req.target_pid = target_pid
        req.flags = flag_bits
        req.duration = duration
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_ELEVATE, req)
            return True
        except OSError as e:
            logger.error(f"Elevation ioctl failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get kernel module status"""
        if not self.open_device():
            return {}
        
        status = KaimStatus()
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_STATUS, status)
            return {
                "version": status.version.decode('utf-8'),
                "process_count": status.process_count,
                "device_count": status.device_count,
                "elevations": status.elevations,
                "device_opens": status.device_opens,
                "permission_checks": status.permission_checks,
                "denials": status.denials
            }
        except OSError as e:
            logger.error(f"Status ioctl failed: {e}")
            return {}
    
    def open_device_with_check(self, device: str, mode: str) -> int:
        """Open device with permission check"""
        if not self.open_device():
            return -1
        
        req = KaimDeviceReq()
        req.device = device.encode('utf-8')
        req.mode = mode.encode('utf-8')
        req.fd = -1
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_DEVICE, req)
            return req.fd
        except OSError as e:
            logger.error(f"Device open ioctl failed: {e}")
            return -1
    
    def check_permission(self, pid: int, flag: str) -> bool:
        """Check if process has permission"""
        if not self.open_device():
            return False
        
        check = KaimPermCheck()
        check.pid = pid
        check.flag = FLAG_NAMES.get(flag, 0)
        check.result = 0
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_CHECK_PERM, check)
            return check.result != 0
        except OSError:
            return False
    
    def drop_permission(self, pid: int, flag: str) -> bool:
        """Drop permission from process"""
        if not self.open_device():
            return False
        
        drop = KaimPermDrop()
        drop.pid = pid
        drop.flag = FLAG_NAMES.get(flag, 0)
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_DROP_PERM, drop)
            return True
        except OSError:
            return False
    
    def get_audit_log(self, count: int = 100) -> List[str]:
        """Get audit log entries"""
        if not self.open_device():
            return []
        
        audit = KaimAuditReq()
        audit.count = count
        
        try:
            fcntl.ioctl(self.device_fd, KAIM_IOCTL_AUDIT, audit)
            log_data = audit.buffer.decode('utf-8', errors='ignore')
            return [line for line in log_data.split('\n') if line]
        except OSError:
            return []

# Enhanced client using both C++ library and kernel interface
class KAIMCtypesClient:
    """Production KAIM client with ctypes"""
    
    def __init__(self, app_name: str, fingerprint: str):
        self.app_name = app_name
        self.fingerprint = fingerprint
        self.kernel = KAIMKernelInterface()
        self.connected = False
        self.use_cpp_lib = _kaim_lib is not None
        
        if self.use_cpp_lib:
            self._setup_cpp_functions()
    
    def _setup_cpp_functions(self):
        """Setup C++ library function signatures"""
        # kaim_init
        _kaim_lib.kaim_init.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _kaim_lib.kaim_init.restype = ctypes.c_int
        
        # kaim_cleanup
        _kaim_lib.kaim_cleanup.argtypes = []
        _kaim_lib.kaim_cleanup.restype = None
        
        # kaim_device_open
        _kaim_lib.kaim_device_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        _kaim_lib.kaim_device_open.restype = ctypes.c_int
        
        # kaim_device_control
        _kaim_lib.kaim_device_control.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
            ctypes.c_char_p, ctypes.c_int
        ]
        _kaim_lib.kaim_device_control.restype = ctypes.c_int
        
        # kaim_process_elevate
        _kaim_lib.kaim_process_elevate.argtypes = [
            ctypes.c_int, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int
        ]
        _kaim_lib.kaim_process_elevate.restype = ctypes.c_int
        
        # kaim_get_status
        _kaim_lib.kaim_get_status.argtypes = [ctypes.c_char_p, ctypes.c_int]
        _kaim_lib.kaim_get_status.restype = ctypes.c_int
    
    def connect(self) -> bool:
        """Connect to KAIM"""
        if self.use_cpp_lib:
            # Use C++ library
            result = _kaim_lib.kaim_init(
                self.app_name.encode('utf-8'),
                self.fingerprint.encode('utf-8')
            )
            self.connected = result == 1
        else:
            # Direct kernel interface
            self.connected = self.kernel.open_device()
        
        return self.connected
    
    def disconnect(self):
        """Disconnect from KAIM"""
        if self.use_cpp_lib:
            _kaim_lib.kaim_cleanup()
        else:
            self.kernel.close_device()
        self.connected = False
    
    def device_open(self, device: str, mode: str = "r") -> int:
        """Open device"""
        if self.use_cpp_lib:
            return _kaim_lib.kaim_device_open(
                device.encode('utf-8'),
                mode.encode('utf-8')
            )
        else:
            return self.kernel.open_device_with_check(device, mode)
    
    def device_control(self, device: str, command: str,
                      params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Control device"""
        if self.use_cpp_lib:
            params_json = json.dumps(params or {})
            result_buffer = ctypes.create_string_buffer(4096)
            
            success = _kaim_lib.kaim_device_control(
                device.encode('utf-8'),
                command.encode('utf-8'),
                params_json.encode('utf-8'),
                result_buffer,
                4096
            )
            
            if success:
                try:
                    return json.loads(result_buffer.value.decode('utf-8'))
                except:
                    return {"success": "true", "raw": result_buffer.value.decode('utf-8')}
            else:
                return {"success": "false", "error": "Control failed"}
        else:
            # Direct kernel control not implemented
            return {"success": "false", "error": "Direct kernel control not available"}
    
    def process_elevate(self, pid: Optional[int] = None,
                       flags: Optional[List[str]] = None) -> bool:
        """Elevate process privileges"""
        if pid is None:
            pid = os.getpid()
        
        if not flags:
            flags = []
        
        if self.use_cpp_lib:
            # Convert Python list to C array
            flag_array = (ctypes.c_char_p * len(flags))()
            for i, flag in enumerate(flags):
                flag_array[i] = flag.encode('utf-8')
            
            return _kaim_lib.kaim_process_elevate(pid, flag_array, len(flags)) == 1
        else:
            return self.kernel.elevate_process(pid, flags)
    
    def get_status(self) -> Dict[str, Any]:
        """Get KAIM status"""
        if self.use_cpp_lib:
            status_buffer = ctypes.create_string_buffer(4096)
            
            if _kaim_lib.kaim_get_status(status_buffer, 4096):
                try:
                    return json.loads(status_buffer.value.decode('utf-8'))
                except:
                    return {}
        
        return self.kernel.get_status()
    
    def check_permission(self, flag: str, pid: Optional[int] = None) -> bool:
        """Check permission"""
        if pid is None:
            pid = os.getpid()
        
        return self.kernel.check_permission(pid, flag)
    
    def drop_permission(self, flag: str, pid: Optional[int] = None) -> bool:
        """Drop permission"""
        if pid is None:
            pid = os.getpid()
        
        return self.kernel.drop_permission(pid, flag)
    
    def get_audit_log(self, count: int = 100) -> List[str]:
        """Get audit log"""
        return self.kernel.get_audit_log(count)
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()

# High-level wrapper functions
def kaim_with_privileges(flags: List[str], duration: int = 900):
    """Decorator to run function with elevated privileges"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            client = KAIMCtypesClient("python_app", "temp_fingerprint")
            if client.connect():
                try:
                    if client.process_elevate(flags=flags):
                        return func(*args, **kwargs)
                    else:
                        raise PermissionError("Failed to elevate privileges")
                finally:
                    client.disconnect()
            else:
                raise ConnectionError("Failed to connect to KAIM")
        return wrapper
    return decorator

# Example usage functions
def test_kaim_integration():
    """Test KAIM integration"""
    client = KAIMCtypesClient("test_app", "test_fingerprint_12345")
    
    if not client.connect():
        print("Failed to connect to KAIM")
        return
    
    try:
        # Get status
        status = client.get_status()
        print(f"KAIM Status: {status}")
        
        # Check permissions
        for flag in ["KDEV", "KNET", "KPROC"]:
            has_perm = client.check_permission(flag)
            print(f"Has {flag}: {has_perm}")
        
        # Try to open a device
        fd = client.device_open("null", "r")
        print(f"Opened /dev/null: fd={fd}")
        
        # Get audit log
        audit = client.get_audit_log(10)
        print(f"Recent audit entries: {len(audit)}")
        for entry in audit:
            print(f"  {entry}")
        
    finally:
        client.disconnect()

if __name__ == "__main__":
    test_kaim_integration()
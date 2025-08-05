"""
KAIM Kernel Interface - Python implementation simulating kernel module
In production, this would be a real kernel module (kaim.ko)
"""

import os
import sys
import ctypes
import struct
import fcntl
import mmap
import threading
import time
import logging
from typing import Dict, Optional, Tuple, Any, List
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

logger = logging.getLogger('kaim.kernel')

# Simulated kernel constants
KAIM_MAJOR = 240  # Dynamic major number
KAIM_MINOR = 0

# ioctl commands
KAIM_IOCTL_MAGIC = 0x4B  # 'K'
KAIM_IOCTL_ELEVATE = (KAIM_IOCTL_MAGIC << 8) | 1
KAIM_IOCTL_STATUS = (KAIM_IOCTL_MAGIC << 8) | 2  
KAIM_IOCTL_SESSION = (KAIM_IOCTL_MAGIC << 8) | 3
KAIM_IOCTL_DEVICE = (KAIM_IOCTL_MAGIC << 8) | 4
KAIM_IOCTL_CHECK_PERM = (KAIM_IOCTL_MAGIC << 8) | 5
KAIM_IOCTL_DROP_PERM = (KAIM_IOCTL_MAGIC << 8) | 6
KAIM_IOCTL_AUDIT = (KAIM_IOCTL_MAGIC << 8) | 7


class PermissionFlags(IntEnum):
    """Kernel permission flags matching the design"""
    KROOT = 0x00000001     # Full unrestricted access
    KSYSTEM = 0x00000002   # System management
    KUSR = 0x00000004      # User management
    KAM = 0x00000008       # Access management
    KNET = 0x00000010      # Network configuration
    KDEV = 0x00000020      # Device access
    KPROC = 0x00000040     # Process management
    KFILE_R = 0x00000080   # File read access
    KFILE_W = 0x00000100   # File write access
    KFILE_X = 0x00000200   # File execute access
    KMEM = 0x00000400      # Memory management
    KLOG = 0x00000800      # Log access
    KSEC = 0x00001000      # Security subsystem
    KAUD = 0x00002000      # Audit logging
    KCFG = 0x00004000      # Configuration management
    KUPD = 0x00008000      # System update
    KSRV = 0x00010000      # Service management
    KDBG = 0x00020000      # Debugging tools


@dataclass
class ProcessInfo:
    """Process information in kernel"""
    pid: int
    uid: int
    gid: int
    flags: int = 0
    elevated_flags: int = 0
    elevated_until: float = 0
    cmdline: str = ""
    cwd: str = ""
    

@dataclass
class DeviceInfo:
    """Device information"""
    name: str
    major: int
    minor: int
    mode: int
    owner_uid: int
    owner_gid: int
    

class KAIMKernelModule:
    """
    Simulated KAIM kernel module functionality
    In production, this would be implemented in C as a real kernel module
    """
    
    def __init__(self):
        self.device_path = "/dev/kaim"
        self.proc_path = "/proc/kaim"
        self.sys_path = "/sys/module/kaim"
        
        # Process tracking
        self.processes: Dict[int, ProcessInfo] = {}
        self.process_lock = threading.RLock()
        
        # Device management
        self.devices: Dict[str, DeviceInfo] = {}
        self.device_fds: Dict[int, Tuple[str, int]] = {}  # fd -> (device, flags)
        self.next_fd = 100
        self.device_lock = threading.RLock()
        
        # Audit log
        self.audit_buffer = []
        self.audit_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "elevations": 0,
            "device_opens": 0,
            "permission_checks": 0,
            "denials": 0
        }
        
        # Initialize
        self._init_kernel_structures()
        
    def _init_kernel_structures(self):
        """Initialize kernel data structures"""
        # Track init process
        self.processes[1] = ProcessInfo(
            pid=1,
            uid=0,
            gid=0,
            flags=PermissionFlags.KROOT,
            cmdline="/sbin/init"
        )
        
        # Register standard devices
        self._register_standard_devices()
        
    def _register_standard_devices(self):
        """Register kernel-known devices"""
        devices = [
            ("null", 1, 3, 0o666, 0, 0),
            ("zero", 1, 5, 0o666, 0, 0),
            ("random", 1, 8, 0o666, 0, 0),
            ("urandom", 1, 9, 0o666, 0, 0),
            ("kmsg", 1, 11, 0o600, 0, 0),
            ("mem", 1, 1, 0o640, 0, 4),  # root:kmem
            ("sda", 8, 0, 0o660, 0, 6),   # root:disk
            ("sdb", 8, 16, 0o660, 0, 6),
        ]
        
        for name, major, minor, mode, uid, gid in devices:
            self.devices[name] = DeviceInfo(
                name=name,
                major=major,
                minor=minor,
                mode=mode,
                owner_uid=uid,
                owner_gid=gid
            )
    
    def ioctl(self, fd: int, cmd: int, arg: bytes) -> bytes:
        """Handle ioctl commands - main kernel interface"""
        
        if cmd == KAIM_IOCTL_ELEVATE:
            return self._ioctl_elevate(arg)
        elif cmd == KAIM_IOCTL_STATUS:
            return self._ioctl_status(arg)
        elif cmd == KAIM_IOCTL_SESSION:
            return self._ioctl_session(arg)
        elif cmd == KAIM_IOCTL_DEVICE:
            return self._ioctl_device(arg)
        elif cmd == KAIM_IOCTL_CHECK_PERM:
            return self._ioctl_check_perm(arg)
        elif cmd == KAIM_IOCTL_DROP_PERM:
            return self._ioctl_drop_perm(arg)
        elif cmd == KAIM_IOCTL_AUDIT:
            return self._ioctl_audit(arg)
        else:
            raise OSError(22, "Invalid ioctl command")  # EINVAL
    
    def _ioctl_elevate(self, arg: bytes) -> bytes:
        """Handle privilege elevation request"""
        if len(arg) < 8:
            raise OSError(22, "Invalid argument")
        
        target_pid, requested_flags = struct.unpack("II", arg[:8])
        
        # Get current process (would be from kernel context)
        current_pid = os.getpid()
        
        # Security checks
        with self.process_lock:
            current_proc = self.processes.get(current_pid)
            if not current_proc:
                raise OSError(1, "Permission denied")  # EPERM
            
            # Check if current process can elevate
            if not (current_proc.flags & PermissionFlags.KROOT):
                # Need at least KSYSTEM to elevate
                if not (current_proc.flags & PermissionFlags.KSYSTEM):
                    self.stats["denials"] += 1
                    self._audit_log("ELEVATE_DENIED", current_pid, 
                                  {"target": target_pid, "flags": requested_flags})
                    raise OSError(1, "Permission denied")
            
            # Get or create target process
            if target_pid not in self.processes:
                self.processes[target_pid] = ProcessInfo(
                    pid=target_pid,
                    uid=os.getuid(),
                    gid=os.getgid()
                )
            
            target_proc = self.processes[target_pid]
            
            # Apply elevation
            target_proc.elevated_flags = requested_flags
            target_proc.elevated_until = time.time() + 900  # 15 minutes
            
            self.stats["elevations"] += 1
            self._audit_log("ELEVATE_SUCCESS", current_pid,
                          {"target": target_pid, "flags": requested_flags})
        
        # Return success
        return struct.pack("i", 0)
    
    def _ioctl_status(self, arg: bytes) -> bytes:
        """Get kernel module status"""
        status_data = {
            "version": "1.0.0",
            "processes": len(self.processes),
            "devices": len(self.devices),
            "stats": self.stats
        }
        
        # Pack status into buffer
        status_str = str(status_data)[:255]
        return status_str.encode().ljust(256, b'\0')
    
    def _ioctl_session(self, arg: bytes) -> bytes:
        """Handle session management"""
        # Session info would be managed here
        # For now, return success
        return struct.pack("i", 0)
    
    def _ioctl_device(self, arg: bytes) -> bytes:
        """Handle device operations"""
        if len(arg) < 68:
            raise OSError(22, "Invalid argument")
        
        device_name = arg[:64].decode().rstrip('\0')
        mode = arg[64:68].decode().rstrip('\0')
        
        with self.device_lock:
            device = self.devices.get(device_name)
            if not device:
                return struct.pack("i", -1)  # Device not found
            
            # Check permissions
            current_pid = os.getpid()
            if not self._check_device_permission(current_pid, device, mode):
                self.stats["denials"] += 1
                self._audit_log("DEVICE_DENIED", current_pid,
                              {"device": device_name, "mode": mode})
                return struct.pack("i", -1)
            
            # "Open" device - return simulated fd
            fd = self.next_fd
            self.next_fd += 1
            
            flags = 0
            if 'r' in mode:
                flags |= os.O_RDONLY
            if 'w' in mode:
                flags |= os.O_WRONLY
            if 'rw' in mode or ('r' in mode and 'w' in mode):
                flags = os.O_RDWR
            
            self.device_fds[fd] = (device_name, flags)
            
            self.stats["device_opens"] += 1
            self._audit_log("DEVICE_OPEN", current_pid,
                          {"device": device_name, "mode": mode, "fd": fd})
        
        return struct.pack("i", fd)
    
    def _ioctl_check_perm(self, arg: bytes) -> bytes:
        """Check if process has permission"""
        if len(arg) < 8:
            raise OSError(22, "Invalid argument")
        
        pid, flag = struct.unpack("II", arg[:8])
        
        with self.process_lock:
            proc = self.processes.get(pid)
            if not proc:
                return struct.pack("i", 0)  # No permissions
            
            # Check base flags
            if proc.flags & flag:
                self.stats["permission_checks"] += 1
                return struct.pack("i", 1)
            
            # Check elevated flags
            if proc.elevated_until > time.time() and proc.elevated_flags & flag:
                self.stats["permission_checks"] += 1
                return struct.pack("i", 1)
        
        return struct.pack("i", 0)
    
    def _ioctl_drop_perm(self, arg: bytes) -> bytes:
        """Drop permissions for process"""
        if len(arg) < 8:
            raise OSError(22, "Invalid argument")
        
        pid, flag = struct.unpack("II", arg[:8])
        
        with self.process_lock:
            proc = self.processes.get(pid)
            if not proc:
                return struct.pack("i", -1)
            
            # Can only drop own permissions or with KROOT
            current_pid = os.getpid()
            current_proc = self.processes.get(current_pid)
            
            if pid != current_pid and not (current_proc and 
                                          current_proc.flags & PermissionFlags.KROOT):
                return struct.pack("i", -1)
            
            # Drop the flag
            proc.flags &= ~flag
            proc.elevated_flags &= ~flag
            
            self._audit_log("PERM_DROPPED", current_pid,
                          {"target": pid, "flag": flag})
        
        return struct.pack("i", 0)
    
    def _ioctl_audit(self, arg: bytes) -> bytes:
        """Get audit log entries"""
        with self.audit_lock:
            # Return last N entries
            entries = self.audit_buffer[-100:]  # Last 100 entries
            audit_data = "\n".join(entries)
            return audit_data.encode()[:4096]  # Max 4K
    
    def _check_device_permission(self, pid: int, device: DeviceInfo, mode: str) -> bool:
        """Check if process can access device"""
        with self.process_lock:
            proc = self.processes.get(pid)
            if not proc:
                return False
            
            # KROOT can access anything
            if proc.flags & PermissionFlags.KROOT:
                return True
            
            # Check KDEV permission
            if not (proc.flags & PermissionFlags.KDEV):
                # Check elevated
                if not (proc.elevated_until > time.time() and 
                       proc.elevated_flags & PermissionFlags.KDEV):
                    return False
            
            # Check device-specific permissions
            # Would check uid/gid and mode bits
            
        return True
    
    def _audit_log(self, action: str, pid: int, details: dict):
        """Add entry to audit log"""
        entry = f"[{time.time():.3f}] {action} pid={pid} {details}"
        
        with self.audit_lock:
            self.audit_buffer.append(entry)
            # Keep last 1000 entries
            if len(self.audit_buffer) > 1000:
                self.audit_buffer = self.audit_buffer[-1000:]
    
    def register_process(self, pid: int, uid: int, gid: int, 
                        flags: int = 0, cmdline: str = ""):
        """Register a process with the kernel module"""
        with self.process_lock:
            self.processes[pid] = ProcessInfo(
                pid=pid,
                uid=uid,
                gid=gid,
                flags=flags,
                cmdline=cmdline
            )
    
    def unregister_process(self, pid: int):
        """Remove process from tracking"""
        with self.process_lock:
            if pid in self.processes:
                del self.processes[pid]
    
    def get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """Get process information"""
        with self.process_lock:
            return self.processes.get(pid)
    
    def create_device_node(self):
        """Create /dev/kaim device node"""
        # In real implementation, this would be done by kernel
        # Here we simulate it
        device_path = Path(self.device_path)
        
        if not device_path.exists():
            # Would use mknod system call
            logger.info(f"Would create device node {self.device_path}")
            
    def proc_read_status(self) -> str:
        """Read /proc/kaim/status"""
        status = []
        status.append("KAIM Kernel Module Status")
        status.append("=" * 40)
        status.append(f"Version: 1.0.0")
        status.append(f"Processes tracked: {len(self.processes)}")
        status.append(f"Devices registered: {len(self.devices)}")
        status.append(f"Open device FDs: {len(self.device_fds)}")
        status.append("")
        status.append("Statistics:")
        for key, value in self.stats.items():
            status.append(f"  {key}: {value}")
        status.append("")
        status.append("Recent audit entries:")
        with self.audit_lock:
            for entry in self.audit_buffer[-10:]:
                status.append(f"  {entry}")
        
        return "\n".join(status)
    
    def proc_read_processes(self) -> str:
        """Read /proc/kaim/processes"""
        lines = []
        lines.append("PID\tUID\tGID\tFLAGS\tELEVATED\tCMD")
        
        with self.process_lock:
            for pid, proc in sorted(self.processes.items()):
                elevated = "Yes" if proc.elevated_until > time.time() else "No"
                lines.append(f"{pid}\t{proc.uid}\t{proc.gid}\t"
                           f"0x{proc.flags:08x}\t{elevated}\t{proc.cmdline}")
        
        return "\n".join(lines)


# Global kernel module instance (singleton)
_kernel_module: Optional[KAIMKernelModule] = None
_kernel_lock = threading.Lock()


def get_kernel_module() -> KAIMKernelModule:
    """Get the kernel module instance"""
    global _kernel_module
    
    with _kernel_lock:
        if _kernel_module is None:
            _kernel_module = KAIMKernelModule()
        return _kernel_module


# C-compatible interface functions
def kaim_kernel_ioctl(fd: int, cmd: int, arg: bytes) -> bytes:
    """Kernel ioctl interface"""
    kernel = get_kernel_module()
    return kernel.ioctl(fd, cmd, arg)


def kaim_kernel_register_process(pid: int, uid: int, gid: int, 
                                flags: int = 0, cmdline: str = "") -> int:
    """Register process with kernel"""
    kernel = get_kernel_module()
    kernel.register_process(pid, uid, gid, flags, cmdline)
    return 0


def kaim_kernel_unregister_process(pid: int) -> int:
    """Unregister process from kernel"""
    kernel = get_kernel_module()
    kernel.unregister_process(pid)
    return 0


def kaim_kernel_check_permission(pid: int, flag: int) -> bool:
    """Check if process has permission"""
    kernel = get_kernel_module()
    proc = kernel.get_process_info(pid)
    if not proc:
        return False
    
    # Check base permissions
    if proc.flags & flag:
        return True
    
    # Check elevated permissions
    if proc.elevated_until > time.time() and proc.elevated_flags & flag:
        return True
    
    return False
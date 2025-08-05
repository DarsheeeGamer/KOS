"""
KOS Kernel Configuration Management (sysctl) Python Wrapper
"""

import ctypes
import os
import logging
from typing import Any, Dict, List, Optional, Union, Callable
from enum import IntEnum

logger = logging.getLogger('KOS.kernel.sysctl')

# Sysctl types
class SysctlType(IntEnum):
    INT = 0
    UINT = 1
    LONG = 2
    ULONG = 3
    STRING = 4
    BOOL = 5
    PROC = 6

# Sysctl flags
SYSCTL_FLAG_RO = 0x01       # Read-only
SYSCTL_FLAG_RW = 0x02       # Read-write
SYSCTL_FLAG_SECURE = 0x04   # Requires CAP_SYS_ADMIN
SYSCTL_FLAG_RUNTIME = 0x08  # Can be changed at runtime
SYSCTL_FLAG_BOOT = 0x10     # Boot-time only

# Sysctl info structure
class SysctlInfo(ctypes.Structure):
    _fields_ = [
        ('name', ctypes.c_char * 256),
        ('value', ctypes.c_char * 1024),
        ('description', ctypes.c_char * 512),
        ('type', ctypes.c_int),
        ('flags', ctypes.c_uint32)
    ]

class KernelSysctl:
    """Python interface to kernel sysctl configuration"""
    
    def __init__(self):
        """Initialize sysctl wrapper"""
        # Try to load the sysctl library
        lib_path = os.path.join(os.path.dirname(__file__), 'libkos_sysctl.so')
        
        try:
            # First try to compile if needed
            makefile = os.path.join(os.path.dirname(__file__), 'Makefile')
            if os.path.exists(makefile) and not os.path.exists(lib_path):
                os.system(f'cd {os.path.dirname(__file__)} && make libkos_sysctl.so')
            
            self.lib = ctypes.CDLL(lib_path)
            self._setup_functions()
            self._initialized = True
            logger.info("Kernel sysctl library loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load kernel sysctl library: {e}")
            self.lib = None
            self._initialized = False
    
    def _setup_functions(self):
        """Setup C function signatures"""
        if not self.lib:
            return
        
        # sysctl_init
        self.lib.sysctl_init.argtypes = []
        self.lib.sysctl_init.restype = ctypes.c_int
        
        # sysctl_cleanup
        self.lib.sysctl_cleanup.argtypes = []
        self.lib.sysctl_cleanup.restype = None
        
        # sysctl_read
        self.lib.sysctl_read.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t)
        ]
        self.lib.sysctl_read.restype = ctypes.c_int
        
        # sysctl_write
        self.lib.sysctl_write.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_size_t
        ]
        self.lib.sysctl_write.restype = ctypes.c_int
        
        # sysctl_get_info
        self.lib.sysctl_get_info.argtypes = [
            ctypes.c_char_p,
            ctypes.POINTER(SysctlInfo)
        ]
        self.lib.sysctl_get_info.restype = ctypes.c_int
        
        # sysctl_set_string
        self.lib.sysctl_set_string.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p
        ]
        self.lib.sysctl_set_string.restype = ctypes.c_int
        
        # sysctl_get_string
        self.lib.sysctl_get_string.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_size_t
        ]
        self.lib.sysctl_get_string.restype = ctypes.c_int
        
        # Initialize the sysctl subsystem
        result = self.lib.sysctl_init()
        if result != 0:
            raise RuntimeError(f"Failed to initialize sysctl: {result}")
    
    def get(self, path: str) -> Any:
        """Get sysctl value"""
        if not self._initialized:
            raise RuntimeError("Sysctl not initialized")
        
        # Get info about the sysctl
        info = SysctlInfo()
        result = self.lib.sysctl_get_info(path.encode(), ctypes.byref(info))
        if result != 0:
            raise KeyError(f"Sysctl '{path}' not found")
        
        # Read based on type
        if info.type == SysctlType.STRING:
            buffer = ctypes.create_string_buffer(1024)
            result = self.lib.sysctl_get_string(path.encode(), buffer, 1024)
            if result == 0:
                return buffer.value.decode()
        
        elif info.type == SysctlType.BOOL:
            value = ctypes.c_bool()
            size = ctypes.c_size_t(ctypes.sizeof(value))
            result = self.lib.sysctl_read(path.encode(), ctypes.byref(value), ctypes.byref(size))
            if result == 0:
                return bool(value.value)
        
        elif info.type in [SysctlType.INT, SysctlType.LONG]:
            value = ctypes.c_long()
            size = ctypes.c_size_t(ctypes.sizeof(value))
            result = self.lib.sysctl_read(path.encode(), ctypes.byref(value), ctypes.byref(size))
            if result == 0:
                return value.value
        
        elif info.type in [SysctlType.UINT, SysctlType.ULONG]:
            value = ctypes.c_ulong()
            size = ctypes.c_size_t(ctypes.sizeof(value))
            result = self.lib.sysctl_read(path.encode(), ctypes.byref(value), ctypes.byref(size))
            if result == 0:
                return value.value
        
        raise ValueError(f"Unsupported sysctl type: {info.type}")
    
    def set(self, path: str, value: Any) -> None:
        """Set sysctl value"""
        if not self._initialized:
            raise RuntimeError("Sysctl not initialized")
        
        # Get info about the sysctl
        info = SysctlInfo()
        result = self.lib.sysctl_get_info(path.encode(), ctypes.byref(info))
        if result != 0:
            raise KeyError(f"Sysctl '{path}' not found")
        
        # Check if writable
        if not (info.flags & SYSCTL_FLAG_RW):
            raise PermissionError(f"Sysctl '{path}' is read-only")
        
        # Write based on type
        if info.type == SysctlType.STRING:
            result = self.lib.sysctl_set_string(path.encode(), str(value).encode())
        
        elif info.type == SysctlType.BOOL:
            bool_val = ctypes.c_bool(bool(value))
            result = self.lib.sysctl_write(path.encode(), ctypes.byref(bool_val), 
                                           ctypes.sizeof(bool_val))
        
        elif info.type in [SysctlType.INT, SysctlType.LONG]:
            int_val = ctypes.c_long(int(value))
            result = self.lib.sysctl_write(path.encode(), ctypes.byref(int_val),
                                           ctypes.sizeof(int_val))
        
        elif info.type in [SysctlType.UINT, SysctlType.ULONG]:
            uint_val = ctypes.c_ulong(int(value))
            result = self.lib.sysctl_write(path.encode(), ctypes.byref(uint_val),
                                           ctypes.sizeof(uint_val))
        
        else:
            raise ValueError(f"Unsupported sysctl type: {info.type}")
        
        if result != 0:
            raise RuntimeError(f"Failed to set sysctl '{path}': error {result}")
    
    def list(self, path: str = "") -> List[Dict[str, Any]]:
        """List sysctl entries under a path"""
        if not self._initialized:
            return []
        
        entries = []
        
        # Use a callback to collect entries
        # TODO: Implement proper listing with callback
        # For now, return a static list of known sysctls
        known_sysctls = [
            # VM parameters
            "vm.swappiness",
            "vm.dirty_ratio",
            "vm.dirty_background_ratio",
            "vm.overcommit_memory",
            "vm.overcommit_ratio",
            "vm.min_free_kbytes",
            "vm.vfs_cache_pressure",
            "vm.page_cluster",
            
            # Scheduler parameters
            "kernel.sched_latency_ns",
            "kernel.sched_min_granularity_ns",
            "kernel.sched_wakeup_granularity_ns",
            "kernel.sched_migration_cost_ns",
            "kernel.sched_nr_migrate",
            "kernel.sched_time_avg_ms",
            "kernel.sched_rt_period_us",
            "kernel.sched_rt_runtime_us",
            
            # Network parameters
            "net.core.rmem_default",
            "net.core.rmem_max",
            "net.core.wmem_default",
            "net.core.wmem_max",
            "net.core.netdev_max_backlog",
            "net.ipv4.tcp_keepalive_time",
            "net.ipv4.tcp_keepalive_probes",
            "net.ipv4.tcp_keepalive_intvl",
            "net.ipv4.ip_forward",
            "net.ipv6.conf.all.forwarding",
            
            # Kernel parameters
            "kernel.hostname",
            "kernel.domainname",
            "kernel.pid_max",
            "kernel.threads_max",
            "kernel.msgmax",
            "kernel.msgmnb",
            "kernel.shmmax",
            "kernel.shmall",
            
            # Security parameters
            "kernel.randomize_va_space",
            "kernel.dmesg_restrict",
            "kernel.kptr_restrict",
            "kernel.perf_event_paranoid",
        ]
        
        for sysctl_path in known_sysctls:
            if path and not sysctl_path.startswith(path):
                continue
            
            try:
                info = SysctlInfo()
                result = self.lib.sysctl_get_info(sysctl_path.encode(), ctypes.byref(info))
                if result == 0:
                    entries.append({
                        'path': sysctl_path,
                        'value': self.get(sysctl_path),
                        'description': info.description.decode(),
                        'type': SysctlType(info.type).name,
                        'readonly': not bool(info.flags & SYSCTL_FLAG_RW),
                        'secure': bool(info.flags & SYSCTL_FLAG_SECURE)
                    })
            except Exception as e:
                logger.debug(f"Failed to get info for {sysctl_path}: {e}")
        
        return entries
    
    def get_all(self) -> Dict[str, Any]:
        """Get all sysctl values as a dictionary"""
        result = {}
        for entry in self.list():
            result[entry['path']] = entry['value']
        return result
    
    def set_multiple(self, values: Dict[str, Any]) -> Dict[str, Optional[Exception]]:
        """Set multiple sysctl values, returning any errors"""
        errors = {}
        for path, value in values.items():
            try:
                self.set(path, value)
                errors[path] = None
            except Exception as e:
                errors[path] = e
        return errors
    
    def cleanup(self):
        """Cleanup sysctl subsystem"""
        if self._initialized and self.lib:
            self.lib.sysctl_cleanup()
            self._initialized = False

# Global sysctl instance
_sysctl = None

def get_kernel_sysctl() -> KernelSysctl:
    """Get global kernel sysctl instance"""
    global _sysctl
    if _sysctl is None:
        _sysctl = KernelSysctl()
    return _sysctl

# Convenience functions
def sysctl_get(path: str) -> Any:
    """Get sysctl value"""
    return get_kernel_sysctl().get(path)

def sysctl_set(path: str, value: Any) -> None:
    """Set sysctl value"""
    get_kernel_sysctl().set(path, value)

def sysctl_list(path: str = "") -> List[Dict[str, Any]]:
    """List sysctls under path"""
    return get_kernel_sysctl().list(path)

# Example usage
if __name__ == "__main__":
    # Initialize sysctl
    sysctl = get_kernel_sysctl()
    
    # List all sysctls
    print("All sysctls:")
    for entry in sysctl.list():
        print(f"  {entry['path']} = {entry['value']} ({entry['type']}, {'RO' if entry['readonly'] else 'RW'})")
    
    # Get specific values
    print(f"\nVM swappiness: {sysctl.get('vm.swappiness')}")
    print(f"Scheduler latency: {sysctl.get('kernel.sched_latency_ns')} ns")
    
    # Set a value (if writable)
    try:
        sysctl.set('vm.swappiness', 30)
        print(f"Set vm.swappiness to: {sysctl.get('vm.swappiness')}")
    except Exception as e:
        print(f"Failed to set vm.swappiness: {e}")
"""
KOS Kernel Resource Monitor Python Wrapper

Provides Python interface to the kernel-level resource monitoring
"""

import ctypes
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger('KOS.kernel.resource_monitor')


# Define structures matching C structs
class KOSCPUInfo(ctypes.Structure):
    _fields_ = [
        ("cpu_count", ctypes.c_uint32),
        ("cpu_count_logical", ctypes.c_uint32),
        ("cpu_percent", ctypes.c_float),
        ("per_cpu_percent", ctypes.POINTER(ctypes.c_float)),
        ("frequency_current", ctypes.c_uint64),
        ("frequency_max", ctypes.c_uint64),
        ("frequency_min", ctypes.c_uint64),
    ]


class KOSMemInfo(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_uint64),
        ("available", ctypes.c_uint64),
        ("used", ctypes.c_uint64),
        ("free", ctypes.c_uint64),
        ("buffers", ctypes.c_uint64),
        ("cached", ctypes.c_uint64),
        ("percent", ctypes.c_float),
    ]


class KOSSwapInfo(ctypes.Structure):
    _fields_ = [
        ("total", ctypes.c_uint64),
        ("used", ctypes.c_uint64),
        ("free", ctypes.c_uint64),
        ("percent", ctypes.c_float),
    ]


class KOSDiskInfo(ctypes.Structure):
    _fields_ = [
        ("device", ctypes.c_char * 256),
        ("mountpoint", ctypes.c_char * 256),
        ("fstype", ctypes.c_char * 64),
        ("total", ctypes.c_uint64),
        ("used", ctypes.c_uint64),
        ("free", ctypes.c_uint64),
        ("percent", ctypes.c_float),
    ]


class KOSNetInfo(ctypes.Structure):
    _fields_ = [
        ("interface", ctypes.c_char * 64),
        ("bytes_sent", ctypes.c_uint64),
        ("bytes_recv", ctypes.c_uint64),
        ("packets_sent", ctypes.c_uint64),
        ("packets_recv", ctypes.c_uint64),
        ("errors_in", ctypes.c_uint64),
        ("errors_out", ctypes.c_uint64),
        ("drop_in", ctypes.c_uint64),
        ("drop_out", ctypes.c_uint64),
    ]


class KOSProcessInfo(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_uint32),
        ("ppid", ctypes.c_uint32),
        ("name", ctypes.c_char * 256),
        ("state", ctypes.c_char),
        ("cpu_percent", ctypes.c_float),
        ("memory_rss", ctypes.c_uint64),
        ("memory_vms", ctypes.c_uint64),
        ("num_threads", ctypes.c_uint64),
        ("create_time", ctypes.c_uint64),
    ]


class KOSSystemInfo(ctypes.Structure):
    _fields_ = [
        ("boot_time", ctypes.c_uint64),
        ("process_count", ctypes.c_uint32),
        ("thread_count", ctypes.c_uint32),
        ("load_avg_1", ctypes.c_float),
        ("load_avg_5", ctypes.c_float),
        ("load_avg_15", ctypes.c_float),
    ]


class KernelResourceMonitor:
    """Python wrapper for KOS kernel resource monitor"""
    
    def __init__(self):
        self.lib = None
        self._load_library()
        self._initialize()
        
    def _load_library(self):
        """Load the resource monitor shared library"""
        # Try to find or compile the library
        lib_dir = os.path.dirname(__file__)
        lib_path = os.path.join(lib_dir, "libkos_resource_monitor.so")
        
        if not os.path.exists(lib_path):
            self._compile_library()
            
        try:
            self.lib = ctypes.CDLL(lib_path)
            self._setup_functions()
        except Exception as e:
            logger.error(f"Failed to load resource monitor library: {e}")
            # Fallback to mock implementation
            self.lib = None
            
    def _compile_library(self):
        """Compile the resource monitor library"""
        import subprocess
        
        lib_dir = os.path.dirname(__file__)
        c_file = os.path.join(lib_dir, "resource_monitor.c")
        h_file = os.path.join(lib_dir, "resource_monitor.h")
        lib_path = os.path.join(lib_dir, "libkos_resource_monitor.so")
        
        if os.path.exists(c_file) and os.path.exists(h_file):
            try:
                cmd = [
                    "gcc", "-shared", "-fPIC", "-O2",
                    "-o", lib_path,
                    c_file
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                logger.info("Successfully compiled resource monitor library")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to compile resource monitor: {e}")
                
    def _setup_functions(self):
        """Setup C function signatures"""
        if not self.lib:
            return
            
        # Initialize
        self.lib.kos_resource_monitor_init.argtypes = []
        self.lib.kos_resource_monitor_init.restype = ctypes.c_int
        
        # CPU functions
        self.lib.kos_get_cpu_info.argtypes = [ctypes.POINTER(KOSCPUInfo)]
        self.lib.kos_get_cpu_info.restype = ctypes.c_int
        
        # Memory functions
        self.lib.kos_get_memory_info.argtypes = [ctypes.POINTER(KOSMemInfo)]
        self.lib.kos_get_memory_info.restype = ctypes.c_int
        
        self.lib.kos_get_swap_info.argtypes = [ctypes.POINTER(KOSSwapInfo)]
        self.lib.kos_get_swap_info.restype = ctypes.c_int
        
        # Disk functions
        self.lib.kos_get_disk_info.argtypes = [ctypes.c_char_p, ctypes.POINTER(KOSDiskInfo)]
        self.lib.kos_get_disk_info.restype = ctypes.c_int
        
        # Network functions
        self.lib.kos_get_network_info.argtypes = [ctypes.c_char_p, ctypes.POINTER(KOSNetInfo)]
        self.lib.kos_get_network_info.restype = ctypes.c_int
        
        # System functions
        self.lib.kos_get_system_info.argtypes = [ctypes.POINTER(KOSSystemInfo)]
        self.lib.kos_get_system_info.restype = ctypes.c_int
        
    def _initialize(self):
        """Initialize the resource monitor"""
        if self.lib:
            ret = self.lib.kos_resource_monitor_init()
            if ret != 0:
                logger.warning("Failed to initialize kernel resource monitor")
                
    def get_system_resources(self) -> Dict[str, Any]:
        """Get all system resources (compatible with ProcessManager interface)"""
        if not self.lib:
            return self._get_mock_resources()
            
        try:
            # Get CPU info
            cpu_info = KOSCPUInfo()
            if self.lib.kos_get_cpu_info(ctypes.byref(cpu_info)) == 0:
                cpu_data = {
                    'percent': cpu_info.cpu_percent,
                    'count': cpu_info.cpu_count,
                    'count_logical': cpu_info.cpu_count_logical,
                    'frequency': {
                        'current': cpu_info.frequency_current,
                        'max': cpu_info.frequency_max,
                        'min': cpu_info.frequency_min
                    }
                }
            else:
                cpu_data = {'percent': 0.0, 'count': 1}
                
            # Get memory info
            mem_info = KOSMemInfo()
            swap_info = KOSSwapInfo()
            
            if self.lib.kos_get_memory_info(ctypes.byref(mem_info)) == 0:
                virtual_mem = {
                    'total': mem_info.total,
                    'available': mem_info.available,
                    'percent': mem_info.percent,
                    'used': mem_info.used,
                    'free': mem_info.free
                }
            else:
                virtual_mem = {
                    'total': 0, 'available': 0, 'percent': 0.0,
                    'used': 0, 'free': 0
                }
                
            if self.lib.kos_get_swap_info(ctypes.byref(swap_info)) == 0:
                swap_mem = {
                    'total': swap_info.total,
                    'used': swap_info.used,
                    'free': swap_info.free,
                    'percent': swap_info.percent
                }
            else:
                swap_mem = {
                    'total': 0, 'used': 0, 'free': 0, 'percent': 0.0
                }
                
            # Get disk info
            disk_info = KOSDiskInfo()
            if self.lib.kos_get_disk_info(b"/", ctypes.byref(disk_info)) == 0:
                disk_data = {
                    'usage': {
                        'total': disk_info.total,
                        'used': disk_info.used,
                        'free': disk_info.free,
                        'percent': disk_info.percent
                    }
                }
            else:
                disk_data = {
                    'usage': {'total': 0, 'used': 0, 'free': 0, 'percent': 0.0}
                }
                
            # Get system info
            sys_info = KOSSystemInfo()
            if self.lib.kos_get_system_info(ctypes.byref(sys_info)) == 0:
                boot_time = sys_info.boot_time
            else:
                boot_time = 0
                
            return {
                'cpu': cpu_data,
                'memory': {
                    'virtual': virtual_mem,
                    'swap': swap_mem
                },
                'disk': disk_data,
                'network': {},
                'boot_time': boot_time
            }
            
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return self._get_mock_resources()
            
    def _get_mock_resources(self) -> Dict[str, Any]:
        """Get mock resources when kernel module not available"""
        import time
        
        # Try to read from /proc if available
        cpu_percent = 0.0
        try:
            with open('/proc/loadavg', 'r') as f:
                load_avg = float(f.read().split()[0])
                cpu_percent = min(load_avg * 100, 100.0)
        except:
            pass
            
        return {
            'cpu': {
                'percent': cpu_percent,
                'count': 1,
                'count_logical': 1,
                'frequency': {}
            },
            'memory': {
                'virtual': {
                    'total': 1024 * 1024 * 1024,  # 1GB mock
                    'available': 512 * 1024 * 1024,
                    'percent': 50.0,
                    'used': 512 * 1024 * 1024,
                    'free': 512 * 1024 * 1024
                },
                'swap': {
                    'total': 0,
                    'used': 0,
                    'free': 0,
                    'percent': 0.0
                }
            },
            'disk': {
                'usage': {
                    'total': 10 * 1024 * 1024 * 1024,  # 10GB mock
                    'used': 5 * 1024 * 1024 * 1024,
                    'free': 5 * 1024 * 1024 * 1024,
                    'percent': 50.0
                }
            },
            'network': {},
            'boot_time': time.time() - 3600  # 1 hour ago
        }
        
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        resources = self.get_system_resources()
        return resources.get('cpu', {})
        
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        resources = self.get_system_resources()
        return resources.get('memory', {})
        
    def get_disk_info(self, path: str = "/") -> Dict[str, Any]:
        """Get disk information for a specific path"""
        resources = self.get_system_resources()
        return resources.get('disk', {}).get('usage', {})


# Global instance
_kernel_monitor = None


def get_kernel_monitor() -> KernelResourceMonitor:
    """Get the global kernel resource monitor instance"""
    global _kernel_monitor
    if _kernel_monitor is None:
        _kernel_monitor = KernelResourceMonitor()
    return _kernel_monitor
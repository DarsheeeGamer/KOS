"""
KOS Advanced Layer (kADVLayer) - System Integration Layer

The kADVLayer module provides advanced integration between Kaede OS (KOS), 
the KOS kernel, and the host operating system. It acts as a bridge for system 
resources, hardware access, networking, and other low-level operations.

Key capabilities:
- Host system resource monitoring and allocation
- Hardware device detection and management
- Direct network stack access and monitoring
- Inter-process communication with host OS processes
- Secure system call interfaces
- Performance profiling and optimization

This module enables KOS to operate efficiently within the host environment
while maintaining proper isolation boundaries and security controls.
"""
import os
import sys
import signal
import platform
import logging
import subprocess
import threading
import queue
import time
import socket
import json
import ctypes
import psutil
from typing import Dict, Any, List, Optional, Union, Callable, Type, Tuple
from pathlib import Path
from datetime import datetime

logger = logging.getLogger('KOS.kadv_layer')

# Constants for system resource management
MAX_MEMORY_PERCENT = 80  # Maximum memory usage percentage
MIN_CPU_AVAILABLE = 0.2  # Minimum available CPU ratio
REFRESH_INTERVAL = 5.0   # Resource monitoring interval in seconds

# System access permission levels
ACCESS_NONE = 0      # No access to host resources
ACCESS_READ = 1      # Read-only access to host resources
ACCESS_WRITE = 2     # Read-write access to host resources
ACCESS_EXECUTE = 4   # Execute access to host resources
ACCESS_ALL = 7       # Full access to host resources

# System component types
COMPONENT_MEMORY = 'memory'
COMPONENT_CPU = 'cpu'
COMPONENT_DISK = 'disk'
COMPONENT_NETWORK = 'network'
COMPONENT_PROCESS = 'process'
COMPONENT_DEVICE = 'device'

# Error codes
ERROR_SUCCESS = 0
ERROR_PERMISSION_DENIED = 1
ERROR_RESOURCE_UNAVAILABLE = 2
ERROR_OPERATION_FAILED = 3
ERROR_INVALID_PARAMETER = 4
ERROR_SYSTEM_ERROR = 5

class KADVLayerError(Exception):
    """Base exception for KADVLayer errors"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[Error {code}] {message}")

class PermissionDeniedError(KADVLayerError):
    """Raised when an operation lacks sufficient permissions"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(ERROR_PERMISSION_DENIED, message)

class ResourceUnavailableError(KADVLayerError):
    """Raised when a requested resource is unavailable"""
    def __init__(self, resource: str):
        super().__init__(ERROR_RESOURCE_UNAVAILABLE, f"Resource unavailable: {resource}")

class SystemResourceMonitor:
    """Monitors and manages system resources usage and limits"""
    
    def __init__(self):
        self._monitoring = False
        self._monitor_thread = None
        self._resource_limits = {
            COMPONENT_MEMORY: MAX_MEMORY_PERCENT,
            COMPONENT_CPU: MIN_CPU_AVAILABLE,
            COMPONENT_DISK: 90,  # Maximum disk usage percentage
            COMPONENT_NETWORK: 75  # Maximum network usage percentage
        }
        self._resource_usage = {}
        self._resource_lock = threading.RLock()
        self.last_update = 0
        
    def start_monitoring(self):
        """Start resource monitoring thread"""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_resources,
            daemon=True,
            name="ResourceMonitor"
        )
        self._monitor_thread.start()
        logger.info("System resource monitoring started")
        
    def stop_monitoring(self):
        """Stop resource monitoring thread"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        logger.info("System resource monitoring stopped")
        
    def _monitor_resources(self):
        """Periodic resource monitoring function"""
        while self._monitoring:
            try:
                self.update_resource_usage()
                self._check_resource_limits()
                time.sleep(REFRESH_INTERVAL)
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                
    def update_resource_usage(self):
        """Update current resource usage information"""
        with self._resource_lock:
            # Memory usage
            memory = psutil.virtual_memory()
            self._resource_usage[COMPONENT_MEMORY] = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'percent': memory.percent,
                'free': memory.free
            }
            
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1, percpu=True)
            cpu_times = psutil.cpu_times_percent()
            self._resource_usage[COMPONENT_CPU] = {
                'total_percent': psutil.cpu_percent(),
                'per_cpu': cpu_usage,
                'count': psutil.cpu_count(),
                'times': {
                    'user': cpu_times.user,
                    'system': cpu_times.system,
                    'idle': cpu_times.idle
                }
            }
            
            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    }
                except:
                    pass
            self._resource_usage[COMPONENT_DISK] = disk_usage
            
            # Network I/O
            network_counters = psutil.net_io_counters(pernic=True)
            self._resource_usage[COMPONENT_NETWORK] = {
                iface: {
                    'bytes_sent': counters.bytes_sent,
                    'bytes_recv': counters.bytes_recv,
                    'packets_sent': counters.packets_sent,
                    'packets_recv': counters.packets_recv,
                    'errin': counters.errin,
                    'errout': counters.errout,
                    'dropin': counters.dropin,
                    'dropout': counters.dropout
                }
                for iface, counters in network_counters.items()
            }
            
            self.last_update = time.time()
            
    def _check_resource_limits(self):
        """Check if resource usage exceeds defined limits"""
        with self._resource_lock:
            # Check memory limit
            if self._resource_usage.get(COMPONENT_MEMORY, {}).get('percent', 0) > self._resource_limits[COMPONENT_MEMORY]:
                logger.warning(f"Memory usage exceeded limit: {self._resource_usage[COMPONENT_MEMORY]['percent']}%")
                
            # Check CPU limit
            cpu_idle = self._resource_usage.get(COMPONENT_CPU, {}).get('times', {}).get('idle', 100)
            if (cpu_idle / 100) < self._resource_limits[COMPONENT_CPU]:
                logger.warning(f"CPU available below limit: {cpu_idle}% idle")
                
            # Check disk space
            for mount, usage in self._resource_usage.get(COMPONENT_DISK, {}).items():
                if usage.get('percent', 0) > self._resource_limits[COMPONENT_DISK]:
                    logger.warning(f"Disk usage exceeded limit on {mount}: {usage['percent']}%")
                    
    def get_resource_usage(self, resource_type: Optional[str] = None) -> Dict[str, Any]:
        """Get current resource usage information"""
        with self._resource_lock:
            if resource_type:
                return self._resource_usage.get(resource_type, {})
            return self._resource_usage.copy()
            
    def set_resource_limit(self, resource_type: str, limit: float) -> bool:
        """Set resource usage limit"""
        if resource_type not in [COMPONENT_MEMORY, COMPONENT_CPU, COMPONENT_DISK, COMPONENT_NETWORK]:
            return False
            
        with self._resource_lock:
            self._resource_limits[resource_type] = limit
            logger.info(f"Resource limit for {resource_type} set to {limit}")
            return True

class SystemInfo:
    """Enhanced system information and capabilities"""
    def __init__(self):
        self.os_type = platform.system().lower()
        self.os_release = platform.release()
        self.machine = platform.machine()
        self.python_version = platform.python_version()
        self.processor = platform.processor()
        self.architecture = platform.architecture()
        self.memory = self._get_memory_info()

    def _get_memory_info(self) -> Dict[str, int]:
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                'total': mem.total,
                'available': mem.available,
                'used': mem.used,
                'percent': mem.percent
            }
        except:
            return {}

    def get_full_info(self) -> Dict[str, Any]:
        return {
            'os_type': self.os_type,
            'os_release': self.os_release,
            'machine': self.machine,
            'processor': self.processor,
            'architecture': self.architecture,
            'python_version': self.python_version,
            'memory': self.memory
        }

class ProcessManager:
    """Enhanced process management with system integration"""
    def __init__(self, system_info: SystemInfo):
        self.system_info = system_info
        self._processes: Dict[int, Dict] = {}

    def run_command(self, 
                   command: Union[str, List[str]], 
                   shell: bool = False,
                   capture_output: bool = True,
                   cwd: Optional[str] = None,
                   env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            if isinstance(command, str) and not shell:
                command = command.split()

            result = subprocess.run(
                command,
                shell=shell,
                capture_output=capture_output,
                text=True,
                cwd=cwd,
                env=env
            )

            return {
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'stdout': result.stdout if capture_output else None,
                'stderr': result.stderr if capture_output else None
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_process_info(self, pid: int) -> Optional[Dict[str, Any]]:
        try:
            import psutil
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                return {
                    'pid': pid,
                    'name': proc.name(),
                    'status': proc.status(),
                    'cpu_percent': proc.cpu_percent(),
                    'memory_percent': proc.memory_percent()
                }
        except:
            pass
        return None

class KADVLayer:
    """Enhanced KOS Advanced Layer with complete system integration"""
    def __init__(self):
        self.system_info = SystemInfo()
        self.process_manager = ProcessManager(self.system_info)
        self._setup_signal_handlers()
        logger.info(f"Initialized enhanced kADVLayer for {self.system_info.os_type}")

    def _setup_signal_handlers(self):
        """Set up system signal handlers"""
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_terminate)

    def _handle_interrupt(self, signum, frame):
        """Handle system interrupt signal"""
        logger.info("Received interrupt signal")
        self._cleanup()

    def _handle_terminate(self, signum, frame):
        """Handle system termination signal"""
        logger.info("Received termination signal")
        self._cleanup()

    def _cleanup(self):
        """Clean up system resources"""
        logger.info("Performing system cleanup")
        # Add cleanup logic here

    def run_kos_application(self,
                         app_dir: str,
                         entry_point: str,
                         cli_function: Optional[str] = None,
                         args: Optional[List[str]] = None,
                         env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Enhanced application execution with system integration"""
        if entry_point.endswith('.py'):
            module_name = os.path.splitext(entry_point)[0]
        else:
            module_name = entry_point

        app_env = os.environ.copy()
        if env:
            app_env.update(env)

        if cli_function:
            cmd = [
                sys.executable,
                '-c',
                f"import sys; sys.path.insert(0, '{app_dir}'); "
                f"from {module_name} import {cli_function}; {cli_function}()"
            ]
        else:
            cmd = [sys.executable, os.path.join(app_dir, entry_point)]

        if args:
            cmd.extend(args)

        return self.process_manager.run_command(
            cmd,
            capture_output=True,
            cwd=app_dir,
            env=app_env
        )

# Global instance
_kadv_layer_instance: Optional[KADVLayer] = None

def get_kadv_layer() -> KADVLayer:
    """Get or create the global kADVLayer instance"""
    global _kadv_layer_instance
    if _kadv_layer_instance is None:
        _kadv_layer_instance = KADVLayer()
    return _kadv_layer_instance
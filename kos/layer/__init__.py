"""
KLayer - KOS Application Layer

This module provides the interface between KOS applications and the KOS system,
enabling applications to control and manipulate KOS functionality with comprehensive
kernel-level capabilities.
"""

import os
import sys
import logging
import threading
import time
import json
import hashlib
import weakref
import gc
from typing import Dict, List, Any, Optional, Union, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Setup logging
logger = logging.getLogger('KOS.layer')

class ResourceType(Enum):
    """Types of system resources"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    GPU = "gpu"
    FILE_HANDLE = "file_handle"
    PROCESS = "process"
    THREAD = "thread"

class PermissionLevel(Enum):
    """Permission levels for operations"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    KERNEL = "kernel"

@dataclass
class ResourceQuota:
    """Resource quota definition"""
    resource_type: ResourceType
    limit: int
    current_usage: int = 0
    warning_threshold: float = 0.8
    hard_limit: bool = True

@dataclass
class SystemCall:
    """System call representation"""
    name: str
    pid: int
    timestamp: float
    args: List[Any] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    duration: float = 0.0

class KernelInterface:
    """Low-level kernel interface for direct system operations"""
    
    def __init__(self):
        self.syscall_table = {}
        self.interrupt_handlers = {}
        self.device_drivers = {}
        self.memory_manager = None
        self.process_scheduler = None
        self.file_system = None
        self.lock = threading.RLock()
        
        self._init_syscall_table()
        
    def _init_syscall_table(self):
        """Initialize system call table with kernel functions"""
        self.syscall_table.update({
            0: self._sys_read,
            1: self._sys_write,
            2: self._sys_open,
            3: self._sys_close,
            4: self._sys_stat,
            5: self._sys_fstat,
            6: self._sys_lstat,
            7: self._sys_poll,
            8: self._sys_lseek,
            9: self._sys_mmap,
            10: self._sys_mprotect,
            11: self._sys_munmap,
            12: self._sys_brk,
            13: self._sys_rt_sigaction,
            14: self._sys_rt_sigprocmask,
            15: self._sys_rt_sigreturn,
            16: self._sys_ioctl,
            17: self._sys_pread64,
            18: self._sys_pwrite64,
            19: self._sys_readv,
            20: self._sys_writev,
            21: self._sys_access,
            22: self._sys_pipe,
            23: self._sys_select,
            24: self._sys_sched_yield,
            25: self._sys_mremap,
            26: self._sys_msync,
            27: self._sys_mincore,
            28: self._sys_madvise,
            29: self._sys_shmget,
            30: self._sys_shmat,
            31: self._sys_shmctl,
            32: self._sys_dup,
            33: self._sys_dup2,
            34: self._sys_pause,
            35: self._sys_nanosleep,
            36: self._sys_getitimer,
            37: self._sys_alarm,
            38: self._sys_setitimer,
            39: self._sys_getpid,
            40: self._sys_sendfile,
            41: self._sys_socket,
            42: self._sys_connect,
            43: self._sys_accept,
            44: self._sys_sendto,
            45: self._sys_recvfrom,
            46: self._sys_sendmsg,
            47: self._sys_recvmsg,
            48: self._sys_shutdown,
            49: self._sys_bind,
            50: self._sys_listen,
            51: self._sys_getsockname,
            52: self._sys_getpeername,
            53: self._sys_socketpair,
            54: self._sys_setsockopt,
            55: self._sys_getsockopt,
            56: self._sys_clone,
            57: self._sys_fork,
            58: self._sys_vfork,
            59: self._sys_execve,
            60: self._sys_exit,
            61: self._sys_wait4,
            62: self._sys_kill,
            63: self._sys_uname,
            64: self._sys_semget,
            65: self._sys_semop,
            66: self._sys_semctl,
            67: self._sys_shmdt,
            68: self._sys_msgget,
            69: self._sys_msgsnd,
            70: self._sys_msgrcv,
            71: self._sys_msgctl,
            72: self._sys_fcntl,
            73: self._sys_flock,
            74: self._sys_fsync,
            75: self._sys_fdatasync,
            76: self._sys_truncate,
            77: self._sys_ftruncate,
            78: self._sys_getdents,
            79: self._sys_getcwd,
            80: self._sys_chdir,
            81: self._sys_fchdir,
            82: self._sys_rename,
            83: self._sys_mkdir,
            84: self._sys_rmdir,
            85: self._sys_creat,
            86: self._sys_link,
            87: self._sys_unlink,
            88: self._sys_symlink,
            89: self._sys_readlink,
            90: self._sys_chmod,
            91: self._sys_fchmod,
            92: self._sys_chown,
            93: self._sys_fchown,
            94: self._sys_lchown,
            95: self._sys_umask,
            96: self._sys_gettimeofday,
            97: self._sys_getrlimit,
            98: self._sys_getrusage,
            99: self._sys_sysinfo,
            100: self._sys_times,
        })
        
    def system_call(self, syscall_num: int, *args) -> Any:
        """Execute a system call"""
        start_time = time.time()
        syscall = SystemCall(
            name=f"syscall_{syscall_num}",
            pid=os.getpid(),
            timestamp=start_time,
            args=list(args)
        )
        
        try:
            if syscall_num in self.syscall_table:
                result = self.syscall_table[syscall_num](*args)
                syscall.result = result
                syscall.duration = time.time() - start_time
                return result
            else:
                error = f"Unknown system call: {syscall_num}"
                syscall.error = error
                raise OSError(error)
        except Exception as e:
            syscall.error = str(e)
            syscall.duration = time.time() - start_time
            raise
        finally:
            # Log system call for audit
            logger.debug(f"Syscall {syscall_num}: {syscall.duration:.6f}s")
    
    # System call implementations
    def _sys_read(self, fd: int, count: int) -> bytes:
        """Read from file descriptor"""
        try:
            if hasattr(self, 'file_system') and self.file_system:
                return self.file_system.read_fd(fd, count)
            return b""
        except Exception as e:
            raise OSError(f"read failed: {e}")
    
    def _sys_write(self, fd: int, data: bytes) -> int:
        """Write to file descriptor"""
        try:
            if hasattr(self, 'file_system') and self.file_system:
                return self.file_system.write_fd(fd, data)
            return len(data)
        except Exception as e:
            raise OSError(f"write failed: {e}")
    
    def _sys_open(self, path: str, flags: int, mode: int = 0o644) -> int:
        """Open file and return file descriptor"""
        try:
            if hasattr(self, 'file_system') and self.file_system:
                return self.file_system.open(path, flags, mode)
            return 3  # Mock fd
        except Exception as e:
            raise OSError(f"open failed: {e}")
    
    def _sys_close(self, fd: int) -> int:
        """Close file descriptor"""
        try:
            if hasattr(self, 'file_system') and self.file_system:
                return self.file_system.close(fd)
            return 0
        except Exception as e:
            raise OSError(f"close failed: {e}")
    
    def _sys_getpid(self) -> int:
        """Get process ID"""
        return os.getpid()
    
    def _sys_fork(self) -> int:
        """Fork process"""
        # Simplified fork implementation
        return 0  # Child process would return 0
    
    def _sys_execve(self, filename: str, argv: List[str], envp: List[str]) -> int:
        """Execute program"""
        try:
            if hasattr(self, 'process_scheduler') and self.process_scheduler:
                return self.process_scheduler.execve(filename, argv, envp)
            return 0
        except Exception as e:
            raise OSError(f"execve failed: {e}")
    
    def _sys_exit(self, status: int) -> None:
        """Exit process"""
        sys.exit(status)
    
    def _sys_kill(self, pid: int, sig: int) -> int:
        """Send signal to process"""
        try:
            if hasattr(self, 'process_scheduler') and self.process_scheduler:
                return self.process_scheduler.kill(pid, sig)
            return 0
        except Exception as e:
            raise OSError(f"kill failed: {e}")
    
    # Placeholder implementations for other syscalls
    def _sys_stat(self, *args): return 0
    def _sys_fstat(self, *args): return 0
    def _sys_lstat(self, *args): return 0
    def _sys_poll(self, *args): return 0
    def _sys_lseek(self, *args): return 0
    def _sys_mmap(self, *args): return 0
    def _sys_mprotect(self, *args): return 0
    def _sys_munmap(self, *args): return 0
    def _sys_brk(self, *args): return 0
    def _sys_rt_sigaction(self, *args): return 0
    def _sys_rt_sigprocmask(self, *args): return 0
    def _sys_rt_sigreturn(self, *args): return 0
    def _sys_ioctl(self, *args): return 0
    def _sys_pread64(self, *args): return b""
    def _sys_pwrite64(self, *args): return 0
    def _sys_readv(self, *args): return b""
    def _sys_writev(self, *args): return 0
    def _sys_access(self, *args): return 0
    def _sys_pipe(self, *args): return [3, 4]
    def _sys_select(self, *args): return 0
    def _sys_sched_yield(self, *args): return 0
    def _sys_mremap(self, *args): return 0
    def _sys_msync(self, *args): return 0
    def _sys_mincore(self, *args): return 0
    def _sys_madvise(self, *args): return 0
    def _sys_shmget(self, *args): return 0
    def _sys_shmat(self, *args): return 0
    def _sys_shmctl(self, *args): return 0
    def _sys_dup(self, *args): return 0
    def _sys_dup2(self, *args): return 0
    def _sys_pause(self, *args): return 0
    def _sys_nanosleep(self, *args): return 0
    def _sys_getitimer(self, *args): return 0
    def _sys_alarm(self, *args): return 0
    def _sys_setitimer(self, *args): return 0
    def _sys_sendfile(self, *args): return 0
    def _sys_socket(self, *args): return 3
    def _sys_connect(self, *args): return 0
    def _sys_accept(self, *args): return 4
    def _sys_sendto(self, *args): return 0
    def _sys_recvfrom(self, *args): return b""
    def _sys_sendmsg(self, *args): return 0
    def _sys_recvmsg(self, *args): return b""
    def _sys_shutdown(self, *args): return 0
    def _sys_bind(self, *args): return 0
    def _sys_listen(self, *args): return 0
    def _sys_getsockname(self, *args): return ""
    def _sys_getpeername(self, *args): return ""
    def _sys_socketpair(self, *args): return [3, 4]
    def _sys_setsockopt(self, *args): return 0
    def _sys_getsockopt(self, *args): return ""
    def _sys_clone(self, *args): return 0
    def _sys_vfork(self, *args): return 0
    def _sys_wait4(self, *args): return 0
    def _sys_uname(self, *args): return {"sysname": "KOS", "release": "1.0.0"}
    def _sys_semget(self, *args): return 0
    def _sys_semop(self, *args): return 0
    def _sys_semctl(self, *args): return 0
    def _sys_shmdt(self, *args): return 0
    def _sys_msgget(self, *args): return 0
    def _sys_msgsnd(self, *args): return 0
    def _sys_msgrcv(self, *args): return b""
    def _sys_msgctl(self, *args): return 0
    def _sys_fcntl(self, *args): return 0
    def _sys_flock(self, *args): return 0
    def _sys_fsync(self, *args): return 0
    def _sys_fdatasync(self, *args): return 0
    def _sys_truncate(self, *args): return 0
    def _sys_ftruncate(self, *args): return 0
    def _sys_getdents(self, *args): return []
    def _sys_getcwd(self, *args): return "/"
    def _sys_chdir(self, *args): return 0
    def _sys_fchdir(self, *args): return 0
    def _sys_rename(self, *args): return 0
    def _sys_mkdir(self, *args): return 0
    def _sys_rmdir(self, *args): return 0
    def _sys_creat(self, *args): return 3
    def _sys_link(self, *args): return 0
    def _sys_unlink(self, *args): return 0
    def _sys_symlink(self, *args): return 0
    def _sys_readlink(self, *args): return ""
    def _sys_chmod(self, *args): return 0
    def _sys_fchmod(self, *args): return 0
    def _sys_chown(self, *args): return 0
    def _sys_fchown(self, *args): return 0
    def _sys_lchown(self, *args): return 0
    def _sys_umask(self, *args): return 0o022
    def _sys_gettimeofday(self, *args): return time.time()
    def _sys_getrlimit(self, *args): return 0
    def _sys_getrusage(self, *args): return {}
    def _sys_sysinfo(self, *args): return {}
    def _sys_times(self, *args): return {}

class ResourceManager:
    """Manage system resources and quotas"""
    
    def __init__(self):
        self.quotas: Dict[str, Dict[ResourceType, ResourceQuota]] = defaultdict(dict)
        self.resource_usage: Dict[ResourceType, Dict[str, int]] = defaultdict(dict)
        self.resource_pools: Dict[ResourceType, int] = {}
        self.lock = threading.RLock()
        
        # Initialize default resource pools
        self._init_resource_pools()
    
    def _init_resource_pools(self):
        """Initialize resource pools with default limits"""
        self.resource_pools.update({
            ResourceType.CPU: 100,  # 100% CPU
            ResourceType.MEMORY: 8 * 1024 * 1024 * 1024,  # 8GB
            ResourceType.DISK: 100 * 1024 * 1024 * 1024,  # 100GB  
            ResourceType.NETWORK: 1000 * 1024 * 1024,  # 1GB/s
            ResourceType.FILE_HANDLE: 1024,
            ResourceType.PROCESS: 1000,
            ResourceType.THREAD: 10000,
        })
    
    def set_quota(self, user_id: str, resource_type: ResourceType, limit: int, 
                  warning_threshold: float = 0.8, hard_limit: bool = True):
        """Set resource quota for user"""
        with self.lock:
            quota = ResourceQuota(
                resource_type=resource_type,
                limit=limit,
                warning_threshold=warning_threshold,
                hard_limit=hard_limit
            )
            self.quotas[user_id][resource_type] = quota
    
    def allocate_resource(self, user_id: str, resource_type: ResourceType, amount: int) -> bool:
        """Allocate resource to user"""
        with self.lock:
            # Check user quota
            if user_id in self.quotas and resource_type in self.quotas[user_id]:
                quota = self.quotas[user_id][resource_type]
                current_usage = self.resource_usage[resource_type].get(user_id, 0)
                
                if quota.hard_limit and current_usage + amount > quota.limit:
                    return False
                
                # Check warning threshold
                if current_usage + amount > quota.limit * quota.warning_threshold:
                    logger.warning(f"User {user_id} approaching {resource_type.value} limit")
            
            # Check global pool
            total_allocated = sum(self.resource_usage[resource_type].values())
            if total_allocated + amount > self.resource_pools[resource_type]:
                return False
            
            # Allocate resource
            self.resource_usage[resource_type][user_id] = \
                self.resource_usage[resource_type].get(user_id, 0) + amount
            
            return True
    
    def release_resource(self, user_id: str, resource_type: ResourceType, amount: int):
        """Release resource from user"""
        with self.lock:
            current = self.resource_usage[resource_type].get(user_id, 0)
            self.resource_usage[resource_type][user_id] = max(0, current - amount)
    
    def get_usage_stats(self, user_id: str = None) -> Dict[str, Any]:
        """Get resource usage statistics"""
        with self.lock:
            if user_id:
                return {
                    resource_type.value: self.resource_usage[resource_type].get(user_id, 0)
                    for resource_type in ResourceType
                }
            else:
                return {
                    resource_type.value: dict(self.resource_usage[resource_type])
                    for resource_type in ResourceType
                }

class SecurityManager:
    """Manage security policies and access control"""
    
    def __init__(self):
        self.permissions: Dict[str, Set[str]] = defaultdict(set)
        self.security_contexts: Dict[str, Dict[str, Any]] = {}
        self.audit_log: List[Dict[str, Any]] = []
        self.lock = threading.RLock()
        
        # Initialize default permissions
        self._init_default_permissions()
    
    def _init_default_permissions(self):
        """Initialize default permission sets"""
        self.permissions.update({
            "admin": {
                "kernel.all", "system.all", "user.all", "network.all", 
                "file.all", "process.all", "memory.all"
            },
            "user": {
                "file.read", "file.write", "process.create", "process.signal",
                "network.connect", "memory.allocate"
            },
            "guest": {
                "file.read", "process.view"
            }
        })
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission"""
        with self.lock:
            # Get user's role/permissions
            user_perms = self.permissions.get(user_id, set())
            
            # Check exact permission
            if permission in user_perms:
                return True
            
            # Check wildcard permissions
            perm_parts = permission.split('.')
            for i in range(len(perm_parts)):
                wildcard = '.'.join(perm_parts[:i+1]) + '.all'
                if wildcard in user_perms:
                    return True
            
            return False
    
    def grant_permission(self, user_id: str, permission: str):
        """Grant permission to user"""
        with self.lock:
            self.permissions[user_id].add(permission)
            self._audit_log("GRANT_PERMISSION", user_id, {"permission": permission})
    
    def revoke_permission(self, user_id: str, permission: str):
        """Revoke permission from user"""
        with self.lock:
            self.permissions[user_id].discard(permission)
            self._audit_log("REVOKE_PERMISSION", user_id, {"permission": permission})
    
    def set_security_context(self, user_id: str, context: Dict[str, Any]):
        """Set security context for user"""
        with self.lock:
            self.security_contexts[user_id] = context
            self._audit_log("SET_CONTEXT", user_id, {"context": context})
    
    def _audit_log(self, action: str, user_id: str, details: Dict[str, Any]):
        """Log security event"""
        entry = {
            "timestamp": time.time(),
            "action": action,
            "user_id": user_id,
            "details": details
        }
        self.audit_log.append(entry)
        
        # Keep only last 10000 entries
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]

class KLayer:
    """
    Main class for the KOS Application Layer (KLayer)
    
    This class provides the comprehensive interface between KOS applications and the KOS system,
    enabling applications to control and utilize all KOS functionality with kernel-level access.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls) -> 'KLayer':
        """Get singleton instance of KLayer"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """Initialize the comprehensive KLayer"""
        # Core components
        self.kernel_interface = KernelInterface()
        self.resource_manager = ResourceManager()
        self.security_manager = SecurityManager()
        
        # System managers
        self.app_manager = None
        self.package_manager = None
        self.file_system = None
        self.virtual_fs = None
        self.memory_manager = None
        self.shell = None
        self.permissions = None
        self.app_registry = None
        self.process_manager = None
        self.network_manager = None
        
        # Advanced features
        self.event_system = EventSystem()
        self.ipc_manager = IPCManager()
        self.device_manager = DeviceManager()
        self.scheduler = TaskScheduler()
        
        # Performance monitoring
        self.performance_monitor = PerformanceMonitor()
        self.statistics = SystemStatistics()
        
        # Threading
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.async_executor = ProcessPoolExecutor(max_workers=5)
        
        # Initialize components
        self._init_components()
        
        logger.info("KLayer initialized with comprehensive kernel functionality")
    
    def _init_components(self):
        """Initialize KLayer components with error handling"""
        components = [
            ("AppManager", "app_manager", ".app_manager", "AppManager"),
            ("FileSystemInterface", "file_system", ".file_system", "FileSystemInterface"),
            ("VirtualFS", "virtual_fs", ".virtual_fs", "virtual_fs"),
            ("MemoryManager", "memory_manager", ".memory_manager", "memory_manager"),
            ("ShellInterface", "shell", ".shell", "ShellInterface"),
            ("PermissionsManager", "permissions", ".permissions", "PermissionsManager"),
            ("AppRegistry", "app_registry", ".app_registry", "AppRegistry"),
        ]
        
        for name, attr, module, class_name in components:
            try:
                module_obj = __import__(f"kos.layer{module}", fromlist=[class_name])
                component = getattr(module_obj, class_name)
                if callable(component):
                    setattr(self, attr, component())
                else:
                    setattr(self, attr, component)
            except ImportError as e:
                logger.warning(f"{name} component not available: {e}")
                setattr(self, attr, None)
    
    # System call interface
    def syscall(self, syscall_num: int, *args) -> Any:
        """Execute system call through kernel interface"""
        return self.kernel_interface.system_call(syscall_num, *args)
    
    # Resource management
    def allocate_resource(self, app_id: str, resource_type: str, amount: int) -> bool:
        """Allocate system resource to application"""
        try:
            res_type = ResourceType(resource_type)
            return self.resource_manager.allocate_resource(app_id, res_type, amount)
        except ValueError:
            logger.error(f"Unknown resource type: {resource_type}")
            return False
    
    def release_resource(self, app_id: str, resource_type: str, amount: int):
        """Release system resource from application"""
        try:
            res_type = ResourceType(resource_type)
            self.resource_manager.release_resource(app_id, res_type, amount)
        except ValueError:
            logger.error(f"Unknown resource type: {resource_type}")
    
    def set_resource_quota(self, app_id: str, resource_type: str, limit: int):
        """Set resource quota for application"""
        try:
            res_type = ResourceType(resource_type)
            self.resource_manager.set_quota(app_id, res_type, limit)
        except ValueError:
            logger.error(f"Unknown resource type: {resource_type}")
    
    # Security and permissions
    def check_permission(self, app_id: str, permission: str) -> bool:
        """Check if application has permission"""
        return self.security_manager.check_permission(app_id, permission)
    
    def grant_permission(self, app_id: str, permission: str):
        """Grant permission to application"""
        self.security_manager.grant_permission(app_id, permission)
    
    def revoke_permission(self, app_id: str, permission: str):
        """Revoke permission from application"""
        self.security_manager.revoke_permission(app_id, permission)
    
    # Application management
    def register_app(self, app_id: str, app_info: Dict[str, Any]) -> bool:
        """Register application with KOS"""
        if not self.app_registry:
            logger.error("AppRegistry not available")
            return False
        
        try:
            return self.app_registry.register_application(app_id, app_info)
        except Exception as e:
            logger.error(f"Failed to register app {app_id}: {e}")
            return False
    
    def unregister_app(self, app_id: str) -> bool:
        """Unregister application from KOS"""
        if not self.app_registry:
            return False
        
        try:
            return self.app_registry.unregister_application(app_id)
        except Exception as e:
            logger.error(f"Failed to unregister app {app_id}: {e}")
            return False
    
    def get_app_info(self, app_id: str) -> Dict[str, Any]:
        """Get application information"""
        if not self.app_registry:
            return {"error": "AppRegistry not available"}
        
        try:
            app_info = self.app_registry.get_application_info(app_id)
            if app_info:
                return {"success": True, "info": app_info}
            else:
                return {"error": f"Application {app_id} not found"}
        except Exception as e:
            return {"error": str(e)}
    
    # File system operations
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file content"""
        if not self.file_system:
            return {"error": "FileSystem not available"}
        
        try:
            content = self.file_system.read_file(path)
            return {"success": True, "content": content}
        except Exception as e:
            return {"error": str(e)}
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file content"""
        if not self.file_system:
            return {"error": "FileSystem not available"}
        
        try:
            self.file_system.write_file(path, content)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}
    
    # Shell operations
    def execute_shell_command(self, command: str) -> Dict[str, Any]:
        """Execute shell command"""
        if not self.shell:
            return {"error": "Shell not available"}
        
        try:
            result = self.shell.execute_command(command)
            return {"success": True, "result": result}
        except Exception as e:
            return {"error": str(e)}
    
    # Package management
    def install_package(self, package_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Install package"""
        if not self.package_manager:
            return {"error": "Package manager not available"}
        
        try:
            success = self.package_manager.install_package(package_name, version)
            if success:
                return {"success": True, "message": f"Package {package_name} installed"}
            else:
                return {"error": f"Failed to install package {package_name}"}
        except Exception as e:
            return {"error": str(e)}
    
    # Advanced features
    def schedule_task(self, task_id: str, task_func: Callable, schedule: str, **kwargs) -> bool:
        """Schedule task for execution"""
        return self.scheduler.schedule_task(task_id, task_func, schedule, **kwargs)
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel scheduled task"""
        return self.scheduler.cancel_task(task_id)
    
    def send_ipc_message(self, target_app: str, message: Dict[str, Any]) -> bool:
        """Send IPC message to another application"""
        return self.ipc_manager.send_message(target_app, message)
    
    def register_ipc_handler(self, app_id: str, handler: Callable):
        """Register IPC message handler"""
        self.ipc_manager.register_handler(app_id, handler)
    
    # Performance monitoring
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        return self.performance_monitor.get_metrics()
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        return self.statistics.get_all_stats()
    
    # Event system
    def register_event_handler(self, event_type: str, handler: Callable):
        """Register event handler"""
        self.event_system.register_handler(event_type, handler)
    
    def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit system event"""
        self.event_system.emit_event(event_type, data)
    
    # Device management
    def register_device(self, device_id: str, device_info: Dict[str, Any]) -> bool:
        """Register device with system"""
        return self.device_manager.register_device(device_id, device_info)
    
    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """Get device information"""
        return self.device_manager.get_device_info(device_id)
    
    # Cleanup
    def shutdown(self):
        """Shutdown KLayer and cleanup resources"""
        logger.info("Shutting down KLayer")
        
        # Cancel all tasks
        self.scheduler.shutdown()
        
        # Shutdown executors
        self.executor.shutdown(wait=True)
        self.async_executor.shutdown(wait=True)
        
        # Cleanup components
        for component in [self.event_system, self.ipc_manager, self.device_manager,
                         self.performance_monitor, self.statistics]:
            if hasattr(component, 'shutdown'):
                try:
                    component.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down component: {e}")

# Additional supporting classes
class EventSystem:
    """System-wide event handling"""
    
    def __init__(self):
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.lock = threading.RLock()
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register event handler"""
        with self.lock:
            self.handlers[event_type].append(handler)
    
    def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event to all handlers"""
        with self.lock:
            for handler in self.handlers.get(event_type, []):
                try:
                    handler(data)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")

class IPCManager:
    """Inter-process communication manager"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self.message_queue: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.RLock()
    
    def register_handler(self, app_id: str, handler: Callable):
        """Register IPC handler for application"""
        with self.lock:
            self.handlers[app_id] = handler
    
    def send_message(self, target_app: str, message: Dict[str, Any]) -> bool:
        """Send IPC message"""
        with self.lock:
            if target_app in self.handlers:
                try:
                    self.handlers[target_app](message)
                    return True
                except Exception as e:
                    logger.error(f"IPC message delivery failed: {e}")
            else:
                # Queue message for later delivery
                self.message_queue[target_app].append(message)
            return False

class DeviceManager:
    """Device management system"""
    
    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
    
    def register_device(self, device_id: str, device_info: Dict[str, Any]) -> bool:
        """Register device"""
        with self.lock:
            self.devices[device_id] = device_info
            return True
    
    def get_device_info(self, device_id: str) -> Dict[str, Any]:
        """Get device information"""
        with self.lock:
            return self.devices.get(device_id, {})

class TaskScheduler:
    """Task scheduling system"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.running = True
        self.lock = threading.RLock()
    
    def schedule_task(self, task_id: str, task_func: Callable, schedule: str, **kwargs) -> bool:
        """Schedule task"""
        with self.lock:
            self.tasks[task_id] = {
                "function": task_func,
                "schedule": schedule,
                "kwargs": kwargs,
                "next_run": time.time()  # Simplified scheduling
            }
            return True
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel task"""
        with self.lock:
            return self.tasks.pop(task_id, None) is not None
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.running = False

class PerformanceMonitor:
    """Performance monitoring system"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        with self.lock:
            return dict(self.metrics)

class SystemStatistics:
    """System statistics collection"""
    
    def __init__(self):
        self.stats: Dict[str, Any] = {}
        self.lock = threading.RLock()
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get all system statistics"""
        with self.lock:
            return dict(self.stats)

# Global KLayer instance
_klayer_instance = None

def get_klayer() -> KLayer:
    """Get global KLayer instance"""
    global _klayer_instance
    if _klayer_instance is None:
        _klayer_instance = KLayer.get_instance()
    return _klayer_instance

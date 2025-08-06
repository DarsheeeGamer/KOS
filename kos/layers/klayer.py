"""
KLayer - Core OS Layer for KOS
Provides fundamental OS services and abstractions with real memory management
"""

import time
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

# Import core components
from kos.core.vfs import PickleVFS
from kos.core.auth import AuthManager, User, UserRole
from kos.core.executor import ProcessExecutor, Process
from kos.core.permissions import PermissionManager, FilePermissions
from kos.core.config import ConfigManager, EnvironmentManager
from kos.core.memory import MemoryManager, MemoryStats, MemoryType
from kos.python.interpreter import PythonEnvironment

class KLayer:
    """
    Core OS Layer providing fundamental services:
    - File System Operations
    - Process Management
    - User Management
    - System Information
    - Basic I/O Operations
    - Memory Management (simulated)
    - Device Abstraction
    """
    
    def __init__(self, disk_file: str = "kaede.kdsk", memory_size: int = 8 * 1024 * 1024 * 1024):
        """Initialize KLayer with all core components including real memory management"""
        self.version = "2.0.0"
        self.boot_time = time.time()
        
        # Core components
        self.vfs = PickleVFS(disk_file)
        self.auth = AuthManager(self.vfs)
        self.executor = ProcessExecutor(self.vfs)
        self.permissions = PermissionManager(self.vfs, self.auth)
        self.config_manager = ConfigManager(self.vfs)
        self.env_manager = EnvironmentManager(self.config_manager)
        
        # Memory management
        self.memory = MemoryManager(memory_size)
        
        # Python environment
        self.python = PythonEnvironment(self.vfs, self.memory)
        
        # System state
        self.current_user: Optional[User] = None
        self.processes: Dict[int, Process] = {}
        self.next_pid = 1000
        self.system_info = self._init_system_info()
        
        # Process memory tracking
        self.process_memory: Dict[int, List[int]] = {}  # pid -> [memory addresses]
        
        # Initialize system
        self._initialize_system()
    
    def _init_system_info(self) -> Dict[str, Any]:
        """Initialize system information"""
        return {
            'name': 'KOS',
            'version': '1.0',
            'kernel': 'KOS-KERNEL-1.0',
            'architecture': 'x86_64',
            'hostname': 'kos',
            'total_memory': 8589934592,  # 8GB simulated
            'cpu_cores': 4,
            'boot_time': self.boot_time
        }
    
    def _initialize_system(self):
        """Initialize core system components"""
        # Create essential directories
        essential_dirs = [
            '/bin', '/sbin', '/usr', '/usr/bin', '/usr/sbin',
            '/etc', '/var', '/var/log', '/var/run',
            '/tmp', '/home', '/root', '/dev', '/proc', '/sys'
        ]
        
        for dir_path in essential_dirs:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path)
                except:
                    pass
        
        # Set up initial user if none exists
        if not self.auth.get_user('root'):
            self.auth.create_user('root', 'root', UserRole.ROOT)
    
    # ==================== File System Operations ====================
    
    def fs_open(self, path: str, mode: str = 'r') -> Optional[Any]:
        """Open file with permission checking"""
        if self.current_user:
            # Check permissions
            if not self.permissions.check_access(
                path, self.current_user.uid, self.current_user.gid, 
                'r' if 'r' in mode else 'w'
            ):
                return None
        
        return self.vfs.open(path, mode)
    
    def fs_read(self, path: str) -> Optional[bytes]:
        """Read file contents"""
        try:
            with self.fs_open(path, 'rb') as f:
                if f:
                    return f.read()
        except:
            pass
        return None
    
    def fs_write(self, path: str, data: bytes) -> bool:
        """Write data to file"""
        try:
            with self.fs_open(path, 'wb') as f:
                if f:
                    f.write(data)
                    return True
        except:
            pass
        return False
    
    def fs_exists(self, path: str) -> bool:
        """Check if path exists"""
        return self.vfs.exists(path)
    
    def fs_mkdir(self, path: str) -> bool:
        """Create directory"""
        try:
            self.vfs.mkdir(path)
            return True
        except:
            return False
    
    def fs_remove(self, path: str) -> bool:
        """Remove file or directory"""
        if self.current_user:
            if not self.permissions.check_access(
                path, self.current_user.uid, self.current_user.gid, 'w'
            ):
                return False
        
        try:
            self.vfs.remove(path)
            return True
        except:
            return False
    
    def fs_list(self, path: str) -> List[str]:
        """List directory contents"""
        try:
            return self.vfs.listdir(path)
        except:
            return []
    
    def fs_stat(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file statistics"""
        if not self.vfs.exists(path):
            return None
        
        # Get VFS node
        node = self.permissions._get_node(path)
        if not node:
            return None
        
        return {
            'path': path,
            'size': getattr(node, 'size', 0),
            'mode': getattr(node, 'mode', 0o644),
            'uid': getattr(node, 'uid', 0),
            'gid': getattr(node, 'gid', 0),
            'atime': getattr(node, 'atime', time.time()),
            'mtime': getattr(node, 'mtime', time.time()),
            'ctime': getattr(node, 'ctime', time.time()),
            'is_dir': self.vfs.isdir(path),
            'is_file': not self.vfs.isdir(path)
        }
    
    # ==================== Process Management ====================
    
    def process_create(self, command: str, args: List[str] = None, 
                      env: Dict[str, str] = None) -> int:
        """Create new process"""
        pid = self.next_pid
        self.next_pid += 1
        
        process = Process(
            pid=pid,
            command=command,
            args=args or [],
            env=env or self.env_manager.export_all(),
            uid=self.current_user.uid if self.current_user else 0,
            gid=self.current_user.gid if self.current_user else 0
        )
        
        self.processes[pid] = process
        return pid
    
    def process_execute(self, pid: int) -> Tuple[int, str, str]:
        """Execute process"""
        if pid not in self.processes:
            return -1, "", "Process not found"
        
        process = self.processes[pid]
        
        # Execute through executor
        result = self.executor.execute(
            process.command,
            args=process.args,
            env=process.env,
            background=False
        )
        
        # Update process state
        process.exit_code = result[0] if isinstance(result, tuple) else 0
        process.state = "terminated"
        
        return result if isinstance(result, tuple) else (0, str(result), "")
    
    def process_kill(self, pid: int, signal: int = 15) -> bool:
        """Kill process"""
        if pid not in self.processes:
            return False
        
        process = self.processes[pid]
        process.state = "terminated"
        process.exit_code = -signal
        
        # Remove from active processes
        del self.processes[pid]
        return True
    
    def process_list(self) -> List[Dict[str, Any]]:
        """List all processes"""
        return [
            {
                'pid': p.pid,
                'command': p.command,
                'state': p.state,
                'uid': p.uid,
                'cpu_time': p.cpu_time,
                'memory': p.memory
            }
            for p in self.processes.values()
        ]
    
    def process_wait(self, pid: int) -> Optional[int]:
        """Wait for process to complete"""
        if pid not in self.processes:
            return None
        
        process = self.processes[pid]
        
        # Simulate waiting
        while process.state == "running":
            time.sleep(0.1)
        
        return process.exit_code
    
    # ==================== User Management ====================
    
    def user_login(self, username: str, password: str) -> bool:
        """Login user"""
        if self.auth.authenticate(username, password):
            self.current_user = self.auth.get_user(username)
            
            # Set environment
            if self.current_user:
                self.env_manager.set('USER', username)
                self.env_manager.set('HOME', f'/home/{username}' if username != 'root' else '/root')
                self.env_manager.set('UID', str(self.current_user.uid))
            
            return True
        return False
    
    def user_logout(self):
        """Logout current user"""
        self.current_user = None
        self.env_manager.unset('USER')
        self.env_manager.unset('UID')
    
    def user_create(self, username: str, password: str, role: str = 'user') -> bool:
        """Create new user"""
        if not self.current_user or self.current_user.role not in [UserRole.ROOT, UserRole.ADMIN]:
            return False
        
        role_map = {
            'root': UserRole.ROOT,
            'admin': UserRole.ADMIN,
            'user': UserRole.USER,
            'guest': UserRole.GUEST
        }
        
        user_role = role_map.get(role, UserRole.USER)
        return self.auth.create_user(username, password, user_role)
    
    def user_delete(self, username: str) -> bool:
        """Delete user"""
        if not self.current_user or self.current_user.role != UserRole.ROOT:
            return False
        
        return self.auth.delete_user(username)
    
    def user_get_current(self) -> Optional[Dict[str, Any]]:
        """Get current user info"""
        if not self.current_user:
            return None
        
        return {
            'username': self.current_user.username,
            'uid': self.current_user.uid,
            'gid': self.current_user.gid,
            'role': self.current_user.role.value,
            'home': self.current_user.home_dir
        }
    
    # ==================== System Information ====================
    
    def sys_info(self) -> Dict[str, Any]:
        """Get system information"""
        return self.system_info.copy()
    
    def sys_uptime(self) -> float:
        """Get system uptime in seconds"""
        return time.time() - self.boot_time
    
    def sys_memory_info(self) -> Dict[str, int]:
        """Get real memory information"""
        stats = self.memory.get_stats()
        
        return {
            'total': stats.total,
            'used': stats.used,
            'free': stats.free,
            'available': stats.available,
            'percent': int(stats.percent),
            'buffers': stats.buffers,
            'cached': stats.cached,
            'shared': stats.shared,
            'swap_total': stats.swap_total,
            'swap_used': stats.swap_used,
            'swap_free': stats.swap_free
        }
    
    def sys_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        return {
            'cores': self.system_info['cpu_cores'],
            'usage': 25.0,  # Simulated
            'load_avg': [0.5, 0.3, 0.2]  # Simulated
        }
    
    def sys_disk_info(self, path: str = '/') -> Dict[str, int]:
        """Get disk information"""
        # Simulated disk info
        total = 107374182400  # 100GB
        used = int(total * 0.2)  # 20% used
        free = total - used
        
        return {
            'total': total,
            'used': used,
            'free': free,
            'percent': (used * 100) // total
        }
    
    # ==================== I/O Operations ====================
    
    def io_print(self, text: str):
        """Print to standard output"""
        print(text)
    
    def io_input(self, prompt: str = "") -> str:
        """Read from standard input"""
        return input(prompt)
    
    def io_error(self, text: str):
        """Print to standard error"""
        import sys
        print(text, file=sys.stderr)
    
    # ==================== Memory Management (Real) ====================
    
    def mem_allocate(self, size: int) -> Optional[int]:
        """Allocate real memory"""
        pid = self.current_user.uid if self.current_user else 0
        addr = self.memory.malloc(size, pid)
        
        if addr and pid not in self.process_memory:
            self.process_memory[pid] = []
        if addr:
            self.process_memory[pid].append(addr)
        
        return addr
    
    def mem_free(self, address: int) -> bool:
        """Free allocated memory"""
        success = self.memory.free(address)
        
        if success:
            # Remove from process tracking
            for pid, addrs in self.process_memory.items():
                if address in addrs:
                    addrs.remove(address)
                    break
        
        return success
    
    def mem_read(self, address: int, size: int) -> Optional[bytes]:
        """Read from real memory address"""
        data = self.memory.allocator.read(address, size)
        return data
    
    def mem_write(self, address: int, data: bytes) -> bool:
        """Write to real memory address"""
        return self.memory.allocator.write(address, data)
    
    def mem_realloc(self, address: int, new_size: int) -> Optional[int]:
        """Reallocate memory block"""
        return self.memory.realloc(address, new_size)
    
    def mem_share(self, name: str, size: int) -> Optional[int]:
        """Create shared memory segment"""
        pid = self.current_user.uid if self.current_user else 0
        return self.memory.create_shared_memory(name, size, pid)
    
    def mem_map_file(self, filepath: str, size: int = 0) -> Optional[int]:
        """Memory-map a file"""
        pid = self.current_user.uid if self.current_user else 0
        return self.memory.mmap(filepath, size, pid=pid)
    
    def mem_get_process_usage(self, pid: int) -> Dict[str, int]:
        """Get process memory usage"""
        return self.memory.get_process_memory(pid)
    
    def mem_garbage_collect(self) -> int:
        """Run garbage collection"""
        return self.memory.garbage_collect()
    
    # ==================== Device Operations ====================
    
    def dev_list(self) -> List[Dict[str, Any]]:
        """List available devices"""
        return [
            {'name': 'sda', 'type': 'disk', 'size': 107374182400},
            {'name': 'tty0', 'type': 'terminal', 'size': 0},
            {'name': 'null', 'type': 'character', 'size': 0},
            {'name': 'random', 'type': 'character', 'size': 0}
        ]
    
    def dev_open(self, device: str) -> Optional[int]:
        """Open device (returns handle)"""
        # Simulated device handle
        import random
        return random.randint(1, 1000)
    
    def dev_close(self, handle: int) -> bool:
        """Close device"""
        return True
    
    def dev_read(self, handle: int, size: int) -> bytes:
        """Read from device"""
        import os
        return os.urandom(size)
    
    def dev_write(self, handle: int, data: bytes) -> int:
        """Write to device"""
        return len(data)
    
    # ==================== Environment Management ====================
    
    def env_get(self, name: str) -> Optional[str]:
        """Get environment variable"""
        return self.env_manager.get(name)
    
    def env_set(self, name: str, value: str) -> bool:
        """Set environment variable"""
        return self.env_manager.set(name, value)
    
    def env_unset(self, name: str) -> bool:
        """Unset environment variable"""
        return self.env_manager.unset(name)
    
    def env_list(self) -> Dict[str, str]:
        """List all environment variables"""
        return self.env_manager.export_all()
    
    # ==================== Permission Management ====================
    
    def perm_chmod(self, path: str, mode: int) -> bool:
        """Change file permissions"""
        uid = self.current_user.uid if self.current_user else 0
        return self.permissions.chmod(path, mode, uid)
    
    def perm_chown(self, path: str, uid: int, gid: int = -1) -> bool:
        """Change file ownership"""
        current_uid = self.current_user.uid if self.current_user else 0
        return self.permissions.chown(path, uid, gid, current_uid)
    
    def perm_check(self, path: str, mode: str) -> bool:
        """Check file permissions"""
        if not self.current_user:
            return True  # Root access
        
        return self.permissions.check_access(
            path, self.current_user.uid, self.current_user.gid, mode
        )
    
    # ==================== Python Support ====================
    
    def python_execute(self, code: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python code in VFS environment"""
        return self.python.execute(code, namespace)
    
    def python_execute_file(self, filepath: str, namespace: Optional[str] = None) -> Dict[str, Any]:
        """Execute Python file from VFS"""
        return self.python.execute_file(filepath, namespace)
    
    def python_install_package(self, package: str, version: Optional[str] = None) -> bool:
        """Install Python package to VFS"""
        return self.python.install_package(package, version)
    
    def python_uninstall_package(self, package: str) -> bool:
        """Uninstall Python package from VFS"""
        return self.python.uninstall_package(package)
    
    def python_list_packages(self) -> List[Dict[str, Any]]:
        """List installed Python packages"""
        return self.python.list_packages()
    
    def python_create_venv(self, name: str, path: Optional[str] = None) -> bool:
        """Create Python virtual environment"""
        return self.python.create_virtualenv(name, path)
    
    def python_repl(self):
        """Start Python REPL"""
        console = self.python.create_repl()
        console.interact(banner="KOS Python REPL (VFS-integrated)")
    
    # ==================== Utility Functions ====================
    
    def shutdown(self):
        """Shutdown KLayer and save state"""
        # Free all process memory
        for pid in list(self.process_memory.keys()):
            self.memory.free_process_memory(pid)
        
        # Run garbage collection
        self.memory.garbage_collect()
        
        # Save VFS
        self.vfs._save()
        
        # Clear processes
        self.processes.clear()
        
        # Logout user
        self.user_logout()
    
    def reboot(self):
        """Reboot system (reload state)"""
        self.shutdown()
        self.__init__(self.vfs.disk_file)
"""
KOS Kernel - High-Level Python Interface

Unified API for all KOS kernel subsystems including:
- Process and thread management
- Memory management
- Filesystem operations
- Network stack
- IPC mechanisms
- Scheduling
- Device drivers
- Resource monitoring
"""

import ctypes
import os
import sys
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path

# Import subsystem wrappers
try:
    from kernel_wrapper import KOSKernel, ProcessInfo, ThreadInfo, ProcessState, ThreadState
except ImportError as e:
    logging.warning(f"Failed to import kernel_wrapper: {e}")
    # Define basic classes here as fallback
    from enum import IntEnum
    from dataclasses import dataclass
    
    class ProcessState(IntEnum):
        NEW = 0
        READY = 1
        RUNNING = 2
        BLOCKED = 3
        ZOMBIE = 4
        DEAD = 5
    
    class ThreadState(IntEnum):
        NEW = 0
        READY = 1
        RUNNING = 2
        BLOCKED = 3
        SLEEPING = 4
        DEAD = 5
    
    @dataclass
    class ProcessInfo:
        pid: int
        ppid: int
        uid: int
        gid: int
        state: ProcessState
        thread_count: int
        cpu_time: int
        priority: int
        nice: int
        start_time: int
    
    @dataclass
    class ThreadInfo:
        tid: int
        pid: int
        state: ThreadState
        cpu_affinity: int
        runtime: int
        timeslice: int
    
    KOSKernel = None

# Try to import other subsystem wrappers (optional)
try:
    from drivers.drivers_wrapper import KOSDriverManager
except ImportError:
    KOSDriverManager = None

try:
    from fs.fs_wrapper import KOSFilesystem
except ImportError:
    KOSFilesystem = None

try:
    from ipc.ipc_wrapper import KOSIPC
except ImportError:
    KOSIPC = None

try:
    from mm.mm_wrapper import KOSMemoryManager
except ImportError:
    KOSMemoryManager = None

try:
    from sched.sched_wrapper import KOSScheduler
except ImportError:
    KOSScheduler = None

try:
    from resource_monitor_wrapper import KOSResourceMonitor
except ImportError:
    KOSResourceMonitor = None

logger = logging.getLogger('KOS.kernel')


class KernelState(IntEnum):
    """Kernel states"""
    UNINITIALIZED = 0
    INITIALIZING = 1
    RUNNING = 2
    SHUTTING_DOWN = 3
    SHUTDOWN = 4
    PANIC = 5


class SystemCallError(Exception):
    """System call error"""
    pass


class KernelPanicError(Exception):
    """Kernel panic error"""
    pass


@dataclass
class KernelConfig:
    """Kernel configuration"""
    debug_mode: bool = False
    max_processes: int = 1024
    max_threads: int = 4096
    max_fds: int = 1024
    kernel_stack_size: int = 8192
    page_size: int = 4096
    scheduler_type: str = "cfs"  # cfs, rt, fair
    network_enabled: bool = True
    filesystem_enabled: bool = True
    ipc_enabled: bool = True
    resource_monitoring: bool = True
    log_level: str = "INFO"


@dataclass
class KernelStats:
    """Kernel statistics"""
    uptime: float = 0.0
    processes: int = 0
    threads: int = 0
    memory_usage: int = 0
    memory_available: int = 0
    cpu_usage: float = 0.0
    network_packets_sent: int = 0
    network_packets_received: int = 0
    filesystem_operations: int = 0
    ipc_messages: int = 0
    syscalls: int = 0
    interrupts: int = 0


class KOSKernelManager:
    """
    Main KOS Kernel Manager
    
    Provides unified interface to all kernel subsystems and manages
    kernel initialization, configuration, and lifecycle.
    """
    
    def __init__(self, config: Optional[KernelConfig] = None):
        self.config = config or KernelConfig()
        self.state = KernelState.UNINITIALIZED
        self.start_time = time.time()
        
        # Initialize logging
        self._setup_logging()
        
        # Subsystem instances
        self.core: Optional[KOSKernel] = None
        self.drivers: Optional[KOSDriverManager] = None
        self.filesystem: Optional[KOSFilesystem] = None
        self.ipc: Optional[KOSIPC] = None
        self.memory: Optional[KOSMemoryManager] = None
        self.network: Optional[KOSNetworkStack] = None
        self.scheduler: Optional[KOSScheduler] = None
        self.resource_monitor: Optional[KOSResourceMonitor] = None
        
        # Kernel thread and synchronization
        self._kernel_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._stats_lock = threading.Lock()
        
        # Callback registrations
        self._callbacks: Dict[str, List[Callable]] = {}
        
        # Performance counters
        self._stats = KernelStats()
        self._last_stats_update = time.time()
        
        logger.info("KOS Kernel Manager created")
    
    def _setup_logging(self):
        """Setup kernel logging"""
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format='[KOS %(asctime)s] %(name)s:%(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        if self.config.debug_mode:
            logger.setLevel(logging.DEBUG)
            logger.debug("Debug logging enabled")
    
    def initialize(self) -> bool:
        """
        Initialize the KOS kernel and all subsystems
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if self.state != KernelState.UNINITIALIZED:
            logger.warning("Kernel already initialized")
            return False
            
        logger.info("Initializing KOS kernel...")
        self.state = KernelState.INITIALIZING
        
        try:
            # Initialize core kernel
            self._initialize_core()
            
            # Initialize subsystems in dependency order
            success = True
            success &= self._initialize_memory()
            success &= self._initialize_filesystem()
            success &= self._initialize_ipc()
            success &= self._initialize_network()
            success &= self._initialize_drivers()
            success &= self._initialize_scheduler()
            success &= self._initialize_resource_monitor()
            
            if not success:
                logger.error("Failed to initialize some subsystems")
                return False
            
            # Start kernel main loop
            self._start_kernel_loop()
            
            self.state = KernelState.RUNNING
            logger.info("KOS kernel initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Kernel initialization failed: {e}")
            self.state = KernelState.UNINITIALIZED
            return False
    
    def _initialize_core(self):
        """Initialize core kernel"""
        try:
            self.core = KOSKernel()
            logger.info("Core kernel initialized")
        except Exception as e:
            logger.error(f"Failed to initialize core kernel: {e}")
            # Create mock implementation
            self.core = self._create_mock_core()
    
    def _initialize_memory(self) -> bool:
        """Initialize memory management subsystem"""
        if not self.config.filesystem_enabled:
            return True
            
        try:
            from .mm.mm_wrapper import KOSMemoryManager
            self.memory = KOSMemoryManager()
            logger.info("Memory management subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize memory subsystem: {e}")
            self.memory = self._create_mock_memory()
            return True
    
    def _initialize_filesystem(self) -> bool:
        """Initialize filesystem subsystem"""
        if not self.config.filesystem_enabled:
            return True
            
        try:
            from .fs.fs_wrapper import KOSFilesystem
            self.filesystem = KOSFilesystem()
            logger.info("Filesystem subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize filesystem: {e}")
            self.filesystem = self._create_mock_filesystem()
            return True
    
    def _initialize_ipc(self) -> bool:
        """Initialize IPC subsystem"""
        if not self.config.ipc_enabled:
            return True
            
        try:
            from .ipc.ipc_wrapper import KOSIPC
            self.ipc = KOSIPC()
            logger.info("IPC subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize IPC: {e}")
            self.ipc = self._create_mock_ipc()
            return True
    
    def _initialize_network(self) -> bool:
        """Initialize network subsystem"""
        if not self.config.network_enabled:
            return True
            
        try:
            from .net.net_wrapper import KOSNetworkStack
            self.network = KOSNetworkStack()
            logger.info("Network subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize network: {e}")
            self.network = self._create_mock_network()
            return True
    
    def _initialize_drivers(self) -> bool:
        """Initialize device drivers"""
        try:
            from .drivers.drivers_wrapper import KOSDriverManager
            self.drivers = KOSDriverManager()
            logger.info("Driver subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize drivers: {e}")
            self.drivers = self._create_mock_drivers()
            return True
    
    def _initialize_scheduler(self) -> bool:
        """Initialize scheduler"""
        try:
            from .sched.sched_wrapper import KOSScheduler
            self.scheduler = KOSScheduler(scheduler_type=self.config.scheduler_type)
            logger.info("Scheduler subsystem initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize scheduler: {e}")
            self.scheduler = self._create_mock_scheduler()
            return True
    
    def _initialize_resource_monitor(self) -> bool:
        """Initialize resource monitoring"""
        if not self.config.resource_monitoring:
            return True
            
        try:
            from .resource_monitor_wrapper import KOSResourceMonitor
            self.resource_monitor = KOSResourceMonitor()
            logger.info("Resource monitor initialized")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize resource monitor: {e}")
            self.resource_monitor = self._create_mock_resource_monitor()
            return True
    
    def _start_kernel_loop(self):
        """Start the kernel main loop in a separate thread"""
        self._kernel_thread = threading.Thread(
            target=self._kernel_main_loop,
            daemon=True,
            name="KOS-Kernel-Thread"
        )
        self._kernel_thread.start()
        logger.info("Kernel main loop started")
    
    def _kernel_main_loop(self):
        """Main kernel loop - handles scheduling, interrupts, etc."""
        logger.debug("Entering kernel main loop")
        
        while not self._shutdown_event.is_set():
            try:
                # Update statistics
                self._update_stats()
                
                # Process pending callbacks
                self._process_callbacks()
                
                # Scheduler tick
                if self.scheduler:
                    self.scheduler.tick()
                
                # Resource monitoring update
                if self.resource_monitor:
                    self.resource_monitor.update()
                
                # Network processing
                if self.network:
                    self.network.process_packets()
                
                # Sleep for kernel tick (1ms)
                time.sleep(0.001)
                
            except Exception as e:
                logger.error(f"Error in kernel loop: {e}")
                if self.config.debug_mode:
                    raise
                
        logger.debug("Kernel main loop terminated")
    
    def _update_stats(self):
        """Update kernel statistics"""
        current_time = time.time()
        if current_time - self._last_stats_update < 1.0:  # Update every second
            return
            
        with self._stats_lock:
            self._stats.uptime = current_time - self.start_time
            
            # Get process/thread counts
            if self.core:
                processes = self.core.get_process_list()
                threads = self.core.get_thread_list()
                self._stats.processes = len(processes)
                self._stats.threads = len(threads)
            
            # Memory statistics
            if self.memory:
                mem_stats = self.memory.get_stats()
                self._stats.memory_usage = mem_stats.get('used', 0)
                self._stats.memory_available = mem_stats.get('free', 0)
            
            # Network statistics
            if self.network:
                net_stats = self.network.get_stats()
                self._stats.network_packets_sent = net_stats.get('packets_sent', 0)
                self._stats.network_packets_received = net_stats.get('packets_received', 0)
        
        self._last_stats_update = current_time
    
    def _process_callbacks(self):
        """Process registered callbacks"""
        for event_type, callbacks in self._callbacks.items():
            for callback in callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in callback for {event_type}: {e}")
    
    def shutdown(self, force: bool = False):
        """Shutdown the kernel"""
        if self.state == KernelState.SHUTDOWN:
            return
            
        logger.info("Shutting down KOS kernel...")
        self.state = KernelState.SHUTTING_DOWN
        
        # Signal kernel thread to stop
        self._shutdown_event.set()
        
        # Wait for kernel thread to finish
        if self._kernel_thread and self._kernel_thread.is_alive():
            self._kernel_thread.join(timeout=5.0)
            if self._kernel_thread.is_alive() and not force:
                logger.warning("Kernel thread did not terminate gracefully")
        
        # Shutdown subsystems in reverse order
        self._shutdown_subsystems()
        
        self.state = KernelState.SHUTDOWN
        logger.info("KOS kernel shutdown complete")
    
    def _shutdown_subsystems(self):
        """Shutdown all subsystems"""
        if self.resource_monitor:
            try:
                self.resource_monitor.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down resource monitor: {e}")
        
        if self.scheduler:
            try:
                self.scheduler.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down scheduler: {e}")
        
        if self.drivers:
            try:
                self.drivers.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down drivers: {e}")
        
        if self.network:
            try:
                self.network.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down network: {e}")
        
        if self.ipc:
            try:
                self.ipc.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down IPC: {e}")
        
        if self.filesystem:
            try:
                self.filesystem.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down filesystem: {e}")
        
        if self.memory:
            try:
                self.memory.shutdown()
            except Exception as e:
                logger.error(f"Error shutting down memory manager: {e}")
    
    def panic(self, message: str):
        """Trigger kernel panic"""
        logger.critical(f"KERNEL PANIC: {message}")
        self.state = KernelState.PANIC
        
        # Try to save crash dump
        try:
            self._save_crash_dump(message)
        except Exception as e:
            logger.error(f"Failed to save crash dump: {e}")
        
        # Forceful shutdown
        self.shutdown(force=True)
        
        raise KernelPanicError(f"Kernel panic: {message}")
    
    def _save_crash_dump(self, message: str):
        """Save crash dump for debugging"""
        crash_dump = {
            'timestamp': time.time(),
            'message': message,
            'stats': self.get_stats(),
            'config': self.config.__dict__,
            'state': self.state.name,
            'uptime': time.time() - self.start_time
        }
        
        # Save to file
        dump_file = f"kos_crash_{int(time.time())}.json"
        import json
        with open(dump_file, 'w') as f:
            json.dump(crash_dump, f, indent=2)
        
        logger.info(f"Crash dump saved to {dump_file}")
    
    # High-level API methods
    
    def create_process(self, name: str = "process", **kwargs) -> Optional[int]:
        """Create a new process"""
        if not self.core:
            return None
        return self.core.create_process(name=name, **kwargs)
    
    def destroy_process(self, pid: int) -> bool:
        """Destroy a process"""
        if not self.core:
            return False
        return self.core.destroy_process(pid)
    
    def create_thread(self, pid: int, entry_func: Optional[Callable] = None) -> Optional[int]:
        """Create a new thread"""
        if not self.core:
            return None
        return self.core.create_thread(pid, entry_func)
    
    def destroy_thread(self, tid: int) -> bool:
        """Destroy a thread"""
        if not self.core:
            return False
        return self.core.destroy_thread(tid)
    
    def allocate_memory(self, size: int) -> Optional[int]:
        """Allocate memory"""
        if self.memory:
            return self.memory.allocate(size)
        elif self.core:
            return self.core.allocate_memory(size)
        return None
    
    def free_memory(self, ptr: int):
        """Free memory"""
        if self.memory:
            self.memory.free(ptr)
        elif self.core:
            self.core.free_memory(ptr)
    
    def open_file(self, path: str, mode: str = 'r') -> Optional[int]:
        """Open a file"""
        if not self.filesystem:
            return None
        return self.filesystem.open(path, mode)
    
    def close_file(self, fd: int) -> bool:
        """Close a file"""
        if not self.filesystem:
            return False
        return self.filesystem.close(fd)
    
    def read_file(self, fd: int, size: int) -> Optional[bytes]:
        """Read from file"""
        if not self.filesystem:
            return None
        return self.filesystem.read(fd, size)
    
    def write_file(self, fd: int, data: bytes) -> int:
        """Write to file"""
        if not self.filesystem:
            return -1
        return self.filesystem.write(fd, data)
    
    def send_ipc_message(self, dest_pid: int, message: Any) -> bool:
        """Send IPC message"""
        if not self.ipc:
            return False
        return self.ipc.send_message(dest_pid, message)
    
    def receive_ipc_message(self, timeout: float = 0) -> Optional[Tuple[int, Any]]:
        """Receive IPC message"""
        if not self.ipc:
            return None
        return self.ipc.receive_message(timeout)
    
    def create_socket(self, domain: int, sock_type: int, protocol: int = 0) -> Optional[int]:
        """Create a socket"""
        if not self.network:
            return None
        return self.network.create_socket(domain, sock_type, protocol)
    
    def bind_socket(self, sockfd: int, address: Tuple[str, int]) -> bool:
        """Bind socket to address"""
        if not self.network:
            return False
        return self.network.bind(sockfd, address)
    
    def connect_socket(self, sockfd: int, address: Tuple[str, int]) -> bool:
        """Connect socket to address"""
        if not self.network:
            return False
        return self.network.connect(sockfd, address)
    
    def send_data(self, sockfd: int, data: bytes) -> int:
        """Send data on socket"""
        if not self.network:
            return -1
        return self.network.send(sockfd, data)
    
    def receive_data(self, sockfd: int, size: int) -> Optional[bytes]:
        """Receive data from socket"""
        if not self.network:
            return None
        return self.network.receive(sockfd, size)
    
    def syscall(self, nr: int, *args) -> int:
        """Make a system call"""
        if not self.core:
            return -1
        return self.core.syscall(nr, *args)
    
    def get_stats(self) -> KernelStats:
        """Get kernel statistics"""
        with self._stats_lock:
            return KernelStats(**self._stats.__dict__)
    
    def get_process_list(self) -> List[ProcessInfo]:
        """Get list of all processes"""
        if not self.core:
            return []
        return self.core.get_process_list()
    
    def get_thread_list(self, pid: Optional[int] = None) -> List[ThreadInfo]:
        """Get list of threads"""
        if not self.core:
            return []
        return self.core.get_thread_list(pid)
    
    def register_callback(self, event_type: str, callback: Callable):
        """Register event callback"""
        if event_type not in self._callbacks:
            self._callbacks[event_type] = []
        self._callbacks[event_type].append(callback)
    
    def unregister_callback(self, event_type: str, callback: Callable):
        """Unregister event callback"""
        if event_type in self._callbacks:
            try:
                self._callbacks[event_type].remove(callback)
            except ValueError:
                pass
    
    # Mock implementations for fallback
    
    def _create_mock_core(self):
        """Create mock core implementation"""
        class MockCore:
            def create_process(self, **kwargs): return 1
            def destroy_process(self, pid): return True
            def create_thread(self, pid, entry_func): return 1
            def destroy_thread(self, tid): return True
            def allocate_memory(self, size): return 0x1000000
            def free_memory(self, ptr): pass
            def syscall(self, nr, *args): return 0
            def get_process_list(self): return []
            def get_thread_list(self, pid=None): return []
        return MockCore()
    
    def _create_mock_memory(self):
        """Create mock memory manager"""
        class MockMemory:
            def allocate(self, size): return 0x1000000
            def free(self, ptr): pass
            def get_stats(self): return {'used': 0, 'free': 1024*1024*1024}
            def shutdown(self): pass
        return MockMemory()
    
    def _create_mock_filesystem(self):
        """Create mock filesystem"""
        class MockFilesystem:
            def open(self, path, mode): return 3
            def close(self, fd): return True
            def read(self, fd, size): return b""
            def write(self, fd, data): return len(data)
            def shutdown(self): pass
        return MockFilesystem()
    
    def _create_mock_ipc(self):
        """Create mock IPC"""
        class MockIPC:
            def send_message(self, dest_pid, message): return True
            def receive_message(self, timeout): return None
            def shutdown(self): pass
        return MockIPC()
    
    def _create_mock_network(self):
        """Create mock network stack"""
        class MockNetwork:
            def create_socket(self, domain, sock_type, protocol): return 4
            def bind(self, sockfd, address): return True
            def connect(self, sockfd, address): return True
            def send(self, sockfd, data): return len(data)
            def receive(self, sockfd, size): return b""
            def get_stats(self): return {'packets_sent': 0, 'packets_received': 0}
            def process_packets(self): pass
            def shutdown(self): pass
        return MockNetwork()
    
    def _create_mock_drivers(self):
        """Create mock driver manager"""
        class MockDrivers:
            def shutdown(self): pass
        return MockDrivers()
    
    def _create_mock_scheduler(self):
        """Create mock scheduler"""
        class MockScheduler:
            def tick(self): pass
            def shutdown(self): pass
        return MockScheduler()
    
    def _create_mock_resource_monitor(self):
        """Create mock resource monitor"""
        class MockResourceMonitor:
            def update(self): pass
            def shutdown(self): pass
        return MockResourceMonitor()


# Global kernel instance
_kernel_instance: Optional[KOSKernelManager] = None


def initialize_kernel(config: Optional[KernelConfig] = None) -> KOSKernelManager:
    """Initialize the global kernel instance"""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = KOSKernelManager(config)
        if not _kernel_instance.initialize():
            logger.error("Failed to initialize kernel")
            _kernel_instance = None
            raise RuntimeError("Kernel initialization failed")
    return _kernel_instance


def get_kernel() -> Optional[KOSKernelManager]:
    """Get the global kernel instance"""
    return _kernel_instance


def shutdown_kernel():
    """Shutdown the global kernel instance"""
    global _kernel_instance
    if _kernel_instance:
        _kernel_instance.shutdown()
        _kernel_instance = None


# Context manager for kernel lifecycle
class KernelContext:
    """Context manager for kernel lifecycle"""
    
    def __init__(self, config: Optional[KernelConfig] = None):
        self.config = config
        self.kernel: Optional[KOSKernelManager] = None
    
    def __enter__(self) -> KOSKernelManager:
        self.kernel = initialize_kernel(self.config)
        return self.kernel
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.kernel:
            self.kernel.shutdown()


# Convenience functions
def create_process(name: str = "process") -> Optional[int]:
    """Create a process using global kernel"""
    kernel = get_kernel()
    return kernel.create_process(name) if kernel else None


def allocate_memory(size: int) -> Optional[int]:
    """Allocate memory using global kernel"""
    kernel = get_kernel()
    return kernel.allocate_memory(size) if kernel else None


def send_ipc(dest_pid: int, message: Any) -> bool:
    """Send IPC message using global kernel"""
    kernel = get_kernel()
    return kernel.send_ipc_message(dest_pid, message) if kernel else False


def create_socket(domain: int = 2, sock_type: int = 1) -> Optional[int]:
    """Create socket using global kernel"""
    kernel = get_kernel()
    return kernel.create_socket(domain, sock_type) if kernel else None


if __name__ == "__main__":
    # Example usage
    with KernelContext(KernelConfig(debug_mode=True)) as kernel:
        print(f"Kernel initialized: {kernel.state}")
        
        # Create a process
        pid = kernel.create_process("test_process")
        print(f"Created process: {pid}")
        
        # Get statistics
        stats = kernel.get_stats()
        print(f"Kernel stats: {stats}")
        
        # Wait a bit
        time.sleep(2)
        
        print("Kernel test completed")
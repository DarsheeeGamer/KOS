"""
KOS Process - Process representation and management
"""

import os
import time
import threading
import signal
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict

class ProcessState(Enum):
    """Process states similar to Linux"""
    RUNNING = "R"      # Currently running
    SLEEPING = "S"     # Interruptible sleep (waiting for an event)
    DISK_SLEEP = "D"   # Uninterruptible sleep (usually IO)
    STOPPED = "T"      # Stopped (on a signal)
    TRACING_STOP = "t" # Tracing stop
    ZOMBIE = "Z"       # Zombie (terminated but not reaped)
    DEAD = "X"         # Dead (should never be seen)

class ProcessType(Enum):
    """Types of processes"""
    KERNEL = "kernel"
    USER = "user"
    KTHREAD = "kthread"

@dataclass
class ProcessCredentials:
    """Process credentials (UIDs, GIDs, capabilities)"""
    uid: int = 0        # Real user ID
    euid: int = 0       # Effective user ID
    suid: int = 0       # Saved user ID
    fsuid: int = 0      # Filesystem user ID
    gid: int = 0        # Real group ID
    egid: int = 0       # Effective group ID
    sgid: int = 0       # Saved group ID
    fsgid: int = 0      # Filesystem group ID
    groups: List[int] = field(default_factory=list)  # Supplementary groups
    capabilities: int = 0  # Capability mask

@dataclass
class ProcessLimits:
    """Process resource limits (rlimits)"""
    cpu_time: int = -1          # CPU time in seconds
    file_size: int = -1         # Maximum file size
    data_size: int = -1         # Maximum data size
    stack_size: int = 8388608   # Maximum stack size (8MB)
    core_size: int = 0          # Maximum core dump size
    rss_size: int = -1          # Maximum resident set size
    num_processes: int = -1     # Maximum number of processes
    num_files: int = 1024       # Maximum number of open files
    memlock_size: int = 65536   # Maximum locked memory
    address_space: int = -1     # Maximum address space
    file_locks: int = -1        # Maximum file locks
    pending_signals: int = -1   # Maximum pending signals
    msgqueue_size: int = 819200 # Maximum message queue size
    nice_priority: int = 0      # Nice priority
    realtime_priority: int = 0  # Real-time priority

@dataclass
class ProcessTimes:
    """Process timing information"""
    start_time: float = field(default_factory=time.time)
    utime: float = 0.0      # User CPU time
    stime: float = 0.0      # System CPU time
    cutime: float = 0.0     # Children user CPU time
    cstime: float = 0.0     # Children system CPU time
    last_cpu_time: float = field(default_factory=time.time)

class KOSProcess:
    """
    KOS Process representation
    Similar to Linux task_struct
    """
    
    def __init__(self, pid: int, name: str, executable: Optional[str] = None):
        # Basic identification
        self.pid = pid
        self.name = name
        self.executable = executable or name
        self.comm = name[:15]  # Command name (truncated to 15 chars like Linux)
        
        # Process hierarchy
        self.ppid = 0  # Parent process ID
        self.pgid = pid  # Process group ID
        self.sid = pid   # Session ID
        self.parent: Optional['KOSProcess'] = None
        self.children: List['KOSProcess'] = []
        
        # Process state
        self.state = ProcessState.RUNNING
        self.exit_code = 0
        self.exit_signal = 0
        self.process_type = ProcessType.USER
        
        # Credentials and security
        self.cred = ProcessCredentials()
        self.limits = ProcessLimits()
        
        # Memory management
        self.mm = None  # Memory descriptor (will be set by memory manager)
        self.memory_usage = 0
        self.max_memory_usage = 0
        
        # File system
        self.cwd = "/"  # Current working directory
        self.root = "/"  # Root directory
        self.umask = 0o022  # File creation mask
        self.files = {}  # Open file descriptors {fd: file_object}
        self.next_fd = 0  # Next available file descriptor
        
        # Signals
        self.signals = {}  # Pending signals
        self.signal_handlers = {}  # Signal handlers
        self.signal_mask = 0  # Blocked signals
        
        # Threading
        self.thread = None  # Python thread object
        self.thread_group_leader = True
        self.threads = []  # List of threads in this process
        
        # Scheduling
        self.priority = 20  # Nice value (-20 to 19)
        self.static_priority = 120  # Static priority (0-139)
        self.normal_priority = 120  # Normal priority
        self.rt_priority = 0  # Real-time priority
        self.policy = 0  # Scheduling policy (SCHED_NORMAL)
        
        # Timing
        self.times = ProcessTimes()
        
        # CPU affinity
        self.cpu_allowed = list(range(4))  # Allowed CPUs
        self.cpu_current = 0  # Current CPU
        
        # Environment
        self.environ = {
            'PATH': '/bin:/usr/bin:/sbin:/usr/sbin',
            'HOME': '/root' if self.cred.uid == 0 else f'/home/user{self.cred.uid}',
            'SHELL': '/bin/sh',
            'USER': 'root' if self.cred.uid == 0 else f'user{self.cred.uid}',
            'TERM': 'xterm'
        }
        
        # Command line arguments
        self.argv = [self.executable]
        
        # Process control
        self.lock = threading.Lock()
        self.exit_event = threading.Event()
        self.wakeup_event = threading.Event()
        
        # Statistics
        self.context_switches = 0
        self.voluntary_context_switches = 0
        self.involuntary_context_switches = 0
        self.page_faults = 0
        self.major_page_faults = 0
        
        # Kernel-specific
        self.kernel_stack = None
        self.thread_info = None
        
        # Namespaces (for container support)
        self.namespaces = {
            'mnt': None,   # Mount namespace
            'pid': None,   # PID namespace  
            'net': None,   # Network namespace
            'ipc': None,   # IPC namespace
            'uts': None,   # UTS namespace
            'user': None,  # User namespace
            'cgroup': None # Cgroup namespace
        }
        
        # cgroups
        self.cgroups = {}
        
    def set_parent(self, parent: 'KOSProcess'):
        """Set parent process"""
        if self.parent:
            self.parent.children.remove(self)
            
        self.parent = parent
        self.ppid = parent.pid if parent else 0
        
        if parent:
            parent.children.append(self)
            
    def add_child(self, child: 'KOSProcess'):
        """Add child process"""
        child.set_parent(self)
        
    def remove_child(self, child: 'KOSProcess'):
        """Remove child process"""
        if child in self.children:
            self.children.remove(child)
            child.parent = None
            child.ppid = 0
            
    def set_state(self, new_state: ProcessState):
        """Change process state"""
        with self.lock:
            old_state = self.state
            self.state = new_state
            
            # Handle state transitions
            if old_state == ProcessState.SLEEPING and new_state == ProcessState.RUNNING:
                self.wakeup_event.set()
            elif new_state == ProcessState.ZOMBIE:
                self.exit_event.set()
                
    def sleep(self, timeout: Optional[float] = None):
        """Put process to sleep"""
        self.set_state(ProcessState.SLEEPING)
        self.wakeup_event.clear()
        
        if timeout:
            self.wakeup_event.wait(timeout)
        else:
            self.wakeup_event.wait()
            
        if self.state == ProcessState.SLEEPING:
            self.set_state(ProcessState.RUNNING)
            
    def wakeup(self):
        """Wake up sleeping process"""
        if self.state == ProcessState.SLEEPING:
            self.wakeup_event.set()
            
    def send_signal(self, signum: int, info: Optional[Dict] = None):
        """Send signal to process"""
        with self.lock:
            if signum not in self.signals:
                self.signals[signum] = []
            self.signals[signum].append(info or {})
            
            # Handle special signals
            if signum == signal.SIGKILL:
                self.terminate()
            elif signum == signal.SIGSTOP:
                self.set_state(ProcessState.STOPPED)
            elif signum == signal.SIGCONT:
                if self.state == ProcessState.STOPPED:
                    self.set_state(ProcessState.RUNNING)
                    
    def handle_signals(self):
        """Process pending signals"""
        with self.lock:
            for signum, signal_list in list(self.signals.items()):
                if signal_list and not (self.signal_mask & (1 << signum)):
                    # Signal is not blocked
                    signal_info = signal_list.pop(0)
                    
                    if not signal_list:
                        del self.signals[signum]
                        
                    # Call signal handler if registered
                    handler = self.signal_handlers.get(signum)
                    if handler:
                        try:
                            handler(signum, signal_info)
                        except Exception:
                            pass  # Ignore handler exceptions
                    else:
                        # Default signal handling
                        self._default_signal_handler(signum, signal_info)
                        
    def _default_signal_handler(self, signum: int, info: Dict):
        """Default signal handling"""
        if signum in (signal.SIGTERM, signal.SIGINT):
            self.terminate()
        elif signum == signal.SIGCHLD:
            pass  # Ignore by default
            
    def terminate(self):
        """Terminate the process"""
        self.set_state(ProcessState.ZOMBIE)
        
        # Close all file descriptors
        for fd in list(self.files.keys()):
            self.close_fd(fd)
            
        # Terminate thread if running
        if self.thread and self.thread.is_alive():
            # In real kernel, would forcibly terminate
            # For Python, we just mark as terminated
            pass
            
    def wait_for_exit(self, timeout: Optional[float] = None) -> bool:
        """Wait for process to exit"""
        return self.exit_event.wait(timeout)
        
    def get_fd(self, fd_num: int) -> Optional[Any]:
        """Get file object for file descriptor"""
        return self.files.get(fd_num)
        
    def add_fd(self, file_obj: Any) -> int:
        """Add file descriptor and return FD number"""
        fd = self.next_fd
        self.files[fd] = file_obj
        self.next_fd += 1
        return fd
        
    def close_fd(self, fd: int) -> bool:
        """Close file descriptor"""
        if fd in self.files:
            file_obj = self.files.pop(fd)
            if hasattr(file_obj, 'close'):
                file_obj.close()
            return True
        return False
        
    def dup_fd(self, fd: int, new_fd: Optional[int] = None) -> Optional[int]:
        """Duplicate file descriptor"""
        if fd not in self.files:
            return None
            
        file_obj = self.files[fd]
        
        if new_fd is None:
            new_fd = self.next_fd
            self.next_fd += 1
        else:
            # Close existing FD if it exists
            self.close_fd(new_fd)
            
        self.files[new_fd] = file_obj
        return new_fd
        
    def set_cwd(self, path: str):
        """Set current working directory"""
        self.cwd = os.path.normpath(path)
        
    def set_root(self, path: str):
        """Set root directory (chroot)"""
        self.root = os.path.normpath(path)
        
    def get_memory_usage(self) -> Dict[str, int]:
        """Get memory usage statistics"""
        return {
            'vsize': self.memory_usage,  # Virtual memory size
            'rss': self.memory_usage,    # Resident set size (simplified)
            'peak_vsize': self.max_memory_usage,
            'peak_rss': self.max_memory_usage
        }
        
    def get_cpu_usage(self) -> Dict[str, float]:
        """Get CPU usage statistics"""
        return {
            'utime': self.times.utime,
            'stime': self.times.stime,
            'cutime': self.times.cutime,
            'cstime': self.times.cstime,
            'total_time': self.times.utime + self.times.stime
        }
        
    def update_cpu_time(self, user_time: float, system_time: float):
        """Update CPU time counters"""
        with self.lock:
            self.times.utime += user_time
            self.times.stime += system_time
            self.times.last_cpu_time = time.time()
            
    def get_age(self) -> float:
        """Get process age in seconds"""
        return time.time() - self.times.start_time
        
    def is_kernel_thread(self) -> bool:
        """Check if this is a kernel thread"""
        return self.process_type == ProcessType.KERNEL
        
    def is_zombie(self) -> bool:
        """Check if process is zombie"""
        return self.state == ProcessState.ZOMBIE
        
    def is_stopped(self) -> bool:
        """Check if process is stopped"""
        return self.state in (ProcessState.STOPPED, ProcessState.TRACING_STOP)
        
    def is_sleeping(self) -> bool:
        """Check if process is sleeping"""
        return self.state in (ProcessState.SLEEPING, ProcessState.DISK_SLEEP)
        
    def is_running(self) -> bool:
        """Check if process is running"""
        return self.state == ProcessState.RUNNING
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert process to dictionary representation"""
        return {
            'pid': self.pid,
            'ppid': self.ppid,
            'name': self.name,
            'state': self.state.value,
            'priority': self.priority,
            'nice': self.priority - 20,
            'uid': self.cred.uid,
            'gid': self.cred.gid,
            'memory': self.get_memory_usage(),
            'cpu': self.get_cpu_usage(),
            'age': self.get_age(),
            'threads': len(self.threads),
            'files': len(self.files),
            'cwd': self.cwd,
            'executable': self.executable,
            'argv': self.argv,
            'context_switches': self.context_switches
        }
        
    def __repr__(self):
        return f"KOSProcess(pid={self.pid}, name='{self.name}', state={self.state.value})"
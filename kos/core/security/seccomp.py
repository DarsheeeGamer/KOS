"""
Seccomp System Call Filtering for KOS

This module implements a Seccomp-like system call filtering mechanism for KOS,
allowing fine-grained control over which system calls processes can execute.

Features:
- System call filtering profiles
- Whitelist and blacklist modes
- Container integration
- Predefined profiles for common use cases
"""

import os
import json
import logging
import threading
from enum import Enum, auto
from typing import Dict, List, Set, Optional, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
SECCOMP_PROFILES_DIR = os.path.join(KOS_ROOT, 'etc/seccomp')

# Ensure directories exist
os.makedirs(SECCOMP_PROFILES_DIR, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class SeccompAction(str, Enum):
    """Actions to take when a syscall matches a rule."""
    ALLOW = "allow"
    KILL = "kill"
    TRAP = "trap"
    ERRNO = "errno"
    LOG = "log"


class SeccompMode(str, Enum):
    """Filter modes for seccomp profiles."""
    WHITELIST = "whitelist"  # Only allow listed syscalls
    BLACKLIST = "blacklist"  # Allow all except listed syscalls


class SeccompFilter:
    """
    Represents a seccomp filter for system calls.
    
    A filter defines which system calls are allowed or denied,
    and what action to take when a denied syscall is attempted.
    """
    
    def __init__(self, name: str, mode: SeccompMode = SeccompMode.WHITELIST,
                default_action: SeccompAction = SeccompAction.ERRNO):
        """
        Initialize a seccomp filter.
        
        Args:
            name: Filter name
            mode: Filter mode (whitelist or blacklist)
            default_action: Default action for non-matching syscalls
        """
        self.name = name
        self.mode = mode
        self.default_action = default_action
        self.syscalls = {}  # syscall_name -> action
    
    def add_rule(self, syscall: str, action: SeccompAction = SeccompAction.ALLOW) -> None:
        """
        Add a rule for a system call.
        
        Args:
            syscall: System call name
            action: Action to take
        """
        self.syscalls[syscall] = action
    
    def remove_rule(self, syscall: str) -> bool:
        """
        Remove a rule for a system call.
        
        Args:
            syscall: System call name
            
        Returns:
            bool: Whether the rule was removed
        """
        if syscall in self.syscalls:
            del self.syscalls[syscall]
            return True
        return False
    
    def check_syscall(self, syscall: str) -> SeccompAction:
        """
        Check if a system call is allowed by this filter.
        
        Args:
            syscall: System call name
            
        Returns:
            SeccompAction: Action to take
        """
        if self.mode == SeccompMode.WHITELIST:
            # In whitelist mode, syscalls must be explicitly allowed
            return self.syscalls.get(syscall, self.default_action)
        else:
            # In blacklist mode, syscalls are allowed unless explicitly denied
            return self.syscalls.get(syscall, SeccompAction.ALLOW)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the filter to a dictionary.
        
        Returns:
            Dict representation of the filter
        """
        return {
            "name": self.name,
            "mode": self.mode,
            "default_action": self.default_action,
            "syscalls": self.syscalls
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SeccompFilter':
        """
        Create a filter from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            SeccompFilter object
        """
        filter = SeccompFilter(
            data["name"],
            SeccompMode(data["mode"]),
            SeccompAction(data["default_action"])
        )
        
        for syscall, action in data.get("syscalls", {}).items():
            filter.add_rule(syscall, SeccompAction(action))
        
        return filter


class SeccompManager:
    """
    Manages seccomp filters for KOS.
    
    This class handles the creation, storage, and enforcement of
    seccomp filters for system call filtering.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SeccompManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the SeccompManager."""
        if self._initialized:
            return
        
        self._initialized = True
        self.filters = self._load_filters()
        self._ensure_default_filters()
    
    def _load_filters(self) -> Dict[str, SeccompFilter]:
        """Load seccomp filters from disk."""
        filters = {}
        
        if os.path.exists(SECCOMP_PROFILES_DIR):
            for filename in os.listdir(SECCOMP_PROFILES_DIR):
                if not filename.endswith('.json'):
                    continue
                
                path = os.path.join(SECCOMP_PROFILES_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        filter = SeccompFilter.from_dict(data)
                        filters[filter.name] = filter
                except Exception as e:
                    logger.error(f"Failed to load filter {filename}: {e}")
        
        return filters
    
    def _save_filter(self, filter: SeccompFilter):
        """Save a seccomp filter to disk."""
        try:
            path = os.path.join(SECCOMP_PROFILES_DIR, f"{filter.name}.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(filter.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save filter {filter.name}: {e}")
    
    def _ensure_default_filters(self):
        """Ensure default seccomp filters exist."""
        # Default minimal filter
        if "minimal" not in self.filters:
            minimal = SeccompFilter("minimal", SeccompMode.WHITELIST, SeccompAction.KILL)
            
            # Essential syscalls for basic operation
            for syscall in [
                "read", "write", "open", "close", "stat", "fstat", "lstat",
                "poll", "lseek", "mmap", "mprotect", "munmap", "brk",
                "rt_sigaction", "rt_sigprocmask", "rt_sigreturn",
                "ioctl", "pread64", "pwrite64", "readv", "writev",
                "access", "pipe", "select", "sched_yield", "mremap",
                "msync", "mincore", "madvise", "shmget", "shmat",
                "shmctl", "dup", "dup2", "pause", "nanosleep", "getitimer",
                "alarm", "setitimer", "getpid", "sendfile", "socket",
                "connect", "accept", "sendto", "recvfrom", "sendmsg",
                "recvmsg", "shutdown", "bind", "listen", "getsockname",
                "getpeername", "socketpair", "setsockopt", "getsockopt",
                "clone", "fork", "vfork", "execve", "exit", "wait4",
                "kill", "uname", "semget", "semop", "semctl", "shmdt",
                "msgget", "msgsnd", "msgrcv", "msgctl", "fcntl", "flock",
                "fsync", "fdatasync", "truncate", "ftruncate", "getdents",
                "getcwd", "chdir", "fchdir", "rename", "mkdir", "rmdir",
                "creat", "link", "unlink", "symlink", "readlink", "chmod",
                "fchmod", "chown", "fchown", "lchown", "umask", "gettimeofday",
                "getrlimit", "getrusage", "sysinfo", "times", "ptrace",
                "getuid", "syslog", "getgid", "setuid", "setgid", "geteuid",
                "getegid", "setpgid", "getppid", "getpgrp", "setsid",
                "setreuid", "setregid", "getgroups", "setgroups", "setresuid",
                "getresuid", "setresgid", "getresgid", "getpgid", "setfsuid",
                "setfsgid", "getsid", "capget", "capset", "rt_sigpending",
                "rt_sigtimedwait", "rt_sigqueueinfo", "rt_sigsuspend",
                "sigaltstack", "utime", "mknod", "uselib", "personality",
                "ustat", "statfs", "fstatfs", "sysfs", "getpriority",
                "setpriority", "sched_setparam", "sched_getparam",
                "sched_setscheduler", "sched_getscheduler", "sched_get_priority_max",
                "sched_get_priority_min", "sched_rr_get_interval", "mlock",
                "munlock", "mlockall", "munlockall", "vhangup", "modify_ldt",
                "pivot_root", "_sysctl", "prctl", "arch_prctl", "adjtimex",
                "setrlimit", "chroot", "sync", "acct", "settimeofday",
                "mount", "umount2", "swapon", "swapoff", "reboot", "sethostname",
                "setdomainname", "iopl", "ioperm", "create_module",
                "init_module", "delete_module", "get_kernel_syms",
                "query_module", "quotactl", "nfsservctl", "getpmsg",
                "putpmsg", "afs_syscall", "tuxcall", "security", "gettid",
                "readahead", "setxattr", "lsetxattr", "fsetxattr",
                "getxattr", "lgetxattr", "fgetxattr", "listxattr",
                "llistxattr", "flistxattr", "removexattr", "lremovexattr",
                "fremovexattr", "tkill", "time", "futex", "sched_setaffinity",
                "sched_getaffinity", "set_thread_area", "io_setup",
                "io_destroy", "io_getevents", "io_submit", "io_cancel",
                "get_thread_area", "lookup_dcookie", "epoll_create",
                "epoll_ctl_old", "epoll_wait_old", "remap_file_pages",
                "getdents64", "set_tid_address", "restart_syscall",
                "semtimedop", "fadvise64", "timer_create", "timer_settime",
                "timer_gettime", "timer_getoverrun", "timer_delete",
                "clock_settime", "clock_gettime", "clock_getres",
                "clock_nanosleep", "exit_group", "epoll_wait", "epoll_ctl",
                "tgkill", "utimes", "vserver", "mbind", "set_mempolicy",
                "get_mempolicy", "mq_open", "mq_unlink", "mq_timedsend",
                "mq_timedreceive", "mq_notify", "mq_getsetattr",
                "kexec_load", "waitid", "add_key", "request_key",
                "keyctl", "ioprio_set", "ioprio_get", "inotify_init",
                "inotify_add_watch", "inotify_rm_watch", "migrate_pages",
                "openat", "mkdirat", "mknodat", "fchownat", "futimesat",
                "newfstatat", "unlinkat", "renameat", "linkat", "symlinkat",
                "readlinkat", "fchmodat", "faccessat", "pselect6",
                "ppoll", "unshare", "set_robust_list", "get_robust_list",
                "splice", "tee", "sync_file_range", "vmsplice", "move_pages",
                "utimensat", "epoll_pwait", "signalfd", "timerfd_create",
                "eventfd", "fallocate", "timerfd_settime", "timerfd_gettime",
                "accept4", "signalfd4", "eventfd2", "epoll_create1",
                "dup3", "pipe2", "inotify_init1", "preadv", "pwritev",
                "rt_tgsigqueueinfo", "perf_event_open", "recvmmsg",
                "fanotify_init", "fanotify_mark", "prlimit64",
                "name_to_handle_at", "open_by_handle_at", "clock_adjtime",
                "syncfs", "sendmmsg", "setns", "getcpu", "process_vm_readv",
                "process_vm_writev", "kcmp", "finit_module", "sched_setattr",
                "sched_getattr", "renameat2", "seccomp", "getrandom",
                "memfd_create", "kexec_file_load", "bpf", "execveat",
                "userfaultfd", "membarrier", "mlock2", "copy_file_range",
                "preadv2", "pwritev2", "pkey_mprotect", "pkey_alloc",
                "pkey_free", "statx"
            ]:
                minimal.add_rule(syscall, SeccompAction.ALLOW)
            
            self.filters["minimal"] = minimal
            self._save_filter(minimal)
        
        # Default container filter
        if "container" not in self.filters:
            container = SeccompFilter("container", SeccompMode.BLACKLIST, SeccompAction.ERRNO)
            
            # Deny potentially dangerous syscalls
            for syscall in [
                "reboot", "mount", "umount", "swapon", "swapoff",
                "init_module", "delete_module", "create_module",
                "kexec_load", "kexec_file_load", "syslog", "acct",
                "settimeofday", "sethostname", "setdomainname",
                "iopl", "ioperm", "nfsservctl", "pivot_root",
                "ptrace", "capset", "bpf"
            ]:
                container.add_rule(syscall, SeccompAction.ERRNO)
            
            self.filters["container"] = container
            self._save_filter(container)
        
        # Default strict filter
        if "strict" not in self.filters:
            strict = SeccompFilter("strict", SeccompMode.WHITELIST, SeccompAction.KILL)
            
            # Only the most essential syscalls
            for syscall in [
                "read", "write", "open", "close", "stat", "fstat", "lstat",
                "poll", "lseek", "mmap", "mprotect", "munmap", "brk",
                "rt_sigaction", "rt_sigprocmask", "rt_sigreturn",
                "ioctl", "pread64", "pwrite64", "readv", "writev",
                "access", "pipe", "select", "sched_yield", "mremap",
                "msync", "mincore", "madvise", "dup", "dup2",
                "nanosleep", "getpid", "socket", "connect", "accept",
                "sendto", "recvfrom", "sendmsg", "recvmsg", "shutdown",
                "bind", "listen", "getsockname", "getpeername",
                "socketpair", "execve", "exit", "exit_group", "wait4",
                "kill", "uname", "fcntl", "flock", "fsync", "fdatasync",
                "truncate", "ftruncate", "getdents", "getcwd", "chdir",
                "rename", "mkdir", "rmdir", "creat", "link", "unlink",
                "symlink", "readlink", "chmod", "fchmod", "gettimeofday",
                "getuid", "getgid", "geteuid", "getegid", "setuid",
                "setgid", "getrlimit", "getrusage", "clock_gettime",
                "clock_getres", "epoll_create", "epoll_ctl", "epoll_wait",
                "openat", "mkdirat", "fchownat", "newfstatat", "unlinkat",
                "renameat", "linkat", "symlinkat", "readlinkat", "fchmodat",
                "faccessat"
            ]:
                strict.add_rule(syscall, SeccompAction.ALLOW)
            
            self.filters["strict"] = strict
            self._save_filter(strict)
    
    def get_filter(self, name: str) -> Optional[SeccompFilter]:
        """
        Get a seccomp filter by name.
        
        Args:
            name: Filter name
            
        Returns:
            SeccompFilter or None if not found
        """
        return self.filters.get(name)
    
    def add_filter(self, filter: SeccompFilter) -> bool:
        """
        Add or update a seccomp filter.
        
        Args:
            filter: Seccomp filter
            
        Returns:
            bool: Success or failure
        """
        try:
            self.filters[filter.name] = filter
            self._save_filter(filter)
            logger.info(f"Added/updated filter: {filter.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add/update filter: {e}")
            return False
    
    def remove_filter(self, name: str) -> bool:
        """
        Remove a seccomp filter.
        
        Args:
            name: Filter name
            
        Returns:
            bool: Success or failure
        """
        if name not in self.filters:
            logger.warning(f"Filter not found: {name}")
            return False
        
        try:
            path = os.path.join(SECCOMP_PROFILES_DIR, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            
            del self.filters[name]
            logger.info(f"Removed filter: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove filter: {e}")
            return False
    
    def check_syscall(self, filter_name: str, syscall: str) -> SeccompAction:
        """
        Check if a system call is allowed by a filter.
        
        Args:
            filter_name: Filter name
            syscall: System call name
            
        Returns:
            SeccompAction: Action to take
        """
        filter = self.filters.get(filter_name)
        if not filter:
            logger.warning(f"Filter not found: {filter_name}")
            return SeccompAction.ALLOW  # Allow if filter doesn't exist
        
        return filter.check_syscall(syscall)
    
    def apply_filter(self, filter_name: str, pid: int = 0) -> bool:
        """
        Apply a seccomp filter to a process.
        
        In a real implementation, this would use prctl() and seccomp()
        syscalls to apply the filter to the specified process.
        
        Args:
            filter_name: Filter name
            pid: Process ID (0 for current process)
            
        Returns:
            bool: Success or failure
        """
        filter = self.filters.get(filter_name)
        if not filter:
            logger.error(f"Filter not found: {filter_name}")
            return False
        
        # In a real implementation, this would apply the filter to the process
        # For our simulation, we'll just log it
        logger.info(f"Applied filter {filter_name} to process {pid or 'current'}")
        
        from ..audit import AuditManager, AuditEventType
        audit = AuditManager()
        audit.log_event(
            AuditEventType.SECCOMP_VIOLATION,
            "system",
            {
                "filter": filter_name,
                "pid": pid or "current"
            },
            True
        )
        
        return True

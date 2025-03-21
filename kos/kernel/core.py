#!/usr/bin/env python3
"""
KOS Kernel Core - Main kernel implementation providing system services and APIs

This module implements the core kernel functionality including:
- Process management and scheduling
- Memory management
- Device management
- Inter-process communication
- System call interface
- Security and access control
"""

import logging
import time
import threading
import queue
import uuid
import signal
import os
import sys
import platform
import psutil
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union, Set, Tuple
from dataclasses import dataclass, field

# Set up kernel logging
logger = logging.getLogger('KOS.Kernel')

# Kernel constants
KERNEL_VERSION = "1.0.0"
MAX_PROCESSES = 1000
DEFAULT_PRIORITY = 10
MAX_PRIORITY = 20
SCHEDULER_INTERVAL = 0.1  # seconds

# Process states
PROCESS_CREATED = 'created'
PROCESS_RUNNING = 'running'
PROCESS_WAITING = 'waiting'
PROCESS_SLEEPING = 'sleeping'
PROCESS_ZOMBIE = 'zombie'
PROCESS_TERMINATED = 'terminated'

# Signal types (similar to POSIX signals)
KSIGINT = 2   # Terminal interrupt signal
KSIGKILL = 9  # Kill signal (cannot be caught)
KSIGTERM = 15 # Termination signal
KSIGSTOP = 17 # Stop process signal
KSIGCONT = 18 # Continue process signal

# Kernel panic codes
PANIC_MEMORY = 1
PANIC_PROCESS = 2
PANIC_FILESYSTEM = 3
PANIC_SECURITY = 4
PANIC_UNKNOWN = 255

# Security levels
SECURITY_LOW = 0
SECURITY_MEDIUM = 1
SECURITY_HIGH = 2

@dataclass
class KernelProcess:
    """Represents a process in the KOS kernel"""
    pid: int
    name: str
    owner: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = "/"
    priority: int = DEFAULT_PRIORITY
    state: str = PROCESS_CREATED
    parent_pid: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    cpu_usage: float = 0.0
    memory_usage: int = 0
    thread: Optional[threading.Thread] = None
    result_queue: queue.Queue = field(default_factory=queue.Queue)
    children: List[int] = field(default_factory=list)
    file_descriptors: Dict[int, Any] = field(default_factory=dict)
    signal_handlers: Dict[int, Callable] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize default signal handlers"""
        self.signal_handlers = {
            KSIGINT: self._default_sigint_handler,
            KSIGTERM: self._default_sigterm_handler
        }
    
    def _default_sigint_handler(self):
        """Default SIGINT handler - terminate process"""
        self.state = PROCESS_TERMINATED
        self.exit_code = 130  # 128 + SIGINT
        return True
    
    def _default_sigterm_handler(self):
        """Default SIGTERM handler - terminate process"""
        self.state = PROCESS_TERMINATED
        self.exit_code = 143  # 128 + SIGTERM
        return True
    
    def register_signal_handler(self, signal_type: int, handler: Callable) -> bool:
        """Register a custom signal handler"""
        if signal_type == KSIGKILL:
            return False  # SIGKILL cannot be caught
        self.signal_handlers[signal_type] = handler
        return True
    
    def send_signal(self, signal_type: int) -> bool:
        """Process a signal sent to this process"""
        # Some signals can't be caught or ignored
        if signal_type == KSIGKILL:
            self.state = PROCESS_TERMINATED
            self.exit_code = 137  # 128 + SIGKILL
            return True
            
        if signal_type == KSIGSTOP:
            self.state = PROCESS_WAITING
            return True
            
        if signal_type == KSIGCONT and self.state == PROCESS_WAITING:
            self.state = PROCESS_RUNNING
            return True
            
        # Process other signals with registered handlers
        if signal_type in self.signal_handlers:
            try:
                return self.signal_handlers[signal_type]()
            except Exception as e:
                logger.error(f"Signal handler error for PID {self.pid}: {e}")
                # If signal handler fails, default to termination
                self.state = PROCESS_TERMINATED
                self.exit_code = 1
                return True
                
        return False  # Signal not handled
    
    def get_runtime(self) -> float:
        """Get the runtime of the process in seconds"""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def add_child(self, child_pid: int) -> None:
        """Add a child process PID"""
        if child_pid not in self.children:
            self.children.append(child_pid)
    
    def remove_child(self, child_pid: int) -> None:
        """Remove a child process PID"""
        if child_pid in self.children:
            self.children.remove(child_pid)
    
    def allocate_fd(self, resource: Any) -> int:
        """Allocate a new file descriptor for a resource"""
        # Find the lowest unused fd number
        fd = 3  # Start after stdin(0), stdout(1), stderr(2)
        while fd in self.file_descriptors:
            fd += 1
        self.file_descriptors[fd] = resource
        return fd
    
    def get_fd(self, fd: int) -> Optional[Any]:
        """Get the resource associated with a file descriptor"""
        return self.file_descriptors.get(fd)
    
    def close_fd(self, fd: int) -> bool:
        """Close a file descriptor"""
        if fd in self.file_descriptors:
            del self.file_descriptors[fd]
            return True
        return False


class KernelScheduler:
    """Process scheduler for the KOS kernel"""
    
    def __init__(self):
        self.processes: Dict[int, KernelProcess] = {}
        self.next_pid = 1
        self.scheduler_thread = None
        self.running = False
        self.process_lock = threading.RLock()
        self.zombie_reaper = None
        self.scheduler_interval = SCHEDULER_INTERVAL
        self.runqueue: List[int] = []  # PIDs of processes in running state
        
    def start(self) -> None:
        """Start the scheduler"""
        if self.running:
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
            name="KernelScheduler"
        )
        self.scheduler_thread.start()
        
        self.zombie_reaper = threading.Thread(
            target=self._reap_zombies,
            daemon=True,
            name="ZombieReaper"
        )
        self.zombie_reaper.start()
        
        logger.info("Kernel scheduler started")
        
    def stop(self) -> None:
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=2.0)
        if self.zombie_reaper:
            self.zombie_reaper.join(timeout=2.0)
        logger.info("Kernel scheduler stopped")
        
    def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        while self.running:
            try:
                self._schedule_processes()
                time.sleep(self.scheduler_interval)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                
    def _schedule_processes(self) -> None:
        """Select processes to run and update their states"""
        with self.process_lock:
            # Update runqueue
            self.runqueue = [
                pid for pid, proc in self.processes.items()
                if proc.state == PROCESS_RUNNING
            ]
            
            # Simple priority-based scheduling
            self.runqueue.sort(
                key=lambda pid: self.processes[pid].priority,
                reverse=True  # Higher priority first
            )
            
            # Update process stats
            for pid in self.runqueue:
                proc = self.processes.get(pid)
                if proc:
                    # Simulate process execution by updating stats
                    proc.cpu_usage = min(100.0, proc.cpu_usage + random.uniform(-5, 5))
                    if proc.cpu_usage < 0:
                        proc.cpu_usage = 0.0
                    
                    # Simulate memory usage fluctuation
                    proc.memory_usage = max(1024, proc.memory_usage + random.randint(-1024, 1024))
                    
    def _reap_zombies(self) -> None:
        """Reap zombie processes periodically"""
        while self.running:
            try:
                with self.process_lock:
                    # Find zombie processes
                    zombie_pids = [
                        pid for pid, proc in self.processes.items()
                        if proc.state == PROCESS_ZOMBIE
                    ]
                    
                    # Reap zombies
                    for pid in zombie_pids:
                        proc = self.processes.get(pid)
                        if proc and proc.parent_pid:
                            # Notify parent of child termination
                            parent = self.processes.get(proc.parent_pid)
                            if parent:
                                parent.remove_child(pid)
                        
                        # Remove zombie process
                        logger.debug(f"Reaping zombie process PID {pid}")
                        del self.processes[pid]
                        
            except Exception as e:
                logger.error(f"Zombie reaper error: {e}")
                
            time.sleep(1.0)  # Check zombies every second
            
    def create_process(self, 
                      name: str, 
                      owner: str, 
                      command: str, 
                      args: List[str] = None, 
                      env: Dict[str, str] = None, 
                      cwd: str = "/", 
                      parent_pid: Optional[int] = None, 
                      priority: int = DEFAULT_PRIORITY) -> Optional[int]:
        """Create a new process"""
        with self.process_lock:
            if len(self.processes) >= MAX_PROCESSES:
                logger.error("Cannot create process: maximum process limit reached")
                return None
                
            # Validate priority
            if priority < 0:
                priority = 0
            elif priority > MAX_PRIORITY:
                priority = MAX_PRIORITY
                
            # Create the process
            pid = self.next_pid
            self.next_pid += 1
            
            process = KernelProcess(
                pid=pid,
                name=name,
                owner=owner,
                command=command,
                args=args or [],
                env=env or {},
                cwd=cwd,
                priority=priority,
                state=PROCESS_CREATED,
                parent_pid=parent_pid
            )
            
            self.processes[pid] = process
            
            # Add as child to parent
            if parent_pid and parent_pid in self.processes:
                self.processes[parent_pid].add_child(pid)
                
            logger.debug(f"Created process PID {pid}: {name}")
            return pid
            
    def start_process(self, pid: int, target_func: Callable, args: tuple = (), kwargs: dict = None) -> bool:
        """Start a process with the given target function"""
        with self.process_lock:
            if pid not in self.processes:
                logger.error(f"Cannot start non-existent process PID {pid}")
                return False
                
            process = self.processes[pid]
            if process.state != PROCESS_CREATED:
                logger.error(f"Cannot start process PID {pid}: invalid state {process.state}")
                return False
                
            kwargs = kwargs or {}
                
            def process_wrapper():
                try:
                    # Execute the target function
                    result = target_func(*args, **kwargs)
                    # Store the result
                    process.result_queue.put(result)
                    # Mark as terminated successfully
                    with self.process_lock:
                        if pid in self.processes:
                            process.state = PROCESS_TERMINATED
                            process.exit_code = 0
                            process.end_time = datetime.now()
                except Exception as e:
                    logger.error(f"Process PID {pid} error: {e}")
                    # Store the exception
                    process.result_queue.put(e)
                    # Mark as terminated with error
                    with self.process_lock:
                        if pid in self.processes:
                            process.state = PROCESS_TERMINATED
                            process.exit_code = 1
                            process.end_time = datetime.now()
                            
            # Create and start the process thread
            process.thread = threading.Thread(
                target=process_wrapper,
                daemon=True,
                name=f"Process-{pid}"
            )
            process.state = PROCESS_RUNNING
            process.thread.start()
            
            logger.debug(f"Started process PID {pid}")
            return True
            
    def terminate_process(self, pid: int, force: bool = False) -> bool:
        """Terminate a process"""
        with self.process_lock:
            if pid not in self.processes:
                logger.error(f"Cannot terminate non-existent process PID {pid}")
                return False
                
            process = self.processes[pid]
            
            # Send appropriate signal
            if force:
                process.send_signal(KSIGKILL)
            else:
                process.send_signal(KSIGTERM)
                
            # If process is already terminated or it's a forced kill, mark as terminated
            if process.state in [PROCESS_TERMINATED, PROCESS_ZOMBIE] or force:
                process.state = PROCESS_TERMINATED
                process.exit_code = process.exit_code or (137 if force else 143)
                process.end_time = process.end_time or datetime.now()
                logger.debug(f"Terminated process PID {pid}")
                
                # Mark for cleanup
                process.state = PROCESS_ZOMBIE
                return True
                
            return False  # Not terminated immediately
            
    def terminate_all(self, force: bool = True) -> None:
        """Terminate all processes"""
        with self.process_lock:
            # Get a copy of PIDs to avoid modification during iteration
            pids = list(self.processes.keys())
            
            for pid in pids:
                self.terminate_process(pid, force=force)
                
    def wait_for_process(self, pid: int, timeout: Optional[float] = None) -> Tuple[bool, Optional[Any]]:
        """Wait for a process to complete and return its result"""
        with self.process_lock:
            if pid not in self.processes:
                logger.error(f"Cannot wait for non-existent process PID {pid}")
                return False, None
                
            process = self.processes[pid]
            
        # Wait for process to complete
        try:
            result = process.result_queue.get(block=True, timeout=timeout)
            return True, result
        except queue.Empty:
            return False, None
            
    def get_process(self, pid: int) -> Optional[KernelProcess]:
        """Get a process by PID"""
        with self.process_lock:
            return self.processes.get(pid)
            
    def list_processes(self) -> List[KernelProcess]:
        """List all processes"""
        with self.process_lock:
            return list(self.processes.values())
            
    def get_process_tree(self) -> Dict[int, List[int]]:
        """Get the process tree"""
        tree = {}
        with self.process_lock:
            for pid, process in self.processes.items():
                parent_pid = process.parent_pid or 0
                if parent_pid not in tree:
                    tree[parent_pid] = []
                tree[parent_pid].append(pid)
        return tree
        
    def send_signal_to_process(self, pid: int, signal_type: int) -> bool:
        """Send a signal to a process"""
        with self.process_lock:
            if pid not in self.processes:
                logger.error(f"Cannot send signal to non-existent process PID {pid}")
                return False
                
            process = self.processes[pid]
            return process.send_signal(signal_type)


class KernelMemoryManager:
    """Memory management for KOS kernel"""
    
    def __init__(self, total_memory: int = 1024 * 1024 * 1024):  # 1GB virtual memory
        self.total_memory = total_memory
        self.allocated_memory = 0
        self.memory_map = {}  # address -> (size, owner)
        self.memory_lock = threading.RLock()
        
    def allocate(self, size: int, owner: str) -> Optional[int]:
        """Allocate memory of given size"""
        with self.memory_lock:
            if size <= 0:
                return None
                
            if self.allocated_memory + size > self.total_memory:
                logger.error(f"Memory allocation failed: out of memory")
                return None
                
            # Simple memory allocation strategy - just increment address
            address = self.allocated_memory
            self.allocated_memory += size
            self.memory_map[address] = (size, owner)
            
            return address
            
    def free(self, address: int) -> bool:
        """Free memory at given address"""
        with self.memory_lock:
            if address not in self.memory_map:
                return False
                
            size, _ = self.memory_map[address]
            del self.memory_map[address]
            
            # In a real system we'd need to handle fragmentation
            # Here we just pretend memory was freed
            
            return True
            
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory usage information"""
        with self.memory_lock:
            free_memory = self.total_memory - self.allocated_memory
            return {
                "total": self.total_memory,
                "allocated": self.allocated_memory,
                "free": free_memory,
                "percent_used": (self.allocated_memory / self.total_memory) * 100,
                "allocations": len(self.memory_map)
            }
            
    def get_allocation_by_owner(self) -> Dict[str, int]:
        """Get memory usage by owner"""
        with self.memory_lock:
            usage = {}
            for _, (size, owner) in self.memory_map.items():
                if owner not in usage:
                    usage[owner] = 0
                usage[owner] += size
            return usage


class KernelIPCManager:
    """Inter-Process Communication for KOS kernel"""
    
    def __init__(self):
        self.message_queues = {}  # queue_name -> Queue
        self.shared_memory = {}   # segment_name -> (data, size, owners)
        self.semaphores = {}      # semaphore_name -> (value, waiters)
        self.pipes = {}           # pipe_id -> (read_queue, write_queue)
        self.ipc_lock = threading.RLock()
        
    def create_message_queue(self, name: str, max_size: int = 100) -> bool:
        """Create a new message queue"""
        with self.ipc_lock:
            if name in self.message_queues:
                return False
                
            self.message_queues[name] = queue.Queue(maxsize=max_size)
            return True
            
    def send_message(self, queue_name: str, message: Any, timeout: Optional[float] = None) -> bool:
        """Send a message to a queue"""
        with self.ipc_lock:
            if queue_name not in self.message_queues:
                return False
                
        # Release lock before blocking operation
        try:
            self.message_queues[queue_name].put(message, block=True, timeout=timeout)
            return True
        except queue.Full:
            return False
            
    def receive_message(self, queue_name: str, timeout: Optional[float] = None) -> Tuple[bool, Any]:
        """Receive a message from a queue"""
        with self.ipc_lock:
            if queue_name not in self.message_queues:
                return False, None
                
        # Release lock before blocking operation
        try:
            message = self.message_queues[queue_name].get(block=True, timeout=timeout)
            return True, message
        except queue.Empty:
            return False, None
            
    def delete_message_queue(self, name: str) -> bool:
        """Delete a message queue"""
        with self.ipc_lock:
            if name not in self.message_queues:
                return False
                
            del self.message_queues[name]
            return True
            
    def create_shared_memory(self, name: str, size: int, owner: str) -> bool:
        """Create a shared memory segment"""
        with self.ipc_lock:
            if name in self.shared_memory:
                return False
                
            self.shared_memory[name] = (bytearray(size), size, set([owner]))
            return True
            
    def attach_shared_memory(self, name: str, owner: str) -> Optional[bytearray]:
        """Attach to a shared memory segment"""
        with self.ipc_lock:
            if name not in self.shared_memory:
                return None
                
            data, size, owners = self.shared_memory[name]
            owners.add(owner)
            return data
            
    def detach_shared_memory(self, name: str, owner: str) -> bool:
        """Detach from a shared memory segment"""
        with self.ipc_lock:
            if name not in self.shared_memory:
                return False
                
            _, _, owners = self.shared_memory[name]
            if owner in owners:
                owners.remove(owner)
            
            # If no more owners, remove the segment
            if not owners:
                del self.shared_memory[name]
                
            return True
            
    def create_pipe(self) -> Optional[int]:
        """Create a new pipe and return its ID"""
        with self.ipc_lock:
            pipe_id = len(self.pipes) + 1
            read_queue = queue.Queue()
            write_queue = queue.Queue()
            
            self.pipes[pipe_id] = (read_queue, write_queue)
            return pipe_id
            
    def pipe_read(self, pipe_id: int, timeout: Optional[float] = None) -> Tuple[bool, Any]:
        """Read from a pipe"""
        with self.ipc_lock:
            if pipe_id not in self.pipes:
                return False, None
                
            read_queue, _ = self.pipes[pipe_id]
            
        # Release lock before blocking operation
        try:
            data = read_queue.get(block=True, timeout=timeout)
            return True, data
        except queue.Empty:
            return False, None
            
    def pipe_write(self, pipe_id: int, data: Any, timeout: Optional[float] = None) -> bool:
        """Write to a pipe"""
        with self.ipc_lock:
            if pipe_id not in self.pipes:
                return False
                
            _, write_queue = self.pipes[pipe_id]
            
        # Release lock before blocking operation
        try:
            write_queue.put(data, block=True, timeout=timeout)
            return True
        except queue.Full:
            return False
            
    def close_pipe(self, pipe_id: int) -> bool:
        """Close a pipe"""
        with self.ipc_lock:
            if pipe_id not in self.pipes:
                return False
                
            del self.pipes[pipe_id]
            return True


class KernelSecurityManager:
    """Security management for KOS kernel"""
    
    def __init__(self):
        self.security_level = SECURITY_MEDIUM
        self.access_controls = {}  # resource -> {owner: permissions}
        self.capabilities = {}     # user -> [capabilities]
        self.security_lock = threading.RLock()
        self.security_log = []
        self.max_security_log = 1000
        
    def set_security_level(self, level: int) -> bool:
        """Set the system security level"""
        with self.security_lock:
            if level not in [SECURITY_LOW, SECURITY_MEDIUM, SECURITY_HIGH]:
                return False
                
            self.security_level = level
            self.log_security_event("Security level changed", f"New level: {level}")
            return True
            
    def log_security_event(self, event_type: str, details: str, user: str = "system") -> None:
        """Log a security event"""
        with self.security_lock:
            timestamp = datetime.now()
            self.security_log.append({
                "timestamp": timestamp,
                "type": event_type,
                "details": details,
                "user": user
            })
            
            # Trim log if it gets too long
            if len(self.security_log) > self.max_security_log:
                self.security_log = self.security_log[-self.max_security_log:]
                
    def get_security_log(self, max_entries: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get the security log"""
        with self.security_lock:
            if max_entries:
                return self.security_log[-max_entries:]
            return self.security_log.copy()
            
    def set_resource_permissions(self, resource: str, owner: str, permissions: int) -> bool:
        """Set permissions for a resource"""
        with self.security_lock:
            if resource not in self.access_controls:
                self.access_controls[resource] = {}
                
            self.access_controls[resource][owner] = permissions
            return True
            
    def check_access(self, resource: str, user: str, requested_perm: int) -> bool:
        """Check if user has access to a resource"""
        with self.security_lock:
            # Root always has access if security level is not high
            if user == "kaede" and self.security_level != SECURITY_HIGH:
                return True
                
            if resource not in self.access_controls:
                return False
                
            if user not in self.access_controls[resource]:
                return False
                
            user_perms = self.access_controls[resource][user]
            return (user_perms & requested_perm) == requested_perm
            
    def grant_capability(self, user: str, capability: str) -> bool:
        """Grant a capability to a user"""
        with self.security_lock:
            if user not in self.capabilities:
                self.capabilities[user] = []
                
            if capability not in self.capabilities[user]:
                self.capabilities[user].append(capability)
                self.log_security_event("Capability granted", 
                                      f"User: {user}, Capability: {capability}")
            return True
            
    def revoke_capability(self, user: str, capability: str) -> bool:
        """Revoke a capability from a user"""
        with self.security_lock:
            if user not in self.capabilities:
                return False
                
            if capability in self.capabilities[user]:
                self.capabilities[user].remove(capability)
                self.log_security_event("Capability revoked", 
                                       f"User: {user}, Capability: {capability}")
            return True
            
    def has_capability(self, user: str, capability: str) -> bool:
        """Check if a user has a capability"""
        with self.security_lock:
            # Root has all capabilities if security level is not high
            if user == "kaede" and self.security_level != SECURITY_HIGH:
                return True
                
            if user not in self.capabilities:
                return False
                
            return capability in self.capabilities[user]
            
    def encrypt_data(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption for data"""
        from itertools import cycle
        key_cycle = cycle(key)
        return bytes(a ^ b for a, b in zip(data, key_cycle))
        
    def decrypt_data(self, encrypted_data: bytes, key: bytes) -> bytes:
        """Simple XOR decryption for data (same as encryption)"""
        return self.encrypt_data(encrypted_data, key)  # XOR is its own inverse


class KernelSyscallManager:
    """System call manager for KOS kernel"""
    
    def __init__(self, scheduler, memory_manager, ipc_manager, security_manager):
        self.scheduler = scheduler
        self.memory_manager = memory_manager
        self.ipc_manager = ipc_manager
        self.security_manager = security_manager
        self.syscall_count = 0
        self.syscall_stats = {}  # syscall_name -> count
        self.syscall_lock = threading.RLock()
        
    def _register_syscall(self, name: str) -> None:
        """Register a syscall for statistics"""
        with self.syscall_lock:
            self.syscall_count += 1
            if name not in self.syscall_stats:
                self.syscall_stats[name] = 0
            self.syscall_stats[name] += 1
            
    def get_syscall_stats(self) -> Dict[str, Any]:
        """Get syscall statistics"""
        with self.syscall_lock:
            return {
                "total": self.syscall_count,
                "by_type": self.syscall_stats.copy()
            }
            
    # Process-related syscalls
    
    def sys_fork(self, pid: int, name: str) -> Optional[int]:
        """Fork a process"""
        self._register_syscall("fork")
        process = self.scheduler.get_process(pid)
        if not process:
            return None
            
        # Create new process as a copy of the parent
        child_pid = self.scheduler.create_process(
            name=f"{name}_fork",
            owner=process.owner,
            command=process.command,
            args=process.args.copy(),
            env=process.env.copy(),
            cwd=process.cwd,
            parent_pid=pid
        )
        
        return child_pid
        
    def sys_exit(self, pid: int, status: int = 0) -> bool:
        """Exit a process"""
        self._register_syscall("exit")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        process.exit_code = status
        process.state = PROCESS_TERMINATED
        process.end_time = datetime.now()
        
        # Mark for cleanup
        process.state = PROCESS_ZOMBIE
        
        return True
        
    def sys_wait(self, pid: int, child_pid: Optional[int] = None) -> Tuple[bool, Optional[int], Optional[int]]:
        """Wait for a child process to terminate"""
        self._register_syscall("wait")
        process = self.scheduler.get_process(pid)
        if not process:
            return False, None, None
            
        if child_pid:
            # Wait for specific child
            child = self.scheduler.get_process(child_pid)
            if not child or child.parent_pid != pid:
                return False, None, None
                
            if child.state == PROCESS_TERMINATED or child.state == PROCESS_ZOMBIE:
                return True, child_pid, child.exit_code
                
            return False, None, None
            
        else:
            # Wait for any child
            for cpid in process.children:
                child = self.scheduler.get_process(cpid)
                if child and (child.state == PROCESS_TERMINATED or child.state == PROCESS_ZOMBIE):
                    return True, cpid, child.exit_code
                    
            return False, None, None
            
    # Memory-related syscalls
    
    def sys_allocate_memory(self, pid: int, size: int) -> Optional[int]:
        """Allocate memory for a process"""
        self._register_syscall("allocate_memory")
        process = self.scheduler.get_process(pid)
        if not process:
            return None
            
        address = self.memory_manager.allocate(size, f"pid_{pid}")
        if address is not None:
            process.memory_usage += size
            
        return address
        
    def sys_free_memory(self, pid: int, address: int) -> bool:
        """Free memory for a process"""
        self._register_syscall("free_memory")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        return self.memory_manager.free(address)
        
    # IPC-related syscalls
    
    def sys_create_pipe(self, pid: int) -> Optional[int]:
        """Create a pipe"""
        self._register_syscall("create_pipe")
        process = self.scheduler.get_process(pid)
        if not process:
            return None
            
        return self.ipc_manager.create_pipe()
        
    def sys_pipe_read(self, pid: int, pipe_id: int, timeout: Optional[float] = None) -> Tuple[bool, Any]:
        """Read from a pipe"""
        self._register_syscall("pipe_read")
        process = self.scheduler.get_process(pid)
        if not process:
            return False, None
            
        return self.ipc_manager.pipe_read(pipe_id, timeout)
        
    def sys_pipe_write(self, pid: int, pipe_id: int, data: Any, timeout: Optional[float] = None) -> bool:
        """Write to a pipe"""
        self._register_syscall("pipe_write")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        return self.ipc_manager.pipe_write(pipe_id, data, timeout)
        
    def sys_send_signal(self, pid: int, target_pid: int, signal: int) -> bool:
        """Send a signal to a process"""
        self._register_syscall("send_signal")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        # Check permissions - only root or owner can send signals
        target = self.scheduler.get_process(target_pid)
        if not target:
            return False
            
        if process.owner != "kaede" and process.owner != target.owner:
            # Log security event
            self.security_manager.log_security_event(
                "Permission denied", 
                f"Process {pid} tried to send signal to {target_pid}",
                process.owner
            )
            return False
            
        return self.scheduler.send_signal_to_process(target_pid, signal)
        
    # Filesystem-related syscalls - these would interface with a filesystem module
    
    def sys_open(self, pid: int, path: str, flags: int) -> Optional[int]:
        """Open a file"""
        self._register_syscall("open")
        # In a real implementation, this would interface with a filesystem module
        # For now, just return a dummy file descriptor
        process = self.scheduler.get_process(pid)
        if not process:
            return None
            
        # Dummy file object
        file_obj = {"path": path, "flags": flags, "position": 0}
        return process.allocate_fd(file_obj)
        
    def sys_close(self, pid: int, fd: int) -> bool:
        """Close a file descriptor"""
        self._register_syscall("close")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        return process.close_fd(fd)
        
    # Security-related syscalls
    
    def sys_check_permission(self, pid: int, resource: str, permission: int) -> bool:
        """Check if process has permission for a resource"""
        self._register_syscall("check_permission")
        process = self.scheduler.get_process(pid)
        if not process:
            return False
            
        return self.security_manager.check_access(resource, process.owner, permission)


class KernelDeviceManager:
    """Device management for KOS kernel"""
    
    def __init__(self):
        self.devices = {}  # device_id -> device_info
        self.device_drivers = {}  # driver_name -> driver_function
        self.device_lock = threading.RLock()
        self.device_counter = 0
        
    def register_device(self, name: str, device_type: str, driver: str, properties: Dict[str, Any] = None) -> int:
        """Register a new device"""
        with self.device_lock:
            device_id = self.device_counter
            self.device_counter += 1
            
            self.devices[device_id] = {
                "id": device_id,
                "name": name,
                "type": device_type,
                "driver": driver,
                "properties": properties or {},
                "status": "registered"
            }
            
            logger.info(f"Registered device: {name} (ID: {device_id}, Type: {device_type})")
            return device_id
            
    def get_device(self, device_id: int) -> Optional[Dict[str, Any]]:
        """Get a device by ID"""
        with self.device_lock:
            return self.devices.get(device_id)
            
    def list_devices(self, device_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all devices, optionally filtered by type"""
        with self.device_lock:
            if device_type:
                return [device for device in self.devices.values() if device["type"] == device_type]
            return list(self.devices.values())
            
    def register_driver(self, name: str, driver_func: Callable) -> bool:
        """Register a device driver"""
        with self.device_lock:
            if name in self.device_drivers:
                return False
                
            self.device_drivers[name] = driver_func
            logger.info(f"Registered device driver: {name}")
            return True
            
    def get_driver(self, name: str) -> Optional[Callable]:
        """Get a device driver by name"""
        with self.device_lock:
            return self.device_drivers.get(name)
            
    def call_driver(self, device_id: int, operation: str, *args, **kwargs) -> Any:
        """Call a device driver for a device operation"""
        with self.device_lock:
            device = self.devices.get(device_id)
            if not device:
                logger.error(f"Device not found: {device_id}")
                return None
                
            driver_name = device["driver"]
            driver_func = self.device_drivers.get(driver_name)
            
            if not driver_func:
                logger.error(f"Driver not found: {driver_name}")
                return None
                
        # Release lock before calling the driver
        try:
            return driver_func(device, operation, *args, **kwargs)
        except Exception as e:
            logger.error(f"Driver error for device {device_id}: {e}")
            return None


class KernelNetworkManager:
    """Network management for KOS kernel"""
    
    def __init__(self):
        self.interfaces = {}  # interface_name -> interface_info
        self.connections = {}  # connection_id -> connection_info
        self.routes = []  # List of routing entries
        self.network_lock = threading.RLock()
        self.connection_counter = 0
        self.packet_stats = {
            "sent": 0,
            "received": 0,
            "dropped": 0,
            "errors": 0
        }
        
    def register_interface(self, name: str, interface_type: str, properties: Dict[str, Any] = None) -> bool:
        """Register a network interface"""
        with self.network_lock:
            if name in self.interfaces:
                return False
                
            self.interfaces[name] = {
                "name": name,
                "type": interface_type,
                "properties": properties or {},
                "status": "down",
                "stats": {
                    "sent_packets": 0,
                    "received_packets": 0,
                    "sent_bytes": 0,
                    "received_bytes": 0,
                    "errors": 0
                }
            }
            
            logger.info(f"Registered network interface: {name} (Type: {interface_type})")
            return True
            
    def set_interface_status(self, name: str, status: str) -> bool:
        """Set the status of a network interface"""
        with self.network_lock:
            if name not in self.interfaces:
                return False
                
            self.interfaces[name]["status"] = status
            logger.info(f"Network interface {name} status changed to {status}")
            return True
            
    def get_interface(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a network interface by name"""
        with self.network_lock:
            return self.interfaces.get(name)
            
    def list_interfaces(self) -> List[Dict[str, Any]]:
        """List all network interfaces"""
        with self.network_lock:
            return list(self.interfaces.values())
            
    def create_connection(self, interface: str, protocol: str, local_addr: str, remote_addr: str) -> Optional[int]:
        """Create a network connection"""
        with self.network_lock:
            if interface not in self.interfaces:
                return None
                
            if self.interfaces[interface]["status"] != "up":
                return None
                
            connection_id = self.connection_counter
            self.connection_counter += 1
            
            self.connections[connection_id] = {
                "id": connection_id,
                "interface": interface,
                "protocol": protocol,
                "local_address": local_addr,
                "remote_address": remote_addr,
                "status": "established",
                "created_time": datetime.now(),
                "stats": {
                    "sent_packets": 0,
                    "received_packets": 0,
                    "sent_bytes": 0,
                    "received_bytes": 0
                }
            }
            
            logger.info(f"Created network connection: {connection_id} ({protocol} {local_addr} -> {remote_addr})")
            return connection_id
            
    def close_connection(self, connection_id: int) -> bool:
        """Close a network connection"""
        with self.network_lock:
            if connection_id not in self.connections:
                return False
                
            self.connections[connection_id]["status"] = "closed"
            logger.info(f"Closed network connection: {connection_id}")
            return True
            
    def send_packet(self, connection_id: int, data: bytes) -> bool:
        """Send data over a network connection"""
        with self.network_lock:
            if connection_id not in self.connections:
                return False
                
            connection = self.connections[connection_id]
            if connection["status"] != "established":
                return False
                
            # Update statistics
            connection["stats"]["sent_packets"] += 1
            connection["stats"]["sent_bytes"] += len(data)
            
            interface_name = connection["interface"]
            if interface_name in self.interfaces:
                self.interfaces[interface_name]["stats"]["sent_packets"] += 1
                self.interfaces[interface_name]["stats"]["sent_bytes"] += len(data)
                
            self.packet_stats["sent"] += 1
            
            # In a real implementation, this would actually transmit data
            # For now, just pretend it worked
            
            return True
            
    def receive_packet(self, connection_id: int, data: bytes) -> bool:
        """Simulate receiving data on a network connection"""
        with self.network_lock:
            if connection_id not in self.connections:
                self.packet_stats["dropped"] += 1
                return False
                
            connection = self.connections[connection_id]
            if connection["status"] != "established":
                self.packet_stats["dropped"] += 1
                return False
                
            # Update statistics
            connection["stats"]["received_packets"] += 1
            connection["stats"]["received_bytes"] += len(data)
            
            interface_name = connection["interface"]
            if interface_name in self.interfaces:
                self.interfaces[interface_name]["stats"]["received_packets"] += 1
                self.interfaces[interface_name]["stats"]["received_bytes"] += len(data)
                
            self.packet_stats["received"] += 1
            
            return True
            
    def add_route(self, destination: str, gateway: str, interface: str, metric: int = 1) -> bool:
        """Add a network route"""
        with self.network_lock:
            if interface not in self.interfaces:
                return False
                
            # Check for duplicate routes
            for route in self.routes:
                if route["destination"] == destination and route["interface"] == interface:
                    return False
                    
            self.routes.append({
                "destination": destination,
                "gateway": gateway,
                "interface": interface,
                "metric": metric,
                "added_time": datetime.now()
            })
            
            logger.info(f"Added network route: {destination} via {gateway} (interface: {interface})")
            return True
            
    def remove_route(self, destination: str, interface: str) -> bool:
        """Remove a network route"""
        with self.network_lock:
            for i, route in enumerate(self.routes):
                if route["destination"] == destination and route["interface"] == interface:
                    del self.routes[i]
                    logger.info(f"Removed network route: {destination} (interface: {interface})")
                    return True
                    
            return False
            
    def get_network_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        with self.network_lock:
            return {
                "interfaces": len(self.interfaces),
                "active_connections": sum(1 for conn in self.connections.values() if conn["status"] == "established"),
                "total_connections": len(self.connections),
                "routes": len(self.routes),
                "packets": self.packet_stats.copy()
            }


class KernelPanicManager:
    """Kernel panic handling for KOS kernel"""
    
    def __init__(self):
        self.panic_history = []
        self.panic_mode = False
        self.panic_lock = threading.RLock()
        
    def panic(self, code: int, reason: str, source: str = "kernel") -> None:
        """Initiate a kernel panic"""
        with self.panic_lock:
            if self.panic_mode:
                # Already in panic mode, just log it
                logger.critical(f"Additional panic while in panic mode: {reason}")
                return
                
            self.panic_mode = True
            timestamp = datetime.now()
            
            panic_info = {
                "timestamp": timestamp,
                "code": code,
                "reason": reason,
                "source": source
            }
            
            self.panic_history.append(panic_info)
            
            logger.critical(f"KERNEL PANIC: {reason} (code: {code}, source: {source})")
            
            # In a real kernel, this would halt the system
            # For our simulation, we'll just log it
            
    def is_in_panic_mode(self) -> bool:
        """Check if the kernel is in panic mode"""
        with self.panic_lock:
            return self.panic_mode
            
    def get_panic_history(self) -> List[Dict[str, Any]]:
        """Get the panic history"""
        with self.panic_lock:
            return self.panic_history.copy()
            
    def reset_panic_mode(self) -> bool:
        """Reset the panic mode (only for simulation)"""
        with self.panic_lock:
            if not self.panic_mode:
                return False
                
            self.panic_mode = False
            logger.warning("Kernel panic mode reset (this would require a reboot in a real kernel)")
            return True


class KOSKernel:
    """Main KOS Kernel class that integrates all kernel subsystems"""
    
    def __init__(self, process_manager=None):
        self.kernel_start_time = datetime.now()
        self.system_name = "KOS"
        self.kernel_version = KERNEL_VERSION
        self.process_manager = process_manager
        
        # Initialize kernel subsystems
        self.scheduler = KernelScheduler()
        self.memory_manager = KernelMemoryManager()
        self.ipc_manager = KernelIPCManager()
        self.security_manager = KernelSecurityManager()
        self.syscall_manager = KernelSyscallManager(
            self.scheduler, self.memory_manager, self.ipc_manager, self.security_manager
        )
        self.device_manager = KernelDeviceManager()
        self.network_manager = KernelNetworkManager()
        self.panic_manager = KernelPanicManager()
        
        # Kernel status
        self.is_running = False
        self.boot_time = None
        
        logger.info(f"KOS Kernel {KERNEL_VERSION} initialized")
        
    def start(self) -> bool:
        """Start the kernel and all subsystems"""
        if self.is_running:
            logger.warning("Kernel already running")
            return False
            
        try:
            logger.info("Starting KOS Kernel...")
            
            # Start scheduler
            self.scheduler.start()
            
            # Set kernel startup time
            self.boot_time = datetime.now()
            self.is_running = True
            
            logger.info(f"KOS Kernel started successfully")
            return True
            
        except Exception as e:
            logger.critical(f"Failed to start kernel: {e}")
            self.panic_manager.panic(PANIC_UNKNOWN, f"Kernel start failed: {e}")
            return False
            
    def stop(self) -> bool:
        """Stop the kernel and all subsystems"""
        if not self.is_running:
            logger.warning("Kernel not running")
            return False
            
        try:
            logger.info("Stopping KOS Kernel...")
            
            # Terminate all processes
            self.scheduler.terminate_all(force=True)
            
            # Stop scheduler
            self.scheduler.stop()
            
            self.is_running = False
            logger.info("KOS Kernel stopped")
            return True
            
        except Exception as e:
            logger.critical(f"Failed to stop kernel cleanly: {e}")
            return False
            
    def get_uptime(self) -> float:
        """Get kernel uptime in seconds"""
        if not self.boot_time:
            return 0.0
        return (datetime.now() - self.boot_time).total_seconds()
        
    def get_kernel_info(self) -> Dict[str, Any]:
        """Get kernel information"""
        uptime = self.get_uptime()
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return {
            "system_name": self.system_name,
            "kernel_version": self.kernel_version,
            "boot_time": self.boot_time,
            "uptime": uptime,
            "uptime_str": f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}",
            "scheduler_running": self.scheduler.running,
            "process_count": len(self.scheduler.processes),
            "memory_usage": self.memory_manager.get_memory_info(),
            "security_level": self.security_manager.security_level,
            "syscall_count": self.syscall_manager.syscall_count
        }
        
    def register_builtin_devices(self) -> None:
        """Register built-in devices"""
        # Register simulated devices
        self.device_manager.register_device(
            name="console",
            device_type="tty",
            driver="tty_driver",
            properties={"columns": 80, "lines": 25}
        )
        
        self.device_manager.register_device(
            name="null",
            device_type="char",
            driver="null_driver"
        )
        
        self.device_manager.register_device(
            name="zero",
            device_type="char",
            driver="zero_driver"
        )
        
        self.device_manager.register_device(
            name="random",
            device_type="char",
            driver="random_driver"
        )
        
        # Register network interfaces
        self.network_manager.register_interface(
            name="lo",
            interface_type="loopback",
            properties={"address": "127.0.0.1", "netmask": "255.0.0.0"}
        )
        
        self.network_manager.register_interface(
            name="eth0",
            interface_type="ethernet",
            properties={"address": "192.168.1.100", "netmask": "255.255.255.0"}
        )
        
        # Set interfaces as up
        self.network_manager.set_interface_status("lo", "up")
        self.network_manager.set_interface_status("eth0", "up")
        
        # Add default route
        self.network_manager.add_route(
            destination="0.0.0.0/0",
            gateway="192.168.1.1",
            interface="eth0"
        )
        
    def _null_driver(self, device, operation, *args, **kwargs):
        """Driver for /dev/null"""
        if operation == "write":
            # Discard all data
            return len(args[0]) if args else 0
        elif operation == "read":
            # Return empty data
            size = args[0] if args else 0
            return b''
            
    def _zero_driver(self, device, operation, *args, **kwargs):
        """Driver for /dev/zero"""
        if operation == "write":
            # Discard all data
            return len(args[0]) if args else 0
        elif operation == "read":
            # Return zeros
            size = args[0] if args else 0
            return b'\0' * size
            
    def _random_driver(self, device, operation, *args, **kwargs):
        """Driver for /dev/random"""
        import random
        if operation == "write":
            # Discard all data
            return len(args[0]) if args else 0
        elif operation == "read":
            # Return random data
            size = args[0] if args else 0
            return bytes(random.randint(0, 255) for _ in range(size))
            
    def _tty_driver(self, device, operation, *args, **kwargs):
        """Driver for TTY devices"""
        if operation == "write":
            # Write to console (simulate by printing)
            data = args[0] if args else b''
            try:
                print(data.decode('utf-8', errors='replace'), end='')
            except:
                pass
            return len(data)
        elif operation == "read":
            # Read from console (simulate by returning empty data)
            size = args[0] if args else 0
            return b''
            
    def register_builtin_drivers(self) -> None:
        """Register built-in device drivers"""
        self.device_manager.register_driver("null_driver", self._null_driver)
        self.device_manager.register_driver("zero_driver", self._zero_driver)
        self.device_manager.register_driver("random_driver", self._random_driver)
        self.device_manager.register_driver("tty_driver", self._tty_driver)
        
    def initialize(self) -> bool:
        """Initialize the kernel fully"""
        try:
            # Register built-in drivers
            self.register_builtin_drivers()
            
            # Register built-in devices
            self.register_builtin_devices()
            
            # Start the kernel
            return self.start()
            
        except Exception as e:
            logger.critical(f"Kernel initialization failed: {e}")
            self.panic_manager.panic(PANIC_UNKNOWN, f"Initialization failed: {e}")
            return False


# Global kernel instance
_kernel_instance = None

def get_kernel(process_manager=None) -> KOSKernel:
    """Get the global kernel instance, creating it if needed"""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = KOSKernel(process_manager)
    return _kernel_instance

# For testing directly
if __name__ == "__main__":
    import random
    logging.basicConfig(level=logging.INFO)
    
    print("Initializing KOS Kernel...")
    kernel = get_kernel()
    
    if kernel.initialize():
        print("Kernel initialized successfully!")
        
        # Print kernel info
        info = kernel.get_kernel_info()
        print(f"System: {info['system_name']} Kernel v{info['kernel_version']}")
        print(f"Uptime: {info['uptime_str']}")
        
        # Create a test process
        pid = kernel.scheduler.create_process(
            name="test_process",
            owner="kaede",
            command="test",
            args=["arg1", "arg2"],
            priority=15
        )
        
        if pid:
            print(f"Created test process with PID {pid}")
            
            # Start the process with a simple function
            def test_func(a, b):
                print(f"Test process running with args: {a}, {b}")
                time.sleep(2)
                return a + b
                
            kernel.scheduler.start_process(pid, test_func, args=("Hello", "World"))
            
            # Wait for the process to complete
            success, result = kernel.scheduler.wait_for_process(pid)
            
            if success:
                print(f"Process completed with result: {result}")
            else:
                print("Process did not complete")
                
        # Stop the kernel
        kernel.stop()
        print("Kernel stopped")
    else:
        print("Failed to initialize kernel!")
"""
KOS Process Manager - Manages process creation, termination, and lifecycle
"""

import threading
import time
import signal
import os
from typing import Dict, List, Optional, Tuple, Callable, Any
from collections import defaultdict

from .process import KOSProcess, ProcessState, ProcessType
from .pid import PIDManager
from ..core.performance import ObjectPool, memoize, get_cpu_affinity, BatchProcessor

class KOSProcessManager:
    """
    Process manager for KOS
    Handles process creation, scheduling, and termination
    """
    
    def __init__(self, kernel: 'KOSKernel'):
        self.kernel = kernel
        self.processes: Dict[int, KOSProcess] = {}  # pid -> process
        self.process_tree: Dict[int, List[int]] = defaultdict(list)  # ppid -> [child_pids]
        
        # PID management
        self.pid_manager = PIDManager()
        
        # Process synchronization
        self.lock = threading.RLock()
        self.process_list_lock = threading.Lock()
        
        # Process statistics
        self.total_processes_created = 0
        self.total_processes_destroyed = 0
        self.max_processes = 32768
        
        # Process reaper for zombies
        self.reaper_thread = None
        self.reaper_running = False
        
        # Process groups and sessions
        self.process_groups: Dict[int, List[int]] = defaultdict(list)  # pgid -> [pids]
        self.sessions: Dict[int, List[int]] = defaultdict(list)  # sid -> [pids]
        
        # Init process (will be created later)
        self.init_process = None
        
        # Performance optimizations
        self._process_pool = ObjectPool(
            factory=lambda: KOSProcess(0, 0, "/bin/init", ProcessType.NORMAL),
            max_size=100
        )
        self._cpu_affinity = get_cpu_affinity()
        
        # Batch signal processing
        self._signal_batcher = BatchProcessor(
            process_func=self._process_signal_batch,
            batch_size=50,
            max_wait=0.01  # 10ms
        )
        
        # Start process reaper
        self._start_process_reaper()
        
    def create_kernel_process(self) -> KOSProcess:
        """Create the kernel process (PID 0)"""
        with self.lock:
            kernel_proc = KOSProcess(0, "kernel")
            kernel_proc.process_type = ProcessType.KERNEL
            kernel_proc.state = ProcessState.RUNNING
            kernel_proc.cred.uid = 0
            kernel_proc.cred.gid = 0
            
            self.processes[0] = kernel_proc
            self.total_processes_created += 1
            
            return kernel_proc
            
    def create_process(self, name: str, executable: str, args: List[str] = None,
                      env: Dict[str, str] = None, uid: int = 0, gid: int = 0,
                      parent_pid: Optional[int] = None, cwd: str = "/") -> Optional[KOSProcess]:
        """
        Create a new process
        """
        with self.lock:
            # Check process limits
            if len(self.processes) >= self.max_processes:
                return None
                
            # Allocate PID
            pid = self.pid_manager.alloc_pid()
            if pid is None:
                return None
                
            # Create process object
            process = KOSProcess(pid, name, executable)
            process.argv = args or [executable]
            process.cwd = cwd
            
            # Set credentials
            process.cred.uid = uid
            process.cred.euid = uid
            process.cred.gid = gid
            process.cred.egid = gid
            
            # Set environment
            if env:
                process.environ.update(env)
                
            # Set parent
            if parent_pid is not None:
                parent = self.processes.get(parent_pid)
                if parent:
                    process.set_parent(parent)
                    self.process_tree[parent_pid].append(pid)
                    
            # Add to process lists
            self.processes[pid] = process
            self.process_groups[process.pgid].append(pid)
            self.sessions[process.sid].append(pid)
            
            self.total_processes_created += 1
            
            # Special handling for init process
            if pid == 1:
                self.init_process = process
                
            return process
            
    def destroy_process(self, pid: int) -> bool:
        """
        Destroy a process and clean up resources
        """
        with self.lock:
            process = self.processes.get(pid)
            if not process:
                return False
                
            # Can't destroy kernel process
            if pid == 0:
                return False
                
            # Terminate the process
            process.terminate()
            
            # Reparent children to init
            if process.children:
                init_proc = self.processes.get(1)
                for child in process.children[:]:
                    if init_proc:
                        child.set_parent(init_proc)
                    else:
                        child.set_parent(None)
                        
            # Remove from parent's children
            if process.parent:
                process.parent.remove_child(process)
                
            # Remove from process tree
            if process.ppid in self.process_tree:
                if pid in self.process_tree[process.ppid]:
                    self.process_tree[process.ppid].remove(pid)
                    
            # Remove from process groups and sessions
            if pid in self.process_groups[process.pgid]:
                self.process_groups[process.pgid].remove(pid)
            if pid in self.sessions[process.sid]:
                self.sessions[process.sid].remove(pid)
                
            # Free PID
            self.pid_manager.free_pid(pid)
            
            # Remove from processes dict
            del self.processes[pid]
            
            self.total_processes_destroyed += 1
            
            return True
            
    def get_process(self, pid: int) -> Optional[KOSProcess]:
        """Get process by PID"""
        return self.processes.get(pid)
        
    def get_all_processes(self) -> List[KOSProcess]:
        """Get all processes"""
        with self.process_list_lock:
            return list(self.processes.values())
            
    def get_processes_by_name(self, name: str) -> List[KOSProcess]:
        """Get processes by name"""
        return [p for p in self.processes.values() if p.name == name]
        
    def get_processes_by_user(self, uid: int) -> List[KOSProcess]:
        """Get processes by user ID"""
        return [p for p in self.processes.values() if p.cred.uid == uid]
        
    def get_children(self, pid: int) -> List[KOSProcess]:
        """Get child processes"""
        process = self.processes.get(pid)
        return process.children if process else []
        
    def get_process_tree(self) -> Dict[int, List[int]]:
        """Get process tree structure"""
        return dict(self.process_tree)
        
    def kill_process(self, pid: int, signum: int = signal.SIGTERM) -> bool:
        """Send signal to process"""
        process = self.processes.get(pid)
        if process:
            process.send_signal(signum)
            return True
        return False
        
    def kill_process_group(self, pgid: int, signum: int = signal.SIGTERM) -> int:
        """Send signal to process group"""
        count = 0
        for pid in self.process_groups.get(pgid, []):
            if self.kill_process(pid, signum):
                count += 1
        return count
        
    def kill_all(self, signum: int = signal.SIGTERM):
        """Kill all user processes (except init and kernel)"""
        for pid, process in list(self.processes.items()):
            if pid > 1 and not process.is_kernel_thread():
                self.kill_process(pid, signum)
                
    def wait_for_process(self, pid: int, timeout: Optional[float] = None) -> Optional[Tuple[int, int]]:
        """
        Wait for process to exit
        Returns (pid, exit_code) or None if timeout
        """
        process = self.processes.get(pid)
        if not process:
            return None
            
        if process.wait_for_exit(timeout):
            return (pid, process.exit_code)
        return None
        
    def get_process_stats(self) -> Dict[str, int]:
        """Get process statistics"""
        stats = {
            'total': len(self.processes),
            'running': 0,
            'sleeping': 0,
            'stopped': 0,
            'zombie': 0,
            'kernel_threads': 0,
            'user_processes': 0
        }
        
        for process in self.processes.values():
            if process.state == ProcessState.RUNNING:
                stats['running'] += 1
            elif process.is_sleeping():
                stats['sleeping'] += 1
            elif process.is_stopped():
                stats['stopped'] += 1
            elif process.is_zombie():
                stats['zombie'] += 1
                
            if process.is_kernel_thread():
                stats['kernel_threads'] += 1
            else:
                stats['user_processes'] += 1
                
        return stats
        
    def get_load_average(self) -> Tuple[float, float, float]:
        """Calculate system load average"""
        # Simple load calculation based on running processes
        running_count = sum(1 for p in self.processes.values() 
                          if p.state == ProcessState.RUNNING)
        
        # In real system, this would be exponentially weighted moving average
        # For simulation, just return current running processes
        load = float(running_count)
        return (load, load, load)  # 1min, 5min, 15min
        
    def _start_process_reaper(self):
        """Start background thread to reap zombie processes"""
        def reaper():
            self.reaper_running = True
            while self.reaper_running:
                time.sleep(1.0)  # Check every second
                
                # Find zombie processes
                zombies = [p for p in self.processes.values() if p.is_zombie()]
                
                for zombie in zombies:
                    # Check if parent is waiting
                    if zombie.parent:
                        # In real system, would notify parent
                        pass
                    else:
                        # No parent, reap immediately
                        self.destroy_process(zombie.pid)
                        
        self.reaper_thread = threading.Thread(target=reaper, name="process-reaper", daemon=True)
        self.reaper_thread.start()
        
    def _stop_process_reaper(self):
        """Stop process reaper thread"""
        self.reaper_running = False
        if self.reaper_thread:
            self.reaper_thread.join(timeout=1.0)
            
    def dump_process_info(self) -> Dict[str, Any]:
        """Dump detailed process information"""
        info = {
            'process_count': len(self.processes),
            'total_created': self.total_processes_created,
            'total_destroyed': self.total_processes_destroyed,
            'max_processes': self.max_processes,
            'pid_manager': self.pid_manager.get_stats(),
            'load_average': self.get_load_average(),
            'stats': self.get_process_stats(),
            'processes': {}
        }
        
        # Add process details
        for pid, process in self.processes.items():
            info['processes'][pid] = process.to_dict()
            
        return info
    
    def _process_signal_batch(self, signals: List[Tuple[int, int]]):
        """Process batch of signals efficiently"""
        # Group signals by target process
        signal_groups = defaultdict(list)
        for pid, signum in signals:
            signal_groups[pid].append(signum)
        
        # Process each group
        with self.lock:
            for pid, signums in signal_groups.items():
                if pid in self.processes:
                    process = self.processes[pid]
                    for signum in signums:
                        process.send_signal(signum)
    
    @memoize(max_size=100, ttl=1.0)
    def get_process_stats_cached(self) -> Dict[str, Any]:
        """Get cached process statistics"""
        return self.get_process_stats()
    
    def set_process_affinity(self, pid: int, cpus: List[int]) -> bool:
        """Set CPU affinity for process"""
        with self.lock:
            if pid in self.processes:
                # Use performance module's CPU affinity
                try:
                    self._cpu_affinity.set_thread_affinity(cpus)
                    return True
                except Exception:
                    return False
        return False
        
    def get_system_resources(self) -> Dict[str, Any]:
        """Get system resource information from KOS kernel"""
        # Use KOS kernel resource monitor instead of host psutil
        from ..kernel.resource_monitor_wrapper import get_kernel_monitor
        
        try:
            monitor = get_kernel_monitor()
            return monitor.get_system_resources()
        except Exception as e:
            logger.warning(f"Failed to get kernel resources: {e}")
            # Fallback to basic implementation
            return {
                'cpu': {'percent': 0.0, 'count': 1},
                'memory': {
                    'virtual': {'total': 0, 'available': 0, 'percent': 0.0, 'used': 0, 'free': 0},
                    'swap': {'total': 0, 'used': 0, 'free': 0, 'percent': 0.0}
                },
                'disk': {
                    'usage': {'total': 0, 'used': 0, 'free': 0, 'percent': 0.0}
                },
                'network': {},
                'boot_time': time.time()
            }
            
    def __del__(self):
        """Cleanup when manager is destroyed"""
        self._stop_process_reaper()
        if hasattr(self, '_signal_batcher'):
            self._signal_batcher.stop()
# Alias for compatibility
ProcessManager = KOSProcessManager

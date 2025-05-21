"""
Enhanced process management and scheduling system with advanced features
"""
import os
import psutil
import time
from typing import Dict, List, Optional, Union, Any, TypedDict
from dataclasses import dataclass
from datetime import datetime
import logging
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache

logger = logging.getLogger('KOS.process')

class ResourceInfo(TypedDict):
    cpu: Dict[str, Union[float, int, Dict[str, float]]]
    memory: Dict[str, Dict[str, Union[float, int]]]
    disk: Dict[str, Dict[str, Union[float, int]]]
    network: Dict[str, Union[Dict[str, int], int]]

@dataclass
class Process:
    """Enhanced process information structure"""
    pid: int
    ppid: int
    name: str
    status: str
    username: str
    create_time: datetime
    cpu_percent: float
    memory_percent: float
    cmdline: List[str]
    priority: int = 0
    nice: int = 0
    threads: int = 1
    io_counters: Optional[Dict[str, int]] = None
    context_switches: Optional[Dict[str, int]] = None

class ProcessManager:
    """Enhanced process management system with advanced scheduling"""
    def __init__(self):
        self.processes: Dict[int, Process] = {}
        self._lock = Lock()
        self._process_cache = TTLCache(maxsize=1000, ttl=2)  # Cache process list for 2 seconds
        self._resource_cache = TTLCache(maxsize=100, ttl=1)  # Cache resource usage for 1 second
        self._executor = ThreadPoolExecutor(max_workers=4)  # For parallel processing
        logger.info("Enhanced process manager initialized")

    def refresh_processes(self, force: bool = False) -> None:
        """Update process list with optimized caching and parallel processing"""
        current_time = time.time()

        if not force and self.processes in self._process_cache:
            return self._process_cache[self.processes]

        with self._lock:
            try:
                processes = {}
                futures = []

                # Parallel process information gathering
                for proc in psutil.process_iter(['pid', 'ppid', 'name', 'username', 'status', 'cmdline']):
                    futures.append(
                        self._executor.submit(self._get_process_info, proc)
                    )

                # Collect results
                for future in futures:
                    try:
                        result = future.result(timeout=1)
                        if result:
                            processes[result.pid] = result
                    except Exception as e:
                        logger.error(f"Error collecting process info: {e}")

                self.processes = processes
                self._process_cache[self.processes] = processes
                logger.debug(f"Refreshed process list, found {len(processes)} processes")

            except Exception as e:
                logger.error(f"Error refreshing process list: {e}")
                raise

    def _get_process_info(self, proc: psutil.Process) -> Optional[Process]:
        """Get detailed process information with error handling"""
        try:
            pinfo = proc.info
            with proc.oneshot():  # Optimize system calls
                cpu_percent = proc.cpu_percent()
                memory_percent = proc.memory_percent()

                io_counters = None
                if hasattr(proc, 'io_counters'):
                    io = proc.io_counters()
                    io_counters = {
                        'read_count': io.read_count,
                        'write_count': io.write_count,
                        'read_bytes': io.read_bytes,
                        'write_bytes': io.write_bytes
                    }

                ctx_switches = None
                if hasattr(proc, 'num_ctx_switches'):
                    ctx = proc.num_ctx_switches()
                    ctx_switches = {
                        'voluntary': ctx.voluntary,
                        'involuntary': ctx.involuntary
                    }

                threads = proc.num_threads()
                nice = proc.nice()

            return Process(
                pid=proc.pid,
                ppid=pinfo['ppid'],
                name=pinfo['name'],
                status=pinfo['status'],
                username=pinfo['username'],
                create_time=datetime.fromtimestamp(proc.create_time()),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                cmdline=pinfo['cmdline'] if pinfo['cmdline'] else [],
                threads=threads,
                nice=nice,
                io_counters=io_counters,
                context_switches=ctx_switches
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            return None

    def get_process(self, pid: int) -> Optional[Process]:
        """Get process information by PID with caching"""
        self.refresh_processes()
        return self.processes.get(pid)

    def list_processes(self, refresh: bool = False) -> List[Process]:
        """Get list of all processes with optional refresh"""
        self.refresh_processes(force=refresh)
        return list(self.processes.values())

    def find_by_name(self, name: str, case_sensitive: bool = False) -> List[Process]:
        """Enhanced process search by name"""
        self.refresh_processes()
        name = name if case_sensitive else name.lower()
        return [
            p for p in self.processes.values()
            if (p.name if case_sensitive else p.name.lower()).find(name) != -1
        ]

    def get_process_tree(self, pid: Optional[int] = None) -> Dict[int, List[Process]]:
        """Get process tree with optimized tree building"""
        self.refresh_processes()

        # Create parent-child relationship map
        tree: Dict[int, List[Process]] = {}
        for process in self.processes.values():
            if process.ppid not in tree:
                tree[process.ppid] = []
            tree[process.ppid].append(process)

        if pid is None:
            return tree

        # Extract subtree for specific PID
        subtree = {}
        def extract_subtree(current_pid: int):
            if current_pid in tree:
                subtree[current_pid] = tree[current_pid]
                for child in tree[current_pid]:
                    extract_subtree(child.pid)

        extract_subtree(pid)
        return subtree

    def get_system_resources(self) -> ResourceInfo:
        """Get detailed system resource usage with caching"""
        if 'resources' in self._resource_cache:
            return self._resource_cache['resources']

        try:
            cpu_freq = None
            if hasattr(psutil, 'cpu_freq'):
                freq = psutil.cpu_freq()
                if freq:
                    cpu_freq = {'current': freq.current, 'min': freq.min, 'max': freq.max}

            disk_io = None
            if hasattr(psutil, 'disk_io_counters'):
                io = psutil.disk_io_counters()
                if io:
                    disk_io = {
                        'read_count': io.read_count,
                        'write_count': io.write_count,
                        'read_bytes': io.read_bytes,
                        'write_bytes': io.write_bytes
                    }

            net_io = None
            if hasattr(psutil, 'net_io_counters'):
                io = psutil.net_io_counters()
                if io:
                    net_io = {
                        'bytes_sent': io.bytes_sent,
                        'bytes_recv': io.bytes_recv,
                        'packets_sent': io.packets_sent,
                        'packets_recv': io.packets_recv
                    }

            resources: ResourceInfo = {
                'cpu': {
                    'percent': psutil.cpu_percent(interval=0.1),
                    'count': psutil.cpu_count(),
                    'freq': cpu_freq,
                    'stats': dict(psutil.cpu_stats()._asdict()),
                    'times': dict(psutil.cpu_times()._asdict())
                },
                'memory': {
                    'virtual': dict(psutil.virtual_memory()._asdict()),
                    'swap': dict(psutil.swap_memory()._asdict())
                },
                'disk': {
                    'usage': dict(psutil.disk_usage('/')._asdict()),
                    'io': disk_io
                },
                'network': {
                    'io': net_io,
                    'connections': len(psutil.net_connections()) if hasattr(psutil, 'net_connections') else 0
                }
            }

            self._resource_cache['resources'] = resources
            return resources

        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            # Return a minimal resource info if there's an error
            return ResourceInfo(
                cpu={'percent': 0.0, 'count': 1, 'freq': None, 'stats': {}, 'times': {}},
                memory={'virtual': {}, 'swap': {}},
                disk={'usage': {}, 'io': None},
                network={'io': None, 'connections': 0}
            )

    def set_process_priority(self, pid: int, priority: int) -> bool:
        """Set process priority (nice value)"""
        try:
            process = psutil.Process(pid)
            process.nice(priority)
            self.refresh_processes(force=True)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error setting priority for process {pid}: {e}")
            return False

    def send_signal(self, pid: int, signal: int) -> bool:
        """Send signal to process with error handling"""
        try:
            process = psutil.Process(pid)
            process.send_signal(signal)
            self.refresh_processes(force=True)
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Error sending signal to process {pid}: {e}")
            return False
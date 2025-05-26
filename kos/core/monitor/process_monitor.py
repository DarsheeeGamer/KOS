"""
KOS Process Monitor

Provides detailed monitoring of processes, including:
- Per-process CPU and memory usage
- I/O statistics
- Network activity
- Process relationships (parent/child)
- Thread information
- File descriptor usage
"""

import os
import threading
import time
import logging
import json
from typing import Dict, List, Any, Optional, Set
import psutil

# Initialize logging
logger = logging.getLogger('KOS.monitor.process')

class ProcessMonitor:
    """
    Monitors processes and provides detailed performance metrics
    """
    def __init__(self, interval: float = 5.0, history_size: int = 60):
        """
        Initialize the process monitor
        
        Args:
            interval: Polling interval in seconds
            history_size: Number of history points to keep per process
        """
        self.interval = interval
        self.history_size = history_size
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread = None
        
        # Process tracking
        self.tracked_processes = set()  # PIDs to specifically track
        self.process_history = {}  # PID -> list of metrics
        self.current_metrics = {}  # PID -> current metrics
        
        # Callbacks
        self.callbacks = []
    
    def start(self):
        """Start monitoring processes"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Process monitor is already running")
            return False
        
        logger.info("Starting process monitor")
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="ProcessMonitorThread"
        )
        self._monitor_thread.start()
        return True
    
    def stop(self):
        """Stop monitoring processes"""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            logger.warning("Process monitor is not running")
            return False
        
        logger.info("Stopping process monitor")
        self._stop_event.set()
        self._monitor_thread.join(timeout=10.0)
        return True
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Process monitor loop started")
        
        while not self._stop_event.is_set():
            try:
                self._collect_process_metrics()
                
                # Sleep until next interval
                self._stop_event.wait(self.interval)
            
            except Exception as e:
                logger.error(f"Error in process monitor loop: {e}")
                time.sleep(self.interval)
        
        logger.info("Process monitor loop stopped")
    
    def _collect_process_metrics(self):
        """Collect metrics for all processes"""
        with self._lock:
            timestamp = time.time()
            
            # Get list of all processes
            all_pids = set()
            for proc in psutil.process_iter(['pid']):
                all_pids.add(proc.info['pid'])
            
            # Add all service PIDs to tracked processes
            from ..service import get_service_pids
            service_pids = get_service_pids()
            self.tracked_processes.update(service_pids)
            
            # Collect metrics for tracked processes and a sample of others
            processes_to_monitor = self.tracked_processes.union(
                # Always monitor the top 10 CPU and memory processes
                self._get_top_processes(10, 'cpu_percent'),
                self._get_top_processes(10, 'memory_percent')
            )
            
            # Clean up processes that no longer exist
            for pid in list(self.process_history.keys()):
                if pid not in all_pids:
                    del self.process_history[pid]
                    if pid in self.current_metrics:
                        del self.current_metrics[pid]
                    if pid in self.tracked_processes:
                        self.tracked_processes.remove(pid)
            
            # Collect metrics for each process
            for pid in processes_to_monitor:
                if pid not in all_pids:
                    continue
                
                try:
                    process = psutil.Process(pid)
                    metrics = self._collect_process_data(process, timestamp)
                    
                    if pid not in self.process_history:
                        self.process_history[pid] = []
                    
                    self.process_history[pid].append(metrics)
                    self.current_metrics[pid] = metrics
                    
                    # Limit history size
                    if len(self.process_history[pid]) > self.history_size:
                        self.process_history[pid].pop(0)
                    
                    # Call any callbacks
                    self._check_process_thresholds(pid, metrics)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    # Process ended or can't be accessed
                    if pid in self.process_history:
                        del self.process_history[pid]
                    if pid in self.current_metrics:
                        del self.current_metrics[pid]
                    if pid in self.tracked_processes:
                        self.tracked_processes.remove(pid)
                
                except Exception as e:
                    logger.error(f"Error collecting metrics for process {pid}: {e}")
    
    def _collect_process_data(self, process, timestamp):
        """Collect comprehensive data for a single process"""
        try:
            # Basic process info
            proc_info = process.as_dict(attrs=[
                'pid', 'name', 'exe', 'cmdline', 'username',
                'status', 'create_time', 'terminal', 'cwd',
                'nice', 'cpu_percent', 'memory_percent',
                'memory_info', 'num_threads', 'num_fds'
            ])
            
            # Calculate uptime
            proc_info['uptime'] = timestamp - proc_info['create_time']
            
            # Get parent/children info
            try:
                parent = process.parent()
                proc_info['parent_pid'] = parent.pid if parent else None
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['parent_pid'] = None
            
            try:
                children = process.children()
                proc_info['children_pids'] = [child.pid for child in children]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['children_pids'] = []
            
            # Get I/O information
            try:
                io_counters = process.io_counters()
                proc_info['io_counters'] = {
                    'read_count': io_counters.read_count,
                    'write_count': io_counters.write_count,
                    'read_bytes': io_counters.read_bytes,
                    'write_bytes': io_counters.write_bytes
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['io_counters'] = None
            
            # Memory info as dictionary
            if proc_info['memory_info']:
                proc_info['memory_info'] = dict(proc_info['memory_info']._asdict())
            
            # Add timestamp
            proc_info['timestamp'] = timestamp
            
            # Get thread information
            try:
                thread_info = []
                for thread in process.threads():
                    thread_info.append({
                        'id': thread.id,
                        'user_time': thread.user_time,
                        'system_time': thread.system_time
                    })
                proc_info['threads'] = thread_info
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['threads'] = []
            
            # Get open files
            try:
                files = []
                for f in process.open_files():
                    files.append({
                        'path': f.path,
                        'fd': f.fd,
                        'position': f.position,
                        'mode': f.mode
                    })
                proc_info['open_files'] = files
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['open_files'] = []
            
            # Get network connections
            try:
                connections = []
                for conn in process.connections(kind='all'):
                    connection_info = {
                        'fd': conn.fd,
                        'family': str(conn.family),
                        'type': str(conn.type),
                        'status': conn.status,
                    }
                    
                    # Add local/remote address if available
                    if conn.laddr:
                        connection_info['local_address'] = {
                            'ip': conn.laddr.ip,
                            'port': conn.laddr.port
                        }
                    
                    if conn.raddr:
                        connection_info['remote_address'] = {
                            'ip': conn.raddr.ip,
                            'port': conn.raddr.port
                        }
                    
                    connections.append(connection_info)
                
                proc_info['connections'] = connections
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                proc_info['connections'] = []
            
            return proc_info
        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            return None
    
    def _check_process_thresholds(self, pid, metrics):
        """Check if process metrics exceed thresholds and notify callbacks"""
        if not metrics:
            return
        
        alerts = []
        
        # Check CPU usage
        if metrics['cpu_percent'] > 90.0:  # 90% CPU usage
            alerts.append({
                'type': 'cpu_high',
                'message': f"Process {pid} ({metrics['name']}) CPU usage is {metrics['cpu_percent']:.1f}%",
                'value': metrics['cpu_percent'],
                'threshold': 90.0
            })
        
        # Check memory usage
        if metrics['memory_percent'] > 80.0:  # 80% memory usage
            alerts.append({
                'type': 'memory_high',
                'message': f"Process {pid} ({metrics['name']}) memory usage is {metrics['memory_percent']:.1f}%",
                'value': metrics['memory_percent'],
                'threshold': 80.0
            })
        
        # Trigger callbacks for any alerts
        for alert in alerts:
            for callback in self.callbacks:
                try:
                    callback(pid, metrics, alert)
                except Exception as e:
                    logger.error(f"Error in process callback: {e}")
    
    def _get_top_processes(self, n: int, sort_by: str):
        """
        Get the top N processes by a specific metric
        
        Args:
            n: Number of processes to return
            sort_by: Metric to sort by (e.g., 'cpu_percent', 'memory_percent')
        """
        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', sort_by]):
                try:
                    proc_info = proc.info
                    if sort_by not in proc_info or proc_info[sort_by] is None:
                        # Update the value
                        if sort_by == 'cpu_percent':
                            proc_info[sort_by] = proc.cpu_percent(interval=0.1)
                        elif sort_by == 'memory_percent':
                            proc_info[sort_by] = proc.memory_percent()
                    
                    procs.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            # Sort by the specified metric and return the top N PIDs
            top_procs = sorted(procs, key=lambda p: p.get(sort_by, 0), reverse=True)[:n]
            return {p['pid'] for p in top_procs}
        
        except Exception as e:
            logger.error(f"Error getting top processes: {e}")
            return set()
    
    def track_process(self, pid: int):
        """Add a process to the tracked list"""
        with self._lock:
            try:
                # Check if process exists
                psutil.Process(pid)
                self.tracked_processes.add(pid)
                return True
            except psutil.NoSuchProcess:
                return False
    
    def untrack_process(self, pid: int):
        """Remove a process from the tracked list"""
        with self._lock:
            if pid in self.tracked_processes:
                self.tracked_processes.remove(pid)
                return True
            return False
    
    def get_process_metrics(self, pid: int):
        """Get the current metrics for a specific process"""
        with self._lock:
            return self.current_metrics.get(pid)
    
    def get_process_history(self, pid: int, points: Optional[int] = None):
        """
        Get the metric history for a specific process
        
        Args:
            pid: Process ID
            points: Number of history points to return (None for all)
        """
        with self._lock:
            history = self.process_history.get(pid, [])
            
            if points and points < len(history):
                return history[-points:]
            
            return history
    
    def register_callback(self, callback):
        """Register a callback for process threshold alerts"""
        with self._lock:
            if callback not in self.callbacks:
                self.callbacks.append(callback)
                return True
            return False
    
    def unregister_callback(self, callback):
        """Unregister a callback"""
        with self._lock:
            if callback in self.callbacks:
                self.callbacks.remove(callback)
                return True
            return False

# Default process monitor instance
_default_instance = None

def get_process_monitor():
    """Get the default ProcessMonitor instance"""
    global _default_instance
    
    if _default_instance is None:
        _default_instance = ProcessMonitor()
    
    return _default_instance

def start_monitoring():
    """Start the default process monitor"""
    monitor = get_process_monitor()
    return monitor.start()

def stop_monitoring():
    """Stop the default process monitor"""
    monitor = get_process_monitor()
    return monitor.stop()

def track_process(pid: int):
    """Track a process in the default monitor"""
    monitor = get_process_monitor()
    return monitor.track_process(pid)

def get_process_metrics(pid: int):
    """Get metrics for a process from the default monitor"""
    monitor = get_process_monitor()
    return monitor.get_process_metrics(pid)

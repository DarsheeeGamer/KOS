"""
KOS System Resource Monitor

Provides comprehensive monitoring of system resources, including:
- CPU usage tracking (system-wide and per-core)
- Memory usage monitoring
- Disk I/O and usage statistics
- Network traffic monitoring
- Hardware temperature sensors
"""

import logging
import os
import threading
import time
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
import psutil

# Initialize logging
logger = logging.getLogger('KOS.monitor.resources')

class ResourceType:
    """Resource types for monitoring"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    TEMPERATURE = "temperature"

class SystemResourceMonitor:
    """
    Monitors and tracks system resources
    """
    def __init__(self, interval: float = 5.0, history_size: int = 60):
        """
        Initialize the system resource monitor
        
        Args:
            interval: Polling interval in seconds
            history_size: Number of history points to keep
        """
        self.interval = interval
        self.history_size = history_size
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._monitor_thread = None
        
        # Resource history
        self.cpu_history = []
        self.memory_history = []
        self.disk_history = {}
        self.network_history = {}
        self.temperature_history = {}
        
        # Current values
        self.current_values = {
            ResourceType.CPU: {},
            ResourceType.MEMORY: {},
            ResourceType.DISK: {},
            ResourceType.NETWORK: {},
            ResourceType.TEMPERATURE: {}
        }
        
        # Callbacks for resource events
        self.callbacks = {
            ResourceType.CPU: [],
            ResourceType.MEMORY: [],
            ResourceType.DISK: [],
            ResourceType.NETWORK: [],
            ResourceType.TEMPERATURE: []
        }
        
        # Thresholds for resource alerts
        self.thresholds = {
            ResourceType.CPU: 80.0,      # 80% CPU usage
            ResourceType.MEMORY: 80.0,   # 80% memory usage
            ResourceType.DISK: 85.0,     # 85% disk usage
            ResourceType.TEMPERATURE: 80.0  # 80C temperature
        }
    
    def start(self):
        """Start monitoring resources"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("Resource monitor is already running")
            return False
        
        logger.info("Starting system resource monitor")
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, 
            daemon=True,
            name="ResourceMonitorThread"
        )
        self._monitor_thread.start()
        return True
    
    def stop(self):
        """Stop monitoring resources"""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            logger.warning("Resource monitor is not running")
            return False
        
        logger.info("Stopping system resource monitor")
        self._stop_event.set()
        self._monitor_thread.join(timeout=10.0)
        return True
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info("Resource monitor loop started")
        
        while not self._stop_event.is_set():
            try:
                self._collect_metrics()
                self._check_thresholds()
                
                # Sleep until next interval
                self._stop_event.wait(self.interval)
            
            except Exception as e:
                logger.error(f"Error in resource monitor loop: {e}")
                time.sleep(self.interval)
        
        logger.info("Resource monitor loop stopped")
    
    def _collect_metrics(self):
        """Collect system metrics"""
        with self._lock:
            # Collect CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            cpu_times = psutil.cpu_times_percent(interval=0.1, percpu=True)
            
            self.current_values[ResourceType.CPU] = {
                'percent': cpu_percent,
                'times': [dict(ct._asdict()) for ct in cpu_times],
                'count': psutil.cpu_count(logical=True),
                'physical_count': psutil.cpu_count(logical=False),
                'load_avg': psutil.getloadavg(),
                'timestamp': time.time()
            }
            
            self.cpu_history.append(self.current_values[ResourceType.CPU])
            if len(self.cpu_history) > self.history_size:
                self.cpu_history.pop(0)
            
            # Collect memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            self.current_values[ResourceType.MEMORY] = {
                'total': memory.total,
                'available': memory.available,
                'used': memory.used,
                'free': memory.free,
                'percent': memory.percent,
                'swap_total': swap.total,
                'swap_used': swap.used,
                'swap_free': swap.free,
                'swap_percent': swap.percent,
                'timestamp': time.time()
            }
            
            self.memory_history.append(self.current_values[ResourceType.MEMORY])
            if len(self.memory_history) > self.history_size:
                self.memory_history.pop(0)
            
            # Collect disk metrics
            for disk in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(disk.mountpoint)
                    
                    if disk.mountpoint not in self.disk_history:
                        self.disk_history[disk.mountpoint] = []
                    
                    disk_info = {
                        'device': disk.device,
                        'mountpoint': disk.mountpoint,
                        'fstype': disk.fstype,
                        'opts': disk.opts,
                        'total': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent,
                        'timestamp': time.time()
                    }
                    
                    self.current_values[ResourceType.DISK][disk.mountpoint] = disk_info
                    
                    self.disk_history[disk.mountpoint].append(disk_info)
                    if len(self.disk_history[disk.mountpoint]) > self.history_size:
                        self.disk_history[disk.mountpoint].pop(0)
                
                except Exception as e:
                    logger.warning(f"Error collecting disk metrics for {disk.mountpoint}: {e}")
            
            # Collect network metrics
            net_io = psutil.net_io_counters(pernic=True)
            
            for interface, counters in net_io.items():
                if interface not in self.network_history:
                    self.network_history[interface] = []
                
                net_info = dict(counters._asdict())
                net_info['timestamp'] = time.time()
                
                self.current_values[ResourceType.NETWORK][interface] = net_info
                
                self.network_history[interface].append(net_info)
                if len(self.network_history[interface]) > self.history_size:
                    self.network_history[interface].pop(0)
            
            # Collect temperature metrics
            try:
                temps = psutil.sensors_temperatures()
                
                for sensor, readings in temps.items():
                    if sensor not in self.temperature_history:
                        self.temperature_history[sensor] = []
                    
                    sensor_readings = []
                    for reading in readings:
                        reading_dict = {
                            'label': reading.label,
                            'current': reading.current,
                            'high': reading.high,
                            'critical': reading.critical
                        }
                        sensor_readings.append(reading_dict)
                    
                    temp_info = {
                        'readings': sensor_readings,
                        'timestamp': time.time()
                    }
                    
                    self.current_values[ResourceType.TEMPERATURE][sensor] = temp_info
                    
                    self.temperature_history[sensor].append(temp_info)
                    if len(self.temperature_history[sensor]) > self.history_size:
                        self.temperature_history[sensor].pop(0)
            
            except Exception as e:
                logger.warning(f"Error collecting temperature metrics: {e}")
    
    def _check_thresholds(self):
        """Check resource thresholds and trigger callbacks"""
        with self._lock:
            # Check CPU threshold
            avg_cpu = sum(self.current_values[ResourceType.CPU]['percent']) / len(self.current_values[ResourceType.CPU]['percent'])
            if avg_cpu > self.thresholds[ResourceType.CPU]:
                self._trigger_callbacks(
                    ResourceType.CPU, 
                    "High CPU Usage", 
                    f"CPU usage is {avg_cpu:.1f}%, exceeding threshold of {self.thresholds[ResourceType.CPU]:.1f}%",
                    self.current_values[ResourceType.CPU]
                )
            
            # Check memory threshold
            mem_percent = self.current_values[ResourceType.MEMORY]['percent']
            if mem_percent > self.thresholds[ResourceType.MEMORY]:
                self._trigger_callbacks(
                    ResourceType.MEMORY,
                    "High Memory Usage",
                    f"Memory usage is {mem_percent:.1f}%, exceeding threshold of {self.thresholds[ResourceType.MEMORY]:.1f}%",
                    self.current_values[ResourceType.MEMORY]
                )
            
            # Check disk threshold
            for mountpoint, disk_info in self.current_values[ResourceType.DISK].items():
                if disk_info['percent'] > self.thresholds[ResourceType.DISK]:
                    self._trigger_callbacks(
                        ResourceType.DISK,
                        "High Disk Usage",
                        f"Disk usage for {mountpoint} is {disk_info['percent']:.1f}%, exceeding threshold of {self.thresholds[ResourceType.DISK]:.1f}%",
                        disk_info
                    )
            
            # Check temperature threshold
            for sensor, temp_info in self.current_values[ResourceType.TEMPERATURE].items():
                for reading in temp_info['readings']:
                    if reading['current'] and reading['current'] > self.thresholds[ResourceType.TEMPERATURE]:
                        self._trigger_callbacks(
                            ResourceType.TEMPERATURE,
                            "High Temperature",
                            f"Temperature for {sensor} ({reading['label']}) is {reading['current']:.1f}°C, exceeding threshold of {self.thresholds[ResourceType.TEMPERATURE]:.1f}°C",
                            reading
                        )
    
    def _trigger_callbacks(self, resource_type, alert_type, message, data):
        """Trigger callbacks for a resource event"""
        for callback in self.callbacks[resource_type]:
            try:
                callback(resource_type, alert_type, message, data)
            except Exception as e:
                logger.error(f"Error in resource callback: {e}")
    
    def register_callback(self, resource_type, callback):
        """Register a callback for resource events"""
        with self._lock:
            if resource_type in self.callbacks:
                self.callbacks[resource_type].append(callback)
                return True
            return False
    
    def unregister_callback(self, resource_type, callback):
        """Unregister a callback"""
        with self._lock:
            if resource_type in self.callbacks and callback in self.callbacks[resource_type]:
                self.callbacks[resource_type].remove(callback)
                return True
            return False
    
    def set_threshold(self, resource_type, threshold):
        """Set a resource threshold"""
        with self._lock:
            if resource_type in self.thresholds:
                self.thresholds[resource_type] = float(threshold)
                return True
            return False
    
    def get_resource_usage(self, resource_type=None):
        """Get current resource usage"""
        with self._lock:
            if resource_type:
                return self.current_values.get(resource_type, {})
            return self.current_values
    
    def get_resource_history(self, resource_type, resource_id=None, points=None):
        """
        Get resource usage history
        
        Args:
            resource_type: Type of resource
            resource_id: Specific resource ID (e.g., disk mountpoint, network interface)
            points: Number of history points (None for all available)
        """
        with self._lock:
            if resource_type == ResourceType.CPU:
                history = self.cpu_history
            elif resource_type == ResourceType.MEMORY:
                history = self.memory_history
            elif resource_type == ResourceType.DISK:
                if resource_id:
                    history = self.disk_history.get(resource_id, [])
                else:
                    # Combine all disk histories
                    history = []
                    for disk_history in self.disk_history.values():
                        history.extend(disk_history)
                    # Sort by timestamp
                    history.sort(key=lambda x: x['timestamp'])
            elif resource_type == ResourceType.NETWORK:
                if resource_id:
                    history = self.network_history.get(resource_id, [])
                else:
                    # Combine all network histories
                    history = []
                    for net_history in self.network_history.values():
                        history.extend(net_history)
                    # Sort by timestamp
                    history.sort(key=lambda x: x['timestamp'])
            elif resource_type == ResourceType.TEMPERATURE:
                if resource_id:
                    history = self.temperature_history.get(resource_id, [])
                else:
                    # Combine all temperature histories
                    history = []
                    for temp_history in self.temperature_history.values():
                        history.extend(temp_history)
                    # Sort by timestamp
                    history.sort(key=lambda x: x['timestamp'])
            else:
                return []
            
            if points and points < len(history):
                return history[-points:]
            
            return history
    
    def get_system_info(self):
        """Get comprehensive system information"""
        try:
            # Collect system information
            boot_time = psutil.boot_time()
            
            info = {
                'hostname': os.uname().nodename,
                'platform': {
                    'system': os.uname().sysname,
                    'release': os.uname().release,
                    'version': os.uname().version,
                    'machine': os.uname().machine,
                    'python': {
                        'version': '.'.join(map(str, os.sys.version_info[:3])),
                        'implementation': os.sys.implementation.name,
                    }
                },
                'uptime': time.time() - boot_time,
                'boot_time': boot_time,
                'cpu': {
                    'physical_cores': psutil.cpu_count(logical=False),
                    'total_cores': psutil.cpu_count(logical=True),
                    'max_frequency': psutil.cpu_freq().max if psutil.cpu_freq() else None,
                    'min_frequency': psutil.cpu_freq().min if psutil.cpu_freq() else None,
                    'current_frequency': psutil.cpu_freq().current if psutil.cpu_freq() else None
                },
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'swap_total': psutil.swap_memory().total
                },
                'disks': []
            }
            
            # Add disk information
            for disk in psutil.disk_partitions(all=False):
                usage = psutil.disk_usage(disk.mountpoint)
                info['disks'].append({
                    'device': disk.device,
                    'mountpoint': disk.mountpoint,
                    'fstype': disk.fstype,
                    'total': usage.total
                })
            
            # Add network information
            info['network'] = {}
            net_io = psutil.net_io_counters(pernic=True)
            net_addrs = psutil.net_if_addrs()
            
            for interface, addrs in net_addrs.items():
                ip_addresses = []
                for addr in addrs:
                    ip_addresses.append({
                        'family': str(addr.family),
                        'address': addr.address,
                        'netmask': addr.netmask,
                        'broadcast': addr.broadcast
                    })
                
                info['network'][interface] = {
                    'addresses': ip_addresses
                }
                
                if interface in net_io:
                    counters = net_io[interface]
                    info['network'][interface].update({
                        'bytes_sent': counters.bytes_sent,
                        'bytes_recv': counters.bytes_recv,
                        'packets_sent': counters.packets_sent,
                        'packets_recv': counters.packets_recv
                    })
            
            return info
        
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}

"""
SystemResourceMonitor Component for KADVLayer

This module provides real-time monitoring of system resources,
including CPU, memory, disk, and network usage with event-based callbacks.
"""

import os
import sys
import time
import threading
import logging
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.resource_monitor')

class ResourceThreshold:
    """Resource threshold configuration for alerts"""
    
    def __init__(self, warning: float, critical: float):
        """
        Initialize resource threshold
        
        Args:
            warning: Warning threshold (percentage)
            critical: Critical threshold (percentage)
        """
        self.warning = warning
        self.critical = critical
    
    def get_status(self, value: float) -> str:
        """
        Get status based on value
        
        Args:
            value: Current value (percentage)
            
        Returns:
            Status (normal, warning, critical)
        """
        if value >= self.critical:
            return "critical"
        elif value >= self.warning:
            return "warning"
        else:
            return "normal"

class SystemResourceMonitor:
    """
    Monitors system resources in real-time
    
    This class provides methods to monitor CPU, memory, disk, and network
    usage with support for thresholds and event-based callbacks.
    """
    
    def __init__(self):
        """Initialize the SystemResourceMonitor component"""
        self.monitoring = False
        self.monitor_thread = None
        self.lock = threading.RLock()
        
        # Resource thresholds (percentage)
        self.thresholds = {
            "cpu": ResourceThreshold(70, 90),
            "memory": ResourceThreshold(80, 95),
            "disk": ResourceThreshold(85, 95),
            "swap": ResourceThreshold(60, 80)
        }
        
        # Monitoring interval (seconds)
        self.interval = 5.0
        
        # Resource status
        self.status = {
            "cpu": "normal",
            "memory": "normal",
            "disk": "normal",
            "swap": "normal"
        }
        
        # Resource metrics
        self.metrics = {
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {}
        }
        
        # History data (for trends)
        self.history_size = 60  # Keep 60 data points
        self.history = {
            "cpu": [],
            "memory": [],
            "disk": [],
            "network": []
        }
        
        # Callbacks for resource events
        self.callbacks = {
            "cpu": [],
            "memory": [],
            "disk": [],
            "network": [],
            "all": []
        }
        
        logger.debug("SystemResourceMonitor component initialized")
    
    def start_monitoring(self, interval: Optional[float] = None) -> bool:
        """
        Start monitoring system resources
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.monitoring:
                logger.warning("Resource monitoring already running")
                return False
            
            if interval is not None:
                self.interval = max(1.0, interval)  # Minimum 1 second
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info(f"Started resource monitoring with interval {self.interval}s")
            return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop monitoring system resources
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.monitoring:
                logger.warning("Resource monitoring not running")
                return False
            
            self.monitoring = False
            
            # Wait for thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("Stopped resource monitoring")
            return True
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot monitor system resources without psutil")
            self.monitoring = False
            return
        
        last_time = time.time()
        
        while self.monitoring:
            try:
                # Collect metrics
                current_metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "cpu": self._get_cpu_metrics(),
                    "memory": self._get_memory_metrics(),
                    "disk": self._get_disk_metrics(),
                    "network": self._get_network_metrics()
                }
                
                # Update metrics
                self.metrics = current_metrics
                
                # Update history
                self._update_history(current_metrics)
                
                # Check thresholds and trigger callbacks
                self._check_thresholds(current_metrics)
                
                # Call 'all' callbacks
                for callback in self.callbacks["all"]:
                    try:
                        callback(current_metrics)
                    except Exception as e:
                        logger.error(f"Error in resource callback: {e}")
                
                # Sleep until next interval
                current_time = time.time()
                elapsed = current_time - last_time
                sleep_time = max(0.1, self.interval - elapsed)
                time.sleep(sleep_time)
                last_time = time.time()
            except Exception as e:
                logger.error(f"Error in resource monitoring: {e}")
                time.sleep(self.interval)
    
    def _get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU metrics"""
        metrics = {}
        
        try:
            # Get CPU usage
            metrics["percent"] = psutil.cpu_percent(interval=0.1)
            
            # Get per-CPU usage
            metrics["per_cpu_percent"] = psutil.cpu_percent(interval=0.1, percpu=True)
            
            # Get CPU times
            cpu_times = psutil.cpu_times_percent(interval=0.1)
            metrics["times"] = {
                "user": cpu_times.user,
                "system": cpu_times.system,
                "idle": cpu_times.idle
            }
            
            # Get CPU frequency if available
            if hasattr(psutil, 'cpu_freq'):
                cpu_freq = psutil.cpu_freq()
                if cpu_freq:
                    metrics["freq"] = {
                        "current": cpu_freq.current,
                        "min": cpu_freq.min,
                        "max": cpu_freq.max
                    }
            
            # Get CPU load average if available
            try:
                load_avg = psutil.getloadavg()
                metrics["load_avg"] = {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                }
            except:
                pass
        except Exception as e:
            logger.error(f"Error getting CPU metrics: {e}")
        
        return metrics
    
    def _get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory metrics"""
        metrics = {}
        
        try:
            # Get virtual memory
            virtual_memory = psutil.virtual_memory()
            metrics["virtual"] = {
                "total": virtual_memory.total,
                "available": virtual_memory.available,
                "used": virtual_memory.used,
                "free": virtual_memory.free,
                "percent": virtual_memory.percent
            }
            
            # Get swap memory
            swap_memory = psutil.swap_memory()
            metrics["swap"] = {
                "total": swap_memory.total,
                "used": swap_memory.used,
                "free": swap_memory.free,
                "percent": swap_memory.percent
            }
        except Exception as e:
            logger.error(f"Error getting memory metrics: {e}")
        
        return metrics
    
    def _get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk metrics"""
        metrics = {
            "partitions": [],
            "io": None
        }
        
        try:
            # Get disk partitions
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    part_metrics = {
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    }
                    metrics["partitions"].append(part_metrics)
                except:
                    # Some mountpoints may not be accessible
                    pass
            
            # Get disk I/O counters
            if hasattr(psutil, 'disk_io_counters'):
                io_counters = psutil.disk_io_counters()
                if io_counters:
                    metrics["io"] = {
                        "read_count": io_counters.read_count,
                        "write_count": io_counters.write_count,
                        "read_bytes": io_counters.read_bytes,
                        "write_bytes": io_counters.write_bytes,
                        "read_time": io_counters.read_time if hasattr(io_counters, 'read_time') else None,
                        "write_time": io_counters.write_time if hasattr(io_counters, 'write_time') else None
                    }
        except Exception as e:
            logger.error(f"Error getting disk metrics: {e}")
        
        return metrics
    
    def _get_network_metrics(self) -> Dict[str, Any]:
        """Get network metrics"""
        metrics = {
            "interfaces": {},
            "connections": {
                "total": 0,
                "established": 0,
                "listening": 0,
                "time_wait": 0
            }
        }
        
        try:
            # Get network I/O counters
            if hasattr(psutil, 'net_io_counters'):
                net_io_all = psutil.net_io_counters()
                metrics["total"] = {
                    "bytes_sent": net_io_all.bytes_sent,
                    "bytes_recv": net_io_all.bytes_recv,
                    "packets_sent": net_io_all.packets_sent,
                    "packets_recv": net_io_all.packets_recv,
                    "errin": net_io_all.errin,
                    "errout": net_io_all.errout,
                    "dropin": net_io_all.dropin,
                    "dropout": net_io_all.dropout
                }
                
                # Get per-interface I/O counters
                net_io_per_nic = psutil.net_io_counters(pernic=True)
                for interface, counters in net_io_per_nic.items():
                    metrics["interfaces"][interface] = {
                        "bytes_sent": counters.bytes_sent,
                        "bytes_recv": counters.bytes_recv,
                        "packets_sent": counters.packets_sent,
                        "packets_recv": counters.packets_recv,
                        "errin": counters.errin,
                        "errout": counters.errout,
                        "dropin": counters.dropin,
                        "dropout": counters.dropout
                    }
            
            # Get network connections
            if hasattr(psutil, 'net_connections'):
                try:
                    connections = psutil.net_connections()
                    metrics["connections"]["total"] = len(connections)
                    
                    # Count by status
                    status_counts = {}
                    for conn in connections:
                        status = conn.status.lower() if conn.status else "unknown"
                        status_counts[status] = status_counts.get(status, 0) + 1
                    
                    # Set specific statuses
                    metrics["connections"]["established"] = status_counts.get("established", 0)
                    metrics["connections"]["listening"] = status_counts.get("listen", 0)
                    metrics["connections"]["time_wait"] = status_counts.get("time_wait", 0)
                    
                    # Add all statuses
                    metrics["connections"]["by_status"] = status_counts
                except:
                    # May require admin privileges
                    pass
        except Exception as e:
            logger.error(f"Error getting network metrics: {e}")
        
        return metrics
    
    def _update_history(self, current_metrics: Dict[str, Any]):
        """
        Update metrics history
        
        Args:
            current_metrics: Current system metrics
        """
        # Add CPU metrics to history
        if "cpu" in current_metrics and "percent" in current_metrics["cpu"]:
            self.history["cpu"].append({
                "timestamp": current_metrics["timestamp"],
                "percent": current_metrics["cpu"]["percent"]
            })
        
        # Add memory metrics to history
        if "memory" in current_metrics and "virtual" in current_metrics["memory"]:
            self.history["memory"].append({
                "timestamp": current_metrics["timestamp"],
                "percent": current_metrics["memory"]["virtual"]["percent"]
            })
        
        # Add disk metrics to history (average partition usage)
        if "disk" in current_metrics and "partitions" in current_metrics["disk"]:
            partitions = current_metrics["disk"]["partitions"]
            if partitions:
                avg_percent = sum(p["percent"] for p in partitions) / len(partitions)
                self.history["disk"].append({
                    "timestamp": current_metrics["timestamp"],
                    "percent": avg_percent
                })
        
        # Add network metrics to history (total bytes sent/received)
        if "network" in current_metrics and "total" in current_metrics["network"]:
            net_total = current_metrics["network"]["total"]
            self.history["network"].append({
                "timestamp": current_metrics["timestamp"],
                "bytes_sent": net_total["bytes_sent"],
                "bytes_recv": net_total["bytes_recv"]
            })
        
        # Trim history to max size
        for key in self.history:
            if len(self.history[key]) > self.history_size:
                self.history[key] = self.history[key][-self.history_size:]
    
    def _check_thresholds(self, current_metrics: Dict[str, Any]):
        """
        Check resource thresholds and trigger callbacks
        
        Args:
            current_metrics: Current system metrics
        """
        # Check CPU usage
        if "cpu" in current_metrics and "percent" in current_metrics["cpu"]:
            cpu_percent = current_metrics["cpu"]["percent"]
            new_status = self.thresholds["cpu"].get_status(cpu_percent)
            
            if new_status != self.status["cpu"]:
                # Status changed, trigger callbacks
                event = {
                    "resource": "cpu",
                    "previous_status": self.status["cpu"],
                    "current_status": new_status,
                    "value": cpu_percent,
                    "threshold": self.thresholds["cpu"].warning if new_status == "warning" else self.thresholds["cpu"].critical,
                    "timestamp": current_metrics["timestamp"]
                }
                
                self.status["cpu"] = new_status
                
                # Call CPU callbacks
                for callback in self.callbacks["cpu"]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in CPU callback: {e}")
        
        # Check memory usage
        if "memory" in current_metrics and "virtual" in current_metrics["memory"]:
            memory_percent = current_metrics["memory"]["virtual"]["percent"]
            new_status = self.thresholds["memory"].get_status(memory_percent)
            
            if new_status != self.status["memory"]:
                # Status changed, trigger callbacks
                event = {
                    "resource": "memory",
                    "previous_status": self.status["memory"],
                    "current_status": new_status,
                    "value": memory_percent,
                    "threshold": self.thresholds["memory"].warning if new_status == "warning" else self.thresholds["memory"].critical,
                    "timestamp": current_metrics["timestamp"]
                }
                
                self.status["memory"] = new_status
                
                # Call memory callbacks
                for callback in self.callbacks["memory"]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in memory callback: {e}")
        
        # Check disk usage (worst partition)
        if "disk" in current_metrics and "partitions" in current_metrics["disk"]:
            partitions = current_metrics["disk"]["partitions"]
            if partitions:
                # Find worst partition
                worst_percent = max(p["percent"] for p in partitions)
                new_status = self.thresholds["disk"].get_status(worst_percent)
                
                if new_status != self.status["disk"]:
                    # Status changed, trigger callbacks
                    event = {
                        "resource": "disk",
                        "previous_status": self.status["disk"],
                        "current_status": new_status,
                        "value": worst_percent,
                        "threshold": self.thresholds["disk"].warning if new_status == "warning" else self.thresholds["disk"].critical,
                        "timestamp": current_metrics["timestamp"]
                    }
                    
                    self.status["disk"] = new_status
                    
                    # Call disk callbacks
                    for callback in self.callbacks["disk"]:
                        try:
                            callback(event)
                        except Exception as e:
                            logger.error(f"Error in disk callback: {e}")
        
        # Check swap usage
        if "memory" in current_metrics and "swap" in current_metrics["memory"]:
            swap_percent = current_metrics["memory"]["swap"]["percent"]
            new_status = self.thresholds["swap"].get_status(swap_percent)
            
            if new_status != self.status["swap"]:
                # Status changed, trigger callbacks
                event = {
                    "resource": "swap",
                    "previous_status": self.status["swap"],
                    "current_status": new_status,
                    "value": swap_percent,
                    "threshold": self.thresholds["swap"].warning if new_status == "warning" else self.thresholds["swap"].critical,
                    "timestamp": current_metrics["timestamp"]
                }
                
                self.status["swap"] = new_status
                
                # We treat swap as a memory resource
                for callback in self.callbacks["memory"]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Error in memory callback: {e}")
    
    def register_callback(self, resource_type: str, callback: Callable) -> bool:
        """
        Register a callback for resource events
        
        Args:
            resource_type: Resource type (cpu, memory, disk, network, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if resource_type not in self.callbacks:
            logger.error(f"Invalid resource type: {resource_type}")
            return False
        
        with self.lock:
            self.callbacks[resource_type].append(callback)
            logger.debug(f"Registered callback for {resource_type} resource events")
            return True
    
    def unregister_callback(self, resource_type: str, callback: Callable) -> bool:
        """
        Unregister a callback for resource events
        
        Args:
            resource_type: Resource type (cpu, memory, disk, network, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if resource_type not in self.callbacks:
            logger.error(f"Invalid resource type: {resource_type}")
            return False
        
        with self.lock:
            if callback in self.callbacks[resource_type]:
                self.callbacks[resource_type].remove(callback)
                logger.debug(f"Unregistered callback for {resource_type} resource events")
                return True
            else:
                logger.warning(f"Callback not found for {resource_type} resource events")
                return False
    
    def set_threshold(self, resource_type: str, warning: float, critical: float) -> bool:
        """
        Set threshold for a resource type
        
        Args:
            resource_type: Resource type (cpu, memory, disk, swap)
            warning: Warning threshold (percentage)
            critical: Critical threshold (percentage)
            
        Returns:
            Success status
        """
        if resource_type not in self.thresholds:
            logger.error(f"Invalid resource type for threshold: {resource_type}")
            return False
        
        with self.lock:
            self.thresholds[resource_type] = ResourceThreshold(warning, critical)
            logger.debug(f"Set threshold for {resource_type}: warning={warning}%, critical={critical}%")
            return True
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current system metrics
        
        Returns:
            Dictionary with current metrics
        """
        return self.metrics
    
    def get_metrics_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get metrics history
        
        Returns:
            Dictionary with metrics history
        """
        return self.history
    
    def get_resource_status(self) -> Dict[str, str]:
        """
        Get current resource status
        
        Returns:
            Dictionary with resource status
        """
        return self.status.copy()
    
    def is_monitoring(self) -> bool:
        """
        Check if monitoring is active
        
        Returns:
            Whether monitoring is active
        """
        return self.monitoring

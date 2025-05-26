"""
Metrics Collection for KOS Orchestration System

This module implements metrics collection for the KOS orchestration system,
providing data for monitoring and autoscaling.
"""

import os
import json
import time
import logging
import threading
import psutil
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable

from kos.core.orchestration.pod import Pod

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
MONITORING_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/monitoring')
METRICS_PATH = os.path.join(MONITORING_ROOT, 'metrics')
METRICS_CONFIG_PATH = os.path.join(MONITORING_ROOT, 'metrics_config.json')

# Ensure directories exist
os.makedirs(METRICS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class MetricsConfig:
    """Configuration for metrics collection."""
    
    def __init__(self, collection_interval: int = 15, 
                 retention_period: int = 86400,  # 24 hours
                 enable_process_metrics: bool = True,
                 enable_network_metrics: bool = True,
                 enable_disk_metrics: bool = True,
                 enable_pod_metrics: bool = True):
        """
        Initialize metrics configuration.
        
        Args:
            collection_interval: Interval between metrics collections (in seconds)
            retention_period: How long to retain metrics (in seconds)
            enable_process_metrics: Whether to collect process metrics
            enable_network_metrics: Whether to collect network metrics
            enable_disk_metrics: Whether to collect disk metrics
            enable_pod_metrics: Whether to collect pod metrics
        """
        self.collection_interval = collection_interval
        self.retention_period = retention_period
        self.enable_process_metrics = enable_process_metrics
        self.enable_network_metrics = enable_network_metrics
        self.enable_disk_metrics = enable_disk_metrics
        self.enable_pod_metrics = enable_pod_metrics
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the metrics configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "collection_interval": self.collection_interval,
            "retention_period": self.retention_period,
            "enable_process_metrics": self.enable_process_metrics,
            "enable_network_metrics": self.enable_network_metrics,
            "enable_disk_metrics": self.enable_disk_metrics,
            "enable_pod_metrics": self.enable_pod_metrics
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MetricsConfig':
        """
        Create a metrics configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            MetricsConfig object
        """
        return cls(
            collection_interval=data.get("collection_interval", 15),
            retention_period=data.get("retention_period", 86400),
            enable_process_metrics=data.get("enable_process_metrics", True),
            enable_network_metrics=data.get("enable_network_metrics", True),
            enable_disk_metrics=data.get("enable_disk_metrics", True),
            enable_pod_metrics=data.get("enable_pod_metrics", True)
        )


class Metric:
    """Metric value with timestamp."""
    
    def __init__(self, name: str, value: Union[int, float, str, bool],
                 timestamp: Optional[float] = None,
                 labels: Optional[Dict[str, str]] = None):
        """
        Initialize a metric.
        
        Args:
            name: Metric name
            value: Metric value
            timestamp: Timestamp in seconds since epoch
            labels: Metric labels
        """
        self.name = name
        self.value = value
        self.timestamp = timestamp or time.time()
        self.labels = labels or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the metric to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "labels": self.labels
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metric':
        """
        Create a metric from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            Metric object
        """
        return cls(
            name=data.get("name", ""),
            value=data.get("value", 0),
            timestamp=data.get("timestamp", time.time()),
            labels=data.get("labels", {})
        )


class MetricsCollector:
    """
    Metrics collector for the KOS orchestration system.
    
    This class collects metrics from various sources, including system metrics
    (CPU, memory, disk, network) and pod metrics.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(MetricsCollector, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the metrics collector."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = self._load_config()
        self._metrics_cache: Dict[str, List[Metric]] = {}
        self._stop_event = threading.Event()
        self._collect_thread = None
        
        # Start collection thread
        self.start()
    
    def _load_config(self) -> MetricsConfig:
        """
        Load metrics configuration from disk.
        
        Returns:
            MetricsConfig object
        """
        if os.path.exists(METRICS_CONFIG_PATH):
            try:
                with open(METRICS_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                
                return MetricsConfig.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load metrics config: {e}")
        
        # Create default configuration
        config = MetricsConfig()
        self._save_config(config)
        
        return config
    
    def _save_config(self, config: MetricsConfig) -> bool:
        """
        Save metrics configuration to disk.
        
        Args:
            config: Configuration to save
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(METRICS_CONFIG_PATH, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save metrics config: {e}")
            return False
    
    def update_config(self, config: MetricsConfig) -> bool:
        """
        Update metrics configuration.
        
        Args:
            config: New configuration
            
        Returns:
            bool: Success or failure
        """
        if self._save_config(config):
            self.config = config
            
            # Restart collection thread
            self.stop()
            self.start()
            
            return True
        
        return False
    
    def start(self) -> bool:
        """
        Start the metrics collector.
        
        Returns:
            bool: Success or failure
        """
        if self._collect_thread and self._collect_thread.is_alive():
            return True
        
        self._stop_event.clear()
        self._collect_thread = threading.Thread(
            target=self._collect_loop,
            daemon=True
        )
        self._collect_thread.start()
        
        return True
    
    def stop(self) -> bool:
        """
        Stop the metrics collector.
        
        Returns:
            bool: Success or failure
        """
        if not self._collect_thread or not self._collect_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._collect_thread.join(timeout=5)
        
        return not self._collect_thread.is_alive()
    
    def _collect_loop(self) -> None:
        """Collection loop for the metrics collector."""
        while not self._stop_event.is_set():
            try:
                self.collect_metrics()
                self._save_metrics()
                self._cleanup_old_metrics()
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
            
            # Sleep for collection interval
            self._stop_event.wait(self.config.collection_interval)
    
    def collect_metrics(self) -> List[Metric]:
        """
        Collect metrics from various sources.
        
        Returns:
            List of collected metrics
        """
        metrics = []
        
        # Collect system metrics
        metrics.extend(self._collect_system_metrics())
        
        # Collect process metrics
        if self.config.enable_process_metrics:
            metrics.extend(self._collect_process_metrics())
        
        # Collect network metrics
        if self.config.enable_network_metrics:
            metrics.extend(self._collect_network_metrics())
        
        # Collect disk metrics
        if self.config.enable_disk_metrics:
            metrics.extend(self._collect_disk_metrics())
        
        # Collect pod metrics
        if self.config.enable_pod_metrics:
            metrics.extend(self._collect_pod_metrics())
        
        # Cache metrics
        self._cache_metrics(metrics)
        
        return metrics
    
    def _collect_system_metrics(self) -> List[Metric]:
        """
        Collect system metrics (CPU, memory).
        
        Returns:
            List of system metrics
        """
        metrics = []
        
        # CPU metrics
        metrics.append(Metric(
            name="system_cpu_usage",
            value=psutil.cpu_percent(),
            labels={"unit": "percent"}
        ))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        metrics.append(Metric(
            name="system_memory_total",
            value=memory.total,
            labels={"unit": "bytes"}
        ))
        metrics.append(Metric(
            name="system_memory_available",
            value=memory.available,
            labels={"unit": "bytes"}
        ))
        metrics.append(Metric(
            name="system_memory_used",
            value=memory.used,
            labels={"unit": "bytes"}
        ))
        metrics.append(Metric(
            name="system_memory_percent",
            value=memory.percent,
            labels={"unit": "percent"}
        ))
        
        # Load average
        try:
            load1, load5, load15 = psutil.getloadavg()
            metrics.append(Metric(
                name="system_load_average_1m",
                value=load1
            ))
            metrics.append(Metric(
                name="system_load_average_5m",
                value=load5
            ))
            metrics.append(Metric(
                name="system_load_average_15m",
                value=load15
            ))
        except (AttributeError, OSError):
            pass
        
        return metrics
    
    def _collect_process_metrics(self) -> List[Metric]:
        """
        Collect process metrics.
        
        Returns:
            List of process metrics
        """
        metrics = []
        
        try:
            # Get process count
            process_count = len(psutil.pids())
            metrics.append(Metric(
                name="system_process_count",
                value=process_count
            ))
            
            # Get KOS process metrics
            for proc in psutil.process_iter(['pid', 'name', 'username', 'cmdline']):
                try:
                    if 'kos' in ''.join(proc.info['cmdline'] or []).lower():
                        proc_info = proc.as_dict(attrs=['pid', 'name', 'cpu_percent', 'memory_info'])
                        
                        # Add CPU metrics
                        metrics.append(Metric(
                            name="process_cpu_percent",
                            value=proc_info['cpu_percent'],
                            labels={
                                "pid": str(proc_info['pid']),
                                "name": proc_info['name'],
                                "unit": "percent"
                            }
                        ))
                        
                        # Add memory metrics
                        memory_info = proc_info['memory_info']
                        if memory_info:
                            metrics.append(Metric(
                                name="process_memory_rss",
                                value=memory_info.rss,
                                labels={
                                    "pid": str(proc_info['pid']),
                                    "name": proc_info['name'],
                                    "unit": "bytes"
                                }
                            ))
                            metrics.append(Metric(
                                name="process_memory_vms",
                                value=memory_info.vms,
                                labels={
                                    "pid": str(proc_info['pid']),
                                    "name": proc_info['name'],
                                    "unit": "bytes"
                                }
                            ))
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception as e:
            logger.error(f"Failed to collect process metrics: {e}")
        
        return metrics
    
    def _collect_network_metrics(self) -> List[Metric]:
        """
        Collect network metrics.
        
        Returns:
            List of network metrics
        """
        metrics = []
        
        try:
            # Get network I/O stats
            net_io = psutil.net_io_counters(pernic=True)
            
            for nic, stats in net_io.items():
                # Skip loopback interface
                if nic == 'lo':
                    continue
                
                # Add bytes sent/received
                metrics.append(Metric(
                    name="network_bytes_sent",
                    value=stats.bytes_sent,
                    labels={
                        "interface": nic,
                        "unit": "bytes"
                    }
                ))
                metrics.append(Metric(
                    name="network_bytes_recv",
                    value=stats.bytes_recv,
                    labels={
                        "interface": nic,
                        "unit": "bytes"
                    }
                ))
                
                # Add packets sent/received
                metrics.append(Metric(
                    name="network_packets_sent",
                    value=stats.packets_sent,
                    labels={"interface": nic}
                ))
                metrics.append(Metric(
                    name="network_packets_recv",
                    value=stats.packets_recv,
                    labels={"interface": nic}
                ))
                
                # Add errors and drops
                metrics.append(Metric(
                    name="network_errin",
                    value=stats.errin,
                    labels={"interface": nic}
                ))
                metrics.append(Metric(
                    name="network_errout",
                    value=stats.errout,
                    labels={"interface": nic}
                ))
                metrics.append(Metric(
                    name="network_dropin",
                    value=stats.dropin,
                    labels={"interface": nic}
                ))
                metrics.append(Metric(
                    name="network_dropout",
                    value=stats.dropout,
                    labels={"interface": nic}
                ))
        except Exception as e:
            logger.error(f"Failed to collect network metrics: {e}")
        
        return metrics
    
    def _collect_disk_metrics(self) -> List[Metric]:
        """
        Collect disk metrics.
        
        Returns:
            List of disk metrics
        """
        metrics = []
        
        try:
            # Get disk usage
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    # Add disk usage metrics
                    metrics.append(Metric(
                        name="disk_total",
                        value=usage.total,
                        labels={
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_used",
                        value=usage.used,
                        labels={
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_free",
                        value=usage.free,
                        labels={
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_percent",
                        value=usage.percent,
                        labels={
                            "device": partition.device,
                            "mountpoint": partition.mountpoint,
                            "fstype": partition.fstype,
                            "unit": "percent"
                        }
                    ))
                except (PermissionError, OSError):
                    # Skip partitions we can't access
                    continue
            
            # Get disk I/O stats
            try:
                disk_io = psutil.disk_io_counters(perdisk=True)
                
                for disk, stats in disk_io.items():
                    # Add disk I/O metrics
                    metrics.append(Metric(
                        name="disk_read_count",
                        value=stats.read_count,
                        labels={"disk": disk}
                    ))
                    metrics.append(Metric(
                        name="disk_write_count",
                        value=stats.write_count,
                        labels={"disk": disk}
                    ))
                    metrics.append(Metric(
                        name="disk_read_bytes",
                        value=stats.read_bytes,
                        labels={
                            "disk": disk,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_write_bytes",
                        value=stats.write_bytes,
                        labels={
                            "disk": disk,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_read_time",
                        value=stats.read_time,
                        labels={
                            "disk": disk,
                            "unit": "ms"
                        }
                    ))
                    metrics.append(Metric(
                        name="disk_write_time",
                        value=stats.write_time,
                        labels={
                            "disk": disk,
                            "unit": "ms"
                        }
                    ))
            except (AttributeError, OSError):
                pass
        except Exception as e:
            logger.error(f"Failed to collect disk metrics: {e}")
        
        return metrics
    
    def _collect_pod_metrics(self) -> List[Metric]:
        """
        Collect pod metrics.
        
        Returns:
            List of pod metrics
        """
        metrics = []
        
        try:
            # Get all pods
            pods = Pod.list_pods()
            
            # Add pod count metrics
            metrics.append(Metric(
                name="pod_count",
                value=len(pods)
            ))
            
            # Count pods by phase
            phase_counts = {}
            for pod in pods:
                phase = pod.status.phase
                if phase not in phase_counts:
                    phase_counts[phase] = 0
                
                phase_counts[phase] += 1
            
            for phase, count in phase_counts.items():
                metrics.append(Metric(
                    name="pod_count_by_phase",
                    value=count,
                    labels={"phase": phase}
                ))
            
            # Collect metrics for each pod
            for pod in pods:
                # Skip pods without PIDs
                if not pod.status.pid:
                    continue
                
                try:
                    # Get process metrics for pod
                    process = psutil.Process(pod.status.pid)
                    
                    # Add CPU metrics
                    cpu_percent = process.cpu_percent()
                    metrics.append(Metric(
                        name="pod_cpu_percent",
                        value=cpu_percent,
                        labels={
                            "namespace": pod.namespace,
                            "name": pod.name,
                            "unit": "percent"
                        }
                    ))
                    
                    # Add memory metrics
                    memory_info = process.memory_info()
                    metrics.append(Metric(
                        name="pod_memory_rss",
                        value=memory_info.rss,
                        labels={
                            "namespace": pod.namespace,
                            "name": pod.name,
                            "unit": "bytes"
                        }
                    ))
                    metrics.append(Metric(
                        name="pod_memory_vms",
                        value=memory_info.vms,
                        labels={
                            "namespace": pod.namespace,
                            "name": pod.name,
                            "unit": "bytes"
                        }
                    ))
                    
                    # Add thread count
                    thread_count = len(process.threads())
                    metrics.append(Metric(
                        name="pod_thread_count",
                        value=thread_count,
                        labels={
                            "namespace": pod.namespace,
                            "name": pod.name
                        }
                    ))
                    
                    # Add file descriptor count
                    try:
                        fd_count = process.num_fds()
                        metrics.append(Metric(
                            name="pod_fd_count",
                            value=fd_count,
                            labels={
                                "namespace": pod.namespace,
                                "name": pod.name
                            }
                        ))
                    except (AttributeError, OSError):
                        pass
                    
                    # Add I/O metrics
                    try:
                        io_counters = process.io_counters()
                        metrics.append(Metric(
                            name="pod_io_read_count",
                            value=io_counters.read_count,
                            labels={
                                "namespace": pod.namespace,
                                "name": pod.name
                            }
                        ))
                        metrics.append(Metric(
                            name="pod_io_write_count",
                            value=io_counters.write_count,
                            labels={
                                "namespace": pod.namespace,
                                "name": pod.name
                            }
                        ))
                        metrics.append(Metric(
                            name="pod_io_read_bytes",
                            value=io_counters.read_bytes,
                            labels={
                                "namespace": pod.namespace,
                                "name": pod.name,
                                "unit": "bytes"
                            }
                        ))
                        metrics.append(Metric(
                            name="pod_io_write_bytes",
                            value=io_counters.write_bytes,
                            labels={
                                "namespace": pod.namespace,
                                "name": pod.name,
                                "unit": "bytes"
                            }
                        ))
                    except (AttributeError, OSError):
                        pass
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as e:
            logger.error(f"Failed to collect pod metrics: {e}")
        
        return metrics
    
    def _cache_metrics(self, metrics: List[Metric]) -> None:
        """
        Cache metrics for later retrieval.
        
        Args:
            metrics: List of metrics to cache
        """
        with self._lock:
            for metric in metrics:
                if metric.name not in self._metrics_cache:
                    self._metrics_cache[metric.name] = []
                
                self._metrics_cache[metric.name].append(metric)
    
    def _save_metrics(self) -> bool:
        """
        Save metrics to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Create metrics data
                metrics_data = {}
                
                for name, metrics in self._metrics_cache.items():
                    metrics_data[name] = [metric.to_dict() for metric in metrics]
                
                # Save to file
                file_path = os.path.join(METRICS_PATH, f"metrics_{int(time.time())}.json")
                
                with open(file_path, 'w') as f:
                    json.dump(metrics_data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
            return False
    
    def _cleanup_old_metrics(self) -> int:
        """
        Clean up old metrics.
        
        Returns:
            Number of old metrics removed
        """
        try:
            with self._lock:
                # Calculate cutoff time
                cutoff_time = time.time() - self.config.retention_period
                
                # Remove old metrics from cache
                for name in list(self._metrics_cache.keys()):
                    self._metrics_cache[name] = [
                        metric for metric in self._metrics_cache[name]
                        if metric.timestamp >= cutoff_time
                    ]
                
                # Remove empty entries
                self._metrics_cache = {
                    name: metrics for name, metrics in self._metrics_cache.items()
                    if metrics
                }
                
                # Remove old files
                removed = 0
                for filename in os.listdir(METRICS_PATH):
                    if not filename.startswith('metrics_') or not filename.endswith('.json'):
                        continue
                    
                    try:
                        # Extract timestamp from filename
                        timestamp_str = filename[len('metrics_'):-len('.json')]
                        timestamp = int(timestamp_str)
                        
                        if timestamp < cutoff_time:
                            file_path = os.path.join(METRICS_PATH, filename)
                            os.remove(file_path)
                            removed += 1
                    except (ValueError, OSError):
                        continue
                
                return removed
        except Exception as e:
            logger.error(f"Failed to clean up old metrics: {e}")
            return 0
    
    def get_metrics(self, name: Optional[str] = None, 
                   start_time: Optional[float] = None,
                   end_time: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None) -> List[Metric]:
        """
        Get metrics from the cache.
        
        Args:
            name: Metric name to filter by
            start_time: Start time (in seconds since epoch)
            end_time: End time (in seconds since epoch)
            labels: Labels to filter by
            
        Returns:
            List of metrics
        """
        with self._lock:
            result = []
            
            # Set default times
            if start_time is None:
                start_time = 0
            
            if end_time is None:
                end_time = time.time()
            
            # Filter by name
            if name:
                if name in self._metrics_cache:
                    metrics = self._metrics_cache[name]
                else:
                    return []
            else:
                # Flatten all metrics
                metrics = []
                for name_metrics in self._metrics_cache.values():
                    metrics.extend(name_metrics)
            
            # Filter by time and labels
            for metric in metrics:
                if metric.timestamp < start_time or metric.timestamp > end_time:
                    continue
                
                if labels:
                    match = True
                    for key, value in labels.items():
                        if metric.labels.get(key) != value:
                            match = False
                            break
                    
                    if not match:
                        continue
                
                result.append(metric)
            
            return result
    
    def get_metric_names(self) -> List[str]:
        """
        Get all metric names.
        
        Returns:
            List of metric names
        """
        with self._lock:
            return list(self._metrics_cache.keys())
    
    def get_metric_labels(self, name: str) -> Set[str]:
        """
        Get all label keys for a metric.
        
        Args:
            name: Metric name
            
        Returns:
            Set of label keys
        """
        with self._lock:
            if name not in self._metrics_cache:
                return set()
            
            labels = set()
            for metric in self._metrics_cache[name]:
                labels.update(metric.labels.keys())
            
            return labels
    
    @staticmethod
    def instance() -> 'MetricsCollector':
        """
        Get the singleton instance.
        
        Returns:
            MetricsCollector instance
        """
        return MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """
    Get the metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    return MetricsCollector.instance()


def start_metrics_collector() -> bool:
    """
    Start the metrics collector.
    
    Returns:
        bool: Success or failure
    """
    collector = MetricsCollector.instance()
    return collector.start()


def stop_metrics_collector() -> bool:
    """
    Stop the metrics collector.
    
    Returns:
        bool: Success or failure
    """
    collector = MetricsCollector.instance()
    return collector.stop()

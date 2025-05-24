"""
SystemMetrics Component for KADVLayer

This module provides system metrics collection and analysis capabilities,
allowing KOS to gather performance data from the host system.
"""

import os
import sys
import time
import json
import threading
import logging
import statistics
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
from collections import deque

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.system_metrics')

class MetricSeries:
    """Time series data for a metric"""
    
    def __init__(self, name: str, max_points: int = 300):
        """
        Initialize metric series
        
        Args:
            name: Metric name
            max_points: Maximum number of data points to store
        """
        self.name = name
        self.max_points = max_points
        self.timestamps = deque(maxlen=max_points)
        self.values = deque(maxlen=max_points)
    
    def add_point(self, timestamp: Union[float, datetime], value: float):
        """
        Add data point to series
        
        Args:
            timestamp: Timestamp (datetime or float)
            value: Metric value
        """
        if isinstance(timestamp, datetime):
            timestamp = timestamp.timestamp()
        
        self.timestamps.append(timestamp)
        self.values.append(value)
    
    def get_points(self, count: Optional[int] = None) -> List[Tuple[float, float]]:
        """
        Get data points
        
        Args:
            count: Number of points to return (None for all)
            
        Returns:
            List of (timestamp, value) tuples
        """
        if count is None or count >= len(self.timestamps):
            return list(zip(self.timestamps, self.values))
        else:
            return list(zip(list(self.timestamps)[-count:], list(self.values)[-count:]))
    
    def get_statistics(self) -> Dict[str, float]:
        """
        Get statistical analysis of values
        
        Returns:
            Dictionary with statistics
        """
        if not self.values:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "std_dev": None
            }
        
        values_list = list(self.values)
        
        stats = {
            "count": len(values_list),
            "min": min(values_list),
            "max": max(values_list),
            "mean": statistics.mean(values_list),
            "median": statistics.median(values_list)
        }
        
        if len(values_list) >= 2:
            try:
                stats["std_dev"] = statistics.stdev(values_list)
            except:
                stats["std_dev"] = None
        else:
            stats["std_dev"] = None
        
        return stats
    
    def clear(self):
        """Clear all data points"""
        self.timestamps.clear()
        self.values.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "name": self.name,
            "points": self.get_points(),
            "statistics": self.get_statistics()
        }

class SystemMetrics:
    """
    Collects and analyzes system metrics
    
    This class provides methods to collect, store, and analyze
    system performance metrics over time.
    """
    
    def __init__(self):
        """Initialize the SystemMetrics component"""
        self.collecting = False
        self.collector_thread = None
        self.lock = threading.RLock()
        
        # Metrics series
        self.metrics = {
            "cpu": {},
            "memory": {},
            "disk": {},
            "network": {},
            "process": {},
            "custom": {}
        }
        
        # Collection interval (seconds)
        self.interval = 10.0
        
        # Retention periods (seconds)
        self.retention = {
            "high_res": 3600,  # 1 hour of raw data
            "hourly": 86400,   # 24 hours of hourly data
            "daily": 2592000   # 30 days of daily data
        }
        
        # Initialize standard metrics
        self._init_standard_metrics()
        
        logger.debug("SystemMetrics component initialized")
    
    def _init_standard_metrics(self):
        """Initialize standard system metrics"""
        # CPU metrics
        self.metrics["cpu"]["usage"] = MetricSeries("cpu.usage")
        self.metrics["cpu"]["user"] = MetricSeries("cpu.user")
        self.metrics["cpu"]["system"] = MetricSeries("cpu.system")
        self.metrics["cpu"]["idle"] = MetricSeries("cpu.idle")
        
        # Memory metrics
        self.metrics["memory"]["usage"] = MetricSeries("memory.usage")
        self.metrics["memory"]["available"] = MetricSeries("memory.available")
        self.metrics["memory"]["used"] = MetricSeries("memory.used")
        self.metrics["memory"]["swap_used"] = MetricSeries("memory.swap_used")
        
        # Disk metrics
        self.metrics["disk"]["usage"] = MetricSeries("disk.usage")
        self.metrics["disk"]["read_bytes"] = MetricSeries("disk.read_bytes")
        self.metrics["disk"]["write_bytes"] = MetricSeries("disk.write_bytes")
        
        # Network metrics
        self.metrics["network"]["bytes_sent"] = MetricSeries("network.bytes_sent")
        self.metrics["network"]["bytes_recv"] = MetricSeries("network.bytes_recv")
        self.metrics["network"]["connections"] = MetricSeries("network.connections")
    
    def start_collection(self, interval: Optional[float] = None) -> bool:
        """
        Start metrics collection
        
        Args:
            interval: Collection interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.collecting:
                logger.warning("Metrics collection already running")
                return False
            
            if not PSUTIL_AVAILABLE:
                logger.error("Cannot collect metrics without psutil")
                return False
            
            if interval is not None:
                self.interval = max(1.0, interval)  # Minimum 1 second
            
            self.collecting = True
            self.collector_thread = threading.Thread(target=self._collector_loop, daemon=True)
            self.collector_thread.start()
            
            logger.info(f"Started metrics collection with interval {self.interval}s")
            return True
    
    def stop_collection(self) -> bool:
        """
        Stop metrics collection
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.collecting:
                logger.warning("Metrics collection not running")
                return False
            
            self.collecting = False
            
            # Wait for thread to finish
            if self.collector_thread and self.collector_thread.is_alive():
                self.collector_thread.join(timeout=2.0)
            
            logger.info("Stopped metrics collection")
            return True
    
    def _collector_loop(self):
        """Main metrics collector loop"""
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot collect metrics without psutil")
            self.collecting = False
            return
        
        # Previous values for rate calculations
        prev_disk_io = None
        prev_net_io = None
        prev_time = time.time()
        
        while self.collecting:
            try:
                current_time = time.time()
                now = datetime.now()
                
                # Collect CPU metrics
                cpu_percent = psutil.cpu_percent(interval=0.1)
                cpu_times_percent = psutil.cpu_times_percent(interval=0.1)
                
                with self.lock:
                    self.metrics["cpu"]["usage"].add_point(now, cpu_percent)
                    self.metrics["cpu"]["user"].add_point(now, cpu_times_percent.user)
                    self.metrics["cpu"]["system"].add_point(now, cpu_times_percent.system)
                    self.metrics["cpu"]["idle"].add_point(now, cpu_times_percent.idle)
                
                # Collect memory metrics
                virtual_mem = psutil.virtual_memory()
                swap_mem = psutil.swap_memory()
                
                with self.lock:
                    self.metrics["memory"]["usage"].add_point(now, virtual_mem.percent)
                    self.metrics["memory"]["available"].add_point(now, virtual_mem.available)
                    self.metrics["memory"]["used"].add_point(now, virtual_mem.used)
                    self.metrics["memory"]["swap_used"].add_point(now, swap_mem.used)
                
                # Collect disk metrics
                disk_usage = psutil.disk_usage('/')
                disk_io = psutil.disk_io_counters()
                
                with self.lock:
                    self.metrics["disk"]["usage"].add_point(now, disk_usage.percent)
                    
                    if prev_disk_io:
                        # Calculate rates
                        time_diff = current_time - prev_time
                        read_bytes_rate = (disk_io.read_bytes - prev_disk_io.read_bytes) / time_diff
                        write_bytes_rate = (disk_io.write_bytes - prev_disk_io.write_bytes) / time_diff
                        
                        self.metrics["disk"]["read_bytes"].add_point(now, read_bytes_rate)
                        self.metrics["disk"]["write_bytes"].add_point(now, write_bytes_rate)
                
                # Collect network metrics
                net_io = psutil.net_io_counters()
                net_connections = len(psutil.net_connections())
                
                with self.lock:
                    if prev_net_io:
                        # Calculate rates
                        time_diff = current_time - prev_time
                        bytes_sent_rate = (net_io.bytes_sent - prev_net_io.bytes_sent) / time_diff
                        bytes_recv_rate = (net_io.bytes_recv - prev_net_io.bytes_recv) / time_diff
                        
                        self.metrics["network"]["bytes_sent"].add_point(now, bytes_sent_rate)
                        self.metrics["network"]["bytes_recv"].add_point(now, bytes_recv_rate)
                    
                    self.metrics["network"]["connections"].add_point(now, net_connections)
                
                # Update previous values
                prev_disk_io = disk_io
                prev_net_io = net_io
                prev_time = current_time
                
                # Sleep until next collection
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                time.sleep(self.interval)
    
    def add_metric_point(self, category: str, name: str, value: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Add a metric data point
        
        Args:
            category: Metric category
            name: Metric name
            value: Metric value
            timestamp: Timestamp (None for current time)
            
        Returns:
            Success status
        """
        if category not in self.metrics:
            logger.error(f"Invalid metric category: {category}")
            return False
        
        metric_id = f"{name}"
        timestamp = timestamp or datetime.now()
        
        with self.lock:
            # Create metric series if it doesn't exist
            if metric_id not in self.metrics[category]:
                self.metrics[category][metric_id] = MetricSeries(f"{category}.{name}")
            
            # Add data point
            self.metrics[category][metric_id].add_point(timestamp, value)
            
            return True
    
    def add_process_metric(self, pid: int, name: str, value: float, timestamp: Optional[datetime] = None) -> bool:
        """
        Add a process-specific metric
        
        Args:
            pid: Process ID
            name: Metric name
            value: Metric value
            timestamp: Timestamp (None for current time)
            
        Returns:
            Success status
        """
        metric_id = f"{pid}.{name}"
        timestamp = timestamp or datetime.now()
        
        with self.lock:
            # Create metric series if it doesn't exist
            if metric_id not in self.metrics["process"]:
                self.metrics["process"][metric_id] = MetricSeries(f"process.{pid}.{name}")
            
            # Add data point
            self.metrics["process"][metric_id].add_point(timestamp, value)
            
            return True
    
    def get_metric(self, category: str, name: str) -> Optional[Dict[str, Any]]:
        """
        Get metric data
        
        Args:
            category: Metric category
            name: Metric name
            
        Returns:
            Dictionary with metric data
        """
        if category not in self.metrics:
            logger.error(f"Invalid metric category: {category}")
            return None
        
        with self.lock:
            metric = self.metrics[category].get(name)
            if metric:
                return metric.to_dict()
            else:
                return None
    
    def get_metric_categories(self) -> List[str]:
        """
        Get available metric categories
        
        Returns:
            List of metric categories
        """
        return list(self.metrics.keys())
    
    def get_metric_names(self, category: str) -> List[str]:
        """
        Get available metrics in category
        
        Args:
            category: Metric category
            
        Returns:
            List of metric names
        """
        if category not in self.metrics:
            logger.error(f"Invalid metric category: {category}")
            return []
        
        return list(self.metrics[category].keys())
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of all metrics
        
        Returns:
            Dictionary with metrics summary
        """
        summary = {}
        
        with self.lock:
            for category, metrics in self.metrics.items():
                category_data = {}
                
                for name, metric in metrics.items():
                    stats = metric.get_statistics()
                    if stats["count"] > 0:
                        category_data[name] = {
                            "current": list(metric.values)[-1] if metric.values else None,
                            "min": stats["min"],
                            "max": stats["max"],
                            "mean": stats["mean"],
                            "points_count": stats["count"]
                        }
                
                if category_data:
                    summary[category] = category_data
        
        return summary
    
    def export_metrics(self, format_type: str = "json") -> str:
        """
        Export metrics data
        
        Args:
            format_type: Export format (json, csv)
            
        Returns:
            Exported data string
        """
        if format_type == "json":
            data = {}
            
            with self.lock:
                for category, metrics in self.metrics.items():
                    category_data = {}
                    
                    for name, metric in metrics.items():
                        category_data[name] = metric.to_dict()
                    
                    data[category] = category_data
            
            return json.dumps(data, indent=2)
        else:
            logger.error(f"Unsupported export format: {format_type}")
            return ""
    
    def clear_metrics(self, category: Optional[str] = None, name: Optional[str] = None) -> bool:
        """
        Clear metrics data
        
        Args:
            category: Metric category (None for all)
            name: Metric name (None for all in category)
            
        Returns:
            Success status
        """
        with self.lock:
            if category is None:
                # Clear all metrics
                for cat in self.metrics:
                    for metric in self.metrics[cat].values():
                        metric.clear()
                
                logger.debug("Cleared all metrics")
                return True
            
            if category not in self.metrics:
                logger.error(f"Invalid metric category: {category}")
                return False
            
            if name is None:
                # Clear all metrics in category
                for metric in self.metrics[category].values():
                    metric.clear()
                
                logger.debug(f"Cleared all metrics in category: {category}")
                return True
            
            if name not in self.metrics[category]:
                logger.error(f"Invalid metric name: {name}")
                return False
            
            # Clear specific metric
            self.metrics[category][name].clear()
            logger.debug(f"Cleared metric: {category}.{name}")
            return True
    
    def is_collecting(self) -> bool:
        """
        Check if collection is active
        
        Returns:
            Whether collection is active
        """
        return self.collecting
    
    def analyze_trend(self, category: str, name: str, period: str = "1h") -> Dict[str, Any]:
        """
        Analyze metric trend
        
        Args:
            category: Metric category
            name: Metric name
            period: Time period (e.g., 1h, 24h)
            
        Returns:
            Dictionary with trend analysis
        """
        if category not in self.metrics:
            logger.error(f"Invalid metric category: {category}")
            return {"error": "Invalid category"}
        
        if name not in self.metrics[category]:
            logger.error(f"Invalid metric name: {name}")
            return {"error": "Invalid metric name"}
        
        metric = self.metrics[category][name]
        points = metric.get_points()
        
        if not points:
            return {"trend": "no_data", "points_count": 0}
        
        # Parse period
        try:
            period_value = int(period[:-1])
            period_unit = period[-1]
            
            if period_unit == 'h':
                seconds = period_value * 3600
            elif period_unit == 'd':
                seconds = period_value * 86400
            else:
                seconds = 3600  # Default to 1h
        except:
            seconds = 3600
        
        # Filter points by time
        now = time.time()
        filtered_points = [(ts, val) for ts, val in points if now - ts <= seconds]
        
        if not filtered_points:
            return {"trend": "no_data", "points_count": 0}
        
        # Extract values
        values = [val for _, val in filtered_points]
        
        # Calculate trend
        if len(values) < 2:
            trend = "stable"
        else:
            first_half = values[:len(values)//2]
            second_half = values[len(values)//2:]
            
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            # Calculate percent change
            if first_avg == 0:
                percent_change = 0
            else:
                percent_change = ((second_avg - first_avg) / first_avg) * 100
            
            if percent_change > 10:
                trend = "rising"
            elif percent_change < -10:
                trend = "falling"
            else:
                trend = "stable"
        
        # Calculate statistics
        stats = {
            "trend": trend,
            "points_count": len(filtered_points),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "current": values[-1],
            "start": values[0]
        }
        
        if NUMPY_AVAILABLE and len(values) > 1:
            try:
                # Linear regression for more accurate trend
                x = np.array(range(len(values)))
                y = np.array(values)
                slope, intercept = np.polyfit(x, y, 1)
                
                stats["slope"] = slope
                stats["intercept"] = intercept
                
                if abs(slope) < 0.01 * (max(values) - min(values)):
                    stats["trend"] = "stable"
                elif slope > 0:
                    stats["trend"] = "rising"
                else:
                    stats["trend"] = "falling"
            except:
                pass
        
        return stats

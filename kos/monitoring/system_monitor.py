"""
System monitoring and performance tools for KOS
"""

import time
import threading
import psutil
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

class MetricType(Enum):
    """Types of system metrics"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    SYSTEM = "system"

@dataclass
class Metric:
    """System metric"""
    timestamp: float
    type: MetricType
    name: str
    value: float
    unit: str = ""
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class Alert:
    """System alert"""
    timestamp: float
    severity: str  # info, warning, critical
    metric: str
    message: str
    value: float
    threshold: float

class SystemMonitor:
    """System resource monitor"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Metrics storage
        self.metrics: Dict[str, Deque[Metric]] = {}
        self.max_history = 1000
        
        # Alerts
        self.alerts: List[Alert] = []
        self.thresholds = {
            'cpu_percent': 80.0,
            'memory_percent': 90.0,
            'disk_percent': 95.0,
            'load_average': 4.0
        }
        
        # Collection interval
        self.interval = 5  # seconds
    
    def start(self):
        """Start monitoring"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            self._collect_metrics()
            self._check_thresholds()
            time.sleep(self.interval)
    
    def _collect_metrics(self):
        """Collect system metrics"""
        timestamp = time.time()
        
        # CPU metrics
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.CPU,
                name="cpu_percent",
                value=cpu_percent,
                unit="%"
            ))
            
            cpu_count = psutil.cpu_count()
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.CPU,
                name="cpu_count",
                value=cpu_count,
                unit="cores"
            ))
            
            # Per-CPU usage
            for i, percent in enumerate(psutil.cpu_percent(percpu=True)):
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.CPU,
                    name=f"cpu{i}_percent",
                    value=percent,
                    unit="%",
                    tags={"cpu": str(i)}
                ))
        except:
            pass
        
        # Memory metrics
        try:
            mem = psutil.virtual_memory()
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.MEMORY,
                name="memory_percent",
                value=mem.percent,
                unit="%"
            ))
            
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.MEMORY,
                name="memory_used",
                value=mem.used,
                unit="bytes"
            ))
            
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.MEMORY,
                name="memory_available",
                value=mem.available,
                unit="bytes"
            ))
            
            swap = psutil.swap_memory()
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.MEMORY,
                name="swap_percent",
                value=swap.percent,
                unit="%"
            ))
        except:
            pass
        
        # Disk metrics
        try:
            disk = psutil.disk_usage('/')
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.DISK,
                name="disk_percent",
                value=disk.percent,
                unit="%"
            ))
            
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.DISK,
                name="disk_used",
                value=disk.used,
                unit="bytes"
            ))
            
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.DISK,
                name="disk_free",
                value=disk.free,
                unit="bytes"
            ))
            
            # Disk I/O
            io_counters = psutil.disk_io_counters()
            if io_counters:
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.DISK,
                    name="disk_read_bytes",
                    value=io_counters.read_bytes,
                    unit="bytes"
                ))
                
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.DISK,
                    name="disk_write_bytes",
                    value=io_counters.write_bytes,
                    unit="bytes"
                ))
        except:
            pass
        
        # Network metrics
        try:
            net = psutil.net_io_counters()
            if net:
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.NETWORK,
                    name="network_bytes_sent",
                    value=net.bytes_sent,
                    unit="bytes"
                ))
                
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.NETWORK,
                    name="network_bytes_recv",
                    value=net.bytes_recv,
                    unit="bytes"
                ))
                
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.NETWORK,
                    name="network_packets_sent",
                    value=net.packets_sent,
                    unit="packets"
                ))
                
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.NETWORK,
                    name="network_packets_recv",
                    value=net.packets_recv,
                    unit="packets"
                ))
        except:
            pass
        
        # System metrics
        try:
            # Load average
            load_avg = psutil.getloadavg()
            for i, load in enumerate(load_avg):
                self._add_metric(Metric(
                    timestamp=timestamp,
                    type=MetricType.SYSTEM,
                    name=f"load_avg_{[1, 5, 15][i]}min",
                    value=load,
                    unit=""
                ))
            
            # Boot time
            boot_time = psutil.boot_time()
            uptime = time.time() - boot_time
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.SYSTEM,
                name="uptime",
                value=uptime,
                unit="seconds"
            ))
            
            # Process count
            process_count = len(psutil.pids())
            self._add_metric(Metric(
                timestamp=timestamp,
                type=MetricType.SYSTEM,
                name="process_count",
                value=process_count,
                unit="processes"
            ))
        except:
            pass
    
    def _add_metric(self, metric: Metric):
        """Add metric to storage"""
        if metric.name not in self.metrics:
            self.metrics[metric.name] = deque(maxlen=self.max_history)
        
        self.metrics[metric.name].append(metric)
    
    def _check_thresholds(self):
        """Check metrics against thresholds"""
        for metric_name, threshold in self.thresholds.items():
            if metric_name in self.metrics:
                latest = list(self.metrics[metric_name])
                if latest:
                    value = latest[-1].value
                    if value > threshold:
                        self._create_alert(metric_name, value, threshold)
    
    def _create_alert(self, metric: str, value: float, threshold: float):
        """Create alert"""
        severity = "warning"
        if value > threshold * 1.2:
            severity = "critical"
        
        alert = Alert(
            timestamp=time.time(),
            severity=severity,
            metric=metric,
            message=f"{metric} exceeded threshold: {value:.1f} > {threshold:.1f}",
            value=value,
            threshold=threshold
        )
        
        self.alerts.append(alert)
        
        # Keep only recent alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_metrics(self, metric_name: str = None, 
                   duration: int = 3600) -> List[Metric]:
        """Get metrics for specified duration"""
        cutoff_time = time.time() - duration
        
        if metric_name:
            if metric_name in self.metrics:
                return [m for m in self.metrics[metric_name] 
                       if m.timestamp >= cutoff_time]
            return []
        
        # Get all metrics
        all_metrics = []
        for metrics_list in self.metrics.values():
            all_metrics.extend([m for m in metrics_list 
                              if m.timestamp >= cutoff_time])
        
        return sorted(all_metrics, key=lambda x: x.timestamp)
    
    def get_current_stats(self) -> Dict:
        """Get current system statistics"""
        stats = {}
        
        for metric_name, metrics_list in self.metrics.items():
            if metrics_list:
                latest = metrics_list[-1]
                stats[metric_name] = {
                    'value': latest.value,
                    'unit': latest.unit,
                    'timestamp': latest.timestamp
                }
        
        return stats
    
    def get_alerts(self, severity: str = None) -> List[Alert]:
        """Get system alerts"""
        if severity:
            return [a for a in self.alerts if a.severity == severity]
        return self.alerts
    
    def set_threshold(self, metric: str, value: float):
        """Set alert threshold"""
        self.thresholds[metric] = value
    
    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in various formats"""
        if format == "json":
            import json
            data = []
            for metric_name, metrics_list in self.metrics.items():
                for metric in metrics_list:
                    data.append({
                        'timestamp': metric.timestamp,
                        'type': metric.type.value,
                        'name': metric.name,
                        'value': metric.value,
                        'unit': metric.unit,
                        'tags': metric.tags
                    })
            return json.dumps(data, indent=2)
        
        elif format == "csv":
            lines = ["timestamp,type,name,value,unit"]
            for metric_name, metrics_list in self.metrics.items():
                for metric in metrics_list:
                    lines.append(f"{metric.timestamp},{metric.type.value},"
                               f"{metric.name},{metric.value},{metric.unit}")
            return "\n".join(lines)
        
        return ""

class ProcessMonitor:
    """Process-level monitoring"""
    
    def __init__(self):
        self.processes: Dict[int, Dict] = {}
    
    def update(self):
        """Update process information"""
        current_pids = set()
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 
                                        'memory_percent', 'status']):
            try:
                info = proc.info
                pid = info['pid']
                current_pids.add(pid)
                
                self.processes[pid] = {
                    'pid': pid,
                    'name': info['name'],
                    'cpu_percent': info['cpu_percent'],
                    'memory_percent': info['memory_percent'],
                    'status': info['status'],
                    'updated': time.time()
                }
            except:
                pass
        
        # Remove dead processes
        dead_pids = set(self.processes.keys()) - current_pids
        for pid in dead_pids:
            del self.processes[pid]
    
    def get_top_processes(self, by: str = "cpu", limit: int = 10) -> List[Dict]:
        """Get top processes by resource usage"""
        self.update()
        
        sort_key = f"{by}_percent"
        sorted_procs = sorted(self.processes.values(), 
                            key=lambda x: x.get(sort_key, 0),
                            reverse=True)
        
        return sorted_procs[:limit]
    
    def get_process(self, pid: int) -> Optional[Dict]:
        """Get specific process info"""
        self.update()
        return self.processes.get(pid)

class ResourceLimits:
    """Resource limit management"""
    
    def __init__(self):
        self.limits = {
            'max_processes': 1000,
            'max_open_files': 10000,
            'max_memory_mb': 8192,
            'max_cpu_percent': 100
        }
        
        self.usage = {
            'processes': 0,
            'open_files': 0,
            'memory_mb': 0,
            'cpu_percent': 0
        }
    
    def check_limits(self) -> List[str]:
        """Check if any limits are exceeded"""
        violations = []
        
        try:
            # Check process limit
            process_count = len(psutil.pids())
            if process_count > self.limits['max_processes']:
                violations.append(f"Process limit exceeded: {process_count} > {self.limits['max_processes']}")
            
            # Check memory limit
            mem = psutil.virtual_memory()
            mem_used_mb = mem.used / (1024 * 1024)
            if mem_used_mb > self.limits['max_memory_mb']:
                violations.append(f"Memory limit exceeded: {mem_used_mb:.0f}MB > {self.limits['max_memory_mb']}MB")
            
            # Check CPU limit
            cpu_percent = psutil.cpu_percent()
            if cpu_percent > self.limits['max_cpu_percent']:
                violations.append(f"CPU limit exceeded: {cpu_percent:.1f}% > {self.limits['max_cpu_percent']}%")
        except:
            pass
        
        return violations
    
    def set_limit(self, resource: str, value: int):
        """Set resource limit"""
        if resource in self.limits:
            self.limits[resource] = value
    
    def get_limits(self) -> Dict:
        """Get all resource limits"""
        return self.limits.copy()
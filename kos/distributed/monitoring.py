"""
Distributed Monitoring and Metrics for KOS Cluster
Provides real-time monitoring of cluster health and performance
"""

import time
import threading
import json
import statistics
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"      # Monotonically increasing
    GAUGE = "gauge"          # Point-in-time value
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"      # Statistical summary

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Metric:
    """Individual metric"""
    name: str
    type: MetricType
    value: float
    timestamp: float
    node_id: str
    labels: Dict[str, str] = field(default_factory=dict)
    unit: str = ""

@dataclass
class Alert:
    """System alert"""
    alert_id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp: float
    node_id: str
    metric: Optional[str] = None
    threshold: Optional[float] = None
    actual: Optional[float] = None
    resolved: bool = False
    resolution_time: Optional[float] = None

@dataclass
class NodeMetrics:
    """Metrics for a single node"""
    node_id: str
    timestamp: float
    
    # System metrics
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    memory_total: int = 0
    disk_usage: float = 0.0
    disk_total: int = 0
    network_rx: int = 0
    network_tx: int = 0
    
    # Cluster metrics
    active_connections: int = 0
    message_rate: float = 0.0
    consensus_term: int = 0
    is_leader: bool = False
    
    # Process metrics
    process_count: int = 0
    thread_count: int = 0
    
    # VFS metrics
    file_count: int = 0
    vfs_operations: int = 0
    replication_lag: float = 0.0
    
    # Memory metrics
    page_faults: int = 0
    page_hits: int = 0
    migrations: int = 0
    
    # Custom metrics
    custom: Dict[str, float] = field(default_factory=dict)

class ClusterMonitor:
    """Distributed monitoring system for KOS cluster"""
    
    def __init__(self, cluster_node, update_interval: int = 5):
        self.cluster = cluster_node
        self.update_interval = update_interval
        
        # Metrics storage
        self.current_metrics: Dict[str, NodeMetrics] = {}
        self.metrics_history: Dict[str, deque] = {}  # Node -> History
        self.history_size = 100  # Keep last N samples
        
        # Aggregated metrics
        self.cluster_metrics: Dict[str, float] = {}
        
        # Alerts
        self.alerts: List[Alert] = []
        self.alert_rules: List[Dict] = []
        self.active_alerts: Dict[str, Alert] = {}
        
        # Thresholds
        self.thresholds = {
            'cpu_critical': 90.0,
            'cpu_warning': 70.0,
            'memory_critical': 90.0,
            'memory_warning': 80.0,
            'disk_critical': 95.0,
            'disk_warning': 85.0,
            'replication_lag_warning': 5.0,
            'node_failure_timeout': 30.0
        }
        
        # Performance tracking
        self.performance_data: Dict[str, deque] = {}
        
        # Thread control
        self.lock = threading.RLock()
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.aggregator_thread = threading.Thread(target=self._aggregator_loop)
        self.aggregator_thread.daemon = True
        self.alert_thread = threading.Thread(target=self._alert_loop)
        self.alert_thread.daemon = True
        self.running = False
        
        self._initialize_alert_rules()
    
    def start(self):
        """Start monitoring"""
        self.running = True
        self.monitor_thread.start()
        self.aggregator_thread.start()
        self.alert_thread.start()
        logger.info("Cluster monitoring started")
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        logger.info("Cluster monitoring stopped")
    
    def _initialize_alert_rules(self):
        """Initialize default alert rules"""
        self.alert_rules = [
            {
                'name': 'high_cpu',
                'metric': 'cpu_usage',
                'condition': 'greater_than',
                'threshold': self.thresholds['cpu_critical'],
                'severity': AlertSeverity.ERROR,
                'title': 'High CPU Usage',
                'message': 'CPU usage is above {threshold}%'
            },
            {
                'name': 'high_memory',
                'metric': 'memory_usage',
                'condition': 'greater_than',
                'threshold': self.thresholds['memory_critical'],
                'severity': AlertSeverity.ERROR,
                'title': 'High Memory Usage',
                'message': 'Memory usage is above {threshold}%'
            },
            {
                'name': 'disk_space',
                'metric': 'disk_usage',
                'condition': 'greater_than',
                'threshold': self.thresholds['disk_critical'],
                'severity': AlertSeverity.CRITICAL,
                'title': 'Low Disk Space',
                'message': 'Disk usage is above {threshold}%'
            },
            {
                'name': 'replication_lag',
                'metric': 'replication_lag',
                'condition': 'greater_than',
                'threshold': self.thresholds['replication_lag_warning'],
                'severity': AlertSeverity.WARNING,
                'title': 'Replication Lag',
                'message': 'Replication lag is {actual:.1f}s (threshold: {threshold}s)'
            },
            {
                'name': 'node_down',
                'metric': 'node_responsive',
                'condition': 'equals',
                'threshold': 0,
                'severity': AlertSeverity.CRITICAL,
                'title': 'Node Down',
                'message': 'Node {node_id} is not responding'
            }
        ]
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Collect local metrics
                local_metrics = self._collect_local_metrics()
                
                with self.lock:
                    # Store metrics
                    self.current_metrics[self.cluster.node_id] = local_metrics
                    
                    # Add to history
                    if self.cluster.node_id not in self.metrics_history:
                        self.metrics_history[self.cluster.node_id] = deque(maxlen=self.history_size)
                    self.metrics_history[self.cluster.node_id].append(local_metrics)
                    
                    # Share with cluster
                    self._share_metrics(local_metrics)
                    
                    # Collect remote metrics
                    self._collect_remote_metrics()
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
    
    def _aggregator_loop(self):
        """Aggregate cluster metrics"""
        while self.running:
            try:
                time.sleep(self.update_interval * 2)  # Less frequent than collection
                
                with self.lock:
                    self._aggregate_metrics()
                    self._calculate_trends()
                    
            except Exception as e:
                logger.error(f"Aggregator loop error: {e}")
    
    def _alert_loop(self):
        """Check alert conditions"""
        while self.running:
            try:
                time.sleep(self.update_interval)
                
                with self.lock:
                    self._check_alerts()
                    self._cleanup_resolved_alerts()
                    
            except Exception as e:
                logger.error(f"Alert loop error: {e}")
    
    def _collect_local_metrics(self) -> NodeMetrics:
        """Collect metrics from local node"""
        metrics = NodeMetrics(
            node_id=self.cluster.node_id,
            timestamp=time.time()
        )
        
        # System metrics
        try:
            import psutil
            
            # CPU
            metrics.cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory
            mem = psutil.virtual_memory()
            metrics.memory_usage = mem.percent
            metrics.memory_total = mem.total
            
            # Disk
            disk = psutil.disk_usage('/')
            metrics.disk_usage = disk.percent
            metrics.disk_total = disk.total
            
            # Network
            net = psutil.net_io_counters()
            metrics.network_rx = net.bytes_recv
            metrics.network_tx = net.bytes_sent
            
            # Process info
            metrics.process_count = len(psutil.pids())
            
        except ImportError:
            # psutil not available, use dummy values
            import random
            metrics.cpu_usage = random.uniform(20, 60)
            metrics.memory_usage = random.uniform(30, 70)
            metrics.memory_total = 8 * 1024 * 1024 * 1024  # 8GB
            metrics.disk_usage = random.uniform(40, 80)
            metrics.disk_total = 100 * 1024 * 1024 * 1024  # 100GB
        
        # Cluster metrics
        metrics.active_connections = len(self.cluster.client_sockets)
        metrics.consensus_term = self.cluster.consensus.current_term
        metrics.is_leader = self.cluster.consensus.is_leader()
        
        # Get metrics from other components if available
        metrics = self._collect_component_metrics(metrics)
        
        return metrics
    
    def _collect_component_metrics(self, metrics: NodeMetrics) -> NodeMetrics:
        """Collect metrics from KOS components"""
        # VFS metrics
        if hasattr(self.cluster, 'dvfs') and self.cluster.dvfs:
            try:
                vfs_status = self.cluster.dvfs.get_replication_status()
                metrics.file_count = vfs_status.get('total_files', 0)
                metrics.vfs_operations = len(self.cluster.dvfs.op_log)
                
                # Calculate replication lag
                if self.cluster.dvfs.last_sync:
                    oldest_sync = min(self.cluster.dvfs.last_sync.values()) if self.cluster.dvfs.last_sync else time.time()
                    metrics.replication_lag = time.time() - oldest_sync
            except:
                pass
        
        # Memory metrics
        if hasattr(self.cluster, 'dmemory') and self.cluster.dmemory:
            try:
                mem_stats = self.cluster.dmemory.get_memory_stats()
                metrics.page_faults = mem_stats.get('page_faults', 0)
                metrics.page_hits = mem_stats.get('page_hits', 0)
                metrics.migrations = mem_stats.get('migrations', 0)
            except:
                pass
        
        # Scheduler metrics
        if hasattr(self.cluster, 'scheduler') and self.cluster.scheduler:
            try:
                metrics.process_count = len(self.cluster.scheduler.processes)
            except:
                pass
        
        return metrics
    
    def _share_metrics(self, metrics: NodeMetrics):
        """Share metrics with cluster"""
        from .cluster import MessageType
        
        # Broadcast metrics to all nodes
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.cluster.node_id:
                self.cluster.send_message(
                    node_id,
                    MessageType.STATE_UPDATE,
                    {
                        'type': 'metrics',
                        'metrics': asdict(metrics)
                    }
                )
    
    def _collect_remote_metrics(self):
        """Collect metrics from remote nodes"""
        from .cluster import MessageType
        
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.cluster.node_id:
                response = self.cluster.send_message(
                    node_id,
                    MessageType.INFO,
                    {'type': 'metrics'}
                )
                
                if response and 'metrics' in response:
                    metrics_dict = response['metrics']
                    metrics = NodeMetrics(**metrics_dict)
                    
                    # Store metrics
                    self.current_metrics[node_id] = metrics
                    
                    # Add to history
                    if node_id not in self.metrics_history:
                        self.metrics_history[node_id] = deque(maxlen=self.history_size)
                    self.metrics_history[node_id].append(metrics)
    
    def _aggregate_metrics(self):
        """Aggregate metrics across cluster"""
        if not self.current_metrics:
            return
        
        # Calculate cluster-wide metrics
        total_cpu = sum(m.cpu_usage for m in self.current_metrics.values())
        avg_cpu = total_cpu / len(self.current_metrics)
        
        total_memory_used = sum(
            m.memory_total * m.memory_usage / 100 
            for m in self.current_metrics.values()
            if m.memory_total > 0
        )
        total_memory = sum(m.memory_total for m in self.current_metrics.values())
        
        total_disk_used = sum(
            m.disk_total * m.disk_usage / 100
            for m in self.current_metrics.values()
            if m.disk_total > 0
        )
        total_disk = sum(m.disk_total for m in self.current_metrics.values())
        
        self.cluster_metrics = {
            'node_count': len(self.current_metrics),
            'avg_cpu': avg_cpu,
            'max_cpu': max(m.cpu_usage for m in self.current_metrics.values()),
            'total_memory': total_memory,
            'used_memory': total_memory_used,
            'memory_usage': (total_memory_used / total_memory * 100) if total_memory > 0 else 0,
            'total_disk': total_disk,
            'used_disk': total_disk_used,
            'disk_usage': (total_disk_used / total_disk * 100) if total_disk > 0 else 0,
            'total_processes': sum(m.process_count for m in self.current_metrics.values()),
            'total_files': sum(m.file_count for m in self.current_metrics.values()),
            'total_page_faults': sum(m.page_faults for m in self.current_metrics.values()),
            'total_migrations': sum(m.migrations for m in self.current_metrics.values()),
            'leader_count': sum(1 for m in self.current_metrics.values() if m.is_leader)
        }
    
    def _calculate_trends(self):
        """Calculate metric trends"""
        for node_id, history in self.metrics_history.items():
            if len(history) < 2:
                continue
            
            # Calculate trends for key metrics
            cpu_values = [m.cpu_usage for m in history]
            mem_values = [m.memory_usage for m in history]
            
            # Store in performance data
            if node_id not in self.performance_data:
                self.performance_data[node_id] = {}
            
            self.performance_data[node_id]['cpu_trend'] = self._calculate_trend(cpu_values)
            self.performance_data[node_id]['memory_trend'] = self._calculate_trend(mem_values)
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction"""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear regression
        recent = values[-10:]  # Last 10 samples
        if len(recent) < 2:
            return 'stable'
        
        avg_first_half = sum(recent[:len(recent)//2]) / (len(recent)//2)
        avg_second_half = sum(recent[len(recent)//2:]) / (len(recent) - len(recent)//2)
        
        diff = avg_second_half - avg_first_half
        
        if abs(diff) < 5:
            return 'stable'
        elif diff > 0:
            return 'increasing'
        else:
            return 'decreasing'
    
    def _check_alerts(self):
        """Check alert conditions"""
        for node_id, metrics in self.current_metrics.items():
            for rule in self.alert_rules:
                self._check_alert_rule(rule, metrics, node_id)
        
        # Check cluster-wide alerts
        self._check_cluster_alerts()
    
    def _check_alert_rule(self, rule: Dict, metrics: NodeMetrics, node_id: str):
        """Check individual alert rule"""
        metric_name = rule['metric']
        
        # Special handling for node responsiveness
        if metric_name == 'node_responsive':
            # Check if node is responding
            if node_id in self.cluster.nodes:
                node_info = self.cluster.nodes[node_id]
                if time.time() - node_info.last_seen > self.thresholds['node_failure_timeout']:
                    self._trigger_alert(rule, 0, node_id)
            return
        
        # Get metric value
        if hasattr(metrics, metric_name):
            value = getattr(metrics, metric_name)
        elif metric_name in metrics.custom:
            value = metrics.custom[metric_name]
        else:
            return
        
        # Check condition
        threshold = rule['threshold']
        triggered = False
        
        if rule['condition'] == 'greater_than' and value > threshold:
            triggered = True
        elif rule['condition'] == 'less_than' and value < threshold:
            triggered = True
        elif rule['condition'] == 'equals' and value == threshold:
            triggered = True
        
        if triggered:
            self._trigger_alert(rule, value, node_id)
        else:
            # Check if we should resolve an existing alert
            alert_key = f"{node_id}_{rule['name']}"
            if alert_key in self.active_alerts:
                self._resolve_alert(alert_key)
    
    def _check_cluster_alerts(self):
        """Check cluster-wide alert conditions"""
        if not self.cluster_metrics:
            return
        
        # Check for split-brain (multiple leaders)
        if self.cluster_metrics.get('leader_count', 0) > 1:
            self._trigger_cluster_alert(
                'split_brain',
                AlertSeverity.CRITICAL,
                'Split Brain Detected',
                f"Multiple leaders detected: {self.cluster_metrics['leader_count']}"
            )
        
        # Check for no leader
        if self.cluster_metrics.get('leader_count', 0) == 0:
            self._trigger_cluster_alert(
                'no_leader',
                AlertSeverity.CRITICAL,
                'No Leader',
                'No leader node in cluster'
            )
    
    def _trigger_alert(self, rule: Dict, value: float, node_id: str):
        """Trigger an alert"""
        alert_key = f"{node_id}_{rule['name']}"
        
        # Check if alert already active
        if alert_key in self.active_alerts:
            return
        
        # Create alert
        alert = Alert(
            alert_id=alert_key,
            severity=rule['severity'],
            title=rule['title'],
            message=rule['message'].format(
                threshold=rule['threshold'],
                actual=value,
                node_id=node_id
            ),
            timestamp=time.time(),
            node_id=node_id,
            metric=rule['metric'],
            threshold=rule['threshold'],
            actual=value
        )
        
        self.alerts.append(alert)
        self.active_alerts[alert_key] = alert
        
        logger.warning(f"Alert triggered: {alert.title} on {node_id}")
        
        # Notify cluster
        self._notify_alert(alert)
    
    def _trigger_cluster_alert(self, name: str, severity: AlertSeverity, 
                              title: str, message: str):
        """Trigger cluster-wide alert"""
        alert_key = f"cluster_{name}"
        
        if alert_key in self.active_alerts:
            return
        
        alert = Alert(
            alert_id=alert_key,
            severity=severity,
            title=title,
            message=message,
            timestamp=time.time(),
            node_id='cluster'
        )
        
        self.alerts.append(alert)
        self.active_alerts[alert_key] = alert
        
        logger.error(f"Cluster alert: {title}")
        self._notify_alert(alert)
    
    def _resolve_alert(self, alert_key: str):
        """Resolve an active alert"""
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.resolved = True
            alert.resolution_time = time.time()
            
            del self.active_alerts[alert_key]
            
            logger.info(f"Alert resolved: {alert.title} on {alert.node_id}")
    
    def _cleanup_resolved_alerts(self):
        """Remove old resolved alerts"""
        cutoff = time.time() - 3600  # Keep for 1 hour
        
        self.alerts = [
            alert for alert in self.alerts
            if not alert.resolved or alert.resolution_time > cutoff
        ]
    
    def _notify_alert(self, alert: Alert):
        """Notify cluster about alert"""
        from .cluster import MessageType
        
        # Broadcast alert to all nodes
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.cluster.node_id:
                self.cluster.send_message(
                    node_id,
                    MessageType.STATE_UPDATE,
                    {
                        'type': 'alert',
                        'alert': asdict(alert)
                    }
                )
    
    def get_node_metrics(self, node_id: str = None) -> Optional[NodeMetrics]:
        """Get metrics for specific node"""
        with self.lock:
            if node_id:
                return self.current_metrics.get(node_id)
            return self.current_metrics.get(self.cluster.node_id)
    
    def get_cluster_metrics(self) -> Dict:
        """Get aggregated cluster metrics"""
        with self.lock:
            return self.cluster_metrics.copy()
    
    def get_metrics_history(self, node_id: str = None, 
                           metric: str = None) -> List:
        """Get historical metrics"""
        with self.lock:
            if node_id and node_id in self.metrics_history:
                history = list(self.metrics_history[node_id])
                
                if metric:
                    # Extract specific metric
                    return [
                        {
                            'timestamp': m.timestamp,
                            'value': getattr(m, metric, None)
                        }
                        for m in history
                    ]
                
                return [asdict(m) for m in history]
            
            return []
    
    def get_active_alerts(self) -> List[Alert]:
        """Get active alerts"""
        with self.lock:
            return list(self.active_alerts.values())
    
    def get_all_alerts(self, resolved: bool = None) -> List[Alert]:
        """Get all alerts"""
        with self.lock:
            if resolved is None:
                return self.alerts.copy()
            return [a for a in self.alerts if a.resolved == resolved]
    
    def add_custom_metric(self, name: str, value: float, 
                         type: MetricType = MetricType.GAUGE,
                         labels: Dict[str, str] = None):
        """Add custom metric"""
        metric = Metric(
            name=name,
            type=type,
            value=value,
            timestamp=time.time(),
            node_id=self.cluster.node_id,
            labels=labels or {}
        )
        
        with self.lock:
            # Add to current node's custom metrics
            if self.cluster.node_id in self.current_metrics:
                self.current_metrics[self.cluster.node_id].custom[name] = value
    
    def add_alert_rule(self, rule: Dict):
        """Add custom alert rule"""
        with self.lock:
            self.alert_rules.append(rule)
    
    def get_performance_report(self) -> Dict:
        """Generate performance report"""
        with self.lock:
            report = {
                'timestamp': time.time(),
                'cluster_health': self._calculate_health_score(),
                'nodes': {}
            }
            
            for node_id, metrics in self.current_metrics.items():
                node_report = {
                    'status': 'healthy',  # Will be updated based on alerts
                    'cpu_usage': metrics.cpu_usage,
                    'memory_usage': metrics.memory_usage,
                    'disk_usage': metrics.disk_usage,
                    'process_count': metrics.process_count,
                    'uptime': time.time() - metrics.timestamp,
                    'role': 'leader' if metrics.is_leader else 'follower'
                }
                
                # Check for alerts on this node
                node_alerts = [
                    a for a in self.active_alerts.values()
                    if a.node_id == node_id
                ]
                
                if node_alerts:
                    # Set status based on highest severity
                    severities = [a.severity for a in node_alerts]
                    if AlertSeverity.CRITICAL in severities:
                        node_report['status'] = 'critical'
                    elif AlertSeverity.ERROR in severities:
                        node_report['status'] = 'error'
                    elif AlertSeverity.WARNING in severities:
                        node_report['status'] = 'warning'
                    
                    node_report['alerts'] = len(node_alerts)
                
                # Add trends if available
                if node_id in self.performance_data:
                    node_report['trends'] = self.performance_data[node_id]
                
                report['nodes'][node_id] = node_report
            
            # Add cluster summary
            if self.cluster_metrics:
                report['summary'] = {
                    'total_nodes': self.cluster_metrics['node_count'],
                    'avg_cpu': self.cluster_metrics['avg_cpu'],
                    'total_memory_gb': self.cluster_metrics['total_memory'] / (1024**3),
                    'used_memory_gb': self.cluster_metrics['used_memory'] / (1024**3),
                    'total_disk_gb': self.cluster_metrics['total_disk'] / (1024**3),
                    'used_disk_gb': self.cluster_metrics['used_disk'] / (1024**3),
                    'total_processes': self.cluster_metrics['total_processes'],
                    'active_alerts': len(self.active_alerts)
                }
            
            return report
    
    def _calculate_health_score(self) -> float:
        """Calculate overall cluster health score (0-100)"""
        if not self.cluster_metrics:
            return 0.0
        
        score = 100.0
        
        # Deduct for resource usage
        cpu_penalty = max(0, self.cluster_metrics.get('avg_cpu', 0) - 50) * 0.5
        mem_penalty = max(0, self.cluster_metrics.get('memory_usage', 0) - 70) * 0.5
        disk_penalty = max(0, self.cluster_metrics.get('disk_usage', 0) - 80) * 0.3
        
        score -= cpu_penalty + mem_penalty + disk_penalty
        
        # Deduct for alerts
        for alert in self.active_alerts.values():
            if alert.severity == AlertSeverity.CRITICAL:
                score -= 20
            elif alert.severity == AlertSeverity.ERROR:
                score -= 10
            elif alert.severity == AlertSeverity.WARNING:
                score -= 5
        
        # Deduct for missing nodes
        expected_nodes = len(self.cluster.nodes)
        active_nodes = len(self.current_metrics)
        if active_nodes < expected_nodes:
            score -= (expected_nodes - active_nodes) * 10
        
        return max(0.0, min(100.0, score))

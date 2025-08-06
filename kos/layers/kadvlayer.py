"""
KADVLayer - Advanced System Layer
Provides monitoring, security, and advanced features
"""

import time
import threading
import hashlib
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from ..core.errors import LayerError

@dataclass
class SecurityEvent:
    """Security event log entry"""
    timestamp: float
    event_type: str
    description: str
    severity: str  # info, warning, critical
    user: str = "system"

@dataclass
class PerformanceMetric:
    """Performance metric data point"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    disk_io_read: float
    disk_io_write: float
    network_in: float
    network_out: float

class KADVLayer:
    """
    Advanced System Layer
    Provides monitoring, security, and advanced OS features
    """
    
    def __init__(self, klayer=None, vfs=None):
        self.klayer = klayer
        self.vfs = vfs
        
        # Security
        self.security_events = deque(maxlen=1000)
        self.firewall_rules = []
        self.access_control = {}
        
        # Monitoring
        self.performance_metrics = deque(maxlen=100)
        self.alerts = []
        self.monitoring_enabled = True
        
        # Container/Virtualization (simplified)
        self.containers = {}
        self.next_container_id = 1
        
        # Advanced networking
        self.port_forwarding = {}
        self.vpn_connections = {}
        
        # Thread management
        self._monitor_thread = None
        self._running = False
        
        self._init_security()
        self.start_monitoring()
    
    def _init_security(self):
        """Initialize security subsystem"""
        # Add default firewall rules
        self.firewall_rules = [
            {'action': 'allow', 'port': 22, 'protocol': 'tcp', 'source': 'any'},
            {'action': 'allow', 'port': 80, 'protocol': 'tcp', 'source': 'any'},
            {'action': 'allow', 'port': 443, 'protocol': 'tcp', 'source': 'any'},
            {'action': 'deny', 'port': 'all', 'protocol': 'all', 'source': 'any'}
        ]
        
        # Log security initialization
        self.log_security_event('info', 'Security subsystem initialized')
    
    # Security Features
    def log_security_event(self, severity: str, description: str, user: str = "system"):
        """Log a security event"""
        event = SecurityEvent(
            timestamp=time.time(),
            event_type='security',
            description=description,
            severity=severity,
            user=user
        )
        self.security_events.append(event)
        
        # Write to VFS log if available
        if self.vfs:
            try:
                log_entry = f"[{datetime.now().isoformat()}] [{severity.upper()}] {description}\n"
                with self.vfs.open('/var/log/security.log', 'a') as f:
                    f.write(log_entry.encode())
            except:
                pass
    
    def add_firewall_rule(self, action: str, port: Any, protocol: str = 'tcp', source: str = 'any'):
        """Add a firewall rule"""
        rule = {
            'action': action,
            'port': port,
            'protocol': protocol,
            'source': source
        }
        
        # Insert before the default deny rule
        self.firewall_rules.insert(-1, rule)
        self.log_security_event('info', f'Firewall rule added: {rule}')
        return True
    
    def check_access(self, user: str, resource: str, action: str) -> bool:
        """Check access control"""
        # Simple ACL check
        user_acl = self.access_control.get(user, {})
        resource_perms = user_acl.get(resource, [])
        
        allowed = action in resource_perms or 'all' in resource_perms
        
        if not allowed:
            self.log_security_event('warning', 
                f'Access denied: user={user}, resource={resource}, action={action}')
        
        return allowed
    
    def set_access_control(self, user: str, resource: str, permissions: List[str]):
        """Set access control for user/resource"""
        if user not in self.access_control:
            self.access_control[user] = {}
        
        self.access_control[user][resource] = permissions
        self.log_security_event('info', 
            f'ACL updated: user={user}, resource={resource}, perms={permissions}')
    
    # Monitoring Features
    def start_monitoring(self):
        """Start performance monitoring"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
    
    def _monitor_loop(self):
        """Monitoring thread loop"""
        while self._running:
            if self.monitoring_enabled:
                # Collect metrics (simulated)
                metric = PerformanceMetric(
                    timestamp=time.time(),
                    cpu_percent=10.0 + (time.time() % 10),  # Simulated
                    memory_percent=25.0 + (time.time() % 5),
                    disk_io_read=100.0,
                    disk_io_write=50.0,
                    network_in=1024.0,
                    network_out=512.0
                )
                
                self.performance_metrics.append(metric)
                
                # Check for alerts
                if metric.cpu_percent > 80:
                    self.add_alert('high_cpu', f'CPU usage: {metric.cpu_percent}%')
                if metric.memory_percent > 90:
                    self.add_alert('high_memory', f'Memory usage: {metric.memory_percent}%')
            
            time.sleep(5)  # Monitor every 5 seconds
    
    def get_metrics(self, last_n: int = 10) -> List[PerformanceMetric]:
        """Get recent performance metrics"""
        return list(self.performance_metrics)[-last_n:]
    
    def add_alert(self, alert_type: str, message: str):
        """Add a system alert"""
        alert = {
            'timestamp': time.time(),
            'type': alert_type,
            'message': message
        }
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
    
    def get_alerts(self, unread_only: bool = False) -> List[Dict]:
        """Get system alerts"""
        return self.alerts
    
    # Container Management (simplified)
    def create_container(self, name: str, image: str = "kos-base") -> int:
        """Create a container (simplified)"""
        container_id = self.next_container_id
        self.next_container_id += 1
        
        container = {
            'id': container_id,
            'name': name,
            'image': image,
            'status': 'created',
            'created': time.time(),
            'pid': None
        }
        
        self.containers[container_id] = container
        self.log_security_event('info', f'Container created: {name} (ID: {container_id})')
        
        return container_id
    
    def start_container(self, container_id: int) -> bool:
        """Start a container"""
        if container_id not in self.containers:
            return False
        
        container = self.containers[container_id]
        if container['status'] == 'running':
            return True
        
        # Create process for container if klayer available
        if self.klayer:
            pid = self.klayer.create_process(f"container:{container['name']}")
            container['pid'] = pid
        
        container['status'] = 'running'
        self.log_security_event('info', f"Container started: {container['name']}")
        
        return True
    
    def stop_container(self, container_id: int) -> bool:
        """Stop a container"""
        if container_id not in self.containers:
            return False
        
        container = self.containers[container_id]
        if container['status'] != 'running':
            return True
        
        # Kill container process if exists
        if container['pid'] and self.klayer:
            self.klayer.kill_process(container['pid'])
        
        container['status'] = 'stopped'
        container['pid'] = None
        self.log_security_event('info', f"Container stopped: {container['name']}")
        
        return True
    
    def list_containers(self) -> List[Dict]:
        """List all containers"""
        return list(self.containers.values())
    
    # Advanced Networking
    def add_port_forward(self, host_port: int, container_port: int, container_id: int):
        """Add port forwarding rule"""
        self.port_forwarding[host_port] = {
            'container_port': container_port,
            'container_id': container_id
        }
        self.log_security_event('info', 
            f'Port forward added: {host_port} -> container {container_id}:{container_port}')
    
    def establish_vpn(self, name: str, server: str, credentials: Dict):
        """Establish VPN connection (simulated)"""
        # Don't store actual credentials
        cred_hash = hashlib.sha256(str(credentials).encode()).hexdigest()[:8]
        
        self.vpn_connections[name] = {
            'server': server,
            'status': 'connected',
            'connected_at': time.time(),
            'cred_hash': cred_hash
        }
        
        self.log_security_event('info', f'VPN connection established: {name} to {server}')
        return True
    
    # System Information
    def get_advanced_info(self) -> Dict[str, Any]:
        """Get advanced system information"""
        return {
            'security': {
                'firewall_rules': len(self.firewall_rules),
                'security_events': len(self.security_events),
                'last_event': self.security_events[-1] if self.security_events else None
            },
            'monitoring': {
                'enabled': self.monitoring_enabled,
                'metrics_count': len(self.performance_metrics),
                'alerts_count': len(self.alerts)
            },
            'containers': {
                'total': len(self.containers),
                'running': sum(1 for c in self.containers.values() if c['status'] == 'running')
            },
            'networking': {
                'port_forwards': len(self.port_forwarding),
                'vpn_connections': len(self.vpn_connections)
            }
        }
    
    def shutdown(self):
        """Shutdown the advanced layer"""
        # Stop monitoring
        self.stop_monitoring()
        
        # Stop all containers
        for container_id in list(self.containers.keys()):
            self.stop_container(container_id)
        
        # Log shutdown
        self.log_security_event('info', 'KADVLayer shutdown initiated')
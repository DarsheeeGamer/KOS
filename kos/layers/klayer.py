"""
KLayer - Core OS Layer
Provides fundamental OS services
"""

import os
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from ..core.errors import LayerError

@dataclass
class Process:
    """Simple process representation"""
    pid: int
    name: str
    status: str = 'running'
    created: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    memory_mb: float = 0.0

@dataclass
class Service:
    """System service"""
    name: str
    status: str = 'stopped'
    enabled: bool = False
    pid: Optional[int] = None

class KLayer:
    """
    Core OS Layer - Provides basic OS functionality
    Actually simple and working, not 87 manager classes
    """
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.processes: Dict[int, Process] = {}
        self.services: Dict[str, Service] = {}
        self.next_pid = 1000
        self.boot_time = time.time()
        self.hostname = "kos"
        self._lock = threading.Lock()
        
        # Initialize core services
        self._init_core_services()
    
    def _init_core_services(self):
        """Initialize core system services"""
        core_services = [
            Service("vfs", "running", True, 1),
            Service("network", "stopped", False),
            Service("logging", "running", True, 2),
            Service("scheduler", "running", True, 3)
        ]
        
        for service in core_services:
            self.services[service.name] = service
            if service.status == "running":
                self.create_process(f"systemd:{service.name}", service.pid)
    
    # Process Management
    def create_process(self, name: str, pid: Optional[int] = None) -> int:
        """Create a new process"""
        with self._lock:
            if pid is None:
                pid = self.next_pid
                self.next_pid += 1
            
            process = Process(pid, name)
            self.processes[pid] = process
            return pid
    
    def kill_process(self, pid: int) -> bool:
        """Kill a process"""
        with self._lock:
            if pid in self.processes:
                self.processes[pid].status = 'terminated'
                del self.processes[pid]
                return True
            return False
    
    def list_processes(self) -> List[Process]:
        """List all processes"""
        return list(self.processes.values())
    
    def get_process(self, pid: int) -> Optional[Process]:
        """Get process by PID"""
        return self.processes.get(pid)
    
    # Service Management
    def start_service(self, name: str) -> bool:
        """Start a service"""
        if name not in self.services:
            return False
        
        service = self.services[name]
        if service.status == "running":
            return True
        
        # Create process for service
        pid = self.create_process(f"service:{name}")
        service.pid = pid
        service.status = "running"
        return True
    
    def stop_service(self, name: str) -> bool:
        """Stop a service"""
        if name not in self.services:
            return False
        
        service = self.services[name]
        if service.status == "stopped":
            return True
        
        if service.pid:
            self.kill_process(service.pid)
        
        service.pid = None
        service.status = "stopped"
        return True
    
    def list_services(self) -> List[Service]:
        """List all services"""
        return list(self.services.values())
    
    # System Information
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        uptime = time.time() - self.boot_time
        
        return {
            'hostname': self.hostname,
            'kernel': 'KOS-2.0',
            'architecture': 'x86_64',
            'uptime_seconds': uptime,
            'uptime_str': self._format_uptime(uptime),
            'process_count': len(self.processes),
            'service_count': len(self.services),
            'load_average': [0.1, 0.2, 0.15],  # Simulated
            'memory': {
                'total_mb': 1024,
                'used_mb': 256,
                'free_mb': 768,
                'percent': 25.0
            },
            'disk': {
                'total_mb': 10240,
                'used_mb': 2048,
                'free_mb': 8192,
                'percent': 20.0
            }
        }
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable form"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        
        return ", ".join(parts) if parts else "Less than a minute"
    
    # User Management (simplified)
    def get_current_user(self) -> str:
        """Get current user"""
        return "user"
    
    def get_home_directory(self) -> str:
        """Get user home directory"""
        return f"/home/{self.get_current_user()}"
    
    # Network (simplified)
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        return {
            'interfaces': [
                {
                    'name': 'lo',
                    'ip': '127.0.0.1',
                    'status': 'up'
                },
                {
                    'name': 'eth0',
                    'ip': '192.168.1.100',
                    'status': 'up'
                }
            ],
            'hostname': self.hostname,
            'dns': ['8.8.8.8', '8.8.4.4']
        }
    
    def set_hostname(self, hostname: str):
        """Set system hostname"""
        self.hostname = hostname
        
        # Update /etc/hostname in VFS if available
        if self.vfs:
            try:
                with self.vfs.open('/etc/hostname', 'w') as f:
                    f.write(hostname.encode() + b'\n')
            except:
                pass
    
    def shutdown(self):
        """Shutdown the layer"""
        # Stop all services
        for service_name in list(self.services.keys()):
            self.stop_service(service_name)
        
        # Kill all processes
        for pid in list(self.processes.keys()):
            self.kill_process(pid)
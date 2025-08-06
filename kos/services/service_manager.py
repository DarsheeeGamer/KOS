"""
Service management system for KOS (systemd-like)
"""

import time
import threading
import json
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

class ServiceState(Enum):
    """Service states"""
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAILED = "failed"
    RELOADING = "reloading"

class ServiceType(Enum):
    """Service types"""
    SIMPLE = "simple"
    FORKING = "forking"
    ONESHOT = "oneshot"
    NOTIFY = "notify"
    IDLE = "idle"

@dataclass
class ServiceUnit:
    """Service unit definition"""
    name: str
    description: str = ""
    type: ServiceType = ServiceType.SIMPLE
    exec_start: str = ""
    exec_stop: Optional[str] = None
    exec_reload: Optional[str] = None
    restart: str = "on-failure"
    restart_sec: int = 10
    timeout_start_sec: int = 90
    timeout_stop_sec: int = 90
    dependencies: List[str] = field(default_factory=list)
    wants: List[str] = field(default_factory=list)
    before: List[str] = field(default_factory=list)
    after: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    working_directory: str = "/"
    user: str = "root"
    group: str = "root"
    
    # Runtime state
    state: ServiceState = ServiceState.INACTIVE
    pid: Optional[int] = None
    start_time: Optional[float] = None
    exit_code: Optional[int] = None
    thread: Optional[threading.Thread] = None

class SystemdManager:
    """Systemd-like service manager"""
    
    def __init__(self, vfs=None, executor=None):
        self.vfs = vfs
        self.executor = executor
        self.units: Dict[str, ServiceUnit] = {}
        self.unit_dir = "/etc/systemd/system"
        self.runtime_dir = "/run/systemd"
        
        self._init_default_services()
        self._load_units()
    
    def _init_default_services(self):
        """Initialize default system services"""
        # Network service
        self.units["network.service"] = ServiceUnit(
            name="network.service",
            description="Network Service",
            type=ServiceType.ONESHOT,
            exec_start="/usr/bin/network-init",
            after=["basic.target"]
        )
        
        # SSH service
        self.units["sshd.service"] = ServiceUnit(
            name="sshd.service",
            description="OpenSSH server daemon",
            type=ServiceType.NOTIFY,
            exec_start="/usr/sbin/sshd -D",
            exec_reload="/bin/kill -HUP $MAINPID",
            restart="on-failure",
            after=["network.target"]
        )
        
        # Cron service
        self.units["cron.service"] = ServiceUnit(
            name="cron.service",
            description="Regular background program processing daemon",
            type=ServiceType.SIMPLE,
            exec_start="/usr/sbin/cron -f",
            restart="on-failure",
            after=["basic.target"]
        )
        
        # System logger
        self.units["rsyslog.service"] = ServiceUnit(
            name="rsyslog.service",
            description="System Logging Service",
            type=ServiceType.NOTIFY,
            exec_start="/usr/sbin/rsyslogd -n",
            restart="on-failure",
            after=["basic.target"]
        )
        
        # HTTP server
        self.units["httpd.service"] = ServiceUnit(
            name="httpd.service",
            description="The Apache HTTP Server",
            type=ServiceType.FORKING,
            exec_start="/usr/sbin/httpd",
            exec_stop="/usr/sbin/httpd -k stop",
            exec_reload="/usr/sbin/httpd -k graceful",
            restart="on-failure",
            after=["network.target"]
        )
        
        # Database
        self.units["mysql.service"] = ServiceUnit(
            name="mysql.service",
            description="MySQL Database Server",
            type=ServiceType.SIMPLE,
            exec_start="/usr/sbin/mysqld",
            restart="on-failure",
            after=["network.target"]
        )
    
    def _load_units(self):
        """Load service units from files"""
        if not self.vfs:
            return
        
        # Ensure directories exist
        for dir_path in [self.unit_dir, self.runtime_dir]:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path)
                except:
                    pass
        
        # Load unit files
        if self.vfs.exists(self.unit_dir):
            try:
                for filename in self.vfs.listdir(self.unit_dir):
                    if filename.endswith('.service'):
                        self._load_unit_file(f"{self.unit_dir}/{filename}")
            except:
                pass
    
    def _load_unit_file(self, filepath: str):
        """Load a unit file"""
        try:
            with self.vfs.open(filepath, 'r') as f:
                content = f.read().decode()
            
            # Parse unit file (simplified INI format)
            unit_data = {}
            current_section = None
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_section = line[1:-1]
                    unit_data[current_section] = {}
                elif '=' in line and current_section:
                    key, value = line.split('=', 1)
                    unit_data[current_section][key.strip()] = value.strip()
            
            # Create unit from data
            if 'Service' in unit_data:
                service = unit_data['Service']
                name = filepath.split('/')[-1]
                
                unit = ServiceUnit(
                    name=name,
                    description=unit_data.get('Unit', {}).get('Description', ''),
                    exec_start=service.get('ExecStart', ''),
                    exec_stop=service.get('ExecStop'),
                    exec_reload=service.get('ExecReload'),
                    restart=service.get('Restart', 'on-failure'),
                    user=service.get('User', 'root')
                )
                
                self.units[name] = unit
        
        except Exception:
            pass
    
    def start_service(self, service_name: str) -> bool:
        """Start a service"""
        if service_name not in self.units:
            return False
        
        unit = self.units[service_name]
        
        if unit.state == ServiceState.ACTIVE:
            return True
        
        # Check dependencies
        for dep in unit.dependencies:
            if dep in self.units and self.units[dep].state != ServiceState.ACTIVE:
                self.start_service(dep)
        
        # Start service
        unit.state = ServiceState.ACTIVATING
        unit.start_time = time.time()
        
        # Run in thread (simulated)
        def run_service():
            try:
                # In real implementation, would execute unit.exec_start
                unit.state = ServiceState.ACTIVE
                unit.pid = 1000 + len([u for u in self.units.values() if u.state == ServiceState.ACTIVE])
                
                # Simulate service running
                while unit.state == ServiceState.ACTIVE:
                    time.sleep(1)
            
            except Exception:
                unit.state = ServiceState.FAILED
                unit.exit_code = 1
        
        thread = threading.Thread(target=run_service, daemon=True)
        thread.start()
        unit.thread = thread
        
        return True
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a service"""
        if service_name not in self.units:
            return False
        
        unit = self.units[service_name]
        
        if unit.state != ServiceState.ACTIVE:
            return True
        
        unit.state = ServiceState.DEACTIVATING
        
        # In real implementation, would execute unit.exec_stop
        time.sleep(0.1)
        
        unit.state = ServiceState.INACTIVE
        unit.pid = None
        unit.exit_code = 0
        
        return True
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        self.stop_service(service_name)
        time.sleep(0.1)
        return self.start_service(service_name)
    
    def reload_service(self, service_name: str) -> bool:
        """Reload service configuration"""
        if service_name not in self.units:
            return False
        
        unit = self.units[service_name]
        
        if unit.state != ServiceState.ACTIVE:
            return False
        
        unit.state = ServiceState.RELOADING
        
        # In real implementation, would execute unit.exec_reload
        time.sleep(0.1)
        
        unit.state = ServiceState.ACTIVE
        return True
    
    def enable_service(self, service_name: str) -> bool:
        """Enable service to start at boot"""
        if service_name not in self.units:
            return False
        
        # Create symlink in wants directory (simplified)
        if self.vfs:
            wants_dir = f"{self.unit_dir}/multi-user.target.wants"
            if not self.vfs.exists(wants_dir):
                self.vfs.mkdir(wants_dir)
            
            # Create enable marker
            try:
                with self.vfs.open(f"{wants_dir}/{service_name}", 'w') as f:
                    f.write(b"enabled")
                return True
            except:
                pass
        
        return False
    
    def disable_service(self, service_name: str) -> bool:
        """Disable service from starting at boot"""
        if self.vfs:
            wants_file = f"{self.unit_dir}/multi-user.target.wants/{service_name}"
            if self.vfs.exists(wants_file):
                self.vfs.remove(wants_file)
                return True
        return False
    
    def get_service_status(self, service_name: str) -> Optional[ServiceUnit]:
        """Get service status"""
        return self.units.get(service_name)
    
    def list_services(self) -> List[ServiceUnit]:
        """List all services"""
        return list(self.units.values())
    
    def daemon_reload(self):
        """Reload systemd manager configuration"""
        self._load_units()
    
    def get_failed_services(self) -> List[ServiceUnit]:
        """Get list of failed services"""
        return [u for u in self.units.values() if u.state == ServiceState.FAILED]
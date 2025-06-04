"""
KOS SystemD-Like Service Manager
===============================

Service management system similar to Ubuntu's systemd, providing:
- Service lifecycle management (start, stop, restart, reload)
- Dependency resolution and ordering
- Service monitoring and health checking
- Socket activation and timers
- Unit file parsing and management
- Journal logging
- Target states (runlevels)
- User and system services
- Service isolation and sandboxing
"""

import os
import sys
import time
import threading
import logging
import subprocess
import signal
import json
import configparser
import glob
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import weakref
from collections import defaultdict, deque
import psutil
import shlex

logger = logging.getLogger('KOS.system.servicemanager')

class ServiceState(Enum):
    """Service states"""
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAILED = "failed"
    RELOADING = "reloading"
    MAINTENANCE = "maintenance"

class ServiceType(Enum):
    """Service types"""
    SIMPLE = "simple"
    EXEC = "exec"
    FORKING = "forking"
    ONESHOT = "oneshot"
    DBUS = "dbus"
    NOTIFY = "notify"
    IDLE = "idle"

class RestartPolicy(Enum):
    """Restart policies"""
    NO = "no"
    ON_SUCCESS = "on-success"
    ON_FAILURE = "on-failure"
    ON_ABNORMAL = "on-abnormal"
    ON_WATCHDOG = "on-watchdog"
    ON_ABORT = "on-abort"
    ALWAYS = "always"

class UnitType(Enum):
    """Unit types"""
    SERVICE = "service"
    SOCKET = "socket"
    TARGET = "target"
    TIMER = "timer"
    MOUNT = "mount"
    DEVICE = "device"
    SCOPE = "scope"
    SLICE = "slice"

@dataclass
class ServiceUnit:
    """Service unit configuration"""
    name: str
    description: str = ""
    service_type: ServiceType = ServiceType.SIMPLE
    exec_start: str = ""
    exec_stop: str = ""
    exec_reload: str = ""
    working_directory: str = "/"
    user: str = "root"
    group: str = "root"
    environment: Dict[str, str] = field(default_factory=dict)
    environment_files: List[str] = field(default_factory=list)
    
    # Dependencies
    wants: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    after: List[str] = field(default_factory=list)
    before: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    
    # Restart configuration
    restart: RestartPolicy = RestartPolicy.NO
    restart_sec: int = 100  # milliseconds
    restart_max_delay_sec: int = 5
    start_limit_interval_sec: int = 10
    start_limit_burst: int = 5
    
    # Timeouts
    timeout_start_sec: int = 90
    timeout_stop_sec: int = 90
    timeout_abort_sec: int = 90
    
    # Resource limits
    limit_cpu: Optional[float] = None
    limit_memory: Optional[int] = None
    limit_nofile: Optional[int] = None
    
    # Security
    private_tmp: bool = False
    private_network: bool = False
    no_new_privileges: bool = False
    protect_system: str = "no"  # no, strict, full
    protect_home: str = "no"    # no, read-only, tmpfs
    
    # Installation
    wanted_by: List[str] = field(default_factory=list)
    required_by: List[str] = field(default_factory=list)
    also: List[str] = field(default_factory=list)
    
    # Runtime state
    state: ServiceState = ServiceState.INACTIVE
    main_pid: Optional[int] = None
    process: Optional[subprocess.Popen] = None
    start_time: Optional[float] = None
    active_enter_timestamp: Optional[float] = None
    active_exit_timestamp: Optional[float] = None
    restart_count: int = 0
    failure_count: int = 0
    last_failure_time: Optional[float] = None

@dataclass 
class SocketUnit:
    """Socket unit for socket activation"""
    name: str
    description: str = ""
    listen_stream: List[str] = field(default_factory=list)
    listen_datagram: List[str] = field(default_factory=list)
    listen_sequential_packet: List[str] = field(default_factory=list)
    listen_fifo: List[str] = field(default_factory=list)
    socket_user: str = "root"
    socket_group: str = "root"
    socket_mode: str = "0666"
    accept: bool = False
    max_connections: int = 64
    keep_alive: bool = False
    priority: int = 0
    receive_buffer: Optional[int] = None
    send_buffer: Optional[int] = None
    
    # Service integration
    service: str = ""  # Associated service
    
    # Runtime state
    sockets: List[Any] = field(default_factory=list)
    active: bool = False

@dataclass
class TimerUnit:
    """Timer unit for scheduled services"""
    name: str
    description: str = ""
    on_calendar: Optional[str] = None  # Calendar specification
    on_boot_sec: Optional[int] = None
    on_startup_sec: Optional[int] = None
    on_unit_active_sec: Optional[int] = None
    on_unit_inactive_sec: Optional[int] = None
    accuracy_sec: int = 60
    randomized_delay_sec: int = 0
    persistent: bool = False
    wake_system: bool = False
    remain_after_elapse: bool = True
    
    # Service integration
    unit: str = ""  # Service to trigger
    
    # Runtime state
    next_elapse: Optional[float] = None
    last_trigger: Optional[float] = None
    active: bool = False

class DependencyResolver:
    """Resolves service dependencies and determines start order"""
    
    def __init__(self, units: Dict[str, ServiceUnit]):
        self.units = units
        self.dependency_graph = defaultdict(set)
        self.reverse_graph = defaultdict(set)
        self._build_graphs()
    
    def _build_graphs(self):
        """Build dependency graphs"""
        for unit_name, unit in self.units.items():
            # Process "after" dependencies
            for dep in unit.after:
                self.dependency_graph[unit_name].add(dep)
                self.reverse_graph[dep].add(unit_name)
            
            # Process "requires" as strong dependencies
            for dep in unit.requires:
                self.dependency_graph[unit_name].add(dep)
                self.reverse_graph[dep].add(unit_name)
    
    def get_start_order(self, target_units: List[str]) -> List[str]:
        """Get the order in which units should be started"""
        visited = set()
        temp_visited = set()
        result = deque()
        
        def visit(unit_name):
            if unit_name in temp_visited:
                raise RuntimeError(f"Circular dependency detected involving {unit_name}")
            if unit_name in visited:
                return
            
            temp_visited.add(unit_name)
            
            # Visit all dependencies first
            for dep in self.dependency_graph.get(unit_name, set()):
                if dep in self.units:  # Only if dependency exists
                    visit(dep)
            
            temp_visited.remove(unit_name)
            visited.add(unit_name)
            result.appendleft(unit_name)
        
        # Visit all target units
        for unit in target_units:
            if unit in self.units:
                visit(unit)
        
        return list(result)
    
    def get_stop_order(self, target_units: List[str]) -> List[str]:
        """Get the order in which units should be stopped (reverse of start order)"""
        start_order = self.get_start_order(target_units)
        return start_order[::-1]
    
    def get_dependents(self, unit_name: str) -> Set[str]:
        """Get all units that depend on this unit"""
        return self.reverse_graph.get(unit_name, set())

class ServiceManager:
    """Main service management system"""
    
    def __init__(self, system_unit_path: str = "/etc/kos/system", 
                 user_unit_path: str = None):
        self.system_unit_path = Path(system_unit_path)
        self.user_unit_path = Path(user_unit_path or Path.home() / ".config/kos/user")
        
        # Create directories
        self.system_unit_path.mkdir(parents=True, exist_ok=True)
        self.user_unit_path.mkdir(parents=True, exist_ok=True)
        
        # Unit storage
        self.service_units: Dict[str, ServiceUnit] = {}
        self.socket_units: Dict[str, SocketUnit] = {}
        self.timer_units: Dict[str, TimerUnit] = {}
        
        # Runtime state
        self.dependency_resolver = None
        self.active_services: Dict[str, ServiceUnit] = {}
        self.failed_services: Dict[str, ServiceUnit] = {}
        self.service_processes: Dict[str, subprocess.Popen] = {}
        
        # Monitoring
        self.monitor_thread = None
        self.monitor_running = False
        self.event_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        
        # Journal logging
        self.journal_path = Path("/var/log/kos")
        self.journal_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing units
        self.reload_units()
        
        # Start monitoring
        self.start_monitoring()
    
    def reload_units(self):
        """Reload all unit files from disk"""
        self.service_units.clear()
        self.socket_units.clear()
        self.timer_units.clear()
        
        # Load system units
        self._load_units_from_path(self.system_unit_path)
        
        # Load user units
        self._load_units_from_path(self.user_unit_path)
        
        # Rebuild dependency resolver
        self.dependency_resolver = DependencyResolver(self.service_units)
        
        logger.info(f"Loaded {len(self.service_units)} service units, "
                   f"{len(self.socket_units)} socket units, "
                   f"{len(self.timer_units)} timer units")
    
    def _load_units_from_path(self, path: Path):
        """Load unit files from a directory"""
        if not path.exists():
            return
        
        # Load service files
        for service_file in path.glob("*.service"):
            try:
                unit = self._parse_service_unit(service_file)
                self.service_units[unit.name] = unit
            except Exception as e:
                logger.error(f"Failed to load service unit {service_file}: {e}")
        
        # Load socket files
        for socket_file in path.glob("*.socket"):
            try:
                unit = self._parse_socket_unit(socket_file)
                self.socket_units[unit.name] = unit
            except Exception as e:
                logger.error(f"Failed to load socket unit {socket_file}: {e}")
        
        # Load timer files
        for timer_file in path.glob("*.timer"):
            try:
                unit = self._parse_timer_unit(timer_file)
                self.timer_units[unit.name] = unit
            except Exception as e:
                logger.error(f"Failed to load timer unit {timer_file}: {e}")
    
    def _parse_service_unit(self, file_path: Path) -> ServiceUnit:
        """Parse a service unit file"""
        config = configparser.ConfigParser()
        config.read(file_path)
        
        name = file_path.stem
        unit = ServiceUnit(name=name)
        
        # Parse [Unit] section
        if 'Unit' in config:
            unit_section = config['Unit']
            unit.description = unit_section.get('Description', '')
            unit.wants = self._parse_list(unit_section.get('Wants', ''))
            unit.requires = self._parse_list(unit_section.get('Requires', ''))
            unit.after = self._parse_list(unit_section.get('After', ''))
            unit.before = self._parse_list(unit_section.get('Before', ''))
            unit.conflicts = self._parse_list(unit_section.get('Conflicts', ''))
        
        # Parse [Service] section
        if 'Service' in config:
            service_section = config['Service']
            unit.service_type = ServiceType(service_section.get('Type', 'simple'))
            unit.exec_start = service_section.get('ExecStart', '')
            unit.exec_stop = service_section.get('ExecStop', '')
            unit.exec_reload = service_section.get('ExecReload', '')
            unit.working_directory = service_section.get('WorkingDirectory', '/')
            unit.user = service_section.get('User', 'root')
            unit.group = service_section.get('Group', 'root')
            
            # Parse environment
            env_vars = service_section.get('Environment', '')
            for env_var in env_vars.split():
                if '=' in env_var:
                    key, value = env_var.split('=', 1)
                    unit.environment[key] = value
            
            # Parse restart policy
            unit.restart = RestartPolicy(service_section.get('Restart', 'no'))
            unit.restart_sec = int(service_section.get('RestartSec', '100'))
            
            # Parse timeouts
            unit.timeout_start_sec = int(service_section.get('TimeoutStartSec', '90'))
            unit.timeout_stop_sec = int(service_section.get('TimeoutStopSec', '90'))
            
            # Parse security settings
            unit.private_tmp = service_section.getboolean('PrivateTmp', False)
            unit.private_network = service_section.getboolean('PrivateNetwork', False)
            unit.no_new_privileges = service_section.getboolean('NoNewPrivileges', False)
            unit.protect_system = service_section.get('ProtectSystem', 'no')
            unit.protect_home = service_section.get('ProtectHome', 'no')
        
        # Parse [Install] section
        if 'Install' in config:
            install_section = config['Install']
            unit.wanted_by = self._parse_list(install_section.get('WantedBy', ''))
            unit.required_by = self._parse_list(install_section.get('RequiredBy', ''))
            unit.also = self._parse_list(install_section.get('Also', ''))
        
        return unit
    
    def _parse_socket_unit(self, file_path: Path) -> SocketUnit:
        """Parse a socket unit file"""
        config = configparser.ConfigParser()
        config.read(file_path)
        
        name = file_path.stem
        unit = SocketUnit(name=name)
        
        # Parse [Unit] section
        if 'Unit' in config:
            unit_section = config['Unit']
            unit.description = unit_section.get('Description', '')
        
        # Parse [Socket] section
        if 'Socket' in config:
            socket_section = config['Socket']
            unit.listen_stream = self._parse_list(socket_section.get('ListenStream', ''))
            unit.listen_datagram = self._parse_list(socket_section.get('ListenDatagram', ''))
            unit.socket_user = socket_section.get('SocketUser', 'root')
            unit.socket_group = socket_section.get('SocketGroup', 'root')
            unit.socket_mode = socket_section.get('SocketMode', '0666')
            unit.accept = socket_section.getboolean('Accept', False)
            unit.max_connections = int(socket_section.get('MaxConnections', '64'))
        
        # Parse [Install] section
        if 'Install' in config:
            install_section = config['Install']
            unit.service = install_section.get('Service', f"{name}.service")
        
        return unit
    
    def _parse_timer_unit(self, file_path: Path) -> TimerUnit:
        """Parse a timer unit file"""
        config = configparser.ConfigParser()
        config.read(file_path)
        
        name = file_path.stem
        unit = TimerUnit(name=name)
        
        # Parse [Unit] section
        if 'Unit' in config:
            unit_section = config['Unit']
            unit.description = unit_section.get('Description', '')
        
        # Parse [Timer] section
        if 'Timer' in config:
            timer_section = config['Timer']
            unit.on_calendar = timer_section.get('OnCalendar')
            unit.on_boot_sec = self._parse_time(timer_section.get('OnBootSec'))
            unit.on_startup_sec = self._parse_time(timer_section.get('OnStartupSec'))
            unit.accuracy_sec = int(timer_section.get('AccuracySec', '60'))
            unit.persistent = timer_section.getboolean('Persistent', False)
            unit.unit = timer_section.get('Unit', f"{name}.service")
        
        return unit
    
    def _parse_list(self, value: str) -> List[str]:
        """Parse space-separated list from unit file"""
        return [item.strip() for item in value.split() if item.strip()]
    
    def _parse_time(self, value: Optional[str]) -> Optional[int]:
        """Parse time specification (e.g., '5min', '30s') to seconds"""
        if not value:
            return None
        
        value = value.strip().lower()
        if value.endswith('s'):
            return int(value[:-1])
        elif value.endswith('min'):
            return int(value[:-3]) * 60
        elif value.endswith('h'):
            return int(value[:-1]) * 3600
        else:
            return int(value)
    
    def start_service(self, service_name: str) -> bool:
        """Start a service and its dependencies"""
        if service_name not in self.service_units:
            logger.error(f"Service {service_name} not found")
            return False
        
        unit = self.service_units[service_name]
        
        if unit.state == ServiceState.ACTIVE:
            logger.info(f"Service {service_name} is already active")
            return True
        
        try:
            # Start dependencies first
            start_order = self.dependency_resolver.get_start_order([service_name])
            
            for dep_service in start_order:
                if dep_service == service_name:
                    continue
                
                if dep_service in self.service_units:
                    dep_unit = self.service_units[dep_service]
                    if dep_unit.state != ServiceState.ACTIVE:
                        if not self._start_single_service(dep_unit):
                            logger.error(f"Failed to start dependency {dep_service}")
                            return False
            
            # Start the target service
            return self._start_single_service(unit)
            
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            unit.state = ServiceState.FAILED
            unit.failure_count += 1
            unit.last_failure_time = time.time()
            return False
    
    def _start_single_service(self, unit: ServiceUnit) -> bool:
        """Start a single service"""
        if not unit.exec_start:
            logger.error(f"No ExecStart defined for service {unit.name}")
            return False
        
        logger.info(f"Starting service {unit.name}")
        unit.state = ServiceState.ACTIVATING
        unit.start_time = time.time()
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(unit.environment)
            
            # Load environment files
            for env_file in unit.environment_files:
                if os.path.exists(env_file):
                    with open(env_file, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and '=' in line and not line.startswith('#'):
                                key, value = line.split('=', 1)
                                env[key] = value
            
            # Parse command
            command = shlex.split(unit.exec_start)
            
            # Start process
            process = subprocess.Popen(
                command,
                cwd=unit.working_directory,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=self._setup_process_security(unit)
            )
            
            unit.process = process
            unit.main_pid = process.pid
            self.service_processes[unit.name] = process
            
            # Handle different service types
            if unit.service_type == ServiceType.SIMPLE:
                # For simple services, assume started immediately
                unit.state = ServiceState.ACTIVE
                unit.active_enter_timestamp = time.time()
                self.active_services[unit.name] = unit
                
            elif unit.service_type == ServiceType.FORKING:
                # Wait for process to fork and exit
                try:
                    process.wait(timeout=unit.timeout_start_sec)
                    if process.returncode == 0:
                        unit.state = ServiceState.ACTIVE
                        unit.active_enter_timestamp = time.time()
                        self.active_services[unit.name] = unit
                    else:
                        raise subprocess.TimeoutExpired(command, unit.timeout_start_sec)
                except subprocess.TimeoutExpired:
                    logger.error(f"Service {unit.name} failed to start within timeout")
                    self._cleanup_failed_service(unit)
                    return False
            
            elif unit.service_type == ServiceType.ONESHOT:
                # Wait for process to complete
                try:
                    process.wait(timeout=unit.timeout_start_sec)
                    if process.returncode == 0:
                        unit.state = ServiceState.ACTIVE
                        unit.active_enter_timestamp = time.time()
                        self.active_services[unit.name] = unit
                    else:
                        raise subprocess.CalledProcessError(process.returncode, command)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    logger.error(f"Oneshot service {unit.name} failed")
                    self._cleanup_failed_service(unit)
                    return False
            
            self._emit_event('service_started', unit.name)
            logger.info(f"Service {unit.name} started successfully (PID: {unit.main_pid})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start service {unit.name}: {e}")
            self._cleanup_failed_service(unit)
            return False
    
    def _setup_process_security(self, unit: ServiceUnit):
        """Setup process security based on unit configuration"""
        def preexec():
            # Change user/group if specified
            if unit.user != 'root':
                try:
                    import pwd
                    pw_record = pwd.getpwnam(unit.user)
                    os.setgid(pw_record.pw_gid)
                    os.setuid(pw_record.pw_uid)
                except KeyError:
                    logger.warning(f"User {unit.user} not found, running as root")
            
            # Set up resource limits
            if unit.limit_nofile:
                import resource
                resource.setrlimit(resource.RLIMIT_NOFILE, (unit.limit_nofile, unit.limit_nofile))
        
        return preexec
    
    def stop_service(self, service_name: str, force: bool = False) -> bool:
        """Stop a service and dependents"""
        if service_name not in self.service_units:
            logger.error(f"Service {service_name} not found")
            return False
        
        unit = self.service_units[service_name]
        
        if unit.state not in [ServiceState.ACTIVE, ServiceState.ACTIVATING]:
            logger.info(f"Service {service_name} is not active")
            return True
        
        try:
            # Stop dependents first
            dependents = self.dependency_resolver.get_dependents(service_name)
            for dependent in dependents:
                if dependent in self.active_services:
                    self.stop_service(dependent, force)
            
            # Stop the service
            return self._stop_single_service(unit, force)
            
        except Exception as e:
            logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    def _stop_single_service(self, unit: ServiceUnit, force: bool = False) -> bool:
        """Stop a single service"""
        logger.info(f"Stopping service {unit.name}")
        unit.state = ServiceState.DEACTIVATING
        
        try:
            # Try graceful stop first
            if unit.exec_stop and not force:
                stop_command = shlex.split(unit.exec_stop)
                stop_process = subprocess.run(
                    stop_command,
                    timeout=unit.timeout_stop_sec,
                    cwd=unit.working_directory
                )
                
                if stop_process.returncode == 0:
                    # Wait for main process to exit
                    if unit.process:
                        try:
                            unit.process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            pass
            
            # Force kill if needed
            if unit.process and unit.process.poll() is None:
                if force:
                    unit.process.kill()
                else:
                    unit.process.terminate()
                
                try:
                    unit.process.wait(timeout=unit.timeout_stop_sec)
                except subprocess.TimeoutExpired:
                    unit.process.kill()
                    unit.process.wait()
            
            # Clean up
            unit.state = ServiceState.INACTIVE
            unit.active_exit_timestamp = time.time()
            unit.main_pid = None
            unit.process = None
            
            if unit.name in self.active_services:
                del self.active_services[unit.name]
            
            if unit.name in self.service_processes:
                del self.service_processes[unit.name]
            
            self._emit_event('service_stopped', unit.name)
            logger.info(f"Service {unit.name} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop service {unit.name}: {e}")
            unit.state = ServiceState.FAILED
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        if self.stop_service(service_name):
            time.sleep(0.1)  # Brief pause
            return self.start_service(service_name)
        return False
    
    def reload_service(self, service_name: str) -> bool:
        """Reload a service configuration"""
        if service_name not in self.service_units:
            logger.error(f"Service {service_name} not found")
            return False
        
        unit = self.service_units[service_name]
        
        if unit.state != ServiceState.ACTIVE:
            logger.error(f"Service {service_name} is not active")
            return False
        
        if not unit.exec_reload:
            logger.warning(f"Service {service_name} does not support reload")
            return False
        
        try:
            unit.state = ServiceState.RELOADING
            
            reload_command = shlex.split(unit.exec_reload)
            reload_process = subprocess.run(
                reload_command,
                timeout=unit.timeout_stop_sec,
                cwd=unit.working_directory
            )
            
            unit.state = ServiceState.ACTIVE
            
            if reload_process.returncode == 0:
                self._emit_event('service_reloaded', unit.name)
                logger.info(f"Service {unit.name} reloaded successfully")
                return True
            else:
                logger.error(f"Service {unit.name} reload failed")
                return False
                
        except Exception as e:
            logger.error(f"Failed to reload service {service_name}: {e}")
            unit.state = ServiceState.ACTIVE  # Restore previous state
            return False
    
    def get_service_status(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a service"""
        if service_name not in self.service_units:
            return None
        
        unit = self.service_units[service_name]
        
        status = {
            'name': unit.name,
            'description': unit.description,
            'state': unit.state.value,
            'type': unit.service_type.value,
            'main_pid': unit.main_pid,
            'start_time': unit.start_time,
            'active_enter_timestamp': unit.active_enter_timestamp,
            'active_exit_timestamp': unit.active_exit_timestamp,
            'restart_count': unit.restart_count,
            'failure_count': unit.failure_count,
            'last_failure_time': unit.last_failure_time,
            'memory_usage': None,
            'cpu_usage': None
        }
        
        # Get resource usage if process is running
        if unit.main_pid:
            try:
                process = psutil.Process(unit.main_pid)
                status['memory_usage'] = process.memory_info().rss
                status['cpu_usage'] = process.cpu_percent()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        return status
    
    def list_services(self, state_filter: Optional[ServiceState] = None) -> List[Dict[str, Any]]:
        """List all services, optionally filtered by state"""
        services = []
        
        for service_name, unit in self.service_units.items():
            if state_filter is None or unit.state == state_filter:
                status = self.get_service_status(service_name)
                if status:
                    services.append(status)
        
        return services
    
    def enable_service(self, service_name: str) -> bool:
        """Enable a service to start automatically"""
        if service_name not in self.service_units:
            logger.error(f"Service {service_name} not found")
            return False
        
        unit = self.service_units[service_name]
        
        # Create symlinks in target directories
        try:
            for target in unit.wanted_by:
                target_dir = self.system_unit_path / f"{target}.wants"
                target_dir.mkdir(exist_ok=True)
                
                service_file = self.system_unit_path / f"{service_name}.service"
                symlink_path = target_dir / f"{service_name}.service"
                
                if not symlink_path.exists():
                    symlink_path.symlink_to(service_file)
            
            logger.info(f"Service {service_name} enabled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enable service {service_name}: {e}")
            return False
    
    def disable_service(self, service_name: str) -> bool:
        """Disable a service from starting automatically"""
        if service_name not in self.service_units:
            logger.error(f"Service {service_name} not found")
            return False
        
        unit = self.service_units[service_name]
        
        # Remove symlinks from target directories
        try:
            for target in unit.wanted_by:
                target_dir = self.system_unit_path / f"{target}.wants"
                symlink_path = target_dir / f"{service_name}.service"
                
                if symlink_path.exists():
                    symlink_path.unlink()
            
            logger.info(f"Service {service_name} disabled")
            return True
            
        except Exception as e:
            logger.error(f"Failed to disable service {service_name}: {e}")
            return False
    
    def start_monitoring(self):
        """Start service monitoring thread"""
        if self.monitor_running:
            return
        
        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_services, daemon=True)
        self.monitor_thread.start()
        logger.info("Service monitoring started")
    
    def stop_monitoring(self):
        """Stop service monitoring"""
        self.monitor_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Service monitoring stopped")
    
    def _monitor_services(self):
        """Monitor active services for failures and restarts"""
        while self.monitor_running:
            try:
                for service_name in list(self.active_services.keys()):
                    unit = self.active_services[service_name]
                    
                    # Check if process is still running
                    if unit.process and unit.process.poll() is not None:
                        # Process has exited
                        exit_code = unit.process.returncode
                        logger.warning(f"Service {service_name} exited with code {exit_code}")
                        
                        # Handle restart policy
                        should_restart = self._should_restart_service(unit, exit_code)
                        
                        if should_restart:
                            logger.info(f"Restarting service {service_name} due to restart policy")
                            self._cleanup_failed_service(unit)
                            time.sleep(unit.restart_sec / 1000.0)  # Convert ms to seconds
                            self.start_service(service_name)
                        else:
                            self._cleanup_failed_service(unit)
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in service monitoring: {e}")
                time.sleep(10)
    
    def _should_restart_service(self, unit: ServiceUnit, exit_code: int) -> bool:
        """Determine if a service should be restarted based on its restart policy"""
        if unit.restart == RestartPolicy.NO:
            return False
        
        if unit.restart == RestartPolicy.ALWAYS:
            return True
        
        if unit.restart == RestartPolicy.ON_SUCCESS and exit_code == 0:
            return True
        
        if unit.restart == RestartPolicy.ON_FAILURE and exit_code != 0:
            return True
        
        if unit.restart == RestartPolicy.ON_ABNORMAL and exit_code not in [0, 1, 2, 8]:
            return True
        
        # Check restart limits
        current_time = time.time()
        if (current_time - (unit.last_failure_time or 0)) < unit.start_limit_interval_sec:
            if unit.restart_count >= unit.start_limit_burst:
                logger.error(f"Service {unit.name} hit restart limit")
                return False
        else:
            # Reset restart count if outside the interval
            unit.restart_count = 0
        
        unit.restart_count += 1
        return True
    
    def _cleanup_failed_service(self, unit: ServiceUnit):
        """Clean up a failed service"""
        unit.state = ServiceState.FAILED
        unit.failure_count += 1
        unit.last_failure_time = time.time()
        unit.active_exit_timestamp = time.time()
        
        if unit.name in self.active_services:
            del self.active_services[unit.name]
        
        if unit.name in self.service_processes:
            del self.service_processes[unit.name]
        
        self.failed_services[unit.name] = unit
        self._emit_event('service_failed', unit.name)
    
    def _emit_event(self, event_type: str, service_name: str):
        """Emit a service event to registered callbacks"""
        event = {
            'type': event_type,
            'service': service_name,
            'timestamp': time.time()
        }
        
        for callback in self.event_callbacks.get(event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """Register a callback for service events"""
        self.event_callbacks[event_type].append(callback)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        active_count = len(self.active_services)
        failed_count = len(self.failed_services)
        total_count = len(self.service_units)
        
        return {
            'total_services': total_count,
            'active_services': active_count,
            'failed_services': failed_count,
            'inactive_services': total_count - active_count - failed_count,
            'uptime': time.time() - getattr(self, 'start_time', time.time()),
            'monitoring_active': self.monitor_running
        }

# Global service manager instance
service_manager = None

def get_service_manager() -> ServiceManager:
    """Get the global service manager instance"""
    global service_manager
    if service_manager is None:
        service_manager = ServiceManager()
    return service_manager

# Export main classes and functions
__all__ = [
    'ServiceManager', 'get_service_manager',
    'ServiceUnit', 'SocketUnit', 'TimerUnit',
    'ServiceState', 'ServiceType', 'RestartPolicy', 'UnitType',
    'DependencyResolver'
] 
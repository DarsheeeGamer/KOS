"""
KOS Systemd-like Init System
Complete init system with unit management, dependencies, and targets
"""

import os
import time
import signal
import threading
import logging
import configparser
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import subprocess

logger = logging.getLogger('kos.init.systemd')


class UnitType(Enum):
    """Systemd unit types"""
    SERVICE = "service"
    SOCKET = "socket"
    DEVICE = "device"
    MOUNT = "mount"
    AUTOMOUNT = "automount"
    SWAP = "swap"
    TARGET = "target"
    PATH = "path"
    TIMER = "timer"
    SLICE = "slice"
    SCOPE = "scope"


class UnitState(Enum):
    """Unit states"""
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
    FORKING = "forking"
    ONESHOT = "oneshot"
    DBUS = "dbus"
    NOTIFY = "notify"
    IDLE = "idle"


class RestartPolicy(Enum):
    """Service restart policies"""
    NO = "no"
    ALWAYS = "always"
    ON_SUCCESS = "on-success"
    ON_FAILURE = "on-failure"
    ON_ABNORMAL = "on-abnormal"
    ON_ABORT = "on-abort"
    ON_WATCHDOG = "on-watchdog"


@dataclass
class UnitDependency:
    """Unit dependency information"""
    requires: Set[str] = field(default_factory=set)
    wants: Set[str] = field(default_factory=set)
    requisite: Set[str] = field(default_factory=set)
    binds_to: Set[str] = field(default_factory=set)
    part_of: Set[str] = field(default_factory=set)
    conflicts: Set[str] = field(default_factory=set)
    before: Set[str] = field(default_factory=set)
    after: Set[str] = field(default_factory=set)
    on_failure: Set[str] = field(default_factory=set)
    propagates_reload_to: Set[str] = field(default_factory=set)
    reload_propagated_from: Set[str] = field(default_factory=set)
    joins_namespace_of: Set[str] = field(default_factory=set)


@dataclass
class ServiceConfig:
    """Service unit configuration"""
    type: ServiceType = ServiceType.SIMPLE
    exec_start: List[str] = field(default_factory=list)
    exec_start_pre: List[str] = field(default_factory=list)
    exec_start_post: List[str] = field(default_factory=list)
    exec_reload: List[str] = field(default_factory=list)
    exec_stop: List[str] = field(default_factory=list)
    exec_stop_post: List[str] = field(default_factory=list)
    restart: RestartPolicy = RestartPolicy.NO
    restart_sec: int = 100  # milliseconds
    timeout_start_sec: int = 90  # seconds
    timeout_stop_sec: int = 90  # seconds
    runtime_max_sec: int = 0  # 0 = infinity
    watchdog_sec: int = 0  # 0 = disabled
    kill_signal: int = signal.SIGTERM
    kill_mode: str = "control-group"  # control-group, process, mixed, none
    pid_file: Optional[str] = None
    bus_name: Optional[str] = None
    notify_access: str = "none"  # none, main, exec, all
    environment: Dict[str, str] = field(default_factory=dict)
    environment_file: Optional[str] = None
    working_directory: str = "/"
    root_directory: Optional[str] = None
    user: Optional[str] = None
    group: Optional[str] = None
    capability_bounding_set: Set[str] = field(default_factory=set)
    standard_input: str = "null"  # null, tty, tty-force, tty-fail, socket, fd
    standard_output: str = "journal"  # inherit, null, tty, journal, syslog, kmsg, socket, fd
    standard_error: str = "inherit"  # same as standard_output
    limit_nofile: Optional[int] = None
    limit_nproc: Optional[int] = None
    limit_memlock: Optional[int] = None
    private_tmp: bool = False
    private_devices: bool = False
    private_network: bool = False
    protect_system: str = "no"  # no, yes, full, strict
    protect_home: str = "no"  # no, yes, read-only, tmpfs
    read_write_paths: List[str] = field(default_factory=list)
    read_only_paths: List[str] = field(default_factory=list)
    inaccessible_paths: List[str] = field(default_factory=list)


@dataclass
class TargetConfig:
    """Target unit configuration"""
    allow_isolate: bool = False
    default_dependencies: bool = True


class Unit:
    """Base systemd unit"""
    
    def __init__(self, name: str, unit_type: UnitType):
        self.name = name
        self.type = unit_type
        self.state = UnitState.INACTIVE
        self.description = ""
        self.documentation = []
        self.dependencies = UnitDependency()
        self.condition_result = True
        self.assert_result = True
        self.load_state = "loaded"  # loaded, not-found, error, masked
        self.active_enter_timestamp = 0
        self.active_exit_timestamp = 0
        self.inactive_enter_timestamp = time.time()
        self.inactive_exit_timestamp = 0
        self._lock = threading.RLock()
        
    def load_from_file(self, filepath: str):
        """Load unit from file"""
        config = configparser.ConfigParser()
        config.read(filepath)
        
        # Load [Unit] section
        if 'Unit' in config:
            unit_section = config['Unit']
            self.description = unit_section.get('Description', '')
            self.documentation = unit_section.get('Documentation', '').split()
            
            # Load dependencies
            for dep_type in ['Requires', 'Wants', 'Requisite', 'BindsTo', 
                           'PartOf', 'Conflicts', 'Before', 'After']:
                if dep_type in unit_section:
                    dep_list = unit_section[dep_type].split()
                    getattr(self.dependencies, dep_type.lower().replace('bindsto', 'binds_to')
                           .replace('partof', 'part_of')).update(dep_list)
                           
    def check_conditions(self) -> bool:
        """Check unit conditions"""
        # In real implementation, would check various conditions
        # ConditionPathExists, ConditionPathIsDirectory, etc.
        return True
        
    def check_assertions(self) -> bool:
        """Check unit assertions"""
        # In real implementation, would check assertions
        # AssertPathExists, AssertFileNotEmpty, etc.
        return True
        
    def can_start(self) -> bool:
        """Check if unit can be started"""
        with self._lock:
            return (self.state == UnitState.INACTIVE and 
                   self.condition_result and 
                   self.assert_result)
                   
    def can_stop(self) -> bool:
        """Check if unit can be stopped"""
        with self._lock:
            return self.state in [UnitState.ACTIVE, UnitState.ACTIVATING, 
                                UnitState.RELOADING]


class ServiceUnit(Unit):
    """Service unit implementation"""
    
    def __init__(self, name: str):
        super().__init__(name, UnitType.SERVICE)
        self.config = ServiceConfig()
        self.main_pid = 0
        self.control_pid = 0
        self.status_text = ""
        self.result = "success"  # success, exit-code, signal, core-dump, timeout, etc.
        self._process = None
        self._watchdog_timer = None
        
    def load_from_file(self, filepath: str):
        """Load service unit from file"""
        super().load_from_file(filepath)
        
        config = configparser.ConfigParser()
        config.read(filepath)
        
        if 'Service' in config:
            service_section = config['Service']
            
            # Service type
            if 'Type' in service_section:
                self.config.type = ServiceType(service_section['Type'])
                
            # Exec commands
            if 'ExecStart' in service_section:
                self.config.exec_start = [service_section['ExecStart']]
            if 'ExecStartPre' in service_section:
                self.config.exec_start_pre = service_section['ExecStartPre'].split('\n')
            if 'ExecStartPost' in service_section:
                self.config.exec_start_post = service_section['ExecStartPost'].split('\n')
            if 'ExecReload' in service_section:
                self.config.exec_reload = [service_section['ExecReload']]
            if 'ExecStop' in service_section:
                self.config.exec_stop = [service_section['ExecStop']]
                
            # Restart policy
            if 'Restart' in service_section:
                self.config.restart = RestartPolicy(service_section['Restart'])
            if 'RestartSec' in service_section:
                self.config.restart_sec = int(service_section['RestartSec'])
                
            # Timeouts
            if 'TimeoutStartSec' in service_section:
                self.config.timeout_start_sec = int(service_section['TimeoutStartSec'])
            if 'TimeoutStopSec' in service_section:
                self.config.timeout_stop_sec = int(service_section['TimeoutStopSec'])
                
            # User/Group
            if 'User' in service_section:
                self.config.user = service_section['User']
            if 'Group' in service_section:
                self.config.group = service_section['Group']
                
            # Working directory
            if 'WorkingDirectory' in service_section:
                self.config.working_directory = service_section['WorkingDirectory']
                
            # Environment
            if 'Environment' in service_section:
                for env_line in service_section['Environment'].split('\n'):
                    if '=' in env_line:
                        key, value = env_line.split('=', 1)
                        self.config.environment[key.strip()] = value.strip()
                        
    def start(self) -> bool:
        """Start service"""
        with self._lock:
            if not self.can_start():
                return False
                
            self.state = UnitState.ACTIVATING
            self.inactive_exit_timestamp = time.time()
            
            try:
                # Execute pre-start commands
                for cmd in self.config.exec_start_pre:
                    if not self._execute_command(cmd):
                        raise RuntimeError("Pre-start command failed")
                        
                # Start main process
                if self.config.exec_start:
                    self._start_main_process()
                    
                # Execute post-start commands
                for cmd in self.config.exec_start_post:
                    self._execute_command(cmd)
                    
                # Update state
                self.state = UnitState.ACTIVE
                self.active_enter_timestamp = time.time()
                self.result = "success"
                
                # Start watchdog if configured
                if self.config.watchdog_sec > 0:
                    self._start_watchdog()
                    
                logger.info(f"Started service {self.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to start service {self.name}: {e}")
                self.state = UnitState.FAILED
                self.result = "exit-code"
                return False
                
    def _start_main_process(self):
        """Start main service process"""
        cmd = self.config.exec_start[0]
        
        # Parse command
        import shlex
        args = shlex.split(cmd)
        
        # Setup environment
        env = os.environ.copy()
        env.update(self.config.environment)
        
        # Start process
        self._process = subprocess.Popen(
            args,
            env=env,
            cwd=self.config.working_directory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        self.main_pid = self._process.pid
        
        # For forking services, wait for main process to exit
        if self.config.type == ServiceType.FORKING:
            self._process.wait()
            # Read PID file if configured
            if self.config.pid_file and os.path.exists(self.config.pid_file):
                with open(self.config.pid_file) as f:
                    self.main_pid = int(f.read().strip())
                    
    def stop(self) -> bool:
        """Stop service"""
        with self._lock:
            if not self.can_stop():
                return False
                
            self.state = UnitState.DEACTIVATING
            self.active_exit_timestamp = time.time()
            
            try:
                # Stop watchdog
                if self._watchdog_timer:
                    self._watchdog_timer.cancel()
                    
                # Execute stop commands
                if self.config.exec_stop:
                    for cmd in self.config.exec_stop:
                        self._execute_command(cmd)
                else:
                    # Default: send kill signal
                    self._kill_processes()
                    
                # Execute post-stop commands
                for cmd in self.config.exec_stop_post:
                    self._execute_command(cmd)
                    
                # Update state
                self.state = UnitState.INACTIVE
                self.inactive_enter_timestamp = time.time()
                self.main_pid = 0
                
                logger.info(f"Stopped service {self.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop service {self.name}: {e}")
                self.state = UnitState.FAILED
                return False
                
    def _kill_processes(self):
        """Kill service processes"""
        if self.main_pid > 0:
            try:
                # Send configured kill signal
                os.kill(self.main_pid, self.config.kill_signal)
                
                # Wait for process to exit
                start_time = time.time()
                while time.time() - start_time < self.config.timeout_stop_sec:
                    try:
                        os.kill(self.main_pid, 0)  # Check if alive
                        time.sleep(0.1)
                    except ProcessLookupError:
                        break
                else:
                    # Force kill
                    os.kill(self.main_pid, signal.SIGKILL)
                    
            except ProcessLookupError:
                pass  # Already dead
                
    def reload(self) -> bool:
        """Reload service configuration"""
        with self._lock:
            if self.state != UnitState.ACTIVE:
                return False
                
            self.state = UnitState.RELOADING
            
            try:
                # Execute reload commands
                if self.config.exec_reload:
                    for cmd in self.config.exec_reload:
                        self._execute_command(cmd)
                else:
                    # Default: send SIGHUP
                    if self.main_pid > 0:
                        os.kill(self.main_pid, signal.SIGHUP)
                        
                self.state = UnitState.ACTIVE
                logger.info(f"Reloaded service {self.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to reload service {self.name}: {e}")
                return False
                
    def _execute_command(self, cmd: str) -> bool:
        """Execute command"""
        try:
            import shlex
            args = shlex.split(cmd)
            
            env = os.environ.copy()
            env.update(self.config.environment)
            
            result = subprocess.run(
                args,
                env=env,
                cwd=self.config.working_directory,
                capture_output=True
            )
            
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Failed to execute command '{cmd}': {e}")
            return False
            
    def _start_watchdog(self):
        """Start watchdog timer"""
        def watchdog_expired():
            logger.warning(f"Watchdog expired for service {self.name}")
            self.state = UnitState.FAILED
            self.result = "watchdog"
            self._kill_processes()
            
        self._watchdog_timer = threading.Timer(
            self.config.watchdog_sec,
            watchdog_expired
        )
        self._watchdog_timer.start()
        
    def reset_watchdog(self):
        """Reset watchdog timer"""
        if self._watchdog_timer:
            self._watchdog_timer.cancel()
            self._start_watchdog()


class TargetUnit(Unit):
    """Target unit implementation"""
    
    def __init__(self, name: str):
        super().__init__(name, UnitType.TARGET)
        self.config = TargetConfig()
        
    def start(self) -> bool:
        """Start target"""
        with self._lock:
            if not self.can_start():
                return False
                
            self.state = UnitState.ACTIVATING
            self.inactive_exit_timestamp = time.time()
            
            # Targets are immediately active
            self.state = UnitState.ACTIVE
            self.active_enter_timestamp = time.time()
            
            logger.info(f"Reached target {self.name}")
            return True
            
    def stop(self) -> bool:
        """Stop target"""
        with self._lock:
            if not self.can_stop():
                return False
                
            self.state = UnitState.DEACTIVATING
            self.active_exit_timestamp = time.time()
            
            # Targets are immediately inactive
            self.state = UnitState.INACTIVE
            self.inactive_enter_timestamp = time.time()
            
            logger.info(f"Stopped target {self.name}")
            return True


class SystemdManager:
    """Systemd-like init system manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.units: Dict[str, Unit] = {}
        self.jobs = []
        self.default_target = "multi-user.target"
        self.system_state = "initializing"  # initializing, starting, running, degraded, maintenance, stopping
        self._lock = threading.RLock()
        
        # Unit directories
        self.unit_dirs = [
            "/etc/systemd/system",
            "/run/systemd/system",
            "/usr/lib/systemd/system"
        ]
        
        # Load units
        self._load_units()
        
        # Create default targets
        self._create_default_targets()
        
    def _load_units(self):
        """Load all unit files"""
        for unit_dir in self.unit_dirs:
            if os.path.exists(unit_dir):
                for filename in os.listdir(unit_dir):
                    if filename.endswith(('.service', '.target', '.socket', 
                                        '.device', '.mount', '.swap')):
                        filepath = os.path.join(unit_dir, filename)
                        self._load_unit_file(filepath)
                        
    def _load_unit_file(self, filepath: str):
        """Load single unit file"""
        filename = os.path.basename(filepath)
        
        # Determine unit type
        if filename.endswith('.service'):
            unit = ServiceUnit(filename)
        elif filename.endswith('.target'):
            unit = TargetUnit(filename)
        else:
            # Generic unit for now
            unit_type = filename.split('.')[-1]
            unit = Unit(filename, UnitType(unit_type))
            
        # Load configuration
        unit.load_from_file(filepath)
        
        # Add to units
        with self._lock:
            self.units[filename] = unit
            
        logger.debug(f"Loaded unit {filename}")
        
    def _create_default_targets(self):
        """Create default system targets"""
        default_targets = [
            "basic.target",
            "sysinit.target",
            "rescue.target",
            "multi-user.target",
            "graphical.target",
            "poweroff.target",
            "reboot.target",
            "halt.target",
            "emergency.target",
            "default.target"
        ]
        
        for target_name in default_targets:
            if target_name not in self.units:
                target = TargetUnit(target_name)
                target.description = f"System {target_name}"
                self.units[target_name] = target
                
        # Set up target dependencies
        self._setup_target_dependencies()
        
    def _setup_target_dependencies(self):
        """Setup default target dependencies"""
        # basic.target wants sysinit.target
        if "basic.target" in self.units:
            self.units["basic.target"].dependencies.wants.add("sysinit.target")
            self.units["basic.target"].dependencies.after.add("sysinit.target")
            
        # multi-user.target wants basic.target
        if "multi-user.target" in self.units:
            self.units["multi-user.target"].dependencies.requires.add("basic.target")
            self.units["multi-user.target"].dependencies.after.add("basic.target")
            
        # graphical.target wants multi-user.target
        if "graphical.target" in self.units:
            self.units["graphical.target"].dependencies.requires.add("multi-user.target")
            self.units["graphical.target"].dependencies.after.add("multi-user.target")
            
    def start_unit(self, unit_name: str) -> bool:
        """Start a unit and its dependencies"""
        with self._lock:
            unit = self.units.get(unit_name)
            if not unit:
                logger.error(f"Unit {unit_name} not found")
                return False
                
            # Check if already active
            if unit.state == UnitState.ACTIVE:
                return True
                
            # Start dependencies first
            for dep in unit.dependencies.requires | unit.dependencies.wants:
                if dep in self.units:
                    self.start_unit(dep)
                    
            # Start units that should be started before this one
            for before_unit_name in unit.dependencies.before:
                if before_unit_name in self.units:
                    before_unit = self.units[before_unit_name]
                    if before_unit.state == UnitState.INACTIVE:
                        self.start_unit(before_unit_name)
                        
            # Start the unit
            if isinstance(unit, ServiceUnit):
                return unit.start()
            elif isinstance(unit, TargetUnit):
                return unit.start()
            else:
                # Generic start
                unit.state = UnitState.ACTIVE
                return True
                
    def stop_unit(self, unit_name: str) -> bool:
        """Stop a unit"""
        with self._lock:
            unit = self.units.get(unit_name)
            if not unit:
                return False
                
            # Stop the unit
            if isinstance(unit, ServiceUnit):
                return unit.stop()
            elif isinstance(unit, TargetUnit):
                return unit.stop()
            else:
                # Generic stop
                unit.state = UnitState.INACTIVE
                return True
                
    def reload_unit(self, unit_name: str) -> bool:
        """Reload a unit"""
        unit = self.units.get(unit_name)
        if not unit:
            return False
            
        if isinstance(unit, ServiceUnit):
            return unit.reload()
        else:
            # No reload for other unit types
            return False
            
    def restart_unit(self, unit_name: str) -> bool:
        """Restart a unit"""
        if self.stop_unit(unit_name):
            time.sleep(0.1)  # Brief pause
            return self.start_unit(unit_name)
        return False
        
    def get_unit_status(self, unit_name: str) -> Dict[str, Any]:
        """Get unit status"""
        unit = self.units.get(unit_name)
        if not unit:
            return {}
            
        status = {
            'name': unit.name,
            'type': unit.type.value,
            'state': unit.state.value,
            'description': unit.description,
            'load_state': unit.load_state,
            'active_enter_timestamp': unit.active_enter_timestamp,
            'inactive_enter_timestamp': unit.inactive_enter_timestamp
        }
        
        if isinstance(unit, ServiceUnit):
            status.update({
                'main_pid': unit.main_pid,
                'status_text': unit.status_text,
                'result': unit.result
            })
            
        return status
        
    def list_units(self, unit_type: Optional[UnitType] = None, 
                  state: Optional[UnitState] = None) -> List[Dict[str, Any]]:
        """List units with optional filtering"""
        units = []
        
        for unit in self.units.values():
            if unit_type and unit.type != unit_type:
                continue
            if state and unit.state != state:
                continue
                
            units.append(self.get_unit_status(unit.name))
            
        return units
        
    def isolate_target(self, target_name: str) -> bool:
        """Isolate to a specific target (stop all units not required by target)"""
        target = self.units.get(target_name)
        if not target or target.type != UnitType.TARGET:
            return False
            
        # Check if target allows isolation
        if isinstance(target, TargetUnit) and not target.config.allow_isolate:
            logger.error(f"Target {target_name} does not allow isolation")
            return False
            
        # Find all units required by target
        required_units = self._get_target_dependencies(target_name)
        required_units.add(target_name)
        
        # Stop units not required
        for unit_name, unit in self.units.items():
            if unit_name not in required_units and unit.state == UnitState.ACTIVE:
                self.stop_unit(unit_name)
                
        # Start target
        return self.start_unit(target_name)
        
    def _get_target_dependencies(self, target_name: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """Get all dependencies of a target recursively"""
        if visited is None:
            visited = set()
            
        if target_name in visited:
            return set()
            
        visited.add(target_name)
        dependencies = set()
        
        target = self.units.get(target_name)
        if target:
            # Add direct dependencies
            deps = target.dependencies.requires | target.dependencies.wants
            dependencies.update(deps)
            
            # Recursively add dependencies
            for dep in deps:
                dependencies.update(self._get_target_dependencies(dep, visited))
                
        return dependencies
        
    def poweroff(self):
        """System poweroff"""
        logger.info("System poweroff initiated")
        self.isolate_target("poweroff.target")
        
    def reboot(self):
        """System reboot"""
        logger.info("System reboot initiated")
        self.isolate_target("reboot.target")
        
    def halt(self):
        """System halt"""
        logger.info("System halt initiated")
        self.isolate_target("halt.target")
        
    def emergency_mode(self):
        """Enter emergency mode"""
        logger.warning("Entering emergency mode")
        self.isolate_target("emergency.target")
        
    def get_system_state(self) -> str:
        """Get overall system state"""
        # Check if any units are failed
        failed_units = [u for u in self.units.values() if u.state == UnitState.FAILED]
        
        if failed_units:
            self.system_state = "degraded"
        elif all(u.state == UnitState.ACTIVE for u in self.units.values() 
                if u.type == UnitType.SERVICE):
            self.system_state = "running"
        else:
            self.system_state = "starting"
            
        return self.system_state


# Global systemd manager instance
_systemd_manager = None

def get_systemd_manager(kernel) -> SystemdManager:
    """Get global systemd manager"""
    global _systemd_manager
    if _systemd_manager is None:
        _systemd_manager = SystemdManager(kernel)
    return _systemd_manager
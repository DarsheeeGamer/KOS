"""
KOS Service Management System

This module provides systemd-like service management capabilities, including:
- Service creation and configuration
- Service lifecycle management (start, stop, restart, etc.)
- Service dependency resolution
- Service health monitoring and automatic recovery
- Service status reporting
"""

import logging
import os
import signal
import threading
import time
import json
import uuid
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable

from .. import process
from .. import ipc

# Initialize logging
logger = logging.getLogger('KOS.service')

# Service system constants
SERVICE_BASE_DIR = "/tmp/kos/services"
SERVICE_CONFIG_DIR = os.path.join(SERVICE_BASE_DIR, "config")
SERVICE_STATE_DIR = os.path.join(SERVICE_BASE_DIR, "state")

# Service states
class ServiceState(Enum):
    INACTIVE = auto()  # Service is not running
    STARTING = auto()  # Service is in the process of starting
    RUNNING = auto()   # Service is running normally
    RELOADING = auto() # Service is reloading its configuration
    STOPPING = auto()  # Service is in the process of stopping
    FAILED = auto()    # Service has failed
    ACTIVATING = auto() # Service is being activated (resolving dependencies)
    DEACTIVATING = auto() # Service is being deactivated

# Service types
class ServiceType(Enum):
    SIMPLE = auto()    # Service starts and runs a main process directly
    FORKING = auto()   # Service forks to create the main process
    ONESHOT = auto()   # Service runs once and exits
    NOTIFY = auto()    # Service sends notifications when startup is complete
    IDLE = auto()      # Service runs after boot tasks are complete

# Service restart policies
class RestartPolicy(Enum):
    NO = auto()        # Don't restart
    ON_SUCCESS = auto() # Restart only if exit is clean
    ON_FAILURE = auto() # Restart only if exit is unclean
    ON_ABNORMAL = auto() # Restart only if exit is unclean or by signal
    ON_WATCHDOG = auto() # Restart only if watchdog timeout occurs
    ALWAYS = auto()    # Always restart

# Service manager global state
_services = {}  # All registered services
_service_lock = threading.RLock()  # Lock for thread-safe operations
_monitor_thread = None  # Service monitoring thread
_is_initialized = False  # Whether the service system is initialized

class KOSService:
    """
    Represents a KOS service, similar to a systemd unit
    """
    def __init__(self, name, description=None, exec_start=None, service_type=ServiceType.SIMPLE,
                 restart=RestartPolicy.ON_FAILURE, working_directory=None, user=None,
                 environment=None, dependencies=None, conflicts=None):
        """
        Initialize a KOS service
        
        Args:
            name: Unique service name
            description: Human-readable description
            exec_start: Command to execute
            service_type: Type of service
            restart: Restart policy
            working_directory: Working directory
            user: User to run as
            environment: Environment variables
            dependencies: Services that must be running before this one
            conflicts: Services that cannot run alongside this one
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description or f"KOS service: {name}"
        self.exec_start = exec_start
        self.service_type = service_type
        self.restart_policy = restart
        self.working_directory = working_directory
        self.user = user
        self.environment = environment or {}
        self.dependencies = dependencies or []
        self.conflicts = conflicts or []
        
        # Runtime state
        self.state = ServiceState.INACTIVE
        self.pid = None
        self.start_time = None
        self.stop_time = None
        self.restart_count = 0
        self.last_exit_code = None
        self.last_exit_time = None
        self.watchdog_timer = None
        self.config_path = os.path.join(SERVICE_CONFIG_DIR, f"{name}.service")
        self.state_path = os.path.join(SERVICE_STATE_DIR, f"{name}.state")
        
        # Performance metrics
        self.cpu_usage = 0.0
        self.memory_usage = 0
        self.io_read = 0
        self.io_write = 0
        
        # IPC resources
        self.stdout_pipe = None
        self.stderr_pipe = None
        self.control_pipe = None
        
    def save_config(self) -> bool:
        """Save service configuration to disk"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config = {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'exec_start': self.exec_start,
                'service_type': self.service_type.name,
                'restart_policy': self.restart_policy.name,
                'working_directory': self.working_directory,
                'user': self.user,
                'environment': self.environment,
                'dependencies': self.dependencies,
                'conflicts': self.conflicts
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving service configuration for {self.name}: {e}")
            return False
    
    def save_state(self) -> bool:
        """Save service state to disk"""
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            
            state = {
                'id': self.id,
                'name': self.name,
                'state': self.state.name,
                'pid': self.pid,
                'start_time': self.start_time,
                'stop_time': self.stop_time,
                'restart_count': self.restart_count,
                'last_exit_code': self.last_exit_code,
                'last_exit_time': self.last_exit_time,
                'cpu_usage': self.cpu_usage,
                'memory_usage': self.memory_usage,
                'io_read': self.io_read,
                'io_write': self.io_write
            }
            
            with open(self.state_path, 'w') as f:
                json.dump(state, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving service state for {self.name}: {e}")
            return False
    
    @classmethod
    def load_from_config(cls, config_path) -> 'KOSService':
        """Load service from configuration file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            service = cls(
                name=config['name'],
                description=config['description'],
                exec_start=config['exec_start'],
                service_type=ServiceType[config['service_type']],
                restart=RestartPolicy[config['restart_policy']],
                working_directory=config['working_directory'],
                user=config['user'],
                environment=config['environment'],
                dependencies=config['dependencies'],
                conflicts=config['conflicts']
            )
            
            service.id = config['id']
            
            # Load state if available
            state_path = os.path.join(SERVICE_STATE_DIR, f"{service.name}.state")
            if os.path.exists(state_path):
                try:
                    with open(state_path, 'r') as f:
                        state = json.load(f)
                    
                    service.state = ServiceState[state['state']]
                    service.pid = state['pid']
                    service.start_time = state['start_time']
                    service.stop_time = state['stop_time']
                    service.restart_count = state['restart_count']
                    service.last_exit_code = state['last_exit_code']
                    service.last_exit_time = state['last_exit_time']
                    service.cpu_usage = state['cpu_usage']
                    service.memory_usage = state['memory_usage']
                    service.io_read = state['io_read']
                    service.io_write = state['io_write']
                except Exception as e:
                    logger.warning(f"Error loading service state for {service.name}: {e}")
            
            return service
        
        except Exception as e:
            logger.error(f"Error loading service from {config_path}: {e}")
            return None
    
    def start(self) -> bool:
        """Start the service"""
        with _service_lock:
            if self.state in (ServiceState.RUNNING, ServiceState.STARTING):
                logger.warning(f"Service {self.name} is already running or starting")
                return True
            
            try:
                logger.info(f"Starting service {self.name}")
                self.state = ServiceState.ACTIVATING
                
                # Check dependencies
                for dep in self.dependencies:
                    if dep not in _services:
                        logger.error(f"Dependency {dep} not found for service {self.name}")
                        self.state = ServiceState.FAILED
                        self.save_state()
                        return False
                    
                    if _services[dep].state != ServiceState.RUNNING:
                        logger.info(f"Starting dependency {dep} for service {self.name}")
                        if not _services[dep].start():
                            logger.error(f"Failed to start dependency {dep} for service {self.name}")
                            self.state = ServiceState.FAILED
                            self.save_state()
                            return False
                
                # Check conflicts
                for conflict in self.conflicts:
                    if conflict in _services and _services[conflict].state == ServiceState.RUNNING:
                        logger.error(f"Conflicting service {conflict} is running, cannot start {self.name}")
                        self.state = ServiceState.FAILED
                        self.save_state()
                        return False
                
                # Create IPC pipes for stdout/stderr
                self.stdout_pipe = ipc.create_pipe(name=f"{self.name}_stdout")
                self.stderr_pipe = ipc.create_pipe(name=f"{self.name}_stderr")
                self.control_pipe = ipc.create_pipe(name=f"{self.name}_control")
                
                # Set state to starting
                self.state = ServiceState.STARTING
                
                # Create process
                env = os.environ.copy()
                env.update(self.environment)
                
                # Add special environment variables
                env['KOS_SERVICE_NAME'] = self.name
                env['KOS_SERVICE_ID'] = self.id
                env['KOS_STDOUT_PIPE'] = self.stdout_pipe
                env['KOS_STDERR_PIPE'] = self.stderr_pipe
                env['KOS_CONTROL_PIPE'] = self.control_pipe
                
                # Start the process
                self.pid = process.create_process(
                    command=self.exec_start,
                    working_dir=self.working_directory,
                    env=env,
                    user=self.user
                )
                
                if not self.pid:
                    logger.error(f"Failed to start process for service {self.name}")
                    self.state = ServiceState.FAILED
                    self.save_state()
                    return False
                
                # Update state
                self.state = ServiceState.RUNNING
                self.start_time = time.time()
                self.stop_time = None
                self.save_state()
                
                logger.info(f"Service {self.name} started with PID {self.pid}")
                return True
            
            except Exception as e:
                logger.error(f"Error starting service {self.name}: {e}")
                self.state = ServiceState.FAILED
                self.save_state()
                return False
    
    def stop(self) -> bool:
        """Stop the service"""
        with _service_lock:
            if self.state not in (ServiceState.RUNNING, ServiceState.STARTING):
                logger.warning(f"Service {self.name} is not running")
                return True
            
            try:
                logger.info(f"Stopping service {self.name}")
                self.state = ServiceState.STOPPING
                
                # Check for reverse dependencies
                for svc_name, service in _services.items():
                    if self.name in service.dependencies and service.state == ServiceState.RUNNING:
                        logger.info(f"Stopping dependent service {svc_name}")
                        service.stop()
                
                # Send a termination signal to the process
                if self.pid and process.process_exists(self.pid):
                    # First send SIGTERM
                    process.send_signal(self.pid, signal.SIGTERM)
                    
                    # Wait for up to 10 seconds for the process to terminate
                    for _ in range(10):
                        if not process.process_exists(self.pid):
                            break
                        time.sleep(1)
                    
                    # If it's still running, send SIGKILL
                    if process.process_exists(self.pid):
                        process.send_signal(self.pid, signal.SIGKILL)
                
                # Close IPC resources
                if self.stdout_pipe:
                    ipc.close_pipe(self.stdout_pipe)
                    self.stdout_pipe = None
                
                if self.stderr_pipe:
                    ipc.close_pipe(self.stderr_pipe)
                    self.stderr_pipe = None
                
                if self.control_pipe:
                    ipc.close_pipe(self.control_pipe)
                    self.control_pipe = None
                
                # Update state
                self.state = ServiceState.INACTIVE
                self.stop_time = time.time()
                self.save_state()
                
                logger.info(f"Service {self.name} stopped")
                return True
            
            except Exception as e:
                logger.error(f"Error stopping service {self.name}: {e}")
                self.state = ServiceState.FAILED
                self.save_state()
                return False
    
    def restart(self) -> bool:
        """Restart the service"""
        with _service_lock:
            logger.info(f"Restarting service {self.name}")
            
            if self.state == ServiceState.RUNNING:
                if not self.stop():
                    return False
            
            # Small delay to ensure proper cleanup
            time.sleep(0.5)
            
            return self.start()
    
    def reload(self) -> bool:
        """Reload service configuration"""
        with _service_lock:
            if self.state != ServiceState.RUNNING:
                logger.warning(f"Service {self.name} is not running, cannot reload")
                return False
            
            try:
                logger.info(f"Reloading service {self.name}")
                self.state = ServiceState.RELOADING
                
                # Send reload signal to process
                if self.pid and process.process_exists(self.pid):
                    ipc.send_signal(self.pid, signal.SIGHUP)
                
                # Update state
                self.state = ServiceState.RUNNING
                self.save_state()
                
                logger.info(f"Service {self.name} reloaded")
                return True
            
            except Exception as e:
                logger.error(f"Error reloading service {self.name}: {e}")
                self.state = ServiceState.FAILED
                self.save_state()
                return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed service status"""
        with _service_lock:
            # Update process metrics if running
            if self.state == ServiceState.RUNNING and self.pid and process.process_exists(self.pid):
                try:
                    # Get process metrics using process module
                    proc_info = process.get_process_info(self.pid)
                    if proc_info:
                        self.cpu_usage = proc_info.get('cpu_percent', 0.0)
                        self.memory_usage = proc_info.get('memory_percent', 0.0)
                        self.io_read = proc_info.get('io_read_count', 0)
                        self.io_write = proc_info.get('io_write_count', 0)
                except Exception as e:
                    logger.warning(f"Error getting process metrics for service {self.name}: {e}")
            
            # Prepare status information
            status = {
                'id': self.id,
                'name': self.name,
                'description': self.description,
                'state': self.state.name,
                'pid': self.pid,
                'uptime': time.time() - self.start_time if self.start_time else None,
                'restart_count': self.restart_count,
                'last_exit_code': self.last_exit_code,
                'last_exit_time': self.last_exit_time,
                'cpu_usage': self.cpu_usage,
                'memory_usage': self.memory_usage,
                'io_read': self.io_read,
                'io_write': self.io_write,
                'service_type': self.service_type.name,
                'restart_policy': self.restart_policy.name,
                'dependencies': self.dependencies,
                'conflicts': self.conflicts
            }
            
            return status

# Service manager functions
def initialize() -> bool:
    """Initialize the service management subsystem"""
    global _is_initialized, _monitor_thread
    
    if _is_initialized:
        return True
    
    try:
        logger.info("Initializing service management subsystem")
        
        # Create service directories
        os.makedirs(SERVICE_BASE_DIR, exist_ok=True)
        os.makedirs(SERVICE_CONFIG_DIR, exist_ok=True)
        os.makedirs(SERVICE_STATE_DIR, exist_ok=True)
        
        # Load existing services
        _load_services()
        
        # Start monitoring thread
        _monitor_thread = threading.Thread(target=_service_monitor, daemon=True)
        _monitor_thread.start()
        
        _is_initialized = True
        logger.info("Service management subsystem initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize service management subsystem: {e}")
        return False

def shutdown() -> bool:
    """Shutdown the service management subsystem"""
    global _is_initialized, _monitor_thread
    
    if not _is_initialized:
        return True
    
    try:
        logger.info("Shutting down service management subsystem")
        
        # Stop all services
        for service_name in list(_services.keys()):
            stop_service(service_name)
        
        _is_initialized = False
        
        # Terminate monitoring thread
        if _monitor_thread and _monitor_thread.is_alive():
            # We can't directly stop threads in Python, 
            # but setting _is_initialized to False will cause it to exit
            _monitor_thread.join(timeout=3.0)
        
        logger.info("Service management subsystem shut down successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to shutdown service management subsystem: {e}")
        return False

def _load_services():
    """Load existing services from disk"""
    try:
        import glob
        
        # Find all service configuration files
        config_files = glob.glob(os.path.join(SERVICE_CONFIG_DIR, "*.service"))
        
        for config_path in config_files:
            service = KOSService.load_from_config(config_path)
            if service:
                _services[service.name] = service
                logger.info(f"Loaded service: {service.name}")
        
        logger.info(f"Loaded {len(_services)} services")
    
    except Exception as e:
        logger.error(f"Error loading services: {e}")

def _service_monitor():
    """Monitor service health and restart failed services"""
    logger.info("Service monitor thread started")
    
    while _is_initialized:
        try:
            with _service_lock:
                # Check each running service
                for service_name, service in _services.items():
                    if service.state == ServiceState.RUNNING:
                        # Check if process is still running
                        if service.pid and not process.process_exists(service.pid):
                            logger.warning(f"Service {service_name} process (PID {service.pid}) has terminated")
                            
                            # Update service state
                            service.state = ServiceState.INACTIVE
                            service.stop_time = time.time()
                            service.save_state()
                            
                            # Restart according to policy
                            if service.restart_policy in (RestartPolicy.ALWAYS, RestartPolicy.ON_FAILURE):
                                logger.info(f"Restarting service {service_name} per policy {service.restart_policy}")
                                service.restart_count += 1
                                service.start()
            
            # Sleep to avoid excessive CPU usage
            time.sleep(2.0)
        
        except Exception as e:
            logger.error(f"Error in service monitor thread: {e}")
            time.sleep(5.0)  # Sleep longer on error
    
    logger.info("Service monitor thread stopped")

def create_service(name: str, description: str = None, exec_start: str = None, 
                  service_type: ServiceType = ServiceType.SIMPLE,
                  restart: RestartPolicy = RestartPolicy.ON_FAILURE,
                  working_directory: str = None, user: str = None,
                  environment: Dict[str, str] = None,
                  dependencies: List[str] = None,
                  conflicts: List[str] = None) -> Optional[KOSService]:
    """Create a new service"""
    with _service_lock:
        try:
            # Check if the service already exists
            if name in _services:
                logger.warning(f"Service {name} already exists")
                return _services[name]
            
            # Create new service
            service = KOSService(
                name=name,
                description=description,
                exec_start=exec_start,
                service_type=service_type,
                restart=restart,
                working_directory=working_directory,
                user=user,
                environment=environment,
                dependencies=dependencies,
                conflicts=conflicts
            )
            
            # Save service configuration
            if not service.save_config():
                logger.error(f"Failed to save configuration for service {name}")
                return None
            
            # Add to registry
            _services[name] = service
            
            logger.info(f"Created service: {name}")
            return service
        
        except Exception as e:
            logger.error(f"Error creating service {name}: {e}")
            return None

def delete_service(name: str) -> bool:
    """Delete a service"""
    with _service_lock:
        try:
            # Check if the service exists
            if name not in _services:
                logger.warning(f"Service {name} does not exist")
                return False
            
            service = _services[name]
            
            # Stop the service if it's running
            if service.state in (ServiceState.RUNNING, ServiceState.STARTING):
                service.stop()
            
            # Remove configuration and state files
            if os.path.exists(service.config_path):
                os.remove(service.config_path)
            
            if os.path.exists(service.state_path):
                os.remove(service.state_path)
            
            # Remove from registry
            del _services[name]
            
            logger.info(f"Deleted service: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting service {name}: {e}")
            return False

def start_service(name: str) -> bool:
    """Start a service"""
    with _service_lock:
        try:
            # Check if the service exists
            if name not in _services:
                logger.warning(f"Service {name} does not exist")
                return False
            
            return _services[name].start()
        
        except Exception as e:
            logger.error(f"Error starting service {name}: {e}")
            return False

def stop_service(name: str) -> bool:
    """Stop a service"""
    with _service_lock:
        try:
            # Check if the service exists
            if name not in _services:
                logger.warning(f"Service {name} does not exist")
                return False
            
            return _services[name].stop()
        
        except Exception as e:
            logger.error(f"Error stopping service {name}: {e}")
            return False

def restart_service(name: str) -> bool:
    """Restart a service"""
    with _service_lock:
        try:
            # Check if the service exists
            if name not in _services:
                logger.warning(f"Service {name} does not exist")
                return False
            
            return _services[name].restart()
        
        except Exception as e:
            logger.error(f"Error restarting service {name}: {e}")
            return False

def list_services() -> List[Dict[str, Any]]:
    """List all services and their basic status"""
    with _service_lock:
        try:
            return [
                {
                    'name': svc.name,
                    'description': svc.description,
                    'state': svc.state.name,
                    'pid': svc.pid,
                    'uptime': time.time() - svc.start_time if svc.start_time else None,
                    'restart_count': svc.restart_count
                }
                for svc in _services.values()
            ]
        
        except Exception as e:
            logger.error(f"Error listing services: {e}")
            return []

def get_service_status(name: str) -> Optional[Dict[str, Any]]:
    """Get detailed status of a service"""
    with _service_lock:
        try:
            # Check if the service exists
            if name not in _services:
                logger.warning(f"Service {name} does not exist")
                return None
            
            return _services[name].get_status()
        
        except Exception as e:
            logger.error(f"Error getting service status for {name}: {e}")
            return None
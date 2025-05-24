
"""
KOS Service Manager

This module provides a systemd-like service management system for KOS,
allowing for the definition, control and monitoring of system services.
"""

import os
import sys
import time
import logging
import threading
import signal
import subprocess
import uuid
import json
import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

# Set up logging
logger = logging.getLogger('KOS.services')

# Service registry
SERVICES = {}
SERVICE_LOCK = threading.Lock()

class ServiceState(Enum):
    """Service state enum"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    ACTIVATING = "activating"
    DEACTIVATING = "deactivating"
    FAILED = "failed"
    RELOADING = "reloading"

class ServiceType(Enum):
    """Service type enum"""
    SIMPLE = "simple"
    FORKING = "forking"
    ONESHOT = "oneshot"
    DBUS = "dbus"
    NOTIFY = "notify"
    IDLE = "idle"

class ServiceRestartPolicy(Enum):
    """Service restart policy enum"""
    NO = "no"
    ALWAYS = "always"
    ON_SUCCESS = "on-success"
    ON_FAILURE = "on-failure"
    ON_ABNORMAL = "on-abnormal"
    ON_ABORT = "on-abort"
    ON_WATCHDOG = "on-watchdog"

class Service:
    """Service class representing a system service"""
    
    def __init__(self, name: str, description: str = None, command: str = None, 
                 working_dir: str = None, environment: Dict[str, str] = None,
                 user: str = None, group: str = None, 
                 type: ServiceType = ServiceType.SIMPLE,
                 restart: ServiceRestartPolicy = ServiceRestartPolicy.NO,
                 restart_sec: int = 5, timeout_sec: int = 30,
                 wants: List[str] = None, requires: List[str] = None,
                 after: List[str] = None, before: List[str] = None):
        """Initialize a new service"""
        self.id = str(uuid.uuid4())[:8]
        self.name = name
        self.description = description or f"Service {name}"
        self.command = command
        self.working_dir = working_dir or os.getcwd()
        self.environment = environment or {}
        self.user = user
        self.group = group
        self.type = type
        self.restart = restart
        self.restart_sec = restart_sec
        self.timeout_sec = timeout_sec
        self.wants = wants or []
        self.requires = requires or []
        self.after = after or []
        self.before = before or []
        
        # Runtime state
        self.state = ServiceState.INACTIVE
        self.pid = None
        self.process = None
        self.exit_code = None
        self.start_time = None
        self.stop_time = None
        self.restart_count = 0
        self.restart_timer = None
        self.watchdog_timer = None
        self.watchers = []  # Callbacks for state changes
    
    def start(self) -> Tuple[bool, str]:
        """Start the service"""
        with SERVICE_LOCK:
            if self.state in [ServiceState.ACTIVE, ServiceState.ACTIVATING]:
                return False, f"Service {self.name} is already active or activating"
            
            # Set state to activating
            self._set_state(ServiceState.ACTIVATING)
        
        # Check dependencies
        for dep in self.requires:
            dep_service = ServiceManager.get_service(dep)
            if not dep_service:
                self._set_state(ServiceState.FAILED)
                return False, f"Required dependency {dep} not found"
            
            if dep_service.state != ServiceState.ACTIVE:
                self._set_state(ServiceState.FAILED)
                return False, f"Required dependency {dep} is not active"
        
        # Start command
        if not self.command:
            self._set_state(ServiceState.FAILED)
            return False, f"No command specified for service {self.name}"
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.environment)
            
            # Start process
            if self.type == ServiceType.FORKING:
                # Forking services are started and then detach
                self.process = subprocess.Popen(
                    self.command,
                    shell=True,
                    cwd=self.working_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True
                )
                # We don't track PID for forking services
                self.pid = None
            else:
                # Simple and other services stay attached
                self.process = subprocess.Popen(
                    self.command,
                    shell=True,
                    cwd=self.working_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self.pid = self.process.pid
            
            # Set start time
            self.start_time = time.time()
            self.stop_time = None
            
            # Start monitoring thread for non-forking services
            if self.type != ServiceType.FORKING:
                thread = threading.Thread(target=self._monitor_process)
                thread.daemon = True
                thread.start()
            else:
                # For forking services, we assume they started successfully
                self._set_state(ServiceState.ACTIVE)
            
            # Start watchdog timer if needed
            if self.restart == ServiceRestartPolicy.ON_WATCHDOG:
                self._start_watchdog()
            
            return True, f"Service {self.name} started"
        
        except Exception as e:
            logger.error(f"Error starting service {self.name}: {str(e)}")
            self._set_state(ServiceState.FAILED)
            return False, f"Error starting service: {str(e)}"
    
    def stop(self) -> Tuple[bool, str]:
        """Stop the service"""
        with SERVICE_LOCK:
            if self.state in [ServiceState.INACTIVE, ServiceState.DEACTIVATING]:
                return False, f"Service {self.name} is already inactive or deactivating"
            
            # Set state to deactivating
            self._set_state(ServiceState.DEACTIVATING)
        
        try:
            # Cancel any timers
            if self.restart_timer:
                self.restart_timer.cancel()
                self.restart_timer = None
            
            if self.watchdog_timer:
                self.watchdog_timer.cancel()
                self.watchdog_timer = None
            
            # Stop process
            if self.process and self.process.poll() is None:
                # Try gentle SIGTERM first
                self.process.terminate()
                
                # Wait for process to exit
                try:
                    self.process.wait(timeout=self.timeout_sec)
                except subprocess.TimeoutExpired:
                    # If it doesn't exit, force kill
                    self.process.kill()
            
            # Set stop time
            self.stop_time = time.time()
            
            # Update state
            self._set_state(ServiceState.INACTIVE)
            
            return True, f"Service {self.name} stopped"
        
        except Exception as e:
            logger.error(f"Error stopping service {self.name}: {str(e)}")
            # Even if there's an error, we consider the service stopped
            self._set_state(ServiceState.INACTIVE)
            return False, f"Error stopping service: {str(e)}"
    
    def restart(self) -> Tuple[bool, str]:
        """Restart the service"""
        # Stop service
        success, message = self.stop()
        if not success:
            logger.warning(f"Warning while stopping service for restart: {message}")
        
        # Give it a moment to fully stop
        time.sleep(0.5)
        
        # Start service
        return self.start()
    
    def reload(self) -> Tuple[bool, str]:
        """Reload the service configuration"""
        with SERVICE_LOCK:
            if self.state != ServiceState.ACTIVE:
                return False, f"Service {self.name} is not active"
            
            # Set state to reloading
            self._set_state(ServiceState.RELOADING)
        
        try:
            # If process exists, send SIGHUP
            if self.process and self.process.poll() is None:
                self.process.send_signal(signal.SIGHUP)
            
            # Update state
            self._set_state(ServiceState.ACTIVE)
            
            return True, f"Service {self.name} reloaded"
        
        except Exception as e:
            logger.error(f"Error reloading service {self.name}: {str(e)}")
            self._set_state(ServiceState.ACTIVE)  # Revert to active state
            return False, f"Error reloading service: {str(e)}"
    
    def status(self) -> Dict[str, Any]:
        """Get service status"""
        with SERVICE_LOCK:
            return {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "state": self.state.value,
                "pid": self.pid,
                "uptime": int(time.time() - self.start_time) if self.start_time and not self.stop_time else 0,
                "restart_count": self.restart_count,
                "command": self.command,
                "working_dir": self.working_dir,
                "type": self.type.value,
                "restart": self.restart.value,
                "wants": self.wants,
                "requires": self.requires,
                "after": self.after,
                "before": self.before
            }
    
    def add_watcher(self, callback: Callable[[str, ServiceState], None]) -> None:
        """Add a watcher callback for state changes"""
        self.watchers.append(callback)
    
    def remove_watcher(self, callback: Callable[[str, ServiceState], None]) -> None:
        """Remove a watcher callback"""
        if callback in self.watchers:
            self.watchers.remove(callback)
    
    def _set_state(self, state: ServiceState) -> None:
        """Set service state and notify watchers"""
        old_state = self.state
        self.state = state
        
        # Notify watchers
        for watcher in self.watchers:
            try:
                watcher(self.name, state)
            except Exception as e:
                logger.error(f"Error in service watcher: {str(e)}")
        
        # Log state change
        logger.info(f"Service {self.name} state changed: {old_state.value} -> {state.value}")
    
    def _monitor_process(self) -> None:
        """Monitor process and handle exits"""
        if not self.process:
            return
        
        # Wait for process to exit
        self.exit_code = self.process.wait()
        
        with SERVICE_LOCK:
            # Process has exited
            self.stop_time = time.time()
            self.pid = None
            
            # Handle different exit scenarios
            if self.exit_code == 0:
                # Normal exit
                if self.type == ServiceType.ONESHOT:
                    # OneShot services are meant to exit after completion
                    self._set_state(ServiceState.INACTIVE)
                elif self.restart == ServiceRestartPolicy.ALWAYS or self.restart == ServiceRestartPolicy.ON_SUCCESS:
                    # Schedule restart
                    self._schedule_restart()
                else:
                    self._set_state(ServiceState.INACTIVE)
            else:
                # Abnormal exit
                logger.warning(f"Service {self.name} exited with code {self.exit_code}")
                
                if self.restart in [ServiceRestartPolicy.ALWAYS, ServiceRestartPolicy.ON_FAILURE, 
                                  ServiceRestartPolicy.ON_ABNORMAL, ServiceRestartPolicy.ON_ABORT]:
                    # Schedule restart
                    self._schedule_restart()
                else:
                    self._set_state(ServiceState.FAILED)
    
    def _schedule_restart(self) -> None:
        """Schedule service restart"""
        self._set_state(ServiceState.ACTIVATING)
        self.restart_count += 1
        
        logger.info(f"Scheduling restart of service {self.name} in {self.restart_sec} seconds")
        
        # Cancel any existing timer
        if self.restart_timer:
            self.restart_timer.cancel()
        
        # Schedule restart
        self.restart_timer = threading.Timer(self.restart_sec, self._restart_service)
        self.restart_timer.daemon = True
        self.restart_timer.start()
    
    def _restart_service(self) -> None:
        """Restart service (called by timer)"""
        logger.info(f"Restarting service {self.name}")
        self.start()
    
    def _start_watchdog(self) -> None:
        """Start watchdog timer"""
        # Cancel any existing timer
        if self.watchdog_timer:
            self.watchdog_timer.cancel()
        
        # Schedule watchdog
        self.watchdog_timer = threading.Timer(self.timeout_sec, self._watchdog_timeout)
        self.watchdog_timer.daemon = True
        self.watchdog_timer.start()
    
    def _watchdog_timeout(self) -> None:
        """Handle watchdog timeout"""
        logger.warning(f"Watchdog timeout for service {self.name}")
        
        with SERVICE_LOCK:
            if self.state == ServiceState.ACTIVE:
                # Restart service
                self.restart()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert service to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "working_dir": self.working_dir,
            "environment": self.environment,
            "user": self.user,
            "group": self.group,
            "type": self.type.value,
            "restart": self.restart.value,
            "restart_sec": self.restart_sec,
            "timeout_sec": self.timeout_sec,
            "wants": self.wants,
            "requires": self.requires,
            "after": self.after,
            "before": self.before,
            "state": self.state.value,
            "restart_count": self.restart_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Service':
        """Create service from dictionary"""
        service = cls(
            name=data["name"],
            description=data["description"],
            command=data["command"],
            working_dir=data["working_dir"],
            environment=data["environment"],
            user=data["user"],
            group=data["group"],
            type=ServiceType(data["type"]),
            restart=ServiceRestartPolicy(data["restart"]),
            restart_sec=data["restart_sec"],
            timeout_sec=data["timeout_sec"],
            wants=data["wants"],
            requires=data["requires"],
            after=data["after"],
            before=data["before"]
        )
        
        service.id = data["id"]
        service.state = ServiceState(data["state"])
        service.restart_count = data["restart_count"]
        
        return service

class ServiceManager:
    """Manager for service operations"""
    
    @staticmethod
    def create_service(name: str, description: str = None, command: str = None, 
                      working_dir: str = None, environment: Dict[str, str] = None,
                      user: str = None, group: str = None, 
                      type: str = "simple",
                      restart: str = "no",
                      restart_sec: int = 5, timeout_sec: int = 30,
                      wants: List[str] = None, requires: List[str] = None,
                      after: List[str] = None, before: List[str] = None) -> Tuple[bool, str, Optional[Service]]:
        """Create a new service"""
        # Check if service name already exists
        with SERVICE_LOCK:
            for service in SERVICES.values():
                if service.name == name:
                    return False, f"Service with name '{name}' already exists", None
        
        try:
            # Create service
            service = Service(
                name=name,
                description=description,
                command=command,
                working_dir=working_dir,
                environment=environment,
                user=user,
                group=group,
                type=ServiceType(type),
                restart=ServiceRestartPolicy(restart),
                restart_sec=restart_sec,
                timeout_sec=timeout_sec,
                wants=wants,
                requires=requires,
                after=after,
                before=before
            )
            
            # Add to registry
            with SERVICE_LOCK:
                SERVICES[service.id] = service
            
            return True, f"Service {name} created", service
        
        except Exception as e:
            logger.error(f"Error creating service: {str(e)}")
            return False, f"Error creating service: {str(e)}", None
    
    @staticmethod
    def get_service(id_or_name: str) -> Optional[Service]:
        """Get service by ID or name"""
        with SERVICE_LOCK:
            # Try to find by ID
            if id_or_name in SERVICES:
                return SERVICES[id_or_name]
            
            # Try to find by name
            for service in SERVICES.values():
                if service.name == id_or_name:
                    return service
            
            return None
    
    @staticmethod
    def list_services() -> List[Service]:
        """List all services"""
        with SERVICE_LOCK:
            return list(SERVICES.values())
    
    @staticmethod
    def start_service(id_or_name: str) -> Tuple[bool, str]:
        """Start a service"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found"
        
        return service.start()
    
    @staticmethod
    def stop_service(id_or_name: str) -> Tuple[bool, str]:
        """Stop a service"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found"
        
        return service.stop()
    
    @staticmethod
    def restart_service(id_or_name: str) -> Tuple[bool, str]:
        """Restart a service"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found"
        
        return service.restart()
    
    @staticmethod
    def reload_service(id_or_name: str) -> Tuple[bool, str]:
        """Reload a service"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found"
        
        return service.reload()
    
    @staticmethod
    def status_service(id_or_name: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Get service status"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found", None
        
        return True, "Service status retrieved", service.status()
    
    @staticmethod
    def delete_service(id_or_name: str) -> Tuple[bool, str]:
        """Delete a service"""
        service = ServiceManager.get_service(id_or_name)
        if not service:
            return False, f"Service '{id_or_name}' not found"
        
        # Stop service if running
        if service.state in [ServiceState.ACTIVE, ServiceState.ACTIVATING, ServiceState.RELOADING]:
            service.stop()
        
        # Remove from registry
        with SERVICE_LOCK:
            if service.id in SERVICES:
                del SERVICES[service.id]
        
        return True, f"Service {service.name} deleted"
    
    @staticmethod
    def save_services(filepath: str) -> Tuple[bool, str]:
        """Save services to file"""
        try:
            with SERVICE_LOCK:
                data = {sid: service.to_dict() for sid, service in SERVICES.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Services saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save services: {str(e)}"
    
    @staticmethod
    def load_services(filepath: str) -> Tuple[bool, str]:
        """Load services from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with SERVICE_LOCK:
                # Stop any existing services
                for service in list(SERVICES.values()):
                    service.stop()
                
                # Clear registry
                SERVICES.clear()
                
                # Load services
                for sid, service_data in data.items():
                    SERVICES[sid] = Service.from_dict(service_data)
            
            return True, f"Services loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load services: {str(e)}"

# Initialize service system
def initialize():
    """Initialize the service system"""
    logger.info("Initializing KOS service system")
    
    # Create service directory
    service_dir = os.path.join(os.path.expanduser('~'), '.kos', 'services')
    os.makedirs(service_dir, exist_ok=True)
    
    # Create default services
    if not SERVICES:
        # Create logger service
        ServiceManager.create_service(
            name="kos-logger",
            description="KOS system logger",
            command="echo 'KOS logger started' > /dev/null",
            type="simple",
            restart="always"
        )
    
    # Load services if they exist
    service_db = os.path.join(service_dir, 'services.json')
    if os.path.exists(service_db):
        ServiceManager.load_services(service_db)
    else:
        # Save default services
        ServiceManager.save_services(service_db)
    
    logger.info("KOS service system initialized")

# Initialize on import
initialize()

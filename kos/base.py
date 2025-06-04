"""
KOS Base Module
===============

Core base functionality and system initialization for KOS.
This module provides fundamental classes and utilities that other KOS components depend on.
"""

import os
import sys
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger('KOS.base')

class KOSException(Exception):
    """Base exception class for KOS-specific errors"""
    pass

class SystemState:
    """Manages the overall state of the KOS system"""
    
    def __init__(self):
        self.state = "initializing"
        self.components: Dict[str, Any] = {}
        self.startup_time = datetime.now()
        self.lock = threading.RLock()
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # System paths
        self.kos_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_dir = os.path.expanduser("~/.kos")
        self.data_dir = os.path.join(self.config_dir, "data")
        self.logs_dir = os.path.join(self.config_dir, "logs")
        
        # Ensure directories exist
        for directory in [self.config_dir, self.data_dir, self.logs_dir]:
            os.makedirs(directory, exist_ok=True)
    
    def register_component(self, name: str, component: Any) -> None:
        """Register a system component"""
        with self.lock:
            self.components[name] = component
            logger.debug(f"Registered component: {name}")
    
    def get_component(self, name: str) -> Optional[Any]:
        """Get a registered component"""
        with self.lock:
            return self.components.get(name)
    
    def list_components(self) -> List[str]:
        """List all registered components"""
        with self.lock:
            return list(self.components.keys())
    
    def set_state(self, new_state: str) -> None:
        """Set the system state"""
        with self.lock:
            old_state = self.state
            self.state = new_state
            logger.info(f"System state changed: {old_state} -> {new_state}")
            self._trigger_event("state_change", old_state=old_state, new_state=new_state)
    
    def get_state(self) -> str:
        """Get the current system state"""
        with self.lock:
            return self.state
    
    def is_running(self) -> bool:
        """Check if the system is running"""
        return self.state in ["running", "active"]
    
    def register_event_handler(self, event: str, handler: Callable) -> None:
        """Register an event handler"""
        with self.lock:
            if event not in self.event_handlers:
                self.event_handlers[event] = []
            self.event_handlers[event].append(handler)
    
    def _trigger_event(self, event: str, **kwargs) -> None:
        """Trigger event handlers"""
        handlers = self.event_handlers.get(event, [])
        for handler in handlers:
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in event handler for {event}: {e}")
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return (datetime.now() - self.startup_time).total_seconds()
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        return {
            "state": self.state,
            "uptime": self.get_uptime(),
            "startup_time": self.startup_time.isoformat(),
            "components": list(self.components.keys()),
            "kos_root": self.kos_root,
            "config_dir": self.config_dir,
            "python_version": sys.version,
            "platform": sys.platform
        }

class ComponentBase:
    """Base class for KOS components"""
    
    def __init__(self, name: str):
        self.name = name
        self.initialized = False
        self.enabled = True
        self.dependencies: List[str] = []
        self.logger = logging.getLogger(f'KOS.{name}')
        self.config: Dict[str, Any] = {}
    
    def initialize(self) -> bool:
        """Initialize the component"""
        try:
            if self.initialized:
                self.logger.warning(f"Component {self.name} already initialized")
                return True
            
            self.logger.info(f"Initializing component: {self.name}")
            
            # Check dependencies
            if not self._check_dependencies():
                self.logger.error(f"Dependencies not satisfied for {self.name}")
                return False
            
            # Perform initialization
            if not self._do_initialize():
                self.logger.error(f"Initialization failed for {self.name}")
                return False
            
            self.initialized = True
            self.logger.info(f"Component {self.name} initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing {self.name}: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the component"""
        try:
            if not self.initialized:
                return True
            
            self.logger.info(f"Shutting down component: {self.name}")
            
            if not self._do_shutdown():
                self.logger.error(f"Shutdown failed for {self.name}")
                return False
            
            self.initialized = False
            self.logger.info(f"Component {self.name} shut down successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error shutting down {self.name}: {e}")
            return False
    
    def _check_dependencies(self) -> bool:
        """Check if dependencies are satisfied"""
        system_state = get_system_state()
        for dep in self.dependencies:
            if not system_state.get_component(dep):
                self.logger.error(f"Dependency not available: {dep}")
                return False
        return True
    
    def _do_initialize(self) -> bool:
        """Override in subclasses to perform actual initialization"""
        return True
    
    def _do_shutdown(self) -> bool:
        """Override in subclasses to perform actual shutdown"""
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get component status"""
        return {
            "name": self.name,
            "initialized": self.initialized,
            "enabled": self.enabled,
            "dependencies": self.dependencies
        }

class ServiceManager:
    """Manages system services and components"""
    
    def __init__(self):
        self.services: Dict[str, ComponentBase] = {}
        self.startup_order: List[str] = []
        self.shutdown_order: List[str] = []
        self.lock = threading.RLock()
    
    def register_service(self, service: ComponentBase) -> bool:
        """Register a service"""
        with self.lock:
            if service.name in self.services:
                logger.warning(f"Service {service.name} already registered")
                return False
            
            self.services[service.name] = service
            logger.info(f"Registered service: {service.name}")
            return True
    
    def unregister_service(self, name: str) -> bool:
        """Unregister a service"""
        with self.lock:
            if name not in self.services:
                logger.warning(f"Service {name} not registered")
                return False
            
            service = self.services[name]
            if service.initialized:
                service.shutdown()
            
            del self.services[name]
            logger.info(f"Unregistered service: {name}")
            return True
    
    def start_service(self, name: str) -> bool:
        """Start a specific service"""
        with self.lock:
            if name not in self.services:
                logger.error(f"Service {name} not found")
                return False
            
            service = self.services[name]
            return service.initialize()
    
    def stop_service(self, name: str) -> bool:
        """Stop a specific service"""
        with self.lock:
            if name not in self.services:
                logger.error(f"Service {name} not found")
                return False
            
            service = self.services[name]
            return service.shutdown()
    
    def start_all_services(self) -> bool:
        """Start all registered services"""
        with self.lock:
            success = True
            
            # Determine startup order based on dependencies
            ordered_services = self._get_startup_order()
            
            for service_name in ordered_services:
                if not self.start_service(service_name):
                    logger.error(f"Failed to start service: {service_name}")
                    success = False
                    break
            
            return success
    
    def stop_all_services(self) -> bool:
        """Stop all running services"""
        with self.lock:
            success = True
            
            # Shutdown in reverse order
            ordered_services = list(reversed(self._get_startup_order()))
            
            for service_name in ordered_services:
                service = self.services.get(service_name)
                if service and service.initialized:
                    if not self.stop_service(service_name):
                        logger.error(f"Failed to stop service: {service_name}")
                        success = False
            
            return success
    
    def _get_startup_order(self) -> List[str]:
        """Determine service startup order based on dependencies"""
        # Simple topological sort
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service_name: str):
            if service_name in temp_visited:
                raise KOSException(f"Circular dependency detected involving {service_name}")
            
            if service_name in visited:
                return
            
            temp_visited.add(service_name)
            
            service = self.services.get(service_name)
            if service:
                for dep in service.dependencies:
                    if dep in self.services:
                        visit(dep)
            
            temp_visited.remove(service_name)
            visited.add(service_name)
            order.append(service_name)
        
        for service_name in self.services:
            if service_name not in visited:
                visit(service_name)
        
        return order
    
    def get_service_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all services"""
        with self.lock:
            status = {}
            for name, service in self.services.items():
                status[name] = service.get_status()
            return status
    
    def list_services(self) -> List[str]:
        """List all registered services"""
        with self.lock:
            return list(self.services.keys())

class ConfigManager:
    """Manages system configuration"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.kos")
        self.config_file = os.path.join(self.config_dir, "kos.conf")
        self.config: Dict[str, Any] = {}
        self.lock = threading.RLock()
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load configuration
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_file):
                import json
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info("Configuration loaded successfully")
            else:
                # Create default configuration
                self.config = self._get_default_config()
                self.save_config()
                logger.info("Default configuration created")
            return True
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config = self._get_default_config()
            return False
    
    def save_config(self) -> bool:
        """Save configuration to file"""
        try:
            import json
            with self.lock:
                with open(self.config_file, 'w') as f:
                    json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        with self.lock:
            keys = key.split('.')
            value = self.config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        with self.lock:
            keys = key.split('.')
            config = self.config
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            config[keys[-1]] = value
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            "system": {
                "name": "KOS",
                "version": "1.0.0",
                "debug": False,
                "log_level": "INFO"
            },
            "paths": {
                "data_dir": os.path.join(self.config_dir, "data"),
                "logs_dir": os.path.join(self.config_dir, "logs"),
                "apps_dir": os.path.join(self.config_dir, "apps")
            },
            "security": {
                "enable_firewall": True,
                "enable_audit": True,
                "secure_by_default": True
            },
            "networking": {
                "enable_ipv6": True,
                "dns_servers": ["8.8.8.8", "8.8.4.4"]
            }
        }

# Global instances
_system_state: Optional[SystemState] = None
_service_manager: Optional[ServiceManager] = None
_config_manager: Optional[ConfigManager] = None

def get_system_state() -> SystemState:
    """Get the global system state instance"""
    global _system_state
    if _system_state is None:
        _system_state = SystemState()
    return _system_state

def get_service_manager() -> ServiceManager:
    """Get the global service manager instance"""
    global _service_manager
    if _service_manager is None:
        _service_manager = ServiceManager()
    return _service_manager

def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def initialize_kos() -> bool:
    """Initialize the KOS base system"""
    try:
        logger.info("Initializing KOS base system...")
        
        # Initialize components
        system_state = get_system_state()
        service_manager = get_service_manager()
        config_manager = get_config_manager()
        
        # Register core components
        system_state.register_component("service_manager", service_manager)
        system_state.register_component("config_manager", config_manager)
        
        # Set system state
        system_state.set_state("initialized")
        
        logger.info("KOS base system initialized successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error initializing KOS base system: {e}")
        return False

def shutdown_kos() -> bool:
    """Shutdown the KOS base system"""
    try:
        logger.info("Shutting down KOS base system...")
        
        # Stop all services
        service_manager = get_service_manager()
        service_manager.stop_all_services()
        
        # Set system state
        system_state = get_system_state()
        system_state.set_state("shutdown")
        
        logger.info("KOS base system shut down successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error shutting down KOS base system: {e}")
        return False

# Auto-initialize when module is imported
if not get_system_state().is_running():
    initialize_kos()

# Export main classes and functions
__all__ = [
    'KOSException', 'SystemState', 'ComponentBase', 'ServiceManager', 
    'ConfigManager', 'get_system_state', 'get_service_manager', 
    'get_config_manager', 'initialize_kos', 'shutdown_kos'
]
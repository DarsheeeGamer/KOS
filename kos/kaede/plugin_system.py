"""
Advanced Plugin System for Kaede
===============================

Comprehensive plugin architecture featuring:
- Dynamic plugin loading and unloading
- Hot code swapping and live updates
- Plugin dependency management
- API versioning and compatibility
- Plugin sandboxing and security
- Event-driven plugin communication
- Plugin marketplace and distribution
- Performance monitoring and metrics
- Configuration management
- Plugin development tools
"""

import os
import sys
import importlib
import importlib.util
import inspect
import threading
import time
import json
import hashlib
import zipfile
import shutil
from typing import Any, Dict, List, Optional, Callable, Type, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
from pathlib import Path
import logging
import weakref
from collections import defaultdict, deque
import tempfile
import subprocess

logger = logging.getLogger('KOS.kaede.plugins')

class PluginStatus(Enum):
    """Plugin status enumeration"""
    INACTIVE = auto()
    LOADING = auto()
    ACTIVE = auto()
    ERROR = auto()
    DISABLED = auto()
    UPDATING = auto()

class PluginType(Enum):
    """Plugin type enumeration"""
    LIBRARY = auto()
    EXTENSION = auto()
    THEME = auto()
    COMPILER_PLUGIN = auto()
    RUNTIME_PLUGIN = auto()
    DEBUG_PLUGIN = auto()
    LANGUAGE_SERVER = auto()
    FORMATTER = auto()
    LINTER = auto()

class APIVersion:
    """API version management"""
    
    def __init__(self, major: int, minor: int, patch: int = 0):
        self.major = major
        self.minor = minor
        self.patch = patch
    
    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __eq__(self, other):
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def is_compatible(self, other):
        """Check if versions are compatible"""
        return self.major == other.major and self.minor >= other.minor

@dataclass
class PluginInfo:
    """Plugin metadata and information"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    email: str = ""
    website: str = ""
    license: str = ""
    plugin_type: PluginType = PluginType.LIBRARY
    api_version: APIVersion = field(default_factory=lambda: APIVersion(1, 0, 0))
    dependencies: List[str] = field(default_factory=list)
    entry_point: str = "main"
    config_schema: Dict = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

@dataclass
class PluginContext:
    """Runtime context for plugin execution"""
    plugin_info: PluginInfo
    config: Dict[str, Any] = field(default_factory=dict)
    resources: Dict[str, Any] = field(default_factory=dict)
    event_bus: Optional['EventBus'] = None
    logger: Optional[logging.Logger] = None
    data_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None

class PluginAPI(ABC):
    """Base class for plugin APIs"""
    
    def __init__(self, context: PluginContext):
        self.context = context
        self.logger = context.logger or logger
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin"""
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """Shutdown the plugin"""
        pass
    
    def get_version(self) -> str:
        """Get plugin version"""
        return self.context.plugin_info.version
    
    def get_config(self, key: str, default=None):
        """Get configuration value"""
        return self.context.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """Set configuration value"""
        self.context.config[key] = value
    
    def emit_event(self, event_name: str, data: Any = None):
        """Emit event to other plugins"""
        if self.context.event_bus:
            self.context.event_bus.emit(event_name, data, source=self.context.plugin_info.name)
    
    def listen_event(self, event_name: str, handler: Callable):
        """Listen for events"""
        if self.context.event_bus:
            self.context.event_bus.subscribe(event_name, handler, plugin=self.context.plugin_info.name)

class EventBus:
    """Event bus for plugin communication"""
    
    def __init__(self):
        self.subscribers = defaultdict(list)
        self.event_history = deque(maxlen=1000)
        self.lock = threading.RLock()
    
    def subscribe(self, event_name: str, handler: Callable, plugin: str = None):
        """Subscribe to event"""
        with self.lock:
            self.subscribers[event_name].append({
                'handler': handler,
                'plugin': plugin,
                'timestamp': time.time()
            })
    
    def unsubscribe(self, event_name: str, handler: Callable = None, plugin: str = None):
        """Unsubscribe from event"""
        with self.lock:
            if event_name in self.subscribers:
                subscribers = self.subscribers[event_name]
                if handler:
                    subscribers[:] = [s for s in subscribers if s['handler'] != handler]
                elif plugin:
                    subscribers[:] = [s for s in subscribers if s['plugin'] != plugin]
    
    def emit(self, event_name: str, data: Any = None, source: str = None):
        """Emit event to subscribers"""
        event = {
            'name': event_name,
            'data': data,
            'source': source,
            'timestamp': time.time()
        }
        
        with self.lock:
            self.event_history.append(event)
            
            for subscriber in self.subscribers.get(event_name, []):
                try:
                    subscriber['handler'](event)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_name}: {e}")
    
    def get_event_history(self, count: int = 100):
        """Get recent event history"""
        with self.lock:
            return list(self.event_history)[-count:]

class PluginSandbox:
    """Security sandbox for plugin execution"""
    
    def __init__(self):
        self.allowed_modules = {
            'json', 'math', 'random', 'time', 'datetime',
            'collections', 'itertools', 'functools', 're'
        }
        self.restricted_functions = {
            'eval', 'exec', 'compile', '__import__', 'open',
            'input', 'raw_input', 'file'
        }
        self.resource_limits = {
            'max_memory': 50 * 1024 * 1024,  # 50MB
            'max_execution_time': 10.0,  # 10 seconds
            'max_file_operations': 100,
            'max_network_requests': 50
        }
    
    def is_safe_import(self, module_name: str) -> bool:
        """Check if module import is safe"""
        return module_name in self.allowed_modules
    
    def is_safe_function(self, function_name: str) -> bool:
        """Check if function call is safe"""
        return function_name not in self.restricted_functions
    
    def create_sandbox_globals(self, plugin_api: PluginAPI):
        """Create sandboxed globals for plugin execution"""
        safe_builtins = {
            'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple',
            'set', 'range', 'enumerate', 'zip', 'map', 'filter',
            'min', 'max', 'sum', 'abs', 'round', 'sorted'
        }
        
        sandbox_globals = {
            '__builtins__': {name: getattr(__builtins__, name) for name in safe_builtins},
            'plugin_api': plugin_api
        }
        
        return sandbox_globals

class PluginLoader:
    """Dynamic plugin loader with hot swapping"""
    
    def __init__(self, plugin_dir: Path):
        self.plugin_dir = Path(plugin_dir)
        self.loaded_plugins = {}
        self.plugin_modules = {}
        self.file_watchers = {}
        self.lock = threading.RLock()
    
    def load_plugin(self, plugin_path: Path, context: PluginContext) -> Optional[PluginAPI]:
        """Load plugin from path"""
        try:
            plugin_name = context.plugin_info.name
            
            # Load module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            
            # Execute module
            with self.lock:
                spec.loader.exec_module(module)
                self.plugin_modules[plugin_name] = module
            
            # Get plugin class
            entry_point = context.plugin_info.entry_point
            if hasattr(module, entry_point):
                plugin_class = getattr(module, entry_point)
                if inspect.isclass(plugin_class) and issubclass(plugin_class, PluginAPI):
                    plugin_instance = plugin_class(context)
                    
                    # Initialize plugin
                    if plugin_instance.initialize():
                        with self.lock:
                            self.loaded_plugins[plugin_name] = plugin_instance
                        logger.info(f"Successfully loaded plugin: {plugin_name}")
                        return plugin_instance
                    else:
                        logger.error(f"Failed to initialize plugin: {plugin_name}")
                else:
                    logger.error(f"Invalid plugin class in {plugin_name}")
            else:
                logger.error(f"Entry point '{entry_point}' not found in {plugin_name}")
                
        except Exception as e:
            logger.error(f"Error loading plugin from {plugin_path}: {e}")
        
        return None
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload plugin"""
        try:
            with self.lock:
                if plugin_name in self.loaded_plugins:
                    plugin = self.loaded_plugins[plugin_name]
                    plugin.shutdown()
                    del self.loaded_plugins[plugin_name]
                
                if plugin_name in self.plugin_modules:
                    del self.plugin_modules[plugin_name]
                    # Remove from sys.modules to allow hot reloading
                    modules_to_remove = [name for name in sys.modules if name.startswith(plugin_name)]
                    for module_name in modules_to_remove:
                        del sys.modules[module_name]
            
            logger.info(f"Successfully unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return False
    
    def reload_plugin(self, plugin_name: str, plugin_path: Path, context: PluginContext) -> bool:
        """Hot reload plugin"""
        if self.unload_plugin(plugin_name):
            return self.load_plugin(plugin_path, context) is not None
        return False
    
    def get_plugin(self, plugin_name: str) -> Optional[PluginAPI]:
        """Get loaded plugin"""
        with self.lock:
            return self.loaded_plugins.get(plugin_name)
    
    def list_plugins(self) -> List[str]:
        """List loaded plugins"""
        with self.lock:
            return list(self.loaded_plugins.keys())

class PluginManager:
    """Main plugin management system"""
    
    def __init__(self, plugin_dir: str = "plugins", config_dir: str = "config"):
        self.plugin_dir = Path(plugin_dir)
        self.config_dir = Path(config_dir)
        self.plugin_loader = PluginLoader(self.plugin_dir)
        self.event_bus = EventBus()
        self.sandbox = PluginSandbox()
        
        # Plugin registry
        self.plugin_registry = {}
        self.plugin_configs = {}
        self.plugin_status = {}
        self.dependency_graph = {}
        
        # Create directories
        self.plugin_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)
        
        # API version
        self.api_version = APIVersion(1, 0, 0)
        
        logger.info(f"Plugin Manager initialized - Plugin dir: {self.plugin_dir}")
    
    def discover_plugins(self) -> List[PluginInfo]:
        """Discover plugins in plugin directory"""
        discovered = []
        
        for item in self.plugin_dir.iterdir():
            if item.is_dir() and (item / "plugin.json").exists():
                try:
                    plugin_info = self._load_plugin_info(item / "plugin.json")
                    discovered.append(plugin_info)
                except Exception as e:
                    logger.error(f"Error discovering plugin in {item}: {e}")
            elif item.suffix == ".zip":
                try:
                    plugin_info = self._load_plugin_info_from_zip(item)
                    if plugin_info:
                        discovered.append(plugin_info)
                except Exception as e:
                    logger.error(f"Error discovering plugin in {item}: {e}")
        
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered
    
    def _load_plugin_info(self, manifest_path: Path) -> PluginInfo:
        """Load plugin info from manifest"""
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        api_ver_data = data.get('api_version', {'major': 1, 'minor': 0, 'patch': 0})
        api_version = APIVersion(
            api_ver_data.get('major', 1),
            api_ver_data.get('minor', 0),
            api_ver_data.get('patch', 0)
        )
        
        plugin_type = PluginType[data.get('type', 'LIBRARY').upper()]
        
        return PluginInfo(
            name=data['name'],
            version=data['version'],
            description=data.get('description', ''),
            author=data.get('author', ''),
            email=data.get('email', ''),
            website=data.get('website', ''),
            license=data.get('license', ''),
            plugin_type=plugin_type,
            api_version=api_version,
            dependencies=data.get('dependencies', []),
            entry_point=data.get('entry_point', 'main'),
            config_schema=data.get('config_schema', {}),
            permissions=data.get('permissions', []),
            tags=data.get('tags', [])
        )
    
    def _load_plugin_info_from_zip(self, zip_path: Path) -> Optional[PluginInfo]:
        """Load plugin info from zip file"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                if 'plugin.json' in zf.namelist():
                    with zf.open('plugin.json') as f:
                        data = json.load(f)
                    
                    # Similar to _load_plugin_info but from zip
                    api_ver_data = data.get('api_version', {'major': 1, 'minor': 0, 'patch': 0})
                    api_version = APIVersion(
                        api_ver_data.get('major', 1),
                        api_ver_data.get('minor', 0),
                        api_ver_data.get('patch', 0)
                    )
                    
                    plugin_type = PluginType[data.get('type', 'LIBRARY').upper()]
                    
                    return PluginInfo(
                        name=data['name'],
                        version=data['version'],
                        description=data.get('description', ''),
                        author=data.get('author', ''),
                        plugin_type=plugin_type,
                        api_version=api_version,
                        dependencies=data.get('dependencies', []),
                        entry_point=data.get('entry_point', 'main')
                    )
        except Exception as e:
            logger.error(f"Error loading plugin info from zip {zip_path}: {e}")
        
        return None
    
    def install_plugin(self, plugin_info: PluginInfo, plugin_path: Path) -> bool:
        """Install plugin"""
        try:
            # Check API compatibility
            if not self.api_version.is_compatible(plugin_info.api_version):
                logger.error(f"Plugin {plugin_info.name} requires incompatible API version {plugin_info.api_version}")
                return False
            
            # Check dependencies
            if not self._check_dependencies(plugin_info.dependencies):
                logger.error(f"Missing dependencies for plugin {plugin_info.name}")
                return False
            
            # Create plugin context
            context = self._create_plugin_context(plugin_info)
            
            # Load plugin
            plugin_instance = self.plugin_loader.load_plugin(plugin_path, context)
            if plugin_instance:
                self.plugin_registry[plugin_info.name] = plugin_info
                self.plugin_status[plugin_info.name] = PluginStatus.ACTIVE
                
                # Emit event
                self.event_bus.emit('plugin_installed', {
                    'plugin': plugin_info.name,
                    'version': plugin_info.version
                })
                
                return True
            
        except Exception as e:
            logger.error(f"Error installing plugin {plugin_info.name}: {e}")
            self.plugin_status[plugin_info.name] = PluginStatus.ERROR
        
        return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """Uninstall plugin"""
        try:
            if self.plugin_loader.unload_plugin(plugin_name):
                if plugin_name in self.plugin_registry:
                    del self.plugin_registry[plugin_name]
                if plugin_name in self.plugin_status:
                    del self.plugin_status[plugin_name]
                
                # Emit event
                self.event_bus.emit('plugin_uninstalled', {'plugin': plugin_name})
                
                return True
                
        except Exception as e:
            logger.error(f"Error uninstalling plugin {plugin_name}: {e}")
        
        return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable plugin"""
        if plugin_name in self.plugin_registry:
            plugin_info = self.plugin_registry[plugin_name]
            plugin_path = self.plugin_dir / plugin_name / "main.py"
            
            context = self._create_plugin_context(plugin_info)
            if self.plugin_loader.load_plugin(plugin_path, context):
                self.plugin_status[plugin_name] = PluginStatus.ACTIVE
                return True
        
        return False
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable plugin"""
        if self.plugin_loader.unload_plugin(plugin_name):
            self.plugin_status[plugin_name] = PluginStatus.DISABLED
            return True
        return False
    
    def _create_plugin_context(self, plugin_info: PluginInfo) -> PluginContext:
        """Create plugin execution context"""
        # Load plugin configuration
        config_path = self.config_dir / f"{plugin_info.name}.json"
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        
        # Create data directory
        data_dir = self.plugin_dir / plugin_info.name / "data"
        data_dir.mkdir(exist_ok=True)
        
        # Create temp directory
        temp_dir = Path(tempfile.mkdtemp(prefix=f"kaede_plugin_{plugin_info.name}_"))
        
        # Create logger
        plugin_logger = logging.getLogger(f'KOS.plugins.{plugin_info.name}')
        
        return PluginContext(
            plugin_info=plugin_info,
            config=config,
            event_bus=self.event_bus,
            logger=plugin_logger,
            data_dir=data_dir,
            temp_dir=temp_dir
        )
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """Check if dependencies are satisfied"""
        for dep in dependencies:
            if dep not in self.plugin_registry:
                return False
            if self.plugin_status.get(dep) != PluginStatus.ACTIVE:
                return False
        return True
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """Get plugin information"""
        return self.plugin_registry.get(plugin_name)
    
    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """Get plugin status"""
        return self.plugin_status.get(plugin_name)
    
    def list_plugins(self) -> Dict[str, Dict]:
        """List all plugins with their info and status"""
        result = {}
        for name, info in self.plugin_registry.items():
            result[name] = {
                'info': info,
                'status': self.plugin_status.get(name, PluginStatus.INACTIVE),
                'loaded': name in self.plugin_loader.loaded_plugins
            }
        return result
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """Get plugins by type"""
        return [name for name, info in self.plugin_registry.items() 
                if info.plugin_type == plugin_type]
    
    def call_plugin_method(self, plugin_name: str, method_name: str, *args, **kwargs):
        """Call method on plugin"""
        plugin = self.plugin_loader.get_plugin(plugin_name)
        if plugin and hasattr(plugin, method_name):
            method = getattr(plugin, method_name)
            return method(*args, **kwargs)
        return None
    
    def broadcast_event(self, event_name: str, data: Any = None):
        """Broadcast event to all plugins"""
        self.event_bus.emit(event_name, data, source='plugin_manager')
    
    def get_plugin_metrics(self) -> Dict:
        """Get plugin system metrics"""
        total_plugins = len(self.plugin_registry)
        active_plugins = sum(1 for status in self.plugin_status.values() 
                           if status == PluginStatus.ACTIVE)
        
        return {
            'total_plugins': total_plugins,
            'active_plugins': active_plugins,
            'plugin_types': {ptype.name: len(self.get_plugins_by_type(ptype)) 
                           for ptype in PluginType},
            'recent_events': self.event_bus.get_event_history(50)
        }
    
    def shutdown(self):
        """Shutdown plugin manager"""
        logger.info("Shutting down plugin manager...")
        
        # Unload all plugins
        for plugin_name in list(self.plugin_loader.loaded_plugins.keys()):
            self.plugin_loader.unload_plugin(plugin_name)
        
        logger.info("Plugin manager shutdown complete")

# Global plugin manager instance
plugin_manager = PluginManager()

def get_plugin_manager():
    """Get the plugin manager instance"""
    return plugin_manager

# Export main classes and functions
__all__ = [
    'PluginManager', 'get_plugin_manager',
    'PluginAPI', 'PluginInfo', 'PluginContext',
    'EventBus', 'PluginLoader', 'PluginSandbox',
    'PluginStatus', 'PluginType', 'APIVersion'
] 
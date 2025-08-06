"""
Application framework for KOS apps
"""

import time
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

class AppState(Enum):
    """Application states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    CRASHED = "crashed"

@dataclass
class AppManifest:
    """Application manifest"""
    app_id: str
    name: str
    version: str
    author: str
    description: str
    main: str  # Main module/entry point
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    resources: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AppManifest':
        """Create from JSON string"""
        data = json.loads(json_str)
        return cls(**data)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps({
            'app_id': self.app_id,
            'name': self.name,
            'version': self.version,
            'author': self.author,
            'description': self.description,
            'main': self.main,
            'dependencies': self.dependencies,
            'permissions': self.permissions,
            'resources': self.resources
        })

class Application(ABC):
    """Base application class"""
    
    def __init__(self, manifest: AppManifest):
        self.manifest = manifest
        self.state = AppState.STOPPED
        self.context: Optional['AppContext'] = None
        self.config: Dict[str, Any] = {}
        self.data: Dict[str, Any] = {}
        
    @abstractmethod
    def on_start(self) -> bool:
        """Called when application starts"""
        pass
    
    @abstractmethod
    def on_stop(self) -> bool:
        """Called when application stops"""
        pass
    
    def on_pause(self):
        """Called when application is paused"""
        pass
    
    def on_resume(self):
        """Called when application is resumed"""
        pass
    
    def on_message(self, message: Dict[str, Any]):
        """Handle inter-app messages"""
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value
        if self.context:
            self.context.save_config(self.manifest.app_id, self.config)
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get application data"""
        return self.data.get(key, default)
    
    def set_data(self, key: str, value: Any):
        """Set application data"""
        self.data[key] = value
        if self.context:
            self.context.save_data(self.manifest.app_id, self.data)

@dataclass
class AppContext:
    """Application execution context"""
    vfs: Any
    auth: Any
    executor: Any
    config_dir: str = "/var/apps/config"
    data_dir: str = "/var/apps/data"
    
    def save_config(self, app_id: str, config: Dict[str, Any]) -> bool:
        """Save application configuration"""
        if not self.vfs:
            return False
        
        config_file = f"{self.config_dir}/{app_id}.json"
        
        try:
            with self.vfs.open(config_file, 'w') as f:
                f.write(json.dumps(config).encode())
            return True
        except:
            return False
    
    def load_config(self, app_id: str) -> Dict[str, Any]:
        """Load application configuration"""
        if not self.vfs:
            return {}
        
        config_file = f"{self.config_dir}/{app_id}.json"
        
        if not self.vfs.exists(config_file):
            return {}
        
        try:
            with self.vfs.open(config_file, 'r') as f:
                return json.loads(f.read().decode())
        except:
            return {}
    
    def save_data(self, app_id: str, data: Dict[str, Any]) -> bool:
        """Save application data"""
        if not self.vfs:
            return False
        
        data_file = f"{self.data_dir}/{app_id}.json"
        
        try:
            with self.vfs.open(data_file, 'w') as f:
                f.write(json.dumps(data).encode())
            return True
        except:
            return False
    
    def load_data(self, app_id: str) -> Dict[str, Any]:
        """Load application data"""
        if not self.vfs:
            return {}
        
        data_file = f"{self.data_dir}/{app_id}.json"
        
        if not self.vfs.exists(data_file):
            return {}
        
        try:
            with self.vfs.open(data_file, 'r') as f:
                return json.loads(f.read().decode())
        except:
            return {}

class AppManager:
    """Application manager"""
    
    def __init__(self, context: AppContext):
        self.context = context
        self.apps: Dict[str, Application] = {}
        self.running_apps: Dict[str, Application] = {}
        self.app_dir = "/var/apps"
        
        self._init_app_system()
    
    def _init_app_system(self):
        """Initialize application system"""
        if not self.context.vfs:
            return
        
        # Create app directories
        dirs = [
            self.app_dir,
            f"{self.app_dir}/installed",
            f"{self.app_dir}/config",
            f"{self.app_dir}/data",
            f"{self.app_dir}/logs"
        ]
        
        for dir_path in dirs:
            if not self.context.vfs.exists(dir_path):
                try:
                    self.context.vfs.mkdir(dir_path)
                except:
                    pass
    
    def install_app(self, manifest: AppManifest, app_class: type) -> bool:
        """Install application"""
        # Check dependencies
        for dep in manifest.dependencies:
            if dep not in self.apps:
                return False  # Dependency not met
        
        # Create app instance
        app = app_class(manifest)
        app.context = self.context
        
        # Load saved config and data
        app.config = self.context.load_config(manifest.app_id)
        app.data = self.context.load_data(manifest.app_id)
        
        # Register app
        self.apps[manifest.app_id] = app
        
        # Save manifest
        self._save_manifest(manifest)
        
        return True
    
    def uninstall_app(self, app_id: str) -> bool:
        """Uninstall application"""
        if app_id not in self.apps:
            return False
        
        # Stop app if running
        if app_id in self.running_apps:
            self.stop_app(app_id)
        
        # Remove app
        del self.apps[app_id]
        
        # Remove manifest
        manifest_file = f"{self.app_dir}/installed/{app_id}.manifest"
        if self.context.vfs and self.context.vfs.exists(manifest_file):
            try:
                self.context.vfs.remove(manifest_file)
            except:
                pass
        
        return True
    
    def start_app(self, app_id: str) -> bool:
        """Start application"""
        if app_id not in self.apps:
            return False
        
        if app_id in self.running_apps:
            return True  # Already running
        
        app = self.apps[app_id]
        
        # Check permissions
        if not self._check_permissions(app):
            return False
        
        # Start app
        app.state = AppState.STARTING
        
        try:
            if app.on_start():
                app.state = AppState.RUNNING
                self.running_apps[app_id] = app
                return True
            else:
                app.state = AppState.STOPPED
                return False
        except Exception as e:
            app.state = AppState.CRASHED
            print(f"App {app_id} crashed: {e}")
            return False
    
    def stop_app(self, app_id: str) -> bool:
        """Stop application"""
        if app_id not in self.running_apps:
            return False
        
        app = self.running_apps[app_id]
        app.state = AppState.STOPPING
        
        try:
            if app.on_stop():
                app.state = AppState.STOPPED
                del self.running_apps[app_id]
                return True
            else:
                app.state = AppState.RUNNING
                return False
        except:
            # Force stop
            app.state = AppState.STOPPED
            del self.running_apps[app_id]
            return True
    
    def pause_app(self, app_id: str) -> bool:
        """Pause application"""
        if app_id not in self.running_apps:
            return False
        
        app = self.running_apps[app_id]
        
        if app.state != AppState.RUNNING:
            return False
        
        app.on_pause()
        app.state = AppState.PAUSED
        return True
    
    def resume_app(self, app_id: str) -> bool:
        """Resume application"""
        if app_id not in self.running_apps:
            return False
        
        app = self.running_apps[app_id]
        
        if app.state != AppState.PAUSED:
            return False
        
        app.on_resume()
        app.state = AppState.RUNNING
        return True
    
    def send_message(self, to_app: str, message: Dict[str, Any]) -> bool:
        """Send message to application"""
        if to_app not in self.running_apps:
            return False
        
        app = self.running_apps[to_app]
        app.on_message(message)
        return True
    
    def list_apps(self) -> List[AppManifest]:
        """List installed applications"""
        return [app.manifest for app in self.apps.values()]
    
    def list_running_apps(self) -> List[str]:
        """List running applications"""
        return list(self.running_apps.keys())
    
    def get_app_info(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Get application information"""
        if app_id not in self.apps:
            return None
        
        app = self.apps[app_id]
        
        return {
            'manifest': app.manifest.__dict__,
            'state': app.state.value,
            'config': app.config,
            'running': app_id in self.running_apps
        }
    
    def _check_permissions(self, app: Application) -> bool:
        """Check application permissions"""
        # Would check against system permissions
        # For now, allow all
        return True
    
    def _save_manifest(self, manifest: AppManifest):
        """Save application manifest"""
        if not self.context.vfs:
            return
        
        manifest_file = f"{self.app_dir}/installed/{manifest.app_id}.manifest"
        
        try:
            with self.context.vfs.open(manifest_file, 'w') as f:
                f.write(manifest.to_json().encode())
        except:
            pass

# Example Applications

class CalculatorApp(Application):
    """Simple calculator application"""
    
    def on_start(self) -> bool:
        print(f"Calculator {self.manifest.version} started")
        return True
    
    def on_stop(self) -> bool:
        print("Calculator stopped")
        return True
    
    def calculate(self, expression: str) -> float:
        """Calculate expression"""
        try:
            # Simple eval (in production, use safe parser)
            return eval(expression)
        except:
            return 0.0

class TextEditorApp(Application):
    """Text editor application"""
    
    def __init__(self, manifest: AppManifest):
        super().__init__(manifest)
        self.current_file = None
        self.content = ""
    
    def on_start(self) -> bool:
        print(f"Text Editor {self.manifest.version} started")
        return True
    
    def on_stop(self) -> bool:
        # Save any unsaved changes
        if self.current_file and self.content:
            self.save_file()
        print("Text Editor stopped")
        return True
    
    def open_file(self, filepath: str) -> bool:
        """Open file for editing"""
        if not self.context or not self.context.vfs:
            return False
        
        try:
            with self.context.vfs.open(filepath, 'r') as f:
                self.content = f.read().decode()
            self.current_file = filepath
            return True
        except:
            return False
    
    def save_file(self) -> bool:
        """Save current file"""
        if not self.current_file or not self.context or not self.context.vfs:
            return False
        
        try:
            with self.context.vfs.open(self.current_file, 'w') as f:
                f.write(self.content.encode())
            return True
        except:
            return False

class FileManagerApp(Application):
    """File manager application"""
    
    def __init__(self, manifest: AppManifest):
        super().__init__(manifest)
        self.current_dir = "/"
    
    def on_start(self) -> bool:
        print(f"File Manager {self.manifest.version} started")
        return True
    
    def on_stop(self) -> bool:
        print("File Manager stopped")
        return True
    
    def list_files(self, path: str = None) -> List[Dict[str, Any]]:
        """List files in directory"""
        if not self.context or not self.context.vfs:
            return []
        
        path = path or self.current_dir
        
        try:
            items = []
            for name in self.context.vfs.listdir(path):
                item_path = f"{path}/{name}".replace('//', '/')
                is_dir = self.context.vfs.isdir(item_path)
                
                items.append({
                    'name': name,
                    'path': item_path,
                    'is_dir': is_dir,
                    'size': 0 if is_dir else self._get_file_size(item_path)
                })
            
            return items
        except:
            return []
    
    def _get_file_size(self, filepath: str) -> int:
        """Get file size"""
        try:
            with self.context.vfs.open(filepath, 'rb') as f:
                f.seek(0, 2)
                return f.tell()
        except:
            return 0

class TerminalApp(Application):
    """Terminal emulator application"""
    
    def __init__(self, manifest: AppManifest):
        super().__init__(manifest)
        self.shell = None
    
    def on_start(self) -> bool:
        print(f"Terminal {self.manifest.version} started")
        # Would start shell process
        return True
    
    def on_stop(self) -> bool:
        # Would stop shell process
        print("Terminal stopped")
        return True
    
    def execute_command(self, command: str) -> Tuple[int, str, str]:
        """Execute command"""
        if not self.context or not self.context.executor:
            return -1, "", "No executor available"
        
        return self.context.executor.execute(command)

class SystemMonitorApp(Application):
    """System monitor application"""
    
    def on_start(self) -> bool:
        print(f"System Monitor {self.manifest.version} started")
        return True
    
    def on_stop(self) -> bool:
        print("System Monitor stopped")
        return True
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        return {
            'cpu_usage': 0.0,  # Would get from monitoring
            'memory_usage': 0.0,
            'disk_usage': 0.0,
            'uptime': time.time(),
            'processes': 0
        }
"""
AppManager Component for KLayer

This module provides application management capabilities for KOS applications,
allowing them to interact with other applications in the KOS environment.
"""

import os
import sys
import json
import logging
import threading
import subprocess
from typing import Dict, List, Any, Optional, Union, Callable

logger = logging.getLogger('KOS.layer.app_manager')

class AppManager:
    """
    Manages KOS applications
    
    This class provides methods for KOS applications to interact with
    and manage other applications within the KOS environment.
    """
    
    def __init__(self):
        """Initialize the AppManager component"""
        self.lock = threading.RLock()
        self.running_apps = {}  # app_id -> app_process_info
        self.app_events = {}  # app_id -> event_callbacks
        self.app_settings = {}  # app_id -> settings
        
        # Load application settings
        self._load_app_settings()
        
        logger.debug("AppManager component initialized")
    
    def _load_app_settings(self):
        """Load application settings from disk"""
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Create settings directory if it doesn't exist
            settings_dir = os.path.join(kos_home, 'settings', 'apps')
            os.makedirs(settings_dir, exist_ok=True)
            
            # Load settings for each app
            for filename in os.listdir(settings_dir):
                if filename.endswith('.json'):
                    app_id = filename[:-5]  # Remove .json extension
                    settings_path = os.path.join(settings_dir, filename)
                    
                    with open(settings_path, 'r') as f:
                        settings = json.load(f)
                        self.app_settings[app_id] = settings
            
            logger.debug(f"Loaded settings for {len(self.app_settings)} applications")
        except Exception as e:
            logger.error(f"Error loading application settings: {e}")
    
    def _save_app_settings(self, app_id: str):
        """
        Save application settings to disk
        
        Args:
            app_id: Application ID
        """
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Create settings directory if it doesn't exist
            settings_dir = os.path.join(kos_home, 'settings', 'apps')
            os.makedirs(settings_dir, exist_ok=True)
            
            # Save settings for app
            settings_path = os.path.join(settings_dir, f"{app_id}.json")
            
            with open(settings_path, 'w') as f:
                json.dump(self.app_settings.get(app_id, {}), f, indent=2)
            
            logger.debug(f"Saved settings for application: {app_id}")
        except Exception as e:
            logger.error(f"Error saving application settings: {e}")
    
    def start_app(self, app_id: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Start a KOS application
        
        Args:
            app_id: Application ID
            args: Command-line arguments
            
        Returns:
            Dictionary with start status
        """
        try:
            # Get app registry to find app location
            from kos.layer import klayer
            app_registry = klayer.get_app_registry()
            
            if not app_registry:
                return {
                    "success": False,
                    "error": "AppRegistry not available"
                }
            
            # Get app info
            app_info = app_registry.get_app_info(app_id)
            
            if not app_info.get("success", False):
                return {
                    "success": False,
                    "error": f"Application not found: {app_id}"
                }
            
            # Check if app is already running
            with self.lock:
                if app_id in self.running_apps:
                    return {
                        "success": False,
                        "error": f"Application already running: {app_id}",
                        "pid": self.running_apps[app_id].get("pid")
                    }
            
            # Get app executable
            app_executable = app_info.get("executable")
            
            if not app_executable or not os.path.exists(app_executable):
                return {
                    "success": False,
                    "error": f"Application executable not found: {app_id}"
                }
            
            # Prepare command
            command = [app_executable]
            
            if args:
                command.extend(args)
            
            # Start process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Register process
            with self.lock:
                self.running_apps[app_id] = {
                    "pid": process.pid,
                    "process": process,
                    "start_time": time.time(),
                    "status": "running"
                }
            
            # Start monitoring thread
            threading.Thread(
                target=self._monitor_app,
                args=(app_id, process),
                daemon=True
            ).start()
            
            logger.info(f"Started application: {app_id} (PID: {process.pid})")
            
            return {
                "success": True,
                "app_id": app_id,
                "pid": process.pid
            }
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _monitor_app(self, app_id: str, process: subprocess.Popen):
        """
        Monitor a running application
        
        Args:
            app_id: Application ID
            process: Process object
        """
        try:
            # Wait for process to finish
            stdout, stderr = process.communicate()
            exit_code = process.returncode
            
            # Update process status
            with self.lock:
                if app_id in self.running_apps:
                    self.running_apps[app_id].update({
                        "status": "terminated",
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "end_time": time.time()
                    })
            
            # Trigger app terminated event
            self._trigger_app_event(app_id, "terminated", {
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr
            })
            
            logger.info(f"Application terminated: {app_id} (Exit code: {exit_code})")
        except Exception as e:
            logger.error(f"Error monitoring application: {e}")
            
            # Update process status on error
            with self.lock:
                if app_id in self.running_apps:
                    self.running_apps[app_id].update({
                        "status": "error",
                        "error": str(e),
                        "end_time": time.time()
                    })
            
            # Trigger app error event
            self._trigger_app_event(app_id, "error", {
                "error": str(e)
            })
    
    def stop_app(self, app_id: str, force: bool = False) -> Dict[str, Any]:
        """
        Stop a running KOS application
        
        Args:
            app_id: Application ID
            force: Whether to force stop the application
            
        Returns:
            Dictionary with stop status
        """
        with self.lock:
            if app_id not in self.running_apps:
                return {
                    "success": False,
                    "error": f"Application not running: {app_id}"
                }
            
            app_process = self.running_apps[app_id]
            
            if app_process["status"] != "running":
                return {
                    "success": False,
                    "error": f"Application not in running state: {app_id}"
                }
            
            process = app_process["process"]
            
            try:
                if force:
                    # Force kill
                    process.kill()
                else:
                    # Graceful termination
                    process.terminate()
                
                # Update status
                app_process["status"] = "stopping"
                
                logger.info(f"Stopping application: {app_id}")
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "force": force
                }
            except Exception as e:
                logger.error(f"Error stopping application: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }
    
    def get_app_status(self, app_id: str) -> Dict[str, Any]:
        """
        Get status of a KOS application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with application status
        """
        with self.lock:
            if app_id not in self.running_apps:
                return {
                    "success": True,
                    "running": False,
                    "app_id": app_id
                }
            
            app_process = self.running_apps[app_id]
            
            # Check if process is still running
            if app_process["status"] == "running":
                process = app_process["process"]
                
                if process.poll() is not None:
                    # Process has terminated
                    app_process["status"] = "terminated"
                    app_process["exit_code"] = process.returncode
                    app_process["end_time"] = time.time()
            
            # Return status
            return {
                "success": True,
                "running": app_process["status"] == "running",
                "app_id": app_id,
                "status": app_process["status"],
                "pid": app_process["pid"],
                "start_time": app_process["start_time"],
                "exit_code": app_process.get("exit_code"),
                "end_time": app_process.get("end_time")
            }
    
    def list_running_apps(self) -> Dict[str, Any]:
        """
        List all running KOS applications
        
        Returns:
            Dictionary with running applications
        """
        running_apps = []
        
        with self.lock:
            for app_id, app_process in self.running_apps.items():
                # Check if process is still running
                if app_process["status"] == "running":
                    process = app_process["process"]
                    
                    if process.poll() is not None:
                        # Process has terminated
                        app_process["status"] = "terminated"
                        app_process["exit_code"] = process.returncode
                        app_process["end_time"] = time.time()
                        continue
                
                # Add to running apps list if still running
                if app_process["status"] == "running":
                    running_apps.append({
                        "app_id": app_id,
                        "pid": app_process["pid"],
                        "start_time": app_process["start_time"]
                    })
        
        return {
            "success": True,
            "running_apps": running_apps,
            "count": len(running_apps)
        }
    
    def send_message_to_app(self, sender_id: str, receiver_id: str, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to another KOS application
        
        Args:
            sender_id: Sender application ID
            receiver_id: Receiver application ID
            message: Message to send
            
        Returns:
            Dictionary with send status
        """
        # Check if receiver app is running
        with self.lock:
            if receiver_id not in self.running_apps:
                return {
                    "success": False,
                    "error": f"Receiver application not running: {receiver_id}"
                }
            
            if self.running_apps[receiver_id]["status"] != "running":
                return {
                    "success": False,
                    "error": f"Receiver application not in running state: {receiver_id}"
                }
        
        # Check permissions
        from kos.layer import klayer
        permissions = klayer.get_permissions()
        
        if permissions and not permissions.check_permission(sender_id, f"message.{receiver_id}"):
            return {
                "success": False,
                "error": f"Permission denied: {sender_id} cannot send messages to {receiver_id}"
            }
        
        # Add message to receiver's message queue
        # (In a real implementation, this would use inter-process communication)
        # For this example, we just trigger an event
        
        self._trigger_app_event(receiver_id, "message", {
            "sender": sender_id,
            "message": message
        })
        
        return {
            "success": True,
            "sender": sender_id,
            "receiver": receiver_id
        }
    
    def register_app_event_callback(self, app_id: str, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for application events
        
        Args:
            app_id: Application ID
            event_type: Event type
            callback: Callback function
            
        Returns:
            Success status
        """
        with self.lock:
            if app_id not in self.app_events:
                self.app_events[app_id] = {}
            
            if event_type not in self.app_events[app_id]:
                self.app_events[app_id][event_type] = []
            
            self.app_events[app_id][event_type].append(callback)
            
            logger.debug(f"Registered callback for {app_id} {event_type} events")
            return True
    
    def unregister_app_event_callback(self, app_id: str, event_type: str, callback: Callable) -> bool:
        """
        Unregister a callback for application events
        
        Args:
            app_id: Application ID
            event_type: Event type
            callback: Callback function
            
        Returns:
            Success status
        """
        with self.lock:
            if app_id not in self.app_events:
                return False
            
            if event_type not in self.app_events[app_id]:
                return False
            
            if callback in self.app_events[app_id][event_type]:
                self.app_events[app_id][event_type].remove(callback)
                logger.debug(f"Unregistered callback for {app_id} {event_type} events")
                return True
            
            return False
    
    def _trigger_app_event(self, app_id: str, event_type: str, event_data: Dict[str, Any]):
        """
        Trigger an application event
        
        Args:
            app_id: Application ID
            event_type: Event type
            event_data: Event data
        """
        with self.lock:
            if app_id not in self.app_events:
                return
            
            if event_type not in self.app_events[app_id]:
                return
            
            # Copy callbacks to avoid modifying during iteration
            callbacks = list(self.app_events[app_id][event_type])
        
        # Call callbacks outside of lock
        for callback in callbacks:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Error in app event callback: {e}")
    
    def get_app_setting(self, app_id: str, key: str, default: Any = None) -> Any:
        """
        Get an application setting
        
        Args:
            app_id: Application ID
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Setting value
        """
        with self.lock:
            if app_id not in self.app_settings:
                return default
            
            return self.app_settings[app_id].get(key, default)
    
    def set_app_setting(self, app_id: str, key: str, value: Any) -> bool:
        """
        Set an application setting
        
        Args:
            app_id: Application ID
            key: Setting key
            value: Setting value
            
        Returns:
            Success status
        """
        with self.lock:
            if app_id not in self.app_settings:
                self.app_settings[app_id] = {}
            
            self.app_settings[app_id][key] = value
            
            # Save settings to disk
            self._save_app_settings(app_id)
            
            return True
    
    def get_app_settings(self, app_id: str) -> Dict[str, Any]:
        """
        Get all settings for an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with application settings
        """
        with self.lock:
            return self.app_settings.get(app_id, {}).copy()
    
    def clear_app_settings(self, app_id: str) -> bool:
        """
        Clear all settings for an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Success status
        """
        with self.lock:
            if app_id in self.app_settings:
                self.app_settings[app_id] = {}
                
                # Save settings to disk
                self._save_app_settings(app_id)
                
                return True
            
            return False

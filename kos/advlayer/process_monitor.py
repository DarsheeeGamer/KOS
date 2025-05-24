"""
ProcessMonitor Component for KADVLayer

This module provides process monitoring capabilities,
allowing KOS to track and manage processes running on the host system.
"""

import os
import sys
import time
import threading
import logging
import signal
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.process_monitor')

class ProcessEvent:
    """Event information for process changes"""
    
    def __init__(self, event_type: str, pid: int, info: Dict[str, Any] = None):
        """
        Initialize process event
        
        Args:
            event_type: Event type (started, terminated, crashed)
            pid: Process ID
            info: Additional process information
        """
        self.event_type = event_type
        self.pid = pid
        self.info = info or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_type": self.event_type,
            "pid": self.pid,
            "info": self.info,
            "timestamp": self.timestamp.isoformat()
        }

class ProcessMonitor:
    """
    Monitors processes on the host system
    
    This class provides methods to track processes, detect process
    creation, termination, and resource usage changes.
    """
    
    def __init__(self):
        """Initialize the ProcessMonitor component"""
        self.monitoring = False
        self.monitor_thread = None
        self.lock = threading.RLock()
        
        # Process tracking
        self.tracked_processes = {}  # pid -> process info
        self.watched_names = set()  # Process names to watch
        self.watched_commands = set()  # Command patterns to watch
        
        # Event history
        self.event_history = []
        self.max_history = 100
        
        # Callbacks for process events
        self.callbacks = {
            "started": [],
            "terminated": [],
            "crashed": [],
            "all": []
        }
        
        # Monitoring interval (seconds)
        self.interval = 3.0
        
        logger.debug("ProcessMonitor component initialized")
    
    def start_monitoring(self, interval: Optional[float] = None) -> bool:
        """
        Start process monitoring
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.monitoring:
                logger.warning("Process monitoring already running")
                return False
            
            if not PSUTIL_AVAILABLE:
                logger.error("Cannot monitor processes without psutil")
                return False
            
            if interval is not None:
                self.interval = max(1.0, interval)  # Minimum 1 second
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info(f"Started process monitoring with interval {self.interval}s")
            return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop process monitoring
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.monitoring:
                logger.warning("Process monitoring not running")
                return False
            
            self.monitoring = False
            
            # Wait for thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("Stopped process monitoring")
            return True
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot monitor processes without psutil")
            self.monitoring = False
            return
        
        # Get initial process list
        current_processes = self._get_current_processes()
        
        while self.monitoring:
            try:
                # Get new process list
                new_processes = self._get_current_processes()
                
                # Find created and terminated processes
                created_pids = set(new_processes.keys()) - set(current_processes.keys())
                terminated_pids = set(current_processes.keys()) - set(new_processes.keys())
                
                # Handle created processes
                for pid in created_pids:
                    self._handle_process_created(pid, new_processes[pid])
                
                # Handle terminated processes
                for pid in terminated_pids:
                    self._handle_process_terminated(pid, current_processes[pid])
                
                # Update status of existing processes
                for pid in set(new_processes.keys()) & set(current_processes.keys()):
                    self._update_process_status(pid, current_processes[pid], new_processes[pid])
                
                # Update current process list
                current_processes = new_processes
                
                # Sleep until next check
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in process monitoring: {e}")
                time.sleep(self.interval)
    
    def _get_current_processes(self) -> Dict[int, Dict[str, Any]]:
        """
        Get current process list
        
        Returns:
            Dictionary of processes (pid -> info)
        """
        processes = {}
        
        try:
            for process in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'status']):
                try:
                    info = process.info
                    processes[info['pid']] = {
                        'name': info['name'],
                        'exe': info['exe'],
                        'cmdline': info['cmdline'],
                        'status': info['status']
                    }
                    
                    # Add additional info for tracked processes
                    if self._should_track_process(info):
                        try:
                            # Get memory info
                            mem_info = process.memory_info()
                            processes[info['pid']]['memory'] = {
                                'rss': mem_info.rss,
                                'vms': mem_info.vms
                            }
                            
                            # Get CPU info
                            processes[info['pid']]['cpu_percent'] = process.cpu_percent(interval=0)
                            
                            # Get creation time
                            processes[info['pid']]['create_time'] = process.create_time()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception as e:
            logger.error(f"Error getting process list: {e}")
        
        return processes
    
    def _should_track_process(self, process_info: Dict[str, Any]) -> bool:
        """
        Check if process should be tracked
        
        Args:
            process_info: Process information
            
        Returns:
            Whether to track process
        """
        # Always track watched process names
        if process_info.get('name') in self.watched_names:
            return True
        
        # Check command line patterns
        if self.watched_commands and process_info.get('cmdline'):
            cmdline = ' '.join(process_info['cmdline'])
            for pattern in self.watched_commands:
                if pattern in cmdline:
                    return True
        
        # Track if already being tracked
        if process_info.get('pid') in self.tracked_processes:
            return True
        
        return False
    
    def _handle_process_created(self, pid: int, process_info: Dict[str, Any]):
        """
        Handle process creation
        
        Args:
            pid: Process ID
            process_info: Process information
        """
        # Check if process should be tracked
        if self._should_track_process(process_info):
            # Update tracked processes
            with self.lock:
                self.tracked_processes[pid] = process_info
            
            # Create event
            event = ProcessEvent("started", pid, process_info)
            
            # Add to history
            self._add_event_to_history(event)
            
            # Call callbacks
            self._call_callbacks("started", event)
            self._call_callbacks("all", event)
    
    def _handle_process_terminated(self, pid: int, process_info: Dict[str, Any]):
        """
        Handle process termination
        
        Args:
            pid: Process ID
            process_info: Process information
        """
        # Check if process was tracked
        if pid in self.tracked_processes:
            # Determine if crashed or terminated normally
            event_type = "crashed" if process_info.get('status') not in ["stopped", "sleeping", "idle"] else "terminated"
            
            # Create event
            event = ProcessEvent(event_type, pid, process_info)
            
            # Add to history
            self._add_event_to_history(event)
            
            # Call callbacks
            self._call_callbacks(event_type, event)
            self._call_callbacks("all", event)
            
            # Remove from tracked processes
            with self.lock:
                if pid in self.tracked_processes:
                    del self.tracked_processes[pid]
    
    def _update_process_status(self, pid: int, old_info: Dict[str, Any], new_info: Dict[str, Any]):
        """
        Update process status
        
        Args:
            pid: Process ID
            old_info: Old process information
            new_info: New process information
        """
        # Check if status changed
        if old_info.get('status') != new_info.get('status'):
            # Update tracked process
            if pid in self.tracked_processes:
                with self.lock:
                    self.tracked_processes[pid] = new_info
    
    def _add_event_to_history(self, event: ProcessEvent):
        """
        Add event to history
        
        Args:
            event: Process event
        """
        with self.lock:
            self.event_history.append(event)
            
            # Trim history if needed
            if len(self.event_history) > self.max_history:
                self.event_history = self.event_history[-self.max_history:]
    
    def _call_callbacks(self, event_type: str, event: ProcessEvent):
        """
        Call callbacks for event
        
        Args:
            event_type: Event type
            event: Process event
        """
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(event.to_dict())
                except Exception as e:
                    logger.error(f"Error in process callback: {e}")
    
    def register_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register callback for process events
        
        Args:
            event_type: Event type (started, terminated, crashed, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if event_type not in self.callbacks:
            logger.error(f"Invalid event type: {event_type}")
            return False
        
        with self.lock:
            self.callbacks[event_type].append(callback)
            logger.debug(f"Registered callback for {event_type} process events")
            return True
    
    def unregister_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Unregister callback for process events
        
        Args:
            event_type: Event type (started, terminated, crashed, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if event_type not in self.callbacks:
            logger.error(f"Invalid event type: {event_type}")
            return False
        
        with self.lock:
            if callback in self.callbacks[event_type]:
                self.callbacks[event_type].remove(callback)
                logger.debug(f"Unregistered callback for {event_type} process events")
                return True
            else:
                logger.warning(f"Callback not found for {event_type} process events")
                return False
    
    def watch_process_name(self, process_name: str) -> bool:
        """
        Add process name to watch list
        
        Args:
            process_name: Process name
            
        Returns:
            Success status
        """
        with self.lock:
            self.watched_names.add(process_name)
            logger.debug(f"Added process name to watch: {process_name}")
            return True
    
    def unwatch_process_name(self, process_name: str) -> bool:
        """
        Remove process name from watch list
        
        Args:
            process_name: Process name
            
        Returns:
            Success status
        """
        with self.lock:
            if process_name in self.watched_names:
                self.watched_names.remove(process_name)
                logger.debug(f"Removed process name from watch: {process_name}")
                return True
            else:
                logger.warning(f"Process name not in watch list: {process_name}")
                return False
    
    def watch_command_pattern(self, pattern: str) -> bool:
        """
        Add command pattern to watch list
        
        Args:
            pattern: Command pattern
            
        Returns:
            Success status
        """
        with self.lock:
            self.watched_commands.add(pattern)
            logger.debug(f"Added command pattern to watch: {pattern}")
            return True
    
    def unwatch_command_pattern(self, pattern: str) -> bool:
        """
        Remove command pattern from watch list
        
        Args:
            pattern: Command pattern
            
        Returns:
            Success status
        """
        with self.lock:
            if pattern in self.watched_commands:
                self.watched_commands.remove(pattern)
                logger.debug(f"Removed command pattern from watch: {pattern}")
                return True
            else:
                logger.warning(f"Command pattern not in watch list: {pattern}")
                return False
    
    def get_tracked_processes(self) -> Dict[int, Dict[str, Any]]:
        """
        Get tracked processes
        
        Returns:
            Dictionary of tracked processes (pid -> info)
        """
        with self.lock:
            return self.tracked_processes.copy()
    
    def get_event_history(self) -> List[Dict[str, Any]]:
        """
        Get event history
        
        Returns:
            List of events
        """
        with self.lock:
            return [event.to_dict() for event in self.event_history]
    
    def is_monitoring(self) -> bool:
        """
        Check if monitoring is active
        
        Returns:
            Whether monitoring is active
        """
        return self.monitoring
    
    def get_watched_names(self) -> Set[str]:
        """
        Get watched process names
        
        Returns:
            Set of watched process names
        """
        with self.lock:
            return self.watched_names.copy()
    
    def get_watched_commands(self) -> Set[str]:
        """
        Get watched command patterns
        
        Returns:
            Set of watched command patterns
        """
        with self.lock:
            return self.watched_commands.copy()
    
    def track_process(self, pid: int) -> bool:
        """
        Start tracking a specific process
        
        Args:
            pid: Process ID
            
        Returns:
            Success status
        """
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot track processes without psutil")
            return False
        
        try:
            # Check if process exists
            process = psutil.Process(pid)
            
            # Get process info
            info = {
                'pid': pid,
                'name': process.name(),
                'exe': process.exe() if hasattr(process, 'exe') else None,
                'cmdline': process.cmdline(),
                'status': process.status()
            }
            
            # Add to tracked processes
            with self.lock:
                self.tracked_processes[pid] = info
            
            logger.debug(f"Started tracking process: {pid}")
            return True
        except psutil.NoSuchProcess:
            logger.warning(f"Process does not exist: {pid}")
            return False
        except psutil.AccessDenied:
            logger.warning(f"Access denied to process: {pid}")
            return False
        except Exception as e:
            logger.error(f"Error tracking process: {e}")
            return False
    
    def untrack_process(self, pid: int) -> bool:
        """
        Stop tracking a specific process
        
        Args:
            pid: Process ID
            
        Returns:
            Success status
        """
        with self.lock:
            if pid in self.tracked_processes:
                del self.tracked_processes[pid]
                logger.debug(f"Stopped tracking process: {pid}")
                return True
            else:
                logger.warning(f"Process not being tracked: {pid}")
                return False

"""
KADVLayer - Advanced Layer for KOS Host Communication

This module provides the interface between KOS and the host computer,
enabling system monitoring, process management, and resource control.
"""

import os
import sys
import logging
import threading
import platform
from typing import Dict, List, Any, Optional, Union, Callable

# Setup logging
logger = logging.getLogger('KOS.advlayer')

class KADVLayer:
    """
    Main class for the KOS Advanced Layer (KADVLayer)
    
    This class provides the interface between KOS and the host computer,
    enabling KOS to monitor and control the underlying system resources.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    @classmethod
    def get_instance(cls) -> 'KADVLayer':
        """Get singleton instance of KADVLayer"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
    
    def __init__(self):
        """Initialize the KADVLayer"""
        self.system_info = None
        self.process_manager = None
        self.resource_monitor = None
        self.process_monitor = None
        self.system_metrics = None
        self.hardware_manager = None
        self.network_manager = None
        
        # Initialize components
        self._init_components()
        
        # Initialize platform-specific modules
        self._init_platform_specific()
        
        logger.info("KADVLayer initialized")
    
    def _init_components(self):
        """Initialize KADVLayer components"""
        # Import locally to avoid circular imports
        from .system_info import SystemInfo
        from .process_manager import ProcessManager
        from .system_resource_monitor import SystemResourceMonitor
        from .process_monitor import ProcessMonitor
        from .system_metrics import SystemMetrics
        from .hardware_manager import HardwareManager
        from .network_manager import NetworkManager
        from .resource_orchestrator import ResourceOrchestrator
        
        self.system_info = SystemInfo()
        self.process_manager = ProcessManager()
        self.resource_monitor = SystemResourceMonitor()
        self.process_monitor = ProcessMonitor()
        self.system_metrics = SystemMetrics()
        self.hardware_manager = HardwareManager()
        self.network_manager = NetworkManager()
        self.resource_orchestrator = ResourceOrchestrator()
    
    def _init_platform_specific(self):
        """Initialize platform-specific components"""
        system = platform.system().lower()
        
        if system == 'windows':
            # Import Windows-specific modules if needed
            try:
                import winreg
                self.has_windows_support = True
            except ImportError:
                self.has_windows_support = False
        elif system == 'linux':
            # Import Linux-specific modules if needed
            try:
                import resource
                self.has_linux_support = True
            except ImportError:
                self.has_linux_support = False
        elif system == 'darwin':
            # Import macOS-specific modules if needed
            try:
                import resource
                self.has_macos_support = True
            except ImportError:
                self.has_macos_support = False
    
    def get_system_info(self) -> Any:
        """Get the SystemInfo component"""
        return self.system_info
    
    def get_process_manager(self) -> Any:
        """Get the ProcessManager component"""
        return self.process_manager
    
    def get_resource_monitor(self) -> Any:
        """Get the SystemResourceMonitor component"""
        return self.resource_monitor
    
    def get_process_monitor(self) -> Any:
        """Get the ProcessMonitor component"""
        return self.process_monitor
    
    def get_system_metrics(self) -> Any:
        """Get the SystemMetrics component"""
        return self.system_metrics
    
    def get_hardware_manager(self) -> Any:
        """Get the HardwareManager component"""
        return self.hardware_manager
    
    def get_network_manager(self) -> Any:
        """Get the NetworkManager component"""
        return self.network_manager
    
    def get_resource_orchestrator(self) -> Any:
        """Get the ResourceOrchestrator component"""
        return self.resource_orchestrator
    
    def execute_command(self, command: str, shell: bool = True, 
                       timeout: Optional[float] = None) -> Dict[str, Any]:
        """
        Execute a command on the host system
        
        Args:
            command: Command to execute
            shell: Whether to use shell
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with execution results
        """
        if self.process_manager:
            return self.process_manager.execute_command(command, shell, timeout)
        else:
            return {"success": False, "error": "ProcessManager not initialized"}
    
    def get_host_info(self) -> Dict[str, Any]:
        """Get information about the host system"""
        if self.system_info:
            return self.system_info.get_system_info()
        else:
            return {"error": "SystemInfo not initialized"}
    
    def register_resource_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for resource events
        
        Args:
            event_type: Type of event (cpu, memory, disk, network)
            callback: Callback function
            
        Returns:
            Success status
        """
        if self.resource_monitor:
            return self.resource_monitor.register_callback(event_type, callback)
        return False
    
    def register_process_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for process events
        
        Args:
            event_type: Type of event (start, stop, crash)
            callback: Callback function
            
        Returns:
            Success status
        """
        if self.process_monitor:
            return self.process_monitor.register_callback(event_type, callback)
        return False
    
    def register_hardware_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for hardware events
        
        Args:
            event_type: Type of event (connected, disconnected, changed, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if self.hardware_manager:
            return self.hardware_manager.register_callback(event_type, callback)
        return False
    
    def register_network_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for network events
        
        Args:
            event_type: Type of event (interface_up, interface_down, traffic_spike, etc.)
            callback: Callback function
            
        Returns:
            Success status
        """
        if self.network_manager:
            return self.network_manager.register_callback(event_type, callback)
        return False
    
    def start_monitoring(self) -> Dict[str, bool]:
        """
        Start all monitoring components
        
        Returns:
            Dictionary with status of each monitoring component
        """
        results = {}
        
        if self.resource_monitor:
            results["resource_monitor"] = self.resource_monitor.start_monitoring()
        
        if self.process_monitor:
            results["process_monitor"] = self.process_monitor.start_monitoring()
        
        if self.hardware_manager:
            results["hardware_manager"] = self.hardware_manager.start_monitoring()
        
        if self.network_manager:
            results["network_manager"] = self.network_manager.start_monitoring()
        
        return results
    
    def stop_monitoring(self) -> Dict[str, bool]:
        """
        Stop all monitoring components
        
        Returns:
            Dictionary with status of each monitoring component
        """
        results = {}
        
        if self.resource_monitor:
            results["resource_monitor"] = self.resource_monitor.stop_monitoring()
        
        if self.process_monitor:
            results["process_monitor"] = self.process_monitor.stop_monitoring()
        
        if self.hardware_manager:
            results["hardware_manager"] = self.hardware_manager.stop_monitoring()
        
        if self.network_manager:
            results["network_manager"] = self.network_manager.stop_monitoring()
        
        return results
    
    def get_system_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive summary of system information
        
        Returns:
            Dictionary with system summary
        """
        import time
        summary = {"timestamp": time.time()}
        
        # Get basic system information
        if self.system_info:
            system_info = self.system_info.get_system_info(use_cache=True)
            summary["system"] = {
                "platform": system_info.get("platform", {}),
                "python": system_info.get("python", {})
            }
        
        # Get resource usage
        if self.resource_monitor:
            metrics = self.resource_monitor.get_current_metrics()
            summary["resources"] = {
                "cpu": metrics.get("cpu", {}),
                "memory": metrics.get("memory", {}),
                "disk": metrics.get("disk", {})
            }
        
        # Get hardware information
        if self.hardware_manager:
            devices = self.hardware_manager.get_devices()
            summary["hardware"] = {
                "devices_count": len(devices),
                "devices_by_type": {}
            }
            
            # Group devices by type
            for device in devices:
                device_type = device.get("device_type", "unknown")
                if device_type not in summary["hardware"]["devices_by_type"]:
                    summary["hardware"]["devices_by_type"][device_type] = []
                summary["hardware"]["devices_by_type"][device_type].append(device)
        
        # Get network information
        if self.network_manager:
            interfaces = self.network_manager.get_interfaces()
            connections = self.network_manager.get_connection_stats()
            
            summary["network"] = {
                "interfaces_count": len(interfaces),
                "interfaces": interfaces,
                "connections": connections
            }
        
        # Get process information
        if self.process_monitor:
            processes = self.process_monitor.get_tracked_processes()
            
            summary["processes"] = {
                "count": len(processes),
                "tracked": processes
            }
        
        return summary

# Create default instance
try:
    kadvlayer = KADVLayer.get_instance()
except Exception as e:
    logger.error(f"Failed to initialize KADVLayer: {e}")
    kadvlayer = None

"""
Service Monitor Component for KADVLayer

This module provides service monitoring capabilities for KOS,
allowing for performance tracking, health checks, and alerts for system services.
"""

import os
import sys
import time
import json
import logging
import threading
import signal
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from datetime import datetime, timedelta

# Import KOS components
from kos.services import ServiceManager, ServiceState, Service
from kos.advlayer.system_metrics import SystemMetrics

# Set up logging
logger = logging.getLogger('KOS.advlayer.service_monitor')

class ServiceMetrics:
    """Service-specific metrics tracking"""
    
    def __init__(self, service_id: str, name: str):
        """
        Initialize service metrics
        
        Args:
            service_id: Service ID
            name: Service name
        """
        self.service_id = service_id
        self.name = name
        self.status_history = []  # List of (timestamp, status) tuples
        self.cpu_usage = []  # List of (timestamp, usage) tuples
        self.memory_usage = []  # List of (timestamp, usage) tuples
        self.restart_history = []  # List of (timestamp, exit_code) tuples
        self.response_times = []  # List of (timestamp, ms) tuples for health checks
        self.health_status = []  # List of (timestamp, status) tuples
        self.log_entries = []  # List of (timestamp, level, message) tuples
        
        # Set max length for each metric to prevent memory bloat
        self.max_history_length = 1000
    
    def add_status(self, timestamp: float, status: str):
        """Add status change to history"""
        self.status_history.append((timestamp, status))
        if len(self.status_history) > self.max_history_length:
            self.status_history.pop(0)
    
    def add_cpu_usage(self, timestamp: float, usage: float):
        """Add CPU usage data point"""
        self.cpu_usage.append((timestamp, usage))
        if len(self.cpu_usage) > self.max_history_length:
            self.cpu_usage.pop(0)
    
    def add_memory_usage(self, timestamp: float, usage: float):
        """Add memory usage data point"""
        self.memory_usage.append((timestamp, usage))
        if len(self.memory_usage) > self.max_history_length:
            self.memory_usage.pop(0)
    
    def add_restart(self, timestamp: float, exit_code: Optional[int]):
        """Add restart event to history"""
        self.restart_history.append((timestamp, exit_code))
        if len(self.restart_history) > self.max_history_length:
            self.restart_history.pop(0)
    
    def add_response_time(self, timestamp: float, ms: float):
        """Add health check response time"""
        self.response_times.append((timestamp, ms))
        if len(self.response_times) > self.max_history_length:
            self.response_times.pop(0)
    
    def add_health_status(self, timestamp: float, status: str):
        """Add health check status"""
        self.health_status.append((timestamp, status))
        if len(self.health_status) > self.max_history_length:
            self.health_status.pop(0)
    
    def add_log_entry(self, timestamp: float, level: str, message: str):
        """Add log entry"""
        self.log_entries.append((timestamp, level, message))
        if len(self.log_entries) > self.max_history_length:
            self.log_entries.pop(0)
    
    def get_latest_status(self) -> Optional[Tuple[float, str]]:
        """Get the latest status"""
        if not self.status_history:
            return None
        return self.status_history[-1]
    
    def get_latest_cpu_usage(self) -> Optional[float]:
        """Get the latest CPU usage"""
        if not self.cpu_usage:
            return None
        return self.cpu_usage[-1][1]
    
    def get_latest_memory_usage(self) -> Optional[float]:
        """Get the latest memory usage"""
        if not self.memory_usage:
            return None
        return self.memory_usage[-1][1]
    
    def get_restart_count(self, period_hours: int = 24) -> int:
        """
        Get number of restarts in the specified period
        
        Args:
            period_hours: Period in hours (default: 24)
            
        Returns:
            Number of restarts
        """
        if not self.restart_history:
            return 0
        
        cutoff = time.time() - (period_hours * 3600)
        return sum(1 for t, _ in self.restart_history if t >= cutoff)
    
    def get_average_response_time(self, period_hours: int = 1) -> Optional[float]:
        """
        Get average response time in the specified period
        
        Args:
            period_hours: Period in hours (default: 1)
            
        Returns:
            Average response time in milliseconds
        """
        if not self.response_times:
            return None
        
        cutoff = time.time() - (period_hours * 3600)
        recent_times = [rt for t, rt in self.response_times if t >= cutoff]
        
        if not recent_times:
            return None
        
        return sum(recent_times) / len(recent_times)
    
    def get_uptime_percentage(self, period_hours: int = 24) -> Optional[float]:
        """
        Calculate uptime percentage over the specified period
        
        Args:
            period_hours: Period in hours (default: 24)
            
        Returns:
            Uptime percentage (0-100)
        """
        if not self.status_history:
            return None
        
        cutoff = time.time() - (period_hours * 3600)
        
        # Filter status history to the specified period
        relevant_history = [(t, s) for t, s in self.status_history if t >= cutoff]
        
        if not relevant_history:
            return None
        
        # Add current time with latest status to complete the timeline
        latest_status = self.status_history[-1][1]
        timeline = relevant_history + [(time.time(), latest_status)]
        
        # Calculate uptime
        uptime = 0
        for i in range(len(timeline) - 1):
            current_time, current_status = timeline[i]
            next_time, _ = timeline[i + 1]
            
            if current_status == "active":
                uptime += (next_time - current_time)
        
        # Calculate total period (from first status to now)
        total_period = time.time() - relevant_history[0][0]
        
        return (uptime / total_period) * 100 if total_period > 0 else None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert service metrics to dictionary
        
        Returns:
            Dictionary representation of service metrics
        """
        return {
            "service_id": self.service_id,
            "name": self.name,
            "current_status": self.get_latest_status()[1] if self.get_latest_status() else "unknown",
            "uptime_percentage": self.get_uptime_percentage(),
            "restart_count_24h": self.get_restart_count(),
            "current_cpu_usage": self.get_latest_cpu_usage(),
            "current_memory_usage": self.get_latest_memory_usage(),
            "average_response_time": self.get_average_response_time(),
            "status_history": self.status_history[-10:],  # Last 10 status changes
            "restart_history": self.restart_history[-10:],  # Last 10 restarts
            "health_status": self.health_status[-10:] if self.health_status else []  # Last 10 health checks
        }

class ServiceMonitor:
    """Monitors services and collects performance metrics"""
    
    def __init__(self, system_metrics: Optional[SystemMetrics] = None):
        """
        Initialize service monitor
        
        Args:
            system_metrics: SystemMetrics instance (optional)
        """
        self.system_metrics = system_metrics
        self.services_metrics = {}  # Map of service ID to ServiceMetrics
        self.health_checks = {}  # Map of service ID to health check function
        self.alert_callbacks = []  # List of alert callback functions
        self.lock = threading.RLock()
        
        # Monitoring control
        self.monitoring = False
        self.monitor_thread = None
        self.health_check_thread = None
        self.monitor_interval = 10  # seconds
        self.health_check_interval = 60  # seconds
        
        # Alert thresholds
        self.cpu_threshold = 80  # percentage
        self.memory_threshold = 80  # percentage
        self.restart_threshold = 3  # restarts in 1 hour
        self.response_time_threshold = 1000  # milliseconds
    
    def start_monitoring(self, monitor_interval: int = 10, health_check_interval: int = 60) -> bool:
        """
        Start service monitoring
        
        Args:
            monitor_interval: Monitoring interval in seconds
            health_check_interval: Health check interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.monitoring:
                logger.warning("Service monitoring is already active")
                return False
            
            self.monitor_interval = monitor_interval
            self.health_check_interval = health_check_interval
            self.monitoring = True
            
            # Start monitoring thread
            self.monitor_thread = threading.Thread(target=self._monitor_loop)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
            
            # Start health check thread
            self.health_check_thread = threading.Thread(target=self._health_check_loop)
            self.health_check_thread.daemon = True
            self.health_check_thread.start()
            
            logger.info(f"Started service monitoring (interval: {monitor_interval}s, health check: {health_check_interval}s)")
            return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop service monitoring
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.monitoring:
                logger.warning("Service monitoring is not active")
                return False
            
            self.monitoring = False
            
            # Threads will terminate on their own due to monitoring flag
            logger.info("Stopped service monitoring")
            return True
    
    def register_service(self, service_id: str, name: str) -> bool:
        """
        Register a service for monitoring
        
        Args:
            service_id: Service ID
            name: Service name
            
        Returns:
            Success status
        """
        with self.lock:
            if service_id in self.services_metrics:
                logger.warning(f"Service {service_id} is already registered")
                return False
            
            # Create service metrics
            self.services_metrics[service_id] = ServiceMetrics(service_id, name)
            
            # Register service state change callback
            service = ServiceManager.get_service(service_id)
            if service:
                service.add_watcher(self._service_state_changed)
            
            logger.info(f"Registered service for monitoring: {name} ({service_id})")
            return True
    
    def unregister_service(self, service_id: str) -> bool:
        """
        Unregister a service from monitoring
        
        Args:
            service_id: Service ID
            
        Returns:
            Success status
        """
        with self.lock:
            if service_id not in self.services_metrics:
                logger.warning(f"Service {service_id} is not registered")
                return False
            
            # Remove service metrics
            del self.services_metrics[service_id]
            
            # Remove health check
            if service_id in self.health_checks:
                del self.health_checks[service_id]
            
            # Unregister service state change callback
            service = ServiceManager.get_service(service_id)
            if service:
                service.remove_watcher(self._service_state_changed)
            
            logger.info(f"Unregistered service from monitoring: {service_id}")
            return True
    
    def register_health_check(self, service_id: str, check_function: Callable[[], Tuple[bool, float]]) -> bool:
        """
        Register a health check function for a service
        
        Args:
            service_id: Service ID
            check_function: Health check function that returns (is_healthy, response_time_ms)
            
        Returns:
            Success status
        """
        with self.lock:
            if service_id not in self.services_metrics:
                logger.warning(f"Service {service_id} is not registered for monitoring")
                return False
            
            self.health_checks[service_id] = check_function
            logger.info(f"Registered health check for service: {service_id}")
            return True
    
    def register_alert_callback(self, callback: Callable[[str, str, Dict[str, Any]], None]) -> bool:
        """
        Register an alert callback function
        
        Args:
            callback: Function(service_id, alert_type, alert_data)
            
        Returns:
            Success status
        """
        with self.lock:
            self.alert_callbacks.append(callback)
            logger.info("Registered alert callback")
            return True
    
    def set_alert_thresholds(self, cpu: Optional[float] = None, memory: Optional[float] = None,
                           restarts: Optional[int] = None, response_time: Optional[float] = None) -> bool:
        """
        Set alert thresholds
        
        Args:
            cpu: CPU usage threshold percentage (0-100)
            memory: Memory usage threshold percentage (0-100)
            restarts: Restart count threshold in 1 hour
            response_time: Response time threshold in milliseconds
            
        Returns:
            Success status
        """
        with self.lock:
            if cpu is not None:
                self.cpu_threshold = cpu
            
            if memory is not None:
                self.memory_threshold = memory
            
            if restarts is not None:
                self.restart_threshold = restarts
            
            if response_time is not None:
                self.response_time_threshold = response_time
            
            logger.info(f"Updated alert thresholds: CPU={self.cpu_threshold}%, "
                       f"Memory={self.memory_threshold}%, Restarts={self.restart_threshold}, "
                       f"Response time={self.response_time_threshold}ms")
            return True
    
    def get_service_metrics(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metrics for a specific service
        
        Args:
            service_id: Service ID
            
        Returns:
            Service metrics dictionary or None if not found
        """
        with self.lock:
            if service_id not in self.services_metrics:
                return None
            
            return self.services_metrics[service_id].to_dict()
    
    def get_all_service_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all services
        
        Returns:
            Dictionary of service ID to metrics
        """
        with self.lock:
            return {sid: metrics.to_dict() for sid, metrics in self.services_metrics.items()}
    
    def _monitor_loop(self):
        """Service monitoring thread loop"""
        logger.info("Service monitoring loop started")
        
        while self.monitoring:
            try:
                # Get list of services
                services = ServiceManager.list_services()
                
                # Process each service
                for service in services:
                    # Skip if not registered
                    if service.id not in self.services_metrics:
                        # Auto-register if monitoring is active
                        self.register_service(service.id, service.name)
                    
                    # Update metrics
                    self._update_service_metrics(service)
                
                # Check thresholds and trigger alerts
                self._check_alerts()
                
            except Exception as e:
                logger.error(f"Error in service monitoring loop: {str(e)}")
            
            # Sleep until next interval
            time.sleep(self.monitor_interval)
        
        logger.info("Service monitoring loop stopped")
    
    def _health_check_loop(self):
        """Health check thread loop"""
        logger.info("Health check loop started")
        
        while self.monitoring:
            try:
                # Run health checks
                with self.lock:
                    for service_id, check_func in list(self.health_checks.items()):
                        # Skip if service is not registered
                        if service_id not in self.services_metrics:
                            continue
                        
                        try:
                            # Run health check
                            is_healthy, response_time = check_func()
                            
                            # Update metrics
                            timestamp = time.time()
                            metrics = self.services_metrics[service_id]
                            metrics.add_response_time(timestamp, response_time)
                            metrics.add_health_status(timestamp, "healthy" if is_healthy else "unhealthy")
                            
                            # Check threshold and trigger alert
                            if response_time > self.response_time_threshold:
                                self._trigger_alert(service_id, "response_time", {
                                    "response_time": response_time,
                                    "threshold": self.response_time_threshold
                                })
                            
                            if not is_healthy:
                                self._trigger_alert(service_id, "health_check", {
                                    "status": "unhealthy",
                                    "response_time": response_time
                                })
                        
                        except Exception as e:
                            logger.error(f"Error running health check for {service_id}: {str(e)}")
                            
                            # Update metrics indicating health check failure
                            timestamp = time.time()
                            metrics = self.services_metrics[service_id]
                            metrics.add_health_status(timestamp, "check_failed")
                            
                            # Trigger alert
                            self._trigger_alert(service_id, "health_check", {
                                "status": "check_failed",
                                "error": str(e)
                            })
            
            except Exception as e:
                logger.error(f"Error in health check loop: {str(e)}")
            
            # Sleep until next interval
            time.sleep(self.health_check_interval)
        
        logger.info("Health check loop stopped")
    
    def _update_service_metrics(self, service: Service):
        """
        Update metrics for a service
        
        Args:
            service: Service instance
        """
        with self.lock:
            if service.id not in self.services_metrics:
                return
            
            metrics = self.services_metrics[service.id]
            timestamp = time.time()
            
            # Update status if changed
            current_status = service.state.value
            if not metrics.status_history or metrics.status_history[-1][1] != current_status:
                metrics.add_status(timestamp, current_status)
            
            # Get process metrics if available
            if service.pid and self.system_metrics:
                try:
                    # Add CPU usage
                    cpu_usage = self.system_metrics.get_metric("process", f"{service.pid}_cpu")
                    if cpu_usage:
                        metrics.add_cpu_usage(timestamp, cpu_usage.get("value", 0))
                    
                    # Add memory usage
                    memory_usage = self.system_metrics.get_metric("process", f"{service.pid}_memory")
                    if memory_usage:
                        metrics.add_memory_usage(timestamp, memory_usage.get("value", 0))
                
                except Exception as e:
                    logger.error(f"Error updating process metrics for {service.name}: {str(e)}")
    
    def _service_state_changed(self, service_name: str, new_state: ServiceState):
        """
        Handle service state change
        
        Args:
            service_name: Service name
            new_state: New service state
        """
        # Find service ID
        service = None
        for s in ServiceManager.list_services():
            if s.name == service_name:
                service = s
                break
        
        if not service:
            return
        
        with self.lock:
            if service.id not in self.services_metrics:
                return
            
            metrics = self.services_metrics[service.id]
            timestamp = time.time()
            
            # Update status
            metrics.add_status(timestamp, new_state.value)
            
            # Check for restart
            if new_state == ServiceState.ACTIVE and metrics.status_history and len(metrics.status_history) >= 2:
                # Check if previous state was INACTIVE or FAILED
                prev_status = metrics.status_history[-2][1]
                if prev_status in ["inactive", "failed"]:
                    # Record restart
                    metrics.add_restart(timestamp, service.exit_code)
                    
                    # Check restart threshold
                    restart_count = metrics.get_restart_count(period_hours=1)
                    if restart_count >= self.restart_threshold:
                        self._trigger_alert(service.id, "frequent_restarts", {
                            "restart_count": restart_count,
                            "threshold": self.restart_threshold,
                            "period_hours": 1
                        })
    
    def _check_alerts(self):
        """Check alert thresholds and trigger alerts"""
        with self.lock:
            for service_id, metrics in self.services_metrics.items():
                # CPU usage alert
                cpu_usage = metrics.get_latest_cpu_usage()
                if cpu_usage is not None and cpu_usage > self.cpu_threshold:
                    self._trigger_alert(service_id, "high_cpu", {
                        "cpu_usage": cpu_usage,
                        "threshold": self.cpu_threshold
                    })
                
                # Memory usage alert
                memory_usage = metrics.get_latest_memory_usage()
                if memory_usage is not None and memory_usage > self.memory_threshold:
                    self._trigger_alert(service_id, "high_memory", {
                        "memory_usage": memory_usage,
                        "threshold": self.memory_threshold
                    })
    
    def _trigger_alert(self, service_id: str, alert_type: str, alert_data: Dict[str, Any]):
        """
        Trigger an alert
        
        Args:
            service_id: Service ID
            alert_type: Alert type
            alert_data: Alert data
        """
        # Get service name
        service_name = "unknown"
        if service_id in self.services_metrics:
            service_name = self.services_metrics[service_id].name
        
        # Log alert
        logger.warning(f"Service alert: {service_name} ({service_id}) - {alert_type}: {alert_data}")
        
        # Add timestamp to alert data
        alert_data["timestamp"] = time.time()
        alert_data["service_name"] = service_name
        
        # Call alert callbacks
        for callback in self.alert_callbacks:
            try:
                callback(service_id, alert_type, alert_data)
            except Exception as e:
                logger.error(f"Error in alert callback: {str(e)}")

# Singleton instance
_instance = None

def get_instance(system_metrics: Optional[SystemMetrics] = None) -> ServiceMonitor:
    """
    Get the ServiceMonitor instance
    
    Args:
        system_metrics: SystemMetrics instance (optional)
        
    Returns:
        ServiceMonitor instance
    """
    global _instance
    if _instance is None:
        _instance = ServiceMonitor(system_metrics)
    return _instance

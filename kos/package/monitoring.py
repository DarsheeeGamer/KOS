"""
Package Management Monitoring for KOS

This module provides monitoring capabilities for KPM operations,
integrating with KADVLayer for advanced system monitoring.
"""

import os
import logging
import json
import time
import threading
from typing import Dict, List, Any, Optional, Tuple, Callable
from datetime import datetime

# Try to import KADVLayer components
try:
    from ...advlayer import KADVLayer
    from ...advlayer.system_metrics import SystemMetrics
    from ...advlayer.process_monitor import ProcessMonitor
    KADV_AVAILABLE = True
except ImportError:
    KADV_AVAILABLE = False

logger = logging.getLogger('KOS.package.monitoring')

# Constants
MONITOR_LOG_DIR = os.path.expanduser('~/.kos/kpm/logs')
METRICS_FILE = os.path.join(MONITOR_LOG_DIR, 'kpm_metrics.json')
OPERATIONS_LOG = os.path.join(MONITOR_LOG_DIR, 'kpm_operations.log')

class PackageOperationType:
    """Enum of package operation types"""
    INSTALL = "install"
    REMOVE = "remove"
    UPDATE = "update"
    SEARCH = "search"
    INDEX = "index"
    REPO_ADD = "repo_add"
    REPO_REMOVE = "repo_remove"
    REPO_UPDATE = "repo_update"
    APP_INSTALL = "app_install"
    APP_REMOVE = "app_remove"
    APP_UPDATE = "app_update"
    PIP_INSTALL = "pip_install"
    PIP_REMOVE = "pip_remove"
    PIP_UPDATE = "pip_update"
    OTHER = "other"

class PackageOperation:
    """Represents a package management operation with metrics"""
    def __init__(self, operation_type: str, package_name: str = None, 
                 repo_name: str = None, app_name: str = None):
        self.operation_type = operation_type
        self.package_name = package_name
        self.repo_name = repo_name
        self.app_name = app_name
        self.start_time = time.time()
        self.end_time = None
        self.success = None
        self.error = None
        self.cpu_usage = None
        self.memory_usage = None
        self.disk_usage = None
        self.details = {}
    
    def complete(self, success: bool, error: str = None):
        """Mark operation as completed"""
        self.end_time = time.time()
        self.success = success
        self.error = error
    
    @property
    def duration(self) -> float:
        """Get operation duration in seconds"""
        if self.end_time is None:
            return time.time() - self.start_time
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'operation_type': self.operation_type,
            'package_name': self.package_name,
            'repo_name': self.repo_name,
            'app_name': self.app_name,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.duration,
            'success': self.success,
            'error': self.error,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'disk_usage': self.disk_usage,
            'details': self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageOperation':
        """Create from dictionary"""
        op = cls(data['operation_type'], 
                data.get('package_name'), 
                data.get('repo_name'),
                data.get('app_name'))
        op.start_time = data.get('start_time')
        op.end_time = data.get('end_time')
        op.success = data.get('success')
        op.error = data.get('error')
        op.cpu_usage = data.get('cpu_usage')
        op.memory_usage = data.get('memory_usage')
        op.disk_usage = data.get('disk_usage')
        op.details = data.get('details', {})
        return op
    
    def __str__(self) -> str:
        target = self.package_name or self.repo_name or self.app_name or 'unknown'
        status = "SUCCESS" if self.success else "FAILED" if self.success is False else "IN PROGRESS"
        return f"{self.operation_type.upper()} {target} - {status} ({self.duration:.2f}s)"

class PackageMonitor:
    """Monitors and records KPM operations and system metrics"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'PackageMonitor':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self.operations = []
        self.current_operation = None
        self.kadv = None
        self.system_metrics = None
        self.process_monitor = None
        
        # Initialize directory
        os.makedirs(MONITOR_LOG_DIR, exist_ok=True)
        
        # Load existing metrics
        self._load_metrics()
        
        # Initialize KADVLayer integration if available
        if KADV_AVAILABLE:
            try:
                self.kadv = KADVLayer()
                self.system_metrics = self.kadv.get_system_metrics()
                self.process_monitor = self.kadv.get_process_monitor()
                logger.info("KADVLayer integration initialized for package monitoring")
            except Exception as e:
                logger.warning(f"Failed to initialize KADVLayer: {e}")
    
    def _load_metrics(self):
        """Load existing metrics from file"""
        try:
            if os.path.exists(METRICS_FILE):
                with open(METRICS_FILE, 'r') as f:
                    data = json.load(f)
                    self.operations = [PackageOperation.from_dict(op) for op in data]
                logger.debug(f"Loaded {len(self.operations)} operation records")
        except Exception as e:
            logger.error(f"Error loading metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to file"""
        try:
            with open(METRICS_FILE, 'w') as f:
                # Keep only the last 1000 operations to prevent file growth
                recent_ops = self.operations[-1000:] if len(self.operations) > 1000 else self.operations
                json.dump([op.to_dict() for op in recent_ops], f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    def _log_operation(self, operation: PackageOperation):
        """Log operation to the operations log"""
        try:
            with open(OPERATIONS_LOG, 'a') as f:
                timestamp = datetime.fromtimestamp(operation.start_time).strftime('%Y-%m-%d %H:%M:%S')
                status = "SUCCESS" if operation.success else "FAILED" if operation.success is False else "IN PROGRESS"
                target = operation.package_name or operation.repo_name or operation.app_name or 'unknown'
                line = f"{timestamp} | {operation.operation_type.upper()} | {target} | {status} | {operation.duration:.2f}s"
                if operation.error:
                    line += f" | ERROR: {operation.error}"
                f.write(line + "\n")
        except Exception as e:
            logger.error(f"Error logging operation: {e}")
    
    def start_operation(self, operation_type: str, package_name: str = None, 
                       repo_name: str = None, app_name: str = None) -> PackageOperation:
        """
        Start monitoring a package operation
        
        Args:
            operation_type: Type of operation (use PackageOperationType constants)
            package_name: Name of the package being operated on
            repo_name: Name of the repository being operated on
            app_name: Name of the application being operated on
            
        Returns:
            The created PackageOperation object
        """
        # Create operation record
        operation = PackageOperation(operation_type, package_name, repo_name, app_name)
        self.current_operation = operation
        
        # Capture initial system metrics if KADVLayer is available
        if self.system_metrics:
            try:
                metrics = self.system_metrics.get_current_metrics()
                operation.cpu_usage = metrics.get('cpu_percent')
                operation.memory_usage = metrics.get('memory_percent')
                operation.disk_usage = metrics.get('disk_usage_percent')
            except Exception as e:
                logger.warning(f"Failed to capture system metrics: {e}")
        
        # Log operation start
        self._log_operation(operation)
        
        return operation
    
    def update_operation(self, operation: PackageOperation, details: Dict[str, Any] = None):
        """Update an ongoing operation with additional details"""
        if details:
            operation.details.update(details)
        
        # Update system metrics if KADVLayer is available
        if self.system_metrics:
            try:
                metrics = self.system_metrics.get_current_metrics()
                operation.cpu_usage = metrics.get('cpu_percent')
                operation.memory_usage = metrics.get('memory_percent')
                operation.disk_usage = metrics.get('disk_usage_percent')
            except Exception as e:
                logger.warning(f"Failed to update system metrics: {e}")
    
    def complete_operation(self, operation: PackageOperation, success: bool, error: str = None):
        """Mark an operation as completed"""
        operation.complete(success, error)
        
        # Final system metrics update if KADVLayer is available
        if self.system_metrics:
            try:
                metrics = self.system_metrics.get_current_metrics()
                operation.cpu_usage = metrics.get('cpu_percent')
                operation.memory_usage = metrics.get('memory_percent')
                operation.disk_usage = metrics.get('disk_usage_percent')
            except Exception as e:
                logger.warning(f"Failed to capture final system metrics: {e}")
        
        # Add to operations list
        self.operations.append(operation)
        if operation == self.current_operation:
            self.current_operation = None
        
        # Log completion
        self._log_operation(operation)
        
        # Save metrics
        self._save_metrics()
        
        return operation
    
    def get_recent_operations(self, limit: int = 10, 
                             operation_type: str = None, 
                             package_name: str = None,
                             repo_name: str = None,
                             app_name: str = None) -> List[PackageOperation]:
        """Get recent operations with optional filtering"""
        filtered = self.operations
        
        if operation_type:
            filtered = [op for op in filtered if op.operation_type == operation_type]
        if package_name:
            filtered = [op for op in filtered if op.package_name == package_name]
        if repo_name:
            filtered = [op for op in filtered if op.repo_name == repo_name]
        if app_name:
            filtered = [op for op in filtered if op.app_name == app_name]
        
        # Return most recent first
        return sorted(filtered, key=lambda op: op.start_time, reverse=True)[:limit]
    
    def get_operation_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get operation statistics for the specified number of days"""
        # Calculate timestamp for N days ago
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        recent_ops = [op for op in self.operations if op.start_time >= cutoff_time]
        
        # Initialize stats structure
        stats = {
            'total_operations': len(recent_ops),
            'successful_operations': sum(1 for op in recent_ops if op.success),
            'failed_operations': sum(1 for op in recent_ops if op.success is False),
            'avg_duration': 0,
            'operation_types': {},
            'common_errors': {},
            'busiest_hour': None,
            'busiest_hour_count': 0,
            'total_cpu_time': 0
        }
        
        # Skip further processing if no operations
        if not recent_ops:
            return stats
        
        # Calculate average duration
        durations = [op.duration for op in recent_ops if op.end_time is not None]
        if durations:
            stats['avg_duration'] = sum(durations) / len(durations)
        
        # Count operation types
        for op in recent_ops:
            if op.operation_type not in stats['operation_types']:
                stats['operation_types'][op.operation_type] = {
                    'total': 0,
                    'success': 0,
                    'failure': 0,
                    'avg_duration': 0
                }
            
            type_stats = stats['operation_types'][op.operation_type]
            type_stats['total'] += 1
            
            if op.success:
                type_stats['success'] += 1
            elif op.success is False:
                type_stats['failure'] += 1
            
            if op.end_time is not None:
                if 'durations' not in type_stats:
                    type_stats['durations'] = []
                type_stats['durations'].append(op.duration)
        
        # Calculate average durations per operation type
        for op_type, type_stats in stats['operation_types'].items():
            if 'durations' in type_stats and type_stats['durations']:
                type_stats['avg_duration'] = sum(type_stats['durations']) / len(type_stats['durations'])
                del type_stats['durations']  # Remove intermediate data
        
        # Count common errors
        for op in recent_ops:
            if op.error:
                # Truncate long error messages
                error_key = op.error[:100] + ('...' if len(op.error) > 100 else '')
                stats['common_errors'][error_key] = stats['common_errors'].get(error_key, 0) + 1
        
        # Find busiest hour
        hour_counts = {}
        for op in recent_ops:
            hour = datetime.fromtimestamp(op.start_time).strftime('%Y-%m-%d %H')
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        if hour_counts:
            busiest_hour = max(hour_counts, key=hour_counts.get)
            stats['busiest_hour'] = busiest_hour
            stats['busiest_hour_count'] = hour_counts[busiest_hour]
        
        # Calculate total CPU time (approximation based on duration * cpu_usage)
        for op in recent_ops:
            if op.end_time is not None and op.cpu_usage is not None:
                # CPU usage is in percent, convert to decimal
                cpu_fraction = op.cpu_usage / 100
                stats['total_cpu_time'] += op.duration * cpu_fraction
        
        return stats
    
    def monitor_package_operation(self, operation_type: str, target_name: str = None, 
                                 is_package: bool = True, is_repo: bool = False, 
                                 is_app: bool = False):
        """
        Decorator for monitoring package operations
        
        Usage:
            @monitor.monitor_package_operation(PackageOperationType.INSTALL)
            def install_package(name, ...):
                ...
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Determine target name from args if not specified
                nonlocal target_name
                if target_name is None and len(args) > 1:
                    target_name = args[1]  # Assuming first arg is self/cls and second is name
                
                # Start monitoring
                package_name = target_name if is_package else None
                repo_name = target_name if is_repo else None
                app_name = target_name if is_app else None
                
                operation = self.start_operation(operation_type, package_name, repo_name, app_name)
                
                try:
                    # Call the original function
                    result = func(*args, **kwargs)
                    
                    # Determine success from result
                    success = True
                    error = None
                    
                    # Handle tuple returns (success, message)
                    if isinstance(result, tuple) and len(result) >= 2:
                        success = result[0]
                        if not success and len(result) >= 2:
                            error = str(result[1])
                    
                    # Complete the operation
                    self.complete_operation(operation, success, error)
                    
                    return result
                except Exception as e:
                    # Log the exception
                    self.complete_operation(operation, False, str(e))
                    raise
                
            return wrapper
        return decorator

# Create singleton instance
package_monitor = PackageMonitor.get_instance()

def monitor_operation(operation_type: str, package_name: str = None, 
                     repo_name: str = None, app_name: str = None):
    """
    Context manager for monitoring package operations
    
    Usage:
        with monitor_operation(PackageOperationType.INSTALL, package_name='example'):
            # Install package
    """
    class OperationContext:
        def __init__(self):
            self.operation = None
        
        def __enter__(self):
            self.operation = package_monitor.start_operation(
                operation_type, package_name, repo_name, app_name)
            return self.operation
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                package_monitor.complete_operation(self.operation, False, str(exc_val))
            else:
                package_monitor.complete_operation(self.operation, True)
            return False  # Don't suppress exceptions
    
    return OperationContext()

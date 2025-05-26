"""
KOS System Monitoring Framework

Provides comprehensive monitoring of system resources and processes:
- Resource usage tracking (CPU, memory, disk, network)
- Process monitoring with detailed metrics
- Service performance tracking
- Alert and notification system for resource thresholds
- Historical data collection and analysis
"""

import logging
import os
import threading
import time
import json
from typing import Dict, List, Any, Optional

# Initialize logging
logger = logging.getLogger('KOS.monitor')

# Import monitoring components
from .system_resource_monitor import (
    SystemResourceMonitor, 
    ResourceType,
    get_system_info
)

from .process_monitor import (
    ProcessMonitor,
    get_process_monitor,
    start_monitoring as start_process_monitoring,
    stop_monitoring as stop_process_monitoring,
    track_process,
    get_process_metrics
)

# Default directory for monitoring data
MONITOR_DIR = '/tmp/kos/monitor'
os.makedirs(MONITOR_DIR, exist_ok=True)

# Monitor status file
STATUS_FILE = os.path.join(MONITOR_DIR, 'status.json')

# Default instances
_system_monitor = None
_process_monitor = None
_monitor_thread = None
_stop_event = threading.Event()

def initialize():
    """Initialize the monitoring subsystem"""
    global _system_monitor, _process_monitor
    
    logger.info("Initializing KOS monitoring subsystem")
    
    # Create system monitor
    _system_monitor = SystemResourceMonitor()
    
    # Create process monitor (automatically created by get_process_monitor())
    _process_monitor = get_process_monitor()
    
    # Register service integration
    _register_service_integration()
    
    # Load previous state if available
    _load_status()
    
    # Start monitors if previously running
    if _get_saved_status().get('running', False):
        start_monitoring()
    
    return True

def _register_service_integration():
    """Register callbacks for service integration"""
    # Import service module
    from ..service import register_service_monitor, get_service_by_pid
    
    # Register callback for service status updates
    def service_resource_callback(resource_type, alert_type, message, data):
        """Handle resource alerts for services"""
        # If we have a PID, check if it's a service
        if isinstance(data, dict) and 'pid' in data:
            pid = data['pid']
            service_info = get_service_by_pid(pid)
            
            if service_info:
                logger.warning(f"Service {service_info['name']} affected: {message}")
                
                # Update service metrics
                from ..service import update_service_metrics
                update_service_metrics(service_info['name'], {
                    'resource_type': resource_type,
                    'alert_type': alert_type,
                    'message': message,
                    'data': data
                })
    
    # Register process callback
    def process_callback(pid, metrics, alert):
        """Handle process alerts for services"""
        # Check if process is a service
        service_info = get_service_by_pid(pid)
        if service_info:
            logger.warning(f"Service {service_info['name']} alert: {alert['message']}")
            
            # Update service metrics
            from ..service import update_service_metrics
            update_service_metrics(service_info['name'], {
                'alert': alert,
                'metrics': metrics
            })
    
    # Register callbacks
    for resource_type in [ResourceType.CPU, ResourceType.MEMORY, ResourceType.DISK]:
        _system_monitor.register_callback(resource_type, service_resource_callback)
    
    _process_monitor.register_callback(process_callback)
    
    # Register with service module
    register_service_monitor({
        'get_metrics': get_service_metrics,
        'track_service': track_service,
        'get_system_metrics': get_system_metrics
    })

def _get_saved_status():
    """Get the saved monitoring status"""
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {'running': False}
    
    return {'running': False}

def _save_status(status):
    """Save monitoring status"""
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f)
    except Exception as e:
        logger.error(f"Failed to save monitoring status: {e}")

def _load_status():
    """Load monitoring status"""
    status = _get_saved_status()
    
    # Set thresholds from saved status
    if 'thresholds' in status:
        for resource_type, threshold in status['thresholds'].items():
            if hasattr(_system_monitor, 'set_threshold'):
                _system_monitor.set_threshold(resource_type, threshold)

def start_monitoring():
    """Start the monitoring subsystem"""
    global _monitor_thread
    
    if _monitor_thread and _monitor_thread.is_alive():
        logger.warning("Monitoring is already running")
        return False
    
    logger.info("Starting KOS monitoring subsystem")
    
    # Start system resource monitor
    _system_monitor.start()
    
    # Start process monitor
    _process_monitor.start()
    
    # Start monitoring thread
    _stop_event.clear()
    _monitor_thread = threading.Thread(
        target=_monitoring_loop,
        daemon=True,
        name="KOSMonitoringThread"
    )
    _monitor_thread.start()
    
    # Save status
    _save_status({
        'running': True,
        'started_at': time.time(),
        'thresholds': _system_monitor.thresholds
    })
    
    return True

def stop_monitoring():
    """Stop the monitoring subsystem"""
    global _monitor_thread
    
    if not _monitor_thread or not _monitor_thread.is_alive():
        logger.warning("Monitoring is not running")
        return False
    
    logger.info("Stopping KOS monitoring subsystem")
    
    # Stop monitoring thread
    _stop_event.set()
    _monitor_thread.join(timeout=10.0)
    
    # Stop system resource monitor
    _system_monitor.stop()
    
    # Stop process monitor
    _process_monitor.stop()
    
    # Save status
    _save_status({'running': False})
    
    return True

def _monitoring_loop():
    """Main monitoring loop for data collection and persistence"""
    logger.info("Monitoring loop started")
    
    while not _stop_event.is_set():
        try:
            # Save monitoring data periodically
            _save_monitoring_data()
            
            # Check for alert conditions
            _check_alert_conditions()
            
            # Sleep until next iteration
            _stop_event.wait(60.0)  # Save data every minute
        
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            time.sleep(60.0)
    
    logger.info("Monitoring loop stopped")

def _save_monitoring_data():
    """Save monitoring data to persistent storage"""
    try:
        # Save system metrics
        system_metrics = _system_monitor.get_resource_usage()
        metrics_file = os.path.join(MONITOR_DIR, f"system_metrics_{int(time.time())}.json")
        with open(metrics_file, 'w') as f:
            json.dump(system_metrics, f)
        
        # Clean up old files (keep last 24 hours)
        _cleanup_old_files(MONITOR_DIR, 'system_metrics_', 24 * 60 * 60)
    
    except Exception as e:
        logger.error(f"Error saving monitoring data: {e}")

def _cleanup_old_files(directory, prefix, max_age):
    """Clean up old monitoring files"""
    try:
        current_time = time.time()
        for filename in os.listdir(directory):
            if filename.startswith(prefix) and filename.endswith('.json'):
                file_path = os.path.join(directory, filename)
                file_age = current_time - os.path.getmtime(file_path)
                
                if file_age > max_age:
                    os.remove(file_path)
    
    except Exception as e:
        logger.error(f"Error cleaning up monitoring files: {e}")

def _check_alert_conditions():
    """Check for alert conditions"""
    # This will be handled by the callbacks registered with the monitors
    pass

def track_service(service_name):
    """Track a service in the monitoring system"""
    from ..service import get_service_status
    
    service_info = get_service_status(service_name)
    if service_info and service_info.get('pid'):
        return track_process(service_info['pid'])
    
    return False

def get_service_metrics(service_name):
    """Get metrics for a service"""
    from ..service import get_service_status
    
    service_info = get_service_status(service_name)
    if service_info and service_info.get('pid'):
        return get_process_metrics(service_info['pid'])
    
    return None

def get_system_metrics():
    """Get current system metrics"""
    return _system_monitor.get_resource_usage()

def get_system_info():
    """Get system information"""
    return _system_monitor.get_system_info()

def set_threshold(resource_type, threshold):
    """Set a resource threshold"""
    result = _system_monitor.set_threshold(resource_type, threshold)
    
    if result:
        # Update saved thresholds
        status = _get_saved_status()
        if 'thresholds' not in status:
            status['thresholds'] = {}
        
        status['thresholds'][resource_type] = threshold
        _save_status(status)
    
    return result

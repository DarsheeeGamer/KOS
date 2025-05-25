"""
KOS Intrusion Detection System (IDS)

This module provides IDS capabilities for KOS, allowing detection
of suspicious activities and potential security breaches.
"""

import os
import sys
import time
import logging
import json
import threading
import re
import socket
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.security.ids')

# Lock for IDS operations
_ids_lock = threading.RLock()

# IDS database
_ids_events = []
_ids_rules = []

# IDS configuration
_ids_config = {
    'enabled': False,
    'alert_threshold': 3,  # Number of events before alert
    'max_events': 1000,    # Maximum number of events to store
    'check_interval': 300, # Default: check every 5 minutes
    'log_file': os.path.join(os.path.expanduser('~'), '.kos', 'security', 'ids.log'),
    'baseline_interval': 86400, # Default: rebaseline every 24 hours
}

# IDS background thread
_ids_thread = None
_ids_thread_stop = False

# Alert handlers
_alert_handlers = []


class IDSEvent:
    """Class representing an IDS event"""
    
    def __init__(self, timestamp: float, event_type: str, source: str, 
                 details: Dict[str, Any], severity: int = 1):
        """
        Initialize IDS event
        
        Args:
            timestamp: Event timestamp
            event_type: Event type
            source: Event source
            details: Event details
            severity: Event severity (1-10)
        """
        self.timestamp = timestamp
        self.event_type = event_type
        self.source = source
        self.details = details
        self.severity = severity
        self.processed = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'source': self.source,
            'details': self.details,
            'severity': self.severity,
            'processed': self.processed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IDSEvent':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            IDSEvent instance
        """
        event = cls(
            timestamp=data.get('timestamp', 0.0),
            event_type=data.get('event_type', ''),
            source=data.get('source', ''),
            details=data.get('details', {}),
            severity=data.get('severity', 1)
        )
        
        event.processed = data.get('processed', False)
        
        return event


class IDSRule:
    """Class representing an IDS rule"""
    
    def __init__(self, rule_id: str, name: str, description: str, 
                 event_type: str, pattern: str, severity: int = 1, 
                 enabled: bool = True):
        """
        Initialize IDS rule
        
        Args:
            rule_id: Rule ID
            name: Rule name
            description: Rule description
            event_type: Event type to match
            pattern: Pattern to match
            severity: Event severity (1-10)
            enabled: Rule enabled
        """
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.event_type = event_type
        self.pattern = pattern
        self.severity = severity
        self.enabled = enabled
        
        # Compile pattern
        try:
            self.pattern_re = re.compile(pattern)
        except re.error:
            logger.error(f"Invalid rule pattern: {pattern}")
            self.pattern_re = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'description': self.description,
            'event_type': self.event_type,
            'pattern': self.pattern,
            'severity': self.severity,
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IDSRule':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            IDSRule instance
        """
        return cls(
            rule_id=data.get('rule_id', ''),
            name=data.get('name', ''),
            description=data.get('description', ''),
            event_type=data.get('event_type', ''),
            pattern=data.get('pattern', ''),
            severity=data.get('severity', 1),
            enabled=data.get('enabled', True)
        )
    
    def matches(self, event: IDSEvent) -> bool:
        """
        Check if rule matches event
        
        Args:
            event: Event to check
        
        Returns:
            True if rule matches event, False otherwise
        """
        if not self.enabled:
            return False
        
        # Check event type
        if self.event_type != '*' and self.event_type != event.event_type:
            return False
        
        # Check pattern
        if self.pattern_re is None:
            return False
        
        # Convert event details to string for pattern matching
        event_str = json.dumps(event.details)
        
        return bool(self.pattern_re.search(event_str))


class IDSManager:
    """Manager for IDS operations"""
    
    @classmethod
    def add_event(cls, event_type: str, source: str, details: Dict[str, Any], 
                severity: int = 1) -> IDSEvent:
        """
        Add an event to the IDS database
        
        Args:
            event_type: Event type
            source: Event source
            details: Event details
            severity: Event severity (1-10)
        
        Returns:
            IDSEvent instance
        """
        with _ids_lock:
            # Create event
            event = IDSEvent(
                timestamp=time.time(),
                event_type=event_type,
                source=source,
                details=details,
                severity=severity
            )
            
            # Add to database
            _ids_events.append(event)
            
            # Limit number of events
            while len(_ids_events) > _ids_config['max_events']:
                _ids_events.pop(0)
            
            # Process event
            if _ids_config['enabled']:
                cls._process_event(event)
            
            return event
    
    @classmethod
    def add_rule(cls, rule_id: str, name: str, description: str, 
                event_type: str, pattern: str, severity: int = 1, 
                enabled: bool = True) -> Tuple[bool, Union[IDSRule, str]]:
        """
        Add a rule to the IDS database
        
        Args:
            rule_id: Rule ID
            name: Rule name
            description: Rule description
            event_type: Event type to match
            pattern: Pattern to match
            severity: Event severity (1-10)
            enabled: Rule enabled
        
        Returns:
            (success, rule or error message)
        """
        with _ids_lock:
            # Check if rule with this ID already exists
            for rule in _ids_rules:
                if rule.rule_id == rule_id:
                    return False, f"Rule with ID {rule_id} already exists"
            
            # Create rule
            try:
                rule = IDSRule(
                    rule_id=rule_id,
                    name=name,
                    description=description,
                    event_type=event_type,
                    pattern=pattern,
                    severity=severity,
                    enabled=enabled
                )
            except Exception as e:
                return False, str(e)
            
            # Check if pattern is valid
            if rule.pattern_re is None:
                return False, f"Invalid rule pattern: {pattern}"
            
            # Add to database
            _ids_rules.append(rule)
            
            logger.info(f"Added rule {rule_id} to IDS database")
            
            return True, rule
    
    @classmethod
    def remove_rule(cls, rule_id: str) -> Tuple[bool, str]:
        """
        Remove a rule from the IDS database
        
        Args:
            rule_id: Rule ID
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            # Find rule
            for i, rule in enumerate(_ids_rules):
                if rule.rule_id == rule_id:
                    # Remove rule
                    _ids_rules.pop(i)
                    
                    logger.info(f"Removed rule {rule_id} from IDS database")
                    
                    return True, f"Rule {rule_id} removed"
            
            return False, f"Rule {rule_id} not found"
    
    @classmethod
    def get_rule(cls, rule_id: str) -> Optional[IDSRule]:
        """
        Get a rule from the IDS database
        
        Args:
            rule_id: Rule ID
        
        Returns:
            IDSRule instance or None if not found
        """
        with _ids_lock:
            for rule in _ids_rules:
                if rule.rule_id == rule_id:
                    return rule
            
            return None
    
    @classmethod
    def list_rules(cls) -> List[IDSRule]:
        """
        List all rules
        
        Returns:
            List of IDSRule instances
        """
        with _ids_lock:
            return _ids_rules.copy()
    
    @classmethod
    def enable_rule(cls, rule_id: str) -> Tuple[bool, str]:
        """
        Enable a rule
        
        Args:
            rule_id: Rule ID
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            rule = cls.get_rule(rule_id)
            
            if rule is None:
                return False, f"Rule {rule_id} not found"
            
            rule.enabled = True
            
            logger.info(f"Enabled rule {rule_id}")
            
            return True, f"Rule {rule_id} enabled"
    
    @classmethod
    def disable_rule(cls, rule_id: str) -> Tuple[bool, str]:
        """
        Disable a rule
        
        Args:
            rule_id: Rule ID
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            rule = cls.get_rule(rule_id)
            
            if rule is None:
                return False, f"Rule {rule_id} not found"
            
            rule.enabled = False
            
            logger.info(f"Disabled rule {rule_id}")
            
            return True, f"Rule {rule_id} disabled"
    
    @classmethod
    def list_events(cls, limit: int = None, event_type: str = None, 
                   source: str = None, min_severity: int = None) -> List[IDSEvent]:
        """
        List events
        
        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type
            source: Filter by source
            min_severity: Filter by minimum severity
        
        Returns:
            List of IDSEvent instances
        """
        with _ids_lock:
            events = _ids_events.copy()
            
            # Apply filters
            if event_type is not None:
                events = [e for e in events if e.event_type == event_type]
            
            if source is not None:
                events = [e for e in events if e.source == source]
            
            if min_severity is not None:
                events = [e for e in events if e.severity >= min_severity]
            
            # Sort by timestamp (newest first)
            events.sort(key=lambda e: e.timestamp, reverse=True)
            
            # Apply limit
            if limit is not None:
                events = events[:limit]
            
            return events
    
    @classmethod
    def clear_events(cls) -> Tuple[bool, str]:
        """
        Clear all events
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            count = len(_ids_events)
            _ids_events.clear()
            
            logger.info(f"Cleared {count} events from IDS database")
            
            return True, f"Cleared {count} events"
    
    @classmethod
    def start_monitoring(cls) -> Tuple[bool, str]:
        """
        Start IDS monitoring
        
        Returns:
            (success, message)
        """
        global _ids_thread, _ids_thread_stop
        
        with _ids_lock:
            # Check if monitoring is already enabled
            if _ids_config['enabled']:
                return True, "IDS monitoring is already enabled"
            
            # Enable monitoring
            _ids_config['enabled'] = True
            _ids_thread_stop = False
            
            # Start monitoring thread
            if _ids_thread is None or not _ids_thread.is_alive():
                _ids_thread = threading.Thread(target=cls._monitoring_thread)
                _ids_thread.daemon = True
                _ids_thread.start()
            
            logger.info("IDS monitoring started")
            
            return True, "IDS monitoring started"
    
    @classmethod
    def stop_monitoring(cls) -> Tuple[bool, str]:
        """
        Stop IDS monitoring
        
        Returns:
            (success, message)
        """
        global _ids_thread, _ids_thread_stop
        
        with _ids_lock:
            # Check if monitoring is already disabled
            if not _ids_config['enabled']:
                return True, "IDS monitoring is already disabled"
            
            # Disable monitoring
            _ids_config['enabled'] = False
            _ids_thread_stop = True
            
            logger.info("IDS monitoring stopped")
            
            return True, "IDS monitoring stopped"
    
    @classmethod
    def set_check_interval(cls, interval: int) -> Tuple[bool, str]:
        """
        Set check interval
        
        Args:
            interval: Check interval in seconds
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            if interval < 1:
                return False, "Check interval must be at least 1 second"
            
            _ids_config['check_interval'] = interval
            
            logger.info(f"IDS check interval set to {interval} seconds")
            
            return True, f"Check interval set to {interval} seconds"
    
    @classmethod
    def set_alert_threshold(cls, threshold: int) -> Tuple[bool, str]:
        """
        Set alert threshold
        
        Args:
            threshold: Alert threshold
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            if threshold < 1:
                return False, "Alert threshold must be at least 1"
            
            _ids_config['alert_threshold'] = threshold
            
            logger.info(f"IDS alert threshold set to {threshold}")
            
            return True, f"Alert threshold set to {threshold}"
    
    @classmethod
    def set_max_events(cls, max_events: int) -> Tuple[bool, str]:
        """
        Set maximum number of events to store
        
        Args:
            max_events: Maximum number of events
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            if max_events < 1:
                return False, "Maximum events must be at least 1"
            
            _ids_config['max_events'] = max_events
            
            # Trim events if needed
            while len(_ids_events) > max_events:
                _ids_events.pop(0)
            
            logger.info(f"IDS max events set to {max_events}")
            
            return True, f"Maximum events set to {max_events}"
    
    @classmethod
    def save_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Save IDS database to file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            try:
                data = {
                    'config': _ids_config,
                    'rules': [rule.to_dict() for rule in _ids_rules],
                    'events': [event.to_dict() for event in _ids_events]
                }
                
                with open(db_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"IDS database saved to {db_file}"
            except Exception as e:
                logger.error(f"Error saving IDS database: {e}")
                return False, str(e)
    
    @classmethod
    def load_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Load IDS database from file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _ids_lock:
            try:
                if not os.path.exists(db_file):
                    return False, f"Database file {db_file} not found"
                
                with open(db_file, 'r') as f:
                    data = json.load(f)
                
                if 'config' in data:
                    _ids_config.update(data['config'])
                
                _ids_rules.clear()
                _ids_events.clear()
                
                if 'rules' in data:
                    for rule_data in data['rules']:
                        _ids_rules.append(IDSRule.from_dict(rule_data))
                
                if 'events' in data:
                    for event_data in data['events']:
                        _ids_events.append(IDSEvent.from_dict(event_data))
                
                return True, "IDS database loaded"
            except Exception as e:
                logger.error(f"Error loading IDS database: {e}")
                return False, str(e)
    
    @classmethod
    def add_alert_handler(cls, handler: Callable[[IDSEvent, IDSRule], None]) -> None:
        """
        Add alert handler
        
        Args:
            handler: Alert handler function
        """
        _alert_handlers.append(handler)
    
    @classmethod
    def _process_event(cls, event: IDSEvent) -> None:
        """
        Process an event
        
        Args:
            event: Event to process
        """
        if event.processed:
            return
        
        # Check rules
        for rule in _ids_rules:
            if rule.matches(event):
                # Rule matched
                event.severity = max(event.severity, rule.severity)
                
                # Log alert
                logger.warning(f"IDS Alert: Rule {rule.rule_id} ({rule.name}) matched event {event.event_type} from {event.source}")
                
                # Notify alert handlers
                for handler in _alert_handlers:
                    try:
                        handler(event, rule)
                    except Exception as e:
                        logger.error(f"Error in alert handler: {e}")
        
        # Mark as processed
        event.processed = True
    
    @classmethod
    def _monitoring_thread(cls) -> None:
        """Monitoring thread function"""
        logger.info("IDS monitoring thread started")
        
        # Track time of last baseline
        last_baseline = time.time()
        
        while not _ids_thread_stop:
            try:
                # Process unprocessed events
                with _ids_lock:
                    for event in _ids_events:
                        if not event.processed:
                            cls._process_event(event)
                
                # Check if it's time to rebaseline
                current_time = time.time()
                if current_time - last_baseline >= _ids_config['baseline_interval']:
                    cls._run_baseline()
                    last_baseline = current_time
            except Exception as e:
                logger.error(f"Error in IDS monitoring thread: {e}")
            
            # Sleep for check interval
            for _ in range(_ids_config['check_interval']):
                if _ids_thread_stop:
                    break
                time.sleep(1)
        
        logger.info("IDS monitoring thread stopped")
    
    @classmethod
    def _run_baseline(cls) -> None:
        """Run security baseline checks"""
        logger.info("Running IDS security baseline")
        
        # Check for common security issues
        
        # 1. Check for world-writable files in system directories
        cls._check_world_writable()
        
        # 2. Check for unusual listening ports
        cls._check_listening_ports()
        
        # 3. Check for suspicious processes
        cls._check_suspicious_processes()
        
        logger.info("Completed IDS security baseline")
    
    @classmethod
    def _check_world_writable(cls) -> None:
        """Check for world-writable files in system directories"""
        # In a full implementation, this would scan system directories
        # For now, just add a placeholder event
        cls.add_event(
            event_type="baseline",
            source="world_writable_check",
            details={"message": "World-writable file check completed", "count": 0}
        )
    
    @classmethod
    def _check_listening_ports(cls) -> None:
        """Check for unusual listening ports"""
        # In a full implementation, this would check netstat
        # For now, just add a placeholder event
        try:
            listening_ports = []
            
            # Try to get listening ports
            for port in range(1, 1025):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.1)
                    result = sock.connect_ex(('127.0.0.1', port))
                    if result == 0:
                        listening_ports.append(port)
                    sock.close()
                except:
                    pass
            
            cls.add_event(
                event_type="baseline",
                source="port_check",
                details={"message": "Listening port check completed", "ports": listening_ports}
            )
        except Exception as e:
            logger.error(f"Error checking listening ports: {e}")
    
    @classmethod
    def _check_suspicious_processes(cls) -> None:
        """Check for suspicious processes"""
        # In a full implementation, this would scan process list
        # For now, just add a placeholder event
        cls.add_event(
            event_type="baseline",
            source="process_check",
            details={"message": "Suspicious process check completed", "count": 0}
        )


def log_handler(event: IDSEvent, rule: IDSRule) -> None:
    """
    Log alert to IDS log file
    
    Args:
        event: Event that triggered alert
        rule: Rule that matched event
    """
    try:
        log_file = _ids_config['log_file']
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # Format log entry
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))
        log_entry = f"{timestamp} - Rule: {rule.rule_id} ({rule.name}) - Event: {event.event_type} - Source: {event.source} - Severity: {event.severity}\n"
        log_entry += f"  Details: {json.dumps(event.details)}\n"
        
        # Write to log file
        with open(log_file, 'a') as f:
            f.write(log_entry)
    except Exception as e:
        logger.error(f"Error writing to IDS log file: {e}")


def create_default_rules() -> None:
    """Create default IDS rules"""
    # Authentication failure rule
    IDSManager.add_rule(
        rule_id="AUTH001",
        name="Authentication Failure",
        description="Detects authentication failures",
        event_type="auth",
        pattern=r"failure|failed|invalid",
        severity=3,
        enabled=True
    )
    
    # Privilege escalation rule
    IDSManager.add_rule(
        rule_id="PRIV001",
        name="Privilege Escalation",
        description="Detects privilege escalation attempts",
        event_type="user",
        pattern=r"root|sudo|su|superuser",
        severity=5,
        enabled=True
    )
    
    # File access rule
    IDSManager.add_rule(
        rule_id="FILE001",
        name="Sensitive File Access",
        description="Detects access to sensitive files",
        event_type="file",
        pattern=r"password|shadow|key|cert|token",
        severity=4,
        enabled=True
    )
    
    # Network connection rule
    IDSManager.add_rule(
        rule_id="NET001",
        name="Unusual Port Access",
        description="Detects connections to unusual ports",
        event_type="network",
        pattern=r"port.*:(21|22|23|25|3389)",
        severity=3,
        enabled=True
    )
    
    # Process execution rule
    IDSManager.add_rule(
        rule_id="PROC001",
        name="Suspicious Process Execution",
        description="Detects execution of suspicious processes",
        event_type="process",
        pattern=r"nc|netcat|nmap|wget|curl|telnet",
        severity=4,
        enabled=True
    )
    
    # Baseline rule
    IDSManager.add_rule(
        rule_id="BASE001",
        name="Baseline Anomaly",
        description="Detects anomalies in security baseline",
        event_type="baseline",
        pattern=r"count.*[1-9][0-9]*|failed|warning|error",
        severity=2,
        enabled=True
    )


def initialize() -> None:
    """Initialize IDS system"""
    logger.info("Initializing IDS system")
    
    # Create IDS directory
    ids_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(ids_dir, exist_ok=True)
    
    # Register alert handlers
    IDSManager.add_alert_handler(log_handler)
    
    # Load database if it exists
    db_file = os.path.join(ids_dir, 'ids.json')
    if os.path.exists(db_file):
        IDSManager.load_database(db_file)
    else:
        # Create default rules
        create_default_rules()
        
        # Save database
        IDSManager.save_database(db_file)
    
    logger.info("IDS system initialized")


# Initialize on module load
initialize()

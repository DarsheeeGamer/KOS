"""
KOS Security Audit System

This module provides a centralized audit logging system for KOS,
recording security-relevant events for compliance and forensic analysis.
"""

import os
import sys
import time
import logging
import json
import threading
import hashlib
import base64
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.security.audit')

# Lock for audit operations
_audit_lock = threading.RLock()

# Audit configuration
_audit_config = {
    'enabled': True,
    'log_file': os.path.join(os.path.expanduser('~'), '.kos', 'security', 'audit.log'),
    'json_file': os.path.join(os.path.expanduser('~'), '.kos', 'security', 'audit.json'),
    'rotation_size': 10 * 1024 * 1024,  # 10MB
    'max_log_files': 10,
    'hash_chain': True,
    'sync_write': True,
    'event_categories': [
        'authentication', 'authorization', 'file_access', 'network',
        'process', 'security_config', 'system', 'user_management'
    ]
}

# Audit data
_audit_events = []
_last_event_hash = None

# Event handlers
_event_handlers = []


class AuditEvent:
    """Class representing an audit event"""
    
    def __init__(self, timestamp: float, category: str, event_type: str, 
                 user: str, source: str, details: Dict[str, Any], 
                 severity: int = 1, outcome: str = 'success',
                 prev_hash: str = None):
        """
        Initialize audit event
        
        Args:
            timestamp: Event timestamp
            category: Event category
            event_type: Event type
            user: Username
            source: Event source
            details: Event details
            severity: Event severity (1-10)
            outcome: Event outcome (success, failure, etc.)
            prev_hash: Hash of previous event (for chain of custody)
        """
        self.timestamp = timestamp
        self.category = category
        self.event_type = event_type
        self.user = user
        self.source = source
        self.details = details
        self.severity = severity
        self.outcome = outcome
        self.prev_hash = prev_hash
        self.event_hash = None
        
        # Generate event hash
        self._generate_hash()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': self.timestamp,
            'category': self.category,
            'event_type': self.event_type,
            'user': self.user,
            'source': self.source,
            'details': self.details,
            'severity': self.severity,
            'outcome': self.outcome,
            'prev_hash': self.prev_hash,
            'event_hash': self.event_hash
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEvent':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            AuditEvent instance
        """
        event = cls(
            timestamp=data.get('timestamp', 0.0),
            category=data.get('category', ''),
            event_type=data.get('event_type', ''),
            user=data.get('user', ''),
            source=data.get('source', ''),
            details=data.get('details', {}),
            severity=data.get('severity', 1),
            outcome=data.get('outcome', 'success'),
            prev_hash=data.get('prev_hash')
        )
        
        # Override generated hash with stored hash
        if 'event_hash' in data:
            event.event_hash = data['event_hash']
        
        return event
    
    def _generate_hash(self) -> None:
        """Generate event hash"""
        # Create string representation for hashing
        hash_str = f"{self.timestamp}|{self.category}|{self.event_type}|{self.user}|{self.source}|"
        hash_str += f"{json.dumps(self.details, sort_keys=True)}|{self.severity}|{self.outcome}|{self.prev_hash}"
        
        # Generate hash
        hash_obj = hashlib.sha256()
        hash_obj.update(hash_str.encode('utf-8'))
        self.event_hash = hash_obj.hexdigest()


class AuditSystem:
    """Manager for audit operations"""
    
    @classmethod
    def add_event(cls, category: str, event_type: str, user: str, source: str, 
                details: Dict[str, Any], severity: int = 1, 
                outcome: str = 'success') -> AuditEvent:
        """
        Add an audit event
        
        Args:
            category: Event category
            event_type: Event type
            user: Username
            source: Event source
            details: Event details
            severity: Event severity (1-10)
            outcome: Event outcome (success, failure, etc.)
        
        Returns:
            AuditEvent instance
        """
        with _audit_lock:
            global _last_event_hash
            
            # Check if auditing is enabled
            if not _audit_config['enabled']:
                # Create event but don't log it
                event = AuditEvent(
                    timestamp=time.time(),
                    category=category,
                    event_type=event_type,
                    user=user,
                    source=source,
                    details=details,
                    severity=severity,
                    outcome=outcome
                )
                return event
            
            # Create event
            event = AuditEvent(
                timestamp=time.time(),
                category=category,
                event_type=event_type,
                user=user,
                source=source,
                details=details,
                severity=severity,
                outcome=outcome,
                prev_hash=_last_event_hash
            )
            
            # Update last event hash
            _last_event_hash = event.event_hash
            
            # Add to events list
            _audit_events.append(event)
            
            # Log event
            cls._log_event(event)
            
            # Notify event handlers
            for handler in _event_handlers:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in audit event handler: {e}")
            
            return event
    
    @classmethod
    def _log_event(cls, event: AuditEvent) -> None:
        """
        Log an audit event
        
        Args:
            event: Audit event
        """
        try:
            # Format log entry
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))
            log_entry = f"{timestamp} [{event.category}] {event.event_type} (User: {event.user}, Source: {event.source}, Outcome: {event.outcome})"
            
            if event.details:
                log_entry += f" - Details: {json.dumps(event.details)}"
            
            # Check for log rotation
            log_file = _audit_config['log_file']
            
            if os.path.exists(log_file) and os.path.getsize(log_file) > _audit_config['rotation_size']:
                cls._rotate_log()
            
            # Write to log file
            with open(log_file, 'a') as f:
                f.write(log_entry + '\n')
                if _audit_config['sync_write']:
                    f.flush()
                    os.fsync(f.fileno())
            
            # Append to JSON file
            json_file = _audit_config['json_file']
            
            try:
                # Read existing events
                events = []
                if os.path.exists(json_file):
                    with open(json_file, 'r') as f:
                        events = json.load(f)
                
                # Append new event
                events.append(event.to_dict())
                
                # Write updated events
                with open(json_file, 'w') as f:
                    json.dump(events, f, indent=2)
                    if _audit_config['sync_write']:
                        f.flush()
                        os.fsync(f.fileno())
            except Exception as e:
                logger.error(f"Error writing to JSON audit file: {e}")
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    @classmethod
    def _rotate_log(cls) -> None:
        """Rotate audit log file"""
        try:
            log_file = _audit_config['log_file']
            max_logs = _audit_config['max_log_files']
            
            # Remove oldest log if we've reached the maximum
            for i in range(max_logs - 1, 0, -1):
                old_log = f"{log_file}.{i}"
                new_log = f"{log_file}.{i+1}"
                
                if i == max_logs - 1 and os.path.exists(old_log):
                    os.remove(old_log)
                
                if os.path.exists(old_log):
                    os.rename(old_log, new_log)
            
            # Rename current log
            if os.path.exists(log_file):
                os.rename(log_file, f"{log_file}.1")
        except Exception as e:
            logger.error(f"Error rotating audit log: {e}")
    
    @classmethod
    def get_events(cls, start_time: float = None, end_time: float = None,
                  category: str = None, event_type: str = None,
                  user: str = None, source: str = None,
                  min_severity: int = None, outcome: str = None,
                  limit: int = None) -> List[AuditEvent]:
        """
        Get audit events with filters
        
        Args:
            start_time: Filter by start time
            end_time: Filter by end time
            category: Filter by category
            event_type: Filter by event type
            user: Filter by user
            source: Filter by source
            min_severity: Filter by minimum severity
            outcome: Filter by outcome
            limit: Maximum number of events to return
        
        Returns:
            List of AuditEvent instances
        """
        with _audit_lock:
            events = _audit_events.copy()
            
            # Apply filters
            if start_time is not None:
                events = [e for e in events if e.timestamp >= start_time]
            
            if end_time is not None:
                events = [e for e in events if e.timestamp <= end_time]
            
            if category is not None:
                events = [e for e in events if e.category == category]
            
            if event_type is not None:
                events = [e for e in events if e.event_type == event_type]
            
            if user is not None:
                events = [e for e in events if e.user == user]
            
            if source is not None:
                events = [e for e in events if e.source == source]
            
            if min_severity is not None:
                events = [e for e in events if e.severity >= min_severity]
            
            if outcome is not None:
                events = [e for e in events if e.outcome == outcome]
            
            # Sort by timestamp (newest first)
            events.sort(key=lambda e: e.timestamp, reverse=True)
            
            # Apply limit
            if limit is not None:
                events = events[:limit]
            
            return events
    
    @classmethod
    def verify_integrity(cls) -> Tuple[bool, Optional[str]]:
        """
        Verify the integrity of the audit log
        
        Returns:
            (integrity_intact, error_message)
        """
        with _audit_lock:
            if not _audit_events:
                return True, None
            
            prev_hash = None
            
            for i, event in enumerate(_audit_events):
                # Skip hash verification if hash chaining is disabled
                if not _audit_config['hash_chain']:
                    continue
                
                # Check previous hash
                if i > 0 and event.prev_hash != prev_hash:
                    return False, f"Hash chain broken at event {i}: expected {prev_hash}, got {event.prev_hash}"
                
                # Verify event hash
                original_hash = event.event_hash
                event._generate_hash()
                if event.event_hash != original_hash:
                    return False, f"Event hash mismatch at event {i}: expected {original_hash}, got {event.event_hash}"
                
                prev_hash = event.event_hash
            
            return True, None
    
    @classmethod
    def clear_events(cls) -> Tuple[bool, str]:
        """
        Clear all events
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            count = len(_audit_events)
            _audit_events.clear()
            
            global _last_event_hash
            _last_event_hash = None
            
            logger.info(f"Cleared {count} audit events")
            
            return True, f"Cleared {count} audit events"
    
    @classmethod
    def enable(cls) -> Tuple[bool, str]:
        """
        Enable auditing
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            if _audit_config['enabled']:
                return True, "Auditing is already enabled"
            
            _audit_config['enabled'] = True
            
            # Add audit enabled event
            cls.add_event(
                category='system',
                event_type='audit_enabled',
                user='system',
                source='audit_system',
                details={'message': 'Audit system enabled'},
                severity=1,
                outcome='success'
            )
            
            logger.info("Audit system enabled")
            
            return True, "Auditing enabled"
    
    @classmethod
    def disable(cls) -> Tuple[bool, str]:
        """
        Disable auditing
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            if not _audit_config['enabled']:
                return True, "Auditing is already disabled"
            
            # Add audit disabled event
            cls.add_event(
                category='system',
                event_type='audit_disabled',
                user='system',
                source='audit_system',
                details={'message': 'Audit system disabled'},
                severity=1,
                outcome='success'
            )
            
            _audit_config['enabled'] = False
            
            logger.info("Audit system disabled")
            
            return True, "Auditing disabled"
    
    @classmethod
    def set_log_file(cls, log_file: str) -> Tuple[bool, str]:
        """
        Set audit log file
        
        Args:
            log_file: Log file path
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            _audit_config['log_file'] = log_file
            
            logger.info(f"Audit log file set to {log_file}")
            
            return True, f"Audit log file set to {log_file}"
    
    @classmethod
    def set_json_file(cls, json_file: str) -> Tuple[bool, str]:
        """
        Set audit JSON file
        
        Args:
            json_file: JSON file path
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            _audit_config['json_file'] = json_file
            
            logger.info(f"Audit JSON file set to {json_file}")
            
            return True, f"Audit JSON file set to {json_file}"
    
    @classmethod
    def set_rotation_size(cls, size: int) -> Tuple[bool, str]:
        """
        Set log rotation size
        
        Args:
            size: Rotation size in bytes
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            if size < 1024:
                return False, "Rotation size must be at least 1KB"
            
            _audit_config['rotation_size'] = size
            
            logger.info(f"Audit log rotation size set to {size} bytes")
            
            return True, f"Audit log rotation size set to {size} bytes"
    
    @classmethod
    def set_max_log_files(cls, max_files: int) -> Tuple[bool, str]:
        """
        Set maximum number of log files
        
        Args:
            max_files: Maximum number of log files
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            if max_files < 1:
                return False, "Maximum log files must be at least 1"
            
            _audit_config['max_log_files'] = max_files
            
            logger.info(f"Audit maximum log files set to {max_files}")
            
            return True, f"Audit maximum log files set to {max_files}"
    
    @classmethod
    def set_hash_chain(cls, enabled: bool) -> Tuple[bool, str]:
        """
        Enable or disable hash chaining
        
        Args:
            enabled: Enable hash chaining
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            _audit_config['hash_chain'] = enabled
            
            logger.info(f"Audit hash chaining {'enabled' if enabled else 'disabled'}")
            
            return True, f"Audit hash chaining {'enabled' if enabled else 'disabled'}"
    
    @classmethod
    def set_sync_write(cls, enabled: bool) -> Tuple[bool, str]:
        """
        Enable or disable synchronous writes
        
        Args:
            enabled: Enable synchronous writes
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            _audit_config['sync_write'] = enabled
            
            logger.info(f"Audit synchronous writes {'enabled' if enabled else 'disabled'}")
            
            return True, f"Audit synchronous writes {'enabled' if enabled else 'disabled'}"
    
    @classmethod
    def add_event_handler(cls, handler: Callable[[AuditEvent], None]) -> None:
        """
        Add event handler
        
        Args:
            handler: Event handler function
        """
        _event_handlers.append(handler)
    
    @classmethod
    def save_config(cls, config_file: str) -> Tuple[bool, str]:
        """
        Save audit configuration to file
        
        Args:
            config_file: Config file path
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            try:
                with open(config_file, 'w') as f:
                    json.dump(_audit_config, f, indent=2)
                
                return True, f"Audit configuration saved to {config_file}"
            except Exception as e:
                logger.error(f"Error saving audit configuration: {e}")
                return False, str(e)
    
    @classmethod
    def load_config(cls, config_file: str) -> Tuple[bool, str]:
        """
        Load audit configuration from file
        
        Args:
            config_file: Config file path
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            try:
                if not os.path.exists(config_file):
                    return False, f"Config file {config_file} not found"
                
                with open(config_file, 'r') as f:
                    config = json.load(f)
                
                _audit_config.update(config)
                
                return True, "Audit configuration loaded"
            except Exception as e:
                logger.error(f"Error loading audit configuration: {e}")
                return False, str(e)
    
    @classmethod
    def export_events(cls, export_file: str, format: str = 'json') -> Tuple[bool, str]:
        """
        Export audit events to file
        
        Args:
            export_file: Export file path
            format: Export format (json, csv)
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            try:
                if format == 'json':
                    # Export as JSON
                    with open(export_file, 'w') as f:
                        events_data = [event.to_dict() for event in _audit_events]
                        json.dump(events_data, f, indent=2)
                elif format == 'csv':
                    # Export as CSV
                    import csv
                    with open(export_file, 'w', newline='') as f:
                        writer = csv.writer(f)
                        
                        # Write header
                        writer.writerow([
                            'Timestamp', 'Category', 'Event Type', 'User', 'Source',
                            'Details', 'Severity', 'Outcome', 'Event Hash'
                        ])
                        
                        # Write events
                        for event in _audit_events:
                            writer.writerow([
                                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp)),
                                event.category,
                                event.event_type,
                                event.user,
                                event.source,
                                json.dumps(event.details),
                                event.severity,
                                event.outcome,
                                event.event_hash
                            ])
                else:
                    return False, f"Unsupported export format: {format}"
                
                return True, f"Exported {len(_audit_events)} audit events to {export_file}"
            except Exception as e:
                logger.error(f"Error exporting audit events: {e}")
                return False, str(e)
    
    @classmethod
    def import_events(cls, import_file: str) -> Tuple[bool, str]:
        """
        Import audit events from file
        
        Args:
            import_file: Import file path
        
        Returns:
            (success, message)
        """
        with _audit_lock:
            try:
                if not os.path.exists(import_file):
                    return False, f"Import file {import_file} not found"
                
                with open(import_file, 'r') as f:
                    events_data = json.load(f)
                
                # Clear existing events
                _audit_events.clear()
                
                # Import events
                for event_data in events_data:
                    _audit_events.append(AuditEvent.from_dict(event_data))
                
                # Update last event hash
                global _last_event_hash
                if _audit_events:
                    _last_event_hash = _audit_events[-1].event_hash
                
                return True, f"Imported {len(_audit_events)} audit events"
            except Exception as e:
                logger.error(f"Error importing audit events: {e}")
                return False, str(e)


def console_handler(event: AuditEvent) -> None:
    """
    Log high-severity events to console
    
    Args:
        event: Audit event
    """
    if event.severity >= 8:
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(event.timestamp))
        print(f"HIGH SEVERITY AUDIT EVENT: {timestamp} [{event.category}] {event.event_type} "
              f"(User: {event.user}, Source: {event.source}, Outcome: {event.outcome})")


def initialize() -> None:
    """Initialize audit system"""
    logger.info("Initializing audit system")
    
    # Create audit directory
    audit_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(audit_dir, exist_ok=True)
    
    # Register event handlers
    AuditSystem.add_event_handler(console_handler)
    
    # Load config if it exists
    config_file = os.path.join(audit_dir, 'audit_config.json')
    if os.path.exists(config_file):
        AuditSystem.load_config(config_file)
    else:
        # Save default config
        AuditSystem.save_config(config_file)
    
    # Load events if they exist
    json_file = _audit_config['json_file']
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                events_data = json.load(f)
            
            for event_data in events_data:
                _audit_events.append(AuditEvent.from_dict(event_data))
            
            # Update last event hash
            global _last_event_hash
            if _audit_events:
                _last_event_hash = _audit_events[-1].event_hash
        except Exception as e:
            logger.error(f"Error loading audit events: {e}")
    
    # Add startup event
    AuditSystem.add_event(
        category='system',
        event_type='system_startup',
        user='system',
        source='audit_system',
        details={'message': 'Audit system initialized'},
        severity=1,
        outcome='success'
    )
    
    logger.info("Audit system initialized")


# Initialize on module load
initialize()

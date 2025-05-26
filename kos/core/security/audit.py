"""
Audit System for KOS

This module provides a comprehensive audit logging system for tracking security-relevant
events across the KOS system. It implements features similar to Linux's auditd.

Features:
- Event logging for security-relevant actions
- Configurable audit rules
- Structured event storage and querying
- Integration with system components
"""

import os
import json
import time
import uuid
import logging
import threading
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
AUDIT_LOG_PATH = os.path.join(KOS_ROOT, 'var/log/audit/audit.log')
AUDIT_RULES_PATH = os.path.join(KOS_ROOT, 'etc/audit/audit.rules')

# Ensure directories exist
os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(AUDIT_RULES_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    USER_AUTH = "USER_AUTH"
    USER_AUTH_FAILURE = "USER_AUTH_FAILURE"
    USER_LOGOUT = "USER_LOGOUT"
    
    # User management events
    USER_ADD = "USER_ADD"
    USER_DEL = "USER_DEL"
    USER_MODIFY = "USER_MODIFY"
    GROUP_ADD = "GROUP_ADD"
    GROUP_DEL = "GROUP_DEL"
    GROUP_MODIFY = "GROUP_MODIFY"
    
    # Permission events
    PERM_CHANGE = "PERM_CHANGE"
    OWNER_CHANGE = "OWNER_CHANGE"
    ACL_CHANGE = "ACL_CHANGE"
    CAP_CHANGE = "CAP_CHANGE"
    
    # File system events
    FILE_CREATE = "FILE_CREATE"
    FILE_DELETE = "FILE_DELETE"
    FILE_MODIFY = "FILE_MODIFY"
    FILE_ACCESS = "FILE_ACCESS"
    
    # Process events
    PROCESS_START = "PROCESS_START"
    PROCESS_END = "PROCESS_END"
    PROCESS_KILL = "PROCESS_KILL"
    
    # System events
    SYSTEM_BOOT = "SYSTEM_BOOT"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    
    # Container events
    CONTAINER_CREATE = "CONTAINER_CREATE"
    CONTAINER_START = "CONTAINER_START"
    CONTAINER_STOP = "CONTAINER_STOP"
    CONTAINER_REMOVE = "CONTAINER_REMOVE"
    
    # Network events
    NETWORK_CONNECT = "NETWORK_CONNECT"
    NETWORK_DISCONNECT = "NETWORK_DISCONNECT"
    FIREWALL_CHANGE = "FIREWALL_CHANGE"
    
    # Service events
    SERVICE_START = "SERVICE_START"
    SERVICE_STOP = "SERVICE_STOP"
    SERVICE_RESTART = "SERVICE_RESTART"
    
    # Security events
    SECCOMP_VIOLATION = "SECCOMP_VIOLATION"
    MAC_VIOLATION = "MAC_VIOLATION"
    CAPABILITY_VIOLATION = "CAPABILITY_VIOLATION"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AuditManager:
    """
    Manages the audit system for KOS.
    
    This class provides a comprehensive audit logging system for tracking
    security-relevant events and actions across the KOS system.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AuditManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the AuditManager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._rules = self._load_rules()
        self._log_lock = threading.Lock()
        
        # Ensure log directory exists
        os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)
    
    def _load_rules(self) -> List[Dict[str, Any]]:
        """Load audit rules from disk."""
        if os.path.exists(AUDIT_RULES_PATH):
            try:
                with open(AUDIT_RULES_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted audit rules file. Creating new one.")
        
        # Default rules
        default_rules = [
            {
                "type": AuditEventType.USER_AUTH_FAILURE.value,
                "enabled": True,
                "severity": AuditSeverity.WARNING.value
            },
            {
                "type": AuditEventType.SECCOMP_VIOLATION.value,
                "enabled": True,
                "severity": AuditSeverity.CRITICAL.value
            },
            {
                "type": AuditEventType.MAC_VIOLATION.value,
                "enabled": True,
                "severity": AuditSeverity.CRITICAL.value
            }
        ]
        
        # Save default rules
        os.makedirs(os.path.dirname(AUDIT_RULES_PATH), exist_ok=True)
        with open(AUDIT_RULES_PATH, 'w') as f:
            json.dump(default_rules, f, indent=2)
        
        return default_rules
    
    def _save_rules(self):
        """Save audit rules to disk."""
        with open(AUDIT_RULES_PATH, 'w') as f:
            json.dump(self._rules, f, indent=2)
    
    def should_audit(self, event_type: AuditEventType) -> bool:
        """
        Check if an event type should be audited based on rules.
        
        Args:
            event_type: Type of event to check
            
        Returns:
            bool: Whether the event should be audited
        """
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        
        for rule in self._rules:
            if rule["type"] == event_type_str and rule["enabled"]:
                return True
        
        # Default to audit all events if no specific rule
        return True
    
    def get_severity(self, event_type: AuditEventType) -> AuditSeverity:
        """
        Get the severity level for an event type.
        
        Args:
            event_type: Type of event
            
        Returns:
            AuditSeverity: Severity level for the event
        """
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        
        for rule in self._rules:
            if rule["type"] == event_type_str:
                return AuditSeverity(rule["severity"])
        
        # Default severity
        return AuditSeverity.INFO
    
    def add_rule(self, event_type: AuditEventType, enabled: bool = True, 
                severity: AuditSeverity = AuditSeverity.INFO) -> bool:
        """
        Add a new audit rule.
        
        Args:
            event_type: Type of event to audit
            enabled: Whether the rule is enabled
            severity: Severity level for the event
            
        Returns:
            bool: Success or failure
        """
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        severity_str = severity.value if isinstance(severity, AuditSeverity) else severity
        
        # Check if rule already exists
        for rule in self._rules:
            if rule["type"] == event_type_str:
                rule["enabled"] = enabled
                rule["severity"] = severity_str
                self._save_rules()
                return True
        
        # Add new rule
        self._rules.append({
            "type": event_type_str,
            "enabled": enabled,
            "severity": severity_str
        })
        
        self._save_rules()
        return True
    
    def remove_rule(self, event_type: AuditEventType) -> bool:
        """
        Remove an audit rule.
        
        Args:
            event_type: Type of event to remove rule for
            
        Returns:
            bool: Success or failure
        """
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        
        initial_len = len(self._rules)
        self._rules = [rule for rule in self._rules if rule["type"] != event_type_str]
        
        if len(self._rules) < initial_len:
            self._save_rules()
            return True
        return False
    
    def log_event(self, event_type: AuditEventType, user: str, 
                 details: Dict[str, Any] = None, success: bool = True) -> bool:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            user: Username that triggered the event
            details: Additional event details
            success: Whether the action was successful
            
        Returns:
            bool: Success or failure
        """
        if not self.should_audit(event_type):
            return True
        
        event_type_str = event_type.value if isinstance(event_type, AuditEventType) else event_type
        severity = self.get_severity(event_type)
        
        # Build event record
        event = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time()),
            "type": event_type_str,
            "severity": severity.value,
            "user": user,
            "success": success,
            "details": details or {}
        }
        
        # Log to file
        with self._log_lock:
            try:
                with open(AUDIT_LOG_PATH, 'a') as f:
                    f.write(json.dumps(event) + '\n')
                return True
            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")
                return False
    
    def query_logs(self, start_time: Optional[int] = None, 
                  end_time: Optional[int] = None,
                  event_types: Optional[List[AuditEventType]] = None,
                  user: Optional[str] = None,
                  success: Optional[bool] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        Query audit logs with filters.
        
        Args:
            start_time: Start timestamp (Unix time)
            end_time: End timestamp (Unix time)
            event_types: List of event types to include
            user: Filter by username
            success: Filter by success status
            limit: Maximum number of results
            
        Returns:
            List[Dict[str, Any]]: Matching audit events
        """
        if not os.path.exists(AUDIT_LOG_PATH):
            return []
        
        # Convert event types to strings
        event_type_strs = None
        if event_types:
            event_type_strs = [
                et.value if isinstance(et, AuditEventType) else et
                for et in event_types
            ]
        
        # Read and filter logs
        results = []
        try:
            with open(AUDIT_LOG_PATH, 'r') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        event = json.loads(line)
                        
                        # Apply filters
                        if start_time is not None and event["timestamp"] < start_time:
                            continue
                        if end_time is not None and event["timestamp"] > end_time:
                            continue
                        if event_type_strs is not None and event["type"] not in event_type_strs:
                            continue
                        if user is not None and event["user"] != user:
                            continue
                        if success is not None and event["success"] != success:
                            continue
                        
                        results.append(event)
                        
                        if len(results) >= limit:
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid audit log entry: {line}")
        except Exception as e:
            logger.error(f"Failed to read audit logs: {e}")
        
        return results
    
    def clear_logs(self) -> bool:
        """
        Clear all audit logs.
        
        Returns:
            bool: Success or failure
        """
        try:
            with open(AUDIT_LOG_PATH, 'w') as f:
                pass
            return True
        except Exception as e:
            logger.error(f"Failed to clear audit logs: {e}")
            return False

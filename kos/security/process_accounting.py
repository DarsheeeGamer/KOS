"""
KOS Process Accounting and Auditing Module

This module provides Unix-like process accounting, allowing system administrators
to track resource usage and process execution on the system.
"""

import os
import sys
import time
import json
import logging
import threading
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager
from kos.security.auth import get_current_uid, get_current_user

# Set up logging
logger = logging.getLogger('KOS.security.process_accounting')

# Constants
DEFAULT_ACCOUNTING_FILE = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'pacct')
DEFAULT_SUMMARY_FILE = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'pacct_summary')
DEFAULT_AUDIT_FILE = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'audit.log')

# Lock for accounting operations
_accounting_lock = threading.RLock()

# Global flag to track if accounting is enabled
_accounting_enabled = False
_auditing_enabled = False


class ProcessRecord:
    """Class representing an accounting record for a process"""
    
    def __init__(self, command: str, uid: int, start_time: float, end_time: float = None,
                exit_code: int = None, cpu_time: float = 0.0, memory_usage: int = 0,
                io_read: int = 0, io_write: int = 0):
        """
        Initialize a process accounting record
        
        Args:
            command: Command that was executed
            uid: User ID that executed the command
            start_time: Process start time (unix timestamp)
            end_time: Process end time (unix timestamp) or None if still running
            exit_code: Process exit code or None if still running
            cpu_time: CPU time used (seconds)
            memory_usage: Memory usage (KB)
            io_read: I/O bytes read
            io_write: I/O bytes written
        """
        self.command = command
        self.uid = uid
        self.start_time = start_time
        self.end_time = end_time
        self.exit_code = exit_code
        self.cpu_time = cpu_time
        self.memory_usage = memory_usage
        self.io_read = io_read
        self.io_write = io_write
        
        # Additional metadata
        self.hostname = os.uname().nodename if hasattr(os, 'uname') else platform.node()
        self.pid = None  # Will be set when process starts
    
    def complete(self, end_time: float, exit_code: int, cpu_time: float,
                memory_usage: int, io_read: int, io_write: int):
        """
        Complete record with process termination information
        
        Args:
            end_time: Process end time
            exit_code: Process exit code
            cpu_time: CPU time used
            memory_usage: Memory usage
            io_read: I/O bytes read
            io_write: I/O bytes written
        """
        self.end_time = end_time
        self.exit_code = exit_code
        self.cpu_time = cpu_time
        self.memory_usage = memory_usage
        self.io_read = io_read
        self.io_write = io_write
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        user = UserManager.get_user_by_uid(self.uid)
        username = user.username if user else f"uid:{self.uid}"
        
        return {
            "command": self.command,
            "uid": self.uid,
            "username": username,
            "pid": self.pid,
            "hostname": self.hostname,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "elapsed_time": (self.end_time - self.start_time) if self.end_time else None,
            "exit_code": self.exit_code,
            "cpu_time": self.cpu_time,
            "memory_usage": self.memory_usage,
            "io_read": self.io_read,
            "io_write": self.io_write
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessRecord':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            ProcessRecord instance
        """
        record = cls(
            command=data.get("command", ""),
            uid=data.get("uid", 0),
            start_time=data.get("start_time", 0),
            end_time=data.get("end_time"),
            exit_code=data.get("exit_code"),
            cpu_time=data.get("cpu_time", 0.0),
            memory_usage=data.get("memory_usage", 0),
            io_read=data.get("io_read", 0),
            io_write=data.get("io_write", 0)
        )
        record.pid = data.get("pid")
        record.hostname = data.get("hostname", "")
        return record


class AuditEvent:
    """Class representing an audit event"""
    
    def __init__(self, event_type: str, uid: int, timestamp: float = None,
                details: Dict[str, Any] = None, success: bool = True):
        """
        Initialize an audit event
        
        Args:
            event_type: Type of event (login, logout, file_access, etc.)
            uid: User ID associated with the event
            timestamp: Event timestamp (defaults to current time)
            details: Additional event details
            success: Whether the event was successful
        """
        self.event_type = event_type
        self.uid = uid
        self.timestamp = timestamp or time.time()
        self.details = details or {}
        self.success = success
        
        # Additional metadata
        self.hostname = os.uname().nodename if hasattr(os, 'uname') else platform.node()
        self.pid = os.getpid()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        user = UserManager.get_user_by_uid(self.uid)
        username = user.username if user else f"uid:{self.uid}"
        
        return {
            "event_type": self.event_type,
            "uid": self.uid,
            "username": username,
            "timestamp": self.timestamp,
            "datetime": datetime.datetime.fromtimestamp(self.timestamp).isoformat(),
            "success": self.success,
            "hostname": self.hostname,
            "pid": self.pid,
            "details": self.details
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
            event_type=data.get("event_type", "unknown"),
            uid=data.get("uid", 0),
            timestamp=data.get("timestamp"),
            details=data.get("details", {}),
            success=data.get("success", True)
        )
        event.hostname = data.get("hostname", "")
        event.pid = data.get("pid")
        return event


class ProcessAccounting:
    """Process accounting manager"""
    
    @classmethod
    def enable_accounting(cls, accounting_file: str = DEFAULT_ACCOUNTING_FILE) -> Tuple[bool, str]:
        """
        Enable process accounting
        
        Args:
            accounting_file: Path to accounting file
        
        Returns:
            (success, message)
        """
        global _accounting_enabled
        
        with _accounting_lock:
            if _accounting_enabled:
                return True, "Process accounting already enabled"
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(accounting_file), exist_ok=True)
                
                # If file doesn't exist, create it
                if not os.path.exists(accounting_file):
                    with open(accounting_file, 'w') as f:
                        json.dump([], f)
                
                _accounting_enabled = True
                return True, f"Process accounting enabled, saving to {accounting_file}"
            
            except Exception as e:
                logger.error(f"Error enabling process accounting: {e}")
                return False, str(e)
    
    @classmethod
    def disable_accounting(cls) -> Tuple[bool, str]:
        """
        Disable process accounting
        
        Returns:
            (success, message)
        """
        global _accounting_enabled
        
        with _accounting_lock:
            if not _accounting_enabled:
                return True, "Process accounting already disabled"
            
            _accounting_enabled = False
            return True, "Process accounting disabled"
    
    @classmethod
    def is_accounting_enabled(cls) -> bool:
        """
        Check if process accounting is enabled
        
        Returns:
            True if enabled
        """
        return _accounting_enabled
    
    @classmethod
    def record_process_start(cls, command: str, uid: int = None) -> Optional[ProcessRecord]:
        """
        Record process start
        
        Args:
            command: Command being executed
            uid: User ID (defaults to current user)
        
        Returns:
            Process record or None if accounting is disabled
        """
        if not _accounting_enabled:
            return None
        
        # Use current user if not specified
        if uid is None:
            uid = get_current_uid()
        
        # Create record
        record = ProcessRecord(
            command=command,
            uid=uid,
            start_time=time.time()
        )
        
        # Set PID
        record.pid = os.getpid()
        
        return record
    
    @classmethod
    def record_process_end(cls, record: ProcessRecord, exit_code: int,
                         cpu_time: float, memory_usage: int,
                         io_read: int, io_write: int) -> bool:
        """
        Record process end
        
        Args:
            record: Process record from record_process_start
            exit_code: Process exit code
            cpu_time: CPU time used
            memory_usage: Memory usage
            io_read: I/O bytes read
            io_write: I/O bytes written
        
        Returns:
            Success status
        """
        if not _accounting_enabled or record is None:
            return False
        
        # Complete record
        record.complete(
            end_time=time.time(),
            exit_code=exit_code,
            cpu_time=cpu_time,
            memory_usage=memory_usage,
            io_read=io_read,
            io_write=io_write
        )
        
        # Write to accounting file
        cls.write_record(record)
        
        return True
    
    @classmethod
    def write_record(cls, record: ProcessRecord, accounting_file: str = DEFAULT_ACCOUNTING_FILE) -> bool:
        """
        Write record to accounting file
        
        Args:
            record: Process record
            accounting_file: Path to accounting file
        
        Returns:
            Success status
        """
        try:
            with _accounting_lock:
                # Read existing records
                records = []
                try:
                    with open(accounting_file, 'r') as f:
                        records = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    records = []
                
                # Add new record
                records.append(record.to_dict())
                
                # Write back to file
                with open(accounting_file, 'w') as f:
                    json.dump(records, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Error writing accounting record: {e}")
            return False
    
    @classmethod
    def read_records(cls, accounting_file: str = DEFAULT_ACCOUNTING_FILE,
                  start_time: float = None, end_time: float = None,
                  uid: int = None, command_filter: str = None) -> List[ProcessRecord]:
        """
        Read accounting records
        
        Args:
            accounting_file: Path to accounting file
            start_time: Filter by start time (minimum)
            end_time: Filter by end time (maximum)
            uid: Filter by user ID
            command_filter: Filter by command substring
        
        Returns:
            List of process records
        """
        try:
            with _accounting_lock:
                # Read records
                try:
                    with open(accounting_file, 'r') as f:
                        record_dicts = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    return []
                
                # Convert to ProcessRecord objects
                records = [ProcessRecord.from_dict(r) for r in record_dicts]
                
                # Apply filters
                if start_time is not None:
                    records = [r for r in records if r.start_time >= start_time]
                
                if end_time is not None:
                    records = [r for r in records if r.end_time is None or r.end_time <= end_time]
                
                if uid is not None:
                    records = [r for r in records if r.uid == uid]
                
                if command_filter is not None:
                    records = [r for r in records if command_filter.lower() in r.command.lower()]
                
                return records
        except Exception as e:
            logger.error(f"Error reading accounting records: {e}")
            return []
    
    @classmethod
    def generate_summary(cls, accounting_file: str = DEFAULT_ACCOUNTING_FILE,
                       summary_file: str = DEFAULT_SUMMARY_FILE,
                       start_time: float = None, end_time: float = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Generate accounting summary
        
        Args:
            accounting_file: Path to accounting file
            summary_file: Path to summary file
            start_time: Filter by start time (minimum)
            end_time: Filter by end time (maximum)
        
        Returns:
            (success, message, summary_data)
        """
        try:
            # Read records
            records = cls.read_records(accounting_file, start_time, end_time)
            
            if not records:
                return False, "No accounting records found", {}
            
            # Calculate summary
            summary = {
                "total_records": len(records),
                "time_period": {
                    "start": min(r.start_time for r in records),
                    "end": max(r.end_time if r.end_time is not None else time.time() for r in records)
                },
                "users": {},
                "commands": {},
                "totals": {
                    "cpu_time": 0,
                    "memory_usage": 0,
                    "io_read": 0,
                    "io_write": 0
                }
            }
            
            # Process records
            for record in records:
                # Skip incomplete records
                if record.end_time is None:
                    continue
                
                # Update totals
                summary["totals"]["cpu_time"] += record.cpu_time
                summary["totals"]["memory_usage"] += record.memory_usage
                summary["totals"]["io_read"] += record.io_read
                summary["totals"]["io_write"] += record.io_write
                
                # Update user stats
                uid_str = str(record.uid)
                if uid_str not in summary["users"]:
                    user = UserManager.get_user_by_uid(record.uid)
                    username = user.username if user else f"uid:{record.uid}"
                    
                    summary["users"][uid_str] = {
                        "username": username,
                        "uid": record.uid,
                        "command_count": 0,
                        "cpu_time": 0,
                        "memory_usage": 0,
                        "io_read": 0,
                        "io_write": 0,
                        "commands": {}
                    }
                
                summary["users"][uid_str]["command_count"] += 1
                summary["users"][uid_str]["cpu_time"] += record.cpu_time
                summary["users"][uid_str]["memory_usage"] += record.memory_usage
                summary["users"][uid_str]["io_read"] += record.io_read
                summary["users"][uid_str]["io_write"] += record.io_write
                
                # Track commands per user
                cmd = record.command.split()[0] if record.command else "unknown"
                if cmd not in summary["users"][uid_str]["commands"]:
                    summary["users"][uid_str]["commands"][cmd] = 0
                summary["users"][uid_str]["commands"][cmd] += 1
                
                # Update command stats
                if cmd not in summary["commands"]:
                    summary["commands"][cmd] = {
                        "count": 0,
                        "cpu_time": 0,
                        "memory_usage": 0,
                        "io_read": 0,
                        "io_write": 0
                    }
                
                summary["commands"][cmd]["count"] += 1
                summary["commands"][cmd]["cpu_time"] += record.cpu_time
                summary["commands"][cmd]["memory_usage"] += record.memory_usage
                summary["commands"][cmd]["io_read"] += record.io_read
                summary["commands"][cmd]["io_write"] += record.io_write
            
            # Save summary
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            return True, f"Summary generated and saved to {summary_file}", summary
        
        except Exception as e:
            logger.error(f"Error generating accounting summary: {e}")
            return False, str(e), {}


class Auditing:
    """System auditing manager"""
    
    @classmethod
    def enable_auditing(cls, audit_file: str = DEFAULT_AUDIT_FILE) -> Tuple[bool, str]:
        """
        Enable system auditing
        
        Args:
            audit_file: Path to audit file
        
        Returns:
            (success, message)
        """
        global _auditing_enabled
        
        with _accounting_lock:
            if _auditing_enabled:
                return True, "System auditing already enabled"
            
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(audit_file), exist_ok=True)
                
                _auditing_enabled = True
                return True, f"System auditing enabled, saving to {audit_file}"
            
            except Exception as e:
                logger.error(f"Error enabling system auditing: {e}")
                return False, str(e)
    
    @classmethod
    def disable_auditing(cls) -> Tuple[bool, str]:
        """
        Disable system auditing
        
        Returns:
            (success, message)
        """
        global _auditing_enabled
        
        with _accounting_lock:
            if not _auditing_enabled:
                return True, "System auditing already disabled"
            
            _auditing_enabled = False
            return True, "System auditing disabled"
    
    @classmethod
    def is_auditing_enabled(cls) -> bool:
        """
        Check if system auditing is enabled
        
        Returns:
            True if enabled
        """
        return _auditing_enabled
    
    @classmethod
    def record_event(cls, event_type: str, details: Dict[str, Any] = None,
                   success: bool = True, uid: int = None) -> bool:
        """
        Record an audit event
        
        Args:
            event_type: Type of event
            details: Event details
            success: Whether the event was successful
            uid: User ID (defaults to current user)
        
        Returns:
            Success status
        """
        if not _auditing_enabled:
            return False
        
        # Use current user if not specified
        if uid is None:
            uid = get_current_uid()
        
        # Create event
        event = AuditEvent(
            event_type=event_type,
            uid=uid,
            details=details,
            success=success
        )
        
        # Write to audit file
        cls.write_event(event)
        
        return True
    
    @classmethod
    def write_event(cls, event: AuditEvent, audit_file: str = DEFAULT_AUDIT_FILE) -> bool:
        """
        Write event to audit file
        
        Args:
            event: Audit event
            audit_file: Path to audit file
        
        Returns:
            Success status
        """
        try:
            with _accounting_lock:
                # Format event as line
                event_json = json.dumps(event.to_dict())
                
                # Append to file
                with open(audit_file, 'a') as f:
                    f.write(event_json + '\n')
                
                return True
        except Exception as e:
            logger.error(f"Error writing audit event: {e}")
            return False
    
    @classmethod
    def read_events(cls, audit_file: str = DEFAULT_AUDIT_FILE,
                  start_time: float = None, end_time: float = None,
                  uid: int = None, event_type: str = None,
                  max_events: int = None) -> List[AuditEvent]:
        """
        Read audit events
        
        Args:
            audit_file: Path to audit file
            start_time: Filter by timestamp (minimum)
            end_time: Filter by timestamp (maximum)
            uid: Filter by user ID
            event_type: Filter by event type
            max_events: Maximum number of events to return
        
        Returns:
            List of audit events
        """
        try:
            events = []
            
            # Read events from file
            try:
                with open(audit_file, 'r') as f:
                    for line in f:
                        try:
                            event_dict = json.loads(line.strip())
                            event = AuditEvent.from_dict(event_dict)
                            
                            # Apply filters
                            if start_time is not None and event.timestamp < start_time:
                                continue
                            
                            if end_time is not None and event.timestamp > end_time:
                                continue
                            
                            if uid is not None and event.uid != uid:
                                continue
                            
                            if event_type is not None and event.event_type != event_type:
                                continue
                            
                            events.append(event)
                            
                            # Check max events
                            if max_events is not None and len(events) >= max_events:
                                break
                        
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                return []
            
            return events
        
        except Exception as e:
            logger.error(f"Error reading audit events: {e}")
            return []
    
    @classmethod
    def search_events(cls, search_term: str, audit_file: str = DEFAULT_AUDIT_FILE,
                    start_time: float = None, end_time: float = None,
                    max_events: int = None) -> List[AuditEvent]:
        """
        Search audit events
        
        Args:
            search_term: Term to search for in event details
            audit_file: Path to audit file
            start_time: Filter by timestamp (minimum)
            end_time: Filter by timestamp (maximum)
            max_events: Maximum number of events to return
        
        Returns:
            List of matching audit events
        """
        try:
            matching_events = []
            
            # Read events from file
            try:
                with open(audit_file, 'r') as f:
                    for line in f:
                        try:
                            if search_term.lower() in line.lower():
                                event_dict = json.loads(line.strip())
                                event = AuditEvent.from_dict(event_dict)
                                
                                # Apply filters
                                if start_time is not None and event.timestamp < start_time:
                                    continue
                                
                                if end_time is not None and event.timestamp > end_time:
                                    continue
                                
                                matching_events.append(event)
                                
                                # Check max events
                                if max_events is not None and len(matching_events) >= max_events:
                                    break
                        
                        except json.JSONDecodeError:
                            continue
            except FileNotFoundError:
                return []
            
            return matching_events
        
        except Exception as e:
            logger.error(f"Error searching audit events: {e}")
            return []


def initialize():
    """Initialize process accounting and auditing"""
    logger.info("Initializing process accounting and auditing")
    
    # Create security directory
    security_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(security_dir, exist_ok=True)
    
    # Enable process accounting
    ProcessAccounting.enable_accounting()
    
    # Enable auditing
    Auditing.enable_auditing()
    
    logger.info("Process accounting and auditing initialized")


# Initialize on module load
initialize()

"""
System logging service for KOS
"""

import time
import json
import threading
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4
    EMERGENCY = 5

@dataclass
class LogEntry:
    """Log entry"""
    timestamp: float
    level: LogLevel
    facility: str
    message: str
    source: str = "system"
    pid: Optional[int] = None
    user: Optional[str] = None
    
    def format(self) -> str:
        """Format log entry"""
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))
        return f"{time_str} {self.facility} {self.level.name}: {self.message}"

class LogRotator:
    """Log rotation handler"""
    
    def __init__(self, vfs, max_size: int = 10485760, max_files: int = 5):
        self.vfs = vfs
        self.max_size = max_size  # 10MB default
        self.max_files = max_files
    
    def should_rotate(self, logfile: str) -> bool:
        """Check if log should be rotated"""
        if not self.vfs or not self.vfs.exists(logfile):
            return False
        
        try:
            # Check file size
            with self.vfs.open(logfile, 'rb') as f:
                f.seek(0, 2)  # Seek to end
                size = f.tell()
            return size >= self.max_size
        except:
            return False
    
    def rotate(self, logfile: str):
        """Rotate log files"""
        if not self.vfs:
            return
        
        # Rotate existing files
        for i in range(self.max_files - 1, 0, -1):
            old_file = f"{logfile}.{i}"
            new_file = f"{logfile}.{i+1}"
            
            if self.vfs.exists(old_file):
                if i == self.max_files - 1:
                    # Delete oldest
                    self.vfs.remove(old_file)
                else:
                    # Rename
                    try:
                        with self.vfs.open(old_file, 'rb') as f:
                            data = f.read()
                        with self.vfs.open(new_file, 'wb') as f:
                            f.write(data)
                        self.vfs.remove(old_file)
                    except:
                        pass
        
        # Rotate current file
        if self.vfs.exists(logfile):
            try:
                with self.vfs.open(logfile, 'rb') as f:
                    data = f.read()
                with self.vfs.open(f"{logfile}.1", 'wb') as f:
                    f.write(data)
                # Clear current file
                with self.vfs.open(logfile, 'wb') as f:
                    f.write(b'')
            except:
                pass

class SyslogService:
    """System logging service"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Log storage
        self.memory_buffer: deque = deque(maxlen=1000)
        self.facilities: Dict[str, List[LogEntry]] = {}
        
        # Log files
        self.log_dir = "/var/log"
        self.syslog_file = f"{self.log_dir}/syslog"
        self.auth_log = f"{self.log_dir}/auth.log"
        self.kern_log = f"{self.log_dir}/kern.log"
        self.mail_log = f"{self.log_dir}/mail.log"
        
        # Rotation
        self.rotator = LogRotator(vfs)
        
        self._init_logs()
    
    def _init_logs(self):
        """Initialize log files"""
        if not self.vfs:
            return
        
        # Create log directory
        if not self.vfs.exists(self.log_dir):
            try:
                self.vfs.mkdir(self.log_dir)
            except:
                pass
        
        # Create default log files
        for logfile in [self.syslog_file, self.auth_log, self.kern_log, self.mail_log]:
            if not self.vfs.exists(logfile):
                try:
                    with self.vfs.open(logfile, 'w') as f:
                        f.write(b'')
                except:
                    pass
    
    def start(self):
        """Start syslog service"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._service_loop, daemon=True)
        self.thread.start()
        
        self.log(LogLevel.INFO, "syslog", "System logging service started")
    
    def stop(self):
        """Stop syslog service"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            self.thread = None
        
        self.log(LogLevel.INFO, "syslog", "System logging service stopped")
    
    def _service_loop(self):
        """Main service loop"""
        while self.running:
            # Flush logs periodically
            self._flush_logs()
            
            # Check rotation
            if self.rotator.should_rotate(self.syslog_file):
                self.rotator.rotate(self.syslog_file)
            
            time.sleep(5)
    
    def log(self, level: LogLevel, facility: str, message: str, 
            source: str = "system", pid: Optional[int] = None, 
            user: Optional[str] = None):
        """Log a message"""
        entry = LogEntry(
            timestamp=time.time(),
            level=level,
            facility=facility,
            message=message,
            source=source,
            pid=pid,
            user=user
        )
        
        # Add to memory buffer
        self.memory_buffer.append(entry)
        
        # Add to facility list
        if facility not in self.facilities:
            self.facilities[facility] = []
        self.facilities[facility].append(entry)
        
        # Write to appropriate log file
        self._write_log(entry)
    
    def _write_log(self, entry: LogEntry):
        """Write log entry to file"""
        if not self.vfs:
            return
        
        # Determine log file
        if entry.facility == "auth":
            logfile = self.auth_log
        elif entry.facility == "kern":
            logfile = self.kern_log
        elif entry.facility == "mail":
            logfile = self.mail_log
        else:
            logfile = self.syslog_file
        
        # Write entry
        try:
            with self.vfs.open(logfile, 'ab') as f:
                f.write((entry.format() + '\n').encode())
        except:
            pass
    
    def _flush_logs(self):
        """Flush logs to disk"""
        # In this implementation, logs are written immediately
        pass
    
    def get_logs(self, facility: Optional[str] = None, 
                 level: Optional[LogLevel] = None,
                 limit: int = 100) -> List[LogEntry]:
        """Get log entries"""
        logs = []
        
        if facility and facility in self.facilities:
            logs = self.facilities[facility]
        else:
            logs = list(self.memory_buffer)
        
        # Filter by level
        if level:
            logs = [l for l in logs if l.level.value >= level.value]
        
        # Limit results
        return logs[-limit:]
    
    def search_logs(self, pattern: str, facility: Optional[str] = None) -> List[LogEntry]:
        """Search logs for pattern"""
        logs = self.get_logs(facility=facility, limit=1000)
        return [l for l in logs if pattern.lower() in l.message.lower()]
    
    def clear_logs(self, facility: Optional[str] = None):
        """Clear logs"""
        if facility:
            if facility in self.facilities:
                self.facilities[facility] = []
        else:
            self.memory_buffer.clear()
            self.facilities.clear()
    
    # Convenience methods for different log levels
    def debug(self, facility: str, message: str, **kwargs):
        self.log(LogLevel.DEBUG, facility, message, **kwargs)
    
    def info(self, facility: str, message: str, **kwargs):
        self.log(LogLevel.INFO, facility, message, **kwargs)
    
    def warning(self, facility: str, message: str, **kwargs):
        self.log(LogLevel.WARNING, facility, message, **kwargs)
    
    def error(self, facility: str, message: str, **kwargs):
        self.log(LogLevel.ERROR, facility, message, **kwargs)
    
    def critical(self, facility: str, message: str, **kwargs):
        self.log(LogLevel.CRITICAL, facility, message, **kwargs)
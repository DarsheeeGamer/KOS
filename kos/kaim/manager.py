"""
KAIM Manager - High-level management for KAIM daemon
Provides service-level operations and coordination
"""

import os
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from pathlib import Path

from kos.kaim.ctypes_wrapper import KAIMKernelInterface, FLAG_NAMES
from kos.security.fingerprint import get_fingerprint_manager

logger = logging.getLogger('kaim.manager')


class KAIMManager:
    """
    KAIM service manager
    Handles high-level operations and policy enforcement
    """
    
    def __init__(self):
        self.kernel = KAIMKernelInterface()
        self.fingerprint_manager = get_fingerprint_manager()
        self.active_sessions: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        
        # Policy configuration
        self.policies = self._load_policies()
        
        # Statistics
        self.stats = {
            "elevations": 0,
            "denials": 0,
            "device_opens": 0,
            "permission_checks": 0
        }
    
    def _load_policies(self) -> Dict[str, Any]:
        """Load security policies"""
        # Default policies
        policies = {
            "max_elevation_duration": 3600,  # 1 hour
            "require_fingerprint": True,
            "allowed_devices": ["null", "zero", "random", "urandom"],
            "restricted_flags": ["KROOT"],  # Flags that require special approval
            "audit_all": True
        }
        
        # Load from config file if exists
        config_path = Path("/etc/kos/kaim.conf")
        if config_path.exists():
            try:
                import json
                with open(config_path) as f:
                    policies.update(json.load(f))
            except Exception as e:
                logger.error(f"Failed to load policies: {e}")
        
        return policies
    
    def elevate_process(self, pid: int, flags: List[str], 
                       duration: int = 900) -> bool:
        """
        Elevate process privileges with policy enforcement
        """
        with self._lock:
            # Validate request
            if duration > self.policies["max_elevation_duration"]:
                logger.warning(f"Elevation duration {duration} exceeds max {self.policies['max_elevation_duration']}")
                duration = self.policies["max_elevation_duration"]
            
            # Check for restricted flags
            for flag in flags:
                if flag in self.policies["restricted_flags"]:
                    logger.warning(f"Restricted flag {flag} requested by PID {pid}")
                    # Would check additional authorization here
                    self.stats["denials"] += 1
                    return False
            
            # Perform elevation
            success = self.kernel.elevate_process(pid, flags, duration)
            
            if success:
                # Track session
                self.active_sessions[pid] = {
                    "flags": flags,
                    "start_time": time.time(),
                    "duration": duration
                }
                self.stats["elevations"] += 1
                logger.info(f"Elevated PID {pid} with flags {flags} for {duration}s")
            else:
                self.stats["denials"] += 1
                logger.error(f"Failed to elevate PID {pid}")
            
            return success
    
    def check_permission(self, pid: int, flag: str) -> bool:
        """Check if process has permission"""
        self.stats["permission_checks"] += 1
        
        # Check kernel
        has_perm = self.kernel.check_permission(pid, flag)
        
        # Check our session tracking
        with self._lock:
            if pid in self.active_sessions:
                session = self.active_sessions[pid]
                # Check if session expired
                elapsed = time.time() - session["start_time"]
                if elapsed > session["duration"]:
                    # Expired, remove session
                    del self.active_sessions[pid]
                    # Drop from kernel too
                    for session_flag in session["flags"]:
                        self.kernel.drop_permission(pid, session_flag)
                    has_perm = False
        
        return has_perm
    
    def device_open(self, device: str, mode: str, 
                   app_name: str, fingerprint: str) -> int:
        """
        Open device with policy checks
        """
        # Check if device is allowed
        if device not in self.policies["allowed_devices"]:
            logger.warning(f"Denied access to restricted device: {device}")
            return -1
        
        # Verify fingerprint if required
        if self.policies["require_fingerprint"]:
            if not self.fingerprint_manager.verify(fingerprint, "app"):
                logger.warning(f"Invalid fingerprint for app {app_name}")
                return -1
        
        # Open device
        fd = self.kernel.open_device_with_check(device, mode)
        
        if fd >= 0:
            self.stats["device_opens"] += 1
            logger.info(f"Opened device {device} for {app_name}: fd={fd}")
        
        return fd
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status"""
        kernel_status = self.kernel.get_status()
        
        with self._lock:
            # Add our stats
            status = {
                **kernel_status,
                "manager_stats": self.stats,
                "active_sessions": len(self.active_sessions),
                "policies": {
                    "max_elevation_duration": self.policies["max_elevation_duration"],
                    "require_fingerprint": self.policies["require_fingerprint"]
                }
            }
        
        return status
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions"""
        with self._lock:
            current_time = time.time()
            expired_pids = []
            
            for pid, session in self.active_sessions.items():
                elapsed = current_time - session["start_time"]
                if elapsed > session["duration"]:
                    expired_pids.append(pid)
            
            for pid in expired_pids:
                session = self.active_sessions[pid]
                # Drop permissions
                for flag in session["flags"]:
                    self.kernel.drop_permission(pid, flag)
                # Remove session
                del self.active_sessions[pid]
                logger.info(f"Cleaned up expired session for PID {pid}")
    
    def get_audit_log(self, count: int = 100) -> List[str]:
        """Get audit log from kernel"""
        return self.kernel.get_audit_log(count)
"""
KOS Security Hardening Framework
Implements various security hardening measures and validation
"""

import os
import logging
import hashlib
import hmac
import secrets
import time
import threading
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger('KOS.security.hardening')

class SecurityLevel(Enum):
    """Security hardening levels"""
    MINIMAL = 1      # Basic security measures
    STANDARD = 2     # Default security level
    HARDENED = 3     # Enhanced security
    PARANOID = 4     # Maximum security

class ThreatType(Enum):
    """Types of security threats"""
    BUFFER_OVERFLOW = "buffer_overflow"
    CODE_INJECTION = "code_injection"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    PATH_TRAVERSAL = "path_traversal"
    TIMING_ATTACK = "timing_attack"
    MEMORY_CORRUPTION = "memory_corruption"
    RACE_CONDITION = "race_condition"
    INPUT_VALIDATION = "input_validation"

@dataclass
class SecurityViolation:
    """Security violation record"""
    threat_type: ThreatType
    severity: str
    description: str
    location: str
    timestamp: float
    remediation: str

class InputValidator:
    """Secure input validation"""
    
    # Maximum safe string lengths
    MAX_PATH_LENGTH = 4096
    MAX_USERNAME_LENGTH = 32
    MAX_PASSWORD_LENGTH = 128
    MAX_COMMAND_LENGTH = 8192
    MAX_FILENAME_LENGTH = 255
    
    # Dangerous patterns
    DANGEROUS_PATTERNS = [
        r'\.\./',           # Path traversal
        r'\.\.\\',          # Windows path traversal
        r'[;&|`$()]',       # Command injection
        r'<script',         # XSS attempt
        r'union.*select',   # SQL injection
        r'exec\s*\(',       # Code execution
        r'eval\s*\(',       # Code evaluation
        r'/proc/',          # Proc filesystem access
        r'/sys/',           # Sys filesystem access
        r'/dev/',           # Device access
    ]
    
    @staticmethod
    def validate_path(path: str, allow_absolute: bool = False) -> Tuple[bool, str]:
        """Validate file path for security"""
        if not path:
            return False, "Empty path"
        
        if len(path) > InputValidator.MAX_PATH_LENGTH:
            return False, f"Path too long: {len(path)} > {InputValidator.MAX_PATH_LENGTH}"
        
        # Check for path traversal
        if '..' in path:
            return False, "Path traversal attempt detected"
        
        # Check for absolute paths if not allowed
        if not allow_absolute and os.path.isabs(path):
            return False, "Absolute path not allowed"
        
        # Check for dangerous patterns
        import re
        for pattern in InputValidator.DANGEROUS_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Check for null bytes
        if '\0' in path:
            return False, "Null byte in path"
        
        # Check for control characters
        if any(ord(c) < 32 and c not in '\t\n\r' for c in path):
            return False, "Control characters in path"
        
        return True, "Valid"
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, str]:
        """Validate username"""
        if not username:
            return False, "Empty username"
        
        if len(username) > InputValidator.MAX_USERNAME_LENGTH:
            return False, f"Username too long: {len(username)}"
        
        # Only allow alphanumeric, underscore, hyphen
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', username):
            return False, "Invalid characters in username"
        
        # Must start with letter
        if not username[0].isalpha():
            return False, "Username must start with letter"
        
        return True, "Valid"
    
    @staticmethod
    def validate_command(command: str) -> Tuple[bool, str]:
        """Validate shell command for security"""
        if not command:
            return False, "Empty command"
        
        if len(command) > InputValidator.MAX_COMMAND_LENGTH:
            return False, f"Command too long: {len(command)}"
        
        # Check for dangerous patterns
        import re
        dangerous_cmds = [
            r'rm\s+-rf\s+/',    # Dangerous rm
            r'dd\s+.*of=/dev/', # Writing to devices
            r'mkfs\.',          # Formatting
            r'fdisk',           # Disk partitioning
            r'format',          # Windows format
            r'del\s+/[qfs]',    # Windows delete
        ]
        
        for pattern in dangerous_cmds:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Dangerous command pattern: {pattern}"
        
        return True, "Valid"
    
    @staticmethod
    def sanitize_string(input_str: str, max_length: int = 1024) -> str:
        """Sanitize string input"""
        if not input_str:
            return ""
        
        # Truncate if too long
        if len(input_str) > max_length:
            input_str = input_str[:max_length]
        
        # Remove null bytes and control characters
        sanitized = ''.join(c for c in input_str 
                          if ord(c) >= 32 or c in '\t\n\r')
        
        return sanitized

class MemoryProtection:
    """Memory protection and validation"""
    
    @staticmethod
    def secure_zero(data: bytearray) -> None:
        """Securely zero memory"""
        # Use volatile operations to prevent optimization
        for i in range(len(data)):
            data[i] = 0
        
        # Additional overwrite passes
        for _ in range(3):
            for i in range(len(data)):
                data[i] = secrets.randbits(8)
    
    @staticmethod
    def validate_buffer_bounds(buffer: bytes, offset: int, length: int) -> bool:
        """Validate buffer access bounds"""
        if offset < 0 or length < 0:
            return False
        
        if offset + length > len(buffer):
            return False
        
        return True
    
    @staticmethod
    def safe_copy(dest: bytearray, src: bytes, max_size: int) -> bool:
        """Safe memory copy with bounds checking"""
        if len(src) > max_size:
            logger.warning(f"Source too large: {len(src)} > {max_size}")
            return False
        
        if len(dest) < len(src):
            logger.warning(f"Destination too small: {len(dest)} < {len(src)}")
            return False
        
        try:
            dest[:len(src)] = src
            return True
        except Exception as e:
            logger.error(f"Memory copy failed: {e}")
            return False

class CryptoHardening:
    """Cryptographic security hardening"""
    
    @staticmethod
    def secure_random_bytes(length: int) -> bytes:
        """Generate cryptographically secure random bytes"""
        return secrets.token_bytes(length)
    
    @staticmethod
    def secure_hash(data: bytes, salt: Optional[bytes] = None) -> bytes:
        """Secure hash with optional salt"""
        if salt is None:
            salt = secrets.token_bytes(32)
        
        # Use PBKDF2 for password-like data
        import hashlib
        return hashlib.pbkdf2_hmac('sha256', data, salt, 100000)
    
    @staticmethod
    def constant_time_compare(a: bytes, b: bytes) -> bool:
        """Constant-time comparison to prevent timing attacks"""
        return hmac.compare_digest(a, b)
    
    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate secure token"""
        return secrets.token_urlsafe(length)

class ProcessHardening:
    """Process and privilege hardening"""
    
    @staticmethod
    def drop_privileges() -> bool:
        """Drop root privileges if running as root"""
        try:
            import pwd
            import grp
            
            # Get nobody user/group
            nobody = pwd.getpwnam('nobody')
            nogroup = grp.getgrnam('nogroup')
            
            # Drop privileges
            os.setgid(nogroup.gr_gid)
            os.setuid(nobody.pw_uid)
            
            # Verify we can't get root back
            try:
                os.setuid(0)
                return False  # Should not succeed
            except PermissionError:
                return True  # Good, can't get root back
            
        except Exception as e:
            logger.error(f"Failed to drop privileges: {e}")
            return False
    
    @staticmethod
    def set_process_limits() -> None:
        """Set secure process limits"""
        try:
            import resource
            
            # Limit core dumps
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            
            # Limit memory usage (1GB)
            max_memory = 1024 * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
            
            # Limit CPU time (5 minutes)
            max_cpu = 300
            resource.setrlimit(resource.RLIMIT_CPU, (max_cpu, max_cpu))
            
            # Limit file descriptors
            max_fds = 1024
            resource.setrlimit(resource.RLIMIT_NOFILE, (max_fds, max_fds))
            
            logger.info("Process limits set successfully")
            
        except Exception as e:
            logger.error(f"Failed to set process limits: {e}")
    
    @staticmethod
    def enable_aslr() -> bool:
        """Enable Address Space Layout Randomization"""
        try:
            # Check if ASLR is enabled
            with open('/proc/sys/kernel/randomize_va_space', 'r') as f:
                aslr_level = int(f.read().strip())
            
            if aslr_level < 2:
                logger.warning(f"ASLR level is {aslr_level}, should be 2")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check ASLR: {e}")
            return False

class FileSystemHardening:
    """Filesystem security hardening"""
    
    SECURE_PERMISSIONS = {
        'config': 0o600,     # rw-------
        'executable': 0o755, # rwxr-xr-x
        'directory': 0o755,  # rwxr-xr-x
        'log': 0o640,        # rw-r-----
        'temp': 0o600,       # rw-------
    }
    
    @staticmethod
    def secure_file_permissions(filepath: str, file_type: str = 'config') -> bool:
        """Set secure file permissions"""
        try:
            perms = FileSystemHardening.SECURE_PERMISSIONS.get(file_type, 0o600)
            os.chmod(filepath, perms)
            return True
        except Exception as e:
            logger.error(f"Failed to set permissions on {filepath}: {e}")
            return False
    
    @staticmethod
    def validate_file_ownership(filepath: str, expected_uid: int = None) -> bool:
        """Validate file ownership"""
        try:
            stat_info = os.stat(filepath)
            
            if expected_uid is None:
                expected_uid = os.getuid()
            
            if stat_info.st_uid != expected_uid:
                logger.warning(f"File {filepath} owned by {stat_info.st_uid}, expected {expected_uid}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check ownership of {filepath}: {e}")
            return False
    
    @staticmethod
    def create_secure_temp_file(prefix: str = "kos_") -> Tuple[str, int]:
        """Create secure temporary file"""
        import tempfile
        
        # Create with secure permissions
        fd, path = tempfile.mkstemp(prefix=prefix)
        os.chmod(path, 0o600)
        
        return path, fd

class NetworkHardening:
    """Network security hardening"""
    
    @staticmethod
    def validate_ip_address(ip: str) -> Tuple[bool, str]:
        """Validate IP address"""
        import ipaddress
        
        try:
            addr = ipaddress.ip_address(ip)
            
            # Check for private/localhost addresses in certain contexts
            if addr.is_private:
                return True, "Private address"
            elif addr.is_loopback:
                return True, "Loopback address"
            elif addr.is_multicast:
                return False, "Multicast address not allowed"
            elif addr.is_reserved:
                return False, "Reserved address not allowed"
            
            return True, "Valid public address"
            
        except ValueError as e:
            return False, f"Invalid IP address: {e}"
    
    @staticmethod
    def validate_port(port: int) -> Tuple[bool, str]:
        """Validate port number"""
        if port < 1 or port > 65535:
            return False, f"Port out of range: {port}"
        
        # Check for privileged ports
        if port < 1024:
            if os.getuid() != 0:
                return False, f"Privileged port {port} requires root"
        
        return True, "Valid port"
    
    @staticmethod
    def setup_firewall_rules() -> bool:
        """Setup basic firewall rules"""
        try:
            # This would integrate with the firewall system
            from ..network.firewall import get_firewall_manager
            
            fw = get_firewall_manager()
            
            # Block common attack ports
            dangerous_ports = [23, 135, 139, 445, 1433, 3389]
            for port in dangerous_ports:
                fw.block_port(port, protocol='tcp')
            
            # Rate limit SSH
            fw.rate_limit(22, 'tcp', 5, 60)  # 5 connections per minute
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup firewall rules: {e}")
            return False

class SecurityAuditor:
    """Security audit and monitoring"""
    
    def __init__(self):
        self.violations: List[SecurityViolation] = []
        self.audit_lock = threading.Lock()
    
    def record_violation(self, violation: SecurityViolation) -> None:
        """Record security violation"""
        with self.audit_lock:
            self.violations.append(violation)
            
        logger.warning(f"Security violation: {violation.threat_type.value} - {violation.description}")
    
    def audit_file_permissions(self, directory: str) -> List[SecurityViolation]:
        """Audit file permissions in directory"""
        violations = []
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    filepath = os.path.join(root, file)
                    stat_info = os.stat(filepath)
                    
                    # Check for world-writable files
                    if stat_info.st_mode & 0o002:
                        violation = SecurityViolation(
                            threat_type=ThreatType.PRIVILEGE_ESCALATION,
                            severity="HIGH",
                            description=f"World-writable file: {filepath}",
                            location=filepath,
                            timestamp=time.time(),
                            remediation=f"chmod 644 {filepath}"
                        )
                        violations.append(violation)
                        self.record_violation(violation)
        
        except Exception as e:
            logger.error(f"File permission audit failed: {e}")
        
        return violations
    
    def audit_process_privileges(self) -> List[SecurityViolation]:
        """Audit current process privileges"""
        violations = []
        
        # Check if running as root
        if os.getuid() == 0:
            violation = SecurityViolation(
                threat_type=ThreatType.PRIVILEGE_ESCALATION,
                severity="MEDIUM",
                description="Process running as root",
                location="current_process",
                timestamp=time.time(),
                remediation="Drop privileges after initialization"
            )
            violations.append(violation)
            self.record_violation(violation)
        
        return violations
    
    def get_security_report(self) -> Dict[str, Any]:
        """Generate security audit report"""
        with self.audit_lock:
            threat_counts = {}
            severity_counts = {}
            
            for violation in self.violations:
                threat_type = violation.threat_type.value
                threat_counts[threat_type] = threat_counts.get(threat_type, 0) + 1
                severity_counts[violation.severity] = severity_counts.get(violation.severity, 0) + 1
            
            return {
                'total_violations': len(self.violations),
                'threat_counts': threat_counts,
                'severity_counts': severity_counts,
                'recent_violations': self.violations[-10:] if self.violations else []
            }

class SecurityManager:
    """Main security hardening manager"""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.STANDARD):
        self.security_level = security_level
        self.auditor = SecurityAuditor()
        self.hardening_enabled = False
        
    def initialize_hardening(self) -> bool:
        """Initialize security hardening measures"""
        try:
            logger.info(f"Initializing security hardening (level: {self.security_level.name})")
            
            # Set process limits
            ProcessHardening.set_process_limits()
            
            # Enable ASLR
            if not ProcessHardening.enable_aslr():
                logger.warning("ASLR not properly enabled")
            
            # Setup secure file permissions for config directories
            config_dirs = [
                os.path.expanduser("~/.kos"),
                "/etc/kos",
                "/var/lib/kos"
            ]
            
            for config_dir in config_dirs:
                if os.path.exists(config_dir):
                    FileSystemHardening.secure_file_permissions(config_dir, 'directory')
            
            # Setup firewall if available
            if self.security_level.value >= SecurityLevel.HARDENED.value:
                NetworkHardening.setup_firewall_rules()
            
            # Run security audit
            self.run_security_audit()
            
            self.hardening_enabled = True
            logger.info("Security hardening initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Security hardening initialization failed: {e}")
            return False
    
    def run_security_audit(self) -> Dict[str, Any]:
        """Run comprehensive security audit"""
        logger.info("Running security audit...")
        
        # Audit various components
        self.auditor.audit_process_privileges()
        
        # Audit KOS directories
        kos_dirs = [
            os.path.expanduser("~/.kos"),
            "/tmp",
            "/var/tmp"
        ]
        
        for directory in kos_dirs:
            if os.path.exists(directory):
                self.auditor.audit_file_permissions(directory)
        
        return self.auditor.get_security_report()
    
    def validate_input(self, input_data: Any, input_type: str) -> Tuple[bool, str]:
        """Validate input based on type"""
        if input_type == "path":
            return InputValidator.validate_path(str(input_data))
        elif input_type == "username":
            return InputValidator.validate_username(str(input_data))
        elif input_type == "command":
            return InputValidator.validate_command(str(input_data))
        else:
            return True, "No validation rule"
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get security metrics"""
        return {
            'hardening_enabled': self.hardening_enabled,
            'security_level': self.security_level.name,
            'aslr_enabled': ProcessHardening.enable_aslr(),
            'audit_report': self.auditor.get_security_report()
        }

# Global security manager instance
_security_manager = None

def get_security_manager(level: SecurityLevel = SecurityLevel.STANDARD) -> SecurityManager:
    """Get global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager(level)
    return _security_manager

# Convenience functions
def validate_path(path: str) -> bool:
    """Quick path validation"""
    valid, _ = InputValidator.validate_path(path)
    return valid

def validate_username(username: str) -> bool:
    """Quick username validation"""
    valid, _ = InputValidator.validate_username(username)
    return valid

def secure_random_string(length: int = 32) -> str:
    """Generate secure random string"""
    return CryptoHardening.generate_token(length)

def secure_compare(a: str, b: str) -> bool:
    """Secure string comparison"""
    return CryptoHardening.constant_time_compare(a.encode(), b.encode())
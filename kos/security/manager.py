"""
KOS Complete Security Manager - Advanced security framework
Implements:
- SELinux-like mandatory access control (MAC)
- POSIX capabilities and privileges
- AppArmor-like profile-based security
- Namespace isolation (PID, network, mount, etc.)
- Seccomp system call filtering
- ASLR and DEP protections
- Audit logging and intrusion detection
- Cryptographic key management
- Certificate and PKI infrastructure
- Firewall and network security
- Process isolation and sandboxing
"""

import os
import time
import threading
import hashlib
import hmac
import uuid
import json
import re
from typing import Dict, List, Optional, Set, Any, Callable, Union, Tuple
from enum import Enum, IntEnum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from collections import defaultdict
import secrets
import base64

class SecurityLevel(Enum):
    """Security levels"""
    DISABLED = "disabled"
    PERMISSIVE = "permissive"
    ENFORCING = "enforcing"
    STRICT = "strict"

class AccessType(Enum):
    """Access types for MAC"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    APPEND = "append"
    CREATE = "create"
    DELETE = "delete"
    SEARCH = "search"
    LISTEN = "listen"
    ACCEPT = "accept"
    CONNECT = "connect"
    SEND = "send"
    RECEIVE = "receive"

class ObjectClass(Enum):
    """SELinux object classes"""
    FILE = "file"
    DIR = "dir"
    SOCKET = "socket"
    PROCESS = "process"
    CAPABILITY = "capability"
    FILESYSTEM = "filesystem"
    NODE = "node"
    NETIF = "netif"
    PACKET = "packet"
    KEY = "key"
    MSGQ = "msgq"
    SEM = "sem"
    SHM = "shm"

class CapabilityType(IntEnum):
    """POSIX capabilities"""
    CAP_CHOWN = 0
    CAP_DAC_OVERRIDE = 1
    CAP_DAC_READ_SEARCH = 2
    CAP_FOWNER = 3
    CAP_FSETID = 4
    CAP_KILL = 5
    CAP_SETGID = 6
    CAP_SETUID = 7
    CAP_SETPCAP = 8
    CAP_LINUX_IMMUTABLE = 9
    CAP_NET_BIND_SERVICE = 10
    CAP_NET_BROADCAST = 11
    CAP_NET_ADMIN = 12
    CAP_NET_RAW = 13
    CAP_IPC_LOCK = 14
    CAP_IPC_OWNER = 15
    CAP_SYS_MODULE = 16
    CAP_SYS_RAWIO = 17
    CAP_SYS_CHROOT = 18
    CAP_SYS_PTRACE = 19
    CAP_SYS_PACCT = 20
    CAP_SYS_ADMIN = 21
    CAP_SYS_BOOT = 22
    CAP_SYS_NICE = 23
    CAP_SYS_RESOURCE = 24
    CAP_SYS_TIME = 25
    CAP_SYS_TTY_CONFIG = 26
    CAP_MKNOD = 27
    CAP_LEASE = 28
    CAP_AUDIT_WRITE = 29
    CAP_AUDIT_CONTROL = 30
    CAP_SETFCAP = 31
    CAP_MAC_OVERRIDE = 32
    CAP_MAC_ADMIN = 33
    CAP_SYSLOG = 34

@dataclass
class SecurityContext:
    """SELinux security context"""
    user: str = "system_u"
    role: str = "system_r"
    type: str = "unconfined_t"
    level: str = "s0"
    
    def __str__(self) -> str:
        return f"{self.user}:{self.role}:{self.type}:{self.level}"
    
    @classmethod
    def parse(cls, context_str: str) -> 'SecurityContext':
        """Parse security context from string"""
        parts = context_str.split(':')
        if len(parts) >= 3:
            return cls(
                user=parts[0],
                role=parts[1],
                type=parts[2],
                level=parts[3] if len(parts) > 3 else "s0"
            )
        return cls()

@dataclass
class AccessVector:
    """Access vector for permission checks"""
    subject_context: SecurityContext
    object_context: SecurityContext
    object_class: ObjectClass
    permissions: Set[AccessType]
    
@dataclass
class SecurityPolicy:
    """Security policy rule"""
    source_type: str
    target_type: str
    object_class: ObjectClass
    permissions: Set[AccessType]
    effect: str = "allow"  # allow, deny, auditallow, dontaudit

@dataclass
class AppArmorProfile:
    """AppArmor security profile"""
    name: str
    mode: str = "enforce"  # enforce, complain, disable
    capabilities: Set[CapabilityType] = field(default_factory=set)
    file_rules: List[Dict[str, Any]] = field(default_factory=list)
    network_rules: List[Dict[str, Any]] = field(default_factory=list)
    rlimits: Dict[str, int] = field(default_factory=dict)
    
@dataclass
class Namespace:
    """Process namespace"""
    ns_type: str  # pid, net, mnt, uts, ipc, user, cgroup
    id: int
    processes: Set[int] = field(default_factory=set)
    
@dataclass
class SecurityEvent:
    """Security audit event"""
    timestamp: float
    event_type: str
    severity: str
    source: str
    target: str
    action: str
    result: str
    details: Dict[str, Any] = field(default_factory=dict)

class SeccompFilter:
    """Seccomp system call filter"""
    
    def __init__(self):
        self.allowed_syscalls: Set[str] = set()
        self.denied_syscalls: Set[str] = set()
        self.default_action = "kill"  # kill, trap, errno, trace, allow
        
    def add_rule(self, syscall: str, action: str):
        """Add seccomp rule"""
        if action == "allow":
            self.allowed_syscalls.add(syscall)
        elif action == "deny":
            self.denied_syscalls.add(syscall)
            
    def check_syscall(self, syscall: str) -> bool:
        """Check if syscall is allowed"""
        if syscall in self.denied_syscalls:
            return False
        if syscall in self.allowed_syscalls:
            return True
        return self.default_action == "allow"

class CryptoManager:
    """Cryptographic key and certificate management"""
    
    def __init__(self):
        self.keys: Dict[str, bytes] = {}
        self.certificates: Dict[str, Dict[str, Any]] = {}
        self.ca_certificates: Dict[str, Dict[str, Any]] = {}
        
    def generate_key(self, key_id: str, key_type: str = "aes256") -> bytes:
        """Generate cryptographic key"""
        if key_type == "aes256":
            key = secrets.token_bytes(32)  # 256 bits
        elif key_type == "aes128":
            key = secrets.token_bytes(16)  # 128 bits
        else:
            key = secrets.token_bytes(32)
            
        self.keys[key_id] = key
        return key
        
    def encrypt_data(self, data: bytes, key_id: str) -> bytes:
        """Encrypt data with key"""
        if key_id not in self.keys:
            raise ValueError(f"Key {key_id} not found")
            
        # Simple XOR encryption for simulation
        key = self.keys[key_id]
        encrypted = bytearray()
        
        for i, byte in enumerate(data):
            encrypted.append(byte ^ key[i % len(key)])
            
        return bytes(encrypted)
        
    def decrypt_data(self, encrypted_data: bytes, key_id: str) -> bytes:
        """Decrypt data with key"""
        # XOR is symmetric
        return self.encrypt_data(encrypted_data, key_id)
        
    def sign_data(self, data: bytes, key_id: str) -> bytes:
        """Sign data with key"""
        if key_id not in self.keys:
            raise ValueError(f"Key {key_id} not found")
            
        key = self.keys[key_id]
        return hmac.new(key, data, hashlib.sha256).digest()
        
    def verify_signature(self, data: bytes, signature: bytes, key_id: str) -> bool:
        """Verify data signature"""
        if key_id not in self.keys:
            return False
            
        expected_signature = self.sign_data(data, key_id)
        return hmac.compare_digest(signature, expected_signature)

class AuditLogger:
    """Security audit logging"""
    
    def __init__(self):
        self.events: List[SecurityEvent] = []
        self.log_file = "/var/log/audit/audit.log"
        self.max_events = 10000
        
    def log_event(self, event_type: str, severity: str, source: str, 
                  target: str, action: str, result: str, **details):
        """Log security event"""
        event = SecurityEvent(
            timestamp=time.time(),
            event_type=event_type,
            severity=severity,
            source=source,
            target=target,
            action=action,
            result=result,
            details=details
        )
        
        self.events.append(event)
        
        # Keep only recent events
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
            
        # Format and log
        log_line = self._format_event(event)
        self._write_log(log_line)
        
    def _format_event(self, event: SecurityEvent) -> str:
        """Format audit event"""
        return (f"type={event.event_type} msg=audit({event.timestamp:.3f}): "
                f"severity={event.severity} src={event.source} dst={event.target} "
                f"action={event.action} result={event.result}")
                
    def _write_log(self, log_line: str):
        """Write to audit log"""
        # In real implementation, would write to actual log file
        pass
        
    def search_events(self, filters: Dict[str, Any]) -> List[SecurityEvent]:
        """Search audit events"""
        results = []
        
        for event in self.events:
            match = True
            
            for key, value in filters.items():
                if hasattr(event, key):
                    if getattr(event, key) != value:
                        match = False
                        break
                elif key in event.details:
                    if event.details[key] != value:
                        match = False
                        break
                        
            if match:
                results.append(event)
                
        return results

class IntrusionDetection:
    """Intrusion detection system"""
    
    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger
        self.rules: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self.running = False
        self.monitor_thread = None
        
    def add_rule(self, rule: Dict[str, Any]):
        """Add IDS rule"""
        self.rules.append(rule)
        
    def start(self):
        """Start IDS monitoring"""
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="ids-monitor",
            daemon=True
        )
        self.monitor_thread.start()
        
    def stop(self):
        """Stop IDS monitoring"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
            
    def _monitor_loop(self):
        """Main IDS monitoring loop"""
        last_check = time.time()
        
        while self.running:
            current_time = time.time()
            
            # Check recent events
            recent_events = [e for e in self.audit_logger.events 
                           if e.timestamp > last_check]
                           
            for event in recent_events:
                self._check_event(event)
                
            last_check = current_time
            time.sleep(1.0)
            
    def _check_event(self, event: SecurityEvent):
        """Check event against IDS rules"""
        for rule in self.rules:
            if self._rule_matches(rule, event):
                self._trigger_alert(rule, event)
                
    def _rule_matches(self, rule: Dict[str, Any], event: SecurityEvent) -> bool:
        """Check if rule matches event"""
        for key, value in rule.get('conditions', {}).items():
            if hasattr(event, key):
                if getattr(event, key) != value:
                    return False
            elif key in event.details:
                if event.details[key] != value:
                    return False
            else:
                return False
        return True
        
    def _trigger_alert(self, rule: Dict[str, Any], event: SecurityEvent):
        """Trigger security alert"""
        alert = {
            'timestamp': time.time(),
            'rule': rule['name'],
            'severity': rule.get('severity', 'medium'),
            'event': event,
            'description': rule.get('description', 'Security rule triggered')
        }
        
        self.alerts.append(alert)
        
        # Log alert
        self.audit_logger.log_event(
            "ALERT", alert['severity'], "ids", 
            event.target, "alert", "triggered",
            rule_name=rule['name']
        )

class KOSSecurityManager:
    """Complete KOS Security Manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        
        # Security state
        self.selinux_state = SecurityLevel.ENFORCING
        self.apparmor_state = SecurityLevel.ENFORCING
        
        # SELinux components
        from .selinux_contexts import get_enforcer, SecurityContext as SELinuxContext
        self.selinux_enforcer = get_enforcer()
        self.security_contexts: Dict[str, SecurityContext] = {}
        self.policies: List[SecurityPolicy] = []
        self.types: Set[str] = set()
        self.roles: Set[str] = set()
        self.users: Set[str] = set()
        
        # AppArmor profiles
        self.apparmor_profiles: Dict[str, AppArmorProfile] = {}
        
        # Capabilities
        self.process_capabilities: Dict[int, Set[CapabilityType]] = {}
        
        # Namespaces
        self.namespaces: Dict[str, Dict[int, Namespace]] = {
            'pid': {}, 'net': {}, 'mnt': {}, 'uts': {}, 'ipc': {}, 'user': {}, 'cgroup': {}
        }
        self.next_namespace_id = 1
        
        # Seccomp filters
        self.seccomp_filters: Dict[int, SeccompFilter] = {}  # pid -> filter
        
        # Cryptography
        self.crypto_manager = CryptoManager()
        
        # Audit and IDS
        self.audit_logger = AuditLogger()
        self.ids = IntrusionDetection(self.audit_logger)
        
        # Initialize security framework
        self._init_security_framework()
        
    def _init_security_framework(self):
        """Initialize security framework"""
        
        # Create default security contexts
        self.security_contexts.update({
            "system": SecurityContext("system_u", "system_r", "kernel_t", "s0"),
            "unconfined": SecurityContext("unconfined_u", "unconfined_r", "unconfined_t", "s0"),
            "init": SecurityContext("system_u", "system_r", "init_t", "s0"),
        })
        
        # Add default types, roles, users
        self.types.update(["kernel_t", "init_t", "unconfined_t", "user_t", "sshd_t"])
        self.roles.update(["system_r", "unconfined_r", "user_r"])
        self.users.update(["system_u", "unconfined_u", "user_u"])
        
        # Create default policies
        default_policies = [
            SecurityPolicy("init_t", "kernel_t", ObjectClass.PROCESS, {AccessType.READ}),
            SecurityPolicy("unconfined_t", "*", ObjectClass.FILE, {AccessType.READ, AccessType.WRITE}),
            SecurityPolicy("user_t", "user_home_t", ObjectClass.FILE, {AccessType.READ, AccessType.WRITE}),
        ]
        self.policies.extend(default_policies)
        
        # Create default AppArmor profiles
        unconfined_profile = AppArmorProfile(
            name="unconfined",
            mode="disable",
            capabilities=set(CapabilityType),
            file_rules=[{"path": "/**", "permissions": ["rwix"]}]
        )
        self.apparmor_profiles["unconfined"] = unconfined_profile
        
        # Generate system keys
        self.crypto_manager.generate_key("system_key", "aes256")
        self.crypto_manager.generate_key("audit_key", "aes256")
        
        # Setup default IDS rules
        self._setup_ids_rules()
        
        # Start IDS
        self.ids.start()
        
    def _setup_ids_rules(self):
        """Setup default IDS rules"""
        rules = [
            {
                'name': 'failed_login_attempts',
                'description': 'Multiple failed login attempts',
                'severity': 'high',
                'conditions': {
                    'event_type': 'USER_AUTH',
                    'result': 'failure'
                }
            },
            {
                'name': 'privilege_escalation',
                'description': 'Privilege escalation attempt',
                'severity': 'critical',
                'conditions': {
                    'action': 'setuid'
                }
            },
            {
                'name': 'suspicious_file_access',
                'description': 'Access to sensitive files',
                'severity': 'medium',
                'conditions': {
                    'target': '/etc/shadow'
                }
            }
        ]
        
        for rule in rules:
            self.ids.add_rule(rule)
        
    def check_permission(self, subject_context: SecurityContext, 
                        object_context: SecurityContext, 
                        object_class: ObjectClass, 
                        permission: AccessType) -> bool:
        """Check SELinux permission"""
        
        if self.selinux_state == SecurityLevel.DISABLED:
            return True
        
        # Convert to new SELinux context format
        from .selinux_contexts import SecurityContext as SELinuxContext, SecurityClass, Permission
        
        # Map object class
        class_map = {
            ObjectClass.FILE: SecurityClass.FILE,
            ObjectClass.DIR: SecurityClass.DIR,
            ObjectClass.PROCESS: SecurityClass.PROCESS,
            ObjectClass.SOCKET: SecurityClass.SOCKET,
            ObjectClass.CAPABILITY: SecurityClass.CAPABILITY
        }
        
        # Map permission
        perm_map = {
            AccessType.READ: Permission.READ,
            AccessType.WRITE: Permission.WRITE,
            AccessType.EXECUTE: Permission.EXECUTE,
            AccessType.CREATE: Permission.CREATE,
            AccessType.DELETE: Permission.DELETE
        }
        
        selinux_subject = SELinuxContext(
            user=subject_context.user,
            role=subject_context.role,
            type=subject_context.type,
            level=subject_context.level
        )
        
        selinux_object = SELinuxContext(
            user=object_context.user,
            role=object_context.role,
            type=object_context.type,
            level=object_context.level
        )
        
        # Use new SELinux enforcer
        mapped_class = class_map.get(object_class, SecurityClass.FILE)
        mapped_perm = perm_map.get(permission, Permission.READ)
        
        return self.selinux_enforcer.check_access(
            selinux_subject, selinux_object,
            mapped_class, mapped_perm
        )
        
    def _type_matches(self, policy_type: str, context_type: str) -> bool:
        """Check if policy type matches context type"""
        return policy_type == "*" or policy_type == context_type
        
    def check_capability(self, pid: int, capability: CapabilityType) -> bool:
        """Check process capability"""
        if pid not in self.process_capabilities:
            # Default capabilities for root process
            if pid == 1:  # init
                self.process_capabilities[pid] = set(CapabilityType)
            else:
                self.process_capabilities[pid] = set()
                
        has_capability = capability in self.process_capabilities[pid]
        
        # Log capability check
        self.audit_logger.log_event(
            "CAPABILITY", "info", f"pid={pid}", capability.name,
            "check", "granted" if has_capability else "denied"
        )
        
        return has_capability
        
    def grant_capability(self, pid: int, capability: CapabilityType):
        """Grant capability to process"""
        if pid not in self.process_capabilities:
            self.process_capabilities[pid] = set()
            
        self.process_capabilities[pid].add(capability)
        
        self.audit_logger.log_event(
            "CAPABILITY", "info", "system", f"pid={pid}",
            "grant", "success", capability=capability.name
        )
        
    def revoke_capability(self, pid: int, capability: CapabilityType):
        """Revoke capability from process"""
        if pid in self.process_capabilities:
            self.process_capabilities[pid].discard(capability)
            
        self.audit_logger.log_event(
            "CAPABILITY", "info", "system", f"pid={pid}",
            "revoke", "success", capability=capability.name
        )
        
    def create_namespace(self, ns_type: str, pid: int) -> int:
        """Create new namespace"""
        ns_id = self.next_namespace_id
        self.next_namespace_id += 1
        
        namespace = Namespace(ns_type, ns_id, {pid})
        self.namespaces[ns_type][ns_id] = namespace
        
        self.audit_logger.log_event(
            "NAMESPACE", "info", f"pid={pid}", f"ns={ns_id}",
            "create", "success", ns_type=ns_type
        )
        
        return ns_id
        
    def join_namespace(self, ns_type: str, ns_id: int, pid: int) -> bool:
        """Join existing namespace"""
        if ns_type in self.namespaces and ns_id in self.namespaces[ns_type]:
            self.namespaces[ns_type][ns_id].processes.add(pid)
            
            self.audit_logger.log_event(
                "NAMESPACE", "info", f"pid={pid}", f"ns={ns_id}",
                "join", "success", ns_type=ns_type
            )
            
            return True
        return False
        
    def set_seccomp_filter(self, pid: int, seccomp_filter: SeccompFilter):
        """Set seccomp filter for process"""
        self.seccomp_filters[pid] = seccomp_filter
        
        self.audit_logger.log_event(
            "SECCOMP", "info", "system", f"pid={pid}",
            "set_filter", "success"
        )
        
    def check_syscall(self, pid: int, syscall: str) -> bool:
        """Check if syscall is allowed by seccomp"""
        if pid not in self.seccomp_filters:
            return True  # No filter, allow all
            
        result = self.seccomp_filters[pid].check_syscall(syscall)
        
        if not result:
            self.audit_logger.log_event(
                "SECCOMP", "warning", f"pid={pid}", syscall,
                "syscall", "denied"
            )
            
        return result
        
    def load_apparmor_profile(self, profile: AppArmorProfile):
        """Load AppArmor profile"""
        self.apparmor_profiles[profile.name] = profile
        
        self.audit_logger.log_event(
            "APPARMOR", "info", "system", profile.name,
            "load_profile", "success", mode=profile.mode
        )
        
    def check_apparmor_permission(self, profile_name: str, 
                                 resource: str, permission: str) -> bool:
        """Check AppArmor permission"""
        if self.apparmor_state == SecurityLevel.DISABLED:
            return True
            
        if profile_name not in self.apparmor_profiles:
            return True  # No profile, allow
            
        profile = self.apparmor_profiles[profile_name]
        
        if profile.mode == "disable":
            return True
            
        # Check file rules
        for rule in profile.file_rules:
            if self._path_matches(rule["path"], resource):
                if permission in rule["permissions"]:
                    return True
                    
        # Default deny for enforce mode
        result = profile.mode != "enforce"
        
        self.audit_logger.log_event(
            "APPARMOR", "info" if result else "warning",
            profile_name, resource, permission,
            "granted" if result else "denied"
        )
        
        return result
        
    def _path_matches(self, pattern: str, path: str) -> bool:
        """Check if file path matches pattern"""
        # Simple glob-like matching
        if pattern == "/**":
            return True
        if pattern.endswith("/*"):
            return path.startswith(pattern[:-2])
        return pattern == path
        
    def get_security_stats(self) -> Dict[str, Any]:
        """Get security subsystem statistics"""
        return {
            'selinux_state': self.selinux_state.value,
            'apparmor_state': self.apparmor_state.value,
            'security_contexts': len(self.security_contexts),
            'policies': len(self.policies),
            'apparmor_profiles': len(self.apparmor_profiles),
            'active_namespaces': sum(len(ns_dict) for ns_dict in self.namespaces.values()),
            'seccomp_filters': len(self.seccomp_filters),
            'audit_events': len(self.audit_logger.events),
            'security_alerts': len(self.ids.alerts),
            'crypto_keys': len(self.crypto_manager.keys)
        }
        
    def sestatus(self) -> str:
        """Get SELinux status"""
        return f"""SELinux status:                 {self.selinux_state.value}
SELinuxfs mount:                /sys/fs/selinux
SELinux root directory:         /etc/selinux
Loaded policy name:             targeted
Current mode:                   {self.selinux_state.value}
Mode from config file:          {self.selinux_state.value}
Policy MLS status:              enabled
Policy deny_unknown status:     allowed
Memory protection checking:     actual (secure)
Max kernel policy version:     33"""

    def getenforce(self) -> str:
        """Get SELinux enforcement mode"""
        return self.selinux_state.value.capitalize()
        
    def setenforce(self, mode: str) -> bool:
        """Set SELinux enforcement mode"""
        try:
            self.selinux_state = SecurityLevel(mode.lower())
            self.audit_logger.log_event(
                "MAC_STATUS", "info", "system", "selinux",
                "setenforce", "success", new_mode=mode
            )
            return True
        except ValueError:
            return False
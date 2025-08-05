#!/usr/bin/env python3
"""
KOS Security Framework Python Bindings

This module provides Python bindings for the KOS security framework,
including capabilities, SELinux, seccomp, audit, and cryptographic functions.
"""

import ctypes
import os
import sys
from ctypes import (
    c_int, c_uint32, c_uint64, c_char_p, c_void_p, c_size_t, c_bool,
    Structure, POINTER, byref, create_string_buffer
)
from enum import IntEnum
from typing import Optional, List, Dict, Tuple, Union

# Add the security library path
SECURITY_LIB_PATH = os.path.join(os.path.dirname(__file__), 'libkos_security.so')

class KOSSecurityError(Exception):
    """Base exception for KOS security errors"""
    def __init__(self, code: int, message: str = ""):
        self.code = code
        self.message = message
        super().__init__(f"Security error {code}: {message}")

class SecurityReturnCode(IntEnum):
    """Security framework return codes"""
    SUCCESS = 0
    ERROR = -1
    EPERM = -2
    EACCES = -3
    EINVAL = -4
    ENOMEM = -5

class Capability(IntEnum):
    """Linux-style capabilities"""
    CHOWN = 0
    DAC_OVERRIDE = 1
    DAC_READ_SEARCH = 2
    FOWNER = 3
    FSETID = 4
    KILL = 5
    SETGID = 6
    SETUID = 7
    SETPCAP = 8
    LINUX_IMMUTABLE = 9
    NET_BIND_SERVICE = 10
    NET_BROADCAST = 11
    NET_ADMIN = 12
    NET_RAW = 13
    IPC_LOCK = 14
    IPC_OWNER = 15
    SYS_MODULE = 16
    SYS_RAWIO = 17
    SYS_CHROOT = 18
    SYS_PTRACE = 19
    SYS_PACCT = 20
    SYS_ADMIN = 21
    SYS_BOOT = 22
    SYS_NICE = 23
    SYS_RESOURCE = 24
    SYS_TIME = 25
    SYS_TTY_CONFIG = 26
    MKNOD = 27
    LEASE = 28
    AUDIT_WRITE = 29
    AUDIT_CONTROL = 30
    SETFCAP = 31
    MAC_OVERRIDE = 32
    MAC_ADMIN = 33
    SYSLOG = 34
    WAKE_ALARM = 35
    BLOCK_SUSPEND = 36
    AUDIT_READ = 37
    PERFMON = 38
    BPF = 39
    CHECKPOINT_RESTORE = 40

class SELinuxMode(IntEnum):
    """SELinux enforcement modes"""
    UNCONFINED = 0
    CONFINED = 1
    ENFORCING = 2
    PERMISSIVE = 3
    DISABLED = 4

class SeccompMode(IntEnum):
    """Seccomp modes"""
    DISABLED = 0
    STRICT = 1
    FILTER = 2

class AuditType(IntEnum):
    """Audit event types"""
    SYSCALL = 1
    FS_WATCH = 2
    PATH = 3
    IPC = 4
    SOCKETCALL = 5
    CONFIG_CHANGE = 6
    SOCKADDR = 7
    CWD = 8
    EXECVE = 9
    USER = 10
    LOGIN = 11
    SELINUX_ERR = 12
    AVC = 13

class HashType(IntEnum):
    """Cryptographic hash types"""
    SHA256 = 0
    SHA512 = 1
    MD5 = 2

class CipherType(IntEnum):
    """Cryptographic cipher types"""
    AES128_CBC = 0
    AES256_CBC = 1
    AES128_GCM = 2
    AES256_GCM = 3

# C Structures
class CapabilitySet(Structure):
    """Capability set structure"""
    _fields_ = [
        ("effective", c_uint64),
        ("permitted", c_uint64),
        ("inheritable", c_uint64),
        ("bounding", c_uint64),
        ("ambient", c_uint64)
    ]

class SELinuxContext(Structure):
    """SELinux security context"""
    _fields_ = [
        ("user", c_char_p * 64),
        ("role", c_char_p * 64),
        ("type", c_char_p * 64),
        ("level", c_char_p * 64),
        ("sid", c_uint32)
    ]

class SeccompFilterArg(Structure):
    """Seccomp filter argument condition"""
    _fields_ = [
        ("arg", c_uint32),
        ("op", c_uint32),
        ("value", c_uint64)
    ]

class SeccompFilter(Structure):
    """Seccomp filter structure"""
    _fields_ = [
        ("syscall_nr", c_uint32),
        ("action", c_uint32),
        ("arg_count", c_uint32),
        ("args", SeccompFilterArg * 6)
    ]

class AuditEvent(Structure):
    """Audit event structure"""
    _fields_ = [
        ("timestamp", c_uint64),
        ("pid", c_uint32),
        ("uid", c_uint32),
        ("gid", c_uint32),
        ("type", c_int),
        ("message", c_char_p * 256),
        ("comm", c_char_p * 16),
        ("exe", c_char_p * 256)
    ]

class KOSSecurity:
    """Main KOS Security Framework interface"""
    
    def __init__(self):
        """Initialize the security framework"""
        self._lib = None
        self._load_library()
        self._setup_functions()
        self._initialize()
    
    def _load_library(self):
        """Load the security library"""
        try:
            self._lib = ctypes.CDLL(SECURITY_LIB_PATH)
        except OSError:
            # Try to load from system paths
            try:
                self._lib = ctypes.CDLL("libkos_security.so")
            except OSError:
                raise ImportError(f"Could not load KOS security library from {SECURITY_LIB_PATH}")
    
    def _setup_functions(self):
        """Setup C function signatures"""
        # Core security functions
        self._lib.kos_security_init.argtypes = []
        self._lib.kos_security_init.restype = c_int
        
        self._lib.kos_security_cleanup.argtypes = []
        self._lib.kos_security_cleanup.restype = None
        
        # Capability functions
        self._lib.kos_cap_init.argtypes = []
        self._lib.kos_cap_init.restype = c_int
        
        self._lib.kos_cap_get.argtypes = [c_uint32, POINTER(CapabilitySet)]
        self._lib.kos_cap_get.restype = c_int
        
        self._lib.kos_cap_set.argtypes = [c_uint32, POINTER(CapabilitySet)]
        self._lib.kos_cap_set.restype = c_int
        
        self._lib.kos_cap_capable.argtypes = [c_uint32, c_int]
        self._lib.kos_cap_capable.restype = c_bool
        
        self._lib.kos_cap_drop.argtypes = [c_uint32, c_int]
        self._lib.kos_cap_drop.restype = c_int
        
        self._lib.kos_cap_raise.argtypes = [c_uint32, c_int]
        self._lib.kos_cap_raise.restype = c_int
        
        # SELinux functions
        self._lib.kos_selinux_init.argtypes = []
        self._lib.kos_selinux_init.restype = c_int
        
        self._lib.kos_selinux_cleanup.argtypes = []
        self._lib.kos_selinux_cleanup.restype = None
        
        self._lib.kos_selinux_set_mode.argtypes = [c_int]
        self._lib.kos_selinux_set_mode.restype = c_int
        
        self._lib.kos_selinux_get_mode.argtypes = []
        self._lib.kos_selinux_get_mode.restype = c_int
        
        self._lib.kos_selinux_check_access.argtypes = [
            POINTER(SELinuxContext), POINTER(SELinuxContext), c_char_p, c_char_p
        ]
        self._lib.kos_selinux_check_access.restype = c_int
        
        # Seccomp functions
        self._lib.kos_seccomp_init.argtypes = []
        self._lib.kos_seccomp_init.restype = c_int
        
        self._lib.kos_seccomp_set_mode.argtypes = [c_uint32, c_int]
        self._lib.kos_seccomp_set_mode.restype = c_int
        
        self._lib.kos_seccomp_get_mode.argtypes = [c_uint32]
        self._lib.kos_seccomp_get_mode.restype = c_int
        
        self._lib.kos_seccomp_add_filter.argtypes = [c_uint32, POINTER(SeccompFilter)]
        self._lib.kos_seccomp_add_filter.restype = c_int
        
        # Audit functions
        self._lib.kos_audit_init.argtypes = []
        self._lib.kos_audit_init.restype = c_int
        
        self._lib.kos_audit_cleanup.argtypes = []
        self._lib.kos_audit_cleanup.restype = None
        
        self._lib.kos_audit_log_event.argtypes = [c_int, c_uint32, c_char_p]
        self._lib.kos_audit_log_event.restype = c_int
        
        self._lib.kos_audit_set_enabled.argtypes = [c_bool]
        self._lib.kos_audit_set_enabled.restype = c_int
        
        self._lib.kos_audit_is_enabled.argtypes = []
        self._lib.kos_audit_is_enabled.restype = c_bool
        
        # Crypto functions
        self._lib.kos_crypto_init.argtypes = []
        self._lib.kos_crypto_init.restype = c_int
        
        self._lib.kos_crypto_cleanup.argtypes = []
        self._lib.kos_crypto_cleanup.restype = None
        
        self._lib.kos_crypto_hash.argtypes = [c_int, c_void_p, c_size_t, c_void_p, c_size_t]
        self._lib.kos_crypto_hash.restype = c_int
        
        self._lib.kos_crypto_random.argtypes = [c_void_p, c_size_t]
        self._lib.kos_crypto_random.restype = c_int
    
    def _initialize(self):
        """Initialize all security subsystems"""
        result = self._lib.kos_security_init()
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, "Failed to initialize security framework")
        
        # Initialize individual subsystems
        self._lib.kos_cap_init()
        self._lib.kos_selinux_init()
        self._lib.kos_seccomp_init()
        self._lib.kos_audit_init()
        self._lib.kos_crypto_init()
    
    def cleanup(self):
        """Clean up security framework"""
        if self._lib:
            self._lib.kos_security_cleanup()
            self._lib.kos_selinux_cleanup()
            self._lib.kos_audit_cleanup()
            self._lib.kos_crypto_cleanup()
    
    def __del__(self):
        """Destructor"""
        self.cleanup()

class CapabilityManager:
    """Capability management interface"""
    
    def __init__(self, security: KOSSecurity):
        self._lib = security._lib
    
    def get_capabilities(self, pid: int) -> Dict[str, int]:
        """Get capabilities for a process"""
        caps = CapabilitySet()
        result = self._lib.kos_cap_get(pid, byref(caps))
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to get capabilities for PID {pid}")
        
        return {
            "effective": caps.effective,
            "permitted": caps.permitted,
            "inheritable": caps.inheritable,
            "bounding": caps.bounding,
            "ambient": caps.ambient
        }
    
    def set_capabilities(self, pid: int, caps: Dict[str, int]):
        """Set capabilities for a process"""
        cap_set = CapabilitySet()
        cap_set.effective = caps.get("effective", 0)
        cap_set.permitted = caps.get("permitted", 0)
        cap_set.inheritable = caps.get("inheritable", 0)
        cap_set.bounding = caps.get("bounding", 0xFFFFFFFFFFFFFFFF)
        cap_set.ambient = caps.get("ambient", 0)
        
        result = self._lib.kos_cap_set(pid, byref(cap_set))
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to set capabilities for PID {pid}")
    
    def is_capable(self, pid: int, capability: Capability) -> bool:
        """Check if process has a specific capability"""
        return self._lib.kos_cap_capable(pid, capability)
    
    def drop_capability(self, pid: int, capability: Capability):
        """Drop a capability from a process"""
        result = self._lib.kos_cap_drop(pid, capability)
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to drop capability {capability} for PID {pid}")
    
    def raise_capability(self, pid: int, capability: Capability):
        """Raise a capability for a process"""
        result = self._lib.kos_cap_raise(pid, capability)
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to raise capability {capability} for PID {pid}")

class SELinuxManager:
    """SELinux management interface"""
    
    def __init__(self, security: KOSSecurity):
        self._lib = security._lib
    
    def get_mode(self) -> SELinuxMode:
        """Get current SELinux mode"""
        return SELinuxMode(self._lib.kos_selinux_get_mode())
    
    def set_mode(self, mode: SELinuxMode):
        """Set SELinux mode"""
        result = self._lib.kos_selinux_set_mode(mode)
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to set SELinux mode to {mode}")
    
    def check_access(self, source_context: Dict[str, str], target_context: Dict[str, str],
                     object_class: str, permission: str) -> bool:
        """Check if access is allowed by SELinux policy"""
        sctx = SELinuxContext()
        tctx = SELinuxContext()
        
        # This is a simplified version - full implementation would need proper context handling
        result = self._lib.kos_selinux_check_access(
            byref(sctx), byref(tctx), 
            object_class.encode('utf-8'), permission.encode('utf-8')
        )
        
        return result == SecurityReturnCode.SUCCESS

class SeccompManager:
    """Seccomp management interface"""
    
    def __init__(self, security: KOSSecurity):
        self._lib = security._lib
    
    def get_mode(self, pid: int) -> SeccompMode:
        """Get seccomp mode for a process"""
        return SeccompMode(self._lib.kos_seccomp_get_mode(pid))
    
    def set_mode(self, pid: int, mode: SeccompMode):
        """Set seccomp mode for a process"""
        result = self._lib.kos_seccomp_set_mode(pid, mode)
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to set seccomp mode for PID {pid}")
    
    def add_filter(self, pid: int, syscall_nr: int, action: int):
        """Add a seccomp filter"""
        filter_obj = SeccompFilter()
        filter_obj.syscall_nr = syscall_nr
        filter_obj.action = action
        filter_obj.arg_count = 0
        
        result = self._lib.kos_seccomp_add_filter(pid, byref(filter_obj))
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, f"Failed to add seccomp filter for PID {pid}")

class AuditManager:
    """Audit management interface"""
    
    def __init__(self, security: KOSSecurity):
        self._lib = security._lib
    
    def is_enabled(self) -> bool:
        """Check if auditing is enabled"""
        return self._lib.kos_audit_is_enabled()
    
    def set_enabled(self, enabled: bool):
        """Enable or disable auditing"""
        result = self._lib.kos_audit_set_enabled(enabled)
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, "Failed to change audit state")
    
    def log_event(self, event_type: AuditType, pid: int, message: str):
        """Log an audit event"""
        result = self._lib.kos_audit_log_event(event_type, pid, message.encode('utf-8'))
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, "Failed to log audit event")

class CryptoManager:
    """Cryptographic functions interface"""
    
    def __init__(self, security: KOSSecurity):
        self._lib = security._lib
    
    def hash_data(self, data: bytes, hash_type: HashType = HashType.SHA256) -> bytes:
        """Compute hash of data"""
        if hash_type == HashType.SHA256:
            hash_size = 32
        elif hash_type == HashType.SHA512:
            hash_size = 64
        else:
            raise ValueError("Unsupported hash type")
        
        hash_buffer = create_string_buffer(hash_size)
        result = self._lib.kos_crypto_hash(
            hash_type, data, len(data), hash_buffer, hash_size
        )
        
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, "Hash computation failed")
        
        return hash_buffer.raw
    
    def generate_random(self, size: int) -> bytes:
        """Generate cryptographically secure random bytes"""
        buffer = create_string_buffer(size)
        result = self._lib.kos_crypto_random(buffer, size)
        
        if result != SecurityReturnCode.SUCCESS:
            raise KOSSecurityError(result, "Random generation failed")
        
        return buffer.raw

# High-level interface
class KOSSecurityFramework:
    """High-level KOS Security Framework interface"""
    
    def __init__(self):
        """Initialize the security framework"""
        self.core = KOSSecurity()
        self.capabilities = CapabilityManager(self.core)
        self.selinux = SELinuxManager(self.core)
        self.seccomp = SeccompManager(self.core)
        self.audit = AuditManager(self.core)
        self.crypto = CryptoManager(self.core)
    
    def get_security_context(self, pid: int) -> Dict[str, any]:
        """Get complete security context for a process"""
        context = {}
        
        try:
            context['capabilities'] = self.capabilities.get_capabilities(pid)
        except KOSSecurityError:
            context['capabilities'] = None
        
        try:
            context['seccomp_mode'] = self.seccomp.get_mode(pid).name
        except KOSSecurityError:
            context['seccomp_mode'] = 'unknown'
        
        context['selinux_mode'] = self.selinux.get_mode().name
        context['audit_enabled'] = self.audit.is_enabled()
        
        return context
    
    def secure_process(self, pid: int, profile: str = "default"):
        """Apply security profile to a process"""
        if profile == "restricted":
            # Drop dangerous capabilities
            dangerous_caps = [
                Capability.SYS_ADMIN, Capability.SYS_MODULE,
                Capability.SYS_RAWIO, Capability.SYS_PTRACE
            ]
            
            for cap in dangerous_caps:
                try:
                    self.capabilities.drop_capability(pid, cap)
                except KOSSecurityError:
                    pass
            
            # Enable seccomp filtering
            self.seccomp.set_mode(pid, SeccompMode.FILTER)
            
        elif profile == "network_service":
            # Allow network capabilities but restrict others
            caps = self.capabilities.get_capabilities(pid)
            caps['effective'] &= (1 << Capability.NET_BIND_SERVICE) | \
                                 (1 << Capability.NET_ADMIN) | \
                                 (1 << Capability.NET_RAW)
            self.capabilities.set_capabilities(pid, caps)
        
        # Log the security profile application
        self.audit.log_event(AuditType.CONFIG_CHANGE, pid, 
                           f"Applied security profile: {profile}")
    
    def cleanup(self):
        """Clean up the security framework"""
        self.core.cleanup()

# Convenience functions
def initialize_security() -> KOSSecurityFramework:
    """Initialize and return KOS security framework"""
    return KOSSecurityFramework()

def check_capability(pid: int, capability: Union[Capability, str]) -> bool:
    """Check if a process has a specific capability"""
    security = initialize_security()
    
    if isinstance(capability, str):
        capability = getattr(Capability, capability.upper())
    
    return security.capabilities.is_capable(pid, capability)

def hash_file(filepath: str, hash_type: HashType = HashType.SHA256) -> str:
    """Compute hash of a file"""
    security = initialize_security()
    
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        hash_bytes = security.crypto.hash_data(data, hash_type)
        return hash_bytes.hex()
    
    finally:
        security.cleanup()

def audit_event(event_type: Union[AuditType, str], pid: int, message: str):
    """Log an audit event"""
    security = initialize_security()
    
    try:
        if isinstance(event_type, str):
            event_type = getattr(AuditType, event_type.upper())
        
        security.audit.log_event(event_type, pid, message)
    
    finally:
        security.cleanup()

# Example usage
if __name__ == "__main__":
    # Initialize security framework
    security = initialize_security()
    
    try:
        # Get current process security context
        import os
        pid = os.getpid()
        
        print(f"Security context for PID {pid}:")
        context = security.get_security_context(pid)
        
        for key, value in context.items():
            print(f"  {key}: {value}")
        
        # Test cryptographic functions
        print("\nCryptographic tests:")
        random_data = security.crypto.generate_random(16)
        print(f"Random data: {random_data.hex()}")
        
        test_data = b"Hello, KOS Security!"
        hash_result = security.crypto.hash_data(test_data)
        print(f"SHA-256 of '{test_data.decode()}': {hash_result.hex()}")
        
        # Test audit logging
        security.audit.log_event(AuditType.USER, pid, "Security framework test completed")
        
    finally:
        security.cleanup()
        print("\nSecurity framework test completed.")
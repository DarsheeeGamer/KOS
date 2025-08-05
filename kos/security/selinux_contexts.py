"""
SELinux-style Security Contexts for KOS
Implements Mandatory Access Control (MAC) with security contexts
"""

import os
import re
import json
import logging
import threading
from typing import Dict, Any, Optional, List, Tuple, Set
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum, auto

logger = logging.getLogger('kos.security.selinux')


class SecurityClass(Enum):
    """Security object classes"""
    FILE = auto()
    DIR = auto()
    PROCESS = auto()
    SOCKET = auto()
    DEVICE = auto()
    SERVICE = auto()
    PORT = auto()
    CAPABILITY = auto()
    KERNEL_MODULE = auto()
    SYSTEM = auto()


class Permission(Enum):
    """Security permissions"""
    # File permissions
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    CREATE = "create"
    DELETE = "delete"
    APPEND = "append"
    RENAME = "rename"
    LINK = "link"
    SETATTR = "setattr"
    GETATTR = "getattr"
    
    # Directory permissions
    SEARCH = "search"
    ADD_NAME = "add_name"
    REMOVE_NAME = "remove_name"
    REPARENT = "reparent"
    RMDIR = "rmdir"
    
    # Process permissions
    FORK = "fork"
    TRANSITION = "transition"
    SIGNAL = "signal"
    PTRACE = "ptrace"
    SETCAP = "setcap"
    SETPGID = "setpgid"
    GETCAP = "getcap"
    SETRLIMIT = "setrlimit"
    
    # Socket permissions
    BIND = "bind"
    CONNECT = "connect"
    LISTEN = "listen"
    ACCEPT = "accept"
    SEND = "send"
    RECV = "recv"
    
    # Device permissions
    OPEN = "open"
    IOCTL = "ioctl"
    MOUNT = "mount"
    UNMOUNT = "unmount"
    
    # Service permissions
    START = "start"
    STOP = "stop"
    STATUS = "status"
    RELOAD = "reload"
    ENABLE = "enable"
    DISABLE = "disable"
    
    # System permissions
    REBOOT = "reboot"
    AUDIT = "audit"
    SETENFORCE = "setenforce"
    SETBOOL = "setbool"
    LOAD_POLICY = "load_policy"
    RELABEL = "relabel"


@dataclass
class SecurityContext:
    """Security context (user:role:type:level)"""
    user: str
    role: str
    type: str
    level: str = "s0"
    categories: Set[str] = field(default_factory=set)
    
    def __str__(self):
        """String representation of context"""
        level_str = self.level
        if self.categories:
            cats = ",".join(sorted(self.categories))
            level_str = f"{self.level}:{cats}"
        return f"{self.user}:{self.role}:{self.type}:{level_str}"
    
    @classmethod
    def from_string(cls, context_str: str) -> 'SecurityContext':
        """Parse context from string"""
        parts = context_str.split(':')
        if len(parts) < 3:
            raise ValueError(f"Invalid context string: {context_str}")
        
        user = parts[0]
        role = parts[1]
        type_str = parts[2]
        
        level = "s0"
        categories = set()
        
        if len(parts) >= 4:
            level_parts = parts[3].split(':')
            level = level_parts[0]
            
            if len(level_parts) > 1:
                # Parse categories
                for cat in level_parts[1].split(','):
                    categories.add(cat.strip())
        
        return cls(user=user, role=role, type=type_str, level=level, categories=categories)
    
    def dominates(self, other: 'SecurityContext') -> bool:
        """Check if this context dominates another (MLS)"""
        # Compare sensitivity levels
        self_level = int(self.level[1:]) if self.level.startswith('s') else 0
        other_level = int(other.level[1:]) if other.level.startswith('s') else 0
        
        if self_level < other_level:
            return False
        
        # Check categories - self must have all categories of other
        return other.categories.issubset(self.categories)


@dataclass
class TypeEnforcementRule:
    """Type enforcement rule"""
    source_type: str
    target_type: str
    object_class: SecurityClass
    permissions: Set[Permission]
    
    def matches(self, source: str, target: str, obj_class: SecurityClass, perm: Permission) -> bool:
        """Check if rule matches request"""
        # Handle wildcards
        if self.source_type != "*" and self.source_type != source:
            return False
        if self.target_type != "*" and self.target_type != target:
            return False
        if self.object_class != obj_class:
            return False
        return perm in self.permissions


@dataclass
class RoleAllowRule:
    """Role allow rule"""
    source_role: str
    target_role: str
    
    def allows_transition(self, source: str, target: str) -> bool:
        """Check if role transition is allowed"""
        return self.source_role == source and self.target_role == target


@dataclass
class TypeTransitionRule:
    """Type transition rule"""
    source_type: str
    target_type: str
    object_class: SecurityClass
    default_type: str
    
    def get_new_type(self, source: str, target: str, obj_class: SecurityClass) -> Optional[str]:
        """Get new type for transition"""
        if (self.source_type == source and 
            self.target_type == target and 
            self.object_class == obj_class):
            return self.default_type
        return None


class SecurityPolicy:
    """SELinux-style security policy"""
    
    def __init__(self):
        self.te_rules: List[TypeEnforcementRule] = []
        self.role_rules: List[RoleAllowRule] = []
        self.type_transitions: List[TypeTransitionRule] = []
        self.user_roles: Dict[str, Set[str]] = {}
        self.role_types: Dict[str, Set[str]] = {}
        self.initial_sids: Dict[str, SecurityContext] = {}
        self.booleans: Dict[str, bool] = {}
        self._lock = threading.RLock()
        
        # Load default policy
        self._load_default_policy()
    
    def _load_default_policy(self):
        """Load default security policy"""
        # Initial SIDs (Security Identifiers)
        self.initial_sids = {
            'kernel': SecurityContext('system_u', 'system_r', 'kernel_t', 's15'),
            'init': SecurityContext('system_u', 'system_r', 'init_t', 's15'),
            'file': SecurityContext('system_u', 'object_r', 'file_t', 's0'),
            'unlabeled': SecurityContext('system_u', 'object_r', 'unlabeled_t', 's0')
        }
        
        # User-role mappings
        self.user_roles = {
            'system_u': {'system_r', 'object_r'},
            'root': {'sysadm_r', 'staff_r', 'user_r'},
            'user_u': {'user_r'},
            'guest_u': {'guest_r'}
        }
        
        # Role-type mappings
        self.role_types = {
            'system_r': {'kernel_t', 'init_t', 'systemd_t', 'device_t', 'service_t'},
            'object_r': {'file_t', 'device_t', 'socket_t', 'unlabeled_t'},
            'sysadm_r': {'sysadm_t', 'user_t'},
            'staff_r': {'staff_t', 'user_t'},
            'user_r': {'user_t'},
            'guest_r': {'guest_t'}
        }
        
        # Type enforcement rules
        self._add_default_te_rules()
        
        # Role transitions
        self._add_default_role_rules()
        
        # Type transitions
        self._add_default_type_transitions()
        
        # Security booleans
        self.booleans = {
            'allow_execmem': False,
            'allow_execstack': False,
            'allow_ptrace': False,
            'secure_mode': True,
            'enforcing': True
        }
    
    def _add_default_te_rules(self):
        """Add default type enforcement rules"""
        # Kernel permissions
        self.add_te_rule('kernel_t', '*', SecurityClass.SYSTEM, 
                        {Permission.REBOOT, Permission.AUDIT, Permission.LOAD_POLICY})
        
        # Init permissions
        self.add_te_rule('init_t', '*', SecurityClass.PROCESS,
                        {Permission.FORK, Permission.SIGNAL, Permission.SETCAP})
        self.add_te_rule('init_t', 'service_t', SecurityClass.SERVICE,
                        {Permission.START, Permission.STOP, Permission.STATUS})
        
        # Sysadm permissions
        self.add_te_rule('sysadm_t', '*', SecurityClass.FILE,
                        {Permission.READ, Permission.WRITE, Permission.CREATE, 
                         Permission.DELETE, Permission.SETATTR})
        self.add_te_rule('sysadm_t', '*', SecurityClass.PROCESS,
                        {Permission.SIGNAL, Permission.PTRACE})
        
        # User permissions
        self.add_te_rule('user_t', 'user_t', SecurityClass.FILE,
                        {Permission.READ, Permission.WRITE, Permission.CREATE})
        self.add_te_rule('user_t', 'user_t', SecurityClass.PROCESS,
                        {Permission.FORK, Permission.SIGNAL})
        
        # Guest restrictions
        self.add_te_rule('guest_t', 'guest_t', SecurityClass.FILE,
                        {Permission.READ})
    
    def _add_default_role_rules(self):
        """Add default role allow rules"""
        self.add_role_rule('sysadm_r', 'system_r')
        self.add_role_rule('staff_r', 'sysadm_r')
        self.add_role_rule('staff_r', 'user_r')
        self.add_role_rule('user_r', 'guest_r')
    
    def _add_default_type_transitions(self):
        """Add default type transition rules"""
        # Process transitions
        self.add_type_transition('init_t', 'service_t', SecurityClass.PROCESS, 'service_t')
        self.add_type_transition('sysadm_t', 'user_t', SecurityClass.PROCESS, 'user_t')
        
        # File creation transitions
        self.add_type_transition('user_t', 'file_t', SecurityClass.FILE, 'user_file_t')
        self.add_type_transition('sysadm_t', 'file_t', SecurityClass.FILE, 'admin_file_t')
    
    def add_te_rule(self, source_type: str, target_type: str, 
                    obj_class: SecurityClass, permissions: Set[Permission]):
        """Add type enforcement rule"""
        with self._lock:
            rule = TypeEnforcementRule(source_type, target_type, obj_class, permissions)
            self.te_rules.append(rule)
    
    def add_role_rule(self, source_role: str, target_role: str):
        """Add role allow rule"""
        with self._lock:
            rule = RoleAllowRule(source_role, target_role)
            self.role_rules.append(rule)
    
    def add_type_transition(self, source_type: str, target_type: str,
                           obj_class: SecurityClass, default_type: str):
        """Add type transition rule"""
        with self._lock:
            rule = TypeTransitionRule(source_type, target_type, obj_class, default_type)
            self.type_transitions.append(rule)
    
    def check_permission(self, source_ctx: SecurityContext, target_ctx: SecurityContext,
                        obj_class: SecurityClass, permission: Permission) -> bool:
        """Check if permission is allowed"""
        if not self.booleans.get('enforcing', True):
            return True  # Permissive mode
        
        with self._lock:
            # Check type enforcement
            for rule in self.te_rules:
                if rule.matches(source_ctx.type, target_ctx.type, obj_class, permission):
                    # Check MLS constraints
                    if self._check_mls_constraint(source_ctx, target_ctx, permission):
                        return True
            
            return False
    
    def _check_mls_constraint(self, source_ctx: SecurityContext, 
                             target_ctx: SecurityContext, permission: Permission) -> bool:
        """Check MLS (Multi-Level Security) constraints"""
        # Read-down, write-up policy
        if permission in {Permission.READ, Permission.GETATTR}:
            # Can read if source dominates target
            return source_ctx.dominates(target_ctx)
        elif permission in {Permission.WRITE, Permission.APPEND, Permission.SETATTR}:
            # Can write if target dominates source
            return target_ctx.dominates(source_ctx)
        else:
            # Other permissions require equal levels
            return source_ctx.level == target_ctx.level
    
    def compute_transition(self, source_ctx: SecurityContext, target_ctx: SecurityContext,
                          obj_class: SecurityClass) -> SecurityContext:
        """Compute new context for object creation or process transition"""
        with self._lock:
            # Check type transitions
            for rule in self.type_transitions:
                new_type = rule.get_new_type(source_ctx.type, target_ctx.type, obj_class)
                if new_type:
                    # Create new context with transitioned type
                    return SecurityContext(
                        user=source_ctx.user,
                        role=source_ctx.role if obj_class == SecurityClass.PROCESS else 'object_r',
                        type=new_type,
                        level=source_ctx.level,
                        categories=source_ctx.categories.copy()
                    )
            
            # Default: inherit from source
            return SecurityContext(
                user=source_ctx.user,
                role=source_ctx.role if obj_class == SecurityClass.PROCESS else 'object_r',
                type=source_ctx.type,
                level=source_ctx.level,
                categories=source_ctx.categories.copy()
            )
    
    def validate_context(self, context: SecurityContext) -> bool:
        """Validate security context"""
        with self._lock:
            # Check user-role
            if context.user in self.user_roles:
                if context.role not in self.user_roles[context.user]:
                    return False
            
            # Check role-type
            if context.role in self.role_types:
                if context.type not in self.role_types[context.role]:
                    return False
            
            return True
    
    def set_boolean(self, name: str, value: bool) -> bool:
        """Set security boolean"""
        with self._lock:
            if name in self.booleans:
                self.booleans[name] = value
                logger.info(f"Set boolean {name} = {value}")
                return True
            return False
    
    def get_boolean(self, name: str) -> Optional[bool]:
        """Get security boolean value"""
        with self._lock:
            return self.booleans.get(name)


class SecurityContextManager:
    """Manages security contexts for system objects"""
    
    def __init__(self, policy: SecurityPolicy):
        self.policy = policy
        self._contexts: Dict[str, SecurityContext] = {}
        self._lock = threading.RLock()
        
        # Context cache
        self._cache: Dict[str, SecurityContext] = {}
        self._cache_size = 1000
    
    def set_context(self, path: str, context: SecurityContext):
        """Set security context for object"""
        if not self.policy.validate_context(context):
            raise ValueError(f"Invalid security context: {context}")
        
        with self._lock:
            self._contexts[path] = context
            self._update_cache(path, context)
            
            # Persist to xattr if supported
            self._set_xattr(path, context)
    
    def get_context(self, path: str) -> SecurityContext:
        """Get security context for object"""
        with self._lock:
            # Check cache
            if path in self._cache:
                return self._cache[path]
            
            # Check memory storage
            if path in self._contexts:
                context = self._contexts[path]
                self._update_cache(path, context)
                return context
            
            # Try to read from xattr
            context = self._get_xattr(path)
            if context:
                self._contexts[path] = context
                self._update_cache(path, context)
                return context
            
            # Return default unlabeled context
            return self.policy.initial_sids.get('unlabeled',
                SecurityContext('system_u', 'object_r', 'unlabeled_t', 's0'))
    
    def compute_create_context(self, parent_path: str, name: str, 
                              obj_class: SecurityClass, source_ctx: SecurityContext) -> SecurityContext:
        """Compute context for new object creation"""
        parent_ctx = self.get_context(parent_path)
        new_ctx = self.policy.compute_transition(source_ctx, parent_ctx, obj_class)
        
        # Set context for new object
        new_path = os.path.join(parent_path, name)
        self.set_context(new_path, new_ctx)
        
        return new_ctx
    
    def relabel(self, path: str, new_context: SecurityContext, source_ctx: SecurityContext) -> bool:
        """Relabel object with new context"""
        # Check relabel permission
        current_ctx = self.get_context(path)
        
        if not self.policy.check_permission(source_ctx, current_ctx, 
                                           SecurityClass.FILE, Permission.RELABEL):
            return False
        
        if not self.policy.check_permission(source_ctx, new_context,
                                           SecurityClass.FILE, Permission.RELABEL):
            return False
        
        # Set new context
        self.set_context(path, new_context)
        return True
    
    def _update_cache(self, path: str, context: SecurityContext):
        """Update context cache"""
        self._cache[path] = context
        
        # Evict old entries if cache is full
        if len(self._cache) > self._cache_size:
            # Remove oldest entry (simple FIFO)
            oldest = next(iter(self._cache))
            del self._cache[oldest]
    
    def _set_xattr(self, path: str, context: SecurityContext):
        """Set extended attribute for context persistence"""
        try:
            import xattr
            xattr.setxattr(path, 'security.selinux', str(context).encode())
        except:
            # xattr not supported or available
            pass
    
    def _get_xattr(self, path: str) -> Optional[SecurityContext]:
        """Get context from extended attributes"""
        try:
            import xattr
            context_str = xattr.getxattr(path, 'security.selinux').decode()
            return SecurityContext.from_string(context_str)
        except:
            return None


class AccessVectorCache:
    """AVC (Access Vector Cache) for performance"""
    
    def __init__(self, max_entries: int = 10000):
        self.max_entries = max_entries
        self._cache: Dict[Tuple[str, str, SecurityClass, Permission], bool] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        self._lock = threading.RLock()
    
    def check(self, source_type: str, target_type: str, 
             obj_class: SecurityClass, permission: Permission) -> Optional[bool]:
        """Check cache for access decision"""
        key = (source_type, target_type, obj_class, permission)
        
        with self._lock:
            if key in self._cache:
                self._stats['hits'] += 1
                return self._cache[key]
            
            self._stats['misses'] += 1
            return None
    
    def add(self, source_type: str, target_type: str,
           obj_class: SecurityClass, permission: Permission, decision: bool):
        """Add access decision to cache"""
        key = (source_type, target_type, obj_class, permission)
        
        with self._lock:
            if len(self._cache) >= self.max_entries:
                # Evict oldest entry
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                self._stats['evictions'] += 1
            
            self._cache[key] = decision
    
    def clear(self):
        """Clear cache"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._lock:
            return self._stats.copy()


class SELinuxEnforcer:
    """Main SELinux enforcer"""
    
    def __init__(self):
        self.policy = SecurityPolicy()
        self.context_manager = SecurityContextManager(self.policy)
        self.avc = AccessVectorCache()
        self._audit_log = []
        self._lock = threading.RLock()
    
    def check_access(self, source_ctx: SecurityContext, target_ctx: SecurityContext,
                    obj_class: SecurityClass, permission: Permission) -> bool:
        """Check access with caching and auditing"""
        # Check AVC first
        cached = self.avc.check(source_ctx.type, target_ctx.type, obj_class, permission)
        if cached is not None:
            return cached
        
        # Compute access decision
        allowed = self.policy.check_permission(source_ctx, target_ctx, obj_class, permission)
        
        # Cache decision
        self.avc.add(source_ctx.type, target_ctx.type, obj_class, permission, allowed)
        
        # Audit
        self._audit_access(source_ctx, target_ctx, obj_class, permission, allowed)
        
        return allowed
    
    def _audit_access(self, source_ctx: SecurityContext, target_ctx: SecurityContext,
                     obj_class: SecurityClass, permission: Permission, allowed: bool):
        """Audit access attempt"""
        audit_entry = {
            'timestamp': os.times().elapsed,
            'source': str(source_ctx),
            'target': str(target_ctx),
            'class': obj_class.name,
            'permission': permission.value,
            'allowed': allowed
        }
        
        with self._lock:
            self._audit_log.append(audit_entry)
            
            # Log denials
            if not allowed:
                logger.warning(f"SELinux: Denied {permission.value} from {source_ctx} to {target_ctx}")
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit entries"""
        with self._lock:
            return self._audit_log[-limit:]
    
    def set_enforcing(self, enforcing: bool):
        """Set enforcing mode"""
        self.policy.set_boolean('enforcing', enforcing)
        logger.info(f"SELinux: Set enforcing = {enforcing}")
    
    def is_enforcing(self) -> bool:
        """Check if in enforcing mode"""
        return self.policy.get_boolean('enforcing')


# Global enforcer instance
_enforcer = None

def get_enforcer() -> SELinuxEnforcer:
    """Get global SELinux enforcer"""
    global _enforcer
    if _enforcer is None:
        _enforcer = SELinuxEnforcer()
    return _enforcer
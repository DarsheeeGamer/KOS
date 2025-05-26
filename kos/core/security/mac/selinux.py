"""
SELinux-like Mandatory Access Control for KOS

This module implements an SELinux-like MAC system for KOS, providing:
- Security contexts for subjects (processes) and objects (files, etc.)
- Type enforcement policies
- Role-based access control
- Policy configuration and enforcement
"""

import os
import json
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
SELINUX_POLICY_PATH = os.path.join(KOS_ROOT, 'etc/selinux/policy.json')
SELINUX_CONTEXTS_PATH = os.path.join(KOS_ROOT, 'etc/selinux/contexts.json')
SELINUX_CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/selinux/config')

# Ensure directories exist
os.makedirs(os.path.dirname(SELINUX_POLICY_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class SELinuxMode(str, Enum):
    """SELinux enforcement modes."""
    ENFORCING = "enforcing"
    PERMISSIVE = "permissive"
    DISABLED = "disabled"


class SecurityContext:
    """
    Represents an SELinux security context.
    
    A security context consists of a user, role, type, and optional MLS level,
    similar to SELinux contexts in Linux.
    """
    
    def __init__(self, user: str, role: str, type: str, mls: str = "s0"):
        """
        Initialize a security context.
        
        Args:
            user: SELinux user
            role: SELinux role
            type: SELinux type
            mls: MLS (Multi-Level Security) level
        """
        self.user = user
        self.role = role
        self.type = type
        self.mls = mls
    
    @staticmethod
    def from_string(context_str: str) -> 'SecurityContext':
        """
        Create a SecurityContext from a string representation.
        
        Args:
            context_str: String in format "user:role:type:mls"
            
        Returns:
            SecurityContext object
        """
        parts = context_str.split(':')
        if len(parts) < 3:
            raise ValueError(f"Invalid security context: {context_str}")
        
        user = parts[0]
        role = parts[1]
        type = parts[2]
        mls = parts[3] if len(parts) > 3 else "s0"
        
        return SecurityContext(user, role, type, mls)
    
    def __str__(self) -> str:
        """Convert to string representation."""
        return f"{self.user}:{self.role}:{self.type}:{self.mls}"
    
    def __eq__(self, other) -> bool:
        """Check equality with another context."""
        if not isinstance(other, SecurityContext):
            return False
        
        return (self.user == other.user and
                self.role == other.role and
                self.type == other.type and
                self.mls == other.mls)


class AccessVector:
    """
    Represents an access vector for SELinux policy rules.
    
    Access vectors define the permissions allowed for a given operation,
    such as read, write, execute, etc.
    """
    
    # File permissions
    READ = 1 << 0
    WRITE = 1 << 1
    EXECUTE = 1 << 2
    CREATE = 1 << 3
    GETATTR = 1 << 4
    SETATTR = 1 << 5
    UNLINK = 1 << 6
    RENAME = 1 << 7
    APPEND = 1 << 8
    
    # Process permissions
    FORK = 1 << 9
    TRANSITION = 1 << 10
    SIGCHLD = 1 << 11
    KILL = 1 << 12
    
    # Socket permissions
    CONNECT = 1 << 13
    BIND = 1 << 14
    ACCEPT = 1 << 15
    LISTEN = 1 << 16
    SEND = 1 << 17
    RECV = 1 << 18
    
    # Special permissions
    ENTRYPOINT = 1 << 19
    DYNTRANSITION = 1 << 20
    
    # Common groupings
    FILE_RW = READ | WRITE | GETATTR | SETATTR
    FILE_RWX = FILE_RW | EXECUTE
    
    @staticmethod
    def from_string(perms_str: str) -> int:
        """
        Convert a string of permissions to a bit vector.
        
        Args:
            perms_str: String of permission names separated by spaces
            
        Returns:
            Integer bit vector
        """
        perms = 0
        for perm in perms_str.split():
            if hasattr(AccessVector, perm.upper()):
                perms |= getattr(AccessVector, perm.upper())
        
        return perms
    
    @staticmethod
    def to_string(perms: int) -> str:
        """
        Convert a bit vector to a string of permissions.
        
        Args:
            perms: Integer bit vector
            
        Returns:
            String of permission names
        """
        result = []
        for name in dir(AccessVector):
            if name.isupper() and not name.startswith('_') and not name.startswith('FILE_'):
                value = getattr(AccessVector, name)
                if isinstance(value, int) and (perms & value) == value:
                    result.append(name.lower())
        
        return " ".join(result)


class Transition:
    """
    Represents a type transition rule in SELinux policy.
    
    Type transitions define how a process can transition from one type to another
    when executing a file.
    """
    
    def __init__(self, source_type: str, target_type: str, 
                object_class: str, result_type: str):
        """
        Initialize a type transition.
        
        Args:
            source_type: Source context type
            target_type: Target context type
            object_class: Object class (e.g., "file", "process")
            result_type: Resulting context type
        """
        self.source_type = source_type
        self.target_type = target_type
        self.object_class = object_class
        self.result_type = result_type
    
    def __str__(self) -> str:
        """Convert to string representation."""
        return (f"type_transition {self.source_type} {self.target_type}:"
                f"{self.object_class} {self.result_type}")


class AllowRule:
    """
    Represents an allow rule in SELinux policy.
    
    Allow rules define what permissions a source type has on a target type
    for a given object class.
    """
    
    def __init__(self, source_type: str, target_type: str, 
                object_class: str, permissions: Union[int, str]):
        """
        Initialize an allow rule.
        
        Args:
            source_type: Source context type
            target_type: Target context type
            object_class: Object class (e.g., "file", "process")
            permissions: Permissions as a bit vector or string
        """
        self.source_type = source_type
        self.target_type = target_type
        self.object_class = object_class
        
        if isinstance(permissions, str):
            self.permissions = AccessVector.from_string(permissions)
        else:
            self.permissions = permissions
    
    def __str__(self) -> str:
        """Convert to string representation."""
        perms = AccessVector.to_string(self.permissions)
        return (f"allow {self.source_type} {self.target_type}:"
                f"{self.object_class} {{ {perms} }}")


class SELinuxManager:
    """
    Manages SELinux-like MAC security for KOS.
    
    This class handles security contexts, policy rules, and access decisions
    for the SELinux-like MAC system.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SELinuxManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the SELinux manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self.mode = self._load_mode()
        self.policy = self._load_policy()
        self.contexts = self._load_contexts()
        self._ensure_default_policy()
    
    def _load_mode(self) -> SELinuxMode:
        """Load SELinux mode from configuration."""
        if os.path.exists(SELINUX_CONFIG_PATH):
            try:
                with open(SELINUX_CONFIG_PATH, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('SELINUX='):
                            mode_str = line.split('=')[1].strip().lower()
                            try:
                                return SELinuxMode(mode_str)
                            except ValueError:
                                logger.error(f"Invalid SELinux mode: {mode_str}")
            except Exception as e:
                logger.error(f"Failed to load SELinux mode: {e}")
        
        # Default to permissive mode
        self._save_mode(SELinuxMode.PERMISSIVE)
        return SELinuxMode.PERMISSIVE
    
    def _save_mode(self, mode: SELinuxMode):
        """Save SELinux mode to configuration."""
        try:
            os.makedirs(os.path.dirname(SELINUX_CONFIG_PATH), exist_ok=True)
            with open(SELINUX_CONFIG_PATH, 'w') as f:
                f.write(f"SELINUX={mode.value}\n")
        except Exception as e:
            logger.error(f"Failed to save SELinux mode: {e}")
    
    def _load_policy(self) -> Dict[str, Any]:
        """Load SELinux policy from disk."""
        if os.path.exists(SELINUX_POLICY_PATH):
            try:
                with open(SELINUX_POLICY_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted SELinux policy. Creating new one.")
        
        return {
            "types": [],
            "roles": [],
            "users": [],
            "allow_rules": [],
            "transitions": []
        }
    
    def _save_policy(self):
        """Save SELinux policy to disk."""
        try:
            os.makedirs(os.path.dirname(SELINUX_POLICY_PATH), exist_ok=True)
            with open(SELINUX_POLICY_PATH, 'w') as f:
                json.dump(self.policy, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save SELinux policy: {e}")
    
    def _load_contexts(self) -> Dict[str, str]:
        """Load file contexts from disk."""
        if os.path.exists(SELINUX_CONTEXTS_PATH):
            try:
                with open(SELINUX_CONTEXTS_PATH, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error("Corrupted SELinux contexts. Creating new one.")
        
        return {}
    
    def _save_contexts(self):
        """Save file contexts to disk."""
        try:
            os.makedirs(os.path.dirname(SELINUX_CONTEXTS_PATH), exist_ok=True)
            with open(SELINUX_CONTEXTS_PATH, 'w') as f:
                json.dump(self.contexts, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save SELinux contexts: {e}")
    
    def _ensure_default_policy(self):
        """Ensure default policy types, roles, and users exist."""
        # Default types
        default_types = [
            "kos_t", "kos_exec_t", "kos_bin_t", "kos_lib_t", "kos_etc_t",
            "kos_var_t", "kos_home_t", "kos_tmp_t", "kos_container_t"
        ]
        
        for type_name in default_types:
            if type_name not in self.policy["types"]:
                self.policy["types"].append(type_name)
        
        # Default roles
        default_roles = ["kos_r", "system_r", "object_r", "unconfined_r"]
        for role in default_roles:
            if role not in self.policy["roles"]:
                self.policy["roles"].append(role)
        
        # Default users
        default_users = ["kos_u", "system_u", "unconfined_u"]
        for user in default_users:
            if user not in self.policy["users"]:
                self.policy["users"].append(user)
        
        # Default file contexts
        default_contexts = {
            f"{KOS_ROOT}/bin(/.*)?": "system_u:object_r:kos_bin_t:s0",
            f"{KOS_ROOT}/lib(/.*)?": "system_u:object_r:kos_lib_t:s0",
            f"{KOS_ROOT}/etc(/.*)?": "system_u:object_r:kos_etc_t:s0",
            f"{KOS_ROOT}/var(/.*)?": "system_u:object_r:kos_var_t:s0",
            f"{KOS_ROOT}/home(/.*)?": "system_u:object_r:kos_home_t:s0",
            f"{KOS_ROOT}/tmp(/.*)?": "system_u:object_r:kos_tmp_t:s0",
            f"{KOS_ROOT}/containers(/.*)?": "system_u:object_r:kos_container_t:s0"
        }
        
        for path, context in default_contexts.items():
            if path not in self.contexts:
                self.contexts[path] = context
        
        # Save changes
        self._save_policy()
        self._save_contexts()
    
    def set_mode(self, mode: SELinuxMode) -> bool:
        """
        Set the SELinux enforcement mode.
        
        Args:
            mode: New enforcement mode
            
        Returns:
            bool: Success or failure
        """
        try:
            self.mode = mode
            self._save_mode(mode)
            logger.info(f"Set SELinux mode to {mode.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to set SELinux mode: {e}")
            return False
    
    def get_file_context(self, path: str) -> SecurityContext:
        """
        Get the security context for a file path.
        
        Args:
            path: File path
            
        Returns:
            SecurityContext for the file
        """
        # Look for the most specific matching pattern
        best_match = None
        best_len = -1
        
        for pattern, context_str in self.contexts.items():
            # Handle regex-like patterns with wildcards
            is_match = False
            if pattern.endswith("(/.*)?"):
                # Directory and its contents
                dir_pattern = pattern[:-6]
                if path == dir_pattern or path.startswith(dir_pattern + "/"):
                    is_match = True
            elif pattern.endswith("(/.*)?$"):
                # Directory and its contents (with end anchor)
                dir_pattern = pattern[:-8]
                if path == dir_pattern or path.startswith(dir_pattern + "/"):
                    is_match = True
            elif pattern.endswith("(/.*)?/.*"):
                # Directory, subdirectories, and their contents
                dir_pattern = pattern[:-8]
                if path.startswith(dir_pattern + "/"):
                    is_match = True
            else:
                # Exact match
                is_match = (path == pattern)
            
            if is_match and len(pattern) > best_len:
                best_match = context_str
                best_len = len(pattern)
        
        if best_match:
            return SecurityContext.from_string(best_match)
        
        # Default context
        return SecurityContext("system_u", "object_r", "kos_t", "s0")
    
    def set_file_context(self, path: str, context: Union[SecurityContext, str]) -> bool:
        """
        Set the security context for a file path.
        
        Args:
            path: File path
            context: Security context
            
        Returns:
            bool: Success or failure
        """
        context_str = str(context) if isinstance(context, SecurityContext) else context
        
        try:
            self.contexts[path] = context_str
            self._save_contexts()
            logger.info(f"Set context for {path}: {context_str}")
            return True
        except Exception as e:
            logger.error(f"Failed to set file context: {e}")
            return False
    
    def add_type(self, type_name: str) -> bool:
        """
        Add a new type to the policy.
        
        Args:
            type_name: Name of the new type
            
        Returns:
            bool: Success or failure
        """
        if type_name in self.policy["types"]:
            logger.warning(f"Type already exists: {type_name}")
            return True
        
        try:
            self.policy["types"].append(type_name)
            self._save_policy()
            logger.info(f"Added type: {type_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add type: {e}")
            return False
    
    def add_role(self, role_name: str) -> bool:
        """
        Add a new role to the policy.
        
        Args:
            role_name: Name of the new role
            
        Returns:
            bool: Success or failure
        """
        if role_name in self.policy["roles"]:
            logger.warning(f"Role already exists: {role_name}")
            return True
        
        try:
            self.policy["roles"].append(role_name)
            self._save_policy()
            logger.info(f"Added role: {role_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add role: {e}")
            return False
    
    def add_user(self, user_name: str) -> bool:
        """
        Add a new user to the policy.
        
        Args:
            user_name: Name of the new user
            
        Returns:
            bool: Success or failure
        """
        if user_name in self.policy["users"]:
            logger.warning(f"User already exists: {user_name}")
            return True
        
        try:
            self.policy["users"].append(user_name)
            self._save_policy()
            logger.info(f"Added user: {user_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add user: {e}")
            return False
    
    def add_allow_rule(self, rule: Union[AllowRule, Dict[str, Any]]) -> bool:
        """
        Add a new allow rule to the policy.
        
        Args:
            rule: Allow rule to add
            
        Returns:
            bool: Success or failure
        """
        if isinstance(rule, AllowRule):
            rule_dict = {
                "source_type": rule.source_type,
                "target_type": rule.target_type,
                "object_class": rule.object_class,
                "permissions": rule.permissions
            }
        else:
            rule_dict = rule
        
        # Check for duplicate rule
        for existing in self.policy["allow_rules"]:
            if (existing["source_type"] == rule_dict["source_type"] and
                existing["target_type"] == rule_dict["target_type"] and
                existing["object_class"] == rule_dict["object_class"]):
                # Update permissions instead of adding duplicate
                existing["permissions"] |= rule_dict["permissions"]
                self._save_policy()
                return True
        
        try:
            self.policy["allow_rules"].append(rule_dict)
            self._save_policy()
            logger.info(f"Added allow rule: {rule_dict}")
            return True
        except Exception as e:
            logger.error(f"Failed to add allow rule: {e}")
            return False
    
    def add_transition(self, transition: Union[Transition, Dict[str, Any]]) -> bool:
        """
        Add a new type transition to the policy.
        
        Args:
            transition: Type transition to add
            
        Returns:
            bool: Success or failure
        """
        if isinstance(transition, Transition):
            transition_dict = {
                "source_type": transition.source_type,
                "target_type": transition.target_type,
                "object_class": transition.object_class,
                "result_type": transition.result_type
            }
        else:
            transition_dict = transition
        
        # Check for duplicate transition
        for existing in self.policy["transitions"]:
            if (existing["source_type"] == transition_dict["source_type"] and
                existing["target_type"] == transition_dict["target_type"] and
                existing["object_class"] == transition_dict["object_class"]):
                # Update result type
                existing["result_type"] = transition_dict["result_type"]
                self._save_policy()
                return True
        
        try:
            self.policy["transitions"].append(transition_dict)
            self._save_policy()
            logger.info(f"Added transition: {transition_dict}")
            return True
        except Exception as e:
            logger.error(f"Failed to add transition: {e}")
            return False
    
    def check_access(self, source_context: Union[SecurityContext, str],
                    target_context: Union[SecurityContext, str],
                    object_class: str, permissions: Union[int, str]) -> bool:
        """
        Check if a source context has permission to access a target context.
        
        Args:
            source_context: Source security context
            target_context: Target security context
            object_class: Object class (e.g., "file", "process")
            permissions: Requested permissions
            
        Returns:
            bool: Whether access is allowed
        """
        # If SELinux is disabled, allow all access
        if self.mode == SELinuxMode.DISABLED:
            return True
        
        # Convert contexts to objects if they're strings
        if isinstance(source_context, str):
            source_context = SecurityContext.from_string(source_context)
        
        if isinstance(target_context, str):
            target_context = SecurityContext.from_string(target_context)
        
        # Convert permissions to int if it's a string
        if isinstance(permissions, str):
            permissions = AccessVector.from_string(permissions)
        
        # Check if any allow rule grants the requested permissions
        for rule in self.policy["allow_rules"]:
            if (rule["source_type"] == source_context.type and
                rule["target_type"] == target_context.type and
                rule["object_class"] == object_class):
                
                # Check if the rule grants all requested permissions
                if (rule["permissions"] & permissions) == permissions:
                    return True
        
        # Access denied
        if self.mode == SELinuxMode.ENFORCING:
            from ..audit import AuditManager, AuditEventType
            audit = AuditManager()
            audit.log_event(
                AuditEventType.MAC_VIOLATION,
                "system",
                {
                    "source": str(source_context),
                    "target": str(target_context),
                    "object_class": object_class,
                    "permissions": AccessVector.to_string(permissions)
                },
                False
            )
            return False
        
        # In permissive mode, log the violation but allow access
        return True
    
    def get_transition_result(self, source_context: Union[SecurityContext, str],
                             target_context: Union[SecurityContext, str],
                             object_class: str) -> Optional[str]:
        """
        Get the resulting type from a type transition.
        
        Args:
            source_context: Source security context
            target_context: Target security context
            object_class: Object class (e.g., "file", "process")
            
        Returns:
            str: Resulting type, or None if no transition applies
        """
        # Convert contexts to objects if they're strings
        if isinstance(source_context, str):
            source_context = SecurityContext.from_string(source_context)
        
        if isinstance(target_context, str):
            target_context = SecurityContext.from_string(target_context)
        
        # Find a matching transition rule
        for transition in self.policy["transitions"]:
            if (transition["source_type"] == source_context.type and
                transition["target_type"] == target_context.type and
                transition["object_class"] == object_class):
                
                return transition["result_type"]
        
        return None
    
    def apply_transition(self, source_context: Union[SecurityContext, str],
                        target_context: Union[SecurityContext, str],
                        object_class: str) -> SecurityContext:
        """
        Apply type transition rules to get a new context.
        
        Args:
            source_context: Source security context
            target_context: Target security context
            object_class: Object class (e.g., "file", "process")
            
        Returns:
            SecurityContext: New context after transition
        """
        # Convert contexts to objects if they're strings
        if isinstance(source_context, str):
            source_context = SecurityContext.from_string(source_context)
        
        if isinstance(target_context, str):
            target_context = SecurityContext.from_string(target_context)
        
        # Get the transition result
        result_type = self.get_transition_result(
            source_context, target_context, object_class
        )
        
        if result_type:
            # Create a new context with the result type
            return SecurityContext(
                source_context.user,
                source_context.role,
                result_type,
                source_context.mls
            )
        
        # If no transition applies, use the target context for files
        # or source context for processes
        if object_class == "file":
            return target_context
        else:
            return source_context

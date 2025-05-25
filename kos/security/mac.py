"""
KOS Mandatory Access Control (MAC) Module

This module provides a SELinux/AppArmor-like MAC implementation for KOS,
enabling fine-grained security policy enforcement beyond traditional DAC.
"""

import os
import sys
import re
import logging
import threading
import json
import fnmatch
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Pattern

from kos.security.users import UserManager, GroupManager
from kos.security.permissions import FileMetadata

# Set up logging
logger = logging.getLogger('KOS.security.mac')

# Lock for MAC operations
_mac_lock = threading.RLock()

# Global flag to track if MAC is enabled
_mac_enabled = True

# Security context types
CONTEXT_TYPE_PROCESS = "process"
CONTEXT_TYPE_FILE = "file"
CONTEXT_TYPE_NETWORK = "network"
CONTEXT_TYPE_IPC = "ipc"

# Default security contexts
DEFAULT_PROCESS_CONTEXT = "system_u:system_r:unlabeled_t"
DEFAULT_FILE_CONTEXT = "system_u:object_r:unlabeled_t"
DEFAULT_NETWORK_CONTEXT = "system_u:object_r:unlabeled_t"
DEFAULT_IPC_CONTEXT = "system_u:object_r:unlabeled_t"

# Context storages
_process_contexts = {}  # pid -> context
_file_contexts = {}  # path -> context
_network_contexts = {}  # addr:port -> context
_ipc_contexts = {}  # ipc_id -> context

# Policy storage
_policy_rules = []  # List of policy rules


class SecurityContext:
    """Class representing a security context (label)"""
    
    def __init__(self, user: str, role: str, type: str, level: str = "s0"):
        """
        Initialize a security context
        
        Args:
            user: Security user
            role: Security role
            type: Security type
            level: Security level (MLS)
        """
        self.user = user
        self.role = role
        self.type = type
        self.level = level
    
    def to_dict(self) -> Dict[str, str]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "user": self.user,
            "role": self.role,
            "type": self.type,
            "level": self.level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'SecurityContext':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            SecurityContext instance
        """
        return cls(
            user=data.get("user", "system_u"),
            role=data.get("role", "system_r"),
            type=data.get("type", "unlabeled_t"),
            level=data.get("level", "s0")
        )
    
    @classmethod
    def from_string(cls, context_str: str) -> 'SecurityContext':
        """
        Create from string representation
        
        Args:
            context_str: String representation (user:role:type:level)
        
        Returns:
            SecurityContext instance
        """
        parts = context_str.split(':')
        
        user = parts[0] if len(parts) > 0 else "system_u"
        role = parts[1] if len(parts) > 1 else "system_r"
        type = parts[2] if len(parts) > 2 else "unlabeled_t"
        level = parts[3] if len(parts) > 3 else "s0"
        
        return cls(user, role, type, level)
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.user}:{self.role}:{self.type}:{self.level}"
    
    def __eq__(self, other) -> bool:
        """Check if contexts are equal"""
        if not isinstance(other, SecurityContext):
            return False
        
        return (self.user == other.user and
                self.role == other.role and
                self.type == other.type and
                self.level == other.level)


class PolicyRule:
    """Class representing a MAC policy rule"""
    
    def __init__(self, source_type: str, target_type: str, class_name: str,
                permissions: List[str], rule_type: str = "allow"):
        """
        Initialize a policy rule
        
        Args:
            source_type: Source security type
            target_type: Target security type
            class_name: Object class (file, process, etc.)
            permissions: List of permissions
            rule_type: Rule type (allow, deny, etc.)
        """
        self.source_type = source_type
        self.target_type = target_type
        self.class_name = class_name
        self.permissions = permissions
        self.rule_type = rule_type
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "source_type": self.source_type,
            "target_type": self.target_type,
            "class_name": self.class_name,
            "permissions": self.permissions,
            "rule_type": self.rule_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PolicyRule':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            PolicyRule instance
        """
        return cls(
            source_type=data.get("source_type", ""),
            target_type=data.get("target_type", ""),
            class_name=data.get("class_name", ""),
            permissions=data.get("permissions", []),
            rule_type=data.get("rule_type", "allow")
        )
    
    def matches(self, source_type: str, target_type: str, class_name: str) -> bool:
        """
        Check if rule matches the given types and class
        
        Args:
            source_type: Source security type
            target_type: Target security type
            class_name: Object class
        
        Returns:
            True if rule matches
        """
        # Handle wildcards
        source_match = (self.source_type == "*" or 
                        source_type == self.source_type or
                        source_type.endswith("_t") and self.source_type.endswith("_t") and
                        self.source_type[:-2] + "_t" == source_type)
        
        target_match = (self.target_type == "*" or 
                        target_type == self.target_type or
                        target_type.endswith("_t") and self.target_type.endswith("_t") and
                        self.target_type[:-2] + "_t" == target_type)
        
        class_match = (self.class_name == "*" or 
                       class_name == self.class_name)
        
        return source_match and target_match and class_match
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.rule_type} {self.source_type} {self.target_type}:{self.class_name} {{ {', '.join(self.permissions)} }};"


class FileContextPattern:
    """Class representing a file context pattern for path-based labeling"""
    
    def __init__(self, pattern: str, context: SecurityContext, regex: bool = False):
        """
        Initialize a file context pattern
        
        Args:
            pattern: File path pattern
            context: Security context
            regex: Whether pattern is a regex
        """
        self.pattern = pattern
        self.context = context
        self.regex = regex
        
        # Compile regex if needed
        self.compiled_pattern = None
        if regex:
            try:
                self.compiled_pattern = re.compile(pattern)
            except re.error:
                logger.error(f"Invalid regex pattern: {pattern}")
                self.regex = False
    
    def matches(self, path: str) -> bool:
        """
        Check if pattern matches the given path
        
        Args:
            path: File path
        
        Returns:
            True if pattern matches
        """
        if self.regex and self.compiled_pattern:
            return bool(self.compiled_pattern.match(path))
        else:
            return fnmatch.fnmatch(path, self.pattern)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "pattern": self.pattern,
            "context": str(self.context),
            "regex": self.regex
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileContextPattern':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            FileContextPattern instance
        """
        return cls(
            pattern=data.get("pattern", ""),
            context=SecurityContext.from_string(data.get("context", DEFAULT_FILE_CONTEXT)),
            regex=data.get("regex", False)
        )
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.pattern} {self.context}"


class MACManager:
    """Manager for MAC operations"""
    
    # File context patterns
    _file_context_patterns = []  # List of FileContextPattern objects
    
    @classmethod
    def enable(cls) -> Tuple[bool, str]:
        """
        Enable MAC enforcement
        
        Returns:
            (success, message)
        """
        global _mac_enabled
        
        with _mac_lock:
            if _mac_enabled:
                return True, "MAC already enabled"
            
            _mac_enabled = True
            logger.info("MAC enforcement enabled")
            return True, "MAC enforcement enabled"
    
    @classmethod
    def disable(cls) -> Tuple[bool, str]:
        """
        Disable MAC enforcement
        
        Returns:
            (success, message)
        """
        global _mac_enabled
        
        with _mac_lock:
            if not _mac_enabled:
                return True, "MAC already disabled"
            
            _mac_enabled = False
            logger.info("MAC enforcement disabled")
            return True, "MAC enforcement disabled"
    
    @classmethod
    def is_enabled(cls) -> bool:
        """
        Check if MAC enforcement is enabled
        
        Returns:
            True if enabled
        """
        return _mac_enabled
    
    @classmethod
    def get_process_context(cls, pid: int) -> SecurityContext:
        """
        Get security context for a process
        
        Args:
            pid: Process ID
        
        Returns:
            Security context
        """
        with _mac_lock:
            if pid in _process_contexts:
                return _process_contexts[pid]
            
            # Return default context
            return SecurityContext.from_string(DEFAULT_PROCESS_CONTEXT)
    
    @classmethod
    def set_process_context(cls, pid: int, context: SecurityContext) -> Tuple[bool, str]:
        """
        Set security context for a process
        
        Args:
            pid: Process ID
            context: Security context
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            _process_contexts[pid] = context
            return True, f"Context set for process {pid}"
    
    @classmethod
    def get_file_context(cls, path: str) -> SecurityContext:
        """
        Get security context for a file
        
        Args:
            path: File path
        
        Returns:
            Security context
        """
        with _mac_lock:
            # Check explicit file contexts
            if path in _file_contexts:
                return _file_contexts[path]
            
            # Check file context patterns
            for pattern in cls._file_context_patterns:
                if pattern.matches(path):
                    return pattern.context
            
            # Return default context
            return SecurityContext.from_string(DEFAULT_FILE_CONTEXT)
    
    @classmethod
    def set_file_context(cls, path: str, context: SecurityContext) -> Tuple[bool, str]:
        """
        Set security context for a file
        
        Args:
            path: File path
            context: Security context
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            # Verify file exists
            if not os.path.exists(path):
                return False, f"No such file or directory: {path}"
            
            _file_contexts[path] = context
            return True, f"Context set for file {path}"
    
    @classmethod
    def add_file_context_pattern(cls, pattern: str, context: SecurityContext, regex: bool = False) -> Tuple[bool, str]:
        """
        Add a file context pattern
        
        Args:
            pattern: File path pattern
            context: Security context
            regex: Whether pattern is a regex
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            # Create pattern
            file_pattern = FileContextPattern(pattern, context, regex)
            
            # Check for duplicate
            for i, existing in enumerate(cls._file_context_patterns):
                if existing.pattern == pattern:
                    # Replace existing pattern
                    cls._file_context_patterns[i] = file_pattern
                    return True, f"File context pattern updated: {pattern}"
            
            # Add new pattern
            cls._file_context_patterns.append(file_pattern)
            return True, f"File context pattern added: {pattern}"
    
    @classmethod
    def remove_file_context_pattern(cls, pattern: str) -> Tuple[bool, str]:
        """
        Remove a file context pattern
        
        Args:
            pattern: File path pattern
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            for i, existing in enumerate(cls._file_context_patterns):
                if existing.pattern == pattern:
                    del cls._file_context_patterns[i]
                    return True, f"File context pattern removed: {pattern}"
            
            return False, f"File context pattern not found: {pattern}"
    
    @classmethod
    def list_file_context_patterns(cls) -> List[FileContextPattern]:
        """
        List all file context patterns
        
        Returns:
            List of file context patterns
        """
        with _mac_lock:
            return cls._file_context_patterns.copy()
    
    @classmethod
    def add_policy_rule(cls, rule: PolicyRule) -> Tuple[bool, str]:
        """
        Add a policy rule
        
        Args:
            rule: Policy rule
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            # Check for duplicate
            for i, existing in enumerate(_policy_rules):
                if (existing.source_type == rule.source_type and
                    existing.target_type == rule.target_type and
                    existing.class_name == rule.class_name and
                    existing.rule_type == rule.rule_type):
                    # Update permissions
                    _policy_rules[i].permissions = list(set(_policy_rules[i].permissions + rule.permissions))
                    return True, "Policy rule updated"
            
            # Add new rule
            _policy_rules.append(rule)
            return True, "Policy rule added"
    
    @classmethod
    def remove_policy_rule(cls, source_type: str, target_type: str, class_name: str, rule_type: str = "allow") -> Tuple[bool, str]:
        """
        Remove a policy rule
        
        Args:
            source_type: Source security type
            target_type: Target security type
            class_name: Object class
            rule_type: Rule type
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            for i, rule in enumerate(_policy_rules):
                if (rule.source_type == source_type and
                    rule.target_type == target_type and
                    rule.class_name == class_name and
                    rule.rule_type == rule_type):
                    del _policy_rules[i]
                    return True, "Policy rule removed"
            
            return False, "Policy rule not found"
    
    @classmethod
    def list_policy_rules(cls) -> List[PolicyRule]:
        """
        List all policy rules
        
        Returns:
            List of policy rules
        """
        with _mac_lock:
            return _policy_rules.copy()
    
    @classmethod
    def check_permission(cls, source_context: SecurityContext, target_context: SecurityContext,
                       class_name: str, permission: str) -> bool:
        """
        Check if access is allowed by policy
        
        Args:
            source_context: Source security context
            target_context: Target security context
            class_name: Object class
            permission: Permission to check
        
        Returns:
            True if access is allowed
        """
        if not _mac_enabled:
            return True
        
        # Root/system always has access
        if source_context.user in ["root_u", "system_u"] and source_context.role in ["system_r"]:
            return True
        
        with _mac_lock:
            # Find matching rules
            allow_rules = []
            deny_rules = []
            
            for rule in _policy_rules:
                if rule.matches(source_context.type, target_context.type, class_name):
                    if rule.rule_type == "allow":
                        allow_rules.append(rule)
                    elif rule.rule_type == "deny":
                        deny_rules.append(rule)
            
            # Check if permission is denied
            for rule in deny_rules:
                if permission in rule.permissions or "*" in rule.permissions:
                    return False
            
            # Check if permission is allowed
            for rule in allow_rules:
                if permission in rule.permissions or "*" in rule.permissions:
                    return True
            
            # Default deny
            return False
    
    @classmethod
    def check_file_access(cls, pid: int, path: str, access_type: str) -> bool:
        """
        Check if process can access file
        
        Args:
            pid: Process ID
            path: File path
            access_type: Access type (read, write, execute)
        
        Returns:
            True if access is allowed
        """
        if not _mac_enabled:
            return True
        
        # Map access type to permission
        perm_map = {
            "read": "read",
            "write": "write",
            "execute": "execute",
            "append": "append"
        }
        
        if access_type not in perm_map:
            return False
        
        permission = perm_map[access_type]
        
        # Get contexts
        process_context = cls.get_process_context(pid)
        file_context = cls.get_file_context(path)
        
        # Check permission
        return cls.check_permission(process_context, file_context, "file", permission)
    
    @classmethod
    def check_process_transition(cls, source_pid: int, target_type: str) -> bool:
        """
        Check if process can transition to a new type
        
        Args:
            source_pid: Source process ID
            target_type: Target security type
        
        Returns:
            True if transition is allowed
        """
        if not _mac_enabled:
            return True
        
        # Get source context
        source_context = cls.get_process_context(source_pid)
        
        # Create target context
        target_context = SecurityContext(
            user=source_context.user,
            role=source_context.role,
            type=target_type,
            level=source_context.level
        )
        
        # Check permission
        return cls.check_permission(source_context, target_context, "process", "transition")
    
    @classmethod
    def save_policy(cls, policy_file: str) -> Tuple[bool, str]:
        """
        Save MAC policy to file
        
        Args:
            policy_file: File path
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            try:
                data = {
                    "policy_rules": [rule.to_dict() for rule in _policy_rules],
                    "file_context_patterns": [pattern.to_dict() for pattern in cls._file_context_patterns],
                    "file_contexts": {path: str(context) for path, context in _file_contexts.items()},
                    "process_contexts": {str(pid): str(context) for pid, context in _process_contexts.items()}
                }
                
                with open(policy_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"Policy saved to {policy_file}"
            except Exception as e:
                logger.error(f"Error saving policy: {e}")
                return False, str(e)
    
    @classmethod
    def load_policy(cls, policy_file: str) -> Tuple[bool, str]:
        """
        Load MAC policy from file
        
        Args:
            policy_file: File path
        
        Returns:
            (success, message)
        """
        global _policy_rules, _file_contexts, _process_contexts
        
        with _mac_lock:
            try:
                if not os.path.exists(policy_file):
                    return False, f"Policy file not found: {policy_file}"
                
                with open(policy_file, 'r') as f:
                    data = json.load(f)
                
                # Load policy rules
                _policy_rules = [PolicyRule.from_dict(rule_data) for rule_data in data.get("policy_rules", [])]
                
                # Load file context patterns
                cls._file_context_patterns = [FileContextPattern.from_dict(pattern_data) for pattern_data in data.get("file_context_patterns", [])]
                
                # Load file contexts
                _file_contexts = {path: SecurityContext.from_string(context_str) for path, context_str in data.get("file_contexts", {}).items()}
                
                # Load process contexts
                _process_contexts = {int(pid): SecurityContext.from_string(context_str) for pid, context_str in data.get("process_contexts", {}).items()}
                
                return True, "Policy loaded successfully"
            except Exception as e:
                logger.error(f"Error loading policy: {e}")
                return False, str(e)
    
    @classmethod
    def create_default_policy(cls) -> Tuple[bool, str]:
        """
        Create default MAC policy
        
        Returns:
            (success, message)
        """
        with _mac_lock:
            # Clear existing policy
            _policy_rules.clear()
            cls._file_context_patterns.clear()
            _file_contexts.clear()
            _process_contexts.clear()
            
            # Add basic policy rules
            
            # Allow system processes to do anything
            cls.add_policy_rule(PolicyRule(
                source_type="system_t",
                target_type="*",
                class_name="*",
                permissions=["*"],
                rule_type="allow"
            ))
            
            # Allow user processes to access user files
            cls.add_policy_rule(PolicyRule(
                source_type="user_t",
                target_type="user_file_t",
                class_name="file",
                permissions=["read", "write", "execute"],
                rule_type="allow"
            ))
            
            # Allow user processes to read system files
            cls.add_policy_rule(PolicyRule(
                source_type="user_t",
                target_type="system_file_t",
                class_name="file",
                permissions=["read", "execute"],
                rule_type="allow"
            ))
            
            # Allow user processes to use network
            cls.add_policy_rule(PolicyRule(
                source_type="user_t",
                target_type="network_t",
                class_name="network",
                permissions=["connect", "bind"],
                rule_type="allow"
            ))
            
            # Add basic file context patterns
            
            # System directories
            cls.add_file_context_pattern(
                pattern="/bin/*",
                context=SecurityContext.from_string("system_u:object_r:system_file_t:s0"),
                regex=False
            )
            
            cls.add_file_context_pattern(
                pattern="/etc/*",
                context=SecurityContext.from_string("system_u:object_r:system_file_t:s0"),
                regex=False
            )
            
            # User directories
            cls.add_file_context_pattern(
                pattern="/home/*",
                context=SecurityContext.from_string("user_u:object_r:user_file_t:s0"),
                regex=False
            )
            
            # Set process context for init
            cls.set_process_context(
                pid=1,
                context=SecurityContext.from_string("system_u:system_r:init_t:s0")
            )
            
            return True, "Default policy created"


def initialize():
    """Initialize MAC system"""
    logger.info("Initializing MAC system")
    
    # Create MAC directory
    mac_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(mac_dir, exist_ok=True)
    
    # Load policy if it exists
    policy_file = os.path.join(mac_dir, 'mac_policy.json')
    if os.path.exists(policy_file):
        MACManager.load_policy(policy_file)
    else:
        # Create default policy
        MACManager.create_default_policy()
        MACManager.save_policy(policy_file)
    
    logger.info("MAC system initialized")


# Initialize on module load
initialize()

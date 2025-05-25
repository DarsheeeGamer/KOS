"""
KOS Security Policy Management System

This module provides a centralized security policy framework for KOS,
allowing administrators to define, enforce, and audit security policies
across all security components.
"""

import os
import sys
import time
import json
import logging
import threading
import re
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.security.policy')

# Global policy data
_policy_lock = threading.RLock()
_policies = {}
_active_policy = None
_policy_handlers = {}
_policy_directory = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'policies')


class SecurityPolicy:
    """Class representing a security policy"""
    
    def __init__(self, name: str, description: str = "", version: str = "1.0.0",
                 author: str = "", created: float = None, modified: float = None,
                 settings: Dict[str, Any] = None, rules: Dict[str, Any] = None,
                 metadata: Dict[str, Any] = None):
        """
        Initialize a security policy
        
        Args:
            name: Policy name
            description: Policy description
            version: Policy version
            author: Policy author
            created: Creation timestamp
            modified: Modification timestamp
            settings: Policy settings
            rules: Policy rules
            metadata: Additional metadata
        """
        self.name = name
        self.description = description
        self.version = version
        self.author = author
        self.created = created or time.time()
        self.modified = modified or time.time()
        self.settings = settings or {}
        self.rules = rules or {}
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'author': self.author,
            'created': self.created,
            'modified': self.modified,
            'settings': self.settings,
            'rules': self.rules,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecurityPolicy':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            SecurityPolicy instance
        """
        return cls(
            name=data.get('name', ''),
            description=data.get('description', ''),
            version=data.get('version', '1.0.0'),
            author=data.get('author', ''),
            created=data.get('created'),
            modified=data.get('modified'),
            settings=data.get('settings', {}),
            rules=data.get('rules', {}),
            metadata=data.get('metadata', {})
        )
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate policy
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if not self.name:
            return False, "Policy name is required"
        
        # Check version format
        if not re.match(r'^\d+\.\d+\.\d+$', self.version):
            return False, "Invalid version format (should be X.Y.Z)"
        
        # Validate rules
        for component, rules in self.rules.items():
            if not isinstance(rules, dict):
                return False, f"Rules for component '{component}' must be a dictionary"
            
            # Check if handler exists for this component
            if component not in _policy_handlers:
                logger.warning(f"No handler registered for component: {component}")
        
        return True, ""
    
    def update_modified(self) -> None:
        """Update the modification timestamp"""
        self.modified = time.time()


class PolicyManager:
    """Manager for security policies"""
    
    @classmethod
    def initialize(cls) -> None:
        """Initialize policy manager"""
        # Create policy directory if it doesn't exist
        os.makedirs(_policy_directory, exist_ok=True)
        
        # Load existing policies
        cls.load_all_policies()
        
        # Load active policy if available
        active_policy_file = os.path.join(_policy_directory, 'active_policy.json')
        if os.path.exists(active_policy_file):
            try:
                with open(active_policy_file, 'r') as f:
                    active_policy_name = json.load(f).get('active_policy')
                
                if active_policy_name and active_policy_name in _policies:
                    cls.activate_policy(active_policy_name, apply=True)
            except Exception as e:
                logger.error(f"Error loading active policy: {e}")
    
    @classmethod
    def register_handler(cls, component: str, handler: Callable[[Dict[str, Any]], Tuple[bool, str]]) -> None:
        """
        Register a policy handler for a component
        
        Args:
            component: Component name
            handler: Handler function that takes rules and returns (success, message)
        """
        with _policy_lock:
            _policy_handlers[component] = handler
            logger.info(f"Registered policy handler for component: {component}")
    
    @classmethod
    def create_policy(cls, name: str, description: str = "", author: str = "",
                     settings: Dict[str, Any] = None, rules: Dict[str, Any] = None,
                     metadata: Dict[str, Any] = None) -> Tuple[bool, Union[SecurityPolicy, str]]:
        """
        Create a new security policy
        
        Args:
            name: Policy name
            description: Policy description
            author: Policy author
            settings: Policy settings
            rules: Policy rules
            metadata: Additional metadata
        
        Returns:
            Tuple of (success, policy or error message)
        """
        with _policy_lock:
            # Check if policy already exists
            if name in _policies:
                return False, f"Policy already exists: {name}"
            
            # Create policy
            policy = SecurityPolicy(
                name=name,
                description=description,
                author=author,
                settings=settings or {},
                rules=rules or {},
                metadata=metadata or {}
            )
            
            # Validate policy
            valid, error = policy.validate()
            if not valid:
                return False, error
            
            # Add to policies
            _policies[name] = policy
            
            # Save policy
            cls.save_policy(policy)
            
            logger.info(f"Created security policy: {name}")
            
            return True, policy
    
    @classmethod
    def get_policy(cls, name: str) -> Optional[SecurityPolicy]:
        """
        Get a security policy by name
        
        Args:
            name: Policy name
        
        Returns:
            SecurityPolicy instance or None
        """
        with _policy_lock:
            return _policies.get(name)
    
    @classmethod
    def update_policy(cls, name: str, description: str = None, author: str = None,
                     settings: Dict[str, Any] = None, rules: Dict[str, Any] = None,
                     metadata: Dict[str, Any] = None, version: str = None) -> Tuple[bool, Union[SecurityPolicy, str]]:
        """
        Update an existing security policy
        
        Args:
            name: Policy name
            description: Policy description
            author: Policy author
            settings: Policy settings
            rules: Policy rules
            metadata: Additional metadata
            version: Policy version
        
        Returns:
            Tuple of (success, policy or error message)
        """
        with _policy_lock:
            # Check if policy exists
            if name not in _policies:
                return False, f"Policy not found: {name}"
            
            # Get policy
            policy = _policies[name]
            
            # Update fields
            if description is not None:
                policy.description = description
            
            if author is not None:
                policy.author = author
            
            if settings is not None:
                policy.settings = settings
            
            if rules is not None:
                policy.rules = rules
            
            if metadata is not None:
                policy.metadata = metadata
            
            if version is not None:
                policy.version = version
            
            # Update modified timestamp
            policy.update_modified()
            
            # Validate policy
            valid, error = policy.validate()
            if not valid:
                return False, error
            
            # Save policy
            cls.save_policy(policy)
            
            # If this is the active policy, reapply it
            global _active_policy
            if _active_policy and _active_policy.name == name:
                cls.apply_policy(policy)
            
            logger.info(f"Updated security policy: {name}")
            
            return True, policy
    
    @classmethod
    def delete_policy(cls, name: str) -> Tuple[bool, str]:
        """
        Delete a security policy
        
        Args:
            name: Policy name
        
        Returns:
            Tuple of (success, message)
        """
        with _policy_lock:
            # Check if policy exists
            if name not in _policies:
                return False, f"Policy not found: {name}"
            
            # Check if policy is active
            global _active_policy
            if _active_policy and _active_policy.name == name:
                return False, "Cannot delete active policy"
            
            # Remove policy
            del _policies[name]
            
            # Delete policy file
            policy_file = os.path.join(_policy_directory, f"{name}.json")
            if os.path.exists(policy_file):
                os.remove(policy_file)
            
            logger.info(f"Deleted security policy: {name}")
            
            return True, f"Policy deleted: {name}"
    
    @classmethod
    def list_policies(cls) -> Dict[str, SecurityPolicy]:
        """
        List all security policies
        
        Returns:
            Dictionary of policy name to SecurityPolicy instance
        """
        with _policy_lock:
            return _policies.copy()
    
    @classmethod
    def save_policy(cls, policy: SecurityPolicy) -> Tuple[bool, str]:
        """
        Save a security policy to file
        
        Args:
            policy: SecurityPolicy instance
        
        Returns:
            Tuple of (success, message)
        """
        try:
            # Create policy directory if it doesn't exist
            os.makedirs(_policy_directory, exist_ok=True)
            
            # Save policy to file
            policy_file = os.path.join(_policy_directory, f"{policy.name}.json")
            with open(policy_file, 'w') as f:
                json.dump(policy.to_dict(), f, indent=2)
            
            return True, f"Policy saved: {policy.name}"
        except Exception as e:
            logger.error(f"Error saving policy: {e}")
            return False, str(e)
    
    @classmethod
    def load_policy(cls, name: str) -> Tuple[bool, Union[SecurityPolicy, str]]:
        """
        Load a security policy from file
        
        Args:
            name: Policy name
        
        Returns:
            Tuple of (success, policy or error message)
        """
        try:
            # Check if policy file exists
            policy_file = os.path.join(_policy_directory, f"{name}.json")
            if not os.path.exists(policy_file):
                return False, f"Policy file not found: {policy_file}"
            
            # Load policy from file
            with open(policy_file, 'r') as f:
                policy_data = json.load(f)
            
            # Create policy
            policy = SecurityPolicy.from_dict(policy_data)
            
            # Add to policies
            with _policy_lock:
                _policies[name] = policy
            
            return True, policy
        except Exception as e:
            logger.error(f"Error loading policy: {e}")
            return False, str(e)
    
    @classmethod
    def load_all_policies(cls) -> Tuple[int, int]:
        """
        Load all security policies from the policy directory
        
        Returns:
            Tuple of (success_count, error_count)
        """
        success_count = 0
        error_count = 0
        
        # Create policy directory if it doesn't exist
        os.makedirs(_policy_directory, exist_ok=True)
        
        # Load policies
        for filename in os.listdir(_policy_directory):
            if filename.endswith('.json') and filename != 'active_policy.json':
                policy_name = filename[:-5]  # Remove .json extension
                success, result = cls.load_policy(policy_name)
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
        
        logger.info(f"Loaded {success_count} policies ({error_count} errors)")
        
        return success_count, error_count
    
    @classmethod
    def activate_policy(cls, name: str, apply: bool = True) -> Tuple[bool, str]:
        """
        Activate a security policy
        
        Args:
            name: Policy name
            apply: Whether to apply the policy immediately
        
        Returns:
            Tuple of (success, message)
        """
        with _policy_lock:
            # Check if policy exists
            if name not in _policies:
                return False, f"Policy not found: {name}"
            
            # Get policy
            policy = _policies[name]
            
            # Set as active policy
            global _active_policy
            _active_policy = policy
            
            # Save active policy
            active_policy_file = os.path.join(_policy_directory, 'active_policy.json')
            with open(active_policy_file, 'w') as f:
                json.dump({'active_policy': name}, f)
            
            # Apply policy if requested
            if apply:
                return cls.apply_policy(policy)
            
            logger.info(f"Activated security policy: {name}")
            
            return True, f"Policy activated: {name}"
    
    @classmethod
    def deactivate_policy(cls) -> Tuple[bool, str]:
        """
        Deactivate the current security policy
        
        Returns:
            Tuple of (success, message)
        """
        with _policy_lock:
            # Check if there's an active policy
            global _active_policy
            if not _active_policy:
                return False, "No active policy"
            
            # Get policy name
            policy_name = _active_policy.name
            
            # Clear active policy
            _active_policy = None
            
            # Remove active policy file
            active_policy_file = os.path.join(_policy_directory, 'active_policy.json')
            if os.path.exists(active_policy_file):
                os.remove(active_policy_file)
            
            logger.info("Deactivated security policy")
            
            return True, f"Policy deactivated: {policy_name}"
    
    @classmethod
    def get_active_policy(cls) -> Optional[SecurityPolicy]:
        """
        Get the active security policy
        
        Returns:
            SecurityPolicy instance or None
        """
        with _policy_lock:
            return _active_policy
    
    @classmethod
    def apply_policy(cls, policy: SecurityPolicy) -> Tuple[bool, str]:
        """
        Apply a security policy to all components
        
        Args:
            policy: SecurityPolicy instance
        
        Returns:
            Tuple of (success, message)
        """
        success_count = 0
        error_count = 0
        errors = []
        
        # Apply policy to each component
        for component, rules in policy.rules.items():
            # Check if handler exists
            if component not in _policy_handlers:
                logger.warning(f"No handler registered for component: {component}")
                continue
            
            # Get handler
            handler = _policy_handlers[component]
            
            # Apply rules
            try:
                success, message = handler(rules)
                
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"{component}: {message}")
            except Exception as e:
                error_count += 1
                errors.append(f"{component}: {str(e)}")
                logger.error(f"Error applying policy to {component}: {e}")
        
        # Log result
        if error_count == 0:
            logger.info(f"Applied policy to {success_count} components")
            return True, f"Policy applied to {success_count} components"
        else:
            logger.warning(f"Applied policy to {success_count} components with {error_count} errors")
            return False, f"Policy applied to {success_count} components with {error_count} errors: {', '.join(errors)}"
    
    @classmethod
    def validate_policy(cls, policy: SecurityPolicy) -> Tuple[bool, str]:
        """
        Validate a security policy
        
        Args:
            policy: SecurityPolicy instance
        
        Returns:
            Tuple of (success, message)
        """
        # Validate policy structure
        valid, error = policy.validate()
        if not valid:
            return False, error
        
        # Validate rules for each component
        for component, rules in policy.rules.items():
            # Check if handler exists
            if component not in _policy_handlers:
                logger.warning(f"No handler registered for component: {component}")
                continue
            
            # Get validator if available
            validator = _policy_handlers.get(f"{component}_validator")
            
            if validator:
                try:
                    valid, error = validator(rules)
                    if not valid:
                        return False, f"{component}: {error}"
                except Exception as e:
                    return False, f"{component}: {str(e)}"
        
        return True, "Policy is valid"
    
    @classmethod
    def export_policy(cls, name: str, export_file: str) -> Tuple[bool, str]:
        """
        Export a security policy to a file
        
        Args:
            name: Policy name
            export_file: Export file path
        
        Returns:
            Tuple of (success, message)
        """
        with _policy_lock:
            # Check if policy exists
            if name not in _policies:
                return False, f"Policy not found: {name}"
            
            # Get policy
            policy = _policies[name]
            
            try:
                # Export policy to file
                with open(export_file, 'w') as f:
                    json.dump(policy.to_dict(), f, indent=2)
                
                return True, f"Policy exported to: {export_file}"
            except Exception as e:
                logger.error(f"Error exporting policy: {e}")
                return False, str(e)
    
    @classmethod
    def import_policy(cls, import_file: str, overwrite: bool = False) -> Tuple[bool, Union[SecurityPolicy, str]]:
        """
        Import a security policy from a file
        
        Args:
            import_file: Import file path
            overwrite: Whether to overwrite existing policy
        
        Returns:
            Tuple of (success, policy or error message)
        """
        try:
            # Check if file exists
            if not os.path.exists(import_file):
                return False, f"Import file not found: {import_file}"
            
            # Load policy from file
            with open(import_file, 'r') as f:
                policy_data = json.load(f)
            
            # Create policy
            policy = SecurityPolicy.from_dict(policy_data)
            
            # Validate policy
            valid, error = policy.validate()
            if not valid:
                return False, error
            
            with _policy_lock:
                # Check if policy already exists
                if policy.name in _policies and not overwrite:
                    return False, f"Policy already exists: {policy.name}"
                
                # Add to policies
                _policies[policy.name] = policy
                
                # Save policy
                cls.save_policy(policy)
            
            logger.info(f"Imported security policy: {policy.name}")
            
            return True, policy
        except Exception as e:
            logger.error(f"Error importing policy: {e}")
            return False, str(e)


# Create default security policy
def create_default_policy() -> SecurityPolicy:
    """
    Create a default security policy
    
    Returns:
        SecurityPolicy instance
    """
    policy = SecurityPolicy(
        name="default",
        description="Default KOS security policy",
        author="KOS System",
        version="1.0.0",
        settings={
            "enforce_mac": True,
            "enforce_acl": True,
            "enable_audit": True,
            "enable_fim": True,
            "enable_ids": True,
            "enable_network_monitor": True,
            "log_level": "info",
            "password_min_length": 8,
            "password_complexity": True,
            "max_login_attempts": 5,
            "session_timeout": 3600,
            "account_lockout_threshold": 5,
            "account_lockout_duration": 300
        },
        rules={
            "acl": {
                "default_permission": "644",
                "restricted_paths": [
                    {"path": "/etc", "permission": "644", "recursive": True},
                    {"path": "/bin", "permission": "755", "recursive": True}
                ]
            },
            "mac": {
                "default_context": "system_u:object_r:default_t",
                "contexts": [
                    {"path": "/etc", "context": "system_u:object_r:etc_t", "recursive": True},
                    {"path": "/bin", "context": "system_u:object_r:bin_t", "recursive": True}
                ],
                "transitions": [
                    {"source": "user_t", "target": "etc_t", "class": "file", "permission": "read"}
                ]
            },
            "fim": {
                "monitored_paths": [
                    {"path": "/etc", "recursive": True, "priority": "high"},
                    {"path": "/bin", "recursive": True, "priority": "medium"}
                ],
                "hash_algorithm": "sha256",
                "check_interval": 3600
            },
            "ids": {
                "rules": [
                    {"name": "suspicious_login", "pattern": "Failed login", "severity": "high"},
                    {"name": "root_access", "pattern": "Root access", "severity": "critical"}
                ],
                "scan_interval": 300
            },
            "network_monitor": {
                "monitored_ports": [22, 80, 443],
                "blacklisted_ips": [],
                "monitor_interval": 60
            },
            "auth": {
                "pam_modules": [
                    {"name": "pam_unix", "type": "auth", "control": "required"},
                    {"name": "pam_deny", "type": "auth", "control": "required"}
                ],
                "allowed_users": ["root", "admin"],
                "allowed_groups": ["wheel", "sudo"]
            },
            "audit": {
                "enabled": True,
                "sync_write": True,
                "hash_chain": True,
                "monitored_events": ["authentication", "authorization", "file_access"]
            }
        },
        metadata={
            "compliance": {
                "cis_level": 1,
                "hipaa_compliant": True,
                "pci_dss_compliant": True
            }
        }
    )
    
    return policy


# Initialize module
def initialize() -> None:
    """Initialize policy module"""
    logger.info("Initializing security policy management")
    
    # Initialize policy manager
    PolicyManager.initialize()
    
    # Create default policy if no policies exist
    if not PolicyManager.list_policies():
        default_policy = create_default_policy()
        PolicyManager.save_policy(default_policy)
        _policies[default_policy.name] = default_policy
        
        # Activate default policy
        PolicyManager.activate_policy("default", apply=False)
    
    logger.info("Security policy management initialized")


# Initialize on module load
initialize()

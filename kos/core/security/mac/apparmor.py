"""
AppArmor-like Profile-Based Confinement for KOS

This module implements an AppArmor-like MAC system for KOS, providing:
- Path-based access control profiles
- Application confinement
- Resource restrictions
- Simple policy language
"""

import os
import re
import json
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any, Pattern

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
APPARMOR_PROFILES_DIR = os.path.join(KOS_ROOT, 'etc/apparmor.d')
APPARMOR_CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/apparmor/apparmor.conf')

# Ensure directories exist
os.makedirs(APPARMOR_PROFILES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(APPARMOR_CONFIG_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ProfileMode(str, Enum):
    """AppArmor profile enforcement modes."""
    ENFORCE = "enforce"
    COMPLAIN = "complain"
    DISABLE = "disable"


class AccessMode(str, Enum):
    """Access modes for path rules."""
    READ = "r"
    WRITE = "w"
    APPEND = "a"
    EXECUTE = "x"
    LINK = "l"
    LOCK = "k"
    MEMORY_MAP = "m"
    
    @staticmethod
    def from_string(mode_str: str) -> Set[str]:
        """
        Convert a mode string to a set of modes.
        
        Args:
            mode_str: String like "rw" or "rwx"
            
        Returns:
            Set of AccessMode values
        """
        modes = set()
        for char in mode_str:
            for mode in AccessMode:
                if char == mode.value:
                    modes.add(mode)
        
        return modes
    
    @staticmethod
    def to_string(modes: Set['AccessMode']) -> str:
        """
        Convert a set of modes to a string.
        
        Args:
            modes: Set of AccessMode values
            
        Returns:
            String representation
        """
        return ''.join(sorted([mode.value for mode in modes]))


class PathRule:
    """
    Represents a path-based access rule in an AppArmor profile.
    
    Path rules define what access modes are allowed for specific file paths.
    """
    
    def __init__(self, path: str, modes: Union[Set[AccessMode], str]):
        """
        Initialize a path rule.
        
        Args:
            path: File path pattern
            modes: Access modes
        """
        self.path = path
        
        if isinstance(modes, str):
            self.modes = AccessMode.from_string(modes)
        else:
            self.modes = modes
        
        # Compile the path pattern
        self.pattern = self._compile_path_pattern(path)
    
    def _compile_path_pattern(self, path: str) -> Pattern:
        """
        Compile a path pattern into a regex pattern.
        
        Args:
            path: Path pattern with wildcards
            
        Returns:
            Compiled regex pattern
        """
        # Convert AppArmor-style wildcards to regex
        # * -> [^/]*
        # ** -> .*
        # ? -> .
        # {a,b} -> (a|b)
        
        # Escape special regex chars
        regex = re.escape(path)
        
        # Replace AppArmor wildcards with regex equivalents
        regex = regex.replace(r'\*\*', '.*')
        regex = regex.replace(r'\*', '[^/]*')
        regex = regex.replace(r'\?', '.')
        
        # Handle alternatives like {bin,sbin}
        def replace_alt(match):
            inner = match.group(1)
            parts = inner.split(',')
            return '(' + '|'.join(parts) + ')'
        
        regex = re.sub(r'\\\{([^}]+)\\\}', replace_alt, regex)
        
        # Anchor the regex
        regex = '^' + regex + '$'
        
        return re.compile(regex)
    
    def matches(self, path: str) -> bool:
        """
        Check if a path matches this rule's pattern.
        
        Args:
            path: Path to check
            
        Returns:
            bool: Whether the path matches
        """
        return bool(self.pattern.match(path))
    
    def allows(self, path: str, requested_modes: Union[Set[AccessMode], str]) -> bool:
        """
        Check if this rule allows the requested access to a path.
        
        Args:
            path: Path to check
            requested_modes: Requested access modes
            
        Returns:
            bool: Whether access is allowed
        """
        if not self.matches(path):
            return False
        
        if isinstance(requested_modes, str):
            requested_set = AccessMode.from_string(requested_modes)
        else:
            requested_set = requested_modes
        
        return requested_set.issubset(self.modes)
    
    def __str__(self) -> str:
        """Convert to string representation."""
        return f"{self.path} {AccessMode.to_string(self.modes)}"


class CapabilityRule:
    """
    Represents a capability rule in an AppArmor profile.
    
    Capability rules define what Linux capabilities are allowed
    for a confined process.
    """
    
    def __init__(self, capability: str):
        """
        Initialize a capability rule.
        
        Args:
            capability: Linux capability name
        """
        self.capability = capability
    
    def __str__(self) -> str:
        """Convert to string representation."""
        return f"capability {self.capability}"


class NetworkRule:
    """
    Represents a network access rule in an AppArmor profile.
    
    Network rules define what network operations are allowed.
    """
    
    def __init__(self, family: str, socket_type: str):
        """
        Initialize a network rule.
        
        Args:
            family: Network family (e.g., "inet", "unix")
            socket_type: Socket type (e.g., "stream", "dgram")
        """
        self.family = family
        self.socket_type = socket_type
    
    def __str__(self) -> str:
        """Convert to string representation."""
        return f"network {self.family} {self.socket_type}"


class SecurityProfile:
    """
    Represents an AppArmor security profile.
    
    Security profiles define the confinement rules for an application,
    including file access, capabilities, and network access.
    """
    
    def __init__(self, name: str, mode: ProfileMode = ProfileMode.ENFORCE):
        """
        Initialize a security profile.
        
        Args:
            name: Profile name
            mode: Enforcement mode
        """
        self.name = name
        self.mode = mode
        self.path_rules = []
        self.capability_rules = []
        self.network_rules = []
        self.include_profiles = []
    
    def add_path_rule(self, path: str, modes: Union[Set[AccessMode], str]) -> None:
        """
        Add a path rule to the profile.
        
        Args:
            path: File path pattern
            modes: Access modes
        """
        rule = PathRule(path, modes)
        self.path_rules.append(rule)
    
    def add_capability_rule(self, capability: str) -> None:
        """
        Add a capability rule to the profile.
        
        Args:
            capability: Linux capability name
        """
        rule = CapabilityRule(capability)
        self.capability_rules.append(rule)
    
    def add_network_rule(self, family: str, socket_type: str) -> None:
        """
        Add a network rule to the profile.
        
        Args:
            family: Network family
            socket_type: Socket type
        """
        rule = NetworkRule(family, socket_type)
        self.network_rules.append(rule)
    
    def include_profile(self, profile_name: str) -> None:
        """
        Include another profile in this profile.
        
        Args:
            profile_name: Name of profile to include
        """
        self.include_profiles.append(profile_name)
    
    def check_path_access(self, path: str, 
                         requested_modes: Union[Set[AccessMode], str]) -> bool:
        """
        Check if this profile allows the requested access to a path.
        
        Args:
            path: Path to check
            requested_modes: Requested access modes
            
        Returns:
            bool: Whether access is allowed
        """
        if self.mode == ProfileMode.DISABLE:
            return True
        
        if isinstance(requested_modes, str):
            requested_set = AccessMode.from_string(requested_modes)
        else:
            requested_set = requested_modes
        
        # Check each path rule
        for rule in self.path_rules:
            if rule.allows(path, requested_set):
                return True
        
        # Access denied
        if self.mode == ProfileMode.ENFORCE:
            return False
        
        # In complain mode, log but allow
        logger.warning(
            f"AppArmor profile {self.name} complains about "
            f"access to {path} with mode {AccessMode.to_string(requested_set)}"
        )
        return True
    
    def check_capability(self, capability: str) -> bool:
        """
        Check if this profile allows a capability.
        
        Args:
            capability: Linux capability name
            
        Returns:
            bool: Whether the capability is allowed
        """
        if self.mode == ProfileMode.DISABLE:
            return True
        
        # Check if the capability is allowed
        for rule in self.capability_rules:
            if rule.capability == capability:
                return True
        
        # Capability denied
        if self.mode == ProfileMode.ENFORCE:
            return False
        
        # In complain mode, log but allow
        logger.warning(
            f"AppArmor profile {self.name} complains about "
            f"capability {capability}"
        )
        return True
    
    def check_network(self, family: str, socket_type: str) -> bool:
        """
        Check if this profile allows network access.
        
        Args:
            family: Network family
            socket_type: Socket type
            
        Returns:
            bool: Whether network access is allowed
        """
        if self.mode == ProfileMode.DISABLE:
            return True
        
        # Check if the network access is allowed
        for rule in self.network_rules:
            if rule.family == family and rule.socket_type == socket_type:
                return True
        
        # Network access denied
        if self.mode == ProfileMode.ENFORCE:
            return False
        
        # In complain mode, log but allow
        logger.warning(
            f"AppArmor profile {self.name} complains about "
            f"network {family} {socket_type}"
        )
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the profile to a dictionary.
        
        Returns:
            Dict representation of the profile
        """
        return {
            "name": self.name,
            "mode": self.mode.value,
            "path_rules": [
                {"path": rule.path, "modes": AccessMode.to_string(rule.modes)}
                for rule in self.path_rules
            ],
            "capability_rules": [
                rule.capability for rule in self.capability_rules
            ],
            "network_rules": [
                {"family": rule.family, "socket_type": rule.socket_type}
                for rule in self.network_rules
            ],
            "include_profiles": self.include_profiles
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'SecurityProfile':
        """
        Create a profile from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            SecurityProfile object
        """
        profile = SecurityProfile(
            data["name"],
            ProfileMode(data["mode"])
        )
        
        for rule_data in data.get("path_rules", []):
            profile.add_path_rule(rule_data["path"], rule_data["modes"])
        
        for capability in data.get("capability_rules", []):
            profile.add_capability_rule(capability)
        
        for rule_data in data.get("network_rules", []):
            profile.add_network_rule(
                rule_data["family"], rule_data["socket_type"]
            )
        
        for include in data.get("include_profiles", []):
            profile.include_profile(include)
        
        return profile


class AppArmorManager:
    """
    Manages AppArmor-like MAC security for KOS.
    
    This class handles security profiles, policy parsing, and access decisions
    for the AppArmor-like MAC system.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AppArmorManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the AppArmor manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self.global_mode = self._load_global_mode()
        self.profiles = self._load_profiles()
        self._ensure_default_profiles()
    
    def _load_global_mode(self) -> ProfileMode:
        """Load global AppArmor mode from configuration."""
        if os.path.exists(APPARMOR_CONFIG_PATH):
            try:
                with open(APPARMOR_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    mode_str = config.get("mode", ProfileMode.COMPLAIN.value)
                    try:
                        return ProfileMode(mode_str)
                    except ValueError:
                        logger.error(f"Invalid AppArmor mode: {mode_str}")
            except Exception as e:
                logger.error(f"Failed to load AppArmor config: {e}")
        
        # Default to complain mode
        self._save_global_mode(ProfileMode.COMPLAIN)
        return ProfileMode.COMPLAIN
    
    def _save_global_mode(self, mode: ProfileMode):
        """Save global AppArmor mode to configuration."""
        try:
            config = {"mode": mode.value}
            os.makedirs(os.path.dirname(APPARMOR_CONFIG_PATH), exist_ok=True)
            with open(APPARMOR_CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save AppArmor config: {e}")
    
    def _load_profiles(self) -> Dict[str, SecurityProfile]:
        """Load security profiles from disk."""
        profiles = {}
        
        if os.path.exists(APPARMOR_PROFILES_DIR):
            for filename in os.listdir(APPARMOR_PROFILES_DIR):
                if not filename.endswith('.json'):
                    continue
                
                path = os.path.join(APPARMOR_PROFILES_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        profile = SecurityProfile.from_dict(data)
                        profiles[profile.name] = profile
                except Exception as e:
                    logger.error(f"Failed to load profile {filename}: {e}")
        
        return profiles
    
    def _ensure_default_profiles(self):
        """Ensure default security profiles exist."""
        # Default base profile
        if "base" not in self.profiles:
            base = SecurityProfile("base", ProfileMode.ENFORCE)
            
            # Basic directories that most programs need
            base.add_path_rule(f"{KOS_ROOT}/bin/**", "rx")
            base.add_path_rule(f"{KOS_ROOT}/lib/**", "r")
            base.add_path_rule(f"{KOS_ROOT}/etc/**", "r")
            base.add_path_rule(f"{KOS_ROOT}/var/lib/**", "r")
            base.add_path_rule(f"{KOS_ROOT}/tmp/**", "rw")
            
            self.profiles["base"] = base
            self._save_profile(base)
        
        # Container profile
        if "container" not in self.profiles:
            container = SecurityProfile("container", ProfileMode.ENFORCE)
            
            # Include base profile
            container.include_profile("base")
            
            # Container-specific paths
            container.add_path_rule(f"{KOS_ROOT}/containers/**", "rw")
            
            # Network capabilities
            container.add_network_rule("inet", "stream")
            container.add_network_rule("inet", "dgram")
            container.add_network_rule("unix", "stream")
            container.add_network_rule("unix", "dgram")
            
            # Limited capabilities
            container.add_capability_rule("net_bind_service")
            container.add_capability_rule("sys_chroot")
            
            self.profiles["container"] = container
            self._save_profile(container)
        
        # Unconfined profile
        if "unconfined" not in self.profiles:
            unconfined = SecurityProfile("unconfined", ProfileMode.DISABLE)
            
            # Allow everything
            unconfined.add_path_rule("/**", "rwxamlk")
            
            # All capabilities
            for capability in [
                "chown", "dac_override", "dac_read_search", "fowner", "fsetid",
                "kill", "setgid", "setuid", "setpcap", "net_bind_service",
                "net_broadcast", "net_admin", "net_raw", "ipc_lock", "ipc_owner",
                "sys_module", "sys_rawio", "sys_chroot", "sys_ptrace",
                "sys_admin", "sys_boot", "sys_nice", "sys_resource", "sys_time",
                "mknod", "audit_write", "audit_control"
            ]:
                unconfined.add_capability_rule(capability)
            
            # All network
            for family in ["inet", "inet6", "unix", "netlink"]:
                for socket_type in ["stream", "dgram", "raw", "seqpacket"]:
                    unconfined.add_network_rule(family, socket_type)
            
            self.profiles["unconfined"] = unconfined
            self._save_profile(unconfined)
    
    def _save_profile(self, profile: SecurityProfile):
        """Save a security profile to disk."""
        try:
            path = os.path.join(APPARMOR_PROFILES_DIR, f"{profile.name}.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                json.dump(profile.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save profile {profile.name}: {e}")
    
    def set_global_mode(self, mode: ProfileMode) -> bool:
        """
        Set the global AppArmor enforcement mode.
        
        Args:
            mode: New enforcement mode
            
        Returns:
            bool: Success or failure
        """
        try:
            self.global_mode = mode
            self._save_global_mode(mode)
            logger.info(f"Set AppArmor mode to {mode.value}")
            return True
        except Exception as e:
            logger.error(f"Failed to set AppArmor mode: {e}")
            return False
    
    def get_profile(self, name: str) -> Optional[SecurityProfile]:
        """
        Get a security profile by name.
        
        Args:
            name: Profile name
            
        Returns:
            SecurityProfile or None if not found
        """
        return self.profiles.get(name)
    
    def add_profile(self, profile: SecurityProfile) -> bool:
        """
        Add or update a security profile.
        
        Args:
            profile: Security profile
            
        Returns:
            bool: Success or failure
        """
        try:
            self.profiles[profile.name] = profile
            self._save_profile(profile)
            logger.info(f"Added/updated profile: {profile.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add/update profile: {e}")
            return False
    
    def remove_profile(self, name: str) -> bool:
        """
        Remove a security profile.
        
        Args:
            name: Profile name
            
        Returns:
            bool: Success or failure
        """
        if name not in self.profiles:
            logger.warning(f"Profile not found: {name}")
            return False
        
        try:
            path = os.path.join(APPARMOR_PROFILES_DIR, f"{name}.json")
            if os.path.exists(path):
                os.remove(path)
            
            del self.profiles[name]
            logger.info(f"Removed profile: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to remove profile: {e}")
            return False
    
    def check_access(self, profile_name: str, path: str, 
                    requested_modes: Union[Set[AccessMode], str]) -> bool:
        """
        Check if a profile allows access to a path.
        
        Args:
            profile_name: Profile name
            path: Path to check
            requested_modes: Requested access modes
            
        Returns:
            bool: Whether access is allowed
        """
        # If global mode is disabled, allow all access
        if self.global_mode == ProfileMode.DISABLE:
            return True
        
        # Get the profile
        profile = self.profiles.get(profile_name)
        if not profile:
            logger.warning(f"Profile not found: {profile_name}")
            return True  # Allow if profile doesn't exist
        
        # Check access against the profile
        result = profile.check_path_access(path, requested_modes)
        
        # If denied and in global complain mode, log but allow
        if not result and self.global_mode == ProfileMode.COMPLAIN:
            logger.warning(
                f"AppArmor profile {profile_name} denies "
                f"access to {path} with mode {requested_modes}"
            )
            return True
        
        return result
    
    def check_capability(self, profile_name: str, capability: str) -> bool:
        """
        Check if a profile allows a capability.
        
        Args:
            profile_name: Profile name
            capability: Linux capability name
            
        Returns:
            bool: Whether the capability is allowed
        """
        # If global mode is disabled, allow all capabilities
        if self.global_mode == ProfileMode.DISABLE:
            return True
        
        # Get the profile
        profile = self.profiles.get(profile_name)
        if not profile:
            logger.warning(f"Profile not found: {profile_name}")
            return True  # Allow if profile doesn't exist
        
        # Check capability against the profile
        result = profile.check_capability(capability)
        
        # If denied and in global complain mode, log but allow
        if not result and self.global_mode == ProfileMode.COMPLAIN:
            logger.warning(
                f"AppArmor profile {profile_name} denies "
                f"capability {capability}"
            )
            return True
        
        return result
    
    def check_network(self, profile_name: str, family: str, socket_type: str) -> bool:
        """
        Check if a profile allows network access.
        
        Args:
            profile_name: Profile name
            family: Network family
            socket_type: Socket type
            
        Returns:
            bool: Whether network access is allowed
        """
        # If global mode is disabled, allow all network access
        if self.global_mode == ProfileMode.DISABLE:
            return True
        
        # Get the profile
        profile = self.profiles.get(profile_name)
        if not profile:
            logger.warning(f"Profile not found: {profile_name}")
            return True  # Allow if profile doesn't exist
        
        # Check network access against the profile
        result = profile.check_network(family, socket_type)
        
        # If denied and in global complain mode, log but allow
        if not result and self.global_mode == ProfileMode.COMPLAIN:
            logger.warning(
                f"AppArmor profile {profile_name} denies "
                f"network {family} {socket_type}"
            )
            return True
        
        return result

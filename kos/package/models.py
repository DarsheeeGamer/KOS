"""
KOS Package Management Data Models

This module defines Pydantic models for package management data structures,
ensuring proper validation, serialization and type safety throughout the system.
"""

from typing import List, Dict, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
import os


class PackageDependency(BaseModel):
    """Represents a package dependency with version requirements
    
    This model supports semver-style version constraints such as:
    - "latest" - Latest available version
    - "1.2.3" - Exact version match
    - ">1.2.3" - Greater than specified version
    - ">=1.2.3" - Greater than or equal to specified version
    - "<1.2.3" - Less than specified version
    - "<=1.2.3" - Less than or equal to specified version
    - "^1.2.3" - Compatible with version (same as >=1.2.3 <2.0.0)
    - "~1.2.3" - Approximately equivalent to version (same as >=1.2.3 <1.3.0)
    - "1.2.3 - 2.3.4" - Range of versions inclusive
    """
    name: str
    version_req: str = "latest"
    optional: bool = False
    repository: Optional[str] = None  # Source repository preference
    alternative_names: List[str] = []  # Alternative package names (e.g., for different repos)
    reason: Optional[str] = None  # Why this dependency is required
    
    @validator('version_req')
    def validate_version_req(cls, v):
        """Validate version requirement format"""
        if v == "latest":
            return v
            
        # Basic validation of version requirement format
        valid_operators = [">", "<", ">=", "<=", "=", "^", "~"]
        
        # Strip spaces
        v = v.strip()
        
        # Check for range format (e.g., "1.2.3 - 2.3.4")
        if " - " in v:
            parts = v.split(" - ")
            if len(parts) != 2:
                raise ValueError(f"Invalid version range format: {v}")
            return v
            
        # Check for operator prefix
        if any(v.startswith(op) for op in valid_operators):
            # It has a valid operator prefix, now validate the version part
            for op in valid_operators:
                if v.startswith(op):
                    version_part = v[len(op):]
                    break
            
            # Basic version format check
            parts = version_part.split('.')
            if not (1 <= len(parts) <= 3):
                raise ValueError(f"Invalid version format in requirement: {v}")
            
            # Ensure each part is a number
            try:
                for part in parts:
                    int(part.split('-')[0])  # Allow for pre-release versions like 1.0.0-beta1
            except ValueError:
                raise ValueError(f"Invalid version number in requirement: {v}")
                
            return v
        
        # No operator, so should be an exact version
        parts = v.split('.')
        if not (1 <= len(parts) <= 3):
            raise ValueError(f"Invalid version format: {v}")
            
        # Ensure each part is a number
        try:
            for part in parts:
                int(part.split('-')[0])  # Allow for pre-release versions
        except ValueError:
            raise ValueError(f"Invalid version number: {v}")
            
        # If it's just a version without an operator, treat it as an exact match
        return v
    
    def is_satisfied_by(self, version: str) -> bool:
        """Check if a version satisfies this dependency requirement"""
        if self.version_req == "latest":
            return True  # Any version satisfies "latest"
            
        # Handle exact version match
        if not any(self.version_req.startswith(op) for op in [">", "<", ">=", "<=", "=", "^", "~"]):
            if " - " not in self.version_req:
                return self.version_req == version
        
        # For more complex version comparison, we would ideally use packaging.version
        # This is a simplified implementation
        
        # Parse versions into components
        def parse_version(ver):
            # Handle pre-release versions like 1.0.0-beta1
            ver_parts = ver.split('-')
            base_ver = ver_parts[0]
            pre_release = ver_parts[1] if len(ver_parts) > 1 else None
            
            # Parse the version numbers
            parts = base_ver.split('.')
            # Pad with zeros if needed
            while len(parts) < 3:
                parts.append('0')
            
            # Convert to integers
            return [int(p) for p in parts], pre_release
        
        req = self.version_req
        
        # Handle version ranges (e.g., "1.2.3 - 2.3.4")
        if " - " in req:
            min_ver, max_ver = req.split(" - ")
            min_parts, _ = parse_version(min_ver)
            max_parts, _ = parse_version(max_ver)
            ver_parts, _ = parse_version(version)
            
            return min_parts <= ver_parts <= max_parts
        
        # Handle caret operator (^) - compatible with version
        if req.startswith("^"):
            req_ver = req[1:]
            req_parts, _ = parse_version(req_ver)
            ver_parts, _ = parse_version(version)
            
            # ^1.2.3 means >=1.2.3 <2.0.0
            if len(req_parts) > 0 and req_parts[0] > 0:
                return (req_parts <= ver_parts and 
                        ver_parts[0] == req_parts[0])
            # ^0.2.3 means >=0.2.3 <0.3.0
            elif len(req_parts) > 1 and req_parts[1] > 0:
                return (req_parts <= ver_parts and
                        ver_parts[0] == req_parts[0] and
                        ver_parts[1] == req_parts[1])
            # ^0.0.3 means >=0.0.3 <0.0.4
            else:
                return req_parts == ver_parts
        
        # Handle tilde operator (~) - approximately equivalent to version
        if req.startswith("~"):
            req_ver = req[1:]
            req_parts, _ = parse_version(req_ver)
            ver_parts, _ = parse_version(version)
            
            # ~1.2.3 means >=1.2.3 <1.3.0
            return (req_parts <= ver_parts and
                    ver_parts[0] == req_parts[0] and
                    ver_parts[1] == req_parts[1])
        
        # Handle comparison operators
        if req.startswith(">"):
            if req.startswith(">="):
                req_ver = req[2:]
                req_parts, _ = parse_version(req_ver)
                ver_parts, _ = parse_version(version)
                return ver_parts >= req_parts
            else:
                req_ver = req[1:]
                req_parts, _ = parse_version(req_ver)
                ver_parts, _ = parse_version(version)
                return ver_parts > req_parts
        
        if req.startswith("<"):
            if req.startswith("<="):
                req_ver = req[2:]
                req_parts, _ = parse_version(req_ver)
                ver_parts, _ = parse_version(version)
                return ver_parts <= req_parts
            else:
                req_ver = req[1:]
                req_parts, _ = parse_version(req_ver)
                ver_parts, _ = parse_version(version)
                return ver_parts < req_parts
        
        if req.startswith("="):
            req_ver = req[1:]
            return req_ver == version
        
        # Default to exact match
        return req == version


class NetworkPortConfig(BaseModel):
    """Represents a network port configuration for an application"""
    port: int
    protocol: str = "tcp"  # tcp, udp, icmp
    direction: str = "inbound"  # inbound, outbound
    purpose: str = ""  # Description of what the port is used for
    required: bool = True  # Is this port required for the application to function


class Package(BaseModel):
    """Represents a package in the KOS package system"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[Union[PackageDependency, Dict[str, Any]]] = []
    install_date: Optional[datetime] = None
    size: int = 0
    checksum: str = ""
    homepage: str = ""
    license: str = ""
    tags: List[str] = []
    repository: str = ""
    entry_point: str = ""  # Makes the package executable as an application
    cli_aliases: List[str] = []
    cli_function: str = ""
    installed: bool = False
    
    # Security and permissions attributes
    network_access: bool = False  # Whether the package needs network access
    required_ports: List[Union[NetworkPortConfig, Dict[str, Any]]] = []  # Ports that need to be opened in the firewall
    filesystem_access: List[str] = []  # Directories the package needs access to
    privileged: bool = False  # Whether the package needs elevated privileges
    sandbox_profile: str = ""  # Name of sandbox profile to use
    
    @validator('dependencies', pre=True)
    def parse_dependencies(cls, v):
        """Convert raw dependency data to PackageDependency objects"""
        if not v:
            return []
            
        result = []
        for dep in v:
            if isinstance(dep, dict):
                result.append(PackageDependency(**dep))
            elif isinstance(dep, PackageDependency):
                result.append(dep)
            elif isinstance(dep, str):
                # Simple dependency format: just a name
                result.append(PackageDependency(name=dep))
        return result
    
    @validator('required_ports', pre=True)
    def parse_port_configs(cls, v):
        """Convert raw port configuration data to NetworkPortConfig objects"""
        if not v:
            return []
            
        result = []
        for port_config in v:
            if isinstance(port_config, dict):
                # Validate port number
                if 'port' not in port_config:
                    raise ValueError(f"Port configuration missing 'port' field: {port_config}")
                    
                port = port_config['port']
                if not isinstance(port, int) or port < 1 or port > 65535:
                    raise ValueError(f"Invalid port number: {port}. Must be between 1-65535.")
                    
                # Validate protocol
                protocol = port_config.get('protocol', 'tcp')
                if protocol not in ['tcp', 'udp', 'icmp']:
                    raise ValueError(f"Invalid protocol: {protocol}. Must be 'tcp', 'udp', or 'icmp'.")
                    
                # Validate direction
                direction = port_config.get('direction', 'inbound')
                if direction not in ['inbound', 'outbound']:
                    raise ValueError(f"Invalid direction: {direction}. Must be 'inbound' or 'outbound'.")
                    
                result.append(NetworkPortConfig(**port_config))
            elif isinstance(port_config, NetworkPortConfig):
                result.append(port_config)
            else:
                raise ValueError(f"Invalid port configuration format: {port_config}")
                
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = self.model_dump(exclude_none=True)
        
        # Convert dependencies to dictionaries
        if "dependencies" in data and data["dependencies"]:
            data["dependencies"] = [
                dep.to_dict() if hasattr(dep, 'to_dict') else dep for dep in data["dependencies"]
            ]
            
        # Convert required_ports to dictionaries
        if "required_ports" in data and data["required_ports"]:
            data["required_ports"] = [
                port.model_dump() if isinstance(port, NetworkPortConfig) else port 
                for port in data["required_ports"]
            ]
        # Convert datetime to string if present
        if "install_date" in data and data["install_date"]:
            data["install_date"] = data["install_date"].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Package':
        """Create a Package instance from a dictionary"""
        # Handle install_date parsing
        if "install_date" in data and data["install_date"] and not isinstance(data["install_date"], datetime):
            try:
                data["install_date"] = datetime.fromisoformat(data["install_date"])
            except (ValueError, TypeError):
                data["install_date"] = None
                
        return cls(**data)
    
    @property
    def is_application(self) -> bool:
        """Determine if this package is an application (has an entry point)"""
        return bool(self.entry_point)


class AppIndexEntry(BaseModel):
    """Represents an entry in the application index"""
    name: str
    version: str
    entry_point: str
    app_path: str
    cli_aliases: List[str] = []
    cli_function: str = ""
    description: str = ""
    author: str = ""
    repository: str = ""
    tags: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization"""
        return self.model_dump(exclude_none=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppIndexEntry':
        """Create entry from dictionary"""
        return cls(**data)
    
    def get_full_path(self, base_dir: str) -> str:
        """Get the full path to the application directory"""
        return os.path.join(base_dir, self.app_path)


class RepositoryInfo(BaseModel):
    """Information about a package repository"""
    name: str
    url: str
    enabled: bool = True
    priority: int = 50  # 0-100, higher is higher priority
    last_updated: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = self.model_dump(exclude_none=True)
        if "last_updated" in data and data["last_updated"]:
            data["last_updated"] = data["last_updated"].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RepositoryInfo':
        """Create from dictionary"""
        if "last_updated" in data and data["last_updated"] and not isinstance(data["last_updated"], datetime):
            try:
                data["last_updated"] = datetime.fromisoformat(data["last_updated"])
            except (ValueError, TypeError):
                data["last_updated"] = None
        return cls(**data)


class RepositoryPackage(BaseModel):
    """A package available in a repository"""
    name: str
    version: str
    description: str = ""
    repository: str  # Repository name
    download_url: str
    checksum: str = ""
    size: int = 0
    dependencies: List[Union[PackageDependency, Dict[str, Any]]] = []
    is_application: bool = False
    
    @validator('dependencies', pre=True)
    def parse_dependencies(cls, v):
        """Convert raw dependency data to PackageDependency objects"""
        if not v:
            return []
            
        result = []
        for dep in v:
            if isinstance(dep, dict):
                result.append(PackageDependency(**dep))
            elif isinstance(dep, PackageDependency):
                result.append(dep)
            elif isinstance(dep, str):
                # Simple dependency format: just a name
                result.append(PackageDependency(name=dep))
        return result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = self.model_dump(exclude_none=True)
        if "dependencies" in data and data["dependencies"]:
            data["dependencies"] = [
                dep.model_dump() if isinstance(dep, PackageDependency) else dep 
                for dep in data["dependencies"]
            ]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RepositoryPackage':
        """Create from dictionary"""
        return cls(**data)

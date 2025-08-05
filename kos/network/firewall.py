"""
KOS Firewall System

This module provides a comprehensive firewall implementation for KOS, allowing for packet
filtering, network address translation (NAT), port forwarding, and application-specific
rules. It serves as a security layer for KOS applications and services.

Key features:
- Rule-based packet filtering
- Network address translation (NAT)
- Port forwarding
- Application-specific firewall rules
- Integration with package management system
- IPv4 and IPv6 support
- Stateful inspection
"""

import os
import sys
import time
import logging
import threading
import uuid
import json
import ipaddress
import socket
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Set

# Try to import Pydantic models if available
try:
    from pydantic import BaseModel, Field, validator
    from typing import Literal
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object
    Field = lambda *args, **kwargs: None
    def validator(*args, **kwargs): return lambda func: func
    Literal = Union

# Set up logging
logger = logging.getLogger('KOS.network.firewall')

# Try to use VFS if available, fallback to host filesystem
try:
    from ..vfs.vfs_wrapper import get_vfs, VFS_O_RDONLY, VFS_O_WRONLY, VFS_O_CREAT, VFS_O_APPEND
    USE_VFS = True
    logger.info("Using KOS VFS for firewall management")
except Exception as e:
    USE_VFS = False
    logger.warning(f"VFS not available, using host filesystem: {e}")

# Constants
FIREWALL_CONFIG_PATH = os.path.join(os.path.expanduser('~'), '.kos', 'firewall')
DEFAULT_CONFIG_FILE = os.path.join(FIREWALL_CONFIG_PATH, 'firewall.json')
RULE_BACKUP_DIR = os.path.join(FIREWALL_CONFIG_PATH, 'backups')

# Ensure directories exist
os.makedirs(FIREWALL_CONFIG_PATH, exist_ok=True)
os.makedirs(RULE_BACKUP_DIR, exist_ok=True)

# Firewall rule tables
TABLES = {
    'filter': {
        'chains': {
            'INPUT': [],
            'FORWARD': [],
            'OUTPUT': []
        },
        'default_policy': {
            'INPUT': 'ACCEPT',
            'FORWARD': 'DROP',
            'OUTPUT': 'ACCEPT'
        }
    },
    'nat': {
        'chains': {
            'PREROUTING': [],
            'POSTROUTING': [],
            'OUTPUT': []
        }
    },
    'mangle': {
        'chains': {
            'PREROUTING': [],
            'INPUT': [],
            'FORWARD': [],
            'OUTPUT': [],
            'POSTROUTING': []
        }
    }
}

FIREWALL_LOCK = threading.Lock()
_initialized = False

# Define Pydantic models if available
if PYDANTIC_AVAILABLE:
    class FirewallRuleModel(BaseModel):
        """Pydantic model for firewall rules"""
        id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
        chain: str
        table: str
        protocol: Optional[str] = None
        source: Optional[str] = None
        destination: Optional[str] = None
        source_port: Optional[str] = None
        destination_port: Optional[str] = None
        interface_in: Optional[str] = None
        interface_out: Optional[str] = None
        action: str = "ACCEPT"
        comment: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.now)
        app_id: Optional[str] = None  # Associated application ID
        priority: int = 0  # Rule priority (higher numbers = higher priority)
        enabled: bool = True  # Whether the rule is active
        hits: int = 0  # Number of times the rule has been matched
        last_hit: Optional[datetime] = None  # Last time the rule was matched
        
        @validator('source', 'destination', pre=True)
        def validate_ip_address(cls, v):
            if v is None:
                return v
            try:
                if '/' in v:  # CIDR notation
                    ipaddress.ip_network(v)
                else:
                    ipaddress.ip_address(v)
                return v
            except ValueError:
                # If not IP, check if it's a valid hostname
                try:
                    socket.gethostbyname(v)
                    return v
                except:
                    raise ValueError(f"Invalid IP address or hostname: {v}")
        
        @validator('protocol')
        def validate_protocol(cls, v):
            if v is None:
                return v
            valid_protocols = ["tcp", "udp", "icmp", "all"]
            if v.lower() not in valid_protocols:
                raise ValueError(f"Protocol must be one of {valid_protocols}")
            return v.lower()
        
        @validator('action')
        def validate_action(cls, v):
            valid_actions = ["ACCEPT", "DROP", "REJECT", "LOG"]
            if v not in valid_actions:
                raise ValueError(f"Action must be one of {valid_actions}")
            return v
        
        @validator('source_port', 'destination_port')
        def validate_port(cls, v):
            if v is None:
                return v
            
            # Check if it's a port range (e.g. 80:90)
            if ':' in v:
                start, end = v.split(':')
                try:
                    start_port = int(start)
                    end_port = int(end)
                    if not (0 <= start_port <= 65535 and 0 <= end_port <= 65535):
                        raise ValueError()
                    if start_port > end_port:
                        raise ValueError()
                    return v
                except ValueError:
                    raise ValueError(f"Invalid port range: {v}")
            
            # Check if it's a single port
            try:
                port = int(v)
                if not (0 <= port <= 65535):
                    raise ValueError()
                return v
            except ValueError:
                raise ValueError(f"Invalid port: {v}")


class FirewallRule:
    """Firewall rule class representing a single firewall rule
    
    This class is designed to work with or without Pydantic, providing
    basic validation in either case. When Pydantic is available, it uses
    the FirewallRuleModel for enhanced validation.
    """
    def __init__(self, chain: str, table: str, protocol: str = None, 
                source: str = None, destination: str = None, 
                source_port: str = None, destination_port: str = None, 
                interface_in: str = None, interface_out: str = None,
                action: str = "ACCEPT", comment: str = None,
                app_id: str = None, priority: int = 0, enabled: bool = True):
        """Initialize a new firewall rule"""
        
        if PYDANTIC_AVAILABLE:
            # Use Pydantic model for validation
            model = FirewallRuleModel(
                chain=chain,
                table=table,
                protocol=protocol,
                source=source,
                destination=destination,
                source_port=source_port,
                destination_port=destination_port,
                interface_in=interface_in,
                interface_out=interface_out,
                action=action,
                comment=comment,
                app_id=app_id,
                priority=priority,
                enabled=enabled
            )
            
            # Copy validated values to self
            for key, value in model.dict().items():
                setattr(self, key, value)
        else:
            # Basic initialization without Pydantic validation
            self.id = str(uuid.uuid4())[:8]
            self.chain = chain
            self.table = table
            self.protocol = protocol.lower() if protocol else None
            self.source = source
            self.destination = destination
            self.source_port = source_port
            self.destination_port = destination_port
            self.interface_in = interface_in
            self.interface_out = interface_out
            self.action = action
            self.comment = comment
            self.created_at = datetime.now()
            self.app_id = app_id
            self.priority = priority
            self.enabled = enabled
            self.hits = 0
            self.last_hit = None
    
    def to_dict(self):
        """Convert rule to dictionary representation"""
        result = {
            "id": self.id,
            "chain": self.chain,
            "table": self.table,
            "protocol": self.protocol,
            "source": self.source,
            "destination": self.destination,
            "source_port": self.source_port,
            "destination_port": self.destination_port,
            "interface_in": self.interface_in,
            "interface_out": self.interface_out,
            "action": self.action,
            "comment": self.comment,
            "created_at": self.created_at,
            "enabled": self.enabled,
            "priority": self.priority,
            "hits": getattr(self, 'hits', 0)
        }
        
        # Add app_id if it exists
        if hasattr(self, 'app_id') and self.app_id:
            result["app_id"] = self.app_id
            
        # Add last_hit if it exists
        if hasattr(self, 'last_hit') and self.last_hit:
            result["last_hit"] = self.last_hit
            
        return result
    
    @classmethod
    def from_dict(cls, data):
        """Create rule from dictionary"""
        # Extract base parameters
        base_params = {
            "chain": data["chain"],
            "table": data["table"],
            "protocol": data.get("protocol"),
            "source": data.get("source"),
            "destination": data.get("destination"),
            "source_port": data.get("source_port"),
            "destination_port": data.get("destination_port"),
            "interface_in": data.get("interface_in"),
            "interface_out": data.get("interface_out"),
            "action": data.get("action", "ACCEPT"),
            "comment": data.get("comment"),
            "app_id": data.get("app_id"),
            "priority": data.get("priority", 0),
            "enabled": data.get("enabled", True)
        }
        
        # Create rule
        rule = cls(**base_params)
        
        # Set additional attributes
        if "id" in data:
            rule.id = data["id"]
        if "created_at" in data:
            if isinstance(data["created_at"], (int, float)):
                # Convert from timestamp to datetime if needed
                rule.created_at = datetime.fromtimestamp(data["created_at"])
            elif isinstance(data["created_at"], str):
                # Parse ISO format datetime string
                try:
                    rule.created_at = datetime.fromisoformat(data["created_at"])
                except ValueError:
                    rule.created_at = datetime.now()
            else:
                rule.created_at = data["created_at"]
        if "hits" in data:
            rule.hits = data["hits"]
        if "last_hit" in data:
            if isinstance(data["last_hit"], (int, float)):
                rule.last_hit = datetime.fromtimestamp(data["last_hit"])
            elif isinstance(data["last_hit"], str):
                try:
                    rule.last_hit = datetime.fromisoformat(data["last_hit"])
                except ValueError:
                    rule.last_hit = None
            else:
                rule.last_hit = data["last_hit"]
        
        return rule
    
    def __str__(self):
        """String representation of the rule"""
        parts = [f"-A {self.chain}"]
        
        if self.protocol:
            parts.append(f"-p {self.protocol}")
        
        if self.source:
            parts.append(f"-s {self.source}")
        
        if self.destination:
            parts.append(f"-d {self.destination}")
        
        if self.source_port:
            parts.append(f"--sport {self.source_port}")
        
        if self.destination_port:
            parts.append(f"--dport {self.destination_port}")
        
        if self.interface_in:
            parts.append(f"-i {self.interface_in}")
        
        if self.interface_out:
            parts.append(f"-o {self.interface_out}")
        
        if self.action:
            parts.append(f"-j {self.action}")
        
        if self.comment:
            parts.append(f"-m comment --comment \"{self.comment}\"")
        
        return " ".join(parts)

class FirewallManager:
    """Manager for firewall operations"""
    
    @staticmethod
    def add_rule(chain: str, table: str = "filter", protocol: str = None, 
                source: str = None, destination: str = None, 
                source_port: str = None, destination_port: str = None, 
                interface_in: str = None, interface_out: str = None,
                action: str = "ACCEPT", comment: str = None) -> Tuple[bool, str, Optional[FirewallRule]]:
        """Add a new firewall rule"""
        ensure_initialized()
        # Validate table
        if table not in TABLES:
            return False, f"Invalid table: {table}", None
        
        # Validate chain
        if chain not in TABLES[table]['chains']:
            return False, f"Invalid chain {chain} for table {table}", None
        
        # Validate action
        valid_actions = ["ACCEPT", "DROP", "REJECT", "LOG", "DNAT", "SNAT", "MASQUERADE", "REDIRECT"]
        if action not in valid_actions:
            return False, f"Invalid action: {action}", None
        
        # Create rule
        rule = FirewallRule(
            chain=chain,
            table=table,
            protocol=protocol,
            source=source,
            destination=destination,
            source_port=source_port,
            destination_port=destination_port,
            interface_in=interface_in,
            interface_out=interface_out,
            action=action,
            comment=comment
        )
        
        # Add to registry
        with FIREWALL_LOCK:
            TABLES[table]['chains'][chain].append(rule)
        
        return True, f"Rule added to {table}/{chain}", rule
    
    @staticmethod
    def delete_rule(rule_id: str, table: str = None, chain: str = None) -> Tuple[bool, str]:
        """Delete a firewall rule"""
        with FIREWALL_LOCK:
            # If table and chain are specified, search only there
            if table and chain:
                if table not in TABLES:
                    return False, f"Invalid table: {table}"
                
                if chain not in TABLES[table]['chains']:
                    return False, f"Invalid chain {chain} for table {table}"
                
                rules = TABLES[table]['chains'][chain]
                for i, rule in enumerate(rules):
                    if rule.id == rule_id:
                        del rules[i]
                        return True, f"Rule {rule_id} deleted from {table}/{chain}"
                
                return False, f"Rule {rule_id} not found in {table}/{chain}"
            
            # Otherwise search all tables and chains
            for table_name, table_data in TABLES.items():
                for chain_name, chain_rules in table_data['chains'].items():
                    for i, rule in enumerate(chain_rules):
                        if rule.id == rule_id:
                            del chain_rules[i]
                            return True, f"Rule {rule_id} deleted from {table_name}/{chain_name}"
            
            return False, f"Rule {rule_id} not found"
    
    @staticmethod
    def list_rules(table: str = None, chain: str = None) -> List[FirewallRule]:
        """List firewall rules"""
        with FIREWALL_LOCK:
            # If table and chain are specified, return only those rules
            if table and chain:
                if table not in TABLES:
                    return []
                
                if chain not in TABLES[table]['chains']:
                    return []
                
                return TABLES[table]['chains'][chain]
            
            # If only table is specified, return all rules for that table
            if table:
                if table not in TABLES:
                    return []
                
                rules = []
                for chain_name, chain_rules in TABLES[table]['chains'].items():
                    rules.extend(chain_rules)
                
                return rules
            
            # Otherwise return all rules
            rules = []
            for table_name, table_data in TABLES.items():
                for chain_name, chain_rules in table_data['chains'].items():
                    rules.extend(chain_rules)
            
            return rules
    
    @staticmethod
    def get_rule(rule_id: str) -> Optional[FirewallRule]:
        """Get a firewall rule by ID"""
        with FIREWALL_LOCK:
            for table_name, table_data in TABLES.items():
                for chain_name, chain_rules in table_data['chains'].items():
                    for rule in chain_rules:
                        if rule.id == rule_id:
                            return rule
            
            return None
    
    @staticmethod
    def clear_chain(table: str, chain: str) -> Tuple[bool, str]:
        """Clear all rules from a chain"""
        with FIREWALL_LOCK:
            if table not in TABLES:
                return False, f"Invalid table: {table}"
            
            if chain not in TABLES[table]['chains']:
                return False, f"Invalid chain {chain} for table {table}"
            
            TABLES[table]['chains'][chain] = []
            
            return True, f"Chain {table}/{chain} cleared"
    
    @staticmethod
    def save_rules(filepath: str) -> Tuple[bool, str]:
        """Save firewall rules to file"""
        try:
            with FIREWALL_LOCK:
                data = {}
                for table_name, table_data in TABLES.items():
                    data[table_name] = {'chains': {}}
                    for chain_name, chain_rules in table_data['chains'].items():
                        data[table_name]['chains'][chain_name] = [rule.to_dict() for rule in chain_rules]
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Firewall rules saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save firewall rules: {str(e)}"
    
    @staticmethod
    def load_rules(filepath: str) -> Tuple[bool, str]:
        """Load firewall rules from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with FIREWALL_LOCK:
                for table_name, table_data in data.items():
                    if table_name not in TABLES:
                        continue
                    
                    for chain_name, chain_rules in table_data['chains'].items():
                        if chain_name not in TABLES[table_name]['chains']:
                            continue
                        
                        TABLES[table_name]['chains'][chain_name] = [
                            FirewallRule.from_dict(rule_data) for rule_data in chain_rules
                        ]
            
            return True, f"Firewall rules loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load firewall rules: {str(e)}"

# NAT (Network Address Translation) helper class
class NAT:
    """NAT operations for the firewall"""
    
    @staticmethod
    def add_port_forward(protocol: str, external_port: int, destination: str, 
                         destination_port: int = None, interface: str = None, 
                         comment: str = None) -> Tuple[bool, str, Optional[FirewallRule]]:
        """Add a port forwarding rule (DNAT)"""
        if not destination_port:
            destination_port = external_port
        
        # Create DNAT rule for PREROUTING
        return FirewallManager.add_rule(
            chain="PREROUTING",
            table="nat",
            protocol=protocol,
            destination_port=str(external_port),
            interface_in=interface,
            action="DNAT",
            comment=comment or f"Port forward: {protocol}/{external_port} -> {destination}:{destination_port}"
        )
    
    @staticmethod
    def add_masquerade(source_network: str = None, interface_out: str = None,
                      comment: str = None) -> Tuple[bool, str, Optional[FirewallRule]]:
        """Add a masquerade rule (source NAT for outgoing traffic)"""
        # Create MASQUERADE rule for POSTROUTING
        return FirewallManager.add_rule(
            chain="POSTROUTING",
            table="nat",
            source=source_network,
            interface_out=interface_out,
            action="MASQUERADE",
            comment=comment or "Masquerade outgoing traffic"
        )

# Initialize firewall system
def initialize():
    """Initialize the firewall system"""
    global _initialized
    if _initialized:
        return
    
    logger.info("Initializing KOS firewall system")
    _initialized = True
    
    # Create firewall directory
    firewall_dir = os.path.join(os.path.expanduser('~'), '.kos', 'firewall')
    os.makedirs(firewall_dir, exist_ok=True)
    
    # Add default rules
    with FIREWALL_LOCK:
        # Default filter table rules
        if not TABLES['filter']['chains']['INPUT']:
            # Allow established connections
            FirewallManager.add_rule(
                chain="INPUT",
                table="filter",
                protocol="all",
                comment="Allow established connections",
                action="ACCEPT"
            )
            
            # Allow loopback
            FirewallManager.add_rule(
                chain="INPUT",
                table="filter",
                interface_in="lo",
                comment="Allow loopback interface",
                action="ACCEPT"
            )
    
    # Load rules if they exist
    rules_db = os.path.join(firewall_dir, 'rules.json')
    if os.path.exists(rules_db):
        FirewallManager.load_rules(rules_db)
    else:
        # Save default rules
        FirewallManager.save_rules(rules_db)
    
    logger.info("KOS firewall system initialized")

# Helper function for lazy initialization
def ensure_initialized():
    """Ensure firewall system is initialized"""
    if not _initialized:
        initialize()

# Initialize lazily when needed (removed automatic initialization to prevent blocking)
# Call initialize() manually when firewall functionality is first used

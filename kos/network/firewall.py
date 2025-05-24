"""
KOS Firewall System

This module provides a firewall implementation for KOS, allowing for packet
filtering, network address translation (NAT), and port forwarding - similar
to iptables in Linux.
"""

import os
import sys
import time
import logging
import threading
import uuid
import json
from typing import Dict, List, Any, Optional, Union, Tuple

# Set up logging
logger = logging.getLogger('KOS.network.firewall')

# Firewall rule tables
TABLES = {
    'filter': {
        'chains': {
            'INPUT': [],
            'FORWARD': [],
            'OUTPUT': []
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

class FirewallRule:
    """Firewall rule class representing a single firewall rule"""
    
    def __init__(self, chain: str, table: str, protocol: str = None, 
                source: str = None, destination: str = None, 
                source_port: str = None, destination_port: str = None, 
                interface_in: str = None, interface_out: str = None,
                action: str = "ACCEPT", comment: str = None):
        """Initialize a new firewall rule"""
        self.id = str(uuid.uuid4())[:8]
        self.chain = chain
        self.table = table
        self.protocol = protocol
        self.source = source
        self.destination = destination
        self.source_port = source_port
        self.destination_port = destination_port
        self.interface_in = interface_in
        self.interface_out = interface_out
        self.action = action
        self.comment = comment
        self.created_at = time.time()
    
    def to_dict(self):
        """Convert rule to dictionary representation"""
        return {
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
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create rule from dictionary"""
        rule = cls(
            chain=data["chain"],
            table=data["table"],
            protocol=data["protocol"],
            source=data["source"],
            destination=data["destination"],
            source_port=data["source_port"],
            destination_port=data["destination_port"],
            interface_in=data["interface_in"],
            interface_out=data["interface_out"],
            action=data["action"],
            comment=data["comment"]
        )
        rule.id = data["id"]
        rule.created_at = data["created_at"]
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
    logger.info("Initializing KOS firewall system")
    
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

# Initialize on import
initialize()

"""
Firewall and network security for KOS
"""

import time
import ipaddress
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class RuleAction(Enum):
    """Firewall rule actions"""
    ACCEPT = "accept"
    DROP = "drop"
    REJECT = "reject"
    LOG = "log"

class Protocol(Enum):
    """Network protocols"""
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    ALL = "all"

class Chain(Enum):
    """Firewall chains"""
    INPUT = "input"
    OUTPUT = "output"
    FORWARD = "forward"

@dataclass
class FirewallRule:
    """Firewall rule definition"""
    chain: Chain
    action: RuleAction
    protocol: Protocol = Protocol.ALL
    source: Optional[str] = None  # IP or network
    destination: Optional[str] = None
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    interface: Optional[str] = None
    state: Optional[str] = None  # NEW, ESTABLISHED, RELATED
    enabled: bool = True
    comment: str = ""
    
    def matches(self, packet: 'Packet') -> bool:
        """Check if packet matches rule"""
        if not self.enabled:
            return False
        
        # Check protocol
        if self.protocol != Protocol.ALL and self.protocol.value != packet.protocol:
            return False
        
        # Check source
        if self.source and not self._ip_matches(packet.source_ip, self.source):
            return False
        
        # Check destination
        if self.destination and not self._ip_matches(packet.dest_ip, self.destination):
            return False
        
        # Check ports
        if self.source_port and packet.source_port != self.source_port:
            return False
        if self.dest_port and packet.dest_port != self.dest_port:
            return False
        
        # Check interface
        if self.interface and packet.interface != self.interface:
            return False
        
        # Check state
        if self.state and packet.state != self.state:
            return False
        
        return True
    
    def _ip_matches(self, ip: str, pattern: str) -> bool:
        """Check if IP matches pattern"""
        try:
            # Check if pattern is a network
            if '/' in pattern:
                network = ipaddress.ip_network(pattern)
                return ipaddress.ip_address(ip) in network
            else:
                return ip == pattern
        except:
            return False

@dataclass
class Packet:
    """Network packet representation"""
    protocol: str
    source_ip: str
    dest_ip: str
    source_port: Optional[int] = None
    dest_port: Optional[int] = None
    interface: Optional[str] = None
    state: Optional[str] = None
    data: bytes = b''

class Firewall:
    """KOS firewall implementation"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.enabled = False
        self.rules: Dict[Chain, List[FirewallRule]] = {
            Chain.INPUT: [],
            Chain.OUTPUT: [],
            Chain.FORWARD: []
        }
        self.default_policy: Dict[Chain, RuleAction] = {
            Chain.INPUT: RuleAction.ACCEPT,
            Chain.OUTPUT: RuleAction.ACCEPT,
            Chain.FORWARD: RuleAction.DROP
        }
        
        # Connection tracking
        self.connections: Dict[str, dict] = {}
        
        # Packet counters
        self.counters = {
            'packets_accepted': 0,
            'packets_dropped': 0,
            'packets_rejected': 0
        }
        
        self._load_rules()
    
    def _load_rules(self):
        """Load firewall rules from configuration"""
        if not self.vfs:
            return
        
        config_file = "/etc/firewall/rules.conf"
        if self.vfs.exists(config_file):
            try:
                with self.vfs.open(config_file, 'r') as f:
                    self._parse_rules(f.read().decode())
            except:
                pass
        else:
            self._create_default_rules()
    
    def _create_default_rules(self):
        """Create default firewall rules"""
        # Allow loopback
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            interface="lo",
            comment="Allow loopback"
        ))
        
        # Allow established connections
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            state="ESTABLISHED",
            comment="Allow established connections"
        ))
        
        # Allow SSH
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            protocol=Protocol.TCP,
            dest_port=22,
            comment="Allow SSH"
        ))
        
        # Allow HTTP/HTTPS
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            protocol=Protocol.TCP,
            dest_port=80,
            comment="Allow HTTP"
        ))
        
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            protocol=Protocol.TCP,
            dest_port=443,
            comment="Allow HTTPS"
        ))
        
        # Allow ping
        self.add_rule(FirewallRule(
            chain=Chain.INPUT,
            action=RuleAction.ACCEPT,
            protocol=Protocol.ICMP,
            comment="Allow ping"
        ))
    
    def enable(self):
        """Enable firewall"""
        self.enabled = True
        self._save_rules()
    
    def disable(self):
        """Disable firewall"""
        self.enabled = False
        self._save_rules()
    
    def add_rule(self, rule: FirewallRule) -> bool:
        """Add firewall rule"""
        if rule.chain in self.rules:
            self.rules[rule.chain].append(rule)
            self._save_rules()
            return True
        return False
    
    def remove_rule(self, chain: Chain, index: int) -> bool:
        """Remove firewall rule by index"""
        if chain in self.rules and 0 <= index < len(self.rules[chain]):
            del self.rules[chain][index]
            self._save_rules()
            return True
        return False
    
    def set_default_policy(self, chain: Chain, action: RuleAction):
        """Set default policy for chain"""
        self.default_policy[chain] = action
        self._save_rules()
    
    def filter_packet(self, packet: Packet, chain: Chain) -> RuleAction:
        """Filter packet through firewall"""
        if not self.enabled:
            return RuleAction.ACCEPT
        
        # Track connection state
        self._track_connection(packet)
        
        # Check rules
        for rule in self.rules.get(chain, []):
            if rule.matches(packet):
                # Log if needed
                if rule.action == RuleAction.LOG:
                    self._log_packet(packet, rule)
                    continue  # Continue to next rule
                
                # Apply action
                self._update_counters(rule.action)
                return rule.action
        
        # Apply default policy
        action = self.default_policy.get(chain, RuleAction.ACCEPT)
        self._update_counters(action)
        return action
    
    def _track_connection(self, packet: Packet):
        """Track connection state"""
        if packet.protocol == "tcp":
            conn_key = f"{packet.source_ip}:{packet.source_port}-{packet.dest_ip}:{packet.dest_port}"
            
            if conn_key not in self.connections:
                self.connections[conn_key] = {
                    'state': 'NEW',
                    'established': False,
                    'last_seen': time.time()
                }
                packet.state = 'NEW'
            else:
                conn = self.connections[conn_key]
                if conn['established']:
                    packet.state = 'ESTABLISHED'
                else:
                    packet.state = 'RELATED'
                conn['last_seen'] = time.time()
    
    def _update_counters(self, action: RuleAction):
        """Update packet counters"""
        if action == RuleAction.ACCEPT:
            self.counters['packets_accepted'] += 1
        elif action == RuleAction.DROP:
            self.counters['packets_dropped'] += 1
        elif action == RuleAction.REJECT:
            self.counters['packets_rejected'] += 1
    
    def _log_packet(self, packet: Packet, rule: FirewallRule):
        """Log packet information"""
        log_msg = f"[FIREWALL] {rule.chain.value}: {packet.protocol} "
        log_msg += f"{packet.source_ip}:{packet.source_port} -> "
        log_msg += f"{packet.dest_ip}:{packet.dest_port}"
        if rule.comment:
            log_msg += f" ({rule.comment})"
        
        # Would integrate with logging service
        print(log_msg)
    
    def list_rules(self, chain: Optional[Chain] = None) -> List[FirewallRule]:
        """List firewall rules"""
        if chain:
            return self.rules.get(chain, [])
        
        all_rules = []
        for chain in Chain:
            all_rules.extend(self.rules.get(chain, []))
        return all_rules
    
    def _save_rules(self):
        """Save firewall rules to file"""
        if not self.vfs:
            return
        
        # Create directory if needed
        if not self.vfs.exists("/etc/firewall"):
            try:
                self.vfs.mkdir("/etc/firewall")
            except:
                pass
        
        # Generate rules content
        content = f"# KOS Firewall Rules\n"
        content += f"# Enabled: {self.enabled}\n\n"
        
        # Default policies
        for chain, action in self.default_policy.items():
            content += f"POLICY {chain.value} {action.value}\n"
        content += "\n"
        
        # Rules
        for chain, rules in self.rules.items():
            for rule in rules:
                content += self._format_rule(chain, rule) + "\n"
        
        # Save to file
        try:
            with self.vfs.open("/etc/firewall/rules.conf", 'w') as f:
                f.write(content.encode())
        except:
            pass
    
    def _format_rule(self, chain: Chain, rule: FirewallRule) -> str:
        """Format rule as string"""
        parts = [chain.value.upper(), rule.action.value.upper()]
        
        if rule.protocol != Protocol.ALL:
            parts.append(f"-p {rule.protocol.value}")
        if rule.source:
            parts.append(f"-s {rule.source}")
        if rule.destination:
            parts.append(f"-d {rule.destination}")
        if rule.source_port:
            parts.append(f"--sport {rule.source_port}")
        if rule.dest_port:
            parts.append(f"--dport {rule.dest_port}")
        if rule.interface:
            parts.append(f"-i {rule.interface}")
        if rule.state:
            parts.append(f"--state {rule.state}")
        if rule.comment:
            parts.append(f'# {rule.comment}')
        
        return " ".join(parts)
    
    def _parse_rules(self, content: str):
        """Parse firewall rules from content"""
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Parse policy
            if line.startswith('POLICY'):
                parts = line.split()
                if len(parts) == 3:
                    try:
                        chain = Chain(parts[1].lower())
                        action = RuleAction(parts[2].lower())
                        self.default_policy[chain] = action
                    except:
                        pass
                continue
            
            # Parse rule (simplified parsing)
            parts = line.split()
            if len(parts) >= 2:
                try:
                    chain = Chain(parts[0].lower())
                    action = RuleAction(parts[1].lower())
                    
                    rule = FirewallRule(chain=chain, action=action)
                    
                    # Parse additional options
                    i = 2
                    while i < len(parts):
                        if parts[i] == '-p' and i + 1 < len(parts):
                            rule.protocol = Protocol(parts[i + 1])
                            i += 2
                        elif parts[i] == '-s' and i + 1 < len(parts):
                            rule.source = parts[i + 1]
                            i += 2
                        elif parts[i] == '-d' and i + 1 < len(parts):
                            rule.destination = parts[i + 1]
                            i += 2
                        elif parts[i] == '--sport' and i + 1 < len(parts):
                            rule.source_port = int(parts[i + 1])
                            i += 2
                        elif parts[i] == '--dport' and i + 1 < len(parts):
                            rule.dest_port = int(parts[i + 1])
                            i += 2
                        elif parts[i] == '-i' and i + 1 < len(parts):
                            rule.interface = parts[i + 1]
                            i += 2
                        elif parts[i] == '--state' and i + 1 < len(parts):
                            rule.state = parts[i + 1]
                            i += 2
                        elif parts[i] == '#':
                            rule.comment = ' '.join(parts[i + 1:])
                            break
                        else:
                            i += 1
                    
                    self.rules[chain].append(rule)
                except:
                    pass
    
    def get_statistics(self) -> Dict:
        """Get firewall statistics"""
        return {
            'enabled': self.enabled,
            'total_rules': sum(len(rules) for rules in self.rules.values()),
            'connections_tracked': len(self.connections),
            **self.counters
        }

class PortScanner:
    """Port scanning detection"""
    
    def __init__(self, firewall: Firewall):
        self.firewall = firewall
        self.scan_attempts: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
        self.threshold = 10  # Ports per second
        self.block_duration = 3600  # 1 hour
    
    def check_scan(self, source_ip: str, dest_port: int) -> bool:
        """Check for port scanning behavior"""
        now = time.time()
        
        # Check if IP is blocked
        if source_ip in self.blocked_ips:
            if now - self.blocked_ips[source_ip] < self.block_duration:
                return True  # Still blocked
            else:
                del self.blocked_ips[source_ip]
        
        # Track port access
        if source_ip not in self.scan_attempts:
            self.scan_attempts[source_ip] = []
        
        # Clean old attempts
        self.scan_attempts[source_ip] = [
            t for t in self.scan_attempts[source_ip]
            if now - t < 1.0
        ]
        
        # Add new attempt
        self.scan_attempts[source_ip].append(now)
        
        # Check threshold
        if len(self.scan_attempts[source_ip]) > self.threshold:
            # Block IP
            self.blocked_ips[source_ip] = now
            
            # Add firewall rule
            self.firewall.add_rule(FirewallRule(
                chain=Chain.INPUT,
                action=RuleAction.DROP,
                source=source_ip,
                comment=f"Port scan block (auto)"
            ))
            
            return True
        
        return False

class IntrusionDetection:
    """Simple intrusion detection system"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.patterns: List[Dict] = []
        self.alerts: List[Dict] = []
        self.enabled = True
        
        self._load_patterns()
    
    def _load_patterns(self):
        """Load attack patterns"""
        # Common attack patterns
        self.patterns = [
            {
                'name': 'SQL Injection',
                'pattern': r'(union|select|insert|update|delete|drop)\s+.*\s+(from|into|table)',
                'severity': 'high'
            },
            {
                'name': 'XSS Attack',
                'pattern': r'<script[^>]*>.*</script>',
                'severity': 'high'
            },
            {
                'name': 'Directory Traversal',
                'pattern': r'\.\./|\.\.\\',
                'severity': 'medium'
            },
            {
                'name': 'Command Injection',
                'pattern': r';|\||&&|`|\$\(.*\)',
                'severity': 'high'
            }
        ]
    
    def analyze_packet(self, packet: Packet) -> Optional[Dict]:
        """Analyze packet for intrusions"""
        if not self.enabled:
            return None
        
        import re
        
        # Check packet data against patterns
        data_str = packet.data.decode('utf-8', errors='ignore')
        
        for pattern_def in self.patterns:
            pattern = pattern_def['pattern']
            if re.search(pattern, data_str, re.IGNORECASE):
                alert = {
                    'timestamp': time.time(),
                    'type': pattern_def['name'],
                    'severity': pattern_def['severity'],
                    'source_ip': packet.source_ip,
                    'dest_ip': packet.dest_ip,
                    'protocol': packet.protocol,
                    'data_sample': data_str[:100]
                }
                
                self.alerts.append(alert)
                return alert
        
        return None
    
    def get_alerts(self, limit: int = 100) -> List[Dict]:
        """Get recent alerts"""
        return self.alerts[-limit:]
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts = []
"""
DNS resolver for KOS
"""

import time
import random
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

@dataclass
class DNSRecord:
    """DNS record"""
    hostname: str
    ip_address: str
    record_type: str = "A"
    ttl: int = 300
    timestamp: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """Check if record is expired"""
        return time.time() - self.timestamp > self.ttl

class DNSResolver:
    """DNS resolution service"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.cache: Dict[str, DNSRecord] = {}
        self.nameservers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
        self.hosts_file = "/etc/hosts"
        self.resolv_conf = "/etc/resolv.conf"
        
        # Static entries
        self.static_entries = {
            "localhost": "127.0.0.1",
            "localhost.localdomain": "127.0.0.1",
        }
        
        self._load_hosts()
        self._load_resolv_conf()
    
    def _load_hosts(self):
        """Load /etc/hosts file"""
        if not self.vfs or not self.vfs.exists(self.hosts_file):
            # Create default hosts file
            if self.vfs:
                try:
                    content = """# /etc/hosts
127.0.0.1       localhost localhost.localdomain
127.0.1.1       kos.local kos

# The following lines are desirable for IPv6 capable hosts
::1             localhost ip6-localhost ip6-loopback
fe00::0         ip6-localnet
ff00::0         ip6-mcastprefix
ff02::1         ip6-allnodes
ff02::2         ip6-allrouters
"""
                    with self.vfs.open(self.hosts_file, 'w') as f:
                        f.write(content.encode())
                except:
                    pass
            return
        
        try:
            with self.vfs.open(self.hosts_file, 'r') as f:
                lines = f.read().decode().split('\n')
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        for hostname in parts[1:]:
                            self.static_entries[hostname] = ip
        except:
            pass
    
    def _load_resolv_conf(self):
        """Load /etc/resolv.conf"""
        if not self.vfs or not self.vfs.exists(self.resolv_conf):
            # Create default resolv.conf
            if self.vfs:
                try:
                    content = """# /etc/resolv.conf
nameserver 8.8.8.8
nameserver 8.8.4.4
nameserver 1.1.1.1
search local
"""
                    with self.vfs.open(self.resolv_conf, 'w') as f:
                        f.write(content.encode())
                except:
                    pass
            return
        
        try:
            with self.vfs.open(self.resolv_conf, 'r') as f:
                lines = f.read().decode().split('\n')
            
            nameservers = []
            for line in lines:
                line = line.strip()
                if line.startswith('nameserver '):
                    ns = line[11:].strip()
                    nameservers.append(ns)
            
            if nameservers:
                self.nameservers = nameservers
        except:
            pass
    
    def resolve(self, hostname: str, record_type: str = "A") -> Optional[str]:
        """Resolve hostname to IP address"""
        # Check static entries first
        if hostname in self.static_entries:
            return self.static_entries[hostname]
        
        # Check cache
        if hostname in self.cache:
            record = self.cache[hostname]
            if not record.is_expired():
                return record.ip_address
            else:
                del self.cache[hostname]
        
        # Simulate DNS resolution
        ip = self._simulate_dns_query(hostname, record_type)
        
        if ip:
            # Cache the result
            self.cache[hostname] = DNSRecord(
                hostname=hostname,
                ip_address=ip,
                record_type=record_type,
                ttl=300
            )
        
        return ip
    
    def _simulate_dns_query(self, hostname: str, record_type: str) -> Optional[str]:
        """Simulate DNS query (would use real DNS in production)"""
        # Simulate some known domains
        known_domains = {
            "google.com": "142.250.185.46",
            "github.com": "140.82.112.3",
            "cloudflare.com": "104.16.132.229",
            "example.com": "93.184.216.34",
            "facebook.com": "157.240.241.35",
            "twitter.com": "104.244.42.1",
            "amazon.com": "52.94.236.248",
            "microsoft.com": "20.70.246.20",
            "apple.com": "17.253.144.10",
            "netflix.com": "54.74.73.31"
        }
        
        # Simulate query delay
        time.sleep(random.uniform(0.01, 0.05))
        
        return known_domains.get(hostname)
    
    def reverse_lookup(self, ip_address: str) -> Optional[str]:
        """Reverse DNS lookup"""
        # Check static entries
        for hostname, ip in self.static_entries.items():
            if ip == ip_address:
                return hostname
        
        # Check cache
        for hostname, record in self.cache.items():
            if record.ip_address == ip_address:
                return hostname
        
        # Simulate reverse lookup
        known_ips = {
            "127.0.0.1": "localhost",
            "8.8.8.8": "dns.google",
            "1.1.1.1": "one.one.one.one",
            "142.250.185.46": "google.com",
            "140.82.112.3": "github.com"
        }
        
        return known_ips.get(ip_address)
    
    def add_host_entry(self, hostname: str, ip_address: str) -> bool:
        """Add entry to hosts file"""
        self.static_entries[hostname] = ip_address
        
        # Update hosts file
        if self.vfs:
            try:
                # Read existing content
                content = ""
                if self.vfs.exists(self.hosts_file):
                    with self.vfs.open(self.hosts_file, 'r') as f:
                        content = f.read().decode()
                
                # Add new entry
                if not content.endswith('\n'):
                    content += '\n'
                content += f"{ip_address}\t{hostname}\n"
                
                # Write back
                with self.vfs.open(self.hosts_file, 'w') as f:
                    f.write(content.encode())
                
                return True
            except:
                pass
        
        return False
    
    def flush_cache(self):
        """Flush DNS cache"""
        self.cache.clear()
    
    def get_nameservers(self) -> List[str]:
        """Get configured nameservers"""
        return self.nameservers
    
    def set_nameservers(self, nameservers: List[str]) -> bool:
        """Set nameservers"""
        self.nameservers = nameservers
        
        # Update resolv.conf
        if self.vfs:
            try:
                content = "# /etc/resolv.conf\n"
                for ns in nameservers:
                    content += f"nameserver {ns}\n"
                content += "search local\n"
                
                with self.vfs.open(self.resolv_conf, 'w') as f:
                    f.write(content.encode())
                
                return True
            except:
                pass
        
        return False
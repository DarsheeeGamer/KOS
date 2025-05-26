"""
Service Discovery for KOS Orchestration System

This module implements DNS-based service discovery for the KOS orchestration system,
allowing pods to discover and communicate with each other using stable network endpoints.
"""

import os
import json
import time
import logging
import threading
import socket
import struct
import ipaddress
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from kos.core.orchestration.pod import Pod
from kos.core.orchestration.service import Service, ServicePort, ServiceSpec

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
DNS_CACHE_PATH = os.path.join(ORCHESTRATION_ROOT, 'dns_cache')
DNS_CONFIG_PATH = os.path.join(ORCHESTRATION_ROOT, 'dns_config.json')

# Ensure directories exist
os.makedirs(DNS_CACHE_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)

# DNS Record Types
A_RECORD = 1      # IPv4 address
AAAA_RECORD = 28  # IPv6 address
SRV_RECORD = 33   # Service record
TXT_RECORD = 16   # Text record
NS_RECORD = 2     # Name server
SOA_RECORD = 6    # Start of authority
PTR_RECORD = 12   # Pointer record

# DNS Record Classes
IN_CLASS = 1      # Internet


class DNSConfig:
    """Configuration for DNS service."""
    
    def __init__(self, domain: str = "kos.local", ttl: int = 60,
                 nameserver: str = "127.0.0.1", port: int = 53,
                 use_host_nameservers: bool = True):
        """
        Initialize DNS configuration.
        
        Args:
            domain: DNS domain for services
            ttl: Time to live for DNS records (in seconds)
            nameserver: IP address of the nameserver
            port: DNS port
            use_host_nameservers: Whether to use host nameservers for external resolution
        """
        self.domain = domain
        self.ttl = ttl
        self.nameserver = nameserver
        self.port = port
        self.use_host_nameservers = use_host_nameservers
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the DNS configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "domain": self.domain,
            "ttl": self.ttl,
            "nameserver": self.nameserver,
            "port": self.port,
            "use_host_nameservers": self.use_host_nameservers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DNSConfig':
        """
        Create a DNS configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DNSConfig object
        """
        return cls(
            domain=data.get("domain", "kos.local"),
            ttl=data.get("ttl", 60),
            nameserver=data.get("nameserver", "127.0.0.1"),
            port=data.get("port", 53),
            use_host_nameservers=data.get("use_host_nameservers", True)
        )
    
    @classmethod
    def load(cls) -> 'DNSConfig':
        """
        Load DNS configuration from disk.
        
        Returns:
            DNSConfig object
        """
        if os.path.exists(DNS_CONFIG_PATH):
            try:
                with open(DNS_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                
                return cls.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load DNS config: {e}")
        
        # Create default configuration
        config = cls()
        config.save()
        
        return config
    
    def save(self) -> bool:
        """
        Save DNS configuration to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with open(DNS_CONFIG_PATH, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save DNS config: {e}")
            return False


class DNSRecord:
    """DNS record for service discovery."""
    
    def __init__(self, name: str, type: int, class_: int = IN_CLASS,
                 ttl: int = 60, data: Optional[bytes] = None):
        """
        Initialize a DNS record.
        
        Args:
            name: Record name
            type: Record type
            class_: Record class
            ttl: Time to live (in seconds)
            data: Record data
        """
        self.name = name
        self.type = type
        self.class_ = class_
        self.ttl = ttl
        self.data = data or b''
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the DNS record to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "type": self.type,
            "class": self.class_,
            "ttl": self.ttl,
            "data": self.data.hex() if self.data else ""
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DNSRecord':
        """
        Create a DNS record from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DNSRecord object
        """
        record_data = bytes.fromhex(data.get("data", "")) if data.get("data") else b''
        
        return cls(
            name=data.get("name", ""),
            type=data.get("type", A_RECORD),
            class_=data.get("class", IN_CLASS),
            ttl=data.get("ttl", 60),
            data=record_data
        )
    
    @classmethod
    def create_a_record(cls, name: str, ip: str, ttl: int = 60) -> 'DNSRecord':
        """
        Create an A record.
        
        Args:
            name: Record name
            ip: IPv4 address
            ttl: Time to live (in seconds)
            
        Returns:
            DNSRecord object
        """
        # Convert IPv4 address to bytes
        ip_bytes = socket.inet_aton(ip)
        
        return cls(
            name=name,
            type=A_RECORD,
            ttl=ttl,
            data=ip_bytes
        )
    
    @classmethod
    def create_aaaa_record(cls, name: str, ip: str, ttl: int = 60) -> 'DNSRecord':
        """
        Create an AAAA record.
        
        Args:
            name: Record name
            ip: IPv6 address
            ttl: Time to live (in seconds)
            
        Returns:
            DNSRecord object
        """
        # Convert IPv6 address to bytes
        ip_bytes = socket.inet_pton(socket.AF_INET6, ip)
        
        return cls(
            name=name,
            type=AAAA_RECORD,
            ttl=ttl,
            data=ip_bytes
        )
    
    @classmethod
    def create_srv_record(cls, name: str, priority: int, weight: int, port: int,
                         target: str, ttl: int = 60) -> 'DNSRecord':
        """
        Create an SRV record.
        
        Args:
            name: Record name
            priority: Priority value
            weight: Weight value
            port: Port number
            target: Target hostname
            ttl: Time to live (in seconds)
            
        Returns:
            DNSRecord object
        """
        # Pack SRV record data
        data = struct.pack('!HHH', priority, weight, port)
        
        # Add target hostname
        for part in target.split('.'):
            data += struct.pack('!B', len(part))
            data += part.encode()
        
        # Add terminating zero
        data += struct.pack('!B', 0)
        
        return cls(
            name=name,
            type=SRV_RECORD,
            ttl=ttl,
            data=data
        )
    
    @classmethod
    def create_txt_record(cls, name: str, text: str, ttl: int = 60) -> 'DNSRecord':
        """
        Create a TXT record.
        
        Args:
            name: Record name
            text: Text value
            ttl: Time to live (in seconds)
            
        Returns:
            DNSRecord object
        """
        # Pack TXT record data
        text_bytes = text.encode()
        data = struct.pack('!B', len(text_bytes)) + text_bytes
        
        return cls(
            name=name,
            type=TXT_RECORD,
            ttl=ttl,
            data=data
        )


class DNSZone:
    """DNS zone for service discovery."""
    
    def __init__(self, domain: str = "kos.local", ttl: int = 60):
        """
        Initialize a DNS zone.
        
        Args:
            domain: Zone domain
            ttl: Default time to live (in seconds)
        """
        self.domain = domain
        self.ttl = ttl
        self.records: Dict[str, Dict[int, List[DNSRecord]]] = {}
    
    def add_record(self, record: DNSRecord) -> None:
        """
        Add a DNS record to the zone.
        
        Args:
            record: DNS record to add
        """
        name = record.name.lower()
        
        if name not in self.records:
            self.records[name] = {}
        
        if record.type not in self.records[name]:
            self.records[name][record.type] = []
        
        self.records[name][record.type].append(record)
    
    def get_records(self, name: str, type_: int) -> List[DNSRecord]:
        """
        Get DNS records from the zone.
        
        Args:
            name: Record name
            type_: Record type
            
        Returns:
            List of DNS records
        """
        name = name.lower()
        
        if name in self.records and type_ in self.records[name]:
            return self.records[name][type_]
        
        return []
    
    def remove_records(self, name: Optional[str] = None, type_: Optional[int] = None) -> int:
        """
        Remove DNS records from the zone.
        
        Args:
            name: Record name, or None to match all names
            type_: Record type, or None to match all types
            
        Returns:
            Number of records removed
        """
        count = 0
        
        if name is not None:
            name = name.lower()
            
            if name in self.records:
                if type_ is not None:
                    if type_ in self.records[name]:
                        count = len(self.records[name][type_])
                        del self.records[name][type_]
                else:
                    for type_records in self.records[name].values():
                        count += len(type_records)
                    
                    del self.records[name]
        else:
            if type_ is not None:
                for name_records in list(self.records.keys()):
                    if type_ in self.records[name_records]:
                        count += len(self.records[name_records][type_])
                        del self.records[name_records][type_]
            else:
                # Remove all records
                total = 0
                for name_records in self.records.values():
                    for type_records in name_records.values():
                        total += len(type_records)
                
                count = total
                self.records.clear()
        
        return count
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the DNS zone to a dictionary.
        
        Returns:
            Dict representation
        """
        records_dict = {}
        
        for name, type_records in self.records.items():
            records_dict[name] = {}
            
            for type_, records in type_records.items():
                records_dict[name][str(type_)] = [record.to_dict() for record in records]
        
        return {
            "domain": self.domain,
            "ttl": self.ttl,
            "records": records_dict
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DNSZone':
        """
        Create a DNS zone from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DNSZone object
        """
        zone = cls(
            domain=data.get("domain", "kos.local"),
            ttl=data.get("ttl", 60)
        )
        
        # Load records
        records_dict = data.get("records", {})
        
        for name, type_records in records_dict.items():
            for type_str, records in type_records.items():
                type_ = int(type_str)
                
                for record_data in records:
                    record = DNSRecord.from_dict(record_data)
                    zone.add_record(record)
        
        return zone
    
    def save(self, file_path: str) -> bool:
        """
        Save the DNS zone to disk.
        
        Args:
            file_path: File path to save to
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save DNS zone: {e}")
            return False
    
    @classmethod
    def load(cls, file_path: str) -> Optional['DNSZone']:
        """
        Load a DNS zone from disk.
        
        Args:
            file_path: File path to load from
            
        Returns:
            DNSZone object or None if loading failed
        """
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                return cls.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load DNS zone: {e}")
        
        return None


class ServiceDiscovery:
    """
    Service discovery for the KOS orchestration system.
    
    This class provides DNS-based service discovery for the KOS orchestration system,
    allowing pods to discover and communicate with each other using stable network endpoints.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ServiceDiscovery, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize service discovery."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = DNSConfig.load()
        self.zone = self._load_zone()
        self._stop_event = threading.Event()
        self._update_thread = None
        self._dns_server = None
        
        # Start update thread
        self._start_update_thread()
    
    def _zone_file_path(self) -> str:
        """Get the file path for the DNS zone."""
        return os.path.join(DNS_CACHE_PATH, f"{self.config.domain}.json")
    
    def _load_zone(self) -> DNSZone:
        """
        Load the DNS zone from disk.
        
        Returns:
            DNSZone object
        """
        zone = DNSZone.load(self._zone_file_path())
        
        if zone is None:
            zone = DNSZone(domain=self.config.domain, ttl=self.config.ttl)
            zone.save(self._zone_file_path())
        
        return zone
    
    def _save_zone(self) -> bool:
        """
        Save the DNS zone to disk.
        
        Returns:
            bool: Success or failure
        """
        return self.zone.save(self._zone_file_path())
    
    def _start_update_thread(self) -> None:
        """Start the update thread."""
        if self._update_thread and self._update_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True
        )
        self._update_thread.start()
    
    def _stop_update_thread(self) -> None:
        """Stop the update thread."""
        if not self._update_thread or not self._update_thread.is_alive():
            return
        
        self._stop_event.set()
        self._update_thread.join(timeout=5)
    
    def _update_loop(self) -> None:
        """Update loop for service discovery."""
        while not self._stop_event.is_set():
            try:
                self.update_records()
            except Exception as e:
                logger.error(f"Error in service discovery update loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(30)  # Update every 30 seconds
    
    def update_records(self) -> bool:
        """
        Update DNS records for services.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Clear existing service records
                self.zone.remove_records(type_=SRV_RECORD)
                
                # Update records for services
                services = Service.list_services()
                
                for service in services:
                    self._add_service_records(service)
                
                # Update records for pods
                pods = Pod.list_pods()
                
                for pod in pods:
                    self._add_pod_records(pod)
                
                # Save zone
                self._save_zone()
                
                return True
        except Exception as e:
            logger.error(f"Failed to update DNS records: {e}")
            return False
    
    def _add_service_records(self, service: Service) -> None:
        """
        Add DNS records for a service.
        
        Args:
            service: Service to add records for
        """
        # Get service endpoint
        endpoints = service.get_endpoints()
        
        if not endpoints:
            return
        
        # Create service domain name
        service_domain = f"{service.name}.{service.namespace}.svc.{self.config.domain}"
        
        # Add A record for service IP
        service_ips = [endpoint["ip"] for endpoint in endpoints]
        
        for ip in service_ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                
                if ip_obj.version == 4:
                    record = DNSRecord.create_a_record(service_domain, ip, self.config.ttl)
                    self.zone.add_record(record)
                elif ip_obj.version == 6:
                    record = DNSRecord.create_aaaa_record(service_domain, ip, self.config.ttl)
                    self.zone.add_record(record)
            except ValueError:
                continue
        
        # Add SRV records for service ports
        for port in service.spec.ports:
            for endpoint in endpoints:
                port_name = port.name or str(port.port)
                srv_name = f"_{port_name}._tcp.{service_domain}"
                
                for subset_port in endpoint.get("ports", []):
                    if subset_port.get("name") == port.name or subset_port.get("port") == port.port:
                        target = f"{endpoint['ip']}.{service.namespace}.pod.{self.config.domain}"
                        record = DNSRecord.create_srv_record(
                            srv_name,
                            0,  # Priority
                            10,  # Weight
                            subset_port.get("port", port.port),
                            target,
                            self.config.ttl
                        )
                        self.zone.add_record(record)
                        break
        
        # Add TXT record with service metadata
        txt_record = DNSRecord.create_txt_record(
            service_domain,
            f"name={service.name} namespace={service.namespace} uid={service.metadata.get('uid', '')}",
            self.config.ttl
        )
        self.zone.add_record(txt_record)
    
    def _add_pod_records(self, pod: Pod) -> None:
        """
        Add DNS records for a pod.
        
        Args:
            pod: Pod to add records for
        """
        # Get pod IP
        pod_ip = pod.status.pod_ip
        
        if not pod_ip:
            return
        
        # Create pod domain name
        pod_domain = f"{pod.name}.{pod.namespace}.pod.{self.config.domain}"
        
        # Add A or AAAA record for pod IP
        try:
            ip_obj = ipaddress.ip_address(pod_ip)
            
            if ip_obj.version == 4:
                record = DNSRecord.create_a_record(pod_domain, pod_ip, self.config.ttl)
                self.zone.add_record(record)
            elif ip_obj.version == 6:
                record = DNSRecord.create_aaaa_record(pod_domain, pod_ip, self.config.ttl)
                self.zone.add_record(record)
        except ValueError:
            return
        
        # Check if pod has hostname and subdomain
        if pod.spec.hostname and pod.spec.subdomain:
            # Create hostname.subdomain domain name
            hostname_domain = f"{pod.spec.hostname}.{pod.spec.subdomain}.{pod.namespace}.svc.{self.config.domain}"
            
            # Add A or AAAA record for hostname
            try:
                ip_obj = ipaddress.ip_address(pod_ip)
                
                if ip_obj.version == 4:
                    record = DNSRecord.create_a_record(hostname_domain, pod_ip, self.config.ttl)
                    self.zone.add_record(record)
                elif ip_obj.version == 6:
                    record = DNSRecord.create_aaaa_record(hostname_domain, pod_ip, self.config.ttl)
                    self.zone.add_record(record)
            except ValueError:
                pass
    
    def lookup_service(self, name: str, namespace: str = "default") -> List[Dict[str, Any]]:
        """
        Look up a service by name and namespace.
        
        Args:
            name: Service name
            namespace: Namespace
            
        Returns:
            List of service endpoints
        """
        try:
            # Get service
            service = Service.get_service(name, namespace)
            
            if not service:
                return []
            
            # Get service endpoints
            return service.get_endpoints()
        except Exception as e:
            logger.error(f"Failed to look up service {namespace}/{name}: {e}")
            return []
    
    def lookup_name(self, name: str, type_: int = A_RECORD) -> List[DNSRecord]:
        """
        Look up a name in the DNS zone.
        
        Args:
            name: Name to look up
            type_: Record type
            
        Returns:
            List of DNS records
        """
        with self._lock:
            return self.zone.get_records(name, type_)
    
    def get_service_url(self, name: str, namespace: str = "default",
                       port_name: Optional[str] = None, port_number: Optional[int] = None,
                       use_https: bool = False) -> Optional[str]:
        """
        Get a URL for a service.
        
        Args:
            name: Service name
            namespace: Namespace
            port_name: Port name
            port_number: Port number
            use_https: Whether to use HTTPS
            
        Returns:
            Service URL or None if service not found
        """
        try:
            # Get service
            service = Service.get_service(name, namespace)
            
            if not service:
                return None
            
            # Find port
            port = None
            
            if port_name:
                # Find port by name
                for p in service.spec.ports:
                    if p.name == port_name:
                        port = p
                        break
            elif port_number:
                # Find port by number
                for p in service.spec.ports:
                    if p.port == port_number:
                        port = p
                        break
            else:
                # Use first port
                if service.spec.ports:
                    port = service.spec.ports[0]
            
            if not port:
                return None
            
            # Build URL
            protocol = "https" if use_https else "http"
            return f"{protocol}://{name}.{namespace}.svc.{self.config.domain}:{port.port}"
        except Exception as e:
            logger.error(f"Failed to get service URL for {namespace}/{name}: {e}")
            return None
    
    def start_dns_server(self) -> bool:
        """
        Start the DNS server.
        
        Returns:
            bool: Success or failure
        """
        if self._dns_server:
            return True
        
        try:
            from kos.core.network.dns import DNSServer
            
            self._dns_server = DNSServer(self)
            return self._dns_server.start()
        except ImportError:
            logger.error("Failed to import DNSServer")
            return False
    
    def stop_dns_server(self) -> bool:
        """
        Stop the DNS server.
        
        Returns:
            bool: Success or failure
        """
        if not self._dns_server:
            return True
        
        return self._dns_server.stop()
    
    def update_config(self, config: DNSConfig) -> bool:
        """
        Update DNS configuration.
        
        Args:
            config: New configuration
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Save new configuration
                self.config = config
                
                if not config.save():
                    logger.error("Failed to save DNS configuration")
                    return False
                
                # Update zone
                self.zone.domain = config.domain
                self.zone.ttl = config.ttl
                
                # Restart DNS server if running
                if self._dns_server:
                    self.stop_dns_server()
                    self.start_dns_server()
                
                return True
        except Exception as e:
            logger.error(f"Failed to update DNS configuration: {e}")
            return False

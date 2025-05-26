"""
Service Discovery for KOS Orchestration

This module implements service discovery for the KOS container orchestration system,
providing DNS-based service discovery and registration.

Service discovery enables containers to find and communicate with services
without knowing their exact IP addresses.
"""

import os
import json
import time
import socket
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

from .service import Service

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
DNS_CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/kos/dns/config.json')
DNS_RECORDS_PATH = os.path.join(KOS_ROOT, 'var/lib/kos/dns/records.json')

# Ensure directories exist
os.makedirs(os.path.dirname(DNS_CONFIG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(DNS_RECORDS_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class DNSRecordType(str, Enum):
    """DNS record types."""
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    SRV = "SRV"
    TXT = "TXT"


class DNSRecord:
    """Represents a DNS record."""
    
    def __init__(self, name: str, type: DNSRecordType, ttl: int = 60,
                 data: Union[str, List[str]] = None):
        """
        Initialize a DNS record.
        
        Args:
            name: Record name (e.g., 'service.namespace.svc.cluster.local')
            type: Record type
            ttl: Time to live in seconds
            data: Record data (IP address, hostname, etc.)
        """
        self.name = name
        self.type = type
        self.ttl = ttl
        self.data = data or []
        self.created = time.time()
        self.updated = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the DNS record to a dictionary.
        
        Returns:
            Dict representation of the DNS record
        """
        return {
            "name": self.name,
            "type": self.type,
            "ttl": self.ttl,
            "data": self.data,
            "created": self.created,
            "updated": self.updated
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DNSRecord':
        """
        Create a DNS record from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            DNSRecord object
        """
        record = DNSRecord(
            name=data.get("name", ""),
            type=data.get("type", DNSRecordType.A),
            ttl=data.get("ttl", 60),
            data=data.get("data", [])
        )
        record.created = data.get("created", time.time())
        record.updated = data.get("updated", time.time())
        
        return record


class DNSProvider:
    """
    DNS provider for service discovery.
    
    This class provides DNS resolution for service discovery within
    the cluster.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DNSProvider, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the DNS provider."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = self._load_config()
        self.records = self._load_records()
        self._record_lock = threading.Lock()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load DNS configuration from disk."""
        if os.path.exists(DNS_CONFIG_PATH):
            try:
                with open(DNS_CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load DNS config: {e}")
        
        # Default configuration
        default_config = {
            "domain": "cluster.local",
            "service_domain": "svc.cluster.local",
            "ttl": 60,
            "enabled": True
        }
        
        # Save default configuration
        try:
            os.makedirs(os.path.dirname(DNS_CONFIG_PATH), exist_ok=True)
            with open(DNS_CONFIG_PATH, 'w') as f:
                json.dump(default_config, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save default DNS config: {e}")
        
        return default_config
    
    def _save_config(self) -> bool:
        """
        Save DNS configuration to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with open(DNS_CONFIG_PATH, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logger.info("Saved DNS configuration")
            return True
        except Exception as e:
            logger.error(f"Failed to save DNS configuration: {e}")
            return False
    
    def _load_records(self) -> Dict[str, DNSRecord]:
        """Load DNS records from disk."""
        if os.path.exists(DNS_RECORDS_PATH):
            try:
                with open(DNS_RECORDS_PATH, 'r') as f:
                    data = json.load(f)
                    return {
                        name: DNSRecord.from_dict(record)
                        for name, record in data.items()
                    }
            except Exception as e:
                logger.error(f"Failed to load DNS records: {e}")
        
        return {}
    
    def _save_records(self) -> bool:
        """
        Save DNS records to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with open(DNS_RECORDS_PATH, 'w') as f:
                json.dump({
                    name: record.to_dict()
                    for name, record in self.records.items()
                }, f, indent=2)
            
            logger.info("Saved DNS records")
            return True
        except Exception as e:
            logger.error(f"Failed to save DNS records: {e}")
            return False
    
    def add_record(self, name: str, type: DNSRecordType, 
                  data: Union[str, List[str]], ttl: int = None) -> bool:
        """
        Add a DNS record.
        
        Args:
            name: Record name
            type: Record type
            data: Record data
            ttl: Time to live in seconds
            
        Returns:
            bool: Success or failure
        """
        with self._record_lock:
            # Set default TTL if not specified
            if ttl is None:
                ttl = self.config.get("ttl", 60)
            
            # Normalize data to list
            if isinstance(data, str):
                data = [data]
            
            # Check if record already exists
            if name in self.records:
                record = self.records[name]
                record.type = type
                record.ttl = ttl
                record.data = data
                record.updated = time.time()
            else:
                # Create new record
                record = DNSRecord(name, type, ttl, data)
                self.records[name] = record
            
            # Save records
            return self._save_records()
    
    def remove_record(self, name: str) -> bool:
        """
        Remove a DNS record.
        
        Args:
            name: Record name
            
        Returns:
            bool: Success or failure
        """
        with self._record_lock:
            if name not in self.records:
                logger.warning(f"DNS record not found: {name}")
                return False
            
            # Remove record
            del self.records[name]
            
            # Save records
            return self._save_records()
    
    def get_record(self, name: str) -> Optional[DNSRecord]:
        """
        Get a DNS record.
        
        Args:
            name: Record name
            
        Returns:
            DNSRecord or None if not found
        """
        return self.records.get(name)
    
    def resolve(self, name: str, type: DNSRecordType = DNSRecordType.A) -> List[str]:
        """
        Resolve a DNS name.
        
        Args:
            name: DNS name to resolve
            type: Record type to resolve
            
        Returns:
            List of resolved values
        """
        # Check if we have a direct record
        record = self.records.get(name)
        if record and record.type == type:
            return record.data
        
        # Check for CNAME records
        record = self.records.get(name)
        if record and record.type == DNSRecordType.CNAME and record.data:
            cname = record.data[0]
            return self.resolve(cname, type)
        
        # Check for wildcard records
        parts = name.split('.')
        while parts:
            wildcard = '*.' + '.'.join(parts[1:])
            record = self.records.get(wildcard)
            if record and record.type == type:
                return record.data
            parts.pop(0)
        
        # No record found
        return []
    
    def set_domain(self, domain: str) -> bool:
        """
        Set the cluster domain.
        
        Args:
            domain: New cluster domain
            
        Returns:
            bool: Success or failure
        """
        self.config["domain"] = domain
        return self._save_config()
    
    def set_service_domain(self, domain: str) -> bool:
        """
        Set the service domain.
        
        Args:
            domain: New service domain
            
        Returns:
            bool: Success or failure
        """
        self.config["service_domain"] = domain
        return self._save_config()
    
    def set_ttl(self, ttl: int) -> bool:
        """
        Set the default TTL.
        
        Args:
            ttl: New default TTL in seconds
            
        Returns:
            bool: Success or failure
        """
        self.config["ttl"] = ttl
        return self._save_config()
    
    def enable(self) -> bool:
        """
        Enable the DNS provider.
        
        Returns:
            bool: Success or failure
        """
        self.config["enabled"] = True
        return self._save_config()
    
    def disable(self) -> bool:
        """
        Disable the DNS provider.
        
        Returns:
            bool: Success or failure
        """
        self.config["enabled"] = False
        return self._save_config()


class ServiceDiscovery:
    """
    Service discovery for the KOS orchestration system.
    
    This class integrates with the DNS provider to enable service discovery
    for pods.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ServiceDiscovery, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the service discovery system."""
        if self._initialized:
            return
        
        self._initialized = True
        self.dns_provider = DNSProvider()
        self._service_watch_thread = None
        self._stop_event = threading.Event()
    
    def start(self):
        """Start the service discovery system."""
        if self._service_watch_thread and self._service_watch_thread.is_alive():
            logger.warning("Service discovery is already running")
            return
        
        self._stop_event.clear()
        self._service_watch_thread = threading.Thread(
            target=self._watch_services, daemon=True
        )
        self._service_watch_thread.start()
        logger.info("Started service discovery")
    
    def stop(self):
        """Stop the service discovery system."""
        if not self._service_watch_thread or not self._service_watch_thread.is_alive():
            logger.warning("Service discovery is not running")
            return
        
        self._stop_event.set()
        self._service_watch_thread.join(timeout=5)
        logger.info("Stopped service discovery")
    
    def _watch_services(self):
        """Watch for service changes and update DNS records."""
        while not self._stop_event.is_set():
            try:
                # Get all services
                services = Service.list_services()
                
                # Update DNS records for each service
                for service in services:
                    self._update_service_records(service)
                
                # Sleep for a while before checking again
                self._stop_event.wait(30)
            except Exception as e:
                logger.error(f"Error in service watch: {e}")
                self._stop_event.wait(10)
    
    def _update_service_records(self, service: Service):
        """
        Update DNS records for a service.
        
        Args:
            service: Service to update records for
        """
        try:
            # Get service domain suffix
            service_domain = self.dns_provider.config.get(
                "service_domain", "svc.cluster.local"
            )
            
            # Create A record for the service
            service_name = f"{service.name}.{service.namespace}.{service_domain}"
            cluster_ip = service.get_cluster_ip()
            
            if cluster_ip:
                self.dns_provider.add_record(
                    name=service_name,
                    type=DNSRecordType.A,
                    data=[cluster_ip]
                )
                
                # Create A records for each port (for SRV resolution)
                for port in service.spec.ports:
                    port_name = f"{port.name}.{service_name}"
                    self.dns_provider.add_record(
                        name=port_name,
                        type=DNSRecordType.A,
                        data=[cluster_ip]
                    )
                    
                    # Create SRV record for the port
                    srv_name = f"_{port.name}._tcp.{service_name}"
                    srv_data = f"0 0 {port.port} {service_name}"
                    self.dns_provider.add_record(
                        name=srv_name,
                        type=DNSRecordType.SRV,
                        data=[srv_data]
                    )
            
            # Create CNAME record for ExternalName services
            if service.spec.type == "ExternalName" and service.spec.external_name:
                self.dns_provider.add_record(
                    name=service_name,
                    type=DNSRecordType.CNAME,
                    data=[service.spec.external_name]
                )
            
            # Create TXT record with service metadata
            txt_data = [
                f"namespace={service.namespace}",
                f"type={service.spec.type}",
                f"created={service.creation_timestamp}"
            ]
            self.dns_provider.add_record(
                name=f"txt.{service_name}",
                type=DNSRecordType.TXT,
                data=txt_data
            )
            
            logger.info(f"Updated DNS records for service {service.namespace}/{service.name}")
        except Exception as e:
            logger.error(f"Failed to update DNS records for service {service.namespace}/{service.name}: {e}")
    
    def register_service(self, service: Service) -> bool:
        """
        Register a service for discovery.
        
        Args:
            service: Service to register
            
        Returns:
            bool: Success or failure
        """
        try:
            self._update_service_records(service)
            return True
        except Exception as e:
            logger.error(f"Failed to register service {service.namespace}/{service.name}: {e}")
            return False
    
    def unregister_service(self, service: Service) -> bool:
        """
        Unregister a service from discovery.
        
        Args:
            service: Service to unregister
            
        Returns:
            bool: Success or failure
        """
        try:
            # Get service domain suffix
            service_domain = self.dns_provider.config.get(
                "service_domain", "svc.cluster.local"
            )
            
            # Remove A record for the service
            service_name = f"{service.name}.{service.namespace}.{service_domain}"
            self.dns_provider.remove_record(service_name)
            
            # Remove port records
            for port in service.spec.ports:
                # Remove A record for the port
                port_name = f"{port.name}.{service_name}"
                self.dns_provider.remove_record(port_name)
                
                # Remove SRV record for the port
                srv_name = f"_{port.name}._tcp.{service_name}"
                self.dns_provider.remove_record(srv_name)
            
            # Remove TXT record
            self.dns_provider.remove_record(f"txt.{service_name}")
            
            logger.info(f"Removed DNS records for service {service.namespace}/{service.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unregister service {service.namespace}/{service.name}: {e}")
            return False
    
    def lookup_service(self, name: str, namespace: str = "default") -> Optional[str]:
        """
        Look up a service by name.
        
        Args:
            name: Service name
            namespace: Service namespace
            
        Returns:
            Service IP address or None if not found
        """
        try:
            # Get service domain suffix
            service_domain = self.dns_provider.config.get(
                "service_domain", "svc.cluster.local"
            )
            
            # Construct service name
            service_name = f"{name}.{namespace}.{service_domain}"
            
            # Resolve service name
            ips = self.dns_provider.resolve(service_name, DNSRecordType.A)
            if ips:
                return ips[0]
            
            # Check if it's an ExternalName service
            cnames = self.dns_provider.resolve(service_name, DNSRecordType.CNAME)
            if cnames:
                try:
                    # Try to resolve the CNAME
                    return socket.gethostbyname(cnames[0])
                except socket.error:
                    return cnames[0]
            
            return None
        except Exception as e:
            logger.error(f"Failed to look up service {namespace}/{name}: {e}")
            return None
    
    def lookup_service_port(self, name: str, port: str, 
                           namespace: str = "default") -> Optional[Tuple[str, int]]:
        """
        Look up a service port.
        
        Args:
            name: Service name
            port: Port name
            namespace: Service namespace
            
        Returns:
            Tuple of (IP, port) or None if not found
        """
        try:
            # Get service domain suffix
            service_domain = self.dns_provider.config.get(
                "service_domain", "svc.cluster.local"
            )
            
            # Construct service name
            service_name = f"{name}.{namespace}.{service_domain}"
            
            # Look up SRV record
            srv_name = f"_{port}._tcp.{service_name}"
            srv_records = self.dns_provider.resolve(srv_name, DNSRecordType.SRV)
            
            if srv_records:
                # Parse SRV record
                # Format: "priority weight port target"
                parts = srv_records[0].split()
                if len(parts) >= 4:
                    srv_port = int(parts[2])
                    srv_target = parts[3]
                    
                    # Look up target IP
                    ips = self.dns_provider.resolve(srv_target, DNSRecordType.A)
                    if ips:
                        return (ips[0], srv_port)
            
            # Fall back to direct service lookup
            service_ip = self.lookup_service(name, namespace)
            if service_ip:
                # Load the service to get the port mapping
                service = Service.load(name, namespace)
                if service:
                    for service_port in service.spec.ports:
                        if service_port.name == port:
                            return (service_ip, service_port.port)
            
            return None
        except Exception as e:
            logger.error(f"Failed to look up service port {namespace}/{name}/{port}: {e}")
            return None

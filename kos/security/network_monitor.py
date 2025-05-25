"""
KOS Network Security Monitor

This module provides network connection monitoring and security features,
allowing detection of suspicious network activity.
"""

import os
import sys
import time
import logging
import json
import threading
import socket
import ipaddress
import re
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable

# Import IDS for alerting
from kos.security.ids import IDSManager

# Set up logging
logger = logging.getLogger('KOS.security.network_monitor')

# Lock for network monitor operations
_netmon_lock = threading.RLock()

# Network monitor database
_connections = {}
_connection_history = []
_known_hosts = {}
_blacklist = []
_whitelist = []

# Network monitor configuration
_netmon_config = {
    'enabled': False,
    'max_connections': 1000,    # Maximum number of connections to store in history
    'check_interval': 60,       # Default: check every minute
    'log_file': os.path.join(os.path.expanduser('~'), '.kos', 'security', 'network.log'),
    'alert_on_blacklist': True, # Alert on blacklisted connections
    'alert_on_new_hosts': True, # Alert on connections to new hosts
    'max_rate': 10,             # Maximum connections per minute to same host
}

# Network monitor background thread
_netmon_thread = None
_netmon_thread_stop = False


class NetworkConnection:
    """Class representing a network connection"""
    
    def __init__(self, timestamp: float, protocol: str, local_addr: str, 
                 local_port: int, remote_addr: str, remote_port: int, 
                 state: str, pid: int = None, program: str = None):
        """
        Initialize network connection
        
        Args:
            timestamp: Connection timestamp
            protocol: Connection protocol (tcp, udp)
            local_addr: Local address
            local_port: Local port
            remote_addr: Remote address
            remote_port: Remote port
            state: Connection state
            pid: Process ID
            program: Program name
        """
        self.timestamp = timestamp
        self.protocol = protocol
        self.local_addr = local_addr
        self.local_port = local_port
        self.remote_addr = remote_addr
        self.remote_port = remote_port
        self.state = state
        self.pid = pid
        self.program = program
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'timestamp': self.timestamp,
            'protocol': self.protocol,
            'local_addr': self.local_addr,
            'local_port': self.local_port,
            'remote_addr': self.remote_addr,
            'remote_port': self.remote_port,
            'state': self.state,
            'pid': self.pid,
            'program': self.program
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkConnection':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            NetworkConnection instance
        """
        return cls(
            timestamp=data.get('timestamp', 0.0),
            protocol=data.get('protocol', ''),
            local_addr=data.get('local_addr', ''),
            local_port=data.get('local_port', 0),
            remote_addr=data.get('remote_addr', ''),
            remote_port=data.get('remote_port', 0),
            state=data.get('state', ''),
            pid=data.get('pid'),
            program=data.get('program')
        )
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.protocol} {self.local_addr}:{self.local_port} -> {self.remote_addr}:{self.remote_port} ({self.state})"


class HostInfo:
    """Class representing information about a network host"""
    
    def __init__(self, address: str, hostname: str = None, 
                 first_seen: float = None, last_seen: float = None,
                 ports: Set[int] = None, tags: List[str] = None):
        """
        Initialize host info
        
        Args:
            address: IP address
            hostname: Hostname
            first_seen: First seen timestamp
            last_seen: Last seen timestamp
            ports: Set of ports used
            tags: List of tags
        """
        self.address = address
        self.hostname = hostname
        self.first_seen = first_seen or time.time()
        self.last_seen = last_seen or time.time()
        self.ports = ports or set()
        self.tags = tags or []
        self.connection_count = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            'address': self.address,
            'hostname': self.hostname,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'ports': list(self.ports),
            'tags': self.tags,
            'connection_count': self.connection_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HostInfo':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            HostInfo instance
        """
        host = cls(
            address=data.get('address', ''),
            hostname=data.get('hostname'),
            first_seen=data.get('first_seen'),
            last_seen=data.get('last_seen'),
            ports=set(data.get('ports', [])),
            tags=data.get('tags', [])
        )
        
        host.connection_count = data.get('connection_count', 0)
        
        return host


class NetworkMonitor:
    """Manager for network monitoring operations"""
    
    @classmethod
    def get_current_connections(cls) -> List[NetworkConnection]:
        """
        Get current network connections
        
        Returns:
            List of NetworkConnection instances
        """
        connections = []
        
        try:
            # In a real implementation, this would use system commands like netstat
            # or direct socket operations to get actual network connections.
            # For now, just simulate some connections for testing.
            
            # Check if we can get socket connections
            try:
                # Try to create a test connection to google.com to have something to detect
                test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                test_socket.settimeout(1)
                test_socket.connect(('8.8.8.8', 53))
                
                # Add a simulated connection for the test
                connections.append(NetworkConnection(
                    timestamp=time.time(),
                    protocol='tcp',
                    local_addr='127.0.0.1',
                    local_port=12345,
                    remote_addr='8.8.8.8',
                    remote_port=53,
                    state='ESTABLISHED',
                    pid=os.getpid(),
                    program='python'
                ))
                
                test_socket.close()
            except:
                pass
            
            # Add some simulated connections for localhost
            connections.append(NetworkConnection(
                timestamp=time.time(),
                protocol='tcp',
                local_addr='127.0.0.1',
                local_port=8080,
                remote_addr='127.0.0.1',
                remote_port=35000,
                state='LISTEN',
                pid=os.getpid(),
                program='python'
            ))
        except Exception as e:
            logger.error(f"Error getting network connections: {e}")
        
        return connections
    
    @classmethod
    def update_connections(cls) -> None:
        """Update current connections"""
        with _netmon_lock:
            # Get current connections
            current = cls.get_current_connections()
            
            # Update connections dictionary
            _connections.clear()
            for conn in current:
                key = f"{conn.protocol}:{conn.local_addr}:{conn.local_port}:{conn.remote_addr}:{conn.remote_port}"
                _connections[key] = conn
            
            # Add to history
            _connection_history.extend(current)
            
            # Limit history size
            while len(_connection_history) > _netmon_config['max_connections']:
                _connection_history.pop(0)
            
            # Update host information
            for conn in current:
                cls._update_host_info(conn)
            
            # Check for suspicious connections
            for conn in current:
                cls._check_connection(conn)
    
    @classmethod
    def _update_host_info(cls, conn: NetworkConnection) -> None:
        """
        Update host information
        
        Args:
            conn: Network connection
        """
        # Skip local connections
        if conn.remote_addr.startswith('127.') or conn.remote_addr == '::1':
            return
        
        # Update remote host info
        if conn.remote_addr not in _known_hosts:
            # New host
            host_info = HostInfo(
                address=conn.remote_addr,
                ports={conn.remote_port}
            )
            
            # Try to resolve hostname
            try:
                hostname = socket.gethostbyaddr(conn.remote_addr)[0]
                host_info.hostname = hostname
            except:
                pass
            
            # Add to known hosts
            _known_hosts[conn.remote_addr] = host_info
            
            # Alert on new host if configured
            if _netmon_config['alert_on_new_hosts']:
                logger.warning(f"New host detected: {conn.remote_addr}")
                
                # Send alert to IDS
                IDSManager.add_event(
                    event_type="network",
                    source="network_monitor",
                    details={
                        "message": "New host detected",
                        "address": conn.remote_addr,
                        "hostname": host_info.hostname,
                        "port": conn.remote_port
                    },
                    severity=2
                )
        else:
            # Update existing host
            host_info = _known_hosts[conn.remote_addr]
            host_info.last_seen = time.time()
            host_info.ports.add(conn.remote_port)
            host_info.connection_count += 1
    
    @classmethod
    def _check_connection(cls, conn: NetworkConnection) -> None:
        """
        Check connection for suspicious activity
        
        Args:
            conn: Network connection
        """
        # Skip local connections
        if conn.remote_addr.startswith('127.') or conn.remote_addr == '::1':
            return
        
        # Check blacklist
        if _netmon_config['alert_on_blacklist'] and cls.is_blacklisted(conn.remote_addr):
            logger.warning(f"Connection to blacklisted host: {conn.remote_addr}")
            
            # Send alert to IDS
            IDSManager.add_event(
                event_type="network",
                source="network_monitor",
                details={
                    "message": "Connection to blacklisted host",
                    "address": conn.remote_addr,
                    "port": conn.remote_port,
                    "protocol": conn.protocol,
                    "program": conn.program
                },
                severity=5
            )
        
        # Check connection rate
        if conn.remote_addr in _known_hosts:
            host_info = _known_hosts[conn.remote_addr]
            
            # Check if connection rate is too high
            recent_connections = cls.get_connection_history(
                remote_addr=conn.remote_addr,
                time_range=60  # Last minute
            )
            
            if len(recent_connections) > _netmon_config['max_rate']:
                logger.warning(f"High connection rate to host: {conn.remote_addr}")
                
                # Send alert to IDS
                IDSManager.add_event(
                    event_type="network",
                    source="network_monitor",
                    details={
                        "message": "High connection rate to host",
                        "address": conn.remote_addr,
                        "port": conn.remote_port,
                        "count": len(recent_connections),
                        "rate_limit": _netmon_config['max_rate']
                    },
                    severity=3
                )
        
        # Check suspicious ports
        suspicious_ports = [21, 22, 23, 25, 135, 445, 3389, 5900]
        if conn.remote_port in suspicious_ports:
            logger.warning(f"Connection to suspicious port: {conn.remote_addr}:{conn.remote_port}")
            
            # Send alert to IDS
            IDSManager.add_event(
                event_type="network",
                source="network_monitor",
                details={
                    "message": "Connection to suspicious port",
                    "address": conn.remote_addr,
                    "port": conn.remote_port,
                    "protocol": conn.protocol,
                    "program": conn.program
                },
                severity=4
            )
    
    @classmethod
    def get_connection_history(cls, protocol: str = None, 
                              local_addr: str = None, local_port: int = None,
                              remote_addr: str = None, remote_port: int = None,
                              program: str = None, time_range: int = None) -> List[NetworkConnection]:
        """
        Get connection history with filters
        
        Args:
            protocol: Filter by protocol
            local_addr: Filter by local address
            local_port: Filter by local port
            remote_addr: Filter by remote address
            remote_port: Filter by remote port
            program: Filter by program name
            time_range: Filter by time range in seconds from now
        
        Returns:
            List of NetworkConnection instances
        """
        with _netmon_lock:
            connections = _connection_history.copy()
            
            # Apply filters
            if protocol is not None:
                connections = [c for c in connections if c.protocol == protocol]
            
            if local_addr is not None:
                connections = [c for c in connections if c.local_addr == local_addr]
            
            if local_port is not None:
                connections = [c for c in connections if c.local_port == local_port]
            
            if remote_addr is not None:
                connections = [c for c in connections if c.remote_addr == remote_addr]
            
            if remote_port is not None:
                connections = [c for c in connections if c.remote_port == remote_port]
            
            if program is not None:
                connections = [c for c in connections if c.program and c.program == program]
            
            if time_range is not None:
                min_time = time.time() - time_range
                connections = [c for c in connections if c.timestamp >= min_time]
            
            return connections
    
    @classmethod
    def get_known_hosts(cls) -> Dict[str, HostInfo]:
        """
        Get known hosts
        
        Returns:
            Dictionary of host address to HostInfo
        """
        with _netmon_lock:
            return _known_hosts.copy()
    
    @classmethod
    def add_host_tag(cls, address: str, tag: str) -> Tuple[bool, str]:
        """
        Add a tag to a host
        
        Args:
            address: Host address
            tag: Tag to add
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if address not in _known_hosts:
                return False, f"Host {address} not found"
            
            host_info = _known_hosts[address]
            
            if tag in host_info.tags:
                return False, f"Host {address} already has tag {tag}"
            
            host_info.tags.append(tag)
            
            logger.info(f"Added tag {tag} to host {address}")
            
            return True, f"Added tag {tag} to host {address}"
    
    @classmethod
    def remove_host_tag(cls, address: str, tag: str) -> Tuple[bool, str]:
        """
        Remove a tag from a host
        
        Args:
            address: Host address
            tag: Tag to remove
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if address not in _known_hosts:
                return False, f"Host {address} not found"
            
            host_info = _known_hosts[address]
            
            if tag not in host_info.tags:
                return False, f"Host {address} does not have tag {tag}"
            
            host_info.tags.remove(tag)
            
            logger.info(f"Removed tag {tag} from host {address}")
            
            return True, f"Removed tag {tag} from host {address}"
    
    @classmethod
    def add_to_blacklist(cls, address: str) -> Tuple[bool, str]:
        """
        Add an address to the blacklist
        
        Args:
            address: IP address to blacklist
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            # Validate IP address
            try:
                ipaddress.ip_address(address)
            except ValueError:
                return False, f"Invalid IP address: {address}"
            
            if address in _blacklist:
                return False, f"Address {address} is already blacklisted"
            
            _blacklist.append(address)
            
            logger.info(f"Added {address} to blacklist")
            
            return True, f"Added {address} to blacklist"
    
    @classmethod
    def remove_from_blacklist(cls, address: str) -> Tuple[bool, str]:
        """
        Remove an address from the blacklist
        
        Args:
            address: IP address to remove from blacklist
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if address not in _blacklist:
                return False, f"Address {address} is not blacklisted"
            
            _blacklist.remove(address)
            
            logger.info(f"Removed {address} from blacklist")
            
            return True, f"Removed {address} from blacklist"
    
    @classmethod
    def is_blacklisted(cls, address: str) -> bool:
        """
        Check if an address is blacklisted
        
        Args:
            address: IP address to check
        
        Returns:
            True if blacklisted, False otherwise
        """
        with _netmon_lock:
            # Check exact match
            if address in _blacklist:
                return True
            
            # Check CIDR ranges
            try:
                ip = ipaddress.ip_address(address)
                for item in _blacklist:
                    if '/' in item:  # CIDR notation
                        try:
                            network = ipaddress.ip_network(item, strict=False)
                            if ip in network:
                                return True
                        except ValueError:
                            pass
            except ValueError:
                pass
            
            return False
    
    @classmethod
    def add_to_whitelist(cls, address: str) -> Tuple[bool, str]:
        """
        Add an address to the whitelist
        
        Args:
            address: IP address to whitelist
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            # Validate IP address
            try:
                ipaddress.ip_address(address)
            except ValueError:
                return False, f"Invalid IP address: {address}"
            
            if address in _whitelist:
                return False, f"Address {address} is already whitelisted"
            
            _whitelist.append(address)
            
            logger.info(f"Added {address} to whitelist")
            
            return True, f"Added {address} to whitelist"
    
    @classmethod
    def remove_from_whitelist(cls, address: str) -> Tuple[bool, str]:
        """
        Remove an address from the whitelist
        
        Args:
            address: IP address to remove from whitelist
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if address not in _whitelist:
                return False, f"Address {address} is not whitelisted"
            
            _whitelist.remove(address)
            
            logger.info(f"Removed {address} from whitelist")
            
            return True, f"Removed {address} from whitelist"
    
    @classmethod
    def is_whitelisted(cls, address: str) -> bool:
        """
        Check if an address is whitelisted
        
        Args:
            address: IP address to check
        
        Returns:
            True if whitelisted, False otherwise
        """
        with _netmon_lock:
            # Check exact match
            if address in _whitelist:
                return True
            
            # Check CIDR ranges
            try:
                ip = ipaddress.ip_address(address)
                for item in _whitelist:
                    if '/' in item:  # CIDR notation
                        try:
                            network = ipaddress.ip_network(item, strict=False)
                            if ip in network:
                                return True
                        except ValueError:
                            pass
            except ValueError:
                pass
            
            return False
    
    @classmethod
    def start_monitoring(cls) -> Tuple[bool, str]:
        """
        Start network monitoring
        
        Returns:
            (success, message)
        """
        global _netmon_thread, _netmon_thread_stop
        
        with _netmon_lock:
            # Check if monitoring is already enabled
            if _netmon_config['enabled']:
                return True, "Network monitoring is already enabled"
            
            # Enable monitoring
            _netmon_config['enabled'] = True
            _netmon_thread_stop = False
            
            # Start monitoring thread
            if _netmon_thread is None or not _netmon_thread.is_alive():
                _netmon_thread = threading.Thread(target=cls._monitoring_thread)
                _netmon_thread.daemon = True
                _netmon_thread.start()
            
            logger.info("Network monitoring started")
            
            return True, "Network monitoring started"
    
    @classmethod
    def stop_monitoring(cls) -> Tuple[bool, str]:
        """
        Stop network monitoring
        
        Returns:
            (success, message)
        """
        global _netmon_thread, _netmon_thread_stop
        
        with _netmon_lock:
            # Check if monitoring is already disabled
            if not _netmon_config['enabled']:
                return True, "Network monitoring is already disabled"
            
            # Disable monitoring
            _netmon_config['enabled'] = False
            _netmon_thread_stop = True
            
            logger.info("Network monitoring stopped")
            
            return True, "Network monitoring stopped"
    
    @classmethod
    def set_check_interval(cls, interval: int) -> Tuple[bool, str]:
        """
        Set check interval
        
        Args:
            interval: Check interval in seconds
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if interval < 1:
                return False, "Check interval must be at least 1 second"
            
            _netmon_config['check_interval'] = interval
            
            logger.info(f"Network monitoring check interval set to {interval} seconds")
            
            return True, f"Check interval set to {interval} seconds"
    
    @classmethod
    def set_max_rate(cls, rate: int) -> Tuple[bool, str]:
        """
        Set maximum connection rate
        
        Args:
            rate: Maximum connection rate per minute
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            if rate < 1:
                return False, "Maximum rate must be at least 1"
            
            _netmon_config['max_rate'] = rate
            
            logger.info(f"Network monitoring maximum rate set to {rate}")
            
            return True, f"Maximum rate set to {rate}"
    
    @classmethod
    def save_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Save network monitor database to file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            try:
                data = {
                    'config': _netmon_config,
                    'known_hosts': {addr: host.to_dict() for addr, host in _known_hosts.items()},
                    'blacklist': _blacklist,
                    'whitelist': _whitelist,
                    'connections': [conn.to_dict() for conn in _connection_history]
                }
                
                with open(db_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"Network monitor database saved to {db_file}"
            except Exception as e:
                logger.error(f"Error saving network monitor database: {e}")
                return False, str(e)
    
    @classmethod
    def load_database(cls, db_file: str) -> Tuple[bool, str]:
        """
        Load network monitor database from file
        
        Args:
            db_file: Database file path
        
        Returns:
            (success, message)
        """
        with _netmon_lock:
            try:
                if not os.path.exists(db_file):
                    return False, f"Database file {db_file} not found"
                
                with open(db_file, 'r') as f:
                    data = json.load(f)
                
                if 'config' in data:
                    _netmon_config.update(data['config'])
                
                if 'known_hosts' in data:
                    _known_hosts.clear()
                    for addr, host_data in data['known_hosts'].items():
                        _known_hosts[addr] = HostInfo.from_dict(host_data)
                
                if 'blacklist' in data:
                    _blacklist.clear()
                    _blacklist.extend(data['blacklist'])
                
                if 'whitelist' in data:
                    _whitelist.clear()
                    _whitelist.extend(data['whitelist'])
                
                if 'connections' in data:
                    _connection_history.clear()
                    for conn_data in data['connections']:
                        _connection_history.append(NetworkConnection.from_dict(conn_data))
                
                return True, "Network monitor database loaded"
            except Exception as e:
                logger.error(f"Error loading network monitor database: {e}")
                return False, str(e)
    
    @classmethod
    def _monitoring_thread(cls) -> None:
        """Monitoring thread function"""
        logger.info("Network monitoring thread started")
        
        while not _netmon_thread_stop:
            try:
                if _netmon_config['enabled']:
                    cls.update_connections()
            except Exception as e:
                logger.error(f"Error in network monitoring thread: {e}")
            
            # Sleep for check interval
            for _ in range(_netmon_config['check_interval']):
                if _netmon_thread_stop:
                    break
                time.sleep(1)
        
        logger.info("Network monitoring thread stopped")


def initialize() -> None:
    """Initialize network monitor system"""
    logger.info("Initializing network monitor system")
    
    # Create network monitor directory
    netmon_dir = os.path.join(os.path.expanduser('~'), '.kos', 'security')
    os.makedirs(netmon_dir, exist_ok=True)
    
    # Initialize whitelist with localhost
    if not _whitelist:
        _whitelist.append('127.0.0.1')
        _whitelist.append('::1')
    
    # Load database if it exists
    db_file = os.path.join(netmon_dir, 'network.json')
    if os.path.exists(db_file):
        NetworkMonitor.load_database(db_file)
    
    logger.info("Network monitor system initialized")


# Initialize on module load
initialize()

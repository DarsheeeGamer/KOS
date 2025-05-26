"""
KOS Network Subsystem

Provides comprehensive networking capabilities for KOS, including:
- Network interface management
- Virtual networking (bridges, VLANs)
- Firewall and packet filtering
- Service discovery and DNS
- Integration with KOS services and IPC
"""

import logging
import os
import threading
import time
import json
import socket
import ipaddress
from typing import Dict, List, Any, Optional, Tuple, Set

# Initialize logging
logger = logging.getLogger('KOS.network')

# Base directory for network configuration
NETWORK_DIR = '/tmp/kos/network'
os.makedirs(NETWORK_DIR, exist_ok=True)

# Configuration files
INTERFACES_CONFIG = os.path.join(NETWORK_DIR, 'interfaces.json')
FIREWALL_CONFIG = os.path.join(NETWORK_DIR, 'firewall.json')
ROUTES_CONFIG = os.path.join(NETWORK_DIR, 'routes.json')
DNS_CONFIG = os.path.join(NETWORK_DIR, 'dns.json')

# Lock for thread safety
_lock = threading.RLock()

# Network manager state
_initialized = False
_network_thread = None
_stop_event = threading.Event()

# Network state
_interfaces = {}
_virtual_interfaces = {}
_firewall_rules = []
_routes = []
_dns_servers = []
_dns_cache = {}

class NetworkInterfaceType:
    """Network interface types"""
    PHYSICAL = "physical"
    LOOPBACK = "loopback"
    BRIDGE = "bridge"
    VLAN = "vlan"
    TUN = "tun"
    TAP = "tap"

class FirewallAction:
    """Firewall rule actions"""
    ACCEPT = "accept"
    REJECT = "reject"
    DROP = "drop"
    LOG = "log"

class NetworkInterfaceState:
    """Network interface states"""
    UP = "up"
    DOWN = "down"
    UNKNOWN = "unknown"

def initialize():
    """Initialize the network subsystem"""
    global _initialized, _network_thread
    
    if _initialized:
        logger.warning("Network subsystem already initialized")
        return True
    
    logger.info("Initializing KOS network subsystem")
    
    # Create network directories
    os.makedirs(os.path.join(NETWORK_DIR, 'interfaces'), exist_ok=True)
    os.makedirs(os.path.join(NETWORK_DIR, 'firewall'), exist_ok=True)
    
    # Load configurations
    _load_interfaces()
    _load_firewall_rules()
    _load_routes()
    _load_dns_config()
    
    # Discover physical interfaces
    _discover_interfaces()
    
    # Start network thread
    _stop_event.clear()
    _network_thread = threading.Thread(
        target=_network_loop,
        daemon=True,
        name="KOSNetworkThread"
    )
    _network_thread.start()
    
    _initialized = True
    return True

def shutdown():
    """Shutdown the network subsystem"""
    global _initialized, _network_thread
    
    if not _initialized:
        logger.warning("Network subsystem not initialized")
        return True
    
    logger.info("Shutting down KOS network subsystem")
    
    # Stop network thread
    _stop_event.set()
    if _network_thread:
        _network_thread.join(timeout=10.0)
    
    # Save configurations
    _save_interfaces()
    _save_firewall_rules()
    _save_routes()
    _save_dns_config()
    
    _initialized = False
    return True

def _network_loop():
    """Main network management loop"""
    logger.info("Network management loop started")
    
    while not _stop_event.is_set():
        try:
            # Update interface states
            _update_interface_states()
            
            # Check DNS cache timeouts
            _clean_dns_cache()
            
            # Sleep until next iteration
            _stop_event.wait(5.0)  # Check every 5 seconds
        
        except Exception as e:
            logger.error(f"Error in network loop: {e}")
            time.sleep(5.0)
    
    logger.info("Network management loop stopped")

def _discover_interfaces():
    """Discover physical network interfaces"""
    with _lock:
        try:
            # Use socket to get host interfaces
            import netifaces
            
            for ifname in netifaces.interfaces():
                if ifname in _interfaces:
                    # Already tracked
                    continue
                
                # Get interface details
                addresses = netifaces.ifaddresses(ifname)
                
                # Skip interfaces with no IPv4 address
                if netifaces.AF_INET not in addresses:
                    continue
                
                ipv4_info = addresses[netifaces.AF_INET][0]
                ipv4_addr = ipv4_info.get('addr')
                ipv4_mask = ipv4_info.get('netmask')
                
                if not ipv4_addr or not ipv4_mask:
                    continue
                
                # Determine interface type
                interface_type = NetworkInterfaceType.PHYSICAL
                if ifname == 'lo' or ifname.startswith('lo'):
                    interface_type = NetworkInterfaceType.LOOPBACK
                elif ifname.startswith('br'):
                    interface_type = NetworkInterfaceType.BRIDGE
                elif ifname.startswith('vlan'):
                    interface_type = NetworkInterfaceType.VLAN
                elif ifname.startswith('tun'):
                    interface_type = NetworkInterfaceType.TUN
                elif ifname.startswith('tap'):
                    interface_type = NetworkInterfaceType.TAP
                
                # Create interface entry
                _interfaces[ifname] = {
                    'name': ifname,
                    'type': interface_type,
                    'ipv4_address': ipv4_addr,
                    'ipv4_netmask': ipv4_mask,
                    'state': NetworkInterfaceState.UP,
                    'mtu': 1500,  # Default MTU
                    'mac_address': _get_mac_address(ifname),
                    'virtual': False,
                    'managed': False,  # Not managed by KOS initially
                    'metrics': {
                        'rx_bytes': 0,
                        'tx_bytes': 0,
                        'rx_packets': 0,
                        'tx_packets': 0,
                        'rx_errors': 0,
                        'tx_errors': 0
                    }
                }
                
                logger.info(f"Discovered interface: {ifname} ({ipv4_addr})")
        
        except ImportError:
            logger.warning("netifaces module not available, interface discovery limited")
            
            # Fallback to socket-based detection
            hostname = socket.gethostname()
            try:
                ipv4_addr = socket.gethostbyname(hostname)
                
                # Create a default interface
                _interfaces['eth0'] = {
                    'name': 'eth0',
                    'type': NetworkInterfaceType.PHYSICAL,
                    'ipv4_address': ipv4_addr,
                    'ipv4_netmask': '255.255.255.0',  # Assume class C
                    'state': NetworkInterfaceState.UP,
                    'mtu': 1500,
                    'mac_address': '00:00:00:00:00:00',  # Unknown
                    'virtual': False,
                    'managed': False,
                    'metrics': {
                        'rx_bytes': 0,
                        'tx_bytes': 0,
                        'rx_packets': 0,
                        'tx_packets': 0,
                        'rx_errors': 0,
                        'tx_errors': 0
                    }
                }
                
                logger.info(f"Created default interface: eth0 ({ipv4_addr})")
            
            except socket.gaierror:
                logger.error("Failed to determine local IP address")

def _get_mac_address(interface):
    """Get MAC address for an interface"""
    try:
        import netifaces
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_LINK in addrs:
            return addrs[netifaces.AF_LINK][0].get('addr', '00:00:00:00:00:00')
    except:
        pass
    
    return '00:00:00:00:00:00'

def _update_interface_states():
    """Update the state of all interfaces"""
    with _lock:
        for ifname, interface in list(_interfaces.items()):
            if not interface['managed']:
                # Only update metrics for non-managed interfaces
                _update_interface_metrics(ifname)

def _update_interface_metrics(ifname):
    """Update metrics for an interface"""
    try:
        # Read metrics from /proc/net/dev
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()
        
        for line in lines:
            if ':' not in line:
                continue
            
            parts = line.split(':')
            if len(parts) != 2:
                continue
            
            if parts[0].strip() == ifname:
                values = parts[1].split()
                if len(values) >= 16:
                    with _lock:
                        if ifname in _interfaces:
                            _interfaces[ifname]['metrics'] = {
                                'rx_bytes': int(values[0]),
                                'rx_packets': int(values[1]),
                                'rx_errors': int(values[2]),
                                'tx_bytes': int(values[8]),
                                'tx_packets': int(values[9]),
                                'tx_errors': int(values[10])
                            }
                break
    
    except Exception as e:
        logger.error(f"Error updating interface metrics for {ifname}: {e}")

def _load_interfaces():
    """Load interface configuration"""
    with _lock:
        if os.path.exists(INTERFACES_CONFIG):
            try:
                with open(INTERFACES_CONFIG, 'r') as f:
                    loaded = json.load(f)
                    
                    if isinstance(loaded, dict):
                        for ifname, config in loaded.items():
                            _interfaces[ifname] = config
                
                logger.info(f"Loaded {len(_interfaces)} interface configurations")
            
            except Exception as e:
                logger.error(f"Error loading interface configuration: {e}")

def _save_interfaces():
    """Save interface configuration"""
    with _lock:
        try:
            with open(INTERFACES_CONFIG, 'w') as f:
                json.dump(_interfaces, f, indent=2)
            
            logger.info(f"Saved {len(_interfaces)} interface configurations")
        
        except Exception as e:
            logger.error(f"Error saving interface configuration: {e}")

def _load_firewall_rules():
    """Load firewall rules"""
    with _lock:
        if os.path.exists(FIREWALL_CONFIG):
            try:
                with open(FIREWALL_CONFIG, 'r') as f:
                    global _firewall_rules
                    _firewall_rules = json.load(f)
                
                logger.info(f"Loaded {len(_firewall_rules)} firewall rules")
            
            except Exception as e:
                logger.error(f"Error loading firewall configuration: {e}")

def _save_firewall_rules():
    """Save firewall rules"""
    with _lock:
        try:
            with open(FIREWALL_CONFIG, 'w') as f:
                json.dump(_firewall_rules, f, indent=2)
            
            logger.info(f"Saved {len(_firewall_rules)} firewall rules")
        
        except Exception as e:
            logger.error(f"Error saving firewall configuration: {e}")

def _load_routes():
    """Load routing table"""
    with _lock:
        if os.path.exists(ROUTES_CONFIG):
            try:
                with open(ROUTES_CONFIG, 'r') as f:
                    global _routes
                    _routes = json.load(f)
                
                logger.info(f"Loaded {len(_routes)} routes")
            
            except Exception as e:
                logger.error(f"Error loading routes configuration: {e}")

def _save_routes():
    """Save routing table"""
    with _lock:
        try:
            with open(ROUTES_CONFIG, 'w') as f:
                json.dump(_routes, f, indent=2)
            
            logger.info(f"Saved {len(_routes)} routes")
        
        except Exception as e:
            logger.error(f"Error saving routes configuration: {e}")

def _load_dns_config():
    """Load DNS configuration"""
    with _lock:
        if os.path.exists(DNS_CONFIG):
            try:
                with open(DNS_CONFIG, 'r') as f:
                    config = json.load(f)
                    
                    global _dns_servers, _dns_cache
                    _dns_servers = config.get('servers', [])
                    _dns_cache = config.get('cache', {})
                
                logger.info(f"Loaded DNS configuration with {len(_dns_servers)} servers")
            
            except Exception as e:
                logger.error(f"Error loading DNS configuration: {e}")

def _save_dns_config():
    """Save DNS configuration"""
    with _lock:
        try:
            config = {
                'servers': _dns_servers,
                'cache': _dns_cache
            }
            
            with open(DNS_CONFIG, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved DNS configuration")
        
        except Exception as e:
            logger.error(f"Error saving DNS configuration: {e}")

def _clean_dns_cache():
    """Clean expired DNS cache entries"""
    with _lock:
        now = time.time()
        expired = []
        
        for hostname, entry in _dns_cache.items():
            if entry['expires'] < now:
                expired.append(hostname)
        
        for hostname in expired:
            del _dns_cache[hostname]
        
        if expired:
            logger.debug(f"Cleaned {len(expired)} expired DNS cache entries")

# ============================================================================
# Public API for network management
# ============================================================================

def list_interfaces():
    """List all network interfaces"""
    with _lock:
        return list(_interfaces.values())

def get_interface(name):
    """Get interface by name"""
    with _lock:
        return _interfaces.get(name)

def create_interface(name, interface_type, ipv4_address=None, ipv4_netmask=None, **kwargs):
    """Create a new virtual interface"""
    with _lock:
        if name in _interfaces:
            logger.warning(f"Interface {name} already exists")
            return False
        
        # Create interface configuration
        interface = {
            'name': name,
            'type': interface_type,
            'ipv4_address': ipv4_address,
            'ipv4_netmask': ipv4_netmask,
            'state': NetworkInterfaceState.DOWN,
            'mtu': kwargs.get('mtu', 1500),
            'mac_address': kwargs.get('mac_address', '00:00:00:00:00:00'),
            'virtual': True,
            'managed': True,
            'metrics': {
                'rx_bytes': 0,
                'tx_bytes': 0,
                'rx_packets': 0,
                'tx_packets': 0,
                'rx_errors': 0,
                'tx_errors': 0
            }
        }
        
        # Add type-specific configuration
        if interface_type == NetworkInterfaceType.BRIDGE:
            interface['bridge_interfaces'] = kwargs.get('bridge_interfaces', [])
        elif interface_type == NetworkInterfaceType.VLAN:
            interface['vlan_id'] = kwargs.get('vlan_id')
            interface['parent_interface'] = kwargs.get('parent_interface')
        elif interface_type in (NetworkInterfaceType.TUN, NetworkInterfaceType.TAP):
            interface['owner'] = kwargs.get('owner')
            interface['group'] = kwargs.get('group')
            interface['persistent'] = kwargs.get('persistent', False)
        
        # Save the interface
        _interfaces[name] = interface
        _save_interfaces()
        
        logger.info(f"Created interface: {name} ({interface_type})")
        return True

def delete_interface(name):
    """Delete a virtual interface"""
    with _lock:
        if name not in _interfaces:
            logger.warning(f"Interface {name} does not exist")
            return False
        
        interface = _interfaces[name]
        if not interface['virtual']:
            logger.warning(f"Cannot delete physical interface {name}")
            return False
        
        # Check if interface is in use by bridges
        for ifname, iface in _interfaces.items():
            if iface['type'] == NetworkInterfaceType.BRIDGE:
                if name in iface.get('bridge_interfaces', []):
                    logger.warning(f"Interface {name} is used by bridge {ifname}")
                    return False
        
        # Delete the interface
        del _interfaces[name]
        _save_interfaces()
        
        logger.info(f"Deleted interface: {name}")
        return True

def set_interface_state(name, state):
    """Set interface state (up/down)"""
    with _lock:
        if name not in _interfaces:
            logger.warning(f"Interface {name} does not exist")
            return False
        
        interface = _interfaces[name]
        interface['state'] = state
        _save_interfaces()
        
        logger.info(f"Set interface {name} state to {state}")
        return True

def set_interface_address(name, ipv4_address, ipv4_netmask):
    """Set interface IP address"""
    with _lock:
        if name not in _interfaces:
            logger.warning(f"Interface {name} does not exist")
            return False
        
        # Validate IP address and netmask
        try:
            ipaddress.IPv4Address(ipv4_address)
            ipaddress.IPv4Address(ipv4_netmask)
        except ValueError as e:
            logger.error(f"Invalid IP address or netmask: {e}")
            return False
        
        interface = _interfaces[name]
        interface['ipv4_address'] = ipv4_address
        interface['ipv4_netmask'] = ipv4_netmask
        _save_interfaces()
        
        logger.info(f"Set interface {name} address to {ipv4_address}/{ipv4_netmask}")
        return True

def add_firewall_rule(rule):
    """Add a firewall rule"""
    with _lock:
        # Validate rule
        required_fields = ['action', 'protocol']
        for field in required_fields:
            if field not in rule:
                logger.error(f"Firewall rule missing required field: {field}")
                return False
        
        # Add the rule
        _firewall_rules.append(rule)
        _save_firewall_rules()
        
        logger.info(f"Added firewall rule: {rule['action']} {rule.get('protocol')} " +
                   f"{rule.get('source', 'any')} -> {rule.get('destination', 'any')}")
        return True

def remove_firewall_rule(index):
    """Remove a firewall rule by index"""
    with _lock:
        if index < 0 or index >= len(_firewall_rules):
            logger.warning(f"Invalid firewall rule index: {index}")
            return False
        
        rule = _firewall_rules.pop(index)
        _save_firewall_rules()
        
        logger.info(f"Removed firewall rule: {rule['action']} {rule.get('protocol')} " +
                   f"{rule.get('source', 'any')} -> {rule.get('destination', 'any')}")
        return True

def list_firewall_rules():
    """List all firewall rules"""
    with _lock:
        return _firewall_rules.copy()

def add_route(destination, gateway=None, interface=None, metric=0):
    """Add a route to the routing table"""
    with _lock:
        # Validate destination network
        try:
            network = ipaddress.IPv4Network(destination)
            destination = str(network)
        except ValueError as e:
            logger.error(f"Invalid destination network: {e}")
            return False
        
        # Validate gateway if provided
        if gateway:
            try:
                ipaddress.IPv4Address(gateway)
            except ValueError as e:
                logger.error(f"Invalid gateway address: {e}")
                return False
        
        # Validate interface if provided
        if interface and interface not in _interfaces:
            logger.warning(f"Interface {interface} does not exist")
            return False
        
        # Create the route
        route = {
            'destination': destination,
            'gateway': gateway,
            'interface': interface,
            'metric': metric
        }
        
        # Check for duplicate route
        for i, existing in enumerate(_routes):
            if existing['destination'] == destination:
                # Replace existing route
                _routes[i] = route
                _save_routes()
                
                logger.info(f"Updated route to {destination} via " +
                           f"{gateway or 'direct'} (metric: {metric})")
                return True
        
        # Add new route
        _routes.append(route)
        _routes.sort(key=lambda r: r['metric'])
        _save_routes()
        
        logger.info(f"Added route to {destination} via " +
                   f"{gateway or 'direct'} (metric: {metric})")
        return True

def remove_route(destination):
    """Remove a route from the routing table"""
    with _lock:
        # Find the route
        for i, route in enumerate(_routes):
            if route['destination'] == destination:
                _routes.pop(i)
                _save_routes()
                
                logger.info(f"Removed route to {destination}")
                return True
        
        logger.warning(f"Route to {destination} not found")
        return False

def list_routes():
    """List all routes"""
    with _lock:
        return _routes.copy()

def add_dns_server(server):
    """Add a DNS server"""
    with _lock:
        # Validate server address
        try:
            ipaddress.IPv4Address(server)
        except ValueError as e:
            logger.error(f"Invalid DNS server address: {e}")
            return False
        
        if server not in _dns_servers:
            _dns_servers.append(server)
            _save_dns_config()
            
            logger.info(f"Added DNS server: {server}")
            return True
        
        return False

def remove_dns_server(server):
    """Remove a DNS server"""
    with _lock:
        if server in _dns_servers:
            _dns_servers.remove(server)
            _save_dns_config()
            
            logger.info(f"Removed DNS server: {server}")
            return True
        
        logger.warning(f"DNS server {server} not found")
        return False

def list_dns_servers():
    """List all DNS servers"""
    with _lock:
        return _dns_servers.copy()

def resolve_hostname(hostname, use_cache=True):
    """Resolve a hostname to an IP address"""
    with _lock:
        # Check cache
        if use_cache and hostname in _dns_cache:
            entry = _dns_cache[hostname]
            if entry['expires'] > time.time():
                return entry['addresses']
            else:
                # Expired entry
                del _dns_cache[hostname]
        
        # Resolve using system DNS
        try:
            addresses = socket.gethostbyname_ex(hostname)[2]
            
            # Cache the result
            if use_cache:
                _dns_cache[hostname] = {
                    'addresses': addresses,
                    'expires': time.time() + 300  # 5 minute TTL
                }
            
            return addresses
        
        except socket.gaierror:
            logger.warning(f"Failed to resolve hostname: {hostname}")
            return []

# ============================================================================
# Integration with service management
# ============================================================================

def register_network_service(service_name, port, protocol='tcp', description=None):
    """Register a network service for service discovery"""
    service_dir = os.path.join(NETWORK_DIR, 'services')
    os.makedirs(service_dir, exist_ok=True)
    
    service_file = os.path.join(service_dir, f"{service_name}.json")
    
    # Get service details from service manager if available
    from ..service import get_service_status
    service_info = get_service_status(service_name) or {}
    
    service_data = {
        'name': service_name,
        'port': port,
        'protocol': protocol,
        'description': description or service_info.get('description', ''),
        'pid': service_info.get('pid'),
        'state': service_info.get('state', 'UNKNOWN'),
        'registered_at': time.time()
    }
    
    try:
        with open(service_file, 'w') as f:
            json.dump(service_data, f, indent=2)
        
        logger.info(f"Registered network service: {service_name} ({protocol}/{port})")
        return True
    
    except Exception as e:
        logger.error(f"Error registering network service: {e}")
        return False

def unregister_network_service(service_name):
    """Unregister a network service"""
    service_dir = os.path.join(NETWORK_DIR, 'services')
    service_file = os.path.join(service_dir, f"{service_name}.json")
    
    if os.path.exists(service_file):
        try:
            os.remove(service_file)
            logger.info(f"Unregistered network service: {service_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error unregistering network service: {e}")
    
    return False

def list_network_services():
    """List all registered network services"""
    service_dir = os.path.join(NETWORK_DIR, 'services')
    os.makedirs(service_dir, exist_ok=True)
    
    services = []
    
    for filename in os.listdir(service_dir):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(service_dir, filename), 'r') as f:
                    service = json.load(f)
                    services.append(service)
            
            except Exception as e:
                logger.error(f"Error loading service file {filename}: {e}")
    
    return services

# ============================================================================
# Integration with IPC and monitoring
# ============================================================================

def get_network_metrics():
    """Get network metrics for monitoring"""
    with _lock:
        metrics = {
            'interfaces': {},
            'services': list_network_services(),
            'firewall': {
                'rules': len(_firewall_rules),
                'active': True  # Assuming firewall is always active
            },
            'dns': {
                'servers': _dns_servers,
                'cache_entries': len(_dns_cache)
            }
        }
        
        # Add interface metrics
        for ifname, interface in _interfaces.items():
            metrics['interfaces'][ifname] = {
                'state': interface['state'],
                'ipv4_address': interface['ipv4_address'],
                'type': interface['type'],
                'metrics': interface['metrics']
            }
        
        return metrics

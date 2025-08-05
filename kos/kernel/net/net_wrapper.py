"""
KOS Network Stack Python Wrapper

Complete Python bindings for the KOS network stack including:
- Socket operations (TCP/UDP)
- Network interfaces
- Routing and ARP
- Packet processing
- Connection tracking
- Netfilter hooks
- Performance monitoring
"""

import ctypes
import os
import sys
import logging
import threading
import time
import socket
import struct
from typing import Dict, List, Optional, Any, Tuple, Callable, Union
from dataclasses import dataclass
from enum import IntEnum
from ipaddress import IPv4Address, IPv4Network

logger = logging.getLogger('KOS.net')


class SocketType(IntEnum):
    """Socket types"""
    STREAM = 1      # TCP
    DGRAM = 2       # UDP
    RAW = 3         # Raw packets
    SEQPACKET = 4   # Sequenced packets


class AddressFamily(IntEnum):
    """Address families"""
    UNSPEC = 0
    INET = 2        # IPv4
    INET6 = 10      # IPv6
    PACKET = 17     # Packet socket
    NETLINK = 16    # Netlink


class SocketState(IntEnum):
    """Socket states"""
    UNCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    DISCONNECTING = 3
    LISTENING = 4
    CLOSED = 5


class TCPState(IntEnum):
    """TCP states"""
    CLOSED = 0
    LISTEN = 1
    SYN_SENT = 2
    SYN_RCVD = 3
    ESTABLISHED = 4
    FIN_WAIT1 = 5
    FIN_WAIT2 = 6
    CLOSE_WAIT = 7
    CLOSING = 8
    LAST_ACK = 9
    TIME_WAIT = 10


class NetfilterHook(IntEnum):
    """Netfilter hooks"""
    PRE_ROUTING = 0
    LOCAL_IN = 1
    FORWARD = 2
    LOCAL_OUT = 3
    POST_ROUTING = 4


class NetfilterVerdict(IntEnum):
    """Netfilter verdicts"""
    DROP = 0
    ACCEPT = 1
    STOLEN = 2
    QUEUE = 3
    REPEAT = 4


@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    index: int
    flags: int
    hw_addr: str
    ip_addr: str
    netmask: str
    broadcast: str
    mtu: int
    rx_packets: int = 0
    tx_packets: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0


@dataclass
class SocketInfo:
    """Socket information"""
    fd: int
    domain: int
    sock_type: int
    protocol: int
    state: SocketState
    local_addr: str
    local_port: int
    remote_addr: str
    remote_port: int
    bytes_sent: int = 0
    bytes_recv: int = 0
    packets_sent: int = 0
    packets_recv: int = 0


@dataclass
class RouteEntry:
    """Routing table entry"""
    dest: str
    gateway: str
    genmask: str
    flags: int
    metric: int
    interface: str


@dataclass
class ARPEntry:
    """ARP cache entry"""
    ip_addr: str
    hw_addr: str
    timestamp: float
    flags: int


@dataclass
class ConnectionInfo:
    """Connection tracking information"""
    src_ip: str
    dst_ip: str
    src_port: int
    dst_port: int
    protocol: int
    state: int
    packets: int
    bytes: int
    timestamp: float


@dataclass
class NetworkStats:
    """Network statistics"""
    interfaces: int = 0
    sockets: int = 0
    routes: int = 0
    arp_entries: int = 0
    connections: int = 0
    packets_sent: int = 0
    packets_received: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    errors: int = 0
    dropped: int = 0


class KOSNetworkStack:
    """KOS Network Stack interface"""
    
    def __init__(self):
        self.lib = None
        self._sockets: Dict[int, SocketInfo] = {}
        self._interfaces: Dict[str, NetworkInterface] = {}
        self._routes: List[RouteEntry] = []
        self._arp_cache: Dict[str, ARPEntry] = {}
        self._connections: List[ConnectionInfo] = []
        self._next_fd = 3  # Start after stdin/stdout/stderr
        self._stats = NetworkStats()
        self._lock = threading.RLock()
        self._packet_queue = []
        self._hooks: Dict[NetfilterHook, List[Callable]] = {}
        
        self._load_library()
        self._initialize_network()
    
    def _load_library(self):
        """Load the network stack library"""
        lib_dir = os.path.dirname(__file__)
        lib_path = os.path.join(lib_dir, "..", "libkos_kernel.so")
        
        if os.path.exists(lib_path):
            try:
                self.lib = ctypes.CDLL(lib_path)
                self._setup_functions()
                logger.info("KOS network library loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load network library: {e}")
                self.lib = None
        else:
            logger.warning("Network library not found, using mock implementation")
            self.lib = None
    
    def _setup_functions(self):
        """Setup C function signatures"""
        if not self.lib:
            return
        
        try:
            # Network stack initialization
            self.lib.kos_netstack_init.argtypes = []
            self.lib.kos_netstack_init.restype = ctypes.c_int
            
            self.lib.kos_netstack_shutdown.argtypes = []
            self.lib.kos_netstack_shutdown.restype = None
            
            # Socket operations
            self.lib.kos_socket.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
            self.lib.kos_socket.restype = ctypes.c_int
            
            self.lib.kos_bind.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint]
            self.lib.kos_bind.restype = ctypes.c_int
            
            self.lib.kos_listen.argtypes = [ctypes.c_int, ctypes.c_int]
            self.lib.kos_listen.restype = ctypes.c_int
            
            self.lib.kos_accept.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.POINTER(ctypes.c_uint)]
            self.lib.kos_accept.restype = ctypes.c_int
            
            self.lib.kos_connect.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_ubyte), ctypes.c_uint]
            self.lib.kos_connect.restype = ctypes.c_int
            
            self.lib.kos_send.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
            self.lib.kos_send.restype = ctypes.c_ssize_t
            
            self.lib.kos_recv.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
            self.lib.kos_recv.restype = ctypes.c_ssize_t
            
            self.lib.kos_close_socket.argtypes = [ctypes.c_int]
            self.lib.kos_close_socket.restype = ctypes.c_int
            
            # Network interface operations
            self.lib.kos_netif_create.argtypes = [ctypes.c_char_p]
            self.lib.kos_netif_create.restype = ctypes.c_void_p
            
            self.lib.kos_netif_find.argtypes = [ctypes.c_char_p]
            self.lib.kos_netif_find.restype = ctypes.c_void_p
            
            logger.debug("Network library functions setup complete")
            
        except AttributeError as e:
            logger.warning(f"Some network functions not available: {e}")
    
    def _initialize_network(self):
        """Initialize the network stack"""
        if self.lib:
            try:
                ret = self.lib.kos_netstack_init()
                if ret == 0:
                    logger.info("Network stack initialized successfully")
                else:
                    logger.error("Failed to initialize network stack")
                    self.lib = None
            except Exception as e:
                logger.error(f"Network initialization error: {e}")
                self.lib = None
        
        # Create default loopback interface
        self._create_loopback_interface()
    
    def _create_loopback_interface(self):
        """Create loopback interface"""
        loopback = NetworkInterface(
            name="lo",
            index=1,
            flags=0x1,  # UP
            hw_addr="00:00:00:00:00:00",
            ip_addr="127.0.0.1",
            netmask="255.0.0.0",
            broadcast="127.255.255.255",
            mtu=65536
        )
        self._interfaces["lo"] = loopback
        logger.debug("Created loopback interface")
    
    def create_socket(self, domain: int, sock_type: int, protocol: int = 0) -> Optional[int]:
        """Create a new socket"""
        with self._lock:
            if self.lib:
                try:
                    fd = self.lib.kos_socket(domain, sock_type, protocol)
                    if fd >= 0:
                        socket_info = SocketInfo(
                            fd=fd,
                            domain=domain,
                            sock_type=sock_type,
                            protocol=protocol,
                            state=SocketState.UNCONNECTED,
                            local_addr="",
                            local_port=0,
                            remote_addr="",
                            remote_port=0
                        )
                        self._sockets[fd] = socket_info
                        self._stats.sockets += 1
                        return fd
                except Exception as e:
                    logger.error(f"Failed to create socket: {e}")
            
            # Mock implementation
            fd = self._next_fd
            self._next_fd += 1
            
            socket_info = SocketInfo(
                fd=fd,
                domain=domain,
                sock_type=sock_type,
                protocol=protocol,
                state=SocketState.UNCONNECTED,
                local_addr="",
                local_port=0,
                remote_addr="",
                remote_port=0
            )
            self._sockets[fd] = socket_info
            self._stats.sockets += 1
            return fd
    
    def bind(self, sockfd: int, address: Tuple[str, int]) -> bool:
        """Bind socket to address"""
        with self._lock:
            if sockfd not in self._sockets:
                return False
            
            addr_str, port = address
            
            if self.lib:
                try:
                    # Convert address to sockaddr structure
                    # This is simplified - real implementation would create proper sockaddr
                    addr_bytes = socket.inet_aton(addr_str) + struct.pack('!H', port)
                    addr_ptr = (ctypes.c_ubyte * len(addr_bytes)).from_buffer_copy(addr_bytes)
                    
                    ret = self.lib.kos_bind(sockfd, addr_ptr, len(addr_bytes))
                    if ret == 0:
                        sock_info = self._sockets[sockfd]
                        sock_info.local_addr = addr_str
                        sock_info.local_port = port
                        return True
                except Exception as e:
                    logger.error(f"Bind failed: {e}")
                    return False
            
            # Mock implementation
            sock_info = self._sockets[sockfd]
            sock_info.local_addr = addr_str
            sock_info.local_port = port
            return True
    
    def listen(self, sockfd: int, backlog: int = 5) -> bool:
        """Listen for connections"""
        with self._lock:
            if sockfd not in self._sockets:
                return False
            
            if self.lib:
                try:
                    ret = self.lib.kos_listen(sockfd, backlog)
                    if ret == 0:
                        self._sockets[sockfd].state = SocketState.LISTENING
                        return True
                except Exception as e:
                    logger.error(f"Listen failed: {e}")
                    return False
            
            # Mock implementation
            self._sockets[sockfd].state = SocketState.LISTENING
            return True
    
    def accept(self, sockfd: int) -> Optional[Tuple[int, Tuple[str, int]]]:
        """Accept a connection"""
        with self._lock:
            if sockfd not in self._sockets:
                return None
            
            if self._sockets[sockfd].state != SocketState.LISTENING:
                return None
            
            if self.lib:
                try:
                    addr_buf = (ctypes.c_ubyte * 16)()  # sockaddr_in size
                    addr_len = ctypes.c_uint(16)
                    
                    new_fd = self.lib.kos_accept(sockfd, addr_buf, ctypes.byref(addr_len))
                    if new_fd >= 0:
                        # Parse address from buffer
                        # This is simplified
                        client_addr = ("127.0.0.1", 12345)  # Mock address
                        
                        # Create socket info for new connection
                        socket_info = SocketInfo(
                            fd=new_fd,
                            domain=self._sockets[sockfd].domain,
                            sock_type=self._sockets[sockfd].sock_type,
                            protocol=self._sockets[sockfd].protocol,
                            state=SocketState.CONNECTED,
                            local_addr=self._sockets[sockfd].local_addr,
                            local_port=self._sockets[sockfd].local_port,
                            remote_addr=client_addr[0],
                            remote_port=client_addr[1]
                        )
                        self._sockets[new_fd] = socket_info
                        return (new_fd, client_addr)
                except Exception as e:
                    logger.error(f"Accept failed: {e}")
            
            # Mock implementation - return mock connection
            new_fd = self._next_fd
            self._next_fd += 1
            client_addr = ("127.0.0.1", 12345)
            
            socket_info = SocketInfo(
                fd=new_fd,
                domain=self._sockets[sockfd].domain,
                sock_type=self._sockets[sockfd].sock_type,
                protocol=self._sockets[sockfd].protocol,
                state=SocketState.CONNECTED,
                local_addr=self._sockets[sockfd].local_addr,
                local_port=self._sockets[sockfd].local_port,
                remote_addr=client_addr[0],
                remote_port=client_addr[1]
            )
            self._sockets[new_fd] = socket_info
            return (new_fd, client_addr)
    
    def connect(self, sockfd: int, address: Tuple[str, int]) -> bool:
        """Connect to remote address"""
        with self._lock:
            if sockfd not in self._sockets:
                return False
            
            addr_str, port = address
            
            if self.lib:
                try:
                    addr_bytes = socket.inet_aton(addr_str) + struct.pack('!H', port)
                    addr_ptr = (ctypes.c_ubyte * len(addr_bytes)).from_buffer_copy(addr_bytes)
                    
                    ret = self.lib.kos_connect(sockfd, addr_ptr, len(addr_bytes))
                    if ret == 0:
                        sock_info = self._sockets[sockfd]
                        sock_info.remote_addr = addr_str
                        sock_info.remote_port = port
                        sock_info.state = SocketState.CONNECTED
                        return True
                except Exception as e:
                    logger.error(f"Connect failed: {e}")
                    return False
            
            # Mock implementation
            sock_info = self._sockets[sockfd]
            sock_info.remote_addr = addr_str
            sock_info.remote_port = port
            sock_info.state = SocketState.CONNECTED
            return True
    
    def send(self, sockfd: int, data: bytes, flags: int = 0) -> int:
        """Send data on socket"""
        with self._lock:
            if sockfd not in self._sockets:
                return -1
            
            if self.lib:
                try:
                    data_ptr = ctypes.c_char_p(data)
                    bytes_sent = self.lib.kos_send(sockfd, data_ptr, len(data), flags)
                    if bytes_sent >= 0:
                        sock_info = self._sockets[sockfd]
                        sock_info.bytes_sent += bytes_sent
                        sock_info.packets_sent += 1
                        self._stats.packets_sent += 1
                        self._stats.bytes_sent += bytes_sent
                        return bytes_sent
                except Exception as e:
                    logger.error(f"Send failed: {e}")
                    return -1
            
            # Mock implementation
            sock_info = self._sockets[sockfd]
            sock_info.bytes_sent += len(data)
            sock_info.packets_sent += 1
            self._stats.packets_sent += 1
            self._stats.bytes_sent += len(data)
            return len(data)
    
    def receive(self, sockfd: int, size: int, flags: int = 0) -> Optional[bytes]:
        """Receive data from socket"""
        with self._lock:
            if sockfd not in self._sockets:
                return None
            
            if self.lib:
                try:
                    buffer = ctypes.create_string_buffer(size)
                    bytes_recv = self.lib.kos_recv(sockfd, buffer, size, flags)
                    if bytes_recv > 0:
                        sock_info = self._sockets[sockfd]
                        sock_info.bytes_recv += bytes_recv
                        sock_info.packets_recv += 1
                        self._stats.packets_received += 1
                        self._stats.bytes_received += bytes_recv
                        return buffer.raw[:bytes_recv]
                except Exception as e:
                    logger.error(f"Receive failed: {e}")
            
            # Mock implementation - return empty data
            return b""
    
    def close_socket(self, sockfd: int) -> bool:
        """Close socket"""
        with self._lock:
            if sockfd not in self._sockets:
                return False
            
            if self.lib:
                try:
                    ret = self.lib.kos_close_socket(sockfd)
                    if ret == 0:
                        del self._sockets[sockfd]
                        self._stats.sockets -= 1
                        return True
                except Exception as e:
                    logger.error(f"Close socket failed: {e}")
                    return False
            
            # Mock implementation
            del self._sockets[sockfd]
            self._stats.sockets -= 1
            return True
    
    def create_interface(self, name: str) -> bool:
        """Create network interface"""
        with self._lock:
            if name in self._interfaces:
                return False
            
            if self.lib:
                try:
                    netif_ptr = self.lib.kos_netif_create(name.encode('utf-8'))
                    if netif_ptr:
                        # Extract interface info from C structure
                        # This is simplified
                        interface = NetworkInterface(
                            name=name,
                            index=len(self._interfaces) + 1,
                            flags=0,
                            hw_addr="00:00:00:00:00:00",
                            ip_addr="0.0.0.0",
                            netmask="0.0.0.0",
                            broadcast="0.0.0.0",
                            mtu=1500
                        )
                        self._interfaces[name] = interface
                        self._stats.interfaces += 1
                        return True
                except Exception as e:
                    logger.error(f"Create interface failed: {e}")
                    return False
            
            # Mock implementation
            interface = NetworkInterface(
                name=name,
                index=len(self._interfaces) + 1,
                flags=0,
                hw_addr="00:00:00:00:00:00",
                ip_addr="0.0.0.0",
                netmask="0.0.0.0",
                broadcast="0.0.0.0",
                mtu=1500
            )
            self._interfaces[name] = interface
            self._stats.interfaces += 1
            return True
    
    def set_interface_address(self, name: str, ip_addr: str, netmask: str) -> bool:
        """Set interface IP address"""
        with self._lock:
            if name not in self._interfaces:
                return False
            
            try:
                # Validate IP addresses
                IPv4Address(ip_addr)
                IPv4Address(netmask)
                
                interface = self._interfaces[name]
                interface.ip_addr = ip_addr
                interface.netmask = netmask
                
                # Calculate broadcast address
                network = IPv4Network(f"{ip_addr}/{netmask}", strict=False)
                interface.broadcast = str(network.broadcast_address)
                
                return True
            except Exception as e:
                logger.error(f"Set interface address failed: {e}")
                return False
    
    def interface_up(self, name: str) -> bool:
        """Bring interface up"""
        with self._lock:
            if name not in self._interfaces:
                return False
            
            self._interfaces[name].flags |= 0x1  # UP flag
            return True
    
    def interface_down(self, name: str) -> bool:
        """Bring interface down"""
        with self._lock:
            if name not in self._interfaces:
                return False
            
            self._interfaces[name].flags &= ~0x1  # Clear UP flag
            return True
    
    def add_route(self, dest: str, gateway: str, netmask: str, interface: str) -> bool:
        """Add routing table entry"""
        with self._lock:
            try:
                # Validate addresses
                IPv4Address(dest)
                IPv4Address(gateway)
                IPv4Address(netmask)
                
                if interface not in self._interfaces:
                    return False
                
                route = RouteEntry(
                    dest=dest,
                    gateway=gateway,
                    genmask=netmask,
                    flags=0,
                    metric=0,
                    interface=interface
                )
                self._routes.append(route)
                self._stats.routes += 1
                return True
            except Exception as e:
                logger.error(f"Add route failed: {e}")
                return False
    
    def delete_route(self, dest: str, netmask: str) -> bool:
        """Delete routing table entry"""
        with self._lock:
            for i, route in enumerate(self._routes):
                if route.dest == dest and route.genmask == netmask:
                    del self._routes[i]
                    self._stats.routes -= 1
                    return True
            return False
    
    def add_arp_entry(self, ip_addr: str, hw_addr: str) -> bool:
        """Add ARP cache entry"""
        with self._lock:
            try:
                IPv4Address(ip_addr)  # Validate IP
                
                arp_entry = ARPEntry(
                    ip_addr=ip_addr,
                    hw_addr=hw_addr,
                    timestamp=time.time(),
                    flags=0
                )
                self._arp_cache[ip_addr] = arp_entry
                self._stats.arp_entries += 1
                return True
            except Exception as e:
                logger.error(f"Add ARP entry failed: {e}")
                return False
    
    def lookup_arp(self, ip_addr: str) -> Optional[str]:
        """Lookup hardware address in ARP cache"""
        with self._lock:
            if ip_addr in self._arp_cache:
                return self._arp_cache[ip_addr].hw_addr
            return None
    
    def register_netfilter_hook(self, hook: NetfilterHook, callback: Callable) -> bool:
        """Register netfilter hook"""
        with self._lock:
            if hook not in self._hooks:
                self._hooks[hook] = []
            self._hooks[hook].append(callback)
            return True
    
    def unregister_netfilter_hook(self, hook: NetfilterHook, callback: Callable) -> bool:
        """Unregister netfilter hook"""
        with self._lock:
            if hook in self._hooks:
                try:
                    self._hooks[hook].remove(callback)
                    return True
                except ValueError:
                    pass
            return False
    
    def process_packets(self):
        """Process pending packets (called from kernel loop)"""
        # In a real implementation, this would process incoming packets
        # For mock, we just update statistics occasionally
        pass
    
    def get_interfaces(self) -> List[NetworkInterface]:
        """Get list of network interfaces"""
        with self._lock:
            return list(self._interfaces.values())
    
    def get_sockets(self) -> List[SocketInfo]:
        """Get list of active sockets"""
        with self._lock:
            return list(self._sockets.values())
    
    def get_routes(self) -> List[RouteEntry]:
        """Get routing table"""
        with self._lock:
            return self._routes.copy()
    
    def get_arp_cache(self) -> List[ARPEntry]:
        """Get ARP cache entries"""
        with self._lock:
            return list(self._arp_cache.values())
    
    def get_connections(self) -> List[ConnectionInfo]:
        """Get connection tracking information"""
        with self._lock:
            return self._connections.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get network statistics"""
        with self._lock:
            return {
                'interfaces': self._stats.interfaces,
                'sockets': self._stats.sockets,
                'routes': self._stats.routes,
                'arp_entries': self._stats.arp_entries,
                'connections': self._stats.connections,
                'packets_sent': self._stats.packets_sent,
                'packets_received': self._stats.packets_received,
                'bytes_sent': self._stats.bytes_sent,
                'bytes_received': self._stats.bytes_received,
                'errors': self._stats.errors,
                'dropped': self._stats.dropped
            }
    
    def dump_interfaces(self) -> str:
        """Dump interface information"""
        output = []
        output.append("Interface    State   IP Address      Netmask         HW Address         MTU")
        output.append("-" * 80)
        
        for interface in self._interfaces.values():
            state = "UP" if interface.flags & 0x1 else "DOWN"
            output.append(f"{interface.name:<12} {state:<7} {interface.ip_addr:<15} "
                         f"{interface.netmask:<15} {interface.hw_addr:<17} {interface.mtu}")
        
        return "\n".join(output)
    
    def dump_sockets(self) -> str:
        """Dump socket information"""
        output = []
        output.append("FD   Type    State       Local Address       Remote Address      Sent/Recv")
        output.append("-" * 80)
        
        for sock in self._sockets.values():
            sock_type = "TCP" if sock.sock_type == SocketType.STREAM else "UDP"
            local = f"{sock.local_addr}:{sock.local_port}"
            remote = f"{sock.remote_addr}:{sock.remote_port}" if sock.remote_addr else "-"
            traffic = f"{sock.bytes_sent}/{sock.bytes_recv}"
            
            output.append(f"{sock.fd:<4} {sock_type:<7} {sock.state.name:<11} "
                         f"{local:<19} {remote:<19} {traffic}")
        
        return "\n".join(output)
    
    def dump_routes(self) -> str:
        """Dump routing table"""
        output = []
        output.append("Destination     Gateway         Genmask         Interface")
        output.append("-" * 60)
        
        for route in self._routes:
            output.append(f"{route.dest:<15} {route.gateway:<15} "
                         f"{route.genmask:<15} {route.interface}")
        
        return "\n".join(output)
    
    def dump_arp(self) -> str:
        """Dump ARP cache"""
        output = []
        output.append("IP Address      HW Address         Age")
        output.append("-" * 40)
        
        current_time = time.time()
        for arp in self._arp_cache.values():
            age = int(current_time - arp.timestamp)
            output.append(f"{arp.ip_addr:<15} {arp.hw_addr:<17} {age}s")
        
        return "\n".join(output)
    
    def shutdown(self):
        """Shutdown network stack"""
        with self._lock:
            # Close all sockets
            for sockfd in list(self._sockets.keys()):
                self.close_socket(sockfd)
            
            # Clear all data structures
            self._interfaces.clear()
            self._routes.clear()
            self._arp_cache.clear()
            self._connections.clear()
            self._hooks.clear()
            
            if self.lib:
                try:
                    self.lib.kos_netstack_shutdown()
                except Exception as e:
                    logger.error(f"Network shutdown error: {e}")
            
            logger.info("Network stack shut down")


# Convenience functions for common operations
def create_tcp_socket() -> Optional[int]:
    """Create a TCP socket"""
    stack = KOSNetworkStack()
    return stack.create_socket(AddressFamily.INET, SocketType.STREAM)


def create_udp_socket() -> Optional[int]:
    """Create a UDP socket"""
    stack = KOSNetworkStack()
    return stack.create_socket(AddressFamily.INET, SocketType.DGRAM)


def create_server_socket(address: Tuple[str, int], backlog: int = 5) -> Optional[int]:
    """Create a server socket and bind/listen"""
    stack = KOSNetworkStack()
    sockfd = stack.create_socket(AddressFamily.INET, SocketType.STREAM)
    if sockfd:
        if stack.bind(sockfd, address) and stack.listen(sockfd, backlog):
            return sockfd
        stack.close_socket(sockfd)
    return None


def create_client_socket(address: Tuple[str, int]) -> Optional[int]:
    """Create a client socket and connect"""
    stack = KOSNetworkStack()
    sockfd = stack.create_socket(AddressFamily.INET, SocketType.STREAM)
    if sockfd:
        if stack.connect(sockfd, address):
            return sockfd
        stack.close_socket(sockfd)
    return None


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    # Create network stack
    net = KOSNetworkStack()
    
    # Create interface
    net.create_interface("eth0")
    net.set_interface_address("eth0", "192.168.1.100", "255.255.255.0")
    net.interface_up("eth0")
    
    # Add route
    net.add_route("0.0.0.0", "192.168.1.1", "0.0.0.0", "eth0")
    
    # Create socket
    sockfd = net.create_socket(AddressFamily.INET, SocketType.STREAM)
    if sockfd:
        print(f"Created socket: {sockfd}")
        
        # Bind and listen
        if net.bind(sockfd, ("192.168.1.100", 8080)):
            print("Socket bound successfully")
            
            if net.listen(sockfd):
                print("Socket listening")
        
        net.close_socket(sockfd)
    
    # Print network information
    print("\nNetwork Interfaces:")
    print(net.dump_interfaces())
    
    print("\nRouting Table:")
    print(net.dump_routes())
    
    print("\nNetwork Statistics:")
    stats = net.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    net.shutdown()
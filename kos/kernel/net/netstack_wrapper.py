#!/usr/bin/env python3
"""
KOS Network Stack Python Wrapper
Provides Python bindings for the KOS network stack
"""

import ctypes
import sys
import os
from ctypes import (
    Structure, POINTER, c_int, c_uint32, c_uint16, c_uint8, c_size_t,
    c_char_p, c_void_p, c_bool, c_uint64, byref, create_string_buffer
)

# Load the network stack library
try:
    # Try to load from current directory first
    lib_path = os.path.join(os.path.dirname(__file__), 'libkos_netstack.so')
    if os.path.exists(lib_path):
        netstack = ctypes.CDLL(lib_path)
    else:
        # Try system library path
        netstack = ctypes.CDLL('libkos_netstack.so')
except OSError as e:
    print(f"Failed to load KOS network stack library: {e}")
    print("Make sure to build the library first: make")
    sys.exit(1)

# Constants
KOS_AF_INET = 2
KOS_SOCK_STREAM = 1
KOS_SOCK_DGRAM = 2
KOS_SOL_SOCKET = 1
KOS_SO_REUSEADDR = 2
KOS_SO_KEEPALIVE = 9

# Socket states
KOS_SS_UNCONNECTED = 0
KOS_SS_CONNECTING = 1
KOS_SS_CONNECTED = 2
KOS_SS_DISCONNECTING = 3
KOS_SS_LISTENING = 4
KOS_SS_CLOSED = 5

# TCP states
KOS_TCP_CLOSED = 0
KOS_TCP_LISTEN = 1
KOS_TCP_SYN_SENT = 2
KOS_TCP_SYN_RCVD = 3
KOS_TCP_ESTABLISHED = 4

# Network interface flags
IFF_UP = 0x1
IFF_BROADCAST = 0x2
IFF_LOOPBACK = 0x8
IFF_RUNNING = 0x40

# Structures
class SockAddrIn(Structure):
    _fields_ = [
        ("sin_family", c_uint16),
        ("sin_port", c_uint16),
        ("sin_addr", c_uint32),
        ("sin_zero", c_uint8 * 8)
    ]

class NetifStats(Structure):
    _fields_ = [
        ("rx_packets", c_uint64),
        ("tx_packets", c_uint64),
        ("rx_bytes", c_uint64),
        ("tx_bytes", c_uint64),
        ("rx_errors", c_uint64),
        ("tx_errors", c_uint64),
        ("rx_dropped", c_uint64),
        ("tx_dropped", c_uint64)
    ]

# Function prototypes
netstack.kos_netstack_init.argtypes = []
netstack.kos_netstack_init.restype = c_int

netstack.kos_netstack_shutdown.argtypes = []
netstack.kos_netstack_shutdown.restype = None

netstack.kos_socket.argtypes = [c_int, c_int, c_int]
netstack.kos_socket.restype = c_int

netstack.kos_bind.argtypes = [c_int, POINTER(SockAddrIn), c_uint32]
netstack.kos_bind.restype = c_int

netstack.kos_listen.argtypes = [c_int, c_int]
netstack.kos_listen.restype = c_int

netstack.kos_accept.argtypes = [c_int, POINTER(SockAddrIn), POINTER(c_uint32)]
netstack.kos_accept.restype = c_int

netstack.kos_connect.argtypes = [c_int, POINTER(SockAddrIn), c_uint32]
netstack.kos_connect.restype = c_int

netstack.kos_send.argtypes = [c_int, c_void_p, c_size_t, c_int]
netstack.kos_send.restype = c_int

netstack.kos_recv.argtypes = [c_int, c_void_p, c_size_t, c_int]
netstack.kos_recv.restype = c_int

netstack.kos_sendto.argtypes = [c_int, c_void_p, c_size_t, c_int, POINTER(SockAddrIn), c_uint32]
netstack.kos_sendto.restype = c_int

netstack.kos_recvfrom.argtypes = [c_int, c_void_p, c_size_t, c_int, POINTER(SockAddrIn), POINTER(c_uint32)]
netstack.kos_recvfrom.restype = c_int

netstack.kos_setsockopt.argtypes = [c_int, c_int, c_int, c_void_p, c_uint32]
netstack.kos_setsockopt.restype = c_int

netstack.kos_close_socket.argtypes = [c_int]
netstack.kos_close_socket.restype = c_int

netstack.kos_netstat_dump.argtypes = []
netstack.kos_netstat_dump.restype = None

netstack.kos_socket_dump.argtypes = []
netstack.kos_socket_dump.restype = None

netstack.kos_netif_dump.argtypes = []
netstack.kos_netif_dump.restype = None

netstack.kos_ip_stats.argtypes = []
netstack.kos_ip_stats.restype = None

netstack.kos_udp_stats.argtypes = []
netstack.kos_udp_stats.restype = None


class KOSNetworkStack:
    """Python wrapper for KOS Network Stack"""
    
    def __init__(self):
        self.initialized = False
    
    def initialize(self):
        """Initialize the network stack"""
        ret = netstack.kos_netstack_init()
        if ret < 0:
            raise OSError(-ret, f"Failed to initialize network stack: {os.strerror(-ret)}")
        self.initialized = True
        return True
    
    def shutdown(self):
        """Shutdown the network stack"""
        if self.initialized:
            netstack.kos_netstack_shutdown()
            self.initialized = False
    
    def __del__(self):
        """Cleanup on destruction"""
        self.shutdown()


class KOSSocket:
    """Python wrapper for KOS sockets"""
    
    def __init__(self, family=KOS_AF_INET, type=KOS_SOCK_STREAM, proto=0):
        self.fd = netstack.kos_socket(family, type, proto)
        if self.fd < 0:
            raise OSError(-self.fd, f"Failed to create socket: {os.strerror(-self.fd)}")
        self.family = family
        self.type = type
        self.closed = False
    
    def bind(self, address):
        """Bind socket to address"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        host, port = address
        addr = SockAddrIn()
        addr.sin_family = self.family
        addr.sin_port = self._htons(port)
        addr.sin_addr = self._inet_addr(host)
        
        ret = netstack.kos_bind(self.fd, byref(addr), ctypes.sizeof(addr))
        if ret < 0:
            raise OSError(-ret, f"Failed to bind: {os.strerror(-ret)}")
    
    def listen(self, backlog=5):
        """Listen for connections"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        ret = netstack.kos_listen(self.fd, backlog)
        if ret < 0:
            raise OSError(-ret, f"Failed to listen: {os.strerror(-ret)}")
    
    def accept(self):
        """Accept a connection"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        addr = SockAddrIn()
        addr_len = c_uint32(ctypes.sizeof(addr))
        
        client_fd = netstack.kos_accept(self.fd, byref(addr), byref(addr_len))
        if client_fd < 0:
            raise OSError(-client_fd, f"Failed to accept: {os.strerror(-client_fd)}")
        
        # Create client socket object
        client = KOSSocket.__new__(KOSSocket)
        client.fd = client_fd
        client.family = self.family
        client.type = self.type
        client.closed = False
        
        # Extract client address
        client_addr = (self._inet_ntoa(addr.sin_addr), self._ntohs(addr.sin_port))
        
        return client, client_addr
    
    def connect(self, address):
        """Connect to remote address"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        host, port = address
        addr = SockAddrIn()
        addr.sin_family = self.family
        addr.sin_port = self._htons(port)
        addr.sin_addr = self._inet_addr(host)
        
        ret = netstack.kos_connect(self.fd, byref(addr), ctypes.sizeof(addr))
        if ret < 0:
            raise OSError(-ret, f"Failed to connect: {os.strerror(-ret)}")
    
    def send(self, data):
        """Send data"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        sent = netstack.kos_send(self.fd, data, len(data), 0)
        if sent < 0:
            raise OSError(-sent, f"Failed to send: {os.strerror(-sent)}")
        
        return sent
    
    def recv(self, bufsize):
        """Receive data"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        buffer = create_string_buffer(bufsize)
        received = netstack.kos_recv(self.fd, buffer, bufsize, 0)
        
        if received < 0:
            raise OSError(-received, f"Failed to receive: {os.strerror(-received)}")
        
        return buffer.raw[:received]
    
    def sendto(self, data, address):
        """Send data to address (UDP)"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        host, port = address
        addr = SockAddrIn()
        addr.sin_family = self.family
        addr.sin_port = self._htons(port)
        addr.sin_addr = self._inet_addr(host)
        
        sent = netstack.kos_sendto(self.fd, data, len(data), 0, byref(addr), ctypes.sizeof(addr))
        if sent < 0:
            raise OSError(-sent, f"Failed to sendto: {os.strerror(-sent)}")
        
        return sent
    
    def recvfrom(self, bufsize):
        """Receive data from address (UDP)"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        buffer = create_string_buffer(bufsize)
        addr = SockAddrIn()
        addr_len = c_uint32(ctypes.sizeof(addr))
        
        received = netstack.kos_recvfrom(self.fd, buffer, bufsize, 0, byref(addr), byref(addr_len))
        
        if received < 0:
            raise OSError(-received, f"Failed to recvfrom: {os.strerror(-received)}")
        
        client_addr = (self._inet_ntoa(addr.sin_addr), self._ntohs(addr.sin_port))
        return buffer.raw[:received], client_addr
    
    def setsockopt(self, level, optname, value):
        """Set socket option"""
        if self.closed:
            raise ValueError("Socket is closed")
        
        if isinstance(value, int):
            opt_val = c_int(value)
            ret = netstack.kos_setsockopt(self.fd, level, optname, byref(opt_val), ctypes.sizeof(opt_val))
        else:
            raise ValueError("Unsupported option value type")
        
        if ret < 0:
            raise OSError(-ret, f"Failed to set socket option: {os.strerror(-ret)}")
    
    def close(self):
        """Close socket"""
        if not self.closed:
            netstack.kos_close_socket(self.fd)
            self.closed = True
    
    def __del__(self):
        """Cleanup on destruction"""
        self.close()
    
    @staticmethod
    def _htons(port):
        """Host to network short"""
        return ((port & 0xFF) << 8) | ((port >> 8) & 0xFF)
    
    @staticmethod
    def _ntohs(port):
        """Network to host short"""
        return ((port & 0xFF) << 8) | ((port >> 8) & 0xFF)
    
    @staticmethod
    def _inet_addr(ip_str):
        """Convert IP string to network byte order"""
        if ip_str == "127.0.0.1":
            return 0x0100007F  # 127.0.0.1 in network byte order
        elif ip_str == "0.0.0.0":
            return 0
        else:
            # Simple parser for dotted decimal notation
            parts = ip_str.split('.')
            if len(parts) != 4:
                raise ValueError("Invalid IP address")
            
            addr = 0
            for i, part in enumerate(parts):
                addr |= (int(part) & 0xFF) << (i * 8)
            return addr
    
    @staticmethod
    def _inet_ntoa(addr):
        """Convert network byte order to IP string"""
        return f"{addr & 0xFF}.{(addr >> 8) & 0xFF}.{(addr >> 16) & 0xFF}.{(addr >> 24) & 0xFF}"


def print_network_stats():
    """Print network statistics"""
    print("=== Network Statistics ===")
    netstack.kos_netstat_dump()
    print("\n=== Socket Information ===")
    netstack.kos_socket_dump()
    print("\n=== Network Interfaces ===")
    netstack.kos_netif_dump()
    print("\n=== IP Statistics ===")
    netstack.kos_ip_stats()
    print("\n=== UDP Statistics ===")
    netstack.kos_udp_stats()


def demo_tcp_server():
    """Demo TCP server"""
    print("Starting TCP server demo...")
    
    # Initialize network stack
    net = KOSNetworkStack()
    net.initialize()
    
    try:
        # Create server socket
        server = KOSSocket(KOS_AF_INET, KOS_SOCK_STREAM)
        server.setsockopt(KOS_SOL_SOCKET, KOS_SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", 8080))
        server.listen(5)
        
        print("TCP server listening on 127.0.0.1:8080")
        print("Connect with: telnet 127.0.0.1 8080")
        
        while True:
            try:
                client, addr = server.accept()
                print(f"Accepted connection from {addr}")
                
                # Echo server
                while True:
                    data = client.recv(1024)
                    if not data:
                        break
                    
                    print(f"Received: {data.decode('utf-8', errors='ignore')}")
                    client.send(data)  # Echo back
                
                client.close()
                print(f"Client {addr} disconnected")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        server.close()
        
    finally:
        net.shutdown()


def demo_udp_server():
    """Demo UDP server"""
    print("Starting UDP server demo...")
    
    # Initialize network stack
    net = KOSNetworkStack()
    net.initialize()
    
    try:
        # Create server socket
        server = KOSSocket(KOS_AF_INET, KOS_SOCK_DGRAM)
        server.bind(("127.0.0.1", 8081))
        
        print("UDP server listening on 127.0.0.1:8081")
        print("Send UDP packets to test")
        
        while True:
            try:
                data, addr = server.recvfrom(1024)
                print(f"Received from {addr}: {data.decode('utf-8', errors='ignore')}")
                
                # Echo back
                response = f"Echo: {data.decode('utf-8', errors='ignore')}"
                server.sendto(response, addr)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
        
        server.close()
        
    finally:
        net.shutdown()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "tcp":
            demo_tcp_server()
        elif sys.argv[1] == "udp":
            demo_udp_server()
        elif sys.argv[1] == "stats":
            net = KOSNetworkStack()
            net.initialize()
            print_network_stats()
            net.shutdown()
        else:
            print("Usage: python3 netstack_wrapper.py [tcp|udp|stats]")
    else:
        print("KOS Network Stack Python Wrapper")
        print("Usage: python3 netstack_wrapper.py [tcp|udp|stats]")
        print("  tcp   - Run TCP server demo")
        print("  udp   - Run UDP server demo") 
        print("  stats - Show network statistics")
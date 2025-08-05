# KOS Network Stack

A complete TCP/IP network stack implementation for the KOS operating system, written in C/C++ with Python bindings.

## Features

### Core Networking
- **Complete TCP/IP Stack**: Full implementation of TCP, UDP, IP, and ICMP protocols
- **Socket API**: Berkeley sockets-compatible API for network programming
- **Network Interfaces**: Virtual network interface management
- **Routing**: IP routing table with route lookup and management
- **ARP Cache**: Address Resolution Protocol cache for MAC address mapping
- **Connection Tracking**: Network connection state tracking
- **Packet Management**: Efficient packet allocation and management

### TCP Implementation
- **Full TCP State Machine**: Complete implementation of all TCP states
- **Three-way Handshake**: Proper connection establishment and teardown
- **Congestion Control**: Slow start, congestion avoidance, and fast recovery
- **Retransmission**: Reliable data delivery with timeout and retransmission
- **Window Management**: Flow control with sliding window protocol
- **Nagle Algorithm**: Optional packet coalescing for improved efficiency

### UDP Implementation
- **Connectionless Service**: Full UDP datagram service
- **Port Management**: Automatic ephemeral port allocation
- **Checksum Verification**: Optional UDP checksum calculation and verification
- **Broadcast Support**: Support for broadcast and multicast packets

### IP Layer
- **IPv4 Support**: Complete IPv4 packet processing
- **Fragmentation**: IP packet fragmentation and reassembly
- **Routing**: IP routing with route table lookup
- **ICMP Support**: Internet Control Message Protocol implementation
- **TTL Handling**: Time-to-live processing and expiration

## Architecture

```
┌─────────────────────────────────────┐
│          Application Layer          │
├─────────────────────────────────────┤
│           Socket Layer              │  ← socket.c
├─────────────────────────────────────┤
│     TCP                UDP          │  ← tcp.c, udp.c
├─────────────────────────────────────┤
│            IP Layer                 │  ← ip.c
├─────────────────────────────────────┤
│         Network Interface           │  ← netstack.c
└─────────────────────────────────────┘
```

## Files

- **netstack.h**: Main header file with all structure definitions and function prototypes
- **netstack.c**: Core network stack initialization, packet management, and network interfaces
- **socket.c**: Socket layer implementation with Berkeley sockets API
- **tcp.c**: Complete TCP protocol implementation with state machine
- **udp.c**: UDP protocol implementation with connectionless service
- **ip.c**: IP layer with routing, fragmentation, and ICMP support
- **Makefile**: Build system for compiling the network stack
- **test_netstack.c**: Comprehensive test program for the network stack
- **netstack_wrapper.py**: Python bindings for easy integration
- **README.md**: This documentation file

## Building

### Prerequisites
- GCC compiler with C99 support
- POSIX threads library (pthread)
- Standard C library with socket headers

### Compilation
```bash
# Build shared library
make

# Build static library
make static

# Build with debug symbols
make debug

# Run tests
make test

# Clean build files
make clean
```

### Installation
```bash
# Install system-wide (requires sudo)
make install
```

## Usage

### C API

```c
#include "netstack.h"

// Initialize network stack
int ret = kos_netstack_init();
if (ret < 0) {
    fprintf(stderr, "Failed to initialize network stack\n");
    return -1;
}

// Create TCP socket
int sockfd = kos_socket(KOS_AF_INET, KOS_SOCK_STREAM, 0);

// Bind to address
struct sockaddr_in addr;
addr.sin_family = AF_INET;
addr.sin_addr.s_addr = htonl(INADDR_ANY);
addr.sin_port = htons(8080);
kos_bind(sockfd, (struct sockaddr*)&addr, sizeof(addr));

// Listen for connections
kos_listen(sockfd, 10);

// Accept connections
struct sockaddr_in client_addr;
socklen_t client_len = sizeof(client_addr);
int client_fd = kos_accept(sockfd, (struct sockaddr*)&client_addr, &client_len);

// Send/receive data
char buffer[1024];
ssize_t received = kos_recv(client_fd, buffer, sizeof(buffer), 0);
ssize_t sent = kos_send(client_fd, "Hello", 5, 0);

// Cleanup
kos_close_socket(client_fd);
kos_close_socket(sockfd);
kos_netstack_shutdown();
```

### Python API

```python
from netstack_wrapper import KOSNetworkStack, KOSSocket, KOS_AF_INET, KOS_SOCK_STREAM

# Initialize network stack
net = KOSNetworkStack()
net.initialize()

# Create TCP server
server = KOSSocket(KOS_AF_INET, KOS_SOCK_STREAM)
server.bind(("127.0.0.1", 8080))
server.listen(5)

# Accept connections
client, addr = server.accept()
print(f"Connected: {addr}")

# Send/receive data
data = client.recv(1024)
client.send(b"Hello from KOS!")

# Cleanup
client.close()
server.close()
net.shutdown()
```

## Testing

The network stack includes comprehensive tests:

### C Test Program
```bash
# Compile and run tests
make test

# Or run manually
./test_netstack
```

### Python Tests
```bash
# Run TCP server demo
python3 netstack_wrapper.py tcp

# Run UDP server demo  
python3 netstack_wrapper.py udp

# Show network statistics
python3 netstack_wrapper.py stats
```

## API Reference

### Core Functions
- `kos_netstack_init()`: Initialize the network stack
- `kos_netstack_shutdown()`: Shutdown the network stack

### Socket Functions
- `kos_socket(domain, type, protocol)`: Create a socket
- `kos_bind(sockfd, addr, addrlen)`: Bind socket to address
- `kos_listen(sockfd, backlog)`: Listen for connections
- `kos_accept(sockfd, addr, addrlen)`: Accept a connection
- `kos_connect(sockfd, addr, addrlen)`: Connect to remote address
- `kos_send(sockfd, buf, len, flags)`: Send data
- `kos_recv(sockfd, buf, len, flags)`: Receive data
- `kos_sendto(sockfd, buf, len, flags, dest_addr, addrlen)`: Send UDP packet
- `kos_recvfrom(sockfd, buf, len, flags, src_addr, addrlen)`: Receive UDP packet
- `kos_setsockopt(sockfd, level, optname, optval, optlen)`: Set socket option
- `kos_getsockopt(sockfd, level, optname, optval, optlen)`: Get socket option
- `kos_close_socket(sockfd)`: Close socket

### Network Interface Functions
- `kos_netif_create(name)`: Create network interface
- `kos_netif_find(name)`: Find interface by name
- `kos_netif_up(netif)`: Bring interface up
- `kos_netif_down(netif)`: Bring interface down
- `kos_netif_set_addr(netif, addr, netmask)`: Set interface IP address

### Statistics Functions
- `kos_netstat_dump()`: Print network statistics
- `kos_socket_dump()`: Print socket information
- `kos_netif_dump()`: Print network interfaces
- `kos_ip_stats()`: Print IP statistics
- `kos_udp_stats()`: Print UDP statistics

## Integration with KOS

The network stack is designed to integrate seamlessly with the KOS operating system:

1. **Kernel Integration**: Core network functions can be called from kernel space
2. **User Space Access**: Socket API available to user space applications
3. **Python Bindings**: Easy integration with KOS Python components
4. **Thread Safety**: All operations are thread-safe using mutexes
5. **Memory Management**: Efficient packet allocation and cleanup

## Performance Considerations

- **Zero-Copy Design**: Minimizes data copying in packet processing
- **Efficient Data Structures**: Hash tables for fast socket and connection lookup
- **Asynchronous Processing**: Background worker thread for timer processing
- **Congestion Control**: TCP congestion control for optimal throughput
- **Buffer Management**: Configurable socket buffer sizes

## Security Features

- **Input Validation**: All network input is validated for security
- **Connection Tracking**: Track all network connections for monitoring
- **Checksum Verification**: Validate packet checksums to detect corruption
- **Rate Limiting**: Built-in protection against some DoS attacks

## Limitations

- **IPv4 Only**: Currently supports IPv4 only (IPv6 support planned)
- **Simulated Network**: Uses simulated network interfaces for testing
- **No Hardware Drivers**: Requires integration with actual network hardware
- **Limited Protocol Support**: Currently supports TCP, UDP, IP, and ICMP only

## Future Enhancements

- IPv6 support
- Advanced routing protocols (OSPF, BGP)
- Network security features (IPSec, TLS)
- Quality of Service (QoS) support
- Network namespaces
- Advanced firewall features
- Performance optimizations
- Hardware offloading support

## Contributing

When contributing to the network stack:

1. Follow the existing code style and conventions
2. Add comprehensive tests for new features
3. Update documentation for API changes
4. Ensure thread safety for all operations
5. Test thoroughly with both C and Python APIs

## License

This network stack is part of the KOS operating system project and follows the same licensing terms.
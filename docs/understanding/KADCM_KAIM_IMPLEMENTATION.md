# KADCM and KAIM Implementation Understanding

## Overview

This document captures my complete understanding of the KADCM and KAIM systems as implemented for KOS.

## KADCM (Kaede Advanced Device Communication Manager)

### Purpose
KADCM enables secure bidirectional communication between the host OS (Windows/Linux) and KOS. It's similar to how WSL allows Windows to interact with Linux subsystems.

### Architecture

#### 1. Communication Channel
- **Primary**: Named pipes with TLS/SSL encryption
  - Linux: `/var/run/kos/runtime/kadcm/kadcm.pipe`
  - Windows: `\\.\pipe\kos\runtime\kadcm\kadcm`
- **Fallback**: TCP sockets on localhost (ports 9876-9878)
- **Encryption**: TLS 1.3 minimum with strong cipher suites

#### 2. Protocol
- **Format**: Binary frame + JSON header + YAML body
- **Frame Structure**: `[4 bytes: length][1 byte: flags][message data]`
- **Message Types**:
  - COMMAND: Execute host/KOS commands
  - DATA: File transfers
  - AUTH: Authentication/fingerprint exchange
  - CONTROL: Tunnel management
  - HEARTBEAT: Keepalive (30s interval)
  - ERROR: Error reporting
  - NOTIFY: Asynchronous alerts

#### 3. Authentication
- **Method**: Challenge-response with fingerprints
- **Flow**:
  1. Server sends challenge (32 random bytes)
  2. Client creates signature: SHA256(challenge + fingerprint)
  3. Server verifies fingerprint and signature
  4. Session created with 300s validity

#### 4. Security
- **Fingerprint verification** for all entities (host, KOS, users)
- **Session management** with automatic expiration
- **Permission-based access control**
- **Audit logging** of all operations

### Implementation Components

1. **Manager** (`manager.py`): Core KADCM daemon
   - Handles connections and message routing
   - Manages sessions and permissions
   - Implements command execution and file operations

2. **Protocol** (`protocol.py`): Message encoding/decoding
   - Binary protocol with compression support
   - JSON/YAML hybrid for structured data

3. **Tunnel** (`tunnel.py`): TLS tunnel implementation
   - SSL context management
   - Platform-specific socket handling

4. **Host Driver** (`host_driver.py`): Runs on host OS
   - C++ implementation for Windows/Linux
   - Python wrapper for high-level API
   - Automatic reconnection and error handling

## KAIM (Kaede Application Interface Manager)

### Purpose
KAIM provides controlled kernel access for applications, similar to how Linux applications interact with the kernel through system calls, but with additional permission management.

### Architecture

#### 1. Kernel Module (`kaim.ko`)
- **Real kernel module** written in C
- Creates `/dev/kaim` character device
- Implements ioctl interface for:
  - Privilege elevation
  - Device access control
  - Permission checking
  - Audit logging

#### 2. Userspace Daemon (`_kaim`)
- Runs as dedicated system user
- Manages high-level operations
- Communicates via Unix socket: `/var/run/kaim.sock`
- Enforces RBAC policies

#### 3. Client Library
- **C++ library** (`libkaim.so`) for native apps
- **Python bindings** via ctypes
- Thread-safe design
- Automatic session management

### Permission System

#### Flags (18 total)
- **KROOT**: Full unrestricted access
- **KSYSTEM**: System management (limited)
- **KUSR**: User management
- **KAM**: Access management
- **KNET**: Network configuration
- **KDEV**: Device access
- **KPROC**: Process management
- **KFILE_R/W/X**: File operations
- **KMEM**: Memory management
- **KLOG**: Log access
- **KSEC**: Security subsystem
- **KAUD**: Audit logging
- **KCFG**: Configuration management
- **KUPD**: System update
- **KSRV**: Service management
- **KDBG**: Debugging tools

### Implementation Components

1. **Kernel Module** (`kaim_module.c`):
   - Hash table for process tracking
   - ioctl handlers for all operations
   - `/proc` interface for status
   - Audit logging to kernel buffer

2. **C++ Library** (`kaim_lib.cpp`):
   - Object-oriented interface
   - Automatic resource management
   - Error handling with exceptions
   - C API for compatibility

3. **Python Integration** (`ctypes_wrapper.py`):
   - Direct kernel ioctl access
   - C++ library wrapper
   - High-level decorators
   - Context manager support

4. **Device Management** (`device.py`):
   - Device type handlers (block, char, network)
   - Control command routing
   - Permission checking

## Key Design Decisions

### 1. Real Implementation vs Simulation
- Kernel module is actual C code, not Python simulation
- Uses real Linux kernel APIs and data structures
- Proper ioctl interface with type safety
- Hardware device interaction capabilities

### 2. Security First
- All operations require authentication
- Fingerprint-based identity verification
- Permission checks at kernel level
- Comprehensive audit trail

### 3. Production Ready
- Error handling at every level
- Thread safety and concurrency
- Resource cleanup and leak prevention
- Extensive logging and debugging

### 4. Platform Support
- Native Windows support via named pipes
- Linux support via Unix sockets
- Fallback mechanisms for compatibility
- Platform-specific optimizations

## Integration Points

### 1. With KOS Core
- ProcessManager tracks KAIM permissions
- FileSystem respects KAIM access controls
- Shell commands use KAIM for privilege elevation
- Services register with KAIM for management

### 2. With Security System
- Fingerprint manager integration
- RBAC policy enforcement
- SELinux-style contexts (future)
- Capability-based security model

### 3. With Applications
- SDK includes KAIM headers
- Build system links against libkaim
- Runtime permission requests
- Graceful degradation without privileges

## Build and Deployment

### 1. Compilation
```bash
cd /kos/kaim/kernel
make all          # Build kernel module and libraries
make install      # Install everything
make install_user # Create system user
```

### 2. Testing
```bash
make test         # Run all tests
./test_kaim       # C++ tests
python test_kaim.py # Python tests
make check_module # Verify installation
```

### 3. Usage
```python
# Python example
from kos.kaim import KAIMClient

client = KAIMClient("myapp", "fingerprint_hash")
if client.connect():
    # Request device access
    fd = client.kaim_device_open("sda", "r")
    
    # Elevate privileges
    client.kaim_process_elevate(flags=["KNET", "KDEV"])
```

## Current Status

### Completed
- ✅ Full KADCM implementation with host driver
- ✅ Complete KAIM kernel module in C
- ✅ C++ client library with full features
- ✅ Python ctypes integration
- ✅ Protocol definitions and message handling
- ✅ Session management and authentication
- ✅ Device management framework
- ✅ Build system and installation

### Next Steps
1. Implement actual hardware device drivers
2. Add SELinux-style security contexts
3. Create GUI management tools
4. Performance optimization
5. Stress testing and fuzzing

## Troubleshooting

### Common Issues

1. **Module won't load**
   - Check kernel headers installed
   - Verify no conflicting modules
   - Check dmesg for errors

2. **Permission denied**
   - Ensure user in 'kaim' group
   - Check /dev/kaim permissions
   - Verify fingerprint registration

3. **Connection failures**
   - Check daemon running
   - Verify socket permissions
   - Check firewall rules

### Debug Commands
```bash
# Check module
lsmod | grep kaim
cat /proc/kaim/status

# Check daemon
ps aux | grep _kaim
systemctl status kaim

# View logs
journalctl -u kaim
dmesg | grep -i kaim

# Test connection
strace -e trace=open,ioctl python -c "import kos.kaim; kos.kaim.test_kaim_integration()"
```
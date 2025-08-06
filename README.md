# KOS - Kaede Operating System v3.0

A complete operating system implementation in Python with layered architecture.

## Architecture

KOS is built with a clean, modular architecture consisting of two main layers:

### KLayer (Core OS Layer)
Provides fundamental OS services:
- **File System Operations** - Virtual filesystem with full POSIX-like operations
- **Process Management** - Process creation, execution, and lifecycle management
- **User Management** - Multi-user support with authentication and roles
- **System Information** - CPU, memory, disk, and system metrics
- **I/O Operations** - Standard input/output handling
- **Memory Management** - Simulated memory allocation and management
- **Device Abstraction** - Device management and I/O
- **Environment Variables** - System and user environment configuration
- **Permissions** - File permissions and access control

### KADVLayer (Advanced Services Layer)
Provides high-level services built on KLayer:
- **Network Stack** - TCP/IP networking, DNS, HTTP client
- **Service Management** - systemd-like service control
- **Security** - Firewall, VPN, SSL/TLS, intrusion detection
- **Monitoring** - System metrics, process monitoring, resource tracking
- **Database** - Built-in database with SQL support
- **Web Services** - HTTP server, REST API, WebSocket support
- **Container Support** - Docker-like container management
- **Orchestration** - Kubernetes-like service orchestration
- **Application Framework** - App lifecycle management
- **Package Management** - Package repository with dependency resolution
- **Backup & Recovery** - System backup and snapshot management
- **AI/ML Integration** - Machine learning model training and inference

## Quick Start

```bash
# Clone the repository
git clone https://github.com/kaededev/kos.git
cd kos

# Run KOS shell
python3 main.py

# Run with verbose output
python3 main.py -v

# Execute single command
python3 main.py -c "ls /"

# Show system status
python3 main.py --status

# Start with clean filesystem
python3 main.py --clean
```

## Demo

Run the comprehensive demo to see all features:

```bash
python3 demo.py
```

## Shell Commands

### File System
- `ls [path]` - List directory contents
- `cd <path>` - Change directory
- `pwd` - Print working directory
- `mkdir <path>` - Create directory
- `touch <file>` - Create empty file
- `cat <file>` - Display file contents
- `echo <text>` - Print text
- `cp <src> <dst>` - Copy file
- `mv <src> <dst>` - Move/rename file
- `rm <path>` - Remove file/directory
- `chmod <mode> <path>` - Change permissions
- `chown <user> <path>` - Change ownership

### User Management
- `whoami` - Show current user
- `useradd <username>` - Add user
- `passwd [username]` - Change password
- `su <username>` - Switch user
- `sudo <command>` - Execute as root

### Process Management
- `ps` - List processes
- `kill <pid>` - Terminate process
- `top` - Process monitor
- `jobs` - List background jobs
- `fg [job]` - Bring job to foreground
- `bg [job]` - Send job to background

### Network
- `ping <host>` - Ping host
- `ifconfig` - Network configuration
- `netstat` - Network statistics
- `curl <url>` - HTTP request
- `wget <url>` - Download file
- `ssh <host>` - SSH client

### Package Management
- `kpm install <package>` - Install package
- `kpm uninstall <package>` - Uninstall package
- `kpm update` - Update packages
- `kpm search <query>` - Search packages
- `kpm list` - List installed packages

### Services
- `systemctl start <service>` - Start service
- `systemctl stop <service>` - Stop service
- `systemctl status <service>` - Service status
- `systemctl enable <service>` - Enable service
- `systemctl disable <service>` - Disable service

### System
- `date` - Show date/time
- `uptime` - System uptime
- `df` - Disk usage
- `free` - Memory usage
- `uname` - System information
- `env` - Environment variables
- `history` - Command history
- `clear` - Clear screen
- `exit` - Exit shell

## Python API

### Using KLayer

```python
from kos.layers.klayer import KLayer

# Initialize KLayer
klayer = KLayer(disk_file='system.kdsk')

# File operations
klayer.fs_write('/test.txt', b'Hello World')
data = klayer.fs_read('/test.txt')

# Process management
pid = klayer.process_create('echo', ['Hello'])
result = klayer.process_execute(pid)

# User management
klayer.user_create('alice', 'password', 'user')
klayer.user_login('alice', 'password')

# System info
info = klayer.sys_info()
memory = klayer.sys_memory_info()
```

### Using KADVLayer

```python
from kos.layers.kadvlayer import KADVLayer

# Initialize KADVLayer
kadvlayer = KADVLayer(klayer=klayer)

# Network operations
kadvlayer.net_configure('eth0', '192.168.1.100', '255.255.255.0')
kadvlayer.net_ping('google.com')

# Service management
kadvlayer.service_create('myapp', '/usr/bin/myapp', 'My Application')
kadvlayer.service_start('myapp')

# Container operations
container = kadvlayer.container_create('webapp', 'nginx')
kadvlayer.container_start('webapp')

# Database operations
kadvlayer.db_connect()
kadvlayer.db_execute("CREATE TABLE users (id INT, name TEXT)")
results = kadvlayer.db_query("SELECT * FROM users")

# Backup
backup_id = kadvlayer.backup_create(['/home'], 'Home backup')
kadvlayer.backup_restore(backup_id)
```

## Project Structure

```
KOS/
├── kos/
│   ├── core/           # Core components
│   │   ├── vfs.py      # Virtual File System
│   │   ├── auth.py     # Authentication
│   │   ├── executor.py # Process execution
│   │   ├── permissions.py # Access control
│   │   └── config.py   # Configuration
│   ├── layers/         # OS Layers
│   │   ├── klayer.py   # Core OS layer
│   │   └── kadvlayer.py # Advanced services
│   ├── shell/          # Shell implementation
│   │   ├── shell.py    # Main shell
│   │   └── commands/   # Shell commands
│   ├── network/        # Networking
│   ├── services/       # Service management
│   ├── security/       # Security features
│   ├── monitoring/     # System monitoring
│   ├── database/       # Database support
│   ├── web/           # Web services
│   ├── apps/          # Application framework
│   ├── package/       # Package management
│   └── utils/         # Utilities
├── main.py            # Main entry point
├── demo.py            # Feature demonstration
└── README.md          # This file
```

## Features

### Virtual File System
- Persistent storage using pickle serialization
- Full directory tree with mount points
- File metadata and attributes
- Symbolic and hard links
- File locking mechanisms

### Authentication & Security
- Multi-user support with roles (ROOT, ADMIN, USER, GUEST)
- Password-based authentication
- File permissions (Unix-style)
- Access Control Lists (ACLs)
- Firewall with rule management
- VPN and SSL/TLS support

### Process Management
- Process creation and execution
- Background job support
- Signal handling
- Process monitoring
- Resource limits

### Networking
- TCP/IP stack simulation
- Network interface configuration
- DNS resolution
- HTTP client/server
- SSH server
- Mail server (SMTP/IMAP)

### Service Management
- systemd-like service control
- Service dependencies
- Automatic restart policies
- Cron job scheduling
- Log management with rotation

### Package Management
- Repository-based packages
- Dependency resolution
- Version management
- Package signing
- Update mechanisms

### Application Framework
- Application lifecycle management
- Inter-app communication
- Resource isolation
- Permission system
- Configuration management

### Container Support
- Container creation and management
- Image support
- Network isolation
- Resource limits
- Container orchestration

### Monitoring & Logging
- Real-time system metrics
- Process monitoring
- Network statistics
- Disk I/O tracking
- Centralized logging
- Log analysis tools

### Backup & Recovery
- Full system backups
- Incremental backups
- Snapshot support
- Restore operations
- Archive management (tar, zip)

## Requirements

- Python 3.8+
- No external dependencies (pure Python)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

## Author

Kaede - Initial work and architecture

## Acknowledgments

- Inspired by Unix/Linux design principles
- Python standard library for core functionality
- Clean architecture and SOLID principles
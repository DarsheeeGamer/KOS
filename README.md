# KOS - Kaede Operating System v4.0

A complete operating system implementation in Python with **real memory management** and **full Python/pip integration**.

## Architecture

KOS is built with a clean, modular architecture consisting of two main layers:

### KLayer (Core OS Layer) 
Provides fundamental OS services with **real implementations**:
- **Real Memory Management** - Actual memory allocation with tracking, garbage collection, and memory mapping
- **Python Integration** - Full Python interpreter with VFS isolation
- **pip Support** - Install real Python packages into VFS
- **Virtual Environments** - Create isolated Python environments
- **File System Operations** - Virtual filesystem with full POSIX-like operations
- **Process Management** - Process creation with memory tracking
- **User Management** - Multi-user support with authentication and roles
- **System Information** - Real memory statistics and system metrics
- **Shared Memory** - IPC through shared memory segments
- **Memory-Mapped Files** - Map files directly into memory
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

## Key Features

### Real Memory Management
- **Actual memory allocation** using Python's memory management
- **Memory tracking** per process and globally
- **Garbage collection** for orphaned memory
- **Memory mapping** for files
- **Shared memory** for IPC
- **Memory statistics** with real usage data

### Python & pip Integration
- **Run Python scripts** from VFS
- **Install packages** with `pip install numpy` (real packages!)
- **Create virtual environments** isolated in VFS
- **Import packages** from VFS seamlessly
- **Execute Python code** in sandboxed namespaces

## Shell Commands

### Python & pip
- `python` - Start Python REPL
- `python script.py` - Run Python script from VFS
- `python -c "code"` - Execute Python code
- `pip install <package>` - Install real Python package
- `pip uninstall <package>` - Remove package
- `pip list` - List installed packages
- `venv create <name>` - Create virtual environment

### Memory Management
- `free [-h]` - Show memory usage (real stats)
- `memstat [pid]` - Detailed memory statistics
- `gc` - Run garbage collection

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

### Using KLayer with Real Memory & Python

```python
from kos.layers.klayer import KLayer

# Initialize KLayer with 8GB memory
klayer = KLayer(disk_file='system.kdsk', memory_size=8*1024*1024*1024)

# Real memory allocation
addr = klayer.mem_allocate(1024)  # Allocate 1KB
klayer.mem_write(addr, b'Hello Memory!')
data = klayer.mem_read(addr, 13)
klayer.mem_free(addr)

# Shared memory for IPC
shm_addr = klayer.mem_share("mydata", 4096)
klayer.mem_write(shm_addr, b'Shared data')

# Python execution in VFS
klayer.python_execute("print('Hello from VFS Python!')")

# Install real Python packages
klayer.python_install_package("requests")
klayer.python_install_package("numpy", "1.21.0")

# Create and use virtual environment
klayer.python_create_venv("myproject", "/home/user/venvs/myproject")

# Execute Python file from VFS
klayer.fs_write('/script.py', b'import requests\nprint(requests.__version__)')
result = klayer.python_execute_file('/script.py')

# Get real memory statistics
mem_stats = klayer.sys_memory_info()
print(f"Memory: {mem_stats['used']}/{mem_stats['total']} ({mem_stats['percent']}%)")

# Process with memory tracking
pid = klayer.process_create('python', ['-c', 'print("test")'])
mem_usage = klayer.mem_get_process_usage(pid)
print(f"Process {pid} using {mem_usage['total']} bytes")
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
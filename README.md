# KOS - Advanced Python-based Shell System

KOS is a powerful Python-based shell system with advanced system utilities that provide Linux-style command functionality for system monitoring, hardware management, process control, and network diagnostics.

## Features

- **Advanced System Layer (KADVLayer)** - Deep system integration with comprehensive monitoring capabilities
  - System resource monitoring (CPU, memory, disk, network)
  - Process management and monitoring
  - Hardware device detection and management
  - Network interface monitoring and diagnostics
  - Event-based callbacks for system events

- **Application Layer (KLayer)** - Application management and security
  - Application lifecycle management
  - Sandboxed file system access
  - Permission-based security model
  - Command execution interface

- **Rich Command Set** - Linux-style utility commands
  - System utilities (`sysinfo`, `psutil`, `sysmon`)
  - Hardware utilities (`lshw`, `lsblk`, `lsusb`, `lspci`, `sensors`)
  - Network utilities (`ifconfig`, `ping`, `traceroute`, `netstat`, `nslookup`)
  - Package management (`kpm`)

## Installation

```bash
# Install from PyPI
pip install kos-shell

# Or install from source
git clone https://github.com/DarsheeeGamer/KOS.git
cd KOS
pip install -e .
```

## Quick Start

```bash
# Start the KOS shell
kos

# Get system information
kos> sysinfo

# Monitor system resources
kos> sysmon start

# List all hardware devices
kos> lshw

# Check network interfaces
kos> ifconfig

# Ping a host
kos> ping google.com
```

## Command Reference

### System Utilities

| Command | Description |
|---------|-------------|
| `sysinfo` | Display comprehensive system information |
| `psutil list` | List all processes |
| `psutil kill <pid>` | Kill a process |
| `sysmon start` | Start system monitoring |
| `sysmon stop` | Stop system monitoring |
| `sysmon status` | Show monitoring status |
| `sysmon report` | Generate monitoring report |

### Hardware Utilities

| Command | Description |
|---------|-------------|
| `lshw` | List hardware devices |
| `lsblk` | List block devices |
| `lsusb` | List USB devices |
| `lspci` | List PCI devices |
| `sensors` | Display hardware sensors information |

### Network Utilities

| Command | Description |
|---------|-------------|
| `ifconfig` | Display network interface configuration |
| `ping <host>` | Send ICMP ECHO_REQUEST to network hosts |
| `traceroute <host>` | Trace route to host |
| `netstat` | Print network connections, routing tables, interface statistics |
| `nslookup <name>` | Query DNS servers |

## Advanced Usage

### System Monitoring

```bash
# Start system monitoring with custom interval
kos> sysmon start --interval=10

# Generate a system report in JSON format
kos> sysmon report --json

# Get detailed CPU information
kos> sysinfo --cpu
```

### Process Management

```bash
# List all processes sorted by CPU usage
kos> psutil list --sort=cpu

# List all processes sorted by memory usage
kos> psutil list --sort=memory

# Kill a process
kos> psutil kill 1234
```

### Network Diagnostics

```bash
# Ping a host with custom count and timeout
kos> ping -c 10 -w 2 google.com

# Trace route to a host with maximum 15 hops
kos> traceroute -m 15 github.com

# Show all network connections
kos> netstat -a
```

## API Reference

KOS provides Python APIs for system integration and monitoring:

```python
from kos.advlayer import kadvlayer
from kos.layer import klayer

# Get system information
system_info = kadvlayer.system_info.get_system_info()

# Monitor CPU usage
def on_high_cpu(data):
    print(f"High CPU usage: {data['percent']}%")

kadvlayer.resource_monitor.register_callback("cpu_high", on_high_cpu)
kadvlayer.start_monitoring()
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

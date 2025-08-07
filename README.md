# KOS - Kaede Operating System

**KOS** is an advanced Python-based operating system with a custom virtual file system, real memory management, and comprehensive system services. Built from scratch without external dependencies, KOS provides a complete OS environment with advanced features.

## 🚀 Features

### Core System
- **Custom Binary VFS** - High-performance virtual file system with inode-based structure
- **Real Memory Management** - Actual memory allocation, tracking, and garbage collection
- **Process Management** - Advanced process control with resource isolation
- **Multi-User Support** - User authentication, permissions, and role-based access
- **Python Integration** - Embedded Python interpreter with isolated execution

### File System
- **Binary Format Storage** - Custom VFS implementation without pickle dependencies
- **Inode-Based Structure** - Unix-like filesystem with superblock and block allocation
- **Directory Hierarchy** - Full POSIX-compatible directory tree
- **File Operations** - Complete read/write/seek support with buffering
- **Background Sync** - Automatic persistence with configurable sync intervals

### Memory System
- **Unified Memory Space** - Single address space with virtual-to-physical mapping
- **Memory Distribution** - Intelligent data distribution across virtual devices
- **Segment Caching** - High-performance cache with LRU eviction
- **Garbage Collection** - Automatic memory reclamation
- **Memory Statistics** - Real-time usage tracking and reporting

### Advanced Services
- **Process Manager** - Execute and manage system processes
- **Network Stack** - TCP/IP networking simulation
- **Package Management** - pip-compatible package installation
- **Service Control** - systemd-like service management
- **System Monitoring** - Resource usage and performance metrics

## 📦 Installation

```bash
# Clone the repository
git clone https://github.com/DarsheeeGamer/KOS.git
cd KOS

# No external dependencies required - pure Python!
# Just run:
python3 kos_system.py
```

## 🎯 Quick Start

### Basic Usage

```python
from kos import KOSUnifiedSystem, KOSConfig

# Initialize KOS
config = KOSConfig(
    vfs_size=100 * 1024 * 1024,  # 100MB VFS
    memory_size=512 * 1024 * 1024,  # 512MB memory
    enable_cache=True
)

kos = KOSUnifiedSystem(config)
kos.initialize()

# Memory operations
addr = kos.malloc(1024)  # Allocate 1KB
kos.write(addr, b"Hello KOS!")
data = kos.read(addr, 10)
kos.free(addr)

# File operations
with kos.vfs.open("/home/user/test.txt", "w") as f:
    f.write(b"KOS VFS Working!")

# Create NumPy arrays in unified memory
import numpy as np
addr, array = kos.create_numpy_array((1000, 1000), np.float32)
array[:] = np.random.randn(1000, 1000)
```

### VFS Operations

```python
from kos.core.vfs import get_vfs

# Get VFS instance
vfs = get_vfs("mydata.vfs")

# Create directories
vfs.makedirs("/home/user/projects")

# Write files
with vfs.open("/home/user/data.txt", "w") as f:
    f.write(b"Custom VFS with binary format")

# List directory
files = vfs.listdir("/home/user")

# Get file stats
stats = vfs.stat("/home/user/data.txt")
print(f"Size: {stats['st_size']} bytes")
```

## 🏗️ Architecture

```
KOS/
├── kos/
│   ├── core/               # Core OS components
│   │   ├── vfs.py         # Custom Virtual File System
│   │   ├── config.py      # System configuration
│   │   ├── errors.py      # Error handling
│   │   └── framework.py   # Core framework
│   ├── memory/            # Memory management
│   │   ├── unified_memory.py    # Unified memory space
│   │   └── data_distributor.py  # Data distribution engine
│   ├── compute/           # Compute management
│   │   ├── kernel_registry.py   # Kernel management
│   │   └── scheduler.py         # Task scheduling
│   ├── hardware/          # Hardware abstraction
│   │   ├── base.py        # Device abstraction
│   │   └── cpu.py         # CPU management
│   ├── advlayer/          # Advanced services
│   │   └── process_manager.py   # Process management
│   └── kos_system.py      # Main system interface
```

## 💡 Key Components

### Custom VFS Implementation
The VFS uses a binary format with:
- **Superblock**: Filesystem metadata
- **Inode Table**: File and directory metadata
- **Data Blocks**: Actual file content
- **Block Allocation**: Dynamic block management
- **Binary Serialization**: Using Python struct module

### Memory Management
- **Virtual Address Space**: 64-bit addressing
- **Page Tables**: Virtual-to-physical mapping
- **Memory Segments**: Distributed data chunks
- **Cache Layer**: High-speed data access

### Process Management
- **Process Isolation**: Separate memory spaces
- **Resource Tracking**: CPU and memory usage
- **Signal Handling**: Inter-process communication
- **Scheduling**: Fair process scheduling

## 🔧 Advanced Features

### Memory-Mapped Arrays
```python
# Create memory-mapped NumPy array
shape = (10000, 10000)
addr, array = kos.create_numpy_array(shape, np.float32)

# Direct array operations
array *= 2.0
result = np.sum(array)
```

### Process Execution
```python
from kos.advlayer.process_manager import ProcessManager

pm = ProcessManager()

# Execute command
result = pm.execute_command('echo "Hello from KOS"')
print(result['stdout'])

# Manage processes
pm.create_process("worker", "/usr/bin/worker")
pm.terminate_process(pid)
```

### Custom Kernels
```python
# Register Python kernel
python_kernel = '''
def process_data(input_array):
    return input_array * 2 + 1
'''

kos.register_kernel("process_data", python_kernel, kernel_type="python")

# Execute kernel
result = kos.execute_kernel("process_data", args=(data,))
```

## 📊 Performance

KOS achieves excellent performance through:
- **Binary VFS Format**: Fast serialization without pickle overhead
- **Memory Caching**: Intelligent segment caching
- **Background Sync**: Asynchronous disk operations
- **Zero-Copy Operations**: Where possible

## 🛠️ Development

### Running Examples
```python
# Start master node
python examples/start_master_node.py

# Start worker node  
python examples/start_worker_node.py

# Run unified demo
python examples/unified_hardware_demo.py
```

### Testing
```bash
python -m pytest tests/
```

## 🤝 Contributing

We welcome contributions! Areas of interest:
- Performance optimizations
- Additional system services
- Documentation improvements
- Bug fixes and testing

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with pure Python - no external dependencies
- Inspired by Unix/Linux design principles
- Custom VFS implementation for reliability

## 📞 Contact

- **GitHub Issues**: [Report bugs or request features](https://github.com/DarsheeeGamer/KOS/issues)
- **Discussions**: [Join the conversation](https://github.com/DarsheeeGamer/KOS/discussions)

## 🎯 Roadmap

- [ ] Network filesystem support
- [ ] Compression for VFS
- [ ] Multi-threading improvements
- [ ] GUI interface
- [ ] Container support
- [ ] Distributed VFS

---

**Note**: KOS is under active development. APIs may change between versions.
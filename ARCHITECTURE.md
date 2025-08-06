# KOS Architecture Documentation

## Overview

KOS (Kaede Operating System) is a complete operating system implementation in Python featuring:
- **Real Memory Management** with allocation tracking, garbage collection, and memory mapping
- **Python Integration** with VFS-isolated package management and virtual environments
- **Layered Architecture** separating core services (KLayer) from advanced features (KADVLayer)

## Core Components

### 1. Memory Management (`kos/core/memory.py`)

#### Real Memory Allocation
- **Page-aligned allocation** with configurable page size
- **Memory pools** for efficient small allocations (16B to 1MB)
- **Free list management** with coalescing
- **Memory types**: HEAP, STACK, SHARED, MAPPED, KERNEL, USER, CACHE, BUFFER

#### Features
```python
# Allocate memory
addr = memory.malloc(1024)  # Allocate 1KB

# Read/Write
memory.write(addr, b"Hello World")
data = memory.read(addr, 11)

# Reallocation
new_addr = memory.realloc(addr, 2048)  # Grow to 2KB

# Shared memory
shm_addr = memory.create_shared_memory("myshm", 4096)

# Memory-mapped files
mmap_addr = memory.mmap("/path/to/file", size=1024)

# Process memory tracking
usage = memory.get_process_memory(pid)
```

#### Memory Statistics
- Real-time memory usage tracking
- Process-specific memory accounting
- Swap memory monitoring
- Buffer and cache statistics

### 2. Python Environment (`kos/python/interpreter.py`)

#### VFS-Integrated Python
- **Custom import hooks** for loading modules from VFS
- **Isolated namespaces** for secure execution
- **Package management** with pip support
- **Virtual environments** within VFS

#### Features
```python
# Execute Python code
result = python.execute("print('Hello from VFS Python')")

# Install packages to VFS
python.install_package("requests")
python.install_package("numpy", version="1.21.0")

# Create virtual environment
python.create_virtualenv("myproject")

# Execute Python file from VFS
python.execute_file("/home/user/script.py")
```

#### Package Management
- **pip integration** downloads real packages
- **Wheel support** for binary packages
- **Tarball support** for source distributions
- **Dependency tracking** in VFS database

### 3. KLayer (Core OS Layer)

#### Services Provided
1. **File System Operations** - VFS with pickle persistence
2. **Process Management** - Creation, execution, signaling
3. **User Management** - Multi-user with roles
4. **Memory Management** - Real allocation and tracking
5. **Python Support** - Integrated interpreter and pip
6. **Device Abstraction** - Virtual devices
7. **Environment Variables** - Process environments
8. **Permissions** - Unix-style file permissions

#### API Examples
```python
# Initialize KLayer
klayer = KLayer(disk_file="system.kdsk", memory_size=8*1024*1024*1024)

# Memory operations
addr = klayer.mem_allocate(1024)
klayer.mem_write(addr, b"data")
data = klayer.mem_read(addr, 4)
klayer.mem_free(addr)

# Python operations
klayer.python_install_package("django")
result = klayer.python_execute("import django; print(django.__version__)")

# Process with memory tracking
pid = klayer.process_create("python", ["-c", "print('test')"])
mem_usage = klayer.mem_get_process_usage(pid)
```

### 4. KADVLayer (Advanced Services)

Built on top of KLayer, provides:
- **Networking** - TCP/IP stack, DNS, HTTP
- **Services** - systemd-like service management
- **Security** - Firewall, VPN, SSL/TLS
- **Monitoring** - System metrics and profiling
- **Containers** - Docker-like containers
- **Databases** - SQL support
- **Web Services** - HTTP server, REST APIs

## Memory Architecture

### Allocation Strategy
```
┌─────────────────────────────────────┐
│         Total Memory (8GB)          │
├─────────────────────────────────────┤
│    Kernel Space (Reserved)          │
├─────────────────────────────────────┤
│    User Space                       │
│    ┌───────────────────────┐        │
│    │   Heap Allocations    │        │
│    ├───────────────────────┤        │
│    │   Memory-Mapped Files │        │
│    ├───────────────────────┤        │
│    │   Shared Memory       │        │
│    ├───────────────────────┤        │
│    │   Stack Space         │        │
│    └───────────────────────┘        │
├─────────────────────────────────────┤
│    Free Space                       │
└─────────────────────────────────────┘
```

### Memory Lifecycle
1. **Allocation** - Find suitable block or allocate new
2. **Usage** - Read/write with permission checks
3. **Reallocation** - Grow/shrink with data preservation
4. **Deallocation** - Return to free list with coalescing
5. **Garbage Collection** - Reclaim orphaned blocks

## Python Integration Architecture

### Import System
```
User Code → Import Hook → VFS Lookup → Module Loading
                ↓              ↓              ↓
           Check Paths    Find .py file   Compile & Execute
                              ↓
                    /usr/lib/python/site-packages/
                    /usr/local/lib/python/
                    /home/user/.local/lib/python/
```

### Package Installation Flow
```
pip install request
        ↓
Download from PyPI → Extract Package → Copy to VFS → Update Database
        ↓                   ↓              ↓              ↓
   Using real pip    .whl or .tar.gz  Site-packages  installed.json
```

### Virtual Environment Structure
```
/home/user/venvs/myproject/
├── bin/
│   ├── activate       # Shell activation script
│   └── pip           # VFS-aware pip wrapper
├── lib/
│   └── python/
│       └── site-packages/  # Isolated packages
├── include/          # Header files
└── pyvenv.cfg       # Configuration
```

## Shell Commands

### Python Commands
- `python [file.py]` - Run Python interpreter or script
- `python -c "code"` - Execute Python code
- `pip install <package>` - Install package to VFS
- `pip uninstall <package>` - Remove package
- `pip list` - List installed packages
- `venv create <name>` - Create virtual environment

### Memory Commands
- `free [-h]` - Display memory usage
- `memstat [pid]` - Detailed memory statistics
- `gc` - Run garbage collection

## Performance Characteristics

### Memory Performance
- **Allocation**: O(1) for small sizes using pools, O(n) for large
- **Deallocation**: O(1) with lazy coalescing
- **Reallocation**: O(1) if space available, O(n) if relocation needed
- **Garbage Collection**: O(n) where n is number of allocations

### Python Performance
- **Import**: First import slower (compilation), cached subsequently
- **Package Install**: Network-bound for download, I/O-bound for extraction
- **Execution**: Near-native Python speed with VFS overhead

## Security Model

### Memory Protection
- **Permission flags**: READ, WRITE, EXECUTE per allocation
- **Process isolation**: Memory tracked per process
- **Bounds checking**: Prevent buffer overflows
- **Automatic cleanup**: Orphaned memory reclaimed

### Python Sandboxing
- **Namespace isolation**: Separate execution contexts
- **VFS restriction**: Can't access host filesystem directly
- **Import control**: Custom import hooks filter modules
- **Resource limits**: Memory quotas per process

## Best Practices

### Memory Management
1. Always free allocated memory when done
2. Use appropriate allocation size to minimize fragmentation
3. Prefer realloc over free+malloc for resizing
4. Use shared memory for IPC
5. Run garbage collection periodically

### Python Integration
1. Install packages to appropriate virtualenv
2. Use namespaces to isolate different applications
3. Cache compiled modules for performance
4. Handle import errors gracefully
5. Clean up virtualenvs when no longer needed

## Troubleshooting

### Memory Issues
- **Out of memory**: Check `free` command, run `gc`
- **Memory leaks**: Use `memstat` to track per-process usage
- **Fragmentation**: Monitor free list size, consider reboot

### Python Issues
- **Import errors**: Check VFS paths with `ls /usr/lib/python`
- **Package conflicts**: Use virtual environments
- **Performance**: Check if modules are being recompiled

## Future Enhancements

### Planned Features
1. **Memory compression** for inactive pages
2. **Swap file support** for memory overflow
3. **NUMA awareness** for multi-socket systems
4. **JIT compilation** for Python hot paths
5. **Package caching** for offline installation
6. **Binary package building** from source
7. **Memory-mapped databases** for persistence
8. **Copy-on-write** for process forking
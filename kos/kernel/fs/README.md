# KOS Filesystem Implementation

A complete filesystem implementation in C/C++ with Python bindings for the KOS operating system. This implementation provides a full VFS (Virtual File System) layer with advanced features including caching, locking, extended attributes, and ACLs.

## Architecture Overview

The KOS filesystem is built on a layered architecture:

```
┌─────────────────────────────────────────┐
│            Python Bindings              │
│         (fs_wrapper.py)                 │
├─────────────────────────────────────────┤
│             System Calls                │
│         (kos_sys_* functions)           │
├─────────────────────────────────────────┤
│               VFS Layer                 │
│    (vfs.c - Virtual File System)       │
├─────────────────────────────────────────┤
│  ┌─────────────┬──────────────────────┐ │
│  │   Inode     │    Directory Cache   │ │
│  │ Management  │      (dcache.c)      │ │
│  │ (inode.c)   │                      │ │
│  └─────────────┴──────────────────────┘ │
├─────────────────────────────────────────┤
│  ┌─────────────┬──────────────────────┐ │
│  │    File     │    Path Resolution   │ │
│  │ Operations  │      (namei.c)       │ │
│  │  (file.c)   │                      │ │
│  └─────────────┴──────────────────────┘ │
├─────────────────────────────────────────┤
│          Filesystem Drivers             │
│     (RAMFS, DEVFS, PROCFS, etc.)       │
└─────────────────────────────────────────┘
```

## Core Components

### 1. VFS Layer (vfs.c)

The Virtual File System layer provides:
- Mount/unmount operations
- Filesystem registration
- File descriptor management
- System call implementations
- Global filesystem state management

**Key Functions:**
- `kos_mount()` - Mount filesystems
- `kos_umount()` - Unmount filesystems
- `kos_sys_open()` - Open files
- `kos_sys_read()` - Read from files
- `kos_sys_write()` - Write to files
- `kos_sys_close()` - Close files

### 2. Inode Management (inode.c)

Manages filesystem inodes with:
- Inode allocation and deallocation
- Reference counting
- Hash table management
- Permission checking
- Metadata management

**Key Features:**
- Thread-safe operations with rwlocks
- Hash table for fast inode lookup
- Generic permission checking
- Time stamp management
- Hard link support

### 3. Directory Entry Cache (dcache.c)

Implements a sophisticated directory entry cache:
- LRU (Least Recently Used) eviction
- Hash table for fast lookups
- Cache timeout and invalidation
- Statistics tracking
- Thread-safe operations

**Cache Features:**
- Configurable maximum entries
- Time-based expiration
- Automatic pruning
- Hit/miss statistics

### 4. File Operations (file.c)

Comprehensive file handling:
- Read/write/seek operations
- File locking (POSIX and flock)
- Permission checking
- Reference counting
- Synchronization support

**Locking Features:**
- Advisory and mandatory locking
- Read/write lock conflicts
- Process-specific lock tracking
- Lock inheritance and cleanup

### 5. Path Name Resolution (namei.c)

Advanced path resolution with:
- Symbolic link following
- Mount point traversal
- Relative/absolute path handling
- Component-by-component lookup
- Security checks

**Path Features:**
- Symlink loop detection
- Permission checking at each level
- Mount point crossing
- Special component handling (., ..)

## Data Structures

### Core Structures

```c
struct kos_inode {
    uint64_t ino;                    // Inode number
    uint32_t mode;                   // File mode and permissions
    uint32_t nlink;                  // Number of hard links
    uid_t uid, gid;                  // Owner and group
    off_t size;                      // File size
    time_t atime, mtime, ctime;      // Time stamps
    // ... extended attributes, ACLs, locks
};

struct kos_dentry {
    char name[KOS_MAX_FILENAME + 1]; // Entry name
    struct kos_inode *inode;         // Associated inode
    struct kos_dentry *parent;       // Parent directory
    // ... hash linkage, caching info
};

struct kos_file {
    struct kos_dentry *dentry;       // Associated dentry
    off_t position;                  // Current position
    uint32_t flags;                  // Open flags
    // ... locks, operations
};
```

### Extended Features

- **Extended Attributes**: Key-value pairs for metadata
- **Access Control Lists**: Fine-grained permissions
- **File Locks**: POSIX and BSD-style locking
- **Mount Points**: Filesystem mounting support

## Python Bindings

The Python bindings provide a high-level interface:

```python
import kos.kernel.fs.fs_wrapper as kos_fs

# File operations
with kos_fs.open("/path/to/file", "w") as f:
    f.write("Hello, KOS!")

# Path operations
if kos_fs.exists("/path/to/file"):
    stat_info = kos_fs.stat("/path/to/file")
    print(f"File size: {stat_info['st_size']}")

# Directory operations
kos_fs.mkdir("/new/directory", 0o755)

# Mount operations
kos_fs.mount("/dev/sda1", "/mnt", "ext4")
```

## Building and Installation

### Prerequisites

- GCC compiler with C11 support
- POSIX threads library
- Python 3.6+ (for bindings)
- Make build system

### Build Instructions

```bash
# Build the shared library
make

# Build with debug symbols
make debug

# Build and run tests
make test
./test_fs

# Install system-wide
sudo make install
```

### Build Targets

- `all` - Build shared library (default)
- `debug` - Build with debug symbols and assertions
- `test` - Build test executable
- `install` - Install library and headers system-wide
- `clean` - Remove build artifacts

## Usage Examples

### C API Usage

```c
#include "fs.h"

int main() {
    // Initialize VFS
    kos_vfs_init();
    
    // Open a file
    int fd = kos_sys_open("/tmp/test.txt", KOS_O_CREAT | KOS_O_WRONLY, 0644);
    
    // Write data
    const char *data = "Hello, World!";
    kos_sys_write(fd, data, strlen(data));
    
    // Close file
    kos_sys_close(fd);
    
    // Cleanup
    kos_vfs_cleanup();
    return 0;
}
```

### Python API Usage

```python
import kos.kernel.fs.fs_wrapper as fs

# High-level file operations
with fs.open("/tmp/example.txt", "w") as f:
    f.write("KOS Filesystem Example")
    f.seek(0)
    content = f.read()

# Path utilities
if fs.exists("/tmp/example.txt"):
    stats = fs.stat("/tmp/example.txt")
    print(f"Size: {stats['st_size']} bytes")

# Directory operations
fs.mkdir("/tmp/new_dir")
print(f"Is directory: {fs.isdir('/tmp/new_dir')}")
```

## Features

### Core Features

- ✅ **VFS Layer**: Complete virtual filesystem implementation
- ✅ **Inode Management**: Full inode operations with caching
- ✅ **Directory Cache**: LRU cache with expiration
- ✅ **File Operations**: Read, write, seek, and locking
- ✅ **Path Resolution**: Complete path name resolution
- ✅ **Mount Support**: Filesystem mounting and unmounting

### Advanced Features

- ✅ **File Locking**: POSIX and BSD-style locks
- ✅ **Extended Attributes**: Key-value metadata storage
- ✅ **Access Control Lists**: Fine-grained permissions
- ✅ **Symbolic Links**: Full symlink support with loop detection
- ✅ **Thread Safety**: All operations are thread-safe
- ✅ **Reference Counting**: Automatic resource management

### Performance Features

- ✅ **Hash Tables**: Fast inode and dentry lookup
- ✅ **LRU Cache**: Efficient memory usage
- ✅ **Lock Optimization**: Minimal lock contention
- ✅ **Lazy Operations**: Deferred expensive operations

## Testing

The implementation includes comprehensive tests:

```bash
# Run C tests
make test
./test_fs

# Run Python tests
python3 fs_wrapper.py
```

### Test Coverage

- File creation, reading, and writing
- Directory operations
- Path resolution
- Mount/unmount operations
- Lock functionality
- Cache performance
- Error handling

## Configuration

### Compile-time Configuration

Key constants in `fs.h`:

```c
#define KOS_MAX_FILENAME 255        // Maximum filename length
#define KOS_MAX_PATH 4096           // Maximum path length
#define KOS_INODE_HASH_SIZE 1024    // Inode hash table size
#define KOS_DENTRY_HASH_SIZE 1024   // Dentry hash table size
```

### Runtime Configuration

Cache parameters in `dcache.c`:

```c
#define KOS_DCACHE_MAX_ENTRIES 10000  // Maximum cache entries
#define KOS_DCACHE_TIMEOUT 300        // Cache timeout (seconds)
```

## Error Handling

The implementation provides comprehensive error handling:

- **C API**: Returns negative error codes (errno style)
- **Python API**: Raises specific exception types
- **Thread Safety**: All error paths are thread-safe
- **Resource Cleanup**: Automatic cleanup on errors

### Common Error Codes

- `ENOENT` - File or directory not found
- `EACCES` - Permission denied
- `EEXIST` - File already exists
- `ENOMEM` - Out of memory
- `EINVAL` - Invalid argument

## Performance Characteristics

### Time Complexity

- **File Open**: O(log n) average case with hash tables
- **Directory Lookup**: O(1) average case with caching
- **Path Resolution**: O(components) with caching
- **Inode Operations**: O(1) with hash table lookup

### Memory Usage

- **Inode**: ~200 bytes per inode
- **Dentry**: ~300 bytes per directory entry
- **File**: ~100 bytes per open file
- **Cache**: Configurable maximum memory usage

## Security

### Permission Model

- Traditional Unix permissions (owner, group, other)
- Extended ACLs for fine-grained control
- Capability-based access control
- SELinux context support (planned)

### Security Features

- Path traversal protection
- Symlink loop detection
- Permission checking at every level
- Secure temporary file creation

## Future Enhancements

### Planned Features

- [ ] **Journaling**: Transaction support for consistency
- [ ] **Compression**: Transparent file compression
- [ ] **Encryption**: File-level encryption support
- [ ] **Quotas**: User and group disk quotas
- [ ] **Snapshots**: Filesystem snapshots
- [ ] **Replication**: Distributed filesystem support

### Performance Improvements

- [ ] **Read-ahead**: Predictive file reading
- [ ] **Write-behind**: Asynchronous write operations
- [ ] **Compression**: On-the-fly compression
- [ ] **Deduplication**: Block-level deduplication

## Contributing

### Development Guidelines

1. Follow Linux kernel coding style
2. All functions must be thread-safe
3. Comprehensive error handling required
4. Unit tests for all new features
5. Documentation for public APIs

### Code Structure

```
kos/kernel/fs/
├── fs.h              # Main header file
├── vfs.c             # VFS implementation
├── inode.c           # Inode management
├── dcache.c          # Directory cache
├── file.c            # File operations
├── namei.c           # Path resolution
├── fs_wrapper.py     # Python bindings
├── Makefile          # Build system
└── README.md         # This file
```

## License

This filesystem implementation is part of the KOS operating system project.

## Authors

- KOS Development Team
- Filesystem implementation by Claude Code

---

For more information about KOS, visit the main project repository.
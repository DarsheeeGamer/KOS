# Memory Management API

Comprehensive API documentation for KOS memory management subsystem.

## Overview

The KOS memory management system provides both high-level Python interfaces and low-level kernel interfaces for memory allocation, page management, and virtual memory operations.

## Core Classes

### MemoryManager

Main interface for system memory management.

```python
from kos.memory.manager import MemoryManager

class MemoryManager:
    """
    High-level memory management interface.
    
    Provides unified access to memory allocation, virtual memory management,
    and system memory monitoring.
    """
    
    def __init__(self):
        """Initialize memory manager with system defaults."""
        
    def initialize(self) -> bool:
        """
        Initialize memory management subsystem.
        
        Returns:
            bool: True if initialization successful, False otherwise
            
        Raises:
            MemoryError: If initialization fails
        """
        
    def allocate(self, size: int, alignment: int = 8) -> int:
        """
        Allocate memory block.
        
        Args:
            size: Size in bytes to allocate
            alignment: Memory alignment requirement (default: 8)
            
        Returns:
            int: Memory address (0 if allocation failed)
            
        Example:
            >>> mgr = MemoryManager()
            >>> addr = mgr.allocate(1024)
            >>> if addr:
            ...     print(f"Allocated at: 0x{addr:x}")
        """
        
    def deallocate(self, address: int, size: int) -> bool:
        """
        Deallocate memory block.
        
        Args:
            address: Memory address to deallocate
            size: Size of the block
            
        Returns:
            bool: True if deallocation successful
        """
        
    def mmap(self, addr: int, length: int, prot: int, flags: int, 
             fd: int, offset: int) -> int:
        """
        Memory map operation.
        
        Args:
            addr: Preferred address (0 for system choice)
            length: Length of mapping
            prot: Protection flags (PROT_READ, PROT_WRITE, PROT_EXEC)
            flags: Mapping flags (MAP_PRIVATE, MAP_SHARED, etc.)
            fd: File descriptor (-1 for anonymous)
            offset: File offset
            
        Returns:
            int: Mapped address or -1 on error
        """
        
    def munmap(self, addr: int, length: int) -> int:
        """
        Unmap memory region.
        
        Args:
            addr: Address to unmap
            length: Length to unmap
            
        Returns:
            int: 0 on success, -1 on error
        """
        
    def mprotect(self, addr: int, length: int, prot: int) -> int:
        """
        Change memory protection.
        
        Args:
            addr: Address of region
            length: Length of region
            prot: New protection flags
            
        Returns:
            int: 0 on success, -1 on error
        """
        
    def get_memory_stats(self) -> dict:
        """
        Get system memory statistics.
        
        Returns:
            dict: Memory statistics
            {
                'total_memory': int,    # Total system memory
                'free_memory': int,     # Available memory
                'used_memory': int,     # Used memory
                'cached_memory': int,   # Cached memory
                'buffer_memory': int,   # Buffer memory
                'swap_total': int,      # Total swap space
                'swap_free': int        # Free swap space
            }
        """
```

### KOSAllocator

General-purpose memory allocator with debugging support.

```python
from kos.memory.allocator import KOSAllocator

class KOSAllocator:
    """
    KOS memory allocator with debugging and tracking capabilities.
    
    Provides malloc/free style interface with additional debugging
    features and memory tracking.
    """
    
    def __init__(self, debug: bool = False):
        """
        Initialize allocator.
        
        Args:
            debug: Enable debug tracking and validation
        """
        
    def malloc(self, size: int) -> int:
        """
        Allocate memory block.
        
        Args:
            size: Size in bytes
            
        Returns:
            int: Pointer to allocated memory (0 if failed)
            
        Example:
            >>> allocator = KOSAllocator()
            >>> ptr = allocator.malloc(1024)
            >>> # Use memory...
            >>> allocator.free(ptr)
        """
        
    def calloc(self, num: int, size: int) -> int:
        """
        Allocate zero-initialized memory.
        
        Args:
            num: Number of elements
            size: Size of each element
            
        Returns:
            int: Pointer to allocated memory
        """
        
    def realloc(self, ptr: int, new_size: int) -> int:
        """
        Resize memory block.
        
        Args:
            ptr: Existing pointer
            new_size: New size
            
        Returns:
            int: New pointer (may be different from input)
        """
        
    def free(self, ptr: int) -> None:
        """
        Free memory block.
        
        Args:
            ptr: Pointer to free
        """
        
    def aligned_alloc(self, alignment: int, size: int) -> int:
        """
        Allocate aligned memory.
        
        Args:
            alignment: Alignment requirement (power of 2)
            size: Size in bytes
            
        Returns:
            int: Aligned pointer
        """
        
    def get_allocation_stats(self) -> dict:
        """
        Get allocator statistics.
        
        Returns:
            dict: Allocation statistics
            {
                'total_allocated': int,
                'total_freed': int,
                'current_usage': int,
                'peak_usage': int,
                'allocation_count': int,
                'free_count': int
            }
        """
```

### PageFrameAllocator

Low-level page frame allocation for kernel memory management.

```python
from kos.memory.page import PageFrameAllocator, PageFrame

class PageFrame:
    """
    Represents a physical memory page frame.
    
    Attributes:
        physical_addr: Physical address of the page
        virtual_addr: Virtual address (if mapped)
        ref_count: Reference count
        flags: Page flags (dirty, locked, etc.)
    """
    
    def __init__(self, physical_addr: int):
        """
        Initialize page frame.
        
        Args:
            physical_addr: Physical address of the page
        """
        
    def get(self) -> None:
        """Increment reference count."""
        
    def put(self) -> None:
        """Decrement reference count."""
        
    def is_dirty(self) -> bool:
        """Check if page is dirty."""
        
    def set_dirty(self) -> None:
        """Mark page as dirty."""
        
    def clear_dirty(self) -> None:
        """Clear dirty flag."""
        
    def is_locked(self) -> bool:
        """Check if page is locked."""
        
    def lock(self) -> None:
        """Lock page in memory."""
        
    def unlock(self) -> None:
        """Unlock page."""
        
    def map_virtual(self, virtual_addr: int) -> None:
        """Map page to virtual address."""
        
    def unmap_virtual(self) -> None:
        """Unmap virtual address."""

class PageFrameAllocator:
    """
    Physical page frame allocator.
    
    Manages allocation and deallocation of physical memory pages
    using buddy allocation algorithm.
    """
    
    def __init__(self):
        """Initialize page frame allocator."""
        
    def alloc_page(self) -> PageFrame:
        """
        Allocate single page frame.
        
        Returns:
            PageFrame: Allocated page frame
            
        Raises:
            MemoryError: If no pages available
        """
        
    def alloc_pages(self, order: int) -> List[PageFrame]:
        """
        Allocate multiple contiguous pages.
        
        Args:
            order: Allocation order (2^order pages)
            
        Returns:
            List[PageFrame]: List of allocated pages
        """
        
    def free_page(self, page: PageFrame) -> None:
        """
        Free single page frame.
        
        Args:
            page: Page frame to free
        """
        
    def free_pages(self, pages: List[PageFrame]) -> None:
        """
        Free multiple page frames.
        
        Args:
            pages: List of pages to free
        """
        
    def get_free_pages(self) -> int:
        """
        Get number of free pages.
        
        Returns:
            int: Number of free pages available
        """
```

## Kernel Memory APIs

### Buddy Allocator

Low-level buddy allocator for kernel memory.

```python
from kos.kernel.mm.mm_wrapper import (
    buddy_alloc, buddy_free, buddy_init, buddy_stats
)

def buddy_init(total_memory: int) -> int:
    """
    Initialize buddy allocator.
    
    Args:
        total_memory: Total memory size in bytes
        
    Returns:
        int: 0 on success, negative on error
    """

def buddy_alloc(order: int) -> int:
    """
    Allocate memory using buddy allocator.
    
    Args:
        order: Allocation order (2^order pages)
        
    Returns:
        int: Physical address of allocated memory (0 if failed)
        
    Example:
        >>> # Allocate 4 pages (16KB on 4KB page system)
        >>> addr = buddy_alloc(2)
        >>> if addr:
        ...     print(f"Allocated at: 0x{addr:x}")
        ...     buddy_free(addr, 2)
    """

def buddy_free(addr: int, order: int) -> int:
    """
    Free memory allocated by buddy allocator.
    
    Args:
        addr: Address to free
        order: Original allocation order
        
    Returns:
        int: 0 on success, negative on error
    """

def buddy_stats() -> dict:
    """
    Get buddy allocator statistics.
    
    Returns:
        dict: Statistics including free blocks by order
    """
```

### Slab Allocator

Object caching allocator for frequently allocated objects.

```python
from kos.kernel.mm.mm_wrapper import (
    slab_create, slab_destroy, slab_alloc, slab_free
)

def slab_create(name: str, object_size: int, alignment: int) -> int:
    """
    Create slab cache.
    
    Args:
        name: Cache name for debugging
        object_size: Size of objects in this cache
        alignment: Alignment requirement
        
    Returns:
        int: Cache ID (positive) or error code (negative)
    """

def slab_alloc(cache_id: int) -> int:
    """
    Allocate object from slab cache.
    
    Args:
        cache_id: Cache ID from slab_create
        
    Returns:
        int: Address of allocated object (0 if failed)
    """

def slab_free(cache_id: int, addr: int) -> int:
    """
    Free object to slab cache.
    
    Args:
        cache_id: Cache ID
        addr: Address to free
        
    Returns:
        int: 0 on success, negative on error
    """

def slab_destroy(cache_id: int) -> int:
    """
    Destroy slab cache.
    
    Args:
        cache_id: Cache ID to destroy
        
    Returns:
        int: 0 on success, negative on error
    """
```

## Memory Constants

### Protection Flags

```python
# Memory protection flags for mmap/mprotect
PROT_NONE = 0x0      # No access
PROT_READ = 0x1      # Read access
PROT_WRITE = 0x2     # Write access
PROT_EXEC = 0x4      # Execute access

# Common combinations
PROT_RW = PROT_READ | PROT_WRITE
PROT_RWX = PROT_READ | PROT_WRITE | PROT_EXEC
```

### Mapping Flags

```python
# Memory mapping flags
MAP_SHARED = 0x01      # Shared mapping
MAP_PRIVATE = 0x02     # Private mapping
MAP_ANONYMOUS = 0x20   # Anonymous mapping (no file)
MAP_FIXED = 0x10       # Fixed address mapping
MAP_GROWSDOWN = 0x0100 # Stack-like segment
MAP_LOCKED = 0x2000    # Lock pages in memory
MAP_POPULATE = 0x8000  # Populate page tables
```

### Memory Zones

```python
# Memory zone types
ZONE_DMA = 0      # DMA-capable memory
ZONE_NORMAL = 1   # Normal memory
ZONE_HIGHMEM = 2  # High memory (32-bit systems)
```

## Error Handling

### Exception Types

```python
from kos.exceptions import MemoryError, AllocationError

class MemoryError(KOSError):
    """Base memory management error."""
    pass

class AllocationError(MemoryError):
    """Memory allocation failed."""
    pass

class MappingError(MemoryError):
    """Memory mapping operation failed."""
    pass

class ProtectionError(MemoryError):
    """Memory protection change failed."""
    pass
```

### Error Codes

```python
# Memory management error codes
ENOMEM = -12     # Out of memory
EINVAL = -22     # Invalid argument
EACCES = -13     # Permission denied
EFAULT = -14     # Bad address
ENXIO = -6       # No such device or address
```

## Usage Examples

### Basic Memory Allocation

```python
from kos.memory.manager import MemoryManager
from kos.exceptions import MemoryError

# Initialize memory manager
memory_mgr = MemoryManager()
memory_mgr.initialize()

try:
    # Allocate 1MB
    addr = memory_mgr.allocate(1024 * 1024)
    if addr:
        print(f"Allocated 1MB at: 0x{addr:x}")
        
        # Use the memory...
        
        # Free when done
        memory_mgr.deallocate(addr, 1024 * 1024)
    else:
        print("Allocation failed")
        
except MemoryError as e:
    print(f"Memory error: {e}")
```

### Memory Mapping

```python
import os
from kos.memory.manager import MemoryManager

memory_mgr = MemoryManager()

# Create temporary file
with open('/tmp/test_file', 'wb') as f:
    f.write(b'x' * 4096)  # 4KB file

# Open file for mapping
fd = os.open('/tmp/test_file', os.O_RDWR)

try:
    # Map file into memory
    addr = memory_mgr.mmap(
        0,                                    # Let system choose address
        4096,                                # Map 4KB
        memory_mgr.PROT_READ | memory_mgr.PROT_WRITE,  # Read/write access
        memory_mgr.MAP_SHARED,               # Shared mapping
        fd,                                  # File descriptor
        0                                    # Offset
    )
    
    if addr != -1:
        print(f"File mapped at: 0x{addr:x}")
        
        # Access mapped memory...
        
        # Unmap when done
        memory_mgr.munmap(addr, 4096)
    
finally:
    os.close(fd)
    os.unlink('/tmp/test_file')
```

### Page Frame Management

```python
from kos.memory.page import PageFrameAllocator
from kos.exceptions import MemoryError

# Initialize page allocator
page_allocator = PageFrameAllocator()

try:
    # Allocate single page
    page = page_allocator.alloc_page()
    print(f"Allocated page at: 0x{page.physical_addr:x}")
    
    # Use page...
    page.set_dirty()
    
    # Check page status
    if page.is_dirty():
        print("Page is dirty")
    
    # Free page
    page_allocator.free_page(page)
    
except MemoryError as e:
    print(f"Page allocation failed: {e}")
```

### Kernel Memory Operations

```python
from kos.kernel.mm.mm_wrapper import buddy_alloc, buddy_free, slab_create, slab_alloc

# Initialize kernel memory (typically done at boot)
# buddy_init(total_memory_size)

# Allocate kernel memory using buddy allocator
# Allocate 4 pages (order 2)
addr = buddy_alloc(2)
if addr:
    print(f"Kernel memory allocated at: 0x{addr:x}")
    
    # Use memory...
    
    # Free when done
    buddy_free(addr, 2)

# Create slab cache for fixed-size objects
cache_id = slab_create("my_objects", 64, 8)  # 64-byte objects, 8-byte aligned
if cache_id > 0:
    # Allocate object from cache
    obj_addr = slab_alloc(cache_id)
    if obj_addr:
        print(f"Object allocated at: 0x{obj_addr:x}")
        
        # Use object...
        
        # Free object back to cache
        slab_free(cache_id, obj_addr)
```

## Performance Considerations

### Allocation Strategies

1. **Small allocations (< 4KB)**: Use slab allocator for frequently allocated objects
2. **Medium allocations (4KB - 1MB)**: Use buddy allocator or general allocator
3. **Large allocations (> 1MB)**: Use direct page allocation or memory mapping

### Memory Alignment

- Use aligned allocations for performance-critical code
- Align to cache line boundaries (typically 64 bytes) for best performance
- Consider NUMA topology for large allocations

### Memory Mapping Best Practices

- Use `MAP_POPULATE` for immediate page allocation
- Use `MAP_LOCKED` for real-time applications
- Prefer `MAP_PRIVATE` for copy-on-write semantics
- Use appropriate protection flags to prevent security issues

## Debugging and Monitoring

### Memory Statistics

```python
# Get system memory statistics
stats = memory_mgr.get_memory_stats()
print(f"Total memory: {stats['total_memory'] // (1024*1024)} MB")
print(f"Free memory: {stats['free_memory'] // (1024*1024)} MB")
print(f"Memory usage: {(stats['used_memory'] / stats['total_memory']) * 100:.1f}%")

# Get allocator statistics
alloc_stats = allocator.get_allocation_stats()
print(f"Current usage: {alloc_stats['current_usage']} bytes")
print(f"Peak usage: {alloc_stats['peak_usage']} bytes")
```

### Memory Leak Detection

```python
# Enable debug mode for allocation tracking
debug_allocator = KOSAllocator(debug=True)

# Perform operations...

# Check for leaks
stats = debug_allocator.get_allocation_stats()
if stats['allocation_count'] != stats['free_count']:
    print(f"Memory leak detected: {stats['allocation_count'] - stats['free_count']} unfreed allocations")
```

## Thread Safety

All memory management APIs are thread-safe unless otherwise noted. However, for performance in single-threaded applications, thread-local allocators may be available:

```python
# Get thread-local allocator for better performance
local_allocator = KOSAllocator.get_thread_local()
```

## Integration with Other Subsystems

### Process Memory Management

The memory manager integrates with the process manager to provide per-process memory tracking and limits:

```python
# Set memory limit for process
process_mgr.set_memory_limit(process_id, 100 * 1024 * 1024)  # 100MB limit
```

### Filesystem Integration

Memory mapping integrates with the filesystem for file-backed mappings:

```python
# Memory-map a file through VFS
vfs = VirtualFileSystem()
fd = vfs.open('/data/largefile.dat', 'r')
addr = memory_mgr.mmap(0, file_size, PROT_READ, MAP_PRIVATE, fd, 0)
```

### Security Integration

All memory operations are subject to security policy enforcement:

```python
# Memory allocations respect security limits
security_mgr = SecurityManager()
if not security_mgr.check_memory_limit(requested_size):
    raise PermissionError("Memory allocation exceeds security limit")
```
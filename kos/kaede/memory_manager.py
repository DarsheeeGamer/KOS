"""
Kaede Memory Manager
===================

High-performance memory management system providing:
- Automatic garbage collection (Python-style)
- Manual memory management (C++-style)
- Smart pointers (unique_ptr, shared_ptr, weak_ptr)
- Memory pools and arenas
- Memory debugging and leak detection
- RAII (Resource Acquisition Is Initialization)
- Copy elision and move semantics
"""

import gc
import sys
import threading
import time
import weakref
from typing import Dict, List, Any, Optional, Set, Generic, TypeVar, Callable
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum
import ctypes
import mmap

T = TypeVar('T')

class AllocationStrategy(Enum):
    """Memory allocation strategies."""
    POOL = "pool"
    ARENA = "arena" 
    STACK = "stack"
    HEAP = "heap"
    MMAP = "mmap"

@dataclass
class MemoryBlock:
    """Represents a memory block."""
    address: int
    size: int
    allocated: bool = True
    owner: Optional[str] = None
    timestamp: float = 0.0
    
class MemoryPool:
    """Fixed-size memory pool for efficient allocation."""
    
    def __init__(self, block_size: int, pool_size: int = 1024):
        self.block_size = block_size
        self.pool_size = pool_size
        self.free_blocks: deque = deque()
        self.allocated_blocks: Set[int] = set()
        self._initialize_pool()
        
    def _initialize_pool(self):
        """Initialize the memory pool."""
        # Allocate a large chunk and divide into blocks
        total_size = self.block_size * self.pool_size
        self.base_address = ctypes.addressof(ctypes.create_string_buffer(total_size))
        
        for i in range(self.pool_size):
            block_addr = self.base_address + (i * self.block_size)
            self.free_blocks.append(block_addr)
    
    def allocate(self) -> Optional[int]:
        """Allocate a block from the pool."""
        if not self.free_blocks:
            return None
        
        addr = self.free_blocks.popleft()
        self.allocated_blocks.add(addr)
        return addr
    
    def deallocate(self, address: int) -> bool:
        """Deallocate a block back to the pool."""
        if address not in self.allocated_blocks:
            return False
        
        self.allocated_blocks.remove(address)
        self.free_blocks.append(address)
        return True
    
    def is_full(self) -> bool:
        """Check if pool is full."""
        return len(self.free_blocks) == 0
    
    def get_utilization(self) -> float:
        """Get pool utilization percentage."""
        return len(self.allocated_blocks) / self.pool_size

class MemoryArena:
    """Memory arena for bulk allocations."""
    
    def __init__(self, size: int = 1024 * 1024):  # 1MB default
        self.size = size
        self.buffer = ctypes.create_string_buffer(size)
        self.base_address = ctypes.addressof(self.buffer)
        self.current_offset = 0
        self.allocations: List[MemoryBlock] = []
    
    def allocate(self, size: int, alignment: int = 8) -> Optional[int]:
        """Allocate memory from arena."""
        # Align the allocation
        aligned_offset = (self.current_offset + alignment - 1) & ~(alignment - 1)
        
        if aligned_offset + size > self.size:
            return None
        
        address = self.base_address + aligned_offset
        self.current_offset = aligned_offset + size
        
        block = MemoryBlock(address, size, True, None, time.time())
        self.allocations.append(block)
        
        return address
    
    def reset(self):
        """Reset arena to empty state."""
        self.current_offset = 0
        self.allocations.clear()
    
    def get_usage(self) -> int:
        """Get current memory usage."""
        return self.current_offset

class SmartPointer(Generic[T]):
    """Base class for smart pointers."""
    
    def __init__(self, obj: T, manager: 'KaedeMemoryManager'):
        self._obj = obj
        self._manager = manager
        self._id = id(obj)
    
    def get(self) -> Optional[T]:
        """Get the managed object."""
        return self._obj
    
    def reset(self):
        """Reset the pointer."""
        self._obj = None

class UniquePtr(SmartPointer[T]):
    """Unique pointer - exclusive ownership."""
    
    def __init__(self, obj: T, manager: 'KaedeMemoryManager'):
        super().__init__(obj, manager)
        self._moved = False
    
    def move(self) -> 'UniquePtr[T]':
        """Move ownership to a new unique_ptr."""
        if self._moved:
            raise RuntimeError("Cannot move from moved unique_ptr")
        
        new_ptr = UniquePtr(self._obj, self._manager)
        self._moved = True
        self._obj = None
        return new_ptr
    
    def get(self) -> Optional[T]:
        if self._moved:
            return None
        return self._obj
    
    def __del__(self):
        if not self._moved and self._obj is not None:
            self._manager._cleanup_object(self._id)

class SharedPtr(SmartPointer[T]):
    """Shared pointer - shared ownership with reference counting."""
    
    _ref_counts: Dict[int, int] = {}
    _ref_lock = threading.Lock()
    
    def __init__(self, obj: T, manager: 'KaedeMemoryManager'):
        super().__init__(obj, manager)
        with self._ref_lock:
            self._ref_counts[self._id] = self._ref_counts.get(self._id, 0) + 1
    
    def use_count(self) -> int:
        """Get reference count."""
        with self._ref_lock:
            return self._ref_counts.get(self._id, 0)
    
    def __del__(self):
        with self._ref_lock:
            if self._id in self._ref_counts:
                self._ref_counts[self._id] -= 1
                if self._ref_counts[self._id] <= 0:
                    del self._ref_counts[self._id]
                    if self._obj is not None:
                        self._manager._cleanup_object(self._id)

class WeakPtr(Generic[T]):
    """Weak pointer - non-owning reference."""
    
    def __init__(self, shared_ptr: SharedPtr[T]):
        self._weak_ref = weakref.ref(shared_ptr._obj)
        self._id = shared_ptr._id
    
    def lock(self) -> Optional[SharedPtr[T]]:
        """Get a shared_ptr if object still exists."""
        obj = self._weak_ref()
        if obj is not None:
            # Create a new SharedPtr to increment reference count
            return SharedPtr(obj, None)  # Manager not needed for existing object
        return None
    
    def expired(self) -> bool:
        """Check if the referenced object has been destroyed."""
        return self._weak_ref() is None

class MemoryTracker:
    """Track memory allocations for debugging."""
    
    def __init__(self):
        self.allocations: Dict[int, MemoryBlock] = {}
        self.allocation_history: List[MemoryBlock] = []
        self.peak_usage = 0
        self.current_usage = 0
        self.lock = threading.Lock()
    
    def track_allocation(self, address: int, size: int, owner: str = None):
        """Track a memory allocation."""
        with self.lock:
            block = MemoryBlock(address, size, True, owner, time.time())
            self.allocations[address] = block
            self.allocation_history.append(block)
            self.current_usage += size
            self.peak_usage = max(self.peak_usage, self.current_usage)
    
    def track_deallocation(self, address: int):
        """Track a memory deallocation."""
        with self.lock:
            if address in self.allocations:
                block = self.allocations[address]
                self.current_usage -= block.size
                del self.allocations[address]
                return True
            return False
    
    def get_leaks(self) -> List[MemoryBlock]:
        """Get list of memory leaks."""
        with self.lock:
            return list(self.allocations.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self.lock:
            return {
                'current_usage': self.current_usage,
                'peak_usage': self.peak_usage,
                'active_allocations': len(self.allocations),
                'total_allocations': len(self.allocation_history),
                'leaked_blocks': len(self.allocations)
            }

class KaedeMemoryManager:
    """Advanced memory manager for Kaede."""
    
    def __init__(self, enable_tracking: bool = True):
        self.enable_tracking = enable_tracking
        self.tracker = MemoryTracker() if enable_tracking else None
        
        # Memory pools for common sizes
        self.pools: Dict[int, MemoryPool] = {}
        self._init_common_pools()
        
        # Memory arenas for bulk allocations
        self.arenas: List[MemoryArena] = []
        self.current_arena = MemoryArena()
        self.arenas.append(self.current_arena)
        
        # Garbage collection settings
        self.gc_enabled = True
        self.gc_threshold = 1000
        self.allocation_count = 0
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Smart pointer management
        self.managed_objects: Dict[int, Any] = {}
        
    def _init_common_pools(self):
        """Initialize memory pools for common allocation sizes."""
        common_sizes = [8, 16, 32, 64, 128, 256, 512, 1024]
        for size in common_sizes:
            self.pools[size] = MemoryPool(size)
    
    def malloc(self, size: int) -> Optional[int]:
        """C-style malloc."""
        with self.lock:
            # Try to use a pool for small allocations
            pool_size = self._find_pool_size(size)
            if pool_size and pool_size in self.pools:
                addr = self.pools[pool_size].allocate()
                if addr:
                    if self.tracker:
                        self.tracker.track_allocation(addr, size, "malloc")
                    return addr
            
            # Fall back to arena allocation
            addr = self.current_arena.allocate(size)
            if not addr:
                # Create new arena
                self.current_arena = MemoryArena()
                self.arenas.append(self.current_arena)
                addr = self.current_arena.allocate(size)
            
            if addr and self.tracker:
                self.tracker.track_allocation(addr, size, "malloc")
            
            self._check_gc()
            return addr
    
    def free(self, address: int) -> bool:
        """C-style free."""
        with self.lock:
            if self.tracker:
                if not self.tracker.track_deallocation(address):
                    return False
            
            # Try to return to pool
            for pool in self.pools.values():
                if pool.deallocate(address):
                    return True
            
            # For arena allocations, we can't free individual blocks
            # They're freed when the arena is reset
            return True
    
    def new(self, obj_type: type, *args, **kwargs) -> Any:
        """C++-style new operator."""
        with self.lock:
            obj = obj_type(*args, **kwargs)
            obj_id = id(obj)
            self.managed_objects[obj_id] = obj
            
            if self.tracker:
                size = sys.getsizeof(obj)
                self.tracker.track_allocation(obj_id, size, f"new {obj_type.__name__}")
            
            self._check_gc()
            return obj
    
    def delete(self, obj: Any) -> bool:
        """C++-style delete operator."""
        with self.lock:
            obj_id = id(obj)
            if obj_id in self.managed_objects:
                del self.managed_objects[obj_id]
                if self.tracker:
                    self.tracker.track_deallocation(obj_id)
                return True
            return False
    
    def make_unique(self, obj: T) -> UniquePtr[T]:
        """Create a unique_ptr."""
        return UniquePtr(obj, self)
    
    def make_shared(self, obj: T) -> SharedPtr[T]:
        """Create a shared_ptr."""
        return SharedPtr(obj, self)
    
    def make_weak(self, shared_ptr: SharedPtr[T]) -> WeakPtr[T]:
        """Create a weak_ptr from shared_ptr."""
        return WeakPtr(shared_ptr)
    
    def _find_pool_size(self, size: int) -> Optional[int]:
        """Find the smallest pool that can accommodate the size."""
        for pool_size in sorted(self.pools.keys()):
            if size <= pool_size:
                return pool_size
        return None
    
    def _check_gc(self):
        """Check if garbage collection should be triggered."""
        self.allocation_count += 1
        if self.gc_enabled and self.allocation_count >= self.gc_threshold:
            self.collect_garbage()
            self.allocation_count = 0
    
    def collect_garbage(self):
        """Force garbage collection."""
        collected = gc.collect()
        # Clean up weak references
        self._cleanup_weak_refs()
        return collected
    
    def _cleanup_weak_refs(self):
        """Clean up dead weak references."""
        dead_refs = []
        for obj_id, obj in self.managed_objects.items():
            if obj is None or (hasattr(obj, '__weakref__') and obj.__weakref__ is None):
                dead_refs.append(obj_id)
        
        for obj_id in dead_refs:
            if obj_id in self.managed_objects:
                del self.managed_objects[obj_id]
    
    def _cleanup_object(self, obj_id: int):
        """Clean up object by ID."""
        if obj_id in self.managed_objects:
            del self.managed_objects[obj_id]
        if self.tracker:
            self.tracker.track_deallocation(obj_id)
    
    def reset_arena(self, arena_index: int = -1):
        """Reset an arena (default: current arena)."""
        with self.lock:
            if arena_index == -1:
                self.current_arena.reset()
            elif 0 <= arena_index < len(self.arenas):
                self.arenas[arena_index].reset()
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get comprehensive memory information."""
        with self.lock:
            info = {
                'managed_objects': len(self.managed_objects),
                'arenas': len(self.arenas),
                'arena_usage': [arena.get_usage() for arena in self.arenas],
                'pool_stats': {
                    size: {
                        'utilization': pool.get_utilization(),
                        'is_full': pool.is_full()
                    }
                    for size, pool in self.pools.items()
                },
                'gc_enabled': self.gc_enabled,
                'allocation_count': self.allocation_count
            }
            
            if self.tracker:
                info.update(self.tracker.get_stats())
            
            return info
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics - alias for get_memory_info for compatibility."""
        return self.get_memory_info()
    
    def detect_leaks(self) -> List[MemoryBlock]:
        """Detect memory leaks."""
        if not self.tracker:
            return []
        return self.tracker.get_leaks()
    
    def enable_debug_mode(self):
        """Enable debug mode with comprehensive tracking."""
        self.enable_tracking = True
        if not self.tracker:
            self.tracker = MemoryTracker()
    
    def disable_debug_mode(self):
        """Disable debug mode."""
        self.enable_tracking = False
        self.tracker = None

# Global memory manager instance
memory_manager = KaedeMemoryManager()

# Convenience functions
def malloc(size: int) -> Optional[int]:
    """Allocate memory."""
    return memory_manager.malloc(size)

def free(address: int) -> bool:
    """Free memory."""
    return memory_manager.free(address)

def new(obj_type: type, *args, **kwargs) -> Any:
    """Create new object."""
    return memory_manager.new(obj_type, *args, **kwargs)

def delete(obj: Any) -> bool:
    """Delete object."""
    return memory_manager.delete(obj)

def make_unique(obj: T) -> UniquePtr[T]:
    """Create unique pointer."""
    return memory_manager.make_unique(obj)

def make_shared(obj: T) -> SharedPtr[T]:
    """Create shared pointer."""
    return memory_manager.make_shared(obj)

def collect_garbage():
    """Force garbage collection."""
    return memory_manager.collect_garbage()

def get_memory_info() -> Dict[str, Any]:
    """Get memory information."""
    return memory_manager.get_memory_info() 
"""
Memory Manager Component for KLayer

This module provides advanced memory management capabilities for KOS,
allowing for efficient memory allocation, monitoring, and optimization.
"""

import os
import sys
import time
import logging
import threading
import json
import psutil
import gc
import weakref
from typing import Dict, List, Any, Optional, Union, Callable, Tuple, Set

logger = logging.getLogger('KOS.layer.memory_manager')

class MemoryObject:
    """Base class for memory-managed objects"""
    
    def __init__(self, object_id: str, size: int = 0):
        """Initialize a memory-managed object"""
        self.object_id = object_id
        self.size = size
        self.creation_time = time.time()
        self.last_access_time = self.creation_time
        self.access_count = 0
        self.locked = False
        self.metadata = {}
    
    def access(self) -> None:
        """Record an access to this object"""
        self.last_access_time = time.time()
        self.access_count += 1
    
    def get_age(self) -> float:
        """Get the age of the object in seconds"""
        return time.time() - self.creation_time
    
    def get_last_access_age(self) -> float:
        """Get the time since last access in seconds"""
        return time.time() - self.last_access_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "object_id": self.object_id,
            "size": self.size,
            "creation_time": self.creation_time,
            "last_access_time": self.last_access_time,
            "access_count": self.access_count,
            "locked": self.locked,
            "age": self.get_age(),
            "last_access_age": self.get_last_access_age(),
            "metadata": self.metadata
        }

class CachedData(MemoryObject):
    """Cached data object for the memory manager"""
    
    def __init__(self, object_id: str, data: Any, size: int = 0, ttl: int = None):
        """Initialize a cached data object"""
        super().__init__(object_id, size)
        self.data = data
        self.ttl = ttl  # Time to live in seconds, None for no expiration
    
    def is_expired(self) -> bool:
        """Check if the object has expired"""
        if self.ttl is None:
            return False
        
        return self.get_age() > self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        result = super().to_dict()
        result["ttl"] = self.ttl
        result["expired"] = self.is_expired()
        return result

class MemoryPool:
    """Memory pool for allocating and managing memory blocks"""
    
    def __init__(self, name: str, max_size: int, block_size: int = 4096):
        """Initialize a memory pool"""
        self.name = name
        self.max_size = max_size  # Maximum pool size in bytes
        self.block_size = block_size  # Size of each block in bytes
        self.used_blocks = 0
        self.total_blocks = max_size // block_size
        self.blocks = [None] * self.total_blocks  # None = free block
        self.block_owners = {}  # Map of object_id -> set of block indices
        self.lock = threading.RLock()
    
    def allocate(self, object_id: str, size: int) -> Tuple[bool, List[int]]:
        """
        Allocate memory blocks for an object
        
        Args:
            object_id: ID of the object requesting memory
            size: Size in bytes to allocate
        
        Returns:
            Tuple of (success, block_indices)
        """
        with self.lock:
            # Calculate number of blocks needed
            num_blocks = (size + self.block_size - 1) // self.block_size
            
            # Check if we have enough free blocks
            if self.used_blocks + num_blocks > self.total_blocks:
                return (False, [])
            
            # Find free blocks
            free_blocks = []
            for i in range(self.total_blocks):
                if self.blocks[i] is None:
                    free_blocks.append(i)
                    if len(free_blocks) == num_blocks:
                        break
            
            # Allocate blocks
            for block_idx in free_blocks:
                self.blocks[block_idx] = object_id
            
            self.used_blocks += num_blocks
            
            # Record block ownership
            if object_id not in self.block_owners:
                self.block_owners[object_id] = set()
            
            self.block_owners[object_id].update(free_blocks)
            
            return (True, free_blocks)
    
    def deallocate(self, object_id: str) -> int:
        """
        Deallocate all blocks for an object
        
        Args:
            object_id: ID of the object to deallocate
            
        Returns:
            Number of blocks freed
        """
        with self.lock:
            if object_id not in self.block_owners:
                return 0
            
            block_indices = self.block_owners[object_id]
            num_blocks = len(block_indices)
            
            # Free blocks
            for block_idx in block_indices:
                self.blocks[block_idx] = None
            
            self.used_blocks -= num_blocks
            
            # Remove ownership record
            del self.block_owners[object_id]
            
            return num_blocks
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory pool statistics"""
        with self.lock:
            return {
                "name": self.name,
                "max_size": self.max_size,
                "block_size": self.block_size,
                "total_blocks": self.total_blocks,
                "used_blocks": self.used_blocks,
                "free_blocks": self.total_blocks - self.used_blocks,
                "usage_percent": (self.used_blocks / self.total_blocks) * 100 if self.total_blocks > 0 else 0,
                "object_count": len(self.block_owners)
            }

class MemoryManager:
    """Memory manager for KOS applications"""
    
    def __init__(self):
        """Initialize the memory manager"""
        self.lock = threading.RLock()
        self.cache = {}  # Map of object_id -> CachedData
        self.memory_pools = {}  # Map of pool_name -> MemoryPool
        self.allocated_memory = 0  # Total allocated memory in bytes
        self.max_memory = 1024 * 1024 * 100  # Default max memory: 100 MB
        self.gc_threshold = 0.8  # Garbage collect when memory usage > 80%
        self.policy = "lru"  # Default eviction policy: Least Recently Used
        self.callbacks = {}  # Map of event_type -> list of callbacks
        
        # Memory pools
        self.create_memory_pool("small", 1024 * 1024 * 10, 1024)  # 10 MB, 1 KB blocks
        self.create_memory_pool("medium", 1024 * 1024 * 30, 4096)  # 30 MB, 4 KB blocks
        self.create_memory_pool("large", 1024 * 1024 * 60, 1024 * 16)  # 60 MB, 16 KB blocks
        
        # Start background cleaner
        self.cleaner_thread = threading.Thread(target=self._background_cleaner, daemon=True)
        self.cleaner_thread.start()
        
        logger.debug("MemoryManager initialized")
    
    def _background_cleaner(self):
        """Background thread to clean expired cache entries"""
        while True:
            try:
                # Sleep for 30 seconds
                time.sleep(30)
                
                # Clean expired entries
                self.clean_expired()
                
                # Check if garbage collection is needed
                if self.get_usage_percent() > self.gc_threshold:
                    self.garbage_collect()
            except Exception as e:
                logger.error(f"Error in background cleaner: {e}")
    
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """
        Register a callback for memory events
        
        Args:
            event_type: Type of event (low_memory, allocation_failure, garbage_collect)
            callback: Callback function
        """
        with self.lock:
            if event_type not in self.callbacks:
                self.callbacks[event_type] = []
            
            self.callbacks[event_type].append(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify callbacks for an event"""
        if event_type not in self.callbacks:
            return
        
        for callback in self.callbacks[event_type]:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in memory callback: {e}")
    
    def create_memory_pool(self, name: str, max_size: int, block_size: int = 4096) -> bool:
        """
        Create a new memory pool
        
        Args:
            name: Name of the pool
            max_size: Maximum size in bytes
            block_size: Size of each block in bytes
            
        Returns:
            Success status
        """
        with self.lock:
            if name in self.memory_pools:
                return False
            
            self.memory_pools[name] = MemoryPool(name, max_size, block_size)
            return True
    
    def allocate(self, object_id: str, size: int, pool_name: str = None) -> bool:
        """
        Allocate memory for an object
        
        Args:
            object_id: ID of the object
            size: Size in bytes
            pool_name: Specific pool to allocate from, or None for automatic
            
        Returns:
            Success status
        """
        with self.lock:
            # Check if already allocated
            if object_id in self.cache:
                return True
            
            # Select pool
            if pool_name is None:
                # Automatic pool selection based on size
                if size <= 1024:  # <= 1 KB
                    pool_name = "small"
                elif size <= 16 * 1024:  # <= 16 KB
                    pool_name = "medium"
                else:
                    pool_name = "large"
            
            # Check if pool exists
            if pool_name not in self.memory_pools:
                self._notify_callbacks("allocation_failure", {
                    "object_id": object_id,
                    "size": size,
                    "reason": f"Pool not found: {pool_name}"
                })
                return False
            
            # Try to allocate
            pool = self.memory_pools[pool_name]
            success, block_indices = pool.allocate(object_id, size)
            
            if not success:
                # Try garbage collection
                self.garbage_collect()
                
                # Try again
                success, block_indices = pool.allocate(object_id, size)
                
                if not success:
                    self._notify_callbacks("allocation_failure", {
                        "object_id": object_id,
                        "size": size,
                        "pool": pool_name,
                        "reason": "Not enough memory"
                    })
                    return False
            
            # Update allocated memory
            self.allocated_memory += size
            
            # Check if we're approaching memory limit
            if self.get_usage_percent() > self.gc_threshold:
                self._notify_callbacks("low_memory", {
                    "allocated": self.allocated_memory,
                    "max": self.max_memory,
                    "percent": self.get_usage_percent()
                })
            
            return True
    
    def deallocate(self, object_id: str) -> bool:
        """
        Deallocate memory for an object
        
        Args:
            object_id: ID of the object
            
        Returns:
            Success status
        """
        with self.lock:
            # Remove from cache
            cached_obj = self.cache.pop(object_id, None)
            
            if cached_obj:
                self.allocated_memory -= cached_obj.size
            
            # Deallocate from pools
            blocks_freed = 0
            for pool in self.memory_pools.values():
                blocks_freed += pool.deallocate(object_id)
            
            return blocks_freed > 0 or cached_obj is not None
    
    def cache_data(self, object_id: str, data: Any, ttl: int = None) -> bool:
        """
        Cache data in memory
        
        Args:
            object_id: ID for the cached data
            data: Data to cache
            ttl: Time to live in seconds, None for no expiration
            
        Returns:
            Success status
        """
        with self.lock:
            # Calculate size (approximate)
            size = sys.getsizeof(data)
            
            # Allocate memory
            if not self.allocate(object_id, size):
                return False
            
            # Create cached data object
            cached_obj = CachedData(object_id, data, size, ttl)
            self.cache[object_id] = cached_obj
            
            return True
    
    def get_cached_data(self, object_id: str) -> Tuple[bool, Any]:
        """
        Get cached data
        
        Args:
            object_id: ID of the cached data
            
        Returns:
            Tuple of (success, data)
        """
        with self.lock:
            cached_obj = self.cache.get(object_id)
            
            if not cached_obj:
                return (False, None)
            
            # Check if expired
            if cached_obj.is_expired():
                self.deallocate(object_id)
                return (False, None)
            
            # Update access time
            cached_obj.access()
            
            return (True, cached_obj.data)
    
    def clean_expired(self) -> int:
        """
        Clean expired cache entries
        
        Returns:
            Number of entries cleaned
        """
        with self.lock:
            expired_ids = []
            
            # Find expired entries
            for object_id, cached_obj in self.cache.items():
                if cached_obj.is_expired():
                    expired_ids.append(object_id)
            
            # Deallocate expired entries
            for object_id in expired_ids:
                self.deallocate(object_id)
            
            return len(expired_ids)
    
    def garbage_collect(self) -> int:
        """
        Perform garbage collection based on the current policy
        
        Returns:
            Number of entries collected
        """
        with self.lock:
            # First clean expired entries
            cleaned = self.clean_expired()
            
            # If memory usage is still high, evict based on policy
            if self.get_usage_percent() > self.gc_threshold:
                # Get non-locked cache entries
                candidates = [obj for obj in self.cache.values() if not obj.locked]
                
                if not candidates:
                    return cleaned  # No candidates to evict
                
                # Sort candidates based on policy
                if self.policy == "lru":
                    # Least Recently Used
                    candidates.sort(key=lambda obj: obj.last_access_time)
                elif self.policy == "lfu":
                    # Least Frequently Used
                    candidates.sort(key=lambda obj: obj.access_count)
                elif self.policy == "fifo":
                    # First In First Out
                    candidates.sort(key=lambda obj: obj.creation_time)
                
                # Evict up to 25% of candidates or until memory usage is acceptable
                to_evict = max(1, len(candidates) // 4)
                evicted = 0
                
                for i in range(min(to_evict, len(candidates))):
                    if self.get_usage_percent() <= self.gc_threshold:
                        break
                    
                    object_id = candidates[i].object_id
                    self.deallocate(object_id)
                    evicted += 1
                
                cleaned += evicted
                
                self._notify_callbacks("garbage_collect", {
                    "evicted": evicted,
                    "policy": self.policy,
                    "allocated": self.allocated_memory,
                    "max": self.max_memory,
                    "percent": self.get_usage_percent()
                })
            
            # Suggest Python's garbage collector to run
            gc.collect()
            
            return cleaned
    
    def get_usage_percent(self) -> float:
        """Get memory usage as a percentage"""
        return (self.allocated_memory / self.max_memory) * 100 if self.max_memory > 0 else 0
    
    def set_max_memory(self, max_memory: int) -> None:
        """Set maximum memory limit in bytes"""
        with self.lock:
            self.max_memory = max_memory
    
    def set_policy(self, policy: str) -> bool:
        """
        Set memory eviction policy
        
        Args:
            policy: Policy name (lru, lfu, fifo)
            
        Returns:
            Success status
        """
        with self.lock:
            if policy not in ["lru", "lfu", "fifo"]:
                return False
            
            self.policy = policy
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory manager statistics"""
        with self.lock:
            pool_stats = {name: pool.get_stats() for name, pool in self.memory_pools.items()}
            
            # Get system memory info
            system_memory = {}
            try:
                mem = psutil.virtual_memory()
                system_memory = {
                    "total": mem.total,
                    "available": mem.available,
                    "used": mem.used,
                    "percent": mem.percent
                }
            except:
                pass
            
            return {
                "allocated_memory": self.allocated_memory,
                "max_memory": self.max_memory,
                "usage_percent": self.get_usage_percent(),
                "cache_entries": len(self.cache),
                "policy": self.policy,
                "gc_threshold": self.gc_threshold,
                "pools": pool_stats,
                "system_memory": system_memory
            }
    
    def lock_object(self, object_id: str) -> bool:
        """
        Lock an object to prevent eviction
        
        Args:
            object_id: ID of the object
            
        Returns:
            Success status
        """
        with self.lock:
            cached_obj = self.cache.get(object_id)
            
            if not cached_obj:
                return False
            
            cached_obj.locked = True
            return True
    
    def unlock_object(self, object_id: str) -> bool:
        """
        Unlock an object to allow eviction
        
        Args:
            object_id: ID of the object
            
        Returns:
            Success status
        """
        with self.lock:
            cached_obj = self.cache.get(object_id)
            
            if not cached_obj:
                return False
            
            cached_obj.locked = False
            return True
    
    def get_object_info(self, object_id: str) -> Dict[str, Any]:
        """
        Get information about a cached object
        
        Args:
            object_id: ID of the object
            
        Returns:
            Object information or error
        """
        with self.lock:
            cached_obj = self.cache.get(object_id)
            
            if not cached_obj:
                return {
                    "success": False,
                    "error": f"Object not found: {object_id}"
                }
            
            return {
                "success": True,
                "object_id": object_id,
                "info": cached_obj.to_dict()
            }
    
    def list_objects(self, pattern: str = None) -> Dict[str, Any]:
        """
        List cached objects
        
        Args:
            pattern: Optional pattern to filter object IDs
            
        Returns:
            Dictionary with object list
        """
        with self.lock:
            objects = []
            
            for object_id, cached_obj in self.cache.items():
                if pattern and pattern not in object_id:
                    continue
                
                objects.append(cached_obj.to_dict())
            
            return {
                "success": True,
                "count": len(objects),
                "objects": objects
            }

# Create a singleton instance
memory_manager = MemoryManager()

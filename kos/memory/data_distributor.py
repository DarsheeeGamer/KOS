"""
Byte-Level Data Storage Engine for KOS Memory System
Advanced data storage with caching and segmentation
"""

import os
import sys
import hashlib
import threading
import numpy as np
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
import logging
import struct
import mmap

# Hardware abstraction removed - using simple memory storage

logger = logging.getLogger(__name__)

class StorageStrategy(Enum):
    """Data storage strategies"""
    SIMPLE = "simple" 
    SEGMENTED = "segmented"
    CACHED = "cached"
    COMPRESSED = "compressed"

class DataType(Enum):
    """Supported data types for distribution"""
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    INT8 = "int8"
    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT8 = "uint8"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    COMPLEX64 = "complex64"
    COMPLEX128 = "complex128"
    BINARY = "binary"

@dataclass
class DataSegment:
    """Represents a segment of stored data"""
    segment_id: str
    storage_id: str  # Storage location identifier
    start_offset: int
    end_offset: int
    size: int
    data_type: DataType
    shape: Optional[Tuple[int, ...]]
    memory_ptr: Optional[int] = None
    checksum: Optional[str] = None
    is_dirty: bool = False
    last_accessed: float = 0.0

@dataclass
class StoredDataObject:
    """Represents a stored data object with segments"""
    object_id: str
    total_size: int
    data_type: DataType
    shape: Optional[Tuple[int, ...]]
    segments: List[DataSegment]
    strategy: StorageStrategy
    coherency_policy: str = "write_back"
    created_time: float = 0.0
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

class ByteLevelStorage:
    """Core byte-level data storage engine"""
    
    def __init__(self, memory_size: int = 1024 * 1024 * 1024):  # 1GB default
        self.memory_size = memory_size
        self.stored_objects: Dict[str, StoredDataObject] = {}
        self.segment_cache: Dict[str, bytes] = {}  # Memory cache
        self.memory_storage = {}  # Direct memory storage
        self.lock = threading.RLock()
        
        # Storage parameters
        self.min_segment_size = 4096  # 4KB minimum
        self.max_segment_size = 256 * 1024 * 1024  # 256MB maximum
        self.cache_size_limit = 512 * 1024 * 1024  # 512MB cache limit
        
        # Storage locations (simulated memory locations)
        self.storage_locations = {
            "primary": {"available": True, "capacity": memory_size // 2},
            "cache": {"available": True, "capacity": memory_size // 4},
            "secondary": {"available": True, "capacity": memory_size // 4}
        }
        
        # Statistics
        self.stats = {
            'total_objects': 0,
            'total_size_stored': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'storage_ops': 0,
            'segments_created': 0
        }
    
    def create_stored_object(self, data: Union[np.ndarray, bytes, memoryview], 
                                 strategy: StorageStrategy = StorageStrategy.SEGMENTED,
                                 preferred_locations: Optional[List[str]] = None) -> Optional[str]:
        """Create a stored data object from input data"""
        
        try:
            with self.lock:
                # Generate object ID
                object_id = self._generate_object_id(data)
                
                # Convert data to bytes if needed
                if isinstance(data, np.ndarray):
                    data_bytes = data.tobytes()
                    data_type = self._numpy_to_datatype(data.dtype)
                    shape = data.shape
                elif isinstance(data, (bytes, bytearray)):
                    data_bytes = bytes(data)
                    data_type = DataType.BINARY
                    shape = None
                elif isinstance(data, memoryview):
                    data_bytes = data.tobytes()
                    data_type = DataType.BINARY
                    shape = None
                else:
                    logger.error(f"Unsupported data type: {type(data)}")
                    return None
                
                total_size = len(data_bytes)
                
                # Select storage locations
                target_locations = self._select_storage_locations(strategy, total_size, preferred_locations)
                if not target_locations:
                    logger.error("No suitable storage locations found")
                    return None
                
                # Create segments
                segments = self._create_segments(data_bytes, target_locations, strategy, data_type, shape)
                if not segments:
                    logger.error("Failed to create data segments")
                    return None
                
                # Create stored object
                stored_obj = StoredDataObject(
                    object_id=object_id,
                    total_size=total_size,
                    data_type=data_type,
                    shape=shape,
                    segments=segments,
                    strategy=strategy,
                    created_time=time.time()
                )
                
                # Store object
                self.stored_objects[object_id] = stored_obj
                
                # Update statistics
                self.stats['total_objects'] += 1
                self.stats['total_size_stored'] += total_size
                self.stats['segments_created'] += len(segments)
                
                logger.info(f"Created stored object {object_id}: {total_size} bytes across {len(segments)} segments")
                return object_id
                
        except Exception as e:
            logger.error(f"Failed to create stored object: {e}")
            return None
    
    def _generate_object_id(self, data: Any) -> str:
        """Generate unique object ID"""
        if isinstance(data, np.ndarray):
            content = data.tobytes()
        else:
            content = bytes(data)
        
        hash_obj = hashlib.sha256()
        hash_obj.update(content)
        hash_obj.update(str(time.time()).encode())
        return f"obj_{hash_obj.hexdigest()[:16]}"
    
    def _numpy_to_datatype(self, np_dtype) -> DataType:
        """Convert numpy dtype to DataType enum"""
        dtype_map = {
            np.float32: DataType.FLOAT32,
            np.float64: DataType.FLOAT64,
            np.int8: DataType.INT8,
            np.int16: DataType.INT16,
            np.int32: DataType.INT32,
            np.int64: DataType.INT64,
            np.uint8: DataType.UINT8,
            np.uint16: DataType.UINT16,
            np.uint32: DataType.UINT32,
            np.uint64: DataType.UINT64,
            np.complex64: DataType.COMPLEX64,
            np.complex128: DataType.COMPLEX128
        }
        return dtype_map.get(np_dtype.type, DataType.BINARY)
    
    def _select_storage_locations(self, strategy: StorageStrategy, data_size: int, 
                       preferred_locations: Optional[List[str]] = None) -> List[str]:
        """Select optimal storage locations for data"""
        
        available_locations = [loc for loc, info in self.storage_locations.items() if info["available"]]
        
        if preferred_locations:
            # Filter by preferred locations
            available_locations = [loc for loc in available_locations if loc in preferred_locations]
        
        if not available_locations:
            return ["primary"]  # Fallback to primary storage
        
        if strategy == StorageStrategy.SIMPLE:
            # Use primary storage only
            return ["primary"] if "primary" in available_locations else [available_locations[0]]
        
        elif strategy == StorageStrategy.SEGMENTED:
            # Use all available locations
            return available_locations
        
        elif strategy == StorageStrategy.CACHED:
            # Prefer cache location
            if "cache" in available_locations:
                return ["cache", "primary"]
            return available_locations
        
        elif strategy == StorageStrategy.COMPRESSED:
            # Use secondary storage for compressed data
            if "secondary" in available_locations:
                return ["secondary", "primary"]
            return available_locations
        
        # Default: return all available locations
        return available_locations
    
    def _create_segments(self, data_bytes: bytes, target_locations: List[str], 
                        strategy: StorageStrategy, data_type: DataType, 
                        shape: Optional[Tuple[int, ...]]) -> List[DataSegment]:
        """Create data segments for storage"""
        
        segments = []
        total_size = len(data_bytes)
        location_count = len(target_locations)
        
        if location_count == 0:
            return segments
        
        try:
            # Calculate segment sizes based on strategy
            segment_sizes = self._calculate_segment_sizes(total_size, target_locations, strategy)
            
            current_offset = 0
            for i, (location_id, segment_size) in enumerate(zip(target_locations, segment_sizes)):
                if current_offset >= total_size:
                    break
                
                # Adjust last segment size
                if current_offset + segment_size > total_size:
                    segment_size = total_size - current_offset
                
                # Create segment
                segment_data = data_bytes[current_offset:current_offset + segment_size]
                segment_id = f"seg_{i}_{location_id}_{current_offset}"
                
                # Calculate checksum
                checksum = hashlib.md5(segment_data).hexdigest()
                
                # Store in memory
                memory_ptr = id(segment_data)  # Use Python object id as memory pointer
                self.memory_storage[memory_ptr] = segment_data
                
                segment = DataSegment(
                    segment_id=segment_id,
                    storage_id=location_id,
                    start_offset=current_offset,
                    end_offset=current_offset + segment_size,
                    size=segment_size,
                    data_type=data_type,
                    shape=shape,
                    memory_ptr=memory_ptr,
                    checksum=checksum,
                    last_accessed=time.time()
                )
                
                segments.append(segment)
                current_offset += segment_size
                
                # Cache segment data for fast access
                self.segment_cache[segment_id] = segment_data
            
            return segments
            
        except Exception as e:
            logger.error(f"Failed to create segments: {e}")
            return []
    
    def _calculate_segment_sizes(self, total_size: int, devices: List[str], 
                               strategy: DistributionStrategy) -> List[int]:
        """Calculate optimal segment sizes for each device"""
        
        device_count = len(devices)
        if device_count == 0:
            return []
        
        if strategy == DistributionStrategy.ROUND_ROBIN:
            # Equal distribution
            base_size = total_size // device_count
            remainder = total_size % device_count
            
            sizes = [base_size] * device_count
            for i in range(remainder):
                sizes[i] += 1
            
            return sizes
        
        elif strategy == DistributionStrategy.BANDWIDTH_OPTIMIZED:
            # Distribute based on bandwidth ratios
            device_bandwidths = []
            for device_id in devices:
                device = self.hardware_pool.get_device(device_id)
                device_bandwidths.append(device.memory_bandwidth if device else 1.0)
            
            total_bandwidth = sum(device_bandwidths)
            sizes = []
            
            for bandwidth in device_bandwidths:
                ratio = bandwidth / total_bandwidth
                size = int(total_size * ratio)
                sizes.append(max(size, self.min_segment_size))
            
            return sizes
        
        elif strategy == DistributionStrategy.MEMORY_OPTIMIZED:
            # Distribute based on available memory
            device_free_memory = []
            for device_id in devices:
                device = self.hardware_pool.get_device(device_id)
                if device:
                    used = self._calculate_device_memory_usage(device_id)
                    free = device.memory_size - used
                    device_free_memory.append(free)
                else:
                    device_free_memory.append(1024 * 1024)  # 1MB default
            
            total_free = sum(device_free_memory)
            sizes = []
            
            for free_mem in device_free_memory:
                ratio = free_mem / total_free
                size = int(total_size * ratio)
                sizes.append(max(size, self.min_segment_size))
            
            return sizes
        
        # Default: equal distribution
        base_size = total_size // device_count
        remainder = total_size % device_count
        sizes = [base_size] * device_count
        for i in range(remainder):
            sizes[i] += 1
        
        return sizes
    
    def _calculate_device_memory_usage(self, device_id: str) -> int:
        """Calculate current memory usage on device"""
        total_used = 0
        
        for obj in self.distributed_objects.values():
            for segment in obj.segments:
                if segment.device_id == device_id:
                    total_used += segment.size
        
        return total_used
    
    def _transfer_to_device(self, handler, device_id: str, data: bytes, device_ptr: int):
        """Transfer data to device memory"""
        # This is a simplified version - real implementation would use proper device APIs
        try:
            # Would use handler.transfer_data or device-specific copy functions
            logger.debug(f"Transferred {len(data)} bytes to device {device_id}")
        except Exception as e:
            logger.error(f"Failed to transfer data to device {device_id}: {e}")
    
    def read_object(self, object_id: str, start_offset: int = 0, 
                   length: Optional[int] = None) -> Optional[bytes]:
        """Read data from distributed object"""
        
        try:
            with self.lock:
                if object_id not in self.stored_objects:
                    return None
                
                obj = self.stored_objects[object_id]
                
                # Determine read range
                if length is None:
                    length = obj.total_size - start_offset
                
                end_offset = min(start_offset + length, obj.total_size)
                
                # Find segments that overlap with read range
                relevant_segments = []
                for segment in obj.segments:
                    if (segment.start_offset < end_offset and 
                        segment.end_offset > start_offset):
                        relevant_segments.append(segment)
                
                # Read data from segments
                result = bytearray()
                current_pos = start_offset
                
                for segment in sorted(relevant_segments, key=lambda s: s.start_offset):
                    # Skip gap if exists
                    if segment.start_offset > current_pos:
                        gap_size = segment.start_offset - current_pos
                        result.extend(b'\x00' * gap_size)
                        current_pos = segment.start_offset
                    
                    # Read from this segment
                    seg_start = max(0, start_offset - segment.start_offset)
                    seg_end = min(segment.size, end_offset - segment.start_offset)
                    
                    if seg_end > seg_start:
                        segment_data = self._read_segment(segment, seg_start, seg_end - seg_start)
                        if segment_data:
                            result.extend(segment_data)
                            current_pos = segment.start_offset + seg_end
                
                # Update access statistics
                obj.access_count += 1
                
                return bytes(result[:length])
                
        except Exception as e:
            logger.error(f"Failed to read object {object_id}: {e}")
            return None
    
    def _read_segment(self, segment: DataSegment, offset: int, length: int) -> Optional[bytes]:
        """Read data from a specific segment"""
        
        try:
            # Always check cache first - this is our actual storage
            if segment.segment_id in self.segment_cache:
                self.stats['cache_hits'] += 1
                cached_data = self.segment_cache[segment.segment_id]
                # Update access time
                segment.last_accessed = time.time()
                return cached_data[offset:offset + length]
            
            self.stats['cache_misses'] += 1
            
            # If not in cache, the data was lost (shouldn't happen in normal operation)
            logger.warning(f"Segment {segment.segment_id} not found in cache")
            return b'\x00' * length
            
        except Exception as e:
            logger.error(f"Failed to read segment {segment.segment_id}: {e}")
            return None
    
    def write_object(self, object_id: str, data: bytes, start_offset: int = 0) -> bool:
        """Write data to distributed object"""
        
        try:
            with self.lock:
                if object_id not in self.stored_objects:
                    return False
                
                obj = self.stored_objects[object_id]
                end_offset = start_offset + len(data)
                
                if end_offset > obj.total_size:
                    logger.error(f"Write exceeds object size: {end_offset} > {obj.total_size}")
                    return False
                
                # Find affected segments
                affected_segments = []
                for segment in obj.segments:
                    if (segment.start_offset < end_offset and 
                        segment.end_offset > start_offset):
                        affected_segments.append(segment)
                
                # Write to each affected segment
                data_pos = 0
                for segment in sorted(affected_segments, key=lambda s: s.start_offset):
                    # Calculate write range within segment
                    seg_start = max(0, start_offset - segment.start_offset)
                    seg_end = min(segment.size, end_offset - segment.start_offset)
                    
                    if seg_end > seg_start:
                        write_size = seg_end - seg_start
                        write_data = data[data_pos:data_pos + write_size]
                        
                        success = self._write_segment(segment, seg_start, write_data)
                        if not success:
                            logger.error(f"Failed to write to segment {segment.segment_id}")
                            return False
                        
                        data_pos += write_size
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to write object {object_id}: {e}")
            return False
    
    def _write_segment(self, segment: DataSegment, offset: int, data: bytes) -> bool:
        """Write data to a specific segment"""
        
        try:
            # Get or create cached data for this segment
            if segment.segment_id in self.segment_cache:
                cached_data = bytearray(self.segment_cache[segment.segment_id])
            else:
                # Initialize with zeros if not in cache
                cached_data = bytearray(segment.size)
            
            # Write the data to the cached segment
            cached_data[offset:offset + len(data)] = data
            self.segment_cache[segment.segment_id] = bytes(cached_data)
            
            # Mark as dirty for coherency
            segment.is_dirty = True
            segment.last_accessed = time.time()
            
            # Update checksum
            segment.checksum = hashlib.md5(self.segment_cache[segment.segment_id]).hexdigest()
            
            # In a real implementation, we would transfer to device here
            # For now, the cache IS our storage
            self.stats['transfers'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write segment {segment.segment_id}: {e}")
            return False
    
    def delete_object(self, object_id: str) -> bool:
        """Delete distributed object and free resources"""
        
        try:
            with self.lock:
                if object_id not in self.stored_objects:
                    return False
                
                obj = self.stored_objects[object_id]
                
                # Free device memory for all segments
                for segment in obj.segments:
                    device = self.hardware_pool.get_device(segment.device_id)
                    if device and segment.device_ptr:
                        handler = self.hardware_pool.device_handlers.get(device.device_type)
                        if handler:
                            handler.free_memory(segment.device_id, segment.device_ptr)
                    
                    # Remove from cache
                    if segment.segment_id in self.segment_cache:
                        del self.segment_cache[segment.segment_id]
                
                # Remove object
                del self.distributed_objects[object_id]
                
                # Update statistics
                self.stats['total_objects'] -= 1
                self.stats['total_size_distributed'] -= obj.total_size
                
                logger.info(f"Deleted distributed object {object_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete object {object_id}: {e}")
            return False
    
    def get_object_info(self, object_id: str) -> Optional[Dict[str, Any]]:
        """Get information about distributed object"""
        
        if object_id not in self.distributed_objects:
            return None
        
        obj = self.distributed_objects[object_id]
        
        return {
            'object_id': obj.object_id,
            'total_size': obj.total_size,
            'data_type': obj.data_type.value,
            'shape': obj.shape,
            'strategy': obj.strategy.value,
            'segment_count': len(obj.segments),
            'devices': [seg.device_id for seg in obj.segments],
            'created_time': obj.created_time,
            'access_count': obj.access_count,
            'segments': [
                {
                    'segment_id': seg.segment_id,
                    'device_id': seg.device_id,
                    'start_offset': seg.start_offset,
                    'size': seg.size,
                    'is_dirty': seg.is_dirty,
                    'last_accessed': seg.last_accessed
                }
                for seg in obj.segments
            ]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get distribution statistics"""
        
        # Calculate additional stats
        total_cache_size = sum(len(data) for data in self.segment_cache.values())
        
        return {
            **self.stats,
            'active_objects': len(self.distributed_objects),
            'cache_size': total_cache_size,
            'cache_hit_rate': (self.stats['cache_hits'] / 
                              max(1, self.stats['cache_hits'] + self.stats['cache_misses'])) * 100
        }
    
    def cleanup_cache(self, max_age: float = 3600.0):
        """Clean up old cache entries"""
        
        try:
            with self.lock:
                current_time = time.time()
                to_remove = []
                
                for segment_id, _ in self.segment_cache.items():
                    # Find corresponding segment
                    segment = None
                    for obj in self.distributed_objects.values():
                        for seg in obj.segments:
                            if seg.segment_id == segment_id:
                                segment = seg
                                break
                        if segment:
                            break
                    
                    if segment and (current_time - segment.last_accessed) > max_age:
                        to_remove.append(segment_id)
                
                for segment_id in to_remove:
                    del self.segment_cache[segment_id]
                
                if to_remove:
                    logger.info(f"Cleaned up {len(to_remove)} cache entries")
                    
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

# Backward compatibility aliases
ByteLevelDistributor = ByteLevelStorage
DistributedDataObject = StoredDataObject
DistributionStrategy = StorageStrategy
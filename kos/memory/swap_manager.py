"""
KOS Swap Space Management
Complete swap management with file and device support
"""

import os
import mmap
import struct
import threading
import logging
import time
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import fcntl
import hashlib

logger = logging.getLogger('kos.memory.swap')


class SwapType(Enum):
    """Swap space types"""
    FILE = auto()
    PARTITION = auto()
    ZRAM = auto()  # Compressed RAM swap
    ZSWAP = auto()  # Compressed swap cache


@dataclass
class SwapHeader:
    """Swap space header (compatible with Linux swap format)"""
    magic: bytes = b'SWAPSPACE2'  # Magic signature
    version: int = 1
    last_page: int = 0
    nr_badpages: int = 0
    sws_uuid: bytes = field(default_factory=lambda: os.urandom(16))
    sws_volume: bytes = b'KOS_SWAP' + b'\x00' * 8  # 16 bytes
    padding: bytes = field(default_factory=lambda: b'\x00' * 117)
    badpages: List[int] = field(default_factory=list)


@dataclass
class SwapExtent:
    """Swap extent for fragmented files"""
    start_page: int
    nr_pages: int
    start_block: int


@dataclass
class SwapInfo:
    """Swap space information"""
    path: str
    swap_type: SwapType
    priority: int = -1  # -1 = default priority
    size: int = 0  # Total size in bytes
    used: int = 0  # Used size in bytes
    free: int = 0  # Free size in bytes
    nr_pages: int = 0  # Total pages
    nr_free: int = 0  # Free pages
    flags: int = 0
    active: bool = False
    extents: List[SwapExtent] = field(default_factory=list)
    bad_pages: Set[int] = field(default_factory=set)


@dataclass
class SwapEntry:
    """Swap entry (32-bit format)"""
    # Bits 0-4: swap type (32 swap areas max)
    # Bits 5-31: page number within swap area
    value: int = 0
    
    @property
    def swap_type(self) -> int:
        return self.value & 0x1F
        
    @property
    def offset(self) -> int:
        return self.value >> 5
        
    @classmethod
    def make(cls, swap_type: int, offset: int) -> 'SwapEntry':
        """Create swap entry"""
        return cls((swap_type & 0x1F) | (offset << 5))


class SwapCache:
    """In-memory swap cache for frequently accessed pages"""
    
    def __init__(self, max_pages: int = 1024):
        self.max_pages = max_pages
        self.cache: Dict[int, bytes] = {}  # swap_entry -> page_data
        self.lru: List[int] = []  # LRU list of swap entries
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0
        
    def get(self, entry: int) -> Optional[bytes]:
        """Get page from cache"""
        with self._lock:
            if entry in self.cache:
                # Move to end of LRU
                self.lru.remove(entry)
                self.lru.append(entry)
                self.hits += 1
                return self.cache[entry]
            self.misses += 1
            return None
            
    def put(self, entry: int, data: bytes):
        """Put page in cache"""
        with self._lock:
            # Check if already in cache
            if entry in self.cache:
                self.lru.remove(entry)
                self.lru.append(entry)
                self.cache[entry] = data
                return
                
            # Evict if necessary
            while len(self.cache) >= self.max_pages:
                evict_entry = self.lru.pop(0)
                del self.cache[evict_entry]
                
            # Add to cache
            self.cache[entry] = data
            self.lru.append(entry)
            
    def invalidate(self, entry: int):
        """Remove page from cache"""
        with self._lock:
            if entry in self.cache:
                del self.cache[entry]
                self.lru.remove(entry)
                
    def clear(self):
        """Clear entire cache"""
        with self._lock:
            self.cache.clear()
            self.lru.clear()
            
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._lock:
            total = self.hits + self.misses
            hit_rate = self.hits / total if total > 0 else 0
            return {
                'size': len(self.cache),
                'max_size': self.max_pages,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate
            }


class SwapDevice:
    """Base swap device handler"""
    
    def __init__(self, path: str, size: int):
        self.path = path
        self.size = size
        self.page_size = 4096  # Standard page size
        self.nr_pages = size // self.page_size
        self.free_pages = set(range(1, self.nr_pages))  # Skip header page
        self.used_pages = set()
        self._lock = threading.Lock()
        
    def allocate_page(self) -> Optional[int]:
        """Allocate a free page"""
        with self._lock:
            if self.free_pages:
                page = self.free_pages.pop()
                self.used_pages.add(page)
                return page
            return None
            
    def free_page(self, page: int):
        """Free an allocated page"""
        with self._lock:
            if page in self.used_pages:
                self.used_pages.remove(page)
                self.free_pages.add(page)
                
    def read_page(self, page: int) -> bytes:
        """Read page from device"""
        # Base implementation - derived classes should override
        return b'\x00' * self.page_size
        
    def write_page(self, page: int, data: bytes):
        """Write page to device"""
        # Base implementation - derived classes should override
        pass
        
    def sync(self):
        """Sync device to storage"""
        # Base implementation - derived classes should override
        pass


class SwapFile(SwapDevice):
    """File-based swap device"""
    
    def __init__(self, path: str, size: int):
        super().__init__(path, size)
        self.fd = None
        self.mmap_obj = None
        
    def create(self):
        """Create swap file"""
        # Create file with specified size
        with open(self.path, 'wb') as f:
            f.seek(self.size - 1)
            f.write(b'\x00')
            
        # Write swap header
        header = SwapHeader()
        header.last_page = self.nr_pages - 1
        
        with open(self.path, 'r+b') as f:
            # Write header at beginning
            f.write(self._pack_header(header))
            
        logger.info(f"Created swap file: {self.path} ({self.size} bytes)")
        
    def _pack_header(self, header: SwapHeader) -> bytes:
        """Pack swap header to bytes"""
        data = bytearray(self.page_size)
        
        # Magic at end of first page
        data[-10:] = header.magic
        
        # Header at beginning
        struct.pack_into('<I', data, 0x400, header.version)
        struct.pack_into('<I', data, 0x404, header.last_page)
        struct.pack_into('<I', data, 0x408, header.nr_badpages)
        data[0x40C:0x41C] = header.sws_uuid
        data[0x41C:0x42C] = header.sws_volume
        
        # Bad pages list
        if header.badpages:
            offset = 0x42C
            for bad_page in header.badpages[:header.nr_badpages]:
                struct.pack_into('<I', data, offset, bad_page)
                offset += 4
                
        return bytes(data)
        
    def activate(self):
        """Activate swap file"""
        self.fd = os.open(self.path, os.O_RDWR)
        
        # Memory map the file
        self.mmap_obj = mmap.mmap(self.fd, self.size)
        
        # Mark bad pages from header
        self._read_header()
        
        logger.info(f"Activated swap file: {self.path}")
        
    def _read_header(self):
        """Read and validate swap header"""
        if not self.mmap_obj:
            return
            
        # Check magic
        magic = self.mmap_obj[-10:]
        if magic != b'SWAPSPACE2':
            raise ValueError(f"Invalid swap file magic: {magic}")
            
        # Read header
        version = struct.unpack('<I', self.mmap_obj[0x400:0x404])[0]
        last_page = struct.unpack('<I', self.mmap_obj[0x404:0x408])[0]
        nr_badpages = struct.unpack('<I', self.mmap_obj[0x408:0x40C])[0]
        
        # Read bad pages
        offset = 0x42C
        for _ in range(nr_badpages):
            bad_page = struct.unpack('<I', self.mmap_obj[offset:offset+4])[0]
            self.free_pages.discard(bad_page)
            offset += 4
            
    def deactivate(self):
        """Deactivate swap file"""
        if self.mmap_obj:
            self.mmap_obj.close()
            self.mmap_obj = None
            
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            
        logger.info(f"Deactivated swap file: {self.path}")
        
    def read_page(self, page: int) -> bytes:
        """Read page from swap file"""
        if not self.mmap_obj:
            raise RuntimeError("Swap file not activated")
            
        offset = page * self.page_size
        return bytes(self.mmap_obj[offset:offset + self.page_size])
        
    def write_page(self, page: int, data: bytes):
        """Write page to swap file"""
        if not self.mmap_obj:
            raise RuntimeError("Swap file not activated")
            
        if len(data) != self.page_size:
            raise ValueError(f"Invalid page size: {len(data)}")
            
        offset = page * self.page_size
        self.mmap_obj[offset:offset + self.page_size] = data
        
    def sync(self):
        """Sync swap file to disk"""
        if self.mmap_obj:
            self.mmap_obj.flush()


class ZramDevice(SwapDevice):
    """Compressed RAM swap device"""
    
    def __init__(self, path: str, size: int, compression: str = 'lz4'):
        super().__init__(path, size)
        self.compression = compression
        self.compressed_pages: Dict[int, bytes] = {}
        self.compression_ratio = 0.0
        
    def create(self):
        """Create ZRAM device"""
        logger.info(f"Created ZRAM device: {self.path} ({self.size} bytes)")
        
    def activate(self):
        """Activate ZRAM device"""
        logger.info(f"Activated ZRAM device: {self.path}")
        
    def deactivate(self):
        """Deactivate ZRAM device"""
        self.compressed_pages.clear()
        logger.info(f"Deactivated ZRAM device: {self.path}")
        
    def read_page(self, page: int) -> bytes:
        """Read page from ZRAM"""
        with self._lock:
            if page in self.compressed_pages:
                compressed = self.compressed_pages[page]
                # Decompress based on algorithm
                if self.compression == 'lz4':
                    import lz4.frame
                    return lz4.frame.decompress(compressed)
                elif self.compression == 'zstd':
                    import zstandard
                    return zstandard.decompress(compressed)
                else:
                    # No compression
                    return compressed
            return b'\x00' * self.page_size
            
    def write_page(self, page: int, data: bytes):
        """Write page to ZRAM"""
        with self._lock:
            # Compress based on algorithm
            if self.compression == 'lz4':
                import lz4.frame
                compressed = lz4.frame.compress(data)
            elif self.compression == 'zstd':
                import zstandard
                cctx = zstandard.ZstdCompressor(level=3)
                compressed = cctx.compress(data)
            else:
                # No compression
                compressed = data
                
            self.compressed_pages[page] = compressed
            
            # Update compression ratio
            total_uncompressed = len(self.compressed_pages) * self.page_size
            total_compressed = sum(len(d) for d in self.compressed_pages.values())
            self.compression_ratio = 1.0 - (total_compressed / total_uncompressed) if total_uncompressed > 0 else 0.0
            
    def sync(self):
        """No-op for ZRAM"""
        pass
        
    def get_stats(self) -> Dict[str, Any]:
        """Get ZRAM statistics"""
        with self._lock:
            total_compressed = sum(len(d) for d in self.compressed_pages.values())
            return {
                'pages': len(self.compressed_pages),
                'uncompressed_size': len(self.compressed_pages) * self.page_size,
                'compressed_size': total_compressed,
                'compression_ratio': self.compression_ratio
            }


class SwapManager:
    """Main swap space manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.swap_areas: List[SwapInfo] = []
        self.swap_devices: Dict[int, SwapDevice] = {}
        self.swap_cache = SwapCache()
        self.page_size = 4096
        self._lock = threading.RLock()
        self.next_swap_id = 0
        
        # Statistics
        self.total_swap = 0
        self.used_swap = 0
        self.swap_ins = 0
        self.swap_outs = 0
        
    def add_swap_file(self, path: str, size: int, priority: int = -1) -> bool:
        """Add swap file"""
        with self._lock:
            # Check if already exists
            for swap in self.swap_areas:
                if swap.path == path:
                    logger.error(f"Swap already exists: {path}")
                    return False
                    
            # Create swap info
            swap_info = SwapInfo(
                path=path,
                swap_type=SwapType.FILE,
                priority=priority,
                size=size,
                free=size - self.page_size,  # Minus header
                nr_pages=size // self.page_size,
                nr_free=(size // self.page_size) - 1
            )
            
            # Create swap device
            swap_device = SwapFile(path, size)
            
            # Create file if doesn't exist
            if not os.path.exists(path):
                swap_device.create()
                
            # Activate
            swap_device.activate()
            
            # Add to manager
            swap_id = self.next_swap_id
            self.next_swap_id += 1
            
            swap_info.active = True
            self.swap_areas.append(swap_info)
            self.swap_devices[swap_id] = swap_device
            
            # Update totals
            self.total_swap += swap_info.free
            
            logger.info(f"Added swap file: {path} (priority: {priority})")
            return True
            
    def add_zram_device(self, size: int, compression: str = 'lz4', priority: int = 100) -> bool:
        """Add ZRAM device"""
        with self._lock:
            # Generate path
            zram_id = len([s for s in self.swap_areas if s.swap_type == SwapType.ZRAM])
            path = f"/dev/zram{zram_id}"
            
            # Create swap info
            swap_info = SwapInfo(
                path=path,
                swap_type=SwapType.ZRAM,
                priority=priority,  # ZRAM usually has higher priority
                size=size,
                free=size,
                nr_pages=size // self.page_size,
                nr_free=size // self.page_size
            )
            
            # Create ZRAM device
            swap_device = ZramDevice(path, size, compression)
            swap_device.create()
            swap_device.activate()
            
            # Add to manager
            swap_id = self.next_swap_id
            self.next_swap_id += 1
            
            swap_info.active = True
            self.swap_areas.append(swap_info)
            self.swap_devices[swap_id] = swap_device
            
            # Update totals
            self.total_swap += swap_info.size
            
            logger.info(f"Added ZRAM device: {path} ({size} bytes, {compression})")
            return True
            
    def remove_swap(self, path: str) -> bool:
        """Remove swap area"""
        with self._lock:
            # Find swap area
            swap_info = None
            swap_id = None
            
            for i, swap in enumerate(self.swap_areas):
                if swap.path == path:
                    swap_info = swap
                    swap_id = i
                    break
                    
            if not swap_info:
                return False
                
            # Check if in use
            if swap_info.used > 0:
                logger.error(f"Cannot remove swap in use: {path}")
                return False
                
            # Deactivate device
            if swap_id in self.swap_devices:
                self.swap_devices[swap_id].deactivate()
                del self.swap_devices[swap_id]
                
            # Remove from list
            self.swap_areas.remove(swap_info)
            
            # Update totals
            self.total_swap -= swap_info.size
            
            logger.info(f"Removed swap: {path}")
            return True
            
    def swap_out(self, page_data: bytes) -> Optional[int]:
        """Swap out page to swap space"""
        with self._lock:
            # Find swap area with free space (sorted by priority)
            sorted_swaps = sorted(
                [(i, s) for i, s in enumerate(self.swap_areas) if s.active and s.nr_free > 0],
                key=lambda x: x[1].priority,
                reverse=True
            )
            
            for swap_id, swap_info in sorted_swaps:
                device = self.swap_devices.get(swap_id)
                if not device:
                    continue
                    
                # Allocate page
                page_num = device.allocate_page()
                if page_num is None:
                    continue
                    
                # Write page
                device.write_page(page_num, page_data)
                
                # Update swap info
                swap_info.used += self.page_size
                swap_info.free -= self.page_size
                swap_info.nr_free -= 1
                
                # Update stats
                self.used_swap += self.page_size
                self.swap_outs += 1
                
                # Create swap entry
                entry = SwapEntry.make(swap_id, page_num).value
                
                # Add to cache
                self.swap_cache.put(entry, page_data)
                
                return entry
                
            # No space available
            logger.warning("No swap space available")
            return None
            
    def swap_in(self, swap_entry: int) -> Optional[bytes]:
        """Swap in page from swap space"""
        # Check cache first
        cached = self.swap_cache.get(swap_entry)
        if cached:
            return cached
            
        with self._lock:
            entry = SwapEntry(swap_entry)
            swap_id = entry.swap_type
            page_num = entry.offset
            
            # Get device
            device = self.swap_devices.get(swap_id)
            if not device:
                logger.error(f"Invalid swap device: {swap_id}")
                return None
                
            # Read page
            page_data = device.read_page(page_num)
            
            # Free page
            device.free_page(page_num)
            
            # Update swap info
            if swap_id < len(self.swap_areas):
                swap_info = self.swap_areas[swap_id]
                swap_info.used -= self.page_size
                swap_info.free += self.page_size
                swap_info.nr_free += 1
                
            # Update stats
            self.used_swap -= self.page_size
            self.swap_ins += 1
            
            # Add to cache
            self.swap_cache.put(swap_entry, page_data)
            
            return page_data
            
    def free_swap_entry(self, swap_entry: int):
        """Free swap entry without reading"""
        with self._lock:
            entry = SwapEntry(swap_entry)
            swap_id = entry.swap_type
            page_num = entry.offset
            
            # Get device
            device = self.swap_devices.get(swap_id)
            if device:
                device.free_page(page_num)
                
                # Update swap info
                if swap_id < len(self.swap_areas):
                    swap_info = self.swap_areas[swap_id]
                    swap_info.used -= self.page_size
                    swap_info.free += self.page_size
                    swap_info.nr_free += 1
                    
                # Update stats
                self.used_swap -= self.page_size
                
            # Invalidate cache
            self.swap_cache.invalidate(swap_entry)
            
    def get_swap_info(self) -> List[Dict[str, Any]]:
        """Get information about all swap areas"""
        with self._lock:
            info = []
            for i, swap in enumerate(self.swap_areas):
                device = self.swap_devices.get(i)
                
                swap_dict = {
                    'path': swap.path,
                    'type': swap.swap_type.name,
                    'size': swap.size,
                    'used': swap.used,
                    'free': swap.free,
                    'priority': swap.priority,
                    'active': swap.active
                }
                
                # Add device-specific stats
                if isinstance(device, ZramDevice):
                    swap_dict['zram_stats'] = device.get_stats()
                    
                info.append(swap_dict)
                
            return info
            
    def get_stats(self) -> Dict[str, Any]:
        """Get swap statistics"""
        return {
            'total': self.total_swap,
            'used': self.used_swap,
            'free': self.total_swap - self.used_swap,
            'swap_ins': self.swap_ins,
            'swap_outs': self.swap_outs,
            'areas': len(self.swap_areas),
            'cache': self.swap_cache.get_stats()
        }
        
    def sync_all(self):
        """Sync all swap devices"""
        with self._lock:
            for device in self.swap_devices.values():
                device.sync()
                
    def swapoff_all(self):
        """Disable all swap areas"""
        with self._lock:
            # Copy list to avoid modification during iteration
            paths = [swap.path for swap in self.swap_areas]
            
            for path in paths:
                self.remove_swap(path)


# Global swap manager instance
_swap_manager = None

def get_swap_manager(kernel) -> SwapManager:
    """Get global swap manager"""
    global _swap_manager
    if _swap_manager is None:
        _swap_manager = SwapManager(kernel)
    return _swap_manager
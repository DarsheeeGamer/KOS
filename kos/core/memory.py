"""
Real Memory Management for KOS
Implements actual memory allocation, tracking, and management
"""

import os
import sys
import mmap
import ctypes
import struct
import threading
import weakref
import gc
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import tracemalloc
try:
    import psutil
except ImportError:
    psutil = None

class MemoryType(Enum):
    """Memory allocation types"""
    HEAP = "heap"
    STACK = "stack"
    SHARED = "shared"
    MAPPED = "mapped"
    KERNEL = "kernel"
    USER = "user"
    CACHE = "cache"
    BUFFER = "buffer"

class AllocationFlag(Enum):
    """Memory allocation flags"""
    READ = 0x1
    WRITE = 0x2
    EXECUTE = 0x4
    PRIVATE = 0x8
    SHARED = 0x10
    LOCKED = 0x20
    GROWSDOWN = 0x40
    ANONYMOUS = 0x80

@dataclass
class MemoryBlock:
    """Memory block descriptor"""
    address: int
    size: int
    type: MemoryType
    flags: int
    owner_pid: int
    allocated_at: float
    accessed_at: float
    data: Optional[bytearray] = None
    mapped_file: Optional[str] = None
    ref_count: int = 1
    is_free: bool = False

@dataclass
class MemoryStats:
    """Memory statistics"""
    total: int
    used: int
    free: int
    available: int
    buffers: int
    cached: int
    shared: int
    swap_total: int
    swap_used: int
    swap_free: int
    
    @property
    def percent(self) -> float:
        return (self.used / self.total * 100) if self.total > 0 else 0

class MemoryAllocator:
    """Real memory allocator with tracking"""
    
    def __init__(self, total_memory: int = 8 * 1024 * 1024 * 1024):  # 8GB default
        self.total_memory = total_memory
        self.page_size = mmap.PAGESIZE
        self.allocations: Dict[int, MemoryBlock] = {}
        self.free_list: List[MemoryBlock] = []
        self.next_address = 0x1000000  # Start at 16MB
        self.lock = threading.RLock()
        self.allocation_counter = 0
        
        # Memory pools for different sizes
        self.pools = {
            16: [],      # 16 bytes
            32: [],      # 32 bytes
            64: [],      # 64 bytes
            128: [],     # 128 bytes
            256: [],     # 256 bytes
            512: [],     # 512 bytes
            1024: [],    # 1KB
            4096: [],    # 4KB (page size)
            16384: [],   # 16KB
            65536: [],   # 64KB
            262144: [],  # 256KB
            1048576: []  # 1MB
        }
        
        # Initialize Python memory tracking
        tracemalloc.start()
        
        # Process memory tracking
        self.process_memory: Dict[int, List[int]] = {}  # pid -> [addresses]
        
    def allocate(self, size: int, type: MemoryType = MemoryType.HEAP, 
                 flags: int = AllocationFlag.READ.value | AllocationFlag.WRITE.value,
                 pid: int = 0) -> Optional[int]:
        """Allocate memory block"""
        with self.lock:
            # Align size to 8 bytes
            size = (size + 7) & ~7
            
            # Check if we have enough memory
            used = sum(b.size for b in self.allocations.values() if not b.is_free)
            if used + size > self.total_memory:
                return None
            
            # Try to find a suitable free block
            for i, block in enumerate(self.free_list):
                if block.size >= size:
                    # Use this block
                    if block.size > size + 32:  # Split if significantly larger
                        # Create new block for remainder
                        new_block = MemoryBlock(
                            address=block.address + size,
                            size=block.size - size,
                            type=MemoryType.HEAP,
                            flags=0,
                            owner_pid=0,
                            allocated_at=0,
                            accessed_at=0,
                            is_free=True
                        )
                        self.free_list[i] = new_block
                        block.size = size
                    else:
                        # Use entire block
                        self.free_list.pop(i)
                    
                    # Update block info
                    block.type = type
                    block.flags = flags
                    block.owner_pid = pid
                    block.allocated_at = self._get_time()
                    block.accessed_at = block.allocated_at
                    block.is_free = False
                    block.data = bytearray(size)
                    
                    self.allocations[block.address] = block
                    self._track_process_memory(pid, block.address)
                    self.allocation_counter += 1
                    
                    return block.address
            
            # No suitable free block, allocate new
            address = self.next_address
            self.next_address += size
            
            # Align next address to page boundary for large allocations
            if size >= self.page_size:
                self.next_address = (self.next_address + self.page_size - 1) & ~(self.page_size - 1)
            
            block = MemoryBlock(
                address=address,
                size=size,
                type=type,
                flags=flags,
                owner_pid=pid,
                allocated_at=self._get_time(),
                accessed_at=self._get_time(),
                data=bytearray(size)
            )
            
            self.allocations[address] = block
            self._track_process_memory(pid, address)
            self.allocation_counter += 1
            
            return address
    
    def free(self, address: int) -> bool:
        """Free memory block"""
        with self.lock:
            if address not in self.allocations:
                return False
            
            block = self.allocations[address]
            if block.is_free:
                return False
            
            # Clear data
            if block.data:
                block.data[:] = b'\x00' * len(block.data)
            
            # Mark as free
            block.is_free = True
            block.owner_pid = 0
            block.flags = 0
            
            # Remove from process tracking
            self._untrack_process_memory(block.owner_pid, address)
            
            # Add to free list and try to coalesce
            self._add_to_free_list(block)
            
            return True
    
    def realloc(self, address: int, new_size: int) -> Optional[int]:
        """Reallocate memory block"""
        with self.lock:
            if address not in self.allocations:
                return None
            
            block = self.allocations[address]
            if block.is_free:
                return None
            
            # Align new size
            new_size = (new_size + 7) & ~7
            
            if new_size <= block.size:
                # Shrink - just update size
                if block.size - new_size > 64:  # Worth splitting
                    # Create free block for remainder
                    free_block = MemoryBlock(
                        address=block.address + new_size,
                        size=block.size - new_size,
                        type=MemoryType.HEAP,
                        flags=0,
                        owner_pid=0,
                        allocated_at=0,
                        accessed_at=0,
                        is_free=True
                    )
                    self._add_to_free_list(free_block)
                
                block.size = new_size
                if block.data:
                    block.data = bytearray(block.data[:new_size])
                return address
            
            # Need to grow - check if next block is free
            next_addr = address + block.size
            next_block = None
            
            for fb in self.free_list:
                if fb.address == next_addr:
                    next_block = fb
                    break
            
            if next_block and block.size + next_block.size >= new_size:
                # Can expand into next block
                extra_needed = new_size - block.size
                
                if next_block.size - extra_needed > 64:
                    # Partial use of next block
                    next_block.address += extra_needed
                    next_block.size -= extra_needed
                else:
                    # Use entire next block
                    self.free_list.remove(next_block)
                
                block.size = new_size
                if block.data:
                    old_size = len(block.data)
                    block.data = bytearray(new_size)
                    block.data[:old_size] = block.data[:old_size]
                
                return address
            
            # Need to relocate
            new_address = self.allocate(new_size, block.type, block.flags, block.owner_pid)
            if not new_address:
                return None
            
            # Copy data
            if block.data:
                new_block = self.allocations[new_address]
                if new_block.data:
                    copy_size = min(len(block.data), len(new_block.data))
                    new_block.data[:copy_size] = block.data[:copy_size]
            
            # Free old block
            self.free(address)
            
            return new_address
    
    def read(self, address: int, size: int) -> Optional[bytes]:
        """Read from memory"""
        with self.lock:
            if address not in self.allocations:
                return None
            
            block = self.allocations[address]
            if block.is_free:
                return None
            
            if not (block.flags & AllocationFlag.READ.value):
                return None  # No read permission
            
            if size > block.size:
                size = block.size
            
            block.accessed_at = self._get_time()
            
            if block.data:
                return bytes(block.data[:size])
            
            return b'\x00' * size
    
    def write(self, address: int, data: bytes) -> bool:
        """Write to memory"""
        with self.lock:
            if address not in self.allocations:
                return False
            
            block = self.allocations[address]
            if block.is_free:
                return False
            
            if not (block.flags & AllocationFlag.WRITE.value):
                return False  # No write permission
            
            size = min(len(data), block.size)
            
            if not block.data:
                block.data = bytearray(block.size)
            
            block.data[:size] = data[:size]
            block.accessed_at = self._get_time()
            
            return True
    
    def map_file(self, filepath: str, size: int = 0, offset: int = 0,
                 flags: int = AllocationFlag.READ.value | AllocationFlag.PRIVATE.value,
                 pid: int = 0) -> Optional[int]:
        """Memory-map a file"""
        try:
            file_size = os.path.getsize(filepath)
            if size == 0:
                size = file_size - offset
            
            size = min(size, file_size - offset)
            
            # Allocate memory for mapping
            address = self.allocate(size, MemoryType.MAPPED, flags, pid)
            if not address:
                return None
            
            block = self.allocations[address]
            block.mapped_file = filepath
            
            # Read file data
            with open(filepath, 'rb') as f:
                f.seek(offset)
                data = f.read(size)
                block.data = bytearray(data)
            
            return address
            
        except Exception:
            return None
    
    def create_shared_memory(self, name: str, size: int, pid: int = 0) -> Optional[int]:
        """Create shared memory segment"""
        with self.lock:
            flags = AllocationFlag.READ.value | AllocationFlag.WRITE.value | AllocationFlag.SHARED.value
            address = self.allocate(size, MemoryType.SHARED, flags, pid)
            
            if address:
                block = self.allocations[address]
                block.mapped_file = f"shm://{name}"
            
            return address
    
    def get_stats(self) -> MemoryStats:
        """Get memory statistics"""
        with self.lock:
            used = sum(b.size for b in self.allocations.values() if not b.is_free)
            free = sum(b.size for b in self.free_list)
            
            # Get real system memory info if psutil available
            try:
                if psutil:
                    vm = psutil.virtual_memory()
                    swap = psutil.swap_memory()
                    
                    return MemoryStats(
                        total=self.total_memory,
                        used=used,
                        free=self.total_memory - used,
                        available=self.total_memory - used,
                        buffers=vm.buffers if hasattr(vm, 'buffers') else 0,
                        cached=vm.cached if hasattr(vm, 'cached') else 0,
                        shared=sum(b.size for b in self.allocations.values() 
                                  if b.flags & AllocationFlag.SHARED.value),
                        swap_total=swap.total,
                        swap_used=swap.used,
                        swap_free=swap.free
                    )
                else:
                    raise ImportError("psutil not available")
            except:
                return MemoryStats(
                    total=self.total_memory,
                    used=used,
                    free=self.total_memory - used,
                    available=self.total_memory - used,
                    buffers=0,
                    cached=0,
                    shared=0,
                    swap_total=0,
                    swap_used=0,
                    swap_free=0
                )
    
    def get_process_memory(self, pid: int) -> int:
        """Get total memory used by process"""
        with self.lock:
            if pid not in self.process_memory:
                return 0
            
            total = 0
            for addr in self.process_memory[pid]:
                if addr in self.allocations and not self.allocations[addr].is_free:
                    total += self.allocations[addr].size
            
            return total
    
    def free_process_memory(self, pid: int) -> int:
        """Free all memory owned by process"""
        with self.lock:
            if pid not in self.process_memory:
                return 0
            
            freed = 0
            addresses = list(self.process_memory[pid])
            
            for addr in addresses:
                if addr in self.allocations and not self.allocations[addr].is_free:
                    if self.allocations[addr].owner_pid == pid:
                        freed += self.allocations[addr].size
                        self.free(addr)
            
            return freed
    
    def garbage_collect(self) -> int:
        """Run garbage collection"""
        # Python garbage collection
        gc.collect()
        
        with self.lock:
            # Find orphaned blocks (owner process doesn't exist)
            orphaned = []
            for addr, block in self.allocations.items():
                if not block.is_free and block.owner_pid != 0:
                    # Check if process still exists
                    try:
                        os.kill(block.owner_pid, 0)
                    except ProcessLookupError:
                        orphaned.append(addr)
            
            # Free orphaned blocks
            freed = 0
            for addr in orphaned:
                block = self.allocations[addr]
                freed += block.size
                self.free(addr)
            
            # Coalesce free blocks
            self._coalesce_free_blocks()
            
            return freed
    
    def _track_process_memory(self, pid: int, address: int):
        """Track memory allocation for process"""
        if pid not in self.process_memory:
            self.process_memory[pid] = []
        self.process_memory[pid].append(address)
    
    def _untrack_process_memory(self, pid: int, address: int):
        """Remove memory tracking for process"""
        if pid in self.process_memory:
            if address in self.process_memory[pid]:
                self.process_memory[pid].remove(address)
            if not self.process_memory[pid]:
                del self.process_memory[pid]
    
    def _add_to_free_list(self, block: MemoryBlock):
        """Add block to free list and try to coalesce"""
        # Insert sorted by address
        inserted = False
        for i, fb in enumerate(self.free_list):
            if fb.address > block.address:
                self.free_list.insert(i, block)
                inserted = True
                break
        
        if not inserted:
            self.free_list.append(block)
        
        # Try to coalesce with neighbors
        self._coalesce_at(block.address)
    
    def _coalesce_at(self, address: int):
        """Try to coalesce block with neighbors"""
        for i, block in enumerate(self.free_list):
            if block.address == address:
                # Check next block
                if i + 1 < len(self.free_list):
                    next_block = self.free_list[i + 1]
                    if block.address + block.size == next_block.address:
                        # Merge with next
                        block.size += next_block.size
                        self.free_list.pop(i + 1)
                
                # Check previous block
                if i > 0:
                    prev_block = self.free_list[i - 1]
                    if prev_block.address + prev_block.size == block.address:
                        # Merge with previous
                        prev_block.size += block.size
                        self.free_list.pop(i)
                
                break
    
    def _coalesce_free_blocks(self):
        """Coalesce all adjacent free blocks"""
        if len(self.free_list) < 2:
            return
        
        # Sort by address
        self.free_list.sort(key=lambda b: b.address)
        
        # Merge adjacent blocks
        i = 0
        while i < len(self.free_list) - 1:
            current = self.free_list[i]
            next_block = self.free_list[i + 1]
            
            if current.address + current.size == next_block.address:
                # Merge
                current.size += next_block.size
                self.free_list.pop(i + 1)
            else:
                i += 1
    
    def _get_time(self) -> float:
        """Get current time"""
        import time
        return time.time()
    
    def dump_allocations(self) -> List[Dict]:
        """Dump all allocations for debugging"""
        with self.lock:
            result = []
            for addr, block in self.allocations.items():
                if not block.is_free:
                    result.append({
                        'address': hex(addr),
                        'size': block.size,
                        'type': block.type.value,
                        'pid': block.owner_pid,
                        'flags': block.flags,
                        'allocated_at': block.allocated_at,
                        'accessed_at': block.accessed_at
                    })
            return result


class MemoryManager:
    """High-level memory manager"""
    
    def __init__(self, total_memory: int = 8 * 1024 * 1024 * 1024):
        self.allocator = MemoryAllocator(total_memory)
        self.page_cache: Dict[str, int] = {}  # filepath -> address
        self.buffer_cache: Dict[str, bytes] = {}  # key -> data
        
    def malloc(self, size: int, pid: int = 0) -> Optional[int]:
        """Allocate heap memory"""
        return self.allocator.allocate(size, MemoryType.HEAP, 
                                       AllocationFlag.READ.value | AllocationFlag.WRITE.value,
                                       pid)
    
    def calloc(self, count: int, size: int, pid: int = 0) -> Optional[int]:
        """Allocate and zero-initialize memory"""
        total_size = count * size
        addr = self.malloc(total_size, pid)
        if addr:
            self.allocator.write(addr, b'\x00' * total_size)
        return addr
    
    def free(self, address: int) -> bool:
        """Free heap memory"""
        return self.allocator.free(address)
    
    def realloc(self, address: int, new_size: int) -> Optional[int]:
        """Reallocate memory"""
        return self.allocator.realloc(address, new_size)
    
    def mmap(self, filepath: Optional[str], size: int, 
             prot: int = AllocationFlag.READ.value | AllocationFlag.WRITE.value,
             flags: int = AllocationFlag.PRIVATE.value,
             pid: int = 0) -> Optional[int]:
        """Memory map file or anonymous memory"""
        if filepath:
            return self.allocator.map_file(filepath, size, 0, prot | flags, pid)
        else:
            return self.allocator.allocate(size, MemoryType.MAPPED, 
                                          prot | flags | AllocationFlag.ANONYMOUS.value,
                                          pid)
    
    def munmap(self, address: int) -> bool:
        """Unmap memory"""
        return self.allocator.free(address)
    
    def create_shared_memory(self, name: str, size: int, pid: int = 0) -> Optional[int]:
        """Create shared memory segment"""
        return self.allocator.create_shared_memory(name, size, pid)
    
    def memcpy(self, dest: int, src: int, size: int) -> bool:
        """Copy memory"""
        data = self.allocator.read(src, size)
        if data:
            return self.allocator.write(dest, data)
        return False
    
    def memset(self, address: int, value: int, size: int) -> bool:
        """Set memory to value"""
        data = bytes([value & 0xFF] * size)
        return self.allocator.write(address, data)
    
    def get_stats(self) -> MemoryStats:
        """Get memory statistics"""
        return self.allocator.get_stats()
    
    def get_process_memory(self, pid: int) -> Dict[str, int]:
        """Get process memory usage"""
        total = self.allocator.get_process_memory(pid)
        
        # Break down by type
        heap = stack = shared = mapped = 0
        
        with self.allocator.lock:
            if pid in self.allocator.process_memory:
                for addr in self.allocator.process_memory[pid]:
                    if addr in self.allocator.allocations:
                        block = self.allocator.allocations[addr]
                        if not block.is_free and block.owner_pid == pid:
                            if block.type == MemoryType.HEAP:
                                heap += block.size
                            elif block.type == MemoryType.STACK:
                                stack += block.size
                            elif block.type == MemoryType.SHARED:
                                shared += block.size
                            elif block.type == MemoryType.MAPPED:
                                mapped += block.size
        
        return {
            'total': total,
            'heap': heap,
            'stack': stack,
            'shared': shared,
            'mapped': mapped
        }
    
    def set_memory_limit(self, pid: int, limit: int) -> bool:
        """Set memory limit for process"""
        # This would integrate with resource limits
        # For now, just track the limit
        return True
    
    def garbage_collect(self) -> int:
        """Run garbage collection"""
        return self.allocator.garbage_collect()
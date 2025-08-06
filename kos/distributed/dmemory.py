"""
Distributed Memory Management for KOS
Provides shared memory across cluster nodes
"""

import time
import threading
import mmap
import struct
import pickle
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class PageState(Enum):
    """Memory page states"""
    LOCAL = "local"       # Page is local
    REMOTE = "remote"      # Page is on remote node
    SHARED = "shared"      # Page is shared across nodes
    MIGRATING = "migrating" # Page is being migrated
    INVALID = "invalid"    # Page is invalid

class AccessMode(Enum):
    """Page access modes"""
    READ_ONLY = "read_only"
    READ_WRITE = "read_write"
    EXCLUSIVE = "exclusive"

@dataclass
class PageDescriptor:
    """Descriptor for a memory page"""
    page_id: int
    virtual_addr: int
    physical_addr: Optional[int]
    size: int
    state: PageState
    owner_node: str
    access_mode: AccessMode
    ref_count: int = 0
    dirty: bool = False
    last_access: float = 0.0
    replicas: List[str] = field(default_factory=list)
    data: Optional[bytes] = None

@dataclass 
class MemorySegment:
    """Memory segment for process"""
    segment_id: str
    process_id: int
    start_addr: int
    end_addr: int
    size: int
    pages: List[int]  # Page IDs
    permissions: int
    shared: bool = False
    locked: bool = False

class DistributedMemory:
    """Distributed memory management system"""
    
    def __init__(self, cluster_node, local_memory, page_size: int = 4096):
        self.cluster = cluster_node
        self.local_memory = local_memory
        self.page_size = page_size
        
        # Page management
        self.pages: Dict[int, PageDescriptor] = {}
        self.local_pages: Dict[int, bytes] = {}  # Local page cache
        self.page_table: Dict[int, int] = {}  # Virtual -> Page ID
        
        # Segment management
        self.segments: Dict[str, MemorySegment] = {}
        self.process_segments: Dict[int, List[str]] = {}  # Process -> Segments
        
        # Remote memory tracking
        self.remote_memory: Dict[str, int] = {}  # Node -> Available memory
        self.memory_pressure = 0.0  # Local memory pressure
        
        # Page fault handling
        self.page_faults = 0
        self.page_hits = 0
        
        # Migration
        self.migration_queue: List[int] = []
        self.migrations_in_progress: Dict[int, str] = {}  # Page -> Target node
        
        # Thread control
        self.lock = threading.RLock()
        self.memory_thread = threading.Thread(target=self._memory_manager)
        self.memory_thread.daemon = True
        self.migration_thread = threading.Thread(target=self._migration_manager)
        self.migration_thread.daemon = True
        self.running = False
        
        # Statistics
        self.stats = {
            'page_faults': 0,
            'page_hits': 0,
            'migrations': 0,
            'remote_accesses': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def start(self):
        """Start distributed memory manager"""
        self.running = True
        self.memory_thread.start()
        self.migration_thread.start()
    
    def stop(self):
        """Stop distributed memory manager"""
        self.running = False
    
    def allocate_distributed(self, size: int, process_id: int, 
                           shared: bool = False) -> Optional[int]:
        """Allocate distributed memory"""
        with self.lock:
            # Calculate pages needed
            pages_needed = (size + self.page_size - 1) // self.page_size
            
            # Try local allocation first
            local_available = self._get_local_available()
            
            if local_available >= size:
                # Allocate locally
                return self._allocate_local(size, process_id, shared)
            
            # Need distributed allocation
            allocated_pages = []
            remaining = pages_needed
            
            # Allocate what we can locally
            local_pages = min(pages_needed, local_available // self.page_size)
            if local_pages > 0:
                for _ in range(local_pages):
                    page_id = self._create_page(self.cluster.node_id)
                    if page_id:
                        allocated_pages.append(page_id)
                        remaining -= 1
            
            # Allocate remaining on remote nodes
            if remaining > 0:
                remote_pages = self._allocate_remote(remaining, process_id)
                allocated_pages.extend(remote_pages)
            
            if len(allocated_pages) < pages_needed:
                # Failed to allocate enough
                self._free_pages(allocated_pages)
                return None
            
            # Create memory segment
            segment = self._create_segment(allocated_pages, process_id, size, shared)
            
            return segment.start_addr
    
    def _allocate_local(self, size: int, process_id: int, shared: bool) -> Optional[int]:
        """Allocate memory locally"""
        # Use local memory manager
        addr = self.local_memory.allocate(size)
        
        if addr:
            # Create pages for tracking
            pages_needed = (size + self.page_size - 1) // self.page_size
            page_ids = []
            
            for i in range(pages_needed):
                page_id = self._generate_page_id()
                page = PageDescriptor(
                    page_id=page_id,
                    virtual_addr=addr + i * self.page_size,
                    physical_addr=addr + i * self.page_size,
                    size=self.page_size,
                    state=PageState.LOCAL,
                    owner_node=self.cluster.node_id,
                    access_mode=AccessMode.EXCLUSIVE if not shared else AccessMode.SHARED,
                    ref_count=1
                )
                
                self.pages[page_id] = page
                page_ids.append(page_id)
            
            # Create segment
            self._create_segment(page_ids, process_id, size, shared)
            
        return addr
    
    def _allocate_remote(self, pages_needed: int, process_id: int) -> List[int]:
        """Allocate pages on remote nodes"""
        allocated = []
        
        # Get nodes with available memory
        available_nodes = self._get_nodes_with_memory()
        
        for node_id in available_nodes:
            if pages_needed == 0:
                break
            
            # Request allocation from remote node
            pages = self._request_remote_allocation(node_id, pages_needed)
            
            for page_id in pages:
                # Create local descriptor
                page = PageDescriptor(
                    page_id=page_id,
                    virtual_addr=0,  # Will be assigned
                    physical_addr=None,  # Remote
                    size=self.page_size,
                    state=PageState.REMOTE,
                    owner_node=node_id,
                    access_mode=AccessMode.READ_WRITE,
                    ref_count=1
                )
                
                self.pages[page_id] = page
                allocated.append(page_id)
                pages_needed -= 1
        
        return allocated
    
    def read_page(self, virtual_addr: int) -> Optional[bytes]:
        """Read a memory page"""
        with self.lock:
            # Find page
            page_id = self._virtual_to_page(virtual_addr)
            if not page_id:
                self.stats['page_faults'] += 1
                return None
            
            page = self.pages.get(page_id)
            if not page:
                return None
            
            # Update access time
            page.last_access = time.time()
            page.ref_count += 1
            
            # Check page state
            if page.state == PageState.LOCAL:
                # Read from local memory
                self.stats['page_hits'] += 1
                return self._read_local_page(page)
            
            elif page.state == PageState.REMOTE:
                # Check cache first
                if page_id in self.local_pages:
                    self.stats['cache_hits'] += 1
                    return self.local_pages[page_id]
                
                # Fetch from remote
                self.stats['cache_misses'] += 1
                self.stats['remote_accesses'] += 1
                data = self._fetch_remote_page(page)
                
                if data:
                    # Cache locally
                    self.local_pages[page_id] = data
                    
                    # Consider migration if accessed frequently
                    if page.ref_count > 10:
                        self.migration_queue.append(page_id)
                
                return data
            
            elif page.state == PageState.SHARED:
                # Read from nearest replica
                return self._read_shared_page(page)
            
            else:
                return None
    
    def write_page(self, virtual_addr: int, data: bytes) -> bool:
        """Write to a memory page"""
        with self.lock:
            # Find page
            page_id = self._virtual_to_page(virtual_addr)
            if not page_id:
                return False
            
            page = self.pages.get(page_id)
            if not page:
                return False
            
            # Check access mode
            if page.access_mode == AccessMode.READ_ONLY:
                return False
            
            # Update page
            page.last_access = time.time()
            page.dirty = True
            
            # Handle based on state
            if page.state == PageState.LOCAL:
                # Write locally
                return self._write_local_page(page, data)
            
            elif page.state == PageState.REMOTE:
                # Need to fetch for write (write-allocate)
                if page.access_mode == AccessMode.EXCLUSIVE:
                    # Migrate page locally
                    self.migration_queue.append(page_id)
                    
                # Write to remote
                return self._write_remote_page(page, data)
            
            elif page.state == PageState.SHARED:
                # Invalidate other copies
                self._invalidate_replicas(page)
                
                # Write locally
                return self._write_shared_page(page, data)
            
            else:
                return False
    
    def migrate_page(self, page_id: int, target_node: str) -> bool:
        """Migrate page to another node"""
        with self.lock:
            if page_id in self.migrations_in_progress:
                return False  # Already migrating
            
            page = self.pages.get(page_id)
            if not page:
                return False
            
            if page.owner_node == target_node:
                return True  # Already there
            
            # Mark as migrating
            page.state = PageState.MIGRATING
            self.migrations_in_progress[page_id] = target_node
            
            # Get page data
            if page.owner_node == self.cluster.node_id:
                # Local page
                data = self._read_local_page(page)
            else:
                # Remote page
                data = self._fetch_remote_page(page)
            
            if not data:
                page.state = PageState.INVALID
                del self.migrations_in_progress[page_id]
                return False
            
            # Send to target node
            if self._send_page_to_node(page_id, target_node, data):
                # Update page descriptor
                page.owner_node = target_node
                
                if target_node == self.cluster.node_id:
                    page.state = PageState.LOCAL
                    self.local_pages[page_id] = data
                else:
                    page.state = PageState.REMOTE
                    # Remove from local cache if present
                    self.local_pages.pop(page_id, None)
                
                del self.migrations_in_progress[page_id]
                self.stats['migrations'] += 1
                
                return True
            else:
                # Migration failed
                page.state = PageState.INVALID
                del self.migrations_in_progress[page_id]
                return False
    
    def _memory_manager(self):
        """Background memory management"""
        while self.running:
            try:
                with self.lock:
                    # Update memory pressure
                    self._update_memory_pressure()
                    
                    # Evict pages if needed
                    if self.memory_pressure > 0.8:
                        self._evict_pages()
                    
                    # Update remote memory info
                    self._update_remote_memory()
                
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Memory manager error: {e}")
    
    def _migration_manager(self):
        """Background page migration"""
        while self.running:
            try:
                if self.migration_queue:
                    with self.lock:
                        # Process migration queue
                        page_id = self.migration_queue.pop(0)
                        
                        page = self.pages.get(page_id)
                        if page and page.state == PageState.REMOTE:
                            # Migrate hot pages locally
                            self.migrate_page(page_id, self.cluster.node_id)
                
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Migration manager error: {e}")
    
    def _create_page(self, owner_node: str) -> Optional[int]:
        """Create a new page"""
        page_id = self._generate_page_id()
        
        page = PageDescriptor(
            page_id=page_id,
            virtual_addr=0,
            physical_addr=None,
            size=self.page_size,
            state=PageState.LOCAL if owner_node == self.cluster.node_id else PageState.REMOTE,
            owner_node=owner_node,
            access_mode=AccessMode.READ_WRITE,
            ref_count=0
        )
        
        self.pages[page_id] = page
        return page_id
    
    def _create_segment(self, page_ids: List[int], process_id: int, 
                       size: int, shared: bool) -> MemorySegment:
        """Create memory segment"""
        segment_id = f"seg_{process_id}_{time.time()}"
        
        # Calculate virtual address range
        start_addr = self._allocate_virtual_range(size)
        
        # Map pages to virtual addresses
        for i, page_id in enumerate(page_ids):
            page = self.pages[page_id]
            page.virtual_addr = start_addr + i * self.page_size
            self.page_table[page.virtual_addr] = page_id
        
        segment = MemorySegment(
            segment_id=segment_id,
            process_id=process_id,
            start_addr=start_addr,
            end_addr=start_addr + size,
            size=size,
            pages=page_ids,
            permissions=0o644,
            shared=shared
        )
        
        self.segments[segment_id] = segment
        
        if process_id not in self.process_segments:
            self.process_segments[process_id] = []
        self.process_segments[process_id].append(segment_id)
        
        return segment
    
    def _virtual_to_page(self, virtual_addr: int) -> Optional[int]:
        """Convert virtual address to page ID"""
        # Align to page boundary
        page_addr = (virtual_addr // self.page_size) * self.page_size
        return self.page_table.get(page_addr)
    
    def _read_local_page(self, page: PageDescriptor) -> Optional[bytes]:
        """Read page from local memory"""
        if page.physical_addr:
            # Would read from actual memory
            # For now, return cached data
            return page.data or b'\x00' * self.page_size
        return None
    
    def _write_local_page(self, page: PageDescriptor, data: bytes) -> bool:
        """Write page to local memory"""
        if page.physical_addr:
            # Would write to actual memory
            # For now, cache data
            page.data = data
            return True
        return False
    
    def _fetch_remote_page(self, page: PageDescriptor) -> Optional[bytes]:
        """Fetch page from remote node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            page.owner_node,
            MessageType.READ,
            {'page_id': page.page_id}
        )
        
        return response.get('data') if response else None
    
    def _write_remote_page(self, page: PageDescriptor, data: bytes) -> bool:
        """Write page to remote node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            page.owner_node,
            MessageType.WRITE,
            {'page_id': page.page_id, 'data': data}
        )
        
        return response and response.get('status') == 'success'
    
    def _read_shared_page(self, page: PageDescriptor) -> Optional[bytes]:
        """Read shared page from nearest replica"""
        # Try local first
        if page.page_id in self.local_pages:
            return self.local_pages[page.page_id]
        
        # Try replicas
        for node_id in page.replicas:
            data = self._fetch_from_node(page.page_id, node_id)
            if data:
                # Cache locally
                self.local_pages[page.page_id] = data
                return data
        
        return None
    
    def _write_shared_page(self, page: PageDescriptor, data: bytes) -> bool:
        """Write to shared page"""
        # Write locally
        self.local_pages[page.page_id] = data
        page.data = data
        
        # Replicate to other nodes
        success = True
        for node_id in page.replicas:
            if node_id != self.cluster.node_id:
                if not self._replicate_to_node(page.page_id, node_id, data):
                    success = False
        
        return success
    
    def _invalidate_replicas(self, page: PageDescriptor):
        """Invalidate page replicas on other nodes"""
        from .cluster import MessageType
        
        for node_id in page.replicas:
            if node_id != self.cluster.node_id:
                self.cluster.send_message(
                    node_id,
                    MessageType.WRITE,
                    {'page_id': page.page_id, 'invalidate': True}
                )
    
    def _send_page_to_node(self, page_id: int, node_id: str, data: bytes) -> bool:
        """Send page data to node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.WRITE,
            {'page_id': page_id, 'data': data, 'migrate': True}
        )
        
        return response and response.get('status') == 'success'
    
    def _fetch_from_node(self, page_id: int, node_id: str) -> Optional[bytes]:
        """Fetch page from specific node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.READ,
            {'page_id': page_id}
        )
        
        return response.get('data') if response else None
    
    def _replicate_to_node(self, page_id: int, node_id: str, data: bytes) -> bool:
        """Replicate page to node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.WRITE,
            {'page_id': page_id, 'data': data, 'replicate': True}
        )
        
        return response and response.get('status') == 'success'
    
    def _request_remote_allocation(self, node_id: str, pages: int) -> List[int]:
        """Request memory allocation from remote node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.EXEC,
            {'action': 'allocate', 'pages': pages}
        )
        
        return response.get('page_ids', []) if response else []
    
    def _get_local_available(self) -> int:
        """Get available local memory"""
        # Would check actual memory
        return self.local_memory.get_free_memory()
    
    def _get_nodes_with_memory(self) -> List[str]:
        """Get nodes with available memory"""
        nodes = []
        
        for node_id, available in self.remote_memory.items():
            if available > self.page_size:
                nodes.append(node_id)
        
        return sorted(nodes, key=lambda n: self.remote_memory[n], reverse=True)
    
    def _update_memory_pressure(self):
        """Update local memory pressure"""
        total = self.local_memory.total_memory
        used = total - self.local_memory.get_free_memory()
        self.memory_pressure = used / total if total > 0 else 1.0
    
    def _update_remote_memory(self):
        """Update remote memory information"""
        from .cluster import MessageType
        
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.cluster.node_id:
                response = self.cluster.send_message(
                    node_id,
                    MessageType.INFO,
                    {'type': 'memory'}
                )
                
                if response:
                    self.remote_memory[node_id] = response.get('available', 0)
    
    def _evict_pages(self):
        """Evict pages to free memory"""
        # Find LRU pages
        evictable = []
        
        for page_id, page in self.pages.items():
            if (page.state == PageState.LOCAL and 
                not page.dirty and 
                page.ref_count == 0):
                evictable.append((page.last_access, page_id))
        
        # Sort by last access time
        evictable.sort()
        
        # Evict oldest pages
        evicted = 0
        target = len(evictable) // 4  # Evict 25%
        
        for _, page_id in evictable[:target]:
            page = self.pages[page_id]
            
            # Find node with most memory
            target_node = self._get_nodes_with_memory()[0] if self._get_nodes_with_memory() else None
            
            if target_node:
                # Migrate to remote node
                if self.migrate_page(page_id, target_node):
                    evicted += 1
        
        logger.info(f"Evicted {evicted} pages")
    
    def _free_pages(self, page_ids: List[int]):
        """Free allocated pages"""
        for page_id in page_ids:
            if page_id in self.pages:
                page = self.pages[page_id]
                
                # Free based on location
                if page.owner_node == self.cluster.node_id:
                    # Free locally
                    if page.physical_addr:
                        self.local_memory.free(page.physical_addr)
                else:
                    # Free remotely
                    from .cluster import MessageType
                    
                    self.cluster.send_message(
                        page.owner_node,
                        MessageType.EXEC,
                        {'action': 'free', 'page_id': page_id}
                    )
                
                # Remove from tracking
                del self.pages[page_id]
                self.local_pages.pop(page_id, None)
                
                # Remove from page table
                for vaddr, pid in list(self.page_table.items()):
                    if pid == page_id:
                        del self.page_table[vaddr]
    
    def _allocate_virtual_range(self, size: int) -> int:
        """Allocate virtual address range"""
        # Simple allocation - would use proper virtual memory manager
        import random
        return random.randint(0x100000, 0xFFFFFF) & ~(self.page_size - 1)
    
    def _generate_page_id(self) -> int:
        """Generate unique page ID"""
        import random
        return random.randint(1000000, 9999999)
    
    def free_process_memory(self, process_id: int):
        """Free all memory for a process"""
        with self.lock:
            if process_id not in self.process_segments:
                return
            
            for segment_id in self.process_segments[process_id]:
                segment = self.segments.get(segment_id)
                if segment:
                    # Free all pages
                    self._free_pages(segment.pages)
                    
                    # Remove segment
                    del self.segments[segment_id]
            
            # Remove process tracking
            del self.process_segments[process_id]
    
    def get_memory_stats(self) -> Dict:
        """Get memory statistics"""
        with self.lock:
            total_pages = len(self.pages)
            local_pages = sum(1 for p in self.pages.values() if p.state == PageState.LOCAL)
            remote_pages = sum(1 for p in self.pages.values() if p.state == PageState.REMOTE)
            shared_pages = sum(1 for p in self.pages.values() if p.state == PageState.SHARED)
            
            return {
                'total_pages': total_pages,
                'local_pages': local_pages,
                'remote_pages': remote_pages,
                'shared_pages': shared_pages,
                'memory_pressure': self.memory_pressure,
                'page_faults': self.stats['page_faults'],
                'page_hits': self.stats['page_hits'],
                'migrations': self.stats['migrations'],
                'remote_accesses': self.stats['remote_accesses'],
                'cache_hit_rate': (self.stats['cache_hits'] / 
                                  (self.stats['cache_hits'] + self.stats['cache_misses']))
                                  if (self.stats['cache_hits'] + self.stats['cache_misses']) > 0 else 0
            }

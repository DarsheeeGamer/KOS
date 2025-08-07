"""
Distributed Memory Coherency for KOS Hardware Pool
Implements network-based MOESI protocol across multiple machines
"""

import os
import sys
import time
import threading
import hashlib
import struct
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from .cluster_communication import KOSClusterManager, NetworkMessage, MessageType

logger = logging.getLogger(__name__)

class DistributedCoherencyState(Enum):
    """MOESI states for distributed memory"""
    MODIFIED = "M"      # Only this node has dirty copy
    OWNED = "O"         # This node owns but may be shared
    EXCLUSIVE = "E"     # Only this node has clean copy
    SHARED = "S"        # Multiple nodes have clean copy
    INVALID = "I"       # Invalid/not present

@dataclass
class DistributedCacheLine:
    """Cache line in distributed memory"""
    address: int
    size: int
    data: Optional[bytes]
    state: DistributedCoherencyState
    node_id: str
    version: int
    last_modified: float
    sharers: Set[str] = field(default_factory=set)
    pending_invalidations: Set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)

@dataclass
class MemoryPage:
    """Memory page in distributed system"""
    page_address: int
    page_size: int
    owner_node: str
    sharers: Set[str]
    version: int
    is_dirty: bool
    last_access: float
    access_count: int
    migration_count: int

class DistributedMemoryCoherency:
    """Network-based memory coherency protocol"""
    
    def __init__(self, cluster_manager: KOSClusterManager):
        self.cluster = cluster_manager
        self.node_id = cluster_manager.node_id
        
        # Distributed cache
        self.cache_lines: Dict[int, DistributedCacheLine] = {}
        self.page_directory: Dict[int, MemoryPage] = {}
        
        # Coherency directory (distributed)
        self.coherency_directory: Dict[int, Dict[str, DistributedCoherencyState]] = defaultdict(dict)
        
        # Pending transactions
        self.pending_transactions: Dict[str, Any] = {}
        
        # Configuration
        self.cache_line_size = 64  # bytes
        self.page_size = 4096  # 4KB pages
        
        # Locks
        self.directory_lock = threading.RLock()
        self.transaction_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'remote_reads': 0,
            'remote_writes': 0,
            'invalidations_sent': 0,
            'invalidations_received': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'page_migrations': 0,
            'coherency_violations': 0
        }
        
        # Register handlers
        self._register_handlers()
        
        logger.info(f"Distributed memory coherency initialized for node {self.node_id}")
    
    def _register_handlers(self):
        """Register network message handlers"""
        # Create new message types for distributed coherency
        handlers = {
            'coherency_read_req': self._handle_read_request,
            'coherency_write_req': self._handle_write_request,
            'coherency_invalidate': self._handle_invalidation,
            'coherency_writeback': self._handle_writeback,
            'coherency_data_resp': self._handle_data_response,
            'coherency_ownership': self._handle_ownership_transfer,
            'coherency_migrate': self._handle_page_migration
        }
        
        # Register with cluster manager
        for msg_type, handler in handlers.items():
            # Would register with actual message type enum
            pass
    
    def read_distributed(self, address: int, size: int) -> Optional[bytes]:
        """Read from distributed memory with coherency"""
        
        try:
            cache_line_addr = self._align_to_cache_line(address)
            
            # Check local cache first
            with self.directory_lock:
                if cache_line_addr in self.cache_lines:
                    cache_line = self.cache_lines[cache_line_addr]
                    
                    if cache_line.state != DistributedCoherencyState.INVALID:
                        self.stats['cache_hits'] += 1
                        
                        # Extract requested data
                        offset = address - cache_line_addr
                        if cache_line.data:
                            return cache_line.data[offset:offset + size]
            
            self.stats['cache_misses'] += 1
            
            # Cache miss - need to fetch from remote node
            return self._handle_distributed_read_miss(address, size)
            
        except Exception as e:
            logger.error(f"Distributed read failed: {e}")
            return None
    
    def write_distributed(self, address: int, data: bytes) -> bool:
        """Write to distributed memory with coherency"""
        
        try:
            cache_line_addr = self._align_to_cache_line(address)
            
            with self.directory_lock:
                # Check if we have exclusive access
                if cache_line_addr in self.cache_lines:
                    cache_line = self.cache_lines[cache_line_addr]
                    
                    if cache_line.state in [DistributedCoherencyState.MODIFIED, 
                                           DistributedCoherencyState.EXCLUSIVE]:
                        # Can write directly
                        return self._perform_local_write(cache_line, address, data)
                    
                    elif cache_line.state in [DistributedCoherencyState.OWNED,
                                            DistributedCoherencyState.SHARED]:
                        # Need to upgrade to exclusive
                        return self._upgrade_to_exclusive(cache_line_addr, address, data)
            
            # Need to acquire exclusive access
            return self._acquire_exclusive_access(address, data)
            
        except Exception as e:
            logger.error(f"Distributed write failed: {e}")
            return False
    
    def _handle_distributed_read_miss(self, address: int, size: int) -> Optional[bytes]:
        """Handle read miss in distributed cache"""
        
        cache_line_addr = self._align_to_cache_line(address)
        
        # Find owner node for this address
        owner_node = self._find_owner_node(cache_line_addr)
        
        if owner_node and owner_node != self.node_id:
            # Request data from owner
            self.stats['remote_reads'] += 1
            
            transaction_id = self._generate_transaction_id()
            
            # Create pending transaction
            self.pending_transactions[transaction_id] = {
                'type': 'read',
                'address': cache_line_addr,
                'completed': False,
                'data': None
            }
            
            # Send read request to owner
            request_data = {
                'transaction_id': transaction_id,
                'address': cache_line_addr,
                'size': self.cache_line_size,
                'requester': self.node_id
            }
            
            # Use cluster manager to send message
            response_data = self._send_coherency_request(
                owner_node, 'read_request', request_data
            )
            
            if response_data:
                # Create local cache line in shared state
                cache_line = DistributedCacheLine(
                    address=cache_line_addr,
                    size=self.cache_line_size,
                    data=response_data,
                    state=DistributedCoherencyState.SHARED,
                    node_id=self.node_id,
                    version=1,
                    last_modified=time.time()
                )
                
                with self.directory_lock:
                    self.cache_lines[cache_line_addr] = cache_line
                    self._update_coherency_directory(cache_line_addr, self.node_id, 
                                                    DistributedCoherencyState.SHARED)
                
                # Extract requested data
                offset = address - cache_line_addr
                return response_data[offset:offset + size]
        
        # No owner found - initialize new data
        return self._initialize_new_cache_line(address, size)
    
    def _acquire_exclusive_access(self, address: int, data: bytes) -> bool:
        """Acquire exclusive access for write"""
        
        cache_line_addr = self._align_to_cache_line(address)
        
        # Find all sharers
        sharers = self._find_sharers(cache_line_addr)
        
        if sharers:
            # Send invalidation to all sharers
            self.stats['invalidations_sent'] += len(sharers)
            
            invalidation_data = {
                'address': cache_line_addr,
                'requester': self.node_id
            }
            
            # Send invalidations
            for sharer_node in sharers:
                if sharer_node != self.node_id:
                    self._send_coherency_request(
                        sharer_node, 'invalidate', invalidation_data
                    )
        
        # Create cache line in modified state
        cache_line_data = bytearray(self.cache_line_size)
        offset = address - cache_line_addr
        cache_line_data[offset:offset + len(data)] = data
        
        cache_line = DistributedCacheLine(
            address=cache_line_addr,
            size=self.cache_line_size,
            data=bytes(cache_line_data),
            state=DistributedCoherencyState.MODIFIED,
            node_id=self.node_id,
            version=1,
            last_modified=time.time()
        )
        
        with self.directory_lock:
            self.cache_lines[cache_line_addr] = cache_line
            self._update_coherency_directory(cache_line_addr, self.node_id,
                                            DistributedCoherencyState.MODIFIED)
        
        self.stats['remote_writes'] += 1
        return True
    
    def _upgrade_to_exclusive(self, cache_line_addr: int, address: int, data: bytes) -> bool:
        """Upgrade shared cache line to exclusive"""
        
        # Get all sharers except ourselves
        sharers = self._find_sharers(cache_line_addr)
        other_sharers = sharers - {self.node_id}
        
        if other_sharers:
            # Send invalidation to other sharers
            self.stats['invalidations_sent'] += len(other_sharers)
            
            invalidation_data = {
                'address': cache_line_addr,
                'requester': self.node_id
            }
            
            for sharer_node in other_sharers:
                self._send_coherency_request(
                    sharer_node, 'invalidate', invalidation_data
                )
        
        # Upgrade local cache line to modified
        with self.directory_lock:
            cache_line = self.cache_lines[cache_line_addr]
            
            # Apply write
            cache_line_data = bytearray(cache_line.data or b'\x00' * self.cache_line_size)
            offset = address - cache_line_addr
            cache_line_data[offset:offset + len(data)] = data
            
            cache_line.data = bytes(cache_line_data)
            cache_line.state = DistributedCoherencyState.MODIFIED
            cache_line.version += 1
            cache_line.last_modified = time.time()
            
            self._update_coherency_directory(cache_line_addr, self.node_id,
                                            DistributedCoherencyState.MODIFIED)
        
        return True
    
    def _perform_local_write(self, cache_line: DistributedCacheLine, 
                           address: int, data: bytes) -> bool:
        """Perform write to local cache line"""
        
        with cache_line.lock:
            # Apply write
            cache_line_data = bytearray(cache_line.data or b'\x00' * self.cache_line_size)
            offset = address - cache_line.address
            cache_line_data[offset:offset + len(data)] = data
            
            cache_line.data = bytes(cache_line_data)
            cache_line.state = DistributedCoherencyState.MODIFIED
            cache_line.version += 1
            cache_line.last_modified = time.time()
        
        return True
    
    def migrate_page(self, page_address: int, target_node: str) -> bool:
        """Migrate memory page to another node"""
        
        try:
            page_addr = self._align_to_page(page_address)
            
            with self.directory_lock:
                if page_addr not in self.page_directory:
                    # Create page entry
                    self.page_directory[page_addr] = MemoryPage(
                        page_address=page_addr,
                        page_size=self.page_size,
                        owner_node=self.node_id,
                        sharers={self.node_id},
                        version=1,
                        is_dirty=False,
                        last_access=time.time(),
                        access_count=1,
                        migration_count=0
                    )
                
                page = self.page_directory[page_addr]
                
                if page.owner_node == self.node_id:
                    # We own this page - can migrate it
                    
                    # Collect all cache lines in this page
                    page_data = self._collect_page_data(page_addr)
                    
                    # Send page to target node
                    migration_data = {
                        'page_address': page_addr,
                        'page_data': page_data,
                        'version': page.version,
                        'sharers': list(page.sharers)
                    }
                    
                    success = self._send_coherency_request(
                        target_node, 'migrate_page', migration_data
                    )
                    
                    if success:
                        # Update ownership
                        page.owner_node = target_node
                        page.migration_count += 1
                        self.stats['page_migrations'] += 1
                        
                        # Invalidate local cache lines for this page
                        self._invalidate_page_cache_lines(page_addr)
                        
                        logger.info(f"Migrated page {page_addr:x} to node {target_node}")
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Page migration failed: {e}")
            return False
    
    def _handle_read_request(self, message: NetworkMessage):
        """Handle remote read request"""
        
        try:
            request_data = message.payload
            address = request_data['address']
            size = request_data['size']
            requester = request_data['requester']
            
            with self.directory_lock:
                if address in self.cache_lines:
                    cache_line = self.cache_lines[address]
                    
                    if cache_line.state != DistributedCoherencyState.INVALID:
                        # Send data to requester
                        response_data = {
                            'transaction_id': request_data['transaction_id'],
                            'data': cache_line.data,
                            'version': cache_line.version
                        }
                        
                        self._send_coherency_response(requester, 'data_response', response_data)
                        
                        # Update state if exclusive
                        if cache_line.state == DistributedCoherencyState.EXCLUSIVE:
                            cache_line.state = DistributedCoherencyState.SHARED
                            cache_line.sharers.add(requester)
                        
                        # Add requester as sharer
                        self._update_coherency_directory(address, requester,
                                                        DistributedCoherencyState.SHARED)
                        
        except Exception as e:
            logger.error(f"Failed to handle read request: {e}")
    
    def _handle_write_request(self, message: NetworkMessage):
        """Handle remote write request"""
        
        try:
            request_data = message.payload
            address = request_data['address']
            data = request_data['data']
            requester = request_data['requester']
            
            # Invalidate local copy if exists
            with self.directory_lock:
                if address in self.cache_lines:
                    cache_line = self.cache_lines[address]
                    
                    # Writeback if dirty
                    if cache_line.state == DistributedCoherencyState.MODIFIED:
                        self._perform_writeback(cache_line)
                    
                    # Invalidate
                    cache_line.state = DistributedCoherencyState.INVALID
                    self.stats['invalidations_received'] += 1
            
            # Send acknowledgment
            self._send_coherency_response(requester, 'write_ack', {'success': True})
            
        except Exception as e:
            logger.error(f"Failed to handle write request: {e}")
    
    def _handle_invalidation(self, message: NetworkMessage):
        """Handle invalidation request"""
        
        try:
            invalidation_data = message.payload
            address = invalidation_data['address']
            requester = invalidation_data['requester']
            
            with self.directory_lock:
                if address in self.cache_lines:
                    cache_line = self.cache_lines[address]
                    
                    # Writeback if dirty
                    if cache_line.state in [DistributedCoherencyState.MODIFIED,
                                           DistributedCoherencyState.OWNED]:
                        self._perform_writeback(cache_line)
                    
                    # Invalidate
                    cache_line.state = DistributedCoherencyState.INVALID
                    self.stats['invalidations_received'] += 1
            
            # Send acknowledgment
            self._send_coherency_response(requester, 'invalidate_ack', {'success': True})
            
        except Exception as e:
            logger.error(f"Failed to handle invalidation: {e}")
    
    def _handle_writeback(self, message: NetworkMessage):
        """Handle writeback from another node"""
        
        try:
            writeback_data = message.payload
            address = writeback_data['address']
            data = writeback_data['data']
            version = writeback_data['version']
            
            # Store in persistent storage or forward to home node
            logger.debug(f"Received writeback for address {address:x}")
            
        except Exception as e:
            logger.error(f"Failed to handle writeback: {e}")
    
    def _handle_data_response(self, message: NetworkMessage):
        """Handle data response from another node"""
        
        try:
            response_data = message.payload
            transaction_id = response_data['transaction_id']
            
            if transaction_id in self.pending_transactions:
                transaction = self.pending_transactions[transaction_id]
                transaction['data'] = response_data['data']
                transaction['completed'] = True
                
        except Exception as e:
            logger.error(f"Failed to handle data response: {e}")
    
    def _handle_ownership_transfer(self, message: NetworkMessage):
        """Handle ownership transfer request"""
        
        try:
            transfer_data = message.payload
            address = transfer_data['address']
            new_owner = transfer_data['new_owner']
            
            with self.directory_lock:
                if address in self.cache_lines:
                    cache_line = self.cache_lines[address]
                    
                    # Transfer ownership
                    if cache_line.state == DistributedCoherencyState.MODIFIED:
                        # Send data to new owner
                        self._send_coherency_request(
                            new_owner, 'ownership_data',
                            {'address': address, 'data': cache_line.data}
                        )
                    
                    # Update local state
                    cache_line.state = DistributedCoherencyState.SHARED
                    
        except Exception as e:
            logger.error(f"Failed to handle ownership transfer: {e}")
    
    def _handle_page_migration(self, message: NetworkMessage):
        """Handle incoming page migration"""
        
        try:
            migration_data = message.payload
            page_addr = migration_data['page_address']
            page_data = migration_data['page_data']
            version = migration_data['version']
            sharers = migration_data['sharers']
            
            with self.directory_lock:
                # Create page entry
                self.page_directory[page_addr] = MemoryPage(
                    page_address=page_addr,
                    page_size=self.page_size,
                    owner_node=self.node_id,
                    sharers=set(sharers),
                    version=version,
                    is_dirty=False,
                    last_access=time.time(),
                    access_count=0,
                    migration_count=1
                )
                
                # Store page data in cache lines
                self._store_page_data(page_addr, page_data)
                
            logger.info(f"Received migrated page {page_addr:x}")
            
        except Exception as e:
            logger.error(f"Failed to handle page migration: {e}")
    
    def _find_owner_node(self, address: int) -> Optional[str]:
        """Find owner node for address"""
        
        # Use consistent hashing or directory-based lookup
        # For now, use simple modulo hashing
        
        all_nodes = list(self.cluster.nodes.keys())
        if not all_nodes:
            return self.node_id
        
        # Hash address to determine owner
        hash_value = hash(address)
        owner_index = hash_value % len(all_nodes)
        
        return all_nodes[owner_index]
    
    def _find_sharers(self, address: int) -> Set[str]:
        """Find all nodes sharing this address"""
        
        with self.directory_lock:
            if address in self.coherency_directory:
                return set(self.coherency_directory[address].keys())
            return set()
    
    def _align_to_cache_line(self, address: int) -> int:
        """Align address to cache line boundary"""
        return (address // self.cache_line_size) * self.cache_line_size
    
    def _align_to_page(self, address: int) -> int:
        """Align address to page boundary"""
        return (address // self.page_size) * self.page_size
    
    def _update_coherency_directory(self, address: int, node_id: str, 
                                   state: DistributedCoherencyState):
        """Update coherency directory"""
        
        with self.directory_lock:
            if state == DistributedCoherencyState.INVALID:
                if address in self.coherency_directory:
                    self.coherency_directory[address].pop(node_id, None)
                    if not self.coherency_directory[address]:
                        del self.coherency_directory[address]
            else:
                self.coherency_directory[address][node_id] = state
    
    def _send_coherency_request(self, target_node: str, request_type: str, 
                               data: Dict) -> Optional[Any]:
        """Send coherency request to another node"""
        
        # Use cluster manager's network transport
        # This is simplified - would use actual message types
        
        if request_type == 'read_request':
            return self.cluster.read_remote_memory(
                target_node, data['address'], data['size']
            )
        elif request_type == 'invalidate':
            # Send invalidation message
            return True
        
        return None
    
    def _send_coherency_response(self, target_node: str, response_type: str, data: Dict):
        """Send coherency response to another node"""
        
        # Use cluster manager's network transport
        pass
    
    def _perform_writeback(self, cache_line: DistributedCacheLine):
        """Perform writeback of dirty cache line"""
        
        if cache_line.data and cache_line.state in [DistributedCoherencyState.MODIFIED,
                                                     DistributedCoherencyState.OWNED]:
            # Find home node for writeback
            home_node = self._find_owner_node(cache_line.address)
            
            if home_node and home_node != self.node_id:
                writeback_data = {
                    'address': cache_line.address,
                    'data': cache_line.data,
                    'version': cache_line.version
                }
                
                self._send_coherency_request(home_node, 'writeback', writeback_data)
    
    def _initialize_new_cache_line(self, address: int, size: int) -> bytes:
        """Initialize new cache line with zeros"""
        
        cache_line_addr = self._align_to_cache_line(address)
        
        # Create new cache line
        cache_line = DistributedCacheLine(
            address=cache_line_addr,
            size=self.cache_line_size,
            data=b'\x00' * self.cache_line_size,
            state=DistributedCoherencyState.EXCLUSIVE,
            node_id=self.node_id,
            version=1,
            last_modified=time.time()
        )
        
        with self.directory_lock:
            self.cache_lines[cache_line_addr] = cache_line
            self._update_coherency_directory(cache_line_addr, self.node_id,
                                            DistributedCoherencyState.EXCLUSIVE)
        
        # Return requested portion
        offset = address - cache_line_addr
        return cache_line.data[offset:offset + size]
    
    def _collect_page_data(self, page_addr: int) -> bytes:
        """Collect all data for a page"""
        
        page_data = bytearray(self.page_size)
        
        # Collect all cache lines in this page
        for offset in range(0, self.page_size, self.cache_line_size):
            cache_line_addr = page_addr + offset
            
            if cache_line_addr in self.cache_lines:
                cache_line = self.cache_lines[cache_line_addr]
                if cache_line.data:
                    page_data[offset:offset + self.cache_line_size] = cache_line.data
        
        return bytes(page_data)
    
    def _store_page_data(self, page_addr: int, page_data: bytes):
        """Store page data in cache lines"""
        
        # Split page into cache lines
        for offset in range(0, self.page_size, self.cache_line_size):
            cache_line_addr = page_addr + offset
            cache_line_data = page_data[offset:offset + self.cache_line_size]
            
            cache_line = DistributedCacheLine(
                address=cache_line_addr,
                size=self.cache_line_size,
                data=cache_line_data,
                state=DistributedCoherencyState.EXCLUSIVE,
                node_id=self.node_id,
                version=1,
                last_modified=time.time()
            )
            
            self.cache_lines[cache_line_addr] = cache_line
    
    def _invalidate_page_cache_lines(self, page_addr: int):
        """Invalidate all cache lines in a page"""
        
        for offset in range(0, self.page_size, self.cache_line_size):
            cache_line_addr = page_addr + offset
            
            if cache_line_addr in self.cache_lines:
                self.cache_lines[cache_line_addr].state = DistributedCoherencyState.INVALID
    
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        return f"{self.node_id}_{int(time.time() * 1000000)}"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get distributed memory statistics"""
        
        with self.directory_lock:
            cache_lines_by_state = defaultdict(int)
            for cache_line in self.cache_lines.values():
                cache_lines_by_state[cache_line.state.value] += 1
            
            return {
                **self.stats,
                'total_cache_lines': len(self.cache_lines),
                'total_pages': len(self.page_directory),
                'cache_lines_by_state': dict(cache_lines_by_state),
                'pending_transactions': len(self.pending_transactions)
            }
    
    def verify_coherency(self) -> List[str]:
        """Verify coherency invariants"""
        
        violations = []
        
        with self.directory_lock:
            # Check for multiple modified copies
            for address, states in self.coherency_directory.items():
                modified_nodes = [
                    node for node, state in states.items()
                    if state == DistributedCoherencyState.MODIFIED
                ]
                
                if len(modified_nodes) > 1:
                    violations.append(
                        f"Multiple modified copies at address {address:x}: {modified_nodes}"
                    )
                    self.stats['coherency_violations'] += 1
            
            # Check for exclusive with sharers
            for address, states in self.coherency_directory.items():
                exclusive_nodes = [
                    node for node, state in states.items()
                    if state == DistributedCoherencyState.EXCLUSIVE
                ]
                
                if exclusive_nodes and len(states) > 1:
                    violations.append(
                        f"Exclusive state with sharers at address {address:x}"
                    )
                    self.stats['coherency_violations'] += 1
        
        return violations
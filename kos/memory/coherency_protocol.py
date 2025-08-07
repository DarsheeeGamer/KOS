"""
MOESI Memory Coherency Protocol for KOS Distributed Hardware Pool
Ensures data consistency across all devices in the pool
"""

import time
import threading
import hashlib
import logging
from enum import Enum
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

from ..hardware.base import UniversalHardwarePool

logger = logging.getLogger(__name__)

class CoherencyState(Enum):
    """MOESI coherency states"""
    MODIFIED = "M"      # Cache line is dirty and owned by this cache only
    OWNED = "O"         # Cache line is dirty but may be shared with other caches
    EXCLUSIVE = "E"     # Cache line is clean and owned by this cache only
    SHARED = "S"        # Cache line is clean and may be shared with other caches
    INVALID = "I"       # Cache line is invalid

class MessageType(Enum):
    """Coherency protocol messages"""
    READ_REQUEST = "read_req"
    WRITE_REQUEST = "write_req"
    INVALIDATE = "invalidate"
    DATA_RESPONSE = "data_resp"
    ACK = "ack"
    WRITEBACK = "writeback"
    UPGRADE = "upgrade"
    EVICTION = "eviction"

class AccessType(Enum):
    """Memory access types"""
    READ = "read"
    WRITE = "write"
    ATOMIC = "atomic"
    PREFETCH = "prefetch"

@dataclass
class CacheLine:
    """Represents a cache line in the coherency protocol"""
    address: int
    size: int
    data: Optional[bytes]
    state: CoherencyState
    device_id: str
    last_accessed: float
    access_count: int = 0
    dirty_timestamp: Optional[float] = None
    owner_id: Optional[str] = None
    sharers: Set[str] = field(default_factory=set)
    pending_requests: List[Any] = field(default_factory=list)

@dataclass
class CoherencyMessage:
    """Message for coherency protocol communication"""
    msg_type: MessageType
    source_device: str
    target_device: str
    address: int
    size: int
    data: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    transaction_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Transaction:
    """Memory transaction for tracking coherency operations"""
    transaction_id: str
    initiator: str
    access_type: AccessType
    address: int
    size: int
    timestamp: float
    completed_responses: Set[str] = field(default_factory=set)
    expected_responses: Set[str] = field(default_factory=set)
    data: Optional[bytes] = None
    is_complete: bool = False

class CoherencyDirectory:
    """Directory to track which devices have copies of each cache line"""
    
    def __init__(self):
        self.directory: Dict[int, Dict[str, CoherencyState]] = defaultdict(dict)
        self.lock = threading.RLock()
    
    def get_sharers(self, address: int) -> Set[str]:
        """Get all devices that have copies of this address"""
        with self.lock:
            return set(self.directory[address].keys())
    
    def get_state(self, address: int, device_id: str) -> CoherencyState:
        """Get coherency state for address on specific device"""
        with self.lock:
            return self.directory[address].get(device_id, CoherencyState.INVALID)
    
    def set_state(self, address: int, device_id: str, state: CoherencyState):
        """Set coherency state for address on specific device"""
        with self.lock:
            if state == CoherencyState.INVALID:
                self.directory[address].pop(device_id, None)
                if not self.directory[address]:
                    del self.directory[address]
            else:
                self.directory[address][device_id] = state
    
    def get_owner(self, address: int) -> Optional[str]:
        """Get the owner of a cache line (if any)"""
        with self.lock:
            for device_id, state in self.directory[address].items():
                if state in [CoherencyState.MODIFIED, CoherencyState.OWNED, CoherencyState.EXCLUSIVE]:
                    return device_id
            return None
    
    def invalidate_all_except(self, address: int, except_device: str) -> Set[str]:
        """Invalidate all copies except for specified device"""
        with self.lock:
            to_invalidate = set()
            for device_id in list(self.directory[address].keys()):
                if device_id != except_device:
                    self.directory[address][device_id] = CoherencyState.INVALID
                    to_invalidate.add(device_id)
            return to_invalidate

class MOESICoherencyProtocol:
    """MOESI coherency protocol implementation"""
    
    def __init__(self, hardware_pool: UniversalHardwarePool):
        self.hardware_pool = hardware_pool
        self.directory = CoherencyDirectory()
        self.cache_lines: Dict[str, Dict[int, CacheLine]] = defaultdict(dict)
        self.message_queue: deque = deque()
        self.transactions: Dict[str, Transaction] = {}
        self.lock = threading.RLock()
        
        # Protocol parameters
        self.cache_line_size = 64  # bytes
        self.max_pending_transactions = 1000
        self.transaction_timeout = 30.0  # seconds
        
        # Statistics
        self.stats = {
            'read_hits': 0,
            'read_misses': 0,
            'write_hits': 0,
            'write_misses': 0,
            'invalidations': 0,
            'writebacks': 0,
            'coherency_messages': 0,
            'state_transitions': 0
        }
        
        # Start message processing thread
        self._running = True
        self._message_thread = threading.Thread(target=self._process_messages, daemon=True)
        self._message_thread.start()
    
    def read_memory(self, device_id: str, address: int, size: int) -> Optional[bytes]:
        """Read memory with coherency protocol"""
        
        try:
            with self.lock:
                cache_line_addr = self._align_to_cache_line(address)
                
                # Check local cache
                if self._has_valid_cache_line(device_id, cache_line_addr):
                    cache_line = self.cache_lines[device_id][cache_line_addr]
                    
                    if cache_line.state != CoherencyState.INVALID:
                        self.stats['read_hits'] += 1
                        cache_line.last_accessed = time.time()
                        cache_line.access_count += 1
                        
                        # Extract requested data from cache line
                        offset = address - cache_line_addr
                        return cache_line.data[offset:offset + size] if cache_line.data else None
                
                self.stats['read_misses'] += 1
                
                # Cache miss - need to fetch from another device or memory
                return self._handle_read_miss(device_id, address, size)
                
        except Exception as e:
            logger.error(f"Read memory failed: {e}")
            return None
    
    def write_memory(self, device_id: str, address: int, data: bytes) -> bool:
        """Write memory with coherency protocol"""
        
        try:
            with self.lock:
                cache_line_addr = self._align_to_cache_line(address)
                size = len(data)
                
                # Check local cache
                if self._has_valid_cache_line(device_id, cache_line_addr):
                    cache_line = self.cache_lines[device_id][cache_line_addr]
                    
                    if cache_line.state in [CoherencyState.MODIFIED, CoherencyState.EXCLUSIVE]:
                        # Can write directly
                        self.stats['write_hits'] += 1
                        return self._perform_local_write(device_id, address, data)
                    
                    elif cache_line.state in [CoherencyState.OWNED, CoherencyState.SHARED]:
                        # Need to upgrade to exclusive access
                        return self._handle_write_upgrade(device_id, address, data)
                
                self.stats['write_misses'] += 1
                
                # Cache miss - need to fetch exclusive access
                return self._handle_write_miss(device_id, address, data)
                
        except Exception as e:
            logger.error(f"Write memory failed: {e}")
            return False
    
    def _align_to_cache_line(self, address: int) -> int:
        """Align address to cache line boundary"""
        return (address // self.cache_line_size) * self.cache_line_size
    
    def _has_valid_cache_line(self, device_id: str, address: int) -> bool:
        """Check if device has valid cache line"""
        return (address in self.cache_lines[device_id] and 
                self.cache_lines[device_id][address].state != CoherencyState.INVALID)
    
    def _handle_read_miss(self, device_id: str, address: int, size: int) -> Optional[bytes]:
        """Handle read cache miss"""
        
        cache_line_addr = self._align_to_cache_line(address)
        
        # Check directory for current owner/sharers
        owner = self.directory.get_owner(cache_line_addr)
        sharers = self.directory.get_sharers(cache_line_addr)
        
        if owner and owner != device_id:
            # Request data from owner
            data = self._request_data_from_owner(device_id, owner, cache_line_addr)
            if data:
                # Create cache line in shared state
                cache_line = CacheLine(
                    address=cache_line_addr,
                    size=self.cache_line_size,
                    data=data,
                    state=CoherencyState.SHARED,
                    device_id=device_id,
                    last_accessed=time.time()
                )
                
                self.cache_lines[device_id][cache_line_addr] = cache_line
                self.directory.set_state(cache_line_addr, device_id, CoherencyState.SHARED)
                
                # Update owner state if it was exclusive
                if self.directory.get_state(cache_line_addr, owner) == CoherencyState.EXCLUSIVE:
                    self.directory.set_state(cache_line_addr, owner, CoherencyState.SHARED)
                
                # Extract requested data
                offset = address - cache_line_addr
                return data[offset:offset + size]
        
        elif sharers and device_id not in sharers:
            # Request data from any sharer
            for sharer in sharers:
                if sharer != device_id:
                    data = self._request_data_from_sharer(device_id, sharer, cache_line_addr)
                    if data:
                        # Create cache line in shared state
                        cache_line = CacheLine(
                            address=cache_line_addr,
                            size=self.cache_line_size,
                            data=data,
                            state=CoherencyState.SHARED,
                            device_id=device_id,
                            last_accessed=time.time()
                        )
                        
                        self.cache_lines[device_id][cache_line_addr] = cache_line
                        self.directory.set_state(cache_line_addr, device_id, CoherencyState.SHARED)
                        
                        # Extract requested data
                        offset = address - cache_line_addr
                        return data[offset:offset + size]
        
        else:
            # No other copies exist - load from main memory
            data = self._load_from_main_memory(cache_line_addr, self.cache_line_size)
            if data:
                cache_line = CacheLine(
                    address=cache_line_addr,
                    size=self.cache_line_size,
                    data=data,
                    state=CoherencyState.EXCLUSIVE,
                    device_id=device_id,
                    last_accessed=time.time()
                )
                
                self.cache_lines[device_id][cache_line_addr] = cache_line
                self.directory.set_state(cache_line_addr, device_id, CoherencyState.EXCLUSIVE)
                
                # Extract requested data
                offset = address - cache_line_addr
                return data[offset:offset + size]
        
        return None
    
    def _handle_write_miss(self, device_id: str, address: int, data: bytes) -> bool:
        """Handle write cache miss"""
        
        cache_line_addr = self._align_to_cache_line(address)
        
        # Need exclusive access for writing
        sharers = self.directory.get_sharers(cache_line_addr)
        
        if sharers:
            # Invalidate all other copies
            invalidated = self._send_invalidation_messages(cache_line_addr, sharers - {device_id})
            if not invalidated:
                return False
        
        # Load cache line and mark as modified
        cache_line_data = self._load_from_main_memory(cache_line_addr, self.cache_line_size)
        if not cache_line_data:
            cache_line_data = b'\x00' * self.cache_line_size
        
        # Apply the write
        cache_line_data = bytearray(cache_line_data)
        offset = address - cache_line_addr
        cache_line_data[offset:offset + len(data)] = data
        
        cache_line = CacheLine(
            address=cache_line_addr,
            size=self.cache_line_size,
            data=bytes(cache_line_data),
            state=CoherencyState.MODIFIED,
            device_id=device_id,
            last_accessed=time.time(),
            dirty_timestamp=time.time()
        )
        
        self.cache_lines[device_id][cache_line_addr] = cache_line
        self.directory.set_state(cache_line_addr, device_id, CoherencyState.MODIFIED)
        
        return True
    
    def _handle_write_upgrade(self, device_id: str, address: int, data: bytes) -> bool:
        """Handle write to shared cache line (upgrade to exclusive)"""
        
        cache_line_addr = self._align_to_cache_line(address)
        sharers = self.directory.get_sharers(cache_line_addr)
        
        # Send invalidation to all other sharers
        other_sharers = sharers - {device_id}
        if other_sharers:
            invalidated = self._send_invalidation_messages(cache_line_addr, other_sharers)
            if not invalidated:
                return False
        
        # Upgrade local cache line to modified
        cache_line = self.cache_lines[device_id][cache_line_addr]
        
        # Apply the write
        cache_line_data = bytearray(cache_line.data or b'\x00' * self.cache_line_size)
        offset = address - cache_line_addr
        cache_line_data[offset:offset + len(data)] = data
        
        cache_line.data = bytes(cache_line_data)
        cache_line.state = CoherencyState.MODIFIED
        cache_line.dirty_timestamp = time.time()
        cache_line.last_accessed = time.time()
        
        self.directory.set_state(cache_line_addr, device_id, CoherencyState.MODIFIED)
        
        return True
    
    def _perform_local_write(self, device_id: str, address: int, data: bytes) -> bool:
        """Perform write to cache line already in modified/exclusive state"""
        
        cache_line_addr = self._align_to_cache_line(address)
        cache_line = self.cache_lines[device_id][cache_line_addr]
        
        # Apply the write
        cache_line_data = bytearray(cache_line.data or b'\x00' * self.cache_line_size)
        offset = address - cache_line_addr
        cache_line_data[offset:offset + len(data)] = data
        
        cache_line.data = bytes(cache_line_data)
        cache_line.state = CoherencyState.MODIFIED
        cache_line.dirty_timestamp = time.time()
        cache_line.last_accessed = time.time()
        
        self.directory.set_state(cache_line_addr, device_id, CoherencyState.MODIFIED)
        
        return True
    
    def _request_data_from_owner(self, requester: str, owner: str, address: int) -> Optional[bytes]:
        """Request data from the owner of a cache line"""
        
        # Create transaction
        transaction_id = self._generate_transaction_id()
        transaction = Transaction(
            transaction_id=transaction_id,
            initiator=requester,
            access_type=AccessType.READ,
            address=address,
            size=self.cache_line_size,
            timestamp=time.time(),
            expected_responses={owner}
        )
        
        self.transactions[transaction_id] = transaction
        
        # Send read request message
        message = CoherencyMessage(
            msg_type=MessageType.READ_REQUEST,
            source_device=requester,
            target_device=owner,
            address=address,
            size=self.cache_line_size,
            transaction_id=transaction_id
        )
        
        self._send_message(message)
        
        # Wait for response (simplified - would use proper synchronization)
        timeout = time.time() + 5.0  # 5 second timeout
        while time.time() < timeout:
            if transaction.is_complete and transaction.data:
                data = transaction.data
                del self.transactions[transaction_id]
                return data
            time.sleep(0.001)
        
        # Timeout
        del self.transactions[transaction_id]
        return None
    
    def _request_data_from_sharer(self, requester: str, sharer: str, address: int) -> Optional[bytes]:
        """Request data from a sharer of a cache line"""
        return self._request_data_from_owner(requester, sharer, address)
    
    def _send_invalidation_messages(self, address: int, targets: Set[str]) -> bool:
        """Send invalidation messages to target devices"""
        
        if not targets:
            return True
        
        transaction_id = self._generate_transaction_id()
        transaction = Transaction(
            transaction_id=transaction_id,
            initiator="coherency_controller",
            access_type=AccessType.WRITE,
            address=address,
            size=self.cache_line_size,
            timestamp=time.time(),
            expected_responses=targets.copy()
        )
        
        self.transactions[transaction_id] = transaction
        
        # Send invalidation messages
        for target in targets:
            message = CoherencyMessage(
                msg_type=MessageType.INVALIDATE,
                source_device="coherency_controller",
                target_device=target,
                address=address,
                size=self.cache_line_size,
                transaction_id=transaction_id
            )
            self._send_message(message)
        
        # Wait for acknowledgments
        timeout = time.time() + 5.0
        while time.time() < timeout:
            if transaction.is_complete:
                del self.transactions[transaction_id]
                return True
            time.sleep(0.001)
        
        # Timeout
        del self.transactions[transaction_id]
        return False
    
    def _load_from_main_memory(self, address: int, size: int) -> Optional[bytes]:
        """Load data from main memory (simplified)"""
        # In real implementation, this would load from the distributed data store
        return b'\x00' * size
    
    def _generate_transaction_id(self) -> str:
        """Generate unique transaction ID"""
        return f"txn_{int(time.time() * 1000000)}_{threading.current_thread().ident}"
    
    def _send_message(self, message: CoherencyMessage):
        """Send coherency protocol message"""
        with self.lock:
            self.message_queue.append(message)
            self.stats['coherency_messages'] += 1
    
    def _process_messages(self):
        """Process coherency protocol messages"""
        
        while self._running:
            try:
                with self.lock:
                    if self.message_queue:
                        message = self.message_queue.popleft()
                    else:
                        message = None
                
                if message:
                    self._handle_message(message)
                else:
                    time.sleep(0.001)  # Small delay when no messages
                    
            except Exception as e:
                logger.error(f"Message processing error: {e}")
                time.sleep(0.1)
    
    def _handle_message(self, message: CoherencyMessage):
        """Handle incoming coherency message"""
        
        try:
            if message.msg_type == MessageType.READ_REQUEST:
                self._handle_read_request(message)
            elif message.msg_type == MessageType.WRITE_REQUEST:
                self._handle_write_request(message)
            elif message.msg_type == MessageType.INVALIDATE:
                self._handle_invalidation(message)
            elif message.msg_type == MessageType.DATA_RESPONSE:
                self._handle_data_response(message)
            elif message.msg_type == MessageType.ACK:
                self._handle_acknowledgment(message)
            elif message.msg_type == MessageType.WRITEBACK:
                self._handle_writeback(message)
            
        except Exception as e:
            logger.error(f"Failed to handle message {message.msg_type}: {e}")
    
    def _handle_read_request(self, message: CoherencyMessage):
        """Handle read request from another device"""
        
        device_id = message.target_device
        address = message.address
        
        if address in self.cache_lines[device_id]:
            cache_line = self.cache_lines[device_id][address]
            
            if cache_line.state in [CoherencyState.MODIFIED, CoherencyState.OWNED, CoherencyState.EXCLUSIVE, CoherencyState.SHARED]:
                # Send data response
                response = CoherencyMessage(
                    msg_type=MessageType.DATA_RESPONSE,
                    source_device=device_id,
                    target_device=message.source_device,
                    address=address,
                    size=message.size,
                    data=cache_line.data,
                    transaction_id=message.transaction_id
                )
                
                self._send_message(response)
                
                # Update state if was exclusive
                if cache_line.state == CoherencyState.EXCLUSIVE:
                    cache_line.state = CoherencyState.SHARED
                    self.directory.set_state(address, device_id, CoherencyState.SHARED)
                    self.stats['state_transitions'] += 1
    
    def _handle_invalidation(self, message: CoherencyMessage):
        """Handle invalidation request"""
        
        device_id = message.target_device
        address = message.address
        
        if address in self.cache_lines[device_id]:
            cache_line = self.cache_lines[device_id][address]
            
            # If cache line is dirty, need to write back
            if cache_line.state in [CoherencyState.MODIFIED, CoherencyState.OWNED]:
                self._perform_writeback(device_id, cache_line)
            
            # Invalidate cache line
            cache_line.state = CoherencyState.INVALID
            self.directory.set_state(address, device_id, CoherencyState.INVALID)
            self.stats['invalidations'] += 1
            self.stats['state_transitions'] += 1
        
        # Send acknowledgment
        ack = CoherencyMessage(
            msg_type=MessageType.ACK,
            source_device=device_id,
            target_device=message.source_device,
            address=address,
            size=message.size,
            transaction_id=message.transaction_id
        )
        
        self._send_message(ack)
    
    def _handle_data_response(self, message: CoherencyMessage):
        """Handle data response"""
        
        if message.transaction_id in self.transactions:
            transaction = self.transactions[message.transaction_id]
            transaction.data = message.data
            transaction.completed_responses.add(message.source_device)
            
            if transaction.completed_responses >= transaction.expected_responses:
                transaction.is_complete = True
    
    def _handle_acknowledgment(self, message: CoherencyMessage):
        """Handle acknowledgment"""
        
        if message.transaction_id in self.transactions:
            transaction = self.transactions[message.transaction_id]
            transaction.completed_responses.add(message.source_device)
            
            if transaction.completed_responses >= transaction.expected_responses:
                transaction.is_complete = True
    
    def _handle_writeback(self, message: CoherencyMessage):
        """Handle writeback from another device"""
        
        # Update main memory with written data
        # In real implementation, this would update the distributed data store
        logger.debug(f"Writeback received for address {message.address}")
    
    def _perform_writeback(self, device_id: str, cache_line: CacheLine):
        """Perform writeback of dirty cache line"""
        
        if cache_line.data:
            writeback_msg = CoherencyMessage(
                msg_type=MessageType.WRITEBACK,
                source_device=device_id,
                target_device="main_memory",
                address=cache_line.address,
                size=cache_line.size,
                data=cache_line.data
            )
            
            self._send_message(writeback_msg)
            self.stats['writebacks'] += 1
    
    def evict_cache_line(self, device_id: str, address: int) -> bool:
        """Evict cache line from device"""
        
        try:
            with self.lock:
                if address not in self.cache_lines[device_id]:
                    return True
                
                cache_line = self.cache_lines[device_id][address]
                
                # Writeback if dirty
                if cache_line.state in [CoherencyState.MODIFIED, CoherencyState.OWNED]:
                    self._perform_writeback(device_id, cache_line)
                
                # Remove from cache and directory
                del self.cache_lines[device_id][address]
                self.directory.set_state(address, device_id, CoherencyState.INVALID)
                
                logger.debug(f"Evicted cache line {address} from device {device_id}")
                return True
                
        except Exception as e:
            logger.error(f"Cache line eviction failed: {e}")
            return False
    
    def get_coherency_state(self, device_id: str, address: int) -> CoherencyState:
        """Get coherency state for address on device"""
        return self.directory.get_state(address, device_id)
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """Get cache and coherency statistics"""
        
        with self.lock:
            # Calculate additional stats
            total_cache_lines = sum(len(cache) for cache in self.cache_lines.values())
            pending_transactions = len(self.transactions)
            
            # Calculate hit rates
            total_reads = self.stats['read_hits'] + self.stats['read_misses']
            total_writes = self.stats['write_hits'] + self.stats['write_misses']
            
            read_hit_rate = (self.stats['read_hits'] / max(1, total_reads)) * 100
            write_hit_rate = (self.stats['write_hits'] / max(1, total_writes)) * 100
            
            return {
                **self.stats,
                'total_cache_lines': total_cache_lines,
                'pending_transactions': pending_transactions,
                'read_hit_rate': read_hit_rate,
                'write_hit_rate': write_hit_rate,
                'message_queue_size': len(self.message_queue)
            }
    
    def shutdown(self):
        """Shutdown coherency protocol"""
        
        self._running = False
        
        # Writeback all dirty cache lines
        with self.lock:
            for device_id, device_cache in self.cache_lines.items():
                for address, cache_line in device_cache.items():
                    if cache_line.state in [CoherencyState.MODIFIED, CoherencyState.OWNED]:
                        self._perform_writeback(device_id, cache_line)
        
        # Wait for message thread to finish
        if self._message_thread.is_alive():
            self._message_thread.join(timeout=5.0)
        
        logger.info("MOESI coherency protocol shutdown complete")
"""
KOS Distributed Cluster Implementation
Server-oriented distributed computing system
"""

import socket
import threading
import time
import json
import pickle
import hashlib
import uuid
import struct
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class NodeState(Enum):
    """Node states in cluster"""
    DISCOVERING = "discovering"
    JOINING = "joining"
    SYNCING = "syncing"
    ACTIVE = "active"
    LEAVING = "leaving"
    DISCONNECTED = "disconnected"
    RECOVERING = "recovering"
    FAILED = "failed"

class NodeRole(Enum):
    """Node roles in Raft consensus"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class MessageType(Enum):
    """Cluster message types"""
    # Discovery
    HELLO = 0x01
    PING = 0x02
    PONG = 0x03
    INFO = 0x04
    
    # Consensus
    VOTE_REQUEST = 0x10
    VOTE_REPLY = 0x11
    APPEND_ENTRIES = 0x12
    HEARTBEAT = 0x13
    
    # Operations
    EXEC = 0x20
    READ = 0x21
    WRITE = 0x22
    LOCK = 0x23
    UNLOCK = 0x24
    
    # Synchronization
    SYNC_REQUEST = 0x30
    SYNC_DATA = 0x31
    SYNC_ACK = 0x32
    STATE_UPDATE = 0x33
    
    # Cluster Management
    JOIN_REQUEST = 0x40
    JOIN_ACCEPTED = 0x41
    LEAVE_NOTICE = 0x42
    NODE_FAILED = 0x43

@dataclass
class NodeInfo:
    """Information about a cluster node"""
    node_id: str
    address: str
    port: int
    state: NodeState
    role: NodeRole
    last_seen: float
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    network_latency: float = 0.0
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)

@dataclass
class ClusterMessage:
    """Message format for cluster communication"""
    msg_type: MessageType
    source_id: str
    dest_id: str
    message_id: str
    timestamp: float
    vector_clock: Dict[str, int]
    payload: Any
    signature: Optional[bytes] = None
    
    def serialize(self) -> bytes:
        """Serialize message to bytes"""
        data = {
            'type': self.msg_type.value,
            'source': self.source_id,
            'dest': self.dest_id,
            'id': self.message_id,
            'timestamp': self.timestamp,
            'vector_clock': self.vector_clock,
            'payload': self.payload
        }
        return pickle.dumps(data)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'ClusterMessage':
        """Deserialize message from bytes"""
        obj = pickle.loads(data)
        return cls(
            msg_type=MessageType(obj['type']),
            source_id=obj['source'],
            dest_id=obj['dest'],
            message_id=obj['id'],
            timestamp=obj['timestamp'],
            vector_clock=obj['vector_clock'],
            payload=obj['payload']
        )

class ConsistentHash:
    """Consistent hashing for data distribution"""
    
    def __init__(self, nodes: List[str] = None, virtual_nodes: int = 150):
        self.nodes = nodes or []
        self.virtual_nodes = virtual_nodes
        self.ring: Dict[int, str] = {}
        self._build_ring()
    
    def _hash(self, key: str) -> int:
        """Hash function"""
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
    
    def _build_ring(self):
        """Build the hash ring"""
        self.ring = {}
        for node in self.nodes:
            for i in range(self.virtual_nodes):
                virtual_key = f"{node}:{i}"
                hash_value = self._hash(virtual_key)
                self.ring[hash_value] = node
    
    def add_node(self, node: str):
        """Add node to ring"""
        if node not in self.nodes:
            self.nodes.append(node)
            self._build_ring()
    
    def remove_node(self, node: str):
        """Remove node from ring"""
        if node in self.nodes:
            self.nodes.remove(node)
            self._build_ring()
    
    def get_node(self, key: str) -> Optional[str]:
        """Get node responsible for key"""
        if not self.ring:
            return None
        
        hash_value = self._hash(key)
        
        # Find the first node clockwise from the hash
        for node_hash in sorted(self.ring.keys()):
            if node_hash >= hash_value:
                return self.ring[node_hash]
        
        # Wrap around to first node
        return self.ring[min(self.ring.keys())]
    
    def get_nodes(self, key: str, count: int = 3) -> List[str]:
        """Get N nodes for replication"""
        if not self.ring:
            return []
        
        nodes = []
        hash_value = self._hash(key)
        sorted_hashes = sorted(self.ring.keys())
        
        # Find starting position
        start_idx = 0
        for i, node_hash in enumerate(sorted_hashes):
            if node_hash >= hash_value:
                start_idx = i
                break
        
        # Get N unique nodes
        seen = set()
        idx = start_idx
        while len(nodes) < count and len(seen) < len(self.nodes):
            node = self.ring[sorted_hashes[idx % len(sorted_hashes)]]
            if node not in seen:
                nodes.append(node)
                seen.add(node)
            idx += 1
        
        return nodes

class VectorClock:
    """Vector clock for causality tracking"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.clock: Dict[str, int] = {node_id: 0}
    
    def increment(self):
        """Increment local clock"""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
    
    def update(self, other_clock: Dict[str, int]):
        """Update with received clock"""
        for node, timestamp in other_clock.items():
            self.clock[node] = max(self.clock.get(node, 0), timestamp)
        self.increment()
    
    def happens_before(self, other: Dict[str, int]) -> bool:
        """Check if this clock happens before other"""
        for node, timestamp in self.clock.items():
            if timestamp > other.get(node, 0):
                return False
        return any(timestamp < other.get(node, 0) for node, timestamp in other.items())
    
    def concurrent_with(self, other: Dict[str, int]) -> bool:
        """Check if events are concurrent"""
        return not self.happens_before(other) and not self._other_happens_before(other)
    
    def _other_happens_before(self, other: Dict[str, int]) -> bool:
        """Check if other happens before this"""
        for node, timestamp in other.items():
            if timestamp > self.clock.get(node, 0):
                return False
        return any(timestamp < self.clock.get(node, 0) for node, timestamp in self.clock.items())
    
    def get_clock(self) -> Dict[str, int]:
        """Get current clock state"""
        return self.clock.copy()

class RaftConsensus:
    """Raft consensus protocol implementation"""
    
    def __init__(self, node_id: str, cluster):
        self.node_id = node_id
        self.cluster = cluster
        self.state = NodeRole.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[Dict] = []
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timing
        self.election_timeout = 0
        self.last_heartbeat = time.time()
        self._reset_election_timeout()
        
        # Thread control
        self.running = True
        self.election_thread = threading.Thread(target=self._election_timer)
        self.election_thread.daemon = True
    
    def start(self):
        """Start consensus protocol"""
        self.election_thread.start()
    
    def stop(self):
        """Stop consensus protocol"""
        self.running = False
    
    def _reset_election_timeout(self):
        """Reset election timeout to random value"""
        import random
        self.election_timeout = time.time() + random.uniform(0.15, 0.3)
    
    def _election_timer(self):
        """Election timeout thread"""
        while self.running:
            if self.state != NodeRole.LEADER:
                if time.time() > self.election_timeout:
                    self._start_election()
            else:
                # Send heartbeats as leader
                self._send_heartbeats()
            
            time.sleep(0.05)  # 50ms check interval
    
    def _start_election(self):
        """Start leader election"""
        self.state = NodeRole.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self._reset_election_timeout()
        
        # Vote for self
        votes = 1
        
        # Request votes from other nodes
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.node_id:
                vote_request = {
                    'term': self.current_term,
                    'candidate_id': self.node_id,
                    'last_log_index': len(self.log) - 1,
                    'last_log_term': self.log[-1]['term'] if self.log else 0
                }
                
                reply = self.cluster.send_message(
                    node_id,
                    MessageType.VOTE_REQUEST,
                    vote_request
                )
                
                if reply and reply.get('vote_granted'):
                    votes += 1
        
        # Check if won election
        if votes > len(self.cluster.get_active_nodes()) / 2:
            self._become_leader()
        else:
            self.state = NodeRole.FOLLOWER
    
    def _become_leader(self):
        """Become the leader"""
        self.state = NodeRole.LEADER
        logger.info(f"Node {self.node_id} became leader for term {self.current_term}")
        
        # Initialize leader state
        for node_id in self.cluster.get_active_nodes():
            self.next_index[node_id] = len(self.log)
            self.match_index[node_id] = 0
        
        # Send initial heartbeat
        self._send_heartbeats()
    
    def _send_heartbeats(self):
        """Send heartbeats to all followers"""
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.node_id:
                self.cluster.send_message(
                    node_id,
                    MessageType.HEARTBEAT,
                    {'term': self.current_term, 'leader_id': self.node_id}
                )
        
        self.last_heartbeat = time.time()
    
    def handle_vote_request(self, request: Dict) -> Dict:
        """Handle vote request from candidate"""
        term = request['term']
        candidate_id = request['candidate_id']
        
        # Update term if necessary
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            self.state = NodeRole.FOLLOWER
        
        # Grant vote if haven't voted and candidate's log is up-to-date
        vote_granted = False
        if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
            # Check log is up-to-date
            last_log_index = len(self.log) - 1
            last_log_term = self.log[-1]['term'] if self.log else 0
            
            if (request['last_log_term'] > last_log_term or
                (request['last_log_term'] == last_log_term and request['last_log_index'] >= last_log_index)):
                vote_granted = True
                self.voted_for = candidate_id
                self._reset_election_timeout()
        
        return {'term': self.current_term, 'vote_granted': vote_granted}
    
    def handle_heartbeat(self, heartbeat: Dict):
        """Handle heartbeat from leader"""
        term = heartbeat['term']
        
        if term >= self.current_term:
            self.current_term = term
            self.state = NodeRole.FOLLOWER
            self._reset_election_timeout()
    
    def is_leader(self) -> bool:
        """Check if this node is the leader"""
        return self.state == NodeRole.LEADER
    
    def get_leader(self) -> Optional[str]:
        """Get current leader ID"""
        if self.state == NodeRole.LEADER:
            return self.node_id
        # Would need to track this from heartbeats
        return None

class ClusterNode:
    """Single node in the KOS cluster"""
    
    def __init__(self, node_id: str = None, address: str = "0.0.0.0", port: int = 9000):
        self.node_id = node_id or str(uuid.uuid4())
        self.address = address
        self.port = port
        self.state = NodeState.DISCONNECTED
        
        # Cluster members
        self.nodes: Dict[str, NodeInfo] = {}
        self.nodes[self.node_id] = NodeInfo(
            node_id=self.node_id,
            address=address,
            port=port,
            state=NodeState.ACTIVE,
            role=NodeRole.FOLLOWER,
            last_seen=time.time()
        )
        
        # Networking
        self.server_socket: Optional[socket.socket] = None
        self.client_sockets: Dict[str, socket.socket] = {}
        self.message_handlers: Dict[MessageType, Any] = {}
        
        # Consensus
        self.consensus = RaftConsensus(self.node_id, self)
        
        # Data distribution
        self.consistent_hash = ConsistentHash([self.node_id])
        
        # Vector clock
        self.vector_clock = VectorClock(self.node_id)
        
        # Thread control
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        self.discovery_thread: Optional[threading.Thread] = None
        
        # Cluster info
        self.cluster_name: Optional[str] = None
        self.cluster_key: Optional[bytes] = None
        
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers"""
        self.message_handlers[MessageType.PING] = self._handle_ping
        self.message_handlers[MessageType.JOIN_REQUEST] = self._handle_join_request
        self.message_handlers[MessageType.VOTE_REQUEST] = self._handle_vote_request
        self.message_handlers[MessageType.HEARTBEAT] = self._handle_heartbeat
        self.message_handlers[MessageType.STATE_UPDATE] = self._handle_state_update
    
    def create_cluster(self, cluster_name: str) -> bool:
        """Create a new cluster"""
        self.cluster_name = cluster_name
        self.cluster_key = hashlib.sha256(cluster_name.encode()).digest()
        self.state = NodeState.ACTIVE
        
        # Start services
        self.start_server()
        self.consensus.start()
        
        # Become leader since we're the only node
        self.consensus._become_leader()
        
        logger.info(f"Created cluster '{cluster_name}' with node {self.node_id}")
        return True
    
    def join_cluster(self, cluster_name: str, target_address: str, target_port: int = 9000) -> bool:
        """Join existing cluster"""
        self.cluster_name = cluster_name
        self.cluster_key = hashlib.sha256(cluster_name.encode()).digest()
        self.state = NodeState.JOINING
        
        # Connect to target node
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((target_address, target_port))
            
            # Send join request
            join_request = {
                'cluster_name': cluster_name,
                'node_info': {
                    'node_id': self.node_id,
                    'address': self.address,
                    'port': self.port,
                    'version': '1.0.0'
                }
            }
            
            message = ClusterMessage(
                msg_type=MessageType.JOIN_REQUEST,
                source_id=self.node_id,
                dest_id='cluster',
                message_id=str(uuid.uuid4()),
                timestamp=time.time(),
                vector_clock=self.vector_clock.get_clock(),
                payload=join_request
            )
            
            self._send_message(sock, message)
            
            # Wait for response
            response = self._receive_message(sock)
            
            if response and response.msg_type == MessageType.JOIN_ACCEPTED:
                # Update cluster state
                cluster_state = response.payload
                self.nodes = cluster_state['nodes']
                self.state = NodeState.SYNCING
                
                # Start services
                self.start_server()
                self.consensus.start()
                
                # Sync VFS and other state
                self._sync_state(cluster_state)
                
                self.state = NodeState.ACTIVE
                logger.info(f"Joined cluster '{cluster_name}'")
                return True
                
        except Exception as e:
            logger.error(f"Failed to join cluster: {e}")
            self.state = NodeState.DISCONNECTED
            
        return False
    
    def start_server(self):
        """Start cluster server"""
        self.running = True
        
        # Start server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.address, self.port))
        self.server_socket.listen(10)
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._server_loop)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start discovery thread
        self.discovery_thread = threading.Thread(target=self._discovery_loop)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()
    
    def stop(self):
        """Stop cluster node"""
        self.running = False
        self.consensus.stop()
        
        if self.server_socket:
            self.server_socket.close()
        
        for sock in self.client_sockets.values():
            sock.close()
    
    def _server_loop(self):
        """Main server loop"""
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                
                # Handle client in new thread
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, addr)
                )
                thread.daemon = True
                thread.start()
                
            except Exception as e:
                if self.running:
                    logger.error(f"Server error: {e}")
    
    def _handle_client(self, client_sock: socket.socket, addr: Tuple[str, int]):
        """Handle client connection"""
        try:
            while self.running:
                message = self._receive_message(client_sock)
                if not message:
                    break
                
                # Update vector clock
                self.vector_clock.update(message.vector_clock)
                
                # Handle message
                handler = self.message_handlers.get(message.msg_type)
                if handler:
                    response = handler(message)
                    if response:
                        self._send_message(client_sock, response)
                        
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            client_sock.close()
    
    def _discovery_loop(self):
        """Periodic discovery and health check"""
        while self.running:
            try:
                # Check node health
                for node_id, node_info in list(self.nodes.items()):
                    if node_id == self.node_id:
                        continue
                    
                    # Check if node is alive
                    if time.time() - node_info.last_seen > 5.0:  # 5 second timeout
                        if node_info.state != NodeState.FAILED:
                            logger.warning(f"Node {node_id} suspected failed")
                            node_info.state = NodeState.FAILED
                            self._handle_node_failure(node_id)
                    
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Discovery error: {e}")
    
    def _handle_ping(self, message: ClusterMessage) -> ClusterMessage:
        """Handle ping message"""
        return ClusterMessage(
            msg_type=MessageType.PONG,
            source_id=self.node_id,
            dest_id=message.source_id,
            message_id=str(uuid.uuid4()),
            timestamp=time.time(),
            vector_clock=self.vector_clock.get_clock(),
            payload={'status': 'alive'}
        )
    
    def _handle_join_request(self, message: ClusterMessage) -> ClusterMessage:
        """Handle join request"""
        if not self.consensus.is_leader():
            # Forward to leader
            leader = self.consensus.get_leader()
            if leader:
                return self.send_message(leader, MessageType.JOIN_REQUEST, message.payload)
            return None
        
        # Validate cluster name
        if message.payload['cluster_name'] != self.cluster_name:
            return None
        
        # Add new node
        node_info = message.payload['node_info']
        new_node = NodeInfo(
            node_id=node_info['node_id'],
            address=node_info['address'],
            port=node_info['port'],
            state=NodeState.ACTIVE,
            role=NodeRole.FOLLOWER,
            last_seen=time.time()
        )
        
        self.nodes[new_node.node_id] = new_node
        self.consistent_hash.add_node(new_node.node_id)
        
        # Send cluster state
        cluster_state = {
            'nodes': self.nodes,
            'leader': self.node_id,
            'vfs_snapshot': None,  # Would include VFS state
            'process_table': None  # Would include process state
        }
        
        return ClusterMessage(
            msg_type=MessageType.JOIN_ACCEPTED,
            source_id=self.node_id,
            dest_id=message.source_id,
            message_id=str(uuid.uuid4()),
            timestamp=time.time(),
            vector_clock=self.vector_clock.get_clock(),
            payload=cluster_state
        )
    
    def _handle_vote_request(self, message: ClusterMessage) -> ClusterMessage:
        """Handle vote request"""
        reply = self.consensus.handle_vote_request(message.payload)
        
        return ClusterMessage(
            msg_type=MessageType.VOTE_REPLY,
            source_id=self.node_id,
            dest_id=message.source_id,
            message_id=str(uuid.uuid4()),
            timestamp=time.time(),
            vector_clock=self.vector_clock.get_clock(),
            payload=reply
        )
    
    def _handle_heartbeat(self, message: ClusterMessage) -> None:
        """Handle heartbeat"""
        self.consensus.handle_heartbeat(message.payload)
        
        # Update node last seen
        if message.source_id in self.nodes:
            self.nodes[message.source_id].last_seen = time.time()
    
    def _handle_state_update(self, message: ClusterMessage) -> None:
        """Handle state update"""
        # Would update VFS, process table, etc.
        pass
    
    def _handle_node_failure(self, node_id: str):
        """Handle node failure"""
        logger.error(f"Node {node_id} failed")
        
        # Remove from hash ring
        self.consistent_hash.remove_node(node_id)
        
        # Trigger data redistribution
        # Would redistribute data and processes
    
    def _sync_state(self, cluster_state: Dict):
        """Sync state with cluster"""
        # Would sync VFS, processes, memory, etc.
        pass
    
    def send_message(self, dest_id: str, msg_type: MessageType, payload: Any) -> Optional[Any]:
        """Send message to another node"""
        if dest_id not in self.nodes:
            return None
        
        node = self.nodes[dest_id]
        
        # Get or create connection
        if dest_id not in self.client_sockets:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((node.address, node.port))
                self.client_sockets[dest_id] = sock
            except Exception as e:
                logger.error(f"Failed to connect to {dest_id}: {e}")
                return None
        
        sock = self.client_sockets[dest_id]
        
        # Create and send message
        message = ClusterMessage(
            msg_type=msg_type,
            source_id=self.node_id,
            dest_id=dest_id,
            message_id=str(uuid.uuid4()),
            timestamp=time.time(),
            vector_clock=self.vector_clock.get_clock(),
            payload=payload
        )
        
        self._send_message(sock, message)
        
        # Wait for response (simplified)
        response = self._receive_message(sock)
        return response.payload if response else None
    
    def _send_message(self, sock: socket.socket, message: ClusterMessage):
        """Send message over socket"""
        data = message.serialize()
        header = struct.pack('!I', len(data))
        sock.sendall(header + data)
        self.vector_clock.increment()
    
    def _receive_message(self, sock: socket.socket) -> Optional[ClusterMessage]:
        """Receive message from socket"""
        # Read header
        header = sock.recv(4)
        if not header:
            return None
        
        length = struct.unpack('!I', header)[0]
        
        # Read data
        data = b''
        while len(data) < length:
            chunk = sock.recv(min(4096, length - len(data)))
            if not chunk:
                return None
            data += chunk
        
        return ClusterMessage.deserialize(data)
    
    def get_active_nodes(self) -> List[str]:
        """Get list of active node IDs"""
        return [
            node_id for node_id, node in self.nodes.items()
            if node.state == NodeState.ACTIVE
        ]
    
    def get_cluster_status(self) -> Dict:
        """Get cluster status"""
        return {
            'cluster_name': self.cluster_name,
            'node_id': self.node_id,
            'state': self.state.value,
            'role': self.consensus.state.value,
            'nodes': len(self.nodes),
            'active_nodes': len(self.get_active_nodes()),
            'leader': self.consensus.get_leader()
        }
"""
Distributed Virtual File System for KOS
Provides synchronized filesystem across cluster nodes
"""

import os
import time
import threading
import hashlib
import json
import pickle
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class OperationType(Enum):
    """File operation types"""
    CREATE = "create"
    WRITE = "write"
    DELETE = "delete"
    RENAME = "rename"
    MKDIR = "mkdir"
    RMDIR = "rmdir"
    CHMOD = "chmod"
    CHOWN = "chown"

@dataclass
class FileOperation:
    """Represents a file system operation"""
    op_id: str
    op_type: OperationType
    path: str
    data: Optional[bytes] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    node_id: str = ""
    vector_clock: Dict[str, int] = field(default_factory=dict)

@dataclass 
class FileMetadata:
    """File metadata for distributed tracking"""
    path: str
    size: int
    checksum: str
    modified: float
    owner: str
    group: str
    permissions: int
    is_directory: bool
    replicas: List[str] = field(default_factory=list)
    version: int = 0
    locked_by: Optional[str] = None

class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL = "manual"
    MERGE = "merge"
    VERSION = "version"

class DistributedVFS:
    """Distributed Virtual File System"""
    
    def __init__(self, local_vfs, cluster_node, replication_factor: int = 3):
        self.local_vfs = local_vfs
        self.cluster = cluster_node
        self.replication_factor = replication_factor
        
        # Operation log for synchronization
        self.op_log: List[FileOperation] = []
        self.op_index: Dict[str, FileOperation] = {}
        
        # File metadata cache
        self.metadata_cache: Dict[str, FileMetadata] = {}
        
        # Conflict resolution
        self.conflict_strategy = ConflictResolution.LAST_WRITE_WINS
        self.conflicts: List[Tuple[FileOperation, FileOperation]] = []
        
        # Locks for distributed operations
        self.file_locks: Dict[str, str] = {}  # path -> node_id
        self.lock = threading.RLock()
        
        # Sync state
        self.last_sync: Dict[str, float] = {}  # node_id -> timestamp
        self.sync_in_progress = False
        
        # Background sync thread
        self.sync_thread = threading.Thread(target=self._sync_loop)
        self.sync_thread.daemon = True
        self.running = False
    
    def start(self):
        """Start distributed VFS"""
        self.running = True
        self.sync_thread.start()
        self._scan_local_files()
    
    def stop(self):
        """Stop distributed VFS"""
        self.running = False
    
    def _scan_local_files(self):
        """Scan local VFS and build metadata cache"""
        with self.lock:
            for path in self._walk_vfs('/'):
                if self.local_vfs.exists(path):
                    metadata = self._get_file_metadata(path)
                    self.metadata_cache[path] = metadata
    
    def _walk_vfs(self, path: str) -> List[str]:
        """Recursively walk VFS tree"""
        paths = []
        
        try:
            if self.local_vfs.isdir(path):
                paths.append(path)
                for item in self.local_vfs.listdir(path):
                    item_path = os.path.join(path, item)
                    paths.extend(self._walk_vfs(item_path))
            else:
                paths.append(path)
        except:
            pass
        
        return paths
    
    def _get_file_metadata(self, path: str) -> FileMetadata:
        """Get file metadata"""
        is_dir = self.local_vfs.isdir(path)
        
        if is_dir:
            size = 0
            checksum = ""
        else:
            # Read file for size and checksum
            try:
                with self.local_vfs.open(path, 'rb') as f:
                    data = f.read()
                    size = len(data)
                    checksum = hashlib.sha256(data).hexdigest()
            except:
                size = 0
                checksum = ""
        
        # Get file stats if available
        try:
            stat = self.local_vfs.stat(path) if hasattr(self.local_vfs, 'stat') else None
            if stat:
                modified = stat.st_mtime
                permissions = stat.st_mode
            else:
                modified = time.time()
                permissions = 0o644
        except:
            modified = time.time()
            permissions = 0o644
        
        return FileMetadata(
            path=path,
            size=size,
            checksum=checksum,
            modified=modified,
            owner="root",
            group="root",
            permissions=permissions,
            is_directory=is_dir,
            replicas=[self.cluster.node_id]
        )
    
    def _sync_loop(self):
        """Background synchronization loop"""
        while self.running:
            try:
                if not self.sync_in_progress:
                    self._sync_with_cluster()
                time.sleep(1)  # Sync every second
            except Exception as e:
                logger.error(f"Sync error: {e}")
    
    def _sync_with_cluster(self):
        """Synchronize with other cluster nodes"""
        self.sync_in_progress = True
        
        try:
            active_nodes = self.cluster.get_active_nodes()
            
            for node_id in active_nodes:
                if node_id == self.cluster.node_id:
                    continue
                
                # Get operations since last sync
                last_sync = self.last_sync.get(node_id, 0)
                
                # Send our operations
                our_ops = [op for op in self.op_log if op.timestamp > last_sync]
                if our_ops:
                    self._send_operations(node_id, our_ops)
                
                # Request their operations
                their_ops = self._request_operations(node_id, last_sync)
                if their_ops:
                    self._apply_operations(their_ops)
                
                self.last_sync[node_id] = time.time()
                
        finally:
            self.sync_in_progress = False
    
    def _send_operations(self, node_id: str, operations: List[FileOperation]):
        """Send operations to another node"""
        from .cluster import MessageType
        
        self.cluster.send_message(
            node_id,
            MessageType.SYNC_DATA,
            {'operations': operations}
        )
    
    def _request_operations(self, node_id: str, since: float) -> List[FileOperation]:
        """Request operations from another node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.SYNC_REQUEST,
            {'since': since}
        )
        
        return response.get('operations', []) if response else []
    
    def _apply_operations(self, operations: List[FileOperation]):
        """Apply remote operations to local VFS"""
        with self.lock:
            for op in operations:
                # Check for conflicts
                if self._check_conflict(op):
                    self._resolve_conflict(op)
                else:
                    self._apply_operation(op)
    
    def _check_conflict(self, op: FileOperation) -> bool:
        """Check if operation conflicts with local state"""
        if op.path in self.metadata_cache:
            local_meta = self.metadata_cache[op.path]
            
            # Check vector clock for causality
            if op.op_id in self.op_index:
                local_op = self.op_index[op.op_id]
                
                # If vector clocks are concurrent, we have a conflict
                local_vc = local_op.vector_clock
                remote_vc = op.vector_clock
                
                if self._are_concurrent(local_vc, remote_vc):
                    return True
        
        return False
    
    def _are_concurrent(self, vc1: Dict[str, int], vc2: Dict[str, int]) -> bool:
        """Check if two vector clocks are concurrent"""
        # Neither happens before the other
        happens_before_1 = all(vc1.get(k, 0) <= vc2.get(k, 0) for k in vc2)
        happens_before_2 = all(vc2.get(k, 0) <= vc1.get(k, 0) for k in vc1)
        
        return not happens_before_1 and not happens_before_2
    
    def _resolve_conflict(self, op: FileOperation):
        """Resolve conflict based on strategy"""
        if self.conflict_strategy == ConflictResolution.LAST_WRITE_WINS:
            # Apply operation if it's newer
            local_op = self.op_index.get(op.op_id)
            if not local_op or op.timestamp > local_op.timestamp:
                self._apply_operation(op)
        
        elif self.conflict_strategy == ConflictResolution.VERSION:
            # Create versioned file
            version_path = f"{op.path}.v{int(time.time())}"
            op_copy = FileOperation(
                op_id=op.op_id,
                op_type=op.op_type,
                path=version_path,
                data=op.data,
                metadata=op.metadata,
                timestamp=op.timestamp,
                node_id=op.node_id,
                vector_clock=op.vector_clock
            )
            self._apply_operation(op_copy)
        
        elif self.conflict_strategy == ConflictResolution.MERGE:
            # Attempt to merge (for text files)
            self._merge_files(op)
        
        else:  # MANUAL
            self.conflicts.append((self.op_index.get(op.op_id), op))
    
    def _merge_files(self, op: FileOperation):
        """Attempt to merge file contents"""
        # Simplified merge - would use proper 3-way merge
        if op.op_type == OperationType.WRITE and op.data:
            try:
                # Read local file
                with self.local_vfs.open(op.path, 'rb') as f:
                    local_data = f.read()
                
                # Simple merge: append remote changes
                merged = local_data + b'\n<<<< MERGE >>>>\n' + op.data
                
                with self.local_vfs.open(op.path, 'wb') as f:
                    f.write(merged)
                    
            except:
                # Fall back to last-write-wins
                self._apply_operation(op)
    
    def _apply_operation(self, op: FileOperation):
        """Apply operation to local VFS"""
        try:
            if op.op_type == OperationType.CREATE:
                with self.local_vfs.open(op.path, 'wb') as f:
                    if op.data:
                        f.write(op.data)
            
            elif op.op_type == OperationType.WRITE:
                with self.local_vfs.open(op.path, 'wb') as f:
                    if op.data:
                        f.write(op.data)
            
            elif op.op_type == OperationType.DELETE:
                if self.local_vfs.exists(op.path):
                    self.local_vfs.remove(op.path)
            
            elif op.op_type == OperationType.MKDIR:
                if not self.local_vfs.exists(op.path):
                    self.local_vfs.mkdir(op.path)
            
            elif op.op_type == OperationType.RMDIR:
                if self.local_vfs.exists(op.path):
                    self.local_vfs.rmdir(op.path)
            
            elif op.op_type == OperationType.RENAME:
                old_path = op.path
                new_path = op.metadata.get('new_path')
                if new_path and self.local_vfs.exists(old_path):
                    self.local_vfs.rename(old_path, new_path)
            
            # Update metadata cache
            if op.op_type != OperationType.DELETE:
                self.metadata_cache[op.path] = self._get_file_metadata(op.path)
            else:
                self.metadata_cache.pop(op.path, None)
            
            # Add to operation log
            self.op_log.append(op)
            self.op_index[op.op_id] = op
            
        except Exception as e:
            logger.error(f"Failed to apply operation {op.op_id}: {e}")
    
    # Public API
    
    def open(self, path: str, mode: str = 'r'):
        """Open file with distributed awareness"""
        # Acquire distributed lock if writing
        if 'w' in mode or 'a' in mode:
            if not self.acquire_lock(path):
                raise IOError(f"Could not acquire lock for {path}")
        
        return self.local_vfs.open(path, mode)
    
    def write(self, path: str, data: bytes) -> bool:
        """Write file with replication"""
        with self.lock:
            # Write locally
            try:
                with self.local_vfs.open(path, 'wb') as f:
                    f.write(data)
            except Exception as e:
                logger.error(f"Local write failed: {e}")
                return False
            
            # Create operation
            op = FileOperation(
                op_id=f"{self.cluster.node_id}:{time.time()}",
                op_type=OperationType.WRITE,
                path=path,
                data=data,
                node_id=self.cluster.node_id,
                vector_clock=self.cluster.vector_clock.get_clock()
            )
            
            # Add to log
            self.op_log.append(op)
            self.op_index[op.op_id] = op
            
            # Update metadata
            self.metadata_cache[path] = self._get_file_metadata(path)
            
            # Replicate to other nodes
            self._replicate_file(path, data)
            
            return True
    
    def read(self, path: str) -> Optional[bytes]:
        """Read file from nearest replica"""
        # Check local first
        if self.local_vfs.exists(path):
            try:
                with self.local_vfs.open(path, 'rb') as f:
                    return f.read()
            except:
                pass
        
        # Try remote replicas
        if path in self.metadata_cache:
            metadata = self.metadata_cache[path]
            for node_id in metadata.replicas:
                if node_id != self.cluster.node_id:
                    data = self._read_remote(node_id, path)
                    if data:
                        # Cache locally
                        self.write(path, data)
                        return data
        
        return None
    
    def delete(self, path: str) -> bool:
        """Delete file from all replicas"""
        with self.lock:
            # Delete locally
            if self.local_vfs.exists(path):
                self.local_vfs.remove(path)
            
            # Create operation
            op = FileOperation(
                op_id=f"{self.cluster.node_id}:{time.time()}",
                op_type=OperationType.DELETE,
                path=path,
                node_id=self.cluster.node_id,
                vector_clock=self.cluster.vector_clock.get_clock()
            )
            
            # Add to log
            self.op_log.append(op)
            self.op_index[op.op_id] = op
            
            # Remove from metadata
            self.metadata_cache.pop(path, None)
            
            # Delete from replicas
            self._delete_replicas(path)
            
            return True
    
    def mkdir(self, path: str) -> bool:
        """Create directory"""
        with self.lock:
            # Create locally
            if not self.local_vfs.exists(path):
                self.local_vfs.mkdir(path)
            
            # Create operation
            op = FileOperation(
                op_id=f"{self.cluster.node_id}:{time.time()}",
                op_type=OperationType.MKDIR,
                path=path,
                node_id=self.cluster.node_id,
                vector_clock=self.cluster.vector_clock.get_clock()
            )
            
            # Add to log
            self.op_log.append(op)
            self.op_index[op.op_id] = op
            
            # Update metadata
            self.metadata_cache[path] = self._get_file_metadata(path)
            
            return True
    
    def listdir(self, path: str) -> List[str]:
        """List directory contents"""
        # Combine local and remote listings
        items = set()
        
        # Local items
        if self.local_vfs.exists(path) and self.local_vfs.isdir(path):
            items.update(self.local_vfs.listdir(path))
        
        # Check metadata cache for distributed items
        path_prefix = path.rstrip('/') + '/'
        for file_path in self.metadata_cache:
            if file_path.startswith(path_prefix):
                # Extract immediate child
                relative = file_path[len(path_prefix):]
                if '/' not in relative:
                    items.add(relative)
        
        return sorted(list(items))
    
    def exists(self, path: str) -> bool:
        """Check if path exists anywhere in cluster"""
        # Check locally
        if self.local_vfs.exists(path):
            return True
        
        # Check metadata cache
        return path in self.metadata_cache
    
    def acquire_lock(self, path: str, timeout: float = 5.0) -> bool:
        """Acquire distributed lock on file"""
        start = time.time()
        
        while time.time() - start < timeout:
            with self.lock:
                if path not in self.file_locks:
                    # Try to acquire cluster-wide lock
                    if self._acquire_cluster_lock(path):
                        self.file_locks[path] = self.cluster.node_id
                        return True
            
            time.sleep(0.1)
        
        return False
    
    def release_lock(self, path: str):
        """Release distributed lock"""
        with self.lock:
            if path in self.file_locks and self.file_locks[path] == self.cluster.node_id:
                self._release_cluster_lock(path)
                del self.file_locks[path]
    
    def _acquire_cluster_lock(self, path: str) -> bool:
        """Acquire lock from cluster"""
        from .cluster import MessageType
        
        # Send lock request to leader
        response = self.cluster.send_message(
            self.cluster.consensus.get_leader() or self.cluster.node_id,
            MessageType.LOCK,
            {'path': path, 'node_id': self.cluster.node_id}
        )
        
        return response and response.get('granted', False)
    
    def _release_cluster_lock(self, path: str):
        """Release lock to cluster"""
        from .cluster import MessageType
        
        self.cluster.send_message(
            self.cluster.consensus.get_leader() or self.cluster.node_id,
            MessageType.UNLOCK,
            {'path': path, 'node_id': self.cluster.node_id}
        )
    
    def _replicate_file(self, path: str, data: bytes):
        """Replicate file to other nodes"""
        # Determine replica nodes using consistent hashing
        replica_nodes = self.cluster.consistent_hash.get_nodes(path, self.replication_factor)
        
        for node_id in replica_nodes:
            if node_id != self.cluster.node_id:
                self._send_replica(node_id, path, data)
    
    def _send_replica(self, node_id: str, path: str, data: bytes):
        """Send file replica to node"""
        from .cluster import MessageType
        
        self.cluster.send_message(
            node_id,
            MessageType.WRITE,
            {'path': path, 'data': data}
        )
    
    def _read_remote(self, node_id: str, path: str) -> Optional[bytes]:
        """Read file from remote node"""
        from .cluster import MessageType
        
        response = self.cluster.send_message(
            node_id,
            MessageType.READ,
            {'path': path}
        )
        
        return response.get('data') if response else None
    
    def _delete_replicas(self, path: str):
        """Delete file from replica nodes"""
        if path in self.metadata_cache:
            metadata = self.metadata_cache[path]
            
            from .cluster import MessageType
            
            for node_id in metadata.replicas:
                if node_id != self.cluster.node_id:
                    self.cluster.send_message(
                        node_id,
                        MessageType.WRITE,
                        {'path': path, 'delete': True}
                    )
    
    def get_file_info(self, path: str) -> Optional[Dict]:
        """Get distributed file information"""
        if path in self.metadata_cache:
            metadata = self.metadata_cache[path]
            return {
                'path': path,
                'size': metadata.size,
                'checksum': metadata.checksum,
                'modified': metadata.modified,
                'replicas': metadata.replicas,
                'version': metadata.version,
                'locked': metadata.locked_by is not None
            }
        return None
    
    def get_replication_status(self) -> Dict:
        """Get replication statistics"""
        total_files = len(self.metadata_cache)
        fully_replicated = sum(
            1 for m in self.metadata_cache.values()
            if len(m.replicas) >= self.replication_factor
        )
        
        return {
            'total_files': total_files,
            'fully_replicated': fully_replicated,
            'under_replicated': total_files - fully_replicated,
            'replication_factor': self.replication_factor,
            'conflicts': len(self.conflicts)
        }
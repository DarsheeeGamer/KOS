"""
Distributed Process Scheduler for KOS
Manages process distribution and load balancing across cluster
"""

import time
import threading
import pickle
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ProcessState(Enum):
    """Process states"""
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    MIGRATING = "migrating"
    COMPLETED = "completed"
    FAILED = "failed"

class SchedulingPolicy(Enum):
    """Scheduling policies"""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    DATA_LOCALITY = "data_locality"
    AFFINITY = "affinity"
    RANDOM = "random"

@dataclass
class DistributedProcess:
    """Distributed process information"""
    pid: int
    command: str
    args: List[str]
    env: Dict[str, str]
    working_dir: str
    owner_uid: int
    owner_gid: int
    state: ProcessState
    node_id: str  # Current node
    origin_node: str  # Where it started
    cpu_usage: float = 0.0
    memory_usage: int = 0
    start_time: float = 0.0
    checkpoint: Optional[bytes] = None
    affinity: Optional[str] = None  # Preferred node
    priority: int = 0
    
class DistributedScheduler:
    """Distributed process scheduler"""
    
    def __init__(self, cluster_node, local_executor):
        self.cluster = cluster_node
        self.executor = local_executor
        
        # Process tracking
        self.processes: Dict[int, DistributedProcess] = {}
        self.local_processes: Dict[int, DistributedProcess] = {}
        self.process_queue: List[DistributedProcess] = []
        
        # Scheduling
        self.policy = SchedulingPolicy.LEAST_LOADED
        self.node_loads: Dict[str, float] = {}
        
        # Migration
        self.migrations_in_progress: Dict[int, str] = {}  # pid -> target_node
        
        # Checkpointing
        self.checkpoint_interval = 60.0  # seconds
        self.last_checkpoint: Dict[int, float] = {}
        
        # Thread control
        self.lock = threading.RLock()
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.running = False
    
    def start(self):
        """Start scheduler"""
        self.running = True
        self.scheduler_thread.start()
        self.monitor_thread.start()
    
    def stop(self):
        """Stop scheduler"""
        self.running = False
    
    def submit_process(self, command: str, args: List[str] = None, 
                      env: Dict[str, str] = None, affinity: str = None) -> int:
        """Submit process for distributed execution"""
        with self.lock:
            # Generate distributed PID
            pid = self._generate_pid()
            
            # Create process object
            process = DistributedProcess(
                pid=pid,
                command=command,
                args=args or [],
                env=env or {},
                working_dir="/",
                owner_uid=0,  # Would get from current user
                owner_gid=0,
                state=ProcessState.PENDING,
                node_id="",
                origin_node=self.cluster.node_id,
                affinity=affinity,
                priority=0
            )
            
            # Add to tracking
            self.processes[pid] = process
            self.process_queue.append(process)
            
            logger.info(f"Submitted process {pid}: {command}")
            return pid
    
    def _scheduler_loop(self):
        """Main scheduling loop"""
        while self.running:
            try:
                with self.lock:
                    # Schedule pending processes
                    while self.process_queue:
                        process = self.process_queue[0]
                        
                        # Select node based on policy
                        target_node = self._select_node(process)
                        
                        if target_node:
                            # Schedule process
                            if self._schedule_on_node(process, target_node):
                                self.process_queue.pop(0)
                                process.state = ProcessState.SCHEDULED
                                process.node_id = target_node
                            else:
                                break  # Try again later
                        else:
                            break  # No suitable node available
                    
                    # Check for load balancing
                    self._check_load_balance()
                
                time.sleep(0.5)  # Schedule every 500ms
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
    
    def _monitor_loop(self):
        """Monitor processes and resources"""
        while self.running:
            try:
                with self.lock:
                    # Update node loads
                    self._update_node_loads()
                    
                    # Check local processes
                    for pid, process in list(self.local_processes.items()):
                        if process.state == ProcessState.RUNNING:
                            # Update resource usage
                            self._update_process_stats(process)
                            
                            # Check if needs checkpoint
                            if self._needs_checkpoint(process):
                                self._checkpoint_process(process)
                    
                    # Check for failed processes
                    self._check_failed_processes()
                
                time.sleep(1)  # Monitor every second
                
            except Exception as e:
                logger.error(f"Monitor error: {e}")
    
    def _select_node(self, process: DistributedProcess) -> Optional[str]:
        """Select node for process execution"""
        active_nodes = self.cluster.get_active_nodes()
        
        if not active_nodes:
            return None
        
        # Check affinity first
        if process.affinity and process.affinity in active_nodes:
            return process.affinity
        
        # Apply scheduling policy
        if self.policy == SchedulingPolicy.ROUND_ROBIN:
            # Simple round-robin
            return active_nodes[process.pid % len(active_nodes)]
        
        elif self.policy == SchedulingPolicy.LEAST_LOADED:
            # Select least loaded node
            min_load = float('inf')
            selected = None
            
            for node_id in active_nodes:
                load = self.node_loads.get(node_id, 0.0)
                if load < min_load:
                    min_load = load
                    selected = node_id
            
            return selected
        
        elif self.policy == SchedulingPolicy.DATA_LOCALITY:
            # Select node with data (simplified)
            # Would check where process data is located
            return self._find_data_node(process) or active_nodes[0]
        
        elif self.policy == SchedulingPolicy.RANDOM:
            import random
            return random.choice(active_nodes)
        
        else:  # AFFINITY
            return process.affinity or active_nodes[0]
    
    def _schedule_on_node(self, process: DistributedProcess, node_id: str) -> bool:
        """Schedule process on specific node"""
        if node_id == self.cluster.node_id:
            # Execute locally
            return self._execute_local(process)
        else:
            # Execute remotely
            return self._execute_remote(process, node_id)
    
    def _execute_local(self, process: DistributedProcess) -> bool:
        """Execute process locally"""
        try:
            # Create local process
            local_pid = self.executor.execute(
                process.command,
                args=process.args,
                env=process.env,
                background=True
            )
            
            if local_pid:
                process.state = ProcessState.RUNNING
                process.start_time = time.time()
                self.local_processes[process.pid] = process
                
                logger.info(f"Started process {process.pid} locally")
                return True
                
        except Exception as e:
            logger.error(f"Failed to execute process {process.pid}: {e}")
            process.state = ProcessState.FAILED
        
        return False
    
    def _execute_remote(self, process: DistributedProcess, node_id: str) -> bool:
        """Execute process on remote node"""
        from .cluster import MessageType
        
        # Send execution request
        response = self.cluster.send_message(
            node_id,
            MessageType.EXEC,
            {
                'process': process,
                'action': 'execute'
            }
        )
        
        if response and response.get('status') == 'started':
            logger.info(f"Started process {process.pid} on {node_id}")
            return True
        
        return False
    
    def migrate_process(self, pid: int, target_node: str) -> bool:
        """Migrate process to another node"""
        with self.lock:
            if pid not in self.processes:
                return False
            
            process = self.processes[pid]
            
            if process.state != ProcessState.RUNNING:
                return False
            
            if process.node_id == target_node:
                return True  # Already there
            
            # Mark as migrating
            process.state = ProcessState.MIGRATING
            self.migrations_in_progress[pid] = target_node
            
            # Checkpoint process
            checkpoint = self._checkpoint_process(process)
            
            if not checkpoint:
                process.state = ProcessState.RUNNING
                del self.migrations_in_progress[pid]
                return False
            
            # Stop on current node
            if process.node_id == self.cluster.node_id:
                self._stop_local_process(process)
            else:
                self._stop_remote_process(process)
            
            # Start on target node
            process.checkpoint = checkpoint
            
            if self._schedule_on_node(process, target_node):
                process.node_id = target_node
                process.state = ProcessState.RUNNING
                del self.migrations_in_progress[pid]
                
                logger.info(f"Migrated process {pid} to {target_node}")
                return True
            else:
                # Restore on original node
                self._schedule_on_node(process, process.node_id)
                process.state = ProcessState.RUNNING
                del self.migrations_in_progress[pid]
                return False
    
    def _checkpoint_process(self, process: DistributedProcess) -> Optional[bytes]:
        """Create process checkpoint"""
        try:
            checkpoint_data = {
                'pid': process.pid,
                'command': process.command,
                'args': process.args,
                'env': process.env,
                'working_dir': process.working_dir,
                'memory': self._dump_process_memory(process),
                'files': self._dump_open_files(process),
                'signals': self._dump_signal_handlers(process)
            }
            
            checkpoint = pickle.dumps(checkpoint_data)
            process.checkpoint = checkpoint
            self.last_checkpoint[process.pid] = time.time()
            
            return checkpoint
            
        except Exception as e:
            logger.error(f"Failed to checkpoint process {process.pid}: {e}")
            return None
    
    def _restore_from_checkpoint(self, process: DistributedProcess) -> bool:
        """Restore process from checkpoint"""
        if not process.checkpoint:
            return False
        
        try:
            checkpoint_data = pickle.loads(process.checkpoint)
            
            # Restore memory
            self._restore_process_memory(process, checkpoint_data['memory'])
            
            # Restore files
            self._restore_open_files(process, checkpoint_data['files'])
            
            # Restore signal handlers
            self._restore_signal_handlers(process, checkpoint_data['signals'])
            
            # Resume execution
            return self._execute_local(process)
            
        except Exception as e:
            logger.error(f"Failed to restore process {process.pid}: {e}")
            return False
    
    def _dump_process_memory(self, process: DistributedProcess) -> bytes:
        """Dump process memory (simplified)"""
        # Would dump actual memory pages
        return b"memory_dump"
    
    def _restore_process_memory(self, process: DistributedProcess, memory: bytes):
        """Restore process memory"""
        # Would restore memory pages
        pass
    
    def _dump_open_files(self, process: DistributedProcess) -> List[Dict]:
        """Dump open file descriptors"""
        # Would get actual open files
        return []
    
    def _restore_open_files(self, process: DistributedProcess, files: List[Dict]):
        """Restore open files"""
        # Would reopen files
        pass
    
    def _dump_signal_handlers(self, process: DistributedProcess) -> Dict:
        """Dump signal handlers"""
        # Would get signal handlers
        return {}
    
    def _restore_signal_handlers(self, process: DistributedProcess, signals: Dict):
        """Restore signal handlers"""
        # Would restore handlers
        pass
    
    def _stop_local_process(self, process: DistributedProcess):
        """Stop local process"""
        # Would send SIGSTOP or terminate
        if process.pid in self.local_processes:
            del self.local_processes[process.pid]
    
    def _stop_remote_process(self, process: DistributedProcess):
        """Stop remote process"""
        from .cluster import MessageType
        
        self.cluster.send_message(
            process.node_id,
            MessageType.EXEC,
            {
                'process': process,
                'action': 'stop'
            }
        )
    
    def _update_node_loads(self):
        """Update node load information"""
        # Get local load
        local_load = self._get_local_load()
        self.node_loads[self.cluster.node_id] = local_load
        
        # Share with cluster
        from .cluster import MessageType
        
        for node_id in self.cluster.get_active_nodes():
            if node_id != self.cluster.node_id:
                self.cluster.send_message(
                    node_id,
                    MessageType.STATE_UPDATE,
                    {
                        'type': 'load',
                        'load': local_load
                    }
                )
    
    def _get_local_load(self) -> float:
        """Get local system load"""
        # Simplified - would use actual system metrics
        return len(self.local_processes) * 0.1
    
    def _update_process_stats(self, process: DistributedProcess):
        """Update process statistics"""
        # Would get actual CPU and memory usage
        process.cpu_usage = 10.0  # Placeholder
        process.memory_usage = 1024 * 1024  # 1MB placeholder
    
    def _needs_checkpoint(self, process: DistributedProcess) -> bool:
        """Check if process needs checkpoint"""
        last = self.last_checkpoint.get(process.pid, 0)
        return time.time() - last > self.checkpoint_interval
    
    def _check_load_balance(self):
        """Check if load balancing is needed"""
        if len(self.node_loads) < 2:
            return
        
        loads = list(self.node_loads.values())
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)
        min_load = min(loads)
        
        # If imbalance is significant
        if max_load - min_load > avg_load * 0.5:
            # Find overloaded and underloaded nodes
            overloaded = [n for n, l in self.node_loads.items() if l > avg_load * 1.2]
            underloaded = [n for n, l in self.node_loads.items() if l < avg_load * 0.8]
            
            # Migrate processes from overloaded to underloaded
            for source in overloaded:
                for target in underloaded:
                    # Find process to migrate
                    for pid, process in self.processes.items():
                        if process.node_id == source and process.state == ProcessState.RUNNING:
                            if process.affinity != source:  # Don't migrate affinity-bound
                                self.migrate_process(pid, target)
                                break
    
    def _check_failed_processes(self):
        """Check for and restart failed processes"""
        for pid, process in list(self.processes.items()):
            if process.state == ProcessState.FAILED:
                # Try to restart
                if process.checkpoint:
                    # Restore from checkpoint
                    logger.info(f"Restarting failed process {pid} from checkpoint")
                    process.state = ProcessState.PENDING
                    self.process_queue.append(process)
                else:
                    # Restart fresh
                    logger.info(f"Restarting failed process {pid}")
                    process.state = ProcessState.PENDING
                    self.process_queue.append(process)
    
    def _find_data_node(self, process: DistributedProcess) -> Optional[str]:
        """Find node where process data is located"""
        # Simplified - would check actual data location
        return None
    
    def _generate_pid(self) -> int:
        """Generate unique distributed PID"""
        import random
        return random.randint(10000, 99999)
    
    def get_process_info(self, pid: int) -> Optional[Dict]:
        """Get process information"""
        with self.lock:
            if pid in self.processes:
                process = self.processes[pid]
                return {
                    'pid': process.pid,
                    'command': process.command,
                    'state': process.state.value,
                    'node': process.node_id,
                    'cpu_usage': process.cpu_usage,
                    'memory_usage': process.memory_usage,
                    'start_time': process.start_time
                }
        return None
    
    def list_processes(self) -> List[Dict]:
        """List all distributed processes"""
        with self.lock:
            return [self.get_process_info(pid) for pid in self.processes]
    
    def kill_process(self, pid: int) -> bool:
        """Kill distributed process"""
        with self.lock:
            if pid not in self.processes:
                return False
            
            process = self.processes[pid]
            
            if process.node_id == self.cluster.node_id:
                self._stop_local_process(process)
            else:
                self._stop_remote_process(process)
            
            process.state = ProcessState.COMPLETED
            
            # Remove from tracking
            self.processes.pop(pid, None)
            self.local_processes.pop(pid, None)
            
            return True
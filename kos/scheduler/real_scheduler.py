"""
KOS Real Process Scheduler Implementation
CFS (Completely Fair Scheduler) and real-time scheduling
"""

import os
import time
import heapq
import threading
import sched
import signal
import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from collections import defaultdict

logger = logging.getLogger('kos.scheduler.real')


class SchedPolicy(IntEnum):
    """Scheduling policies"""
    SCHED_OTHER = 0    # CFS normal
    SCHED_FIFO = 1     # Real-time FIFO
    SCHED_RR = 2       # Real-time round-robin
    SCHED_BATCH = 3    # Batch processing
    SCHED_IDLE = 5     # Idle priority
    SCHED_DEADLINE = 6 # Deadline scheduling


class ProcessState(Enum):
    """Process states"""
    RUNNABLE = "runnable"
    RUNNING = "running"
    SLEEPING = "sleeping"
    STOPPED = "stopped"
    ZOMBIE = "zombie"


@dataclass
class SchedEntity:
    """Scheduling entity (process or thread)"""
    pid: int
    tgid: int  # Thread group ID
    policy: SchedPolicy = SchedPolicy.SCHED_OTHER
    nice: int = 0
    priority: int = 0  # RT priority (0-99)
    
    # CFS statistics
    vruntime: float = 0.0  # Virtual runtime
    exec_start: float = 0.0
    sum_exec_runtime: float = 0.0
    prev_sum_exec_runtime: float = 0.0
    nr_switches: int = 0
    
    # Load tracking
    load_weight: int = 1024  # Default weight
    inv_weight: float = 1.0 / 1024
    
    # CPU affinity
    cpus_allowed: Set[int] = field(default_factory=lambda: set(range(os.cpu_count() or 1)))
    
    # State
    state: ProcessState = ProcessState.RUNNABLE
    on_rq: bool = False
    
    # Deadline scheduling
    deadline: float = 0.0
    runtime: float = 0.0
    period: float = 0.0
    
    def __lt__(self, other):
        """Compare by vruntime for heap operations"""
        return self.vruntime < other.vruntime


class RunQueue:
    """Per-CPU run queue"""
    
    def __init__(self, cpu: int):
        self.cpu = cpu
        self.nr_running = 0
        self.load_weight = 0
        
        # CFS red-black tree (simulated with heap)
        self.cfs_rq = []  # Min heap by vruntime
        self.entities = {}  # pid -> SchedEntity
        
        # RT queues (priority 0-99)
        self.rt_rq = [[] for _ in range(100)]
        self.rt_nr_running = 0
        
        # Currently running entity
        self.curr = None
        self.idle = None
        
        # Timing
        self.clock = 0.0
        self.min_vruntime = 0.0
        
        # Lock
        self.lock = threading.Lock()
        
    def enqueue_entity(self, entity: SchedEntity):
        """Add entity to run queue"""
        with self.lock:
            if entity.on_rq:
                return
                
            entity.on_rq = True
            self.entities[entity.pid] = entity
            
            if entity.policy in [SchedPolicy.SCHED_FIFO, SchedPolicy.SCHED_RR]:
                # Real-time entity
                self.rt_rq[entity.priority].append(entity)
                self.rt_nr_running += 1
            else:
                # CFS entity
                heapq.heappush(self.cfs_rq, entity)
                self.load_weight += entity.load_weight
                
            self.nr_running += 1
            
    def dequeue_entity(self, entity: SchedEntity):
        """Remove entity from run queue"""
        with self.lock:
            if not entity.on_rq:
                return
                
            entity.on_rq = False
            self.entities.pop(entity.pid, None)
            
            if entity.policy in [SchedPolicy.SCHED_FIFO, SchedPolicy.SCHED_RR]:
                # Real-time entity
                if entity in self.rt_rq[entity.priority]:
                    self.rt_rq[entity.priority].remove(entity)
                    self.rt_nr_running -= 1
            else:
                # CFS entity - rebuild heap without entity
                self.cfs_rq = [e for e in self.cfs_rq if e.pid != entity.pid]
                heapq.heapify(self.cfs_rq)
                self.load_weight -= entity.load_weight
                
            self.nr_running -= 1
            
    def pick_next_entity(self) -> Optional[SchedEntity]:
        """Pick next entity to run"""
        with self.lock:
            # Check RT queues first (highest priority)
            for prio in range(99, -1, -1):
                if self.rt_rq[prio]:
                    return self.rt_rq[prio][0]
                    
            # Check CFS queue
            if self.cfs_rq:
                return self.cfs_rq[0]
                
            # Return idle task
            return self.idle
            
    def update_curr(self, now: float):
        """Update current entity runtime"""
        if not self.curr:
            return
            
        delta = now - self.curr.exec_start
        if delta <= 0:
            return
            
        self.curr.sum_exec_runtime += delta
        
        if self.curr.policy == SchedPolicy.SCHED_OTHER:
            # Update vruntime for CFS
            delta_weighted = delta * self.curr.inv_weight
            self.curr.vruntime += delta_weighted
            
            # Update min_vruntime
            if self.cfs_rq:
                self.min_vruntime = min(self.curr.vruntime, self.cfs_rq[0].vruntime)
            else:
                self.min_vruntime = self.curr.vruntime


class CFSScheduler:
    """Completely Fair Scheduler implementation"""
    
    # Nice to weight mapping
    NICE_TO_WEIGHT = [
        # Nice -20 to 19
        88761, 71755, 56483, 46273, 36291,  # -20 to -16
        29154, 23254, 18705, 14949, 11916,  # -15 to -11
        9548, 7620, 6100, 4904, 3906,       # -10 to -6
        3121, 2501, 1991, 1586, 1277,       # -5 to -1
        1024, 820, 655, 526, 423,           # 0 to 4
        335, 272, 215, 172, 137,            # 5 to 9
        110, 87, 70, 56, 45,                # 10 to 14
        36, 29, 23, 18, 15,                 # 15 to 19
    ]
    
    def __init__(self):
        self.cpu_count = os.cpu_count() or 1
        self.runqueues = [RunQueue(cpu) for cpu in range(self.cpu_count)]
        self.processes = {}  # pid -> SchedEntity
        self.lock = threading.RLock()
        
        # Scheduling parameters
        self.sysctl_sched_latency = 6000000  # 6ms in ns
        self.sysctl_sched_min_granularity = 750000  # 0.75ms in ns
        self.sysctl_sched_wakeup_granularity = 1000000  # 1ms in ns
        
        # Load balancing
        self.balance_interval = 0.1  # 100ms
        self.last_balance = time.time()
        
        # Scheduler thread
        self.running = False
        self.scheduler_thread = None
        
    def start(self):
        """Start scheduler"""
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        logger.info("Started CFS scheduler")
        
    def stop(self):
        """Stop scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()
        logger.info("Stopped CFS scheduler")
        
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            now = time.time()
            
            # Schedule on each CPU
            for cpu in range(self.cpu_count):
                self._schedule_cpu(cpu, now)
                
            # Load balancing
            if now - self.last_balance > self.balance_interval:
                self._load_balance()
                self.last_balance = now
                
            # Sleep briefly
            time.sleep(0.001)  # 1ms
            
    def _schedule_cpu(self, cpu: int, now: float):
        """Schedule on specific CPU"""
        rq = self.runqueues[cpu]
        
        with rq.lock:
            # Update current task
            rq.update_curr(now)
            
            # Check if we need to preempt
            if self._need_resched(rq):
                self._schedule(rq, now)
                
    def _need_resched(self, rq: RunQueue) -> bool:
        """Check if we need to reschedule"""
        if not rq.curr:
            return True
            
        # RT task preempts non-RT
        if rq.rt_nr_running > 0:
            if rq.curr.policy not in [SchedPolicy.SCHED_FIFO, SchedPolicy.SCHED_RR]:
                return True
                
        # Check CFS preemption
        if rq.curr.policy == SchedPolicy.SCHED_OTHER and rq.cfs_rq:
            # Preempt if current has run long enough and there's a task
            # with significantly lower vruntime
            ideal_runtime = self._sched_slice(rq, rq.curr)
            delta = rq.curr.sum_exec_runtime - rq.curr.prev_sum_exec_runtime
            
            if delta > ideal_runtime:
                leftmost = rq.cfs_rq[0]
                if leftmost.vruntime < rq.curr.vruntime - self.sysctl_sched_wakeup_granularity:
                    return True
                    
        return False
        
    def _schedule(self, rq: RunQueue, now: float):
        """Perform scheduling decision"""
        # Put current back on queue
        prev = rq.curr
        if prev and prev.state == ProcessState.RUNNABLE:
            rq.enqueue_entity(prev)
            
        # Pick next task
        next_entity = rq.pick_next_entity()
        
        if next_entity != prev:
            # Context switch
            self._context_switch(rq, prev, next_entity, now)
            
    def _context_switch(self, rq: RunQueue, prev: Optional[SchedEntity], 
                       next: Optional[SchedEntity], now: float):
        """Perform context switch"""
        # Dequeue next from runqueue
        if next and next != rq.idle:
            rq.dequeue_entity(next)
            
        # Update stats
        if prev:
            prev.prev_sum_exec_runtime = prev.sum_exec_runtime
            prev.nr_switches += 1
            
        if next:
            next.exec_start = now
            next.nr_switches += 1
            
        # Set current
        rq.curr = next
        
        logger.debug(f"Context switch on CPU {rq.cpu}: "
                    f"{prev.pid if prev else 'idle'} -> "
                    f"{next.pid if next else 'idle'}")
                    
    def _sched_slice(self, rq: RunQueue, entity: SchedEntity) -> float:
        """Calculate time slice for entity"""
        # Target latency divided by number of tasks
        nr_running = max(1, rq.nr_running)
        slice = self.sysctl_sched_latency / nr_running
        
        # Weight-based adjustment
        if rq.load_weight > 0:
            slice = slice * entity.load_weight / rq.load_weight
            
        # Ensure minimum granularity
        return max(slice, self.sysctl_sched_min_granularity)
        
    def _load_balance(self):
        """Balance load between CPUs"""
        # Find busiest and least busy CPUs
        loads = [(rq.nr_running, i) for i, rq in enumerate(self.runqueues)]
        loads.sort()
        
        min_load, min_cpu = loads[0]
        max_load, max_cpu = loads[-1]
        
        # Balance if significant imbalance
        if max_load > min_load + 1:
            self._migrate_task(max_cpu, min_cpu)
            
    def _migrate_task(self, from_cpu: int, to_cpu: int):
        """Migrate task between CPUs"""
        from_rq = self.runqueues[from_cpu]
        to_rq = self.runqueues[to_cpu]
        
        with from_rq.lock, to_rq.lock:
            # Find a migratable task
            for entity in from_rq.entities.values():
                if to_cpu in entity.cpus_allowed and entity != from_rq.curr:
                    # Migrate
                    from_rq.dequeue_entity(entity)
                    to_rq.enqueue_entity(entity)
                    logger.debug(f"Migrated task {entity.pid} from CPU {from_cpu} to {to_cpu}")
                    break
                    
    def create_process(self, pid: int, tgid: int = None, nice: int = 0,
                      policy: SchedPolicy = SchedPolicy.SCHED_OTHER,
                      priority: int = 0) -> SchedEntity:
        """Create new process/thread"""
        if tgid is None:
            tgid = pid
            
        # Calculate weight from nice
        weight_idx = nice + 20
        weight = self.NICE_TO_WEIGHT[weight_idx] if 0 <= weight_idx < 40 else 1024
        
        entity = SchedEntity(
            pid=pid,
            tgid=tgid,
            policy=policy,
            nice=nice,
            priority=priority,
            load_weight=weight,
            inv_weight=1.0 / weight
        )
        
        with self.lock:
            self.processes[pid] = entity
            
            # Add to least loaded CPU
            min_rq = min(self.runqueues, key=lambda rq: rq.nr_running)
            min_rq.enqueue_entity(entity)
            
        return entity
        
    def set_affinity(self, pid: int, cpus: Set[int]):
        """Set CPU affinity for process"""
        with self.lock:
            if pid in self.processes:
                entity = self.processes[pid]
                entity.cpus_allowed = cpus
                
                # Check if we need to migrate
                for rq in self.runqueues:
                    if entity in rq.entities.values() and rq.cpu not in cpus:
                        # Need to migrate
                        rq.dequeue_entity(entity)
                        
                        # Find suitable CPU
                        for cpu in cpus:
                            if cpu < self.cpu_count:
                                self.runqueues[cpu].enqueue_entity(entity)
                                break
                                
    def set_nice(self, pid: int, nice: int):
        """Set process nice value"""
        with self.lock:
            if pid in self.processes:
                entity = self.processes[pid]
                
                # Update weight
                weight_idx = nice + 20
                if 0 <= weight_idx < 40:
                    entity.nice = nice
                    entity.load_weight = self.NICE_TO_WEIGHT[weight_idx]
                    entity.inv_weight = 1.0 / entity.load_weight
                    
    def yield_cpu(self, pid: int):
        """Yield CPU for process"""
        with self.lock:
            if pid in self.processes:
                entity = self.processes[pid]
                
                # Find which CPU it's on
                for rq in self.runqueues:
                    if entity == rq.curr:
                        # Force reschedule
                        self._schedule(rq, time.time())
                        break
                        
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        stats = {
            'cpus': self.cpu_count,
            'total_processes': len(self.processes),
            'runqueues': []
        }
        
        for cpu, rq in enumerate(self.runqueues):
            rq_stats = {
                'cpu': cpu,
                'nr_running': rq.nr_running,
                'rt_nr_running': rq.rt_nr_running,
                'load_weight': rq.load_weight,
                'min_vruntime': rq.min_vruntime,
                'current': rq.curr.pid if rq.curr else None
            }
            stats['runqueues'].append(rq_stats)
            
        return stats


# Global scheduler instance
_scheduler = None

def get_scheduler() -> CFSScheduler:
    """Get global scheduler instance"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CFSScheduler()
        _scheduler.start()
    return _scheduler
"""
KOS CFS Scheduler - Completely Fair Scheduler implementation
"""

import heapq
import threading
import time
import math
from typing import List, Dict, Optional, Tuple, Any
from collections import defaultdict

from ..process.process import KOSProcess, ProcessState

class SchedulingEntity:
    """
    Scheduling entity for CFS
    Represents a schedulable task
    """
    
    def __init__(self, process: KOSProcess):
        self.process = process
        self.vruntime = 0  # Virtual runtime
        self.load_weight = self._calculate_load_weight()
        self.time_slice = 0
        self.last_run_time = 0
        self.total_runtime = 0
        
    def _calculate_load_weight(self) -> int:
        """Calculate load weight based on nice value"""
        # Linux nice to weight table (simplified)
        nice_to_weight = {
            -20: 88761, -19: 71755, -18: 56483, -17: 46273, -16: 36291,
            -15: 29154, -14: 23254, -13: 18705, -12: 14949, -11: 11916,
            -10: 9548, -9: 7620, -8: 6100, -7: 4904, -6: 3906,
            -5: 3121, -4: 2501, -3: 1991, -2: 1586, -1: 1277,
            0: 1024, 1: 820, 2: 655, 3: 526, 4: 423,
            5: 335, 6: 272, 7: 215, 8: 172, 9: 137,
            10: 110, 11: 87, 12: 70, 13: 56, 14: 45,
            15: 36, 16: 29, 17: 23, 18: 18, 19: 15
        }
        
        nice = self.process.priority - 20  # Convert to nice value
        nice = max(-20, min(19, nice))  # Clamp to valid range
        return nice_to_weight.get(nice, 1024)
        
    def update_vruntime(self, delta_time: float):
        """Update virtual runtime"""
        # Virtual runtime increases slower for higher priority processes
        weighted_time = delta_time * (1024.0 / self.load_weight)
        self.vruntime += weighted_time
        self.total_runtime += delta_time
        
    def __lt__(self, other):
        """For heap operations - lower vruntime has higher priority"""
        return self.vruntime < other.vruntime

class RunQueue:
    """
    Per-CPU run queue for CFS
    """
    
    def __init__(self, cpu_id: int):
        self.cpu_id = cpu_id
        self.entities = []  # Min-heap of scheduling entities
        self.min_vruntime = 0  # Minimum vruntime in this runqueue
        self.nr_running = 0
        self.load_weight = 0
        self.lock = threading.Lock()
        
        # Load tracking
        self.load_avg_1 = 0.0
        self.load_avg_5 = 0.0
        self.load_avg_15 = 0.0
        self.last_load_update = time.time()
        
    def enqueue(self, entity: SchedulingEntity):
        """Add entity to runqueue"""
        with self.lock:
            # Normalize vruntime to min_vruntime for fairness
            if entity.vruntime < self.min_vruntime:
                entity.vruntime = self.min_vruntime
                
            heapq.heappush(self.entities, entity)
            self.nr_running += 1
            self.load_weight += entity.load_weight
            
    def dequeue(self) -> Optional[SchedulingEntity]:
        """Remove and return entity with lowest vruntime"""
        with self.lock:
            if self.entities:
                entity = heapq.heappop(self.entities)
                self.nr_running -= 1
                self.load_weight -= entity.load_weight
                return entity
        return None
        
    def peek(self) -> Optional[SchedulingEntity]:
        """Look at next entity without removing it"""
        with self.lock:
            if self.entities:
                return self.entities[0]
        return None
        
    def remove_entity(self, entity: SchedulingEntity) -> bool:
        """Remove specific entity from runqueue"""
        with self.lock:
            if entity in self.entities:
                self.entities.remove(entity)
                heapq.heapify(self.entities)  # Re-heapify after removal
                self.nr_running -= 1
                self.load_weight -= entity.load_weight
                return True
        return False
        
    def update_min_vruntime(self):
        """Update minimum vruntime"""
        with self.lock:
            if self.entities:
                # Min vruntime is the vruntime of leftmost (minimum) entity
                leftmost_vruntime = self.entities[0].vruntime
                self.min_vruntime = max(self.min_vruntime, leftmost_vruntime)
            # If no entities, min_vruntime stays the same
            
    def update_load_average(self):
        """Update load averages"""
        current_time = time.time()
        time_delta = current_time - self.last_load_update
        
        if time_delta > 0:
            # Exponential decay for load averages
            exp_1 = math.exp(-time_delta / 60.0)    # 1 minute
            exp_5 = math.exp(-time_delta / 300.0)   # 5 minutes  
            exp_15 = math.exp(-time_delta / 900.0)  # 15 minutes
            
            current_load = float(self.nr_running)
            
            self.load_avg_1 = exp_1 * self.load_avg_1 + (1 - exp_1) * current_load
            self.load_avg_5 = exp_5 * self.load_avg_5 + (1 - exp_5) * current_load
            self.load_avg_15 = exp_15 * self.load_avg_15 + (1 - exp_15) * current_load
            
            self.last_load_update = current_time
            
    def get_stats(self) -> Dict[str, Any]:
        """Get runqueue statistics"""
        with self.lock:
            return {
                'cpu_id': self.cpu_id,
                'nr_running': self.nr_running,
                'load_weight': self.load_weight,
                'min_vruntime': self.min_vruntime,
                'load_avg_1': self.load_avg_1,
                'load_avg_5': self.load_avg_5,
                'load_avg_15': self.load_avg_15
            }

class CFSScheduler:
    """
    Completely Fair Scheduler (CFS) implementation
    """
    
    def __init__(self, num_cpus: int = 4):
        self.num_cpus = num_cpus
        self.runqueues = [RunQueue(i) for i in range(num_cpus)]
        self.current_tasks = [None] * num_cpus  # Currently running task per CPU
        
        # Scheduling entities
        self.entities: Dict[int, SchedulingEntity] = {}  # pid -> entity
        
        # Timing
        self.sched_latency = 0.006  # 6ms - target latency
        self.min_granularity = 0.0015  # 1.5ms - minimum time slice
        
        # Statistics
        self.total_context_switches = 0
        self.last_balance_time = time.time()
        self.balance_interval = 0.1  # 100ms
        
        # Load balancing
        self.balancing_enabled = True
        
        self.lock = threading.RLock()
        
    def add_task(self, process: KOSProcess, cpu: Optional[int] = None) -> bool:
        """Add task to scheduler"""
        with self.lock:
            if process.pid in self.entities:
                return False  # Already scheduled
                
            entity = SchedulingEntity(process)
            self.entities[process.pid] = entity
            
            # Choose CPU
            if cpu is None:
                cpu = self._select_cpu(process)
                
            # Set initial vruntime to runqueue's min_vruntime
            # This prevents new tasks from starving existing ones
            rq = self.runqueues[cpu]
            entity.vruntime = rq.min_vruntime
            
            rq.enqueue(entity)
            process.cpu_current = cpu
            
            return True
            
    def remove_task(self, process: KOSProcess) -> bool:
        """Remove task from scheduler"""
        with self.lock:
            if process.pid not in self.entities:
                return False
                
            entity = self.entities[process.pid]
            cpu = process.cpu_current
            
            # Remove from runqueue
            rq = self.runqueues[cpu]
            rq.remove_entity(entity)
            
            # Remove from current if it's running
            if self.current_tasks[cpu] == entity:
                self.current_tasks[cpu] = None
                
            del self.entities[process.pid]
            return True
            
    def schedule_cpu(self, cpu: int) -> Optional[KOSProcess]:
        """Schedule next task on specific CPU"""
        with self.lock:
            rq = self.runqueues[cpu]
            current = self.current_tasks[cpu]
            
            # Update current task's vruntime if running
            if current and current.process.state == ProcessState.RUNNING:
                current_time = time.time()
                if current.last_run_time > 0:
                    runtime = current_time - current.last_run_time
                    current.update_vruntime(runtime)
                    
                # Check if current task should be preempted
                if self._should_preempt(current, rq):
                    # Put current task back in runqueue
                    rq.enqueue(current)
                    self.current_tasks[cpu] = None
                    current = None
                    
            # Pick next task if no current task
            if not current:
                entity = rq.dequeue()
                if entity:
                    self.current_tasks[cpu] = entity
                    entity.last_run_time = time.time()
                    entity.time_slice = self._calculate_time_slice(rq)
                    self.total_context_switches += 1
                    
                    # Update runqueue min_vruntime
                    rq.update_min_vruntime()
                    
                    return entity.process
                    
            elif current.process.state == ProcessState.RUNNING:
                # Continue current task
                return current.process
                
        return None
        
    def _should_preempt(self, current: SchedulingEntity, rq: RunQueue) -> bool:
        """Check if current task should be preempted"""
        # Preempt if time slice expired
        current_time = time.time()
        if current.last_run_time > 0:
            runtime = current_time - current.last_run_time
            if runtime >= current.time_slice:
                return True
                
        # Preempt if there's a task with much lower vruntime
        leftmost = rq.peek()
        if leftmost:
            vruntime_diff = current.vruntime - leftmost.vruntime
            if vruntime_diff > self.sched_latency:
                return True
                
        return False
        
    def _calculate_time_slice(self, rq: RunQueue) -> float:
        """Calculate time slice for task"""
        if rq.nr_running == 0:
            return self.sched_latency
            
        # Divide target latency by number of running tasks
        time_slice = self.sched_latency / rq.nr_running
        
        # Ensure minimum granularity
        return max(time_slice, self.min_granularity)
        
    def _select_cpu(self, process: KOSProcess) -> int:
        """Select CPU for new task"""
        # Simple load balancing - choose least loaded CPU
        min_load = float('inf')
        best_cpu = 0
        
        for cpu in range(self.num_cpus):
            if cpu in process.cpu_allowed:
                load = self.runqueues[cpu].nr_running
                if load < min_load:
                    min_load = load
                    best_cpu = cpu
                    
        return best_cpu
        
    def balance_load(self):
        """Perform load balancing between CPUs"""
        if not self.balancing_enabled:
            return
            
        current_time = time.time()
        if current_time - self.last_balance_time < self.balance_interval:
            return
            
        with self.lock:
            # Calculate average load
            total_load = sum(rq.nr_running for rq in self.runqueues)
            avg_load = total_load / self.num_cpus
            
            # Find overloaded and underloaded CPUs
            overloaded = []
            underloaded = []
            
            for i, rq in enumerate(self.runqueues):
                if rq.nr_running > avg_load + 1:
                    overloaded.append(i)
                elif rq.nr_running < avg_load - 1:
                    underloaded.append(i)
                    
            # Migrate tasks from overloaded to underloaded CPUs
            for over_cpu in overloaded:
                if not underloaded:
                    break
                    
                under_cpu = underloaded[0]
                
                # Try to migrate one task
                over_rq = self.runqueues[over_cpu]
                under_rq = self.runqueues[under_cpu]
                
                if over_rq.entities:
                    # Find a suitable task to migrate
                    # For simplicity, take the last task (highest vruntime)
                    entity = over_rq.entities[-1]
                    
                    if over_rq.remove_entity(entity):
                        entity.process.cpu_current = under_cpu
                        under_rq.enqueue(entity)
                        
                        # Update underloaded list
                        if under_rq.nr_running >= avg_load:
                            underloaded.remove(under_cpu)
                            
        self.last_balance_time = current_time
        
    def update_load_averages(self):
        """Update load averages for all runqueues"""
        for rq in self.runqueues:
            rq.update_load_average()
            
    def get_load_average(self) -> Tuple[float, float, float]:
        """Get system-wide load average"""
        total_1 = sum(rq.load_avg_1 for rq in self.runqueues)
        total_5 = sum(rq.load_avg_5 for rq in self.runqueues)
        total_15 = sum(rq.load_avg_15 for rq in self.runqueues)
        
        return (total_1, total_5, total_15)
        
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        with self.lock:
            stats = {
                'num_cpus': self.num_cpus,
                'total_tasks': len(self.entities),
                'context_switches': self.total_context_switches,
                'load_average': self.get_load_average(),
                'runqueues': []
            }
            
            for rq in self.runqueues:
                stats['runqueues'].append(rq.get_stats())
                
            return stats

class KOSScheduler:
    """
    Main scheduler for KOS
    Wraps CFS scheduler and provides high-level interface
    """
    
    def __init__(self, kernel: 'KOSKernel'):
        self.kernel = kernel
        self.cfs = CFSScheduler()
        self.running = False
        self.scheduler_thread = None
        
        # Scheduling statistics
        self.schedule_count = 0
        self.last_schedule_time = time.time()
        
    def start(self):
        """Start the scheduler"""
        if not self.running:
            self.running = True
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_loop,
                name="kos-scheduler",
                daemon=True
            )
            self.scheduler_thread.start()
            
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1.0)
            
    def add_process(self, process: KOSProcess) -> bool:
        """Add process to scheduler"""
        return self.cfs.add_task(process)
        
    def remove_process(self, process: KOSProcess) -> bool:
        """Remove process from scheduler"""
        return self.cfs.remove_task(process)
        
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Schedule each CPU
                for cpu in range(self.cfs.num_cpus):
                    self.cfs.schedule_cpu(cpu)
                    
                # Periodic maintenance
                self.cfs.balance_load()
                self.cfs.update_load_averages()
                
                self.schedule_count += 1
                
                # Sleep for a short time (simulate timer interrupt)
                time.sleep(0.001)  # 1ms
                
            except Exception as e:
                if self.kernel:
                    self.kernel._printk(f"Scheduler error: {e}")
                    
    def get_load_average(self) -> Tuple[float, float, float]:
        """Get system load average"""
        return self.cfs.get_load_average()
        
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        stats = self.cfs.get_stats()
        stats['schedule_count'] = self.schedule_count
        stats['running'] = self.running
        return stats
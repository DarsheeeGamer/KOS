# Process Scheduler API

Comprehensive API documentation for KOS process scheduling subsystem.

## Overview

The KOS scheduler provides sophisticated task scheduling capabilities including the Completely Fair Scheduler (CFS), real-time scheduling, and load balancing across multiple CPUs.

## Core Classes

### KOSScheduler

Main scheduler interface providing unified access to all scheduling policies.

```python
from kos.scheduler.real_scheduler import KOSScheduler, SchedulingPolicy, TaskState

class KOSScheduler:
    """
    Main KOS scheduler implementing multiple scheduling policies.
    
    Supports CFS (Completely Fair Scheduler), real-time scheduling,
    and various other scheduling policies with load balancing.
    """
    
    def __init__(self, num_cpus: int = None):
        """
        Initialize scheduler.
        
        Args:
            num_cpus: Number of CPUs (auto-detect if None)
        """
        
    def initialize(self) -> bool:
        """
        Initialize scheduler subsystem.
        
        Returns:
            bool: True if initialization successful
            
        Raises:
            SchedulerError: If initialization fails
        """
        
    def add_process(self, process: 'KOSProcess') -> bool:
        """
        Add process to scheduler.
        
        Args:
            process: Process to add
            
        Returns:
            bool: True if process added successfully
            
        Example:
            >>> scheduler = KOSScheduler()
            >>> process = KOSProcess('my_app', None, ['/bin/my_app'])
            >>> scheduler.add_process(process)
            True
        """
        
    def remove_process(self, pid: int) -> bool:
        """
        Remove process from scheduler.
        
        Args:
            pid: Process ID to remove
            
        Returns:
            bool: True if process removed successfully
        """
        
    def schedule(self) -> 'KOSProcess':
        """
        Select next process to run.
        
        Returns:
            KOSProcess: Next process to execute (None if no runnable processes)
            
        Note:
            This is the main scheduling decision function called by the kernel.
        """
        
    def yield_current(self) -> None:
        """
        Yield current process voluntarily.
        
        Moves the current process to the end of its scheduling queue
        and triggers rescheduling.
        """
        
    def set_priority(self, pid: int, priority: int) -> bool:
        """
        Set process priority.
        
        Args:
            pid: Process ID
            priority: Priority value (higher = more important)
                     Range: -20 to 19 for normal processes
                     Range: 1 to 99 for real-time processes
                     
        Returns:
            bool: True if priority set successfully
        """
        
    def set_policy(self, pid: int, policy: SchedulingPolicy) -> bool:
        """
        Set scheduling policy for process.
        
        Args:
            pid: Process ID
            policy: Scheduling policy to use
            
        Returns:
            bool: True if policy set successfully
        """
        
    def set_cpu_affinity(self, pid: int, cpu_mask: List[int]) -> bool:
        """
        Set CPU affinity for process.
        
        Args:
            pid: Process ID
            cpu_mask: List of allowed CPU IDs
            
        Returns:
            bool: True if affinity set successfully
            
        Example:
            >>> # Restrict process to CPUs 0 and 2
            >>> scheduler.set_cpu_affinity(pid, [0, 2])
        """
        
    def get_cpu_loads(self) -> Dict[int, float]:
        """
        Get current CPU load percentages.
        
        Returns:
            Dict[int, float]: CPU ID -> load percentage (0.0-100.0)
        """
        
    def context_switch(self, from_process: 'KOSProcess', 
                      to_process: 'KOSProcess') -> bool:
        """
        Perform context switch between processes.
        
        Args:
            from_process: Process being switched out
            to_process: Process being switched in
            
        Returns:
            bool: True if context switch successful
        """
        
    def get_statistics(self) -> dict:
        """
        Get scheduler statistics.
        
        Returns:
            dict: Comprehensive scheduler statistics
            {
                'total_switches': int,
                'total_processes': int,
                'cpu_usage': Dict[int, float],
                'policy_distribution': Dict[str, int],
                'average_latency': float,
                'load_balance_count': int
            }
        """
```

### CFSScheduler

Completely Fair Scheduler implementation.

```python
from kos.scheduler.cfs import CFSScheduler

class CFSScheduler:
    """
    Completely Fair Scheduler (CFS) implementation.
    
    Provides fair CPU time distribution among processes using
    virtual runtime tracking and red-black tree scheduling.
    """
    
    def __init__(self):
        """Initialize CFS scheduler."""
        
    def add_process(self, process: 'KOSProcess') -> None:
        """
        Add process to CFS runqueue.
        
        Args:
            process: Process to add
        """
        
    def remove_process(self, pid: int) -> None:
        """
        Remove process from CFS runqueue.
        
        Args:
            pid: Process ID to remove
        """
        
    def pick_next_task(self) -> 'KOSProcess':
        """
        Select next task to run using CFS algorithm.
        
        Returns:
            KOSProcess: Process with lowest virtual runtime
        """
        
    def update_current(self, process: 'KOSProcess', delta_exec: int) -> None:
        """
        Update current running process statistics.
        
        Args:
            process: Currently running process
            delta_exec: Execution time since last update (nanoseconds)
        """
        
    def calculate_vruntime(self, process: 'KOSProcess', exec_time: int) -> int:
        """
        Calculate virtual runtime for process.
        
        Args:
            process: Process to calculate for
            exec_time: Actual execution time
            
        Returns:
            int: Virtual runtime value
            
        Note:
            Virtual runtime accounts for process priority and nice values.
            Lower priority processes accumulate vruntime faster.
        """
        
    def calculate_time_slice(self, process: 'KOSProcess', nr_running: int) -> int:
        """
        Calculate time slice for process.
        
        Args:
            process: Process to calculate for
            nr_running: Number of running processes
            
        Returns:
            int: Time slice in nanoseconds
        """
        
    def yield_task(self, process: 'KOSProcess') -> None:
        """
        Handle voluntary yield from process.
        
        Args:
            process: Process that is yielding
        """
        
    def place_entity(self, process: 'KOSProcess', initial: bool = False) -> None:
        """
        Place process in runqueue with appropriate vruntime.
        
        Args:
            process: Process to place
            initial: True if this is initial placement
        """
        
    def check_preempt(self, current: 'KOSProcess', candidate: 'KOSProcess') -> bool:
        """
        Check if candidate should preempt current process.
        
        Args:
            current: Currently running process
            candidate: Process that might preempt
            
        Returns:
            bool: True if preemption should occur
        """
```

## Scheduling Policies

### SchedulingPolicy Enumeration

```python
from enum import Enum

class SchedulingPolicy(Enum):
    """
    Available scheduling policies.
    """
    CFS = 'cfs'           # Completely Fair Scheduler
    RT = 'rt'             # Real-time FIFO
    RR = 'rr'             # Real-time Round Robin
    IDLE = 'idle'         # Idle priority
    BATCH = 'batch'       # Batch processing
    DEADLINE = 'deadline' # Deadline scheduling
```

### Task States

```python
class TaskState(Enum):
    """
    Process/task states in the scheduler.
    """
    RUNNABLE = 'runnable'     # Ready to run
    RUNNING = 'running'       # Currently executing
    SLEEPING = 'sleeping'     # Waiting for event
    STOPPED = 'stopped'       # Stopped by signal
    ZOMBIE = 'zombie'         # Terminated but not reaped
    DEAD = 'dead'            # Completely terminated
```

## Kernel Scheduling Interface

### Low-Level Scheduler Functions

```python
from kos.kernel.sched.sched_wrapper import (
    sched_init, sched_schedule, sched_yield, sched_wakeup,
    set_task_priority, get_task_priority
)

def sched_init() -> int:
    """
    Initialize kernel scheduler.
    
    Returns:
        int: 0 on success, negative error code on failure
    """

def sched_schedule() -> int:
    """
    Trigger scheduling decision in kernel.
    
    Returns:
        int: PID of selected process (0 if idle)
    """

def sched_yield() -> int:
    """
    Yield current process voluntarily.
    
    Returns:
        int: 0 on success, negative on error
    """

def sched_wakeup(pid: int) -> int:
    """
    Wake up sleeping process.
    
    Args:
        pid: Process ID to wake up
        
    Returns:
        int: 0 on success, negative on error
    """

def set_task_priority(pid: int, priority: int) -> int:
    """
    Set task priority in kernel.
    
    Args:
        pid: Process ID
        priority: Priority value
        
    Returns:
        int: 0 on success, negative on error
    """

def get_task_priority(pid: int) -> int:
    """
    Get task priority from kernel.
    
    Args:
        pid: Process ID
        
    Returns:
        int: Priority value (negative on error)
    """
```

### CFS Kernel Interface

```python
from kos.kernel.sched.fair import (
    wake_up_new_task_fair, yield_task_fair, 
    update_curr_fair, check_preempt_fair
)

def wake_up_new_task_fair(task_struct: int) -> None:
    """
    Wake up newly created task in CFS.
    
    Args:
        task_struct: Kernel task structure pointer
    """

def yield_task_fair(runqueue: int) -> None:
    """
    Handle task yield in CFS.
    
    Args:
        runqueue: Kernel runqueue pointer
    """

def update_curr_fair(cfs_rq: int, se: int) -> None:
    """
    Update current task runtime in CFS.
    
    Args:
        cfs_rq: CFS runqueue pointer
        se: Scheduling entity pointer
    """

def check_preempt_fair(rq: int, p: int, flags: int) -> None:
    """
    Check for preemption in CFS.
    
    Args:
        rq: Runqueue pointer
        p: Task pointer
        flags: Wakeup flags
    """
```

## Priority and Nice Values

### Priority Ranges

```python
# Priority ranges for different scheduling classes
NORMAL_PRIO_MIN = -20    # Highest normal priority (nice -20)
NORMAL_PRIO_MAX = 19     # Lowest normal priority (nice +19)
RT_PRIO_MIN = 1          # Lowest real-time priority
RT_PRIO_MAX = 99         # Highest real-time priority

# Default values
DEFAULT_PRIO = 0         # Default nice value
DEFAULT_RT_PRIO = 50     # Default RT priority
```

### Nice Value Conversion

```python
def nice_to_weight(nice: int) -> int:
    """
    Convert nice value to scheduler weight.
    
    Args:
        nice: Nice value (-20 to +19)
        
    Returns:
        int: Scheduler weight
    """
    
def weight_to_nice(weight: int) -> int:
    """
    Convert scheduler weight to nice value.
    
    Args:
        weight: Scheduler weight
        
    Returns:
        int: Nice value
    """

def prio_to_nice(prio: int) -> int:
    """
    Convert priority to nice value.
    
    Args:
        prio: Priority value
        
    Returns:
        int: Nice value
    """
```

## Load Balancing

### Load Balancer Interface

```python
class LoadBalancer:
    """
    CPU load balancing functionality.
    
    Automatically migrates processes between CPUs to maintain
    balanced system load.
    """
    
    def __init__(self, scheduler: KOSScheduler):
        """
        Initialize load balancer.
        
        Args:
            scheduler: Main scheduler instance
        """
        
    def trigger_balance(self) -> None:
        """
        Trigger load balancing across all CPUs.
        
        This method is typically called periodically by the kernel
        or when load imbalance is detected.
        """
        
    def balance_cpu(self, cpu_id: int) -> int:
        """
        Balance load for specific CPU.
        
        Args:
            cpu_id: CPU to balance
            
        Returns:
            int: Number of processes migrated
        """
        
    def find_busiest_cpu(self, exclude_cpu: int = None) -> int:
        """
        Find the most heavily loaded CPU.
        
        Args:
            exclude_cpu: CPU to exclude from search
            
        Returns:
            int: CPU ID of busiest CPU (-1 if none found)
        """
        
    def can_migrate(self, process: 'KOSProcess', target_cpu: int) -> bool:
        """
        Check if process can be migrated to target CPU.
        
        Args:
            process: Process to check
            target_cpu: Target CPU ID
            
        Returns:
            bool: True if migration is allowed
        """
        
    def migrate_process(self, process: 'KOSProcess', target_cpu: int) -> bool:
        """
        Migrate process to target CPU.
        
        Args:
            process: Process to migrate
            target_cpu: Target CPU ID
            
        Returns:
            bool: True if migration successful
        """
```

## Real-Time Scheduling

### Real-Time Policies

```python
class RTScheduler:
    """
    Real-time scheduler for time-critical processes.
    
    Provides FIFO and Round-Robin real-time scheduling with
    strict priority enforcement.
    """
    
    def __init__(self):
        """Initialize real-time scheduler."""
        
    def add_rt_process(self, process: 'KOSProcess', priority: int) -> bool:
        """
        Add process to real-time scheduling.
        
        Args:
            process: Process to add
            priority: RT priority (1-99, higher = more important)
            
        Returns:
            bool: True if process added successfully
        """
        
    def pick_next_rt_task(self) -> 'KOSProcess':
        """
        Select next real-time task.
        
        Returns:
            KOSProcess: Highest priority RT task
        """
        
    def yield_rt_task(self, process: 'KOSProcess') -> None:
        """
        Handle RT task yield.
        
        Args:
            process: RT process that is yielding
        """
        
    def set_rt_priority(self, pid: int, priority: int) -> bool:
        """
        Set real-time priority.
        
        Args:
            pid: Process ID
            priority: RT priority (1-99)
            
        Returns:
            bool: True if priority set successfully
        """
```

## Scheduling Parameters

### Tunable Parameters

```python
from kos.kernel.sysctl_wrapper import sysctl_get, sysctl_set

# CFS tunable parameters
def get_sched_latency() -> int:
    """Get target scheduling latency (nanoseconds)."""
    return sysctl_get("kernel.sched_latency_ns")

def set_sched_latency(latency_ns: int) -> bool:
    """Set target scheduling latency."""
    return sysctl_set("kernel.sched_latency_ns", latency_ns)

def get_sched_min_granularity() -> int:
    """Get minimum scheduling granularity (nanoseconds)."""
    return sysctl_get("kernel.sched_min_granularity_ns")

def set_sched_min_granularity(granularity_ns: int) -> bool:
    """Set minimum scheduling granularity."""
    return sysctl_set("kernel.sched_min_granularity_ns", granularity_ns)

def get_sched_wakeup_granularity() -> int:
    """Get wakeup preemption granularity (nanoseconds)."""
    return sysctl_get("kernel.sched_wakeup_granularity_ns")

def set_sched_wakeup_granularity(granularity_ns: int) -> bool:
    """Set wakeup preemption granularity."""
    return sysctl_set("kernel.sched_wakeup_granularity_ns", granularity_ns)
```

### Default Values

```python
# Default CFS parameters
DEFAULT_SCHED_LATENCY = 6000000      # 6ms target latency
DEFAULT_MIN_GRANULARITY = 750000     # 0.75ms minimum granularity  
DEFAULT_WAKEUP_GRANULARITY = 1000000 # 1ms wakeup granularity

# Load balancing parameters
DEFAULT_BALANCE_INTERVAL = 1000      # 1ms balance interval
DEFAULT_MIGRATION_COST = 500000      # 0.5ms migration cost
```

## Error Handling

### Exception Types

```python
from kos.exceptions import SchedulerError

class SchedulerError(KOSError):
    """Base scheduler error."""
    pass

class InvalidPriorityError(SchedulerError):
    """Invalid priority value."""
    pass

class ProcessNotFoundError(SchedulerError):
    """Process not found in scheduler."""
    pass

class PolicyError(SchedulerError):
    """Scheduling policy error."""
    pass

class AffinityError(SchedulerError):
    """CPU affinity error."""
    pass
```

## Usage Examples

### Basic Scheduler Setup

```python
from kos.scheduler.real_scheduler import KOSScheduler, SchedulingPolicy
from kos.process.process import KOSProcess

# Initialize scheduler
scheduler = KOSScheduler(num_cpus=4)
scheduler.initialize()

# Create processes
process1 = KOSProcess('high_prio', None, ['/bin/important_app'])
process2 = KOSProcess('normal', None, ['/bin/regular_app'])

# Add to scheduler
scheduler.add_process(process1)
scheduler.add_process(process2)

# Set different priorities
scheduler.set_priority(process1.pid, -10)  # Higher priority
scheduler.set_priority(process2.pid, 5)    # Lower priority

# Set scheduling policies
scheduler.set_policy(process1.pid, SchedulingPolicy.RT)
scheduler.set_policy(process2.pid, SchedulingPolicy.CFS)
```

### CFS Scheduling

```python
from kos.scheduler.cfs import CFSScheduler

# Initialize CFS scheduler
cfs = CFSScheduler()

# Add processes
for i in range(5):
    process = KOSProcess(f'task_{i}', None, [f'/bin/task_{i}'])
    process.nice = i - 2  # Nice values from -2 to +2
    cfs.add_process(process)

# Scheduling loop (simplified)
while True:
    current_task = cfs.pick_next_task()
    if current_task:
        # Run task for its time slice
        time_slice = cfs.calculate_time_slice(current_task, cfs.nr_running)
        
        # Simulate execution
        exec_time = min(time_slice, 1000000)  # 1ms max
        cfs.update_current(current_task, exec_time)
        
        # Check for preemption
        next_task = cfs.pick_next_task()
        if next_task != current_task:
            # Context switch needed
            scheduler.context_switch(current_task, next_task)
    else:
        # No runnable tasks, idle
        break
```

### Real-Time Scheduling

```python
from kos.scheduler.real_scheduler import RTScheduler

rt_sched = RTScheduler()

# Create real-time processes
rt_process1 = KOSProcess('rt_high', None, ['/bin/rt_app1'])
rt_process2 = KOSProcess('rt_low', None, ['/bin/rt_app2'])

# Add with different RT priorities
rt_sched.add_rt_process(rt_process1, 90)  # High RT priority
rt_sched.add_rt_process(rt_process2, 50)  # Lower RT priority

# RT processes will always preempt normal processes
next_rt_task = rt_sched.pick_next_rt_task()
print(f"Next RT task: {next_rt_task.name}")
```

### CPU Affinity Management

```python
# Restrict process to specific CPUs
process = KOSProcess('cpu_bound', None, ['/bin/cpu_intensive'])
scheduler.add_process(process)

# Pin to CPUs 0 and 1 only
scheduler.set_cpu_affinity(process.pid, [0, 1])

# Check current CPU loads
cpu_loads = scheduler.get_cpu_loads()
for cpu_id, load in cpu_loads.items():
    print(f"CPU {cpu_id}: {load:.1f}% load")

# Manual load balancing trigger
scheduler.trigger_load_balance()
```

### Scheduler Statistics and Monitoring

```python
# Get comprehensive scheduler statistics
stats = scheduler.get_statistics()

print(f"Total context switches: {stats['total_switches']}")
print(f"Total processes managed: {stats['total_processes']}")
print(f"Average scheduling latency: {stats['average_latency']:.2f}ms")

# CPU usage breakdown
for cpu_id, usage in stats['cpu_usage'].items():
    print(f"CPU {cpu_id} usage: {usage:.1f}%")

# Policy distribution
for policy, count in stats['policy_distribution'].items():
    print(f"{policy} processes: {count}")
```

## Performance Optimization

### Scheduler Tuning

```python
# Tune for low latency (interactive workloads)
set_sched_latency(3000000)         # 3ms target latency
set_sched_min_granularity(375000)  # 0.375ms min granularity

# Tune for throughput (batch workloads)  
set_sched_latency(12000000)        # 12ms target latency
set_sched_min_granularity(1500000) # 1.5ms min granularity
```

### Process Optimization

```python
# Optimize process for scheduling
process = KOSProcess('optimized', None, ['/bin/app'])

# Set appropriate nice value
process.nice = -5  # Slightly higher priority

# Set CPU affinity for NUMA awareness
process.cpu_affinity = [0, 1, 2, 3]  # Bind to first NUMA node

# Use appropriate scheduling policy
scheduler.set_policy(process.pid, SchedulingPolicy.CFS)
```

## Integration with Other Subsystems

### Process Manager Integration

```python
# Scheduler automatically integrates with process manager
from kos.process.manager import ProcessManager

proc_mgr = ProcessManager()
scheduler = KOSScheduler()

# Process manager notifies scheduler of new processes
process = proc_mgr.create_process('app', ['/bin/app'])
scheduler.add_process(process)  # Usually done automatically

# Process state changes trigger scheduler updates
proc_mgr.start_process(process.pid)  # Moves to RUNNING state
proc_mgr.suspend_process(process.pid)  # Moves to SLEEPING state
```

### Memory Manager Integration

```python
# Scheduler considers memory pressure in decisions
from kos.memory.manager import MemoryManager

memory_mgr = MemoryManager()
if memory_mgr.get_memory_stats()['free_memory'] < (50 * 1024 * 1024):
    # Low memory - prefer to schedule processes that release memory
    scheduler.set_low_memory_mode(True)
```

### Security Integration

```python
# Scheduler respects security policies
from kos.security.manager import SecurityManager

security_mgr = SecurityManager()

# Only allow priority changes if permitted
if security_mgr.check_permission(current_user, 'set_priority'):
    scheduler.set_priority(process.pid, new_priority)
else:
    raise PermissionError("Priority change not permitted")
```
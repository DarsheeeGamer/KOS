# KOS Kernel Process Scheduler

This directory contains a complete kernel process scheduler implementation in C/C++ with Python bindings for the KOS operating system.

## Overview

The scheduler implements multiple scheduling classes:

- **CFS (Completely Fair Scheduler)**: Default scheduler for normal tasks using red-black trees
- **RT (Real-Time Scheduler)**: FIFO and Round-Robin scheduling for real-time tasks  
- **Fair Scheduler**: Advanced fair scheduling with load balancing and bandwidth control

## Architecture

### Core Components

- `sched.h`: Main header file with all structure definitions and function declarations
- `core.c`: Core scheduler infrastructure, initialization, and main scheduling loop
- `cfs.c`: CFS implementation with red-black tree operations
- `rt.c`: Real-time scheduler with priority queues and load balancing
- `fair.c`: Advanced fair scheduling algorithms and group scheduling
- `sched_wrapper.py`: Python bindings for scheduler functionality

### Key Features

1. **Multi-CPU Support**: Per-CPU runqueues with load balancing
2. **Red-Black Trees**: Efficient O(log n) task insertion/removal for CFS
3. **Priority Queues**: Bitmap-based priority queues for RT scheduling
4. **Load Balancing**: Automatic task migration between CPUs
5. **Bandwidth Control**: CPU bandwidth limiting and throttling
6. **Group Scheduling**: Hierarchical task group support
7. **Statistics**: Comprehensive performance monitoring and debugging

## Scheduling Classes

### CFS (Completely Fair Scheduler)

- Uses virtual runtime (vruntime) for fairness
- Red-black tree for O(log n) operations
- Load-weight based time slicing
- Wakeup preemption for responsiveness

### Real-Time Scheduler

- FIFO and Round-Robin policies
- Priority-based scheduling (0-99)
- Bandwidth throttling to prevent RT task monopolization
- Load balancing with priority awareness

### Fair Scheduler

- Advanced load tracking with exponential decay
- Group scheduling for process hierarchies
- Bandwidth enforcement per group
- Sophisticated load balancing algorithms

## Data Structures

### Task Structure
```c
struct task_struct {
    uint32_t pid;                    // Process ID
    task_state_t state;              // Current state
    int prio;                        // Dynamic priority
    uint32_t policy;                 // Scheduling policy
    struct sched_entity se;          // CFS scheduling entity
    struct sched_rt_entity rt;       // RT scheduling entity
    uint32_t cpu;                    // Current CPU
    uint32_t cpus_allowed;           // CPU affinity mask
    // ... more fields
};
```

### Runqueue Structure
```c
struct rq {
    uint32_t cpu;                    // CPU ID
    struct task_struct *curr;        // Current task
    struct cfs_rq cfs;              // CFS runqueue
    struct rt_rq rt;                // RT runqueue
    uint64_t nr_switches;           // Context switches
    uint64_t load_weight;           // CPU load
    // ... more fields
};
```

## Compilation

### Build the scheduler library:
```bash
make all
```

### Run tests:
```bash
# Python test
make test

# C test program
make test-c
```

### Clean build files:
```bash
make clean
```

## Usage

### C API Example

```c
#include "sched.h"

int main() {
    // Initialize scheduler with 4 CPUs
    sched_init(4);
    sched_start();
    
    // Create a task
    struct task_struct *task = create_task(1001, "test_task");
    set_task_policy(task, SCHED_NORMAL);
    set_user_nice(task, -5);  // Higher priority
    wake_up_process(task);
    
    // Let scheduler run
    sleep(10);
    
    // Cleanup
    destroy_task(task);
    sched_stop();
    return 0;
}
```

### Python API Example

```python
from sched_wrapper import KOSScheduler, SchedPolicy

# Create scheduler
sched = KOSScheduler(nr_cpus=4)
sched.start()

# Create tasks
sched.create_task(1001, "worker1", SchedPolicy.NORMAL, -5)
sched.create_task(1002, "rt_task", SchedPolicy.FIFO, 10)

# Monitor statistics
sched.print_stats()

# Cleanup
sched.stop()
```

## Scheduler Algorithms

### CFS Virtual Runtime

The CFS scheduler uses virtual runtime to ensure fairness:

```
vruntime += runtime * (NICE_0_LOAD / task_load_weight)
```

Tasks with higher priority (lower nice values) have higher load weights, causing their vruntime to advance slower.

### RT Priority Scheduling

RT tasks are scheduled strictly by priority using bitmaps for O(1) selection:

```
highest_prio = find_first_bit(rt_rq->bitmap, MAX_RT_PRIO)
```

### Load Balancing

Load balancing occurs periodically and on wakeup:

1. Find imbalanced CPUs
2. Select tasks for migration
3. Check CPU affinity
4. Migrate tasks to balance load

## Performance Characteristics

- **Task Selection**: O(1) for RT, O(log n) for CFS
- **Task Insertion**: O(log n) for CFS, O(1) for RT
- **Load Balancing**: O(n) where n is number of tasks
- **Memory Usage**: O(n) per CPU for runqueues

## Configuration

Scheduler parameters can be tuned via the configuration interface:

```c
set_sched_latency(6000000);        // 6ms target latency
set_sched_min_granularity(1500000); // 1.5ms minimum
set_sched_wakeup_granularity(2000000); // 2ms wakeup
```

## Debugging

Enable debug output and statistics:

```c
print_scheduler_stats();  // Overall statistics
print_task_info(task);    // Individual task info
```

## Integration with KOS

The scheduler integrates with KOS through:

1. **Process Management**: Creating/destroying processes
2. **Memory Management**: Stack allocation and cleanup  
3. **Signal Handling**: Process state changes
4. **System Calls**: Priority and policy changes
5. **Timer Interrupts**: Periodic scheduling and preemption

## Future Enhancements

- Deadline scheduling (SCHED_DEADLINE)
- NUMA topology awareness
- Energy-aware scheduling
- Container-aware scheduling
- Real-time bandwidth inheritance
- Hierarchical group scheduling

## References

- Linux CFS Scheduler Documentation
- "Operating System Concepts" by Silberschatz
- "Understanding the Linux Kernel" by Bovet & Cesati
- Real-Time Systems Design and Analysis by Phillip Laplante
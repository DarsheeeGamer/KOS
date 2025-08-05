# KOS Inter-Process Communication (IPC) System

A comprehensive IPC implementation for the KOS operating system, providing complete inter-process communication mechanisms in C/C++ with Python bindings.

## Overview

The KOS IPC system implements all major IPC mechanisms found in modern operating systems:

- **Pipes**: Anonymous and named pipes (FIFOs)
- **Shared Memory**: POSIX and System V shared memory segments
- **Message Queues**: POSIX and System V message queues
- **Semaphores**: POSIX and System V counting and binary semaphores
- **Mutexes**: Process-shared mutexes with recursive locking
- **Condition Variables**: Process-shared condition variables
- **Signals**: Signal handling and management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    KOS IPC System                          │
├─────────────────────────────────────────────────────────────┤
│  Python Bindings (ipc_wrapper.py)                          │
├─────────────────────────────────────────────────────────────┤
│  C Library (libkos_ipc.so)                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Pipes   │ │   SHM    │ │ Messages │ │ Signals  │      │
│  │ (pipe.c) │ │ (shm.c)  │ │(msgque.c)│ │(signal.c)│      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Semaphore │ │ Mutexes  │ │ CondVars │ │ Utilities│      │
│  │ (sem.c)  │ │          │ │          │ │(utils.c) │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
├─────────────────────────────────────────────────────────────┤
│               Core IPC Header (ipc.h)                      │
├─────────────────────────────────────────────────────────────┤
│           System Calls & Kernel Interface                  │
└─────────────────────────────────────────────────────────────┘
```

## Files Structure

```
kos/kernel/ipc/
├── ipc.h              # Main header file with all declarations
├── pipe.c             # Pipe implementation (anonymous & named)
├── shm.c              # Shared memory implementation
├── msgqueue.c         # Message queue implementation  
├── sem.c              # Semaphore, mutex, condition variable implementation
├── signal.c           # Signal handling implementation
├── ipc_utils.c        # Utility functions and IPC management
├── ipc_wrapper.py     # Python bindings
├── simple_makefile    # Build configuration
├── test_ipc.c         # C test program
├── demo_ipc.py        # Python demonstration
├── libkos_ipc.so      # Compiled shared library
└── README.md          # This file
```

## Features

### 1. Pipes (pipe.c)
- **Anonymous pipes**: Fast communication between related processes
- **Named pipes (FIFOs)**: Communication between unrelated processes
- **Non-blocking I/O**: Prevents deadlocks
- **Thread-safe**: Mutex protection for all operations

### 2. Shared Memory (shm.c)
- **POSIX shared memory**: Modern `shm_open`/`shm_unlink` interface
- **System V shared memory**: Traditional `shmget`/`shmat`/`shmdt` interface
- **Automatic synchronization**: Built-in mutex for safe access
- **Memory mapping**: Efficient zero-copy data sharing

### 3. Message Queues (msgqueue.c)
- **POSIX message queues**: Feature-rich with priorities and timeouts
- **System V message queues**: Traditional message passing
- **Priority handling**: Higher priority messages delivered first
- **Timed operations**: Non-blocking and timeout-based operations

### 4. Semaphores (sem.c)
- **POSIX semaphores**: Named and unnamed semaphores
- **System V semaphores**: Traditional semaphore sets
- **Counting semaphores**: Resource counting and limiting
- **Binary semaphores**: Mutual exclusion

### 5. Mutexes & Condition Variables
- **Process-shared mutexes**: Synchronization across processes
- **Recursive mutexes**: Safe for nested locking
- **Condition variables**: Wait/signal/broadcast operations
- **Timed waits**: Timeout-based waiting

### 6. Signal Handling (signal.c)
- **Signal registration**: Custom signal handlers
- **Signal blocking/unblocking**: Fine-grained signal control
- **Signal sending**: Send signals to processes
- **Signal waiting**: Synchronous signal handling

## Building

### Prerequisites
- GCC compiler with C99 support
- POSIX-compliant system (Linux, Unix)
- pthread library
- realtime library (librt)

### Compilation
```bash
cd kos/kernel/ipc
make -f simple_makefile
```

This creates `libkos_ipc.so` shared library.

### Testing
```bash
# Compile test program
gcc -Wall -Wextra -O2 -std=c99 -D_GNU_SOURCE test_ipc.c -L. -lkos_ipc -lpthread -lrt -o test_ipc

# Run tests
export LD_LIBRARY_PATH=.:$LD_LIBRARY_PATH
./test_ipc
```

## C API Usage

### Include Header
```c
#include "ipc.h"
```

### Error Handling
All functions return:
- `KOS_IPC_SUCCESS` (0) on success
- `KOS_IPC_ERROR` (-1) on error
- `KOS_IPC_TIMEOUT` (-2) on timeout
- `KOS_IPC_RESOURCE_BUSY` (-4) when resource is busy

### Example: Pipe Usage
```c
kos_pipe_t pipe;

// Create anonymous pipe
if (kos_pipe_create(&pipe) == KOS_IPC_SUCCESS) {
    // Write data
    const char *msg = "Hello, KOS!";
    kos_pipe_write(&pipe, msg, strlen(msg));
    
    // Read data
    char buffer[256];
    int bytes = kos_pipe_read(&pipe, buffer, sizeof(buffer));
    
    // Cleanup
    kos_pipe_destroy(&pipe);
}
```

### Example: Shared Memory Usage
```c
kos_shm_t shm;
size_t size = 4096;

// Create shared memory
if (kos_shm_create(&shm, "my_shm", size, 0) == KOS_IPC_SUCCESS) {
    // Get memory address
    void *addr = kos_shm_get_addr(&shm);
    
    // Lock for safe access
    kos_shm_lock(&shm);
    strcpy((char*)addr, "Shared data");
    kos_shm_unlock(&shm);
    
    // Cleanup
    kos_shm_destroy(&shm);
}
```

### Example: Semaphore Usage
```c
kos_semaphore_t sem;

// Create semaphore with initial value 1
if (kos_semaphore_create(&sem, "my_sem", 1, 1) == KOS_IPC_SUCCESS) {
    // Wait (P operation)
    if (kos_semaphore_wait(&sem, 1000) == KOS_IPC_SUCCESS) {
        // Critical section
        printf("In critical section\n");
        
        // Signal (V operation)
        kos_semaphore_post(&sem);
    }
    
    // Cleanup
    kos_semaphore_destroy(&sem);
}
```

## Python API Usage

### Basic Import
```python
from ipc_wrapper import *
```

### Context Manager (Recommended)
```python
with IPCManager() as ipc:
    # All IPC resources are automatically managed
    pipe = ipc.manage(Pipe())
    pipe.write(b"Hello from Python!")
    data = pipe.read()
```

### Example: Message Queue
```python
try:
    with MessageQueue("my_queue", posix=True) as mq:
        # Send message
        mq.send(b"Hello, World!", priority=5)
        
        # Receive message
        message, priority = mq.receive()
        print(f"Received: {message} (priority: {priority})")
        
except IPCException as e:
    print(f"IPC error: {e}")
```

### Example: Shared Memory
```python
with SharedMemory("my_shm", 1024, create=True) as shm:
    # Write data
    shm.write(b"Shared data from Python")
    
    # Read data
    data = shm.read()
    print(f"Read: {data}")
```

## Performance Characteristics

| IPC Method        | Latency | Throughput | Memory Usage | Complexity |
|-------------------|---------|------------|--------------|------------|
| Pipes             | Low     | High       | Low          | Simple     |
| Shared Memory     | Lowest  | Highest    | Medium       | Medium     |
| Message Queues    | Medium  | Medium     | Medium       | Medium     |
| Semaphores        | Low     | N/A        | Low          | Simple     |
| Signals           | Medium  | Low        | Lowest       | Complex    |

## Thread Safety

All IPC mechanisms are thread-safe and process-safe:
- Internal mutexes protect shared data structures
- Process-shared synchronization primitives
- Signal-safe functions where applicable
- Atomic operations for critical sections

## Error Handling

The system provides comprehensive error handling:
- Detailed error codes for different failure modes
- Automatic cleanup on errors
- Resource leak prevention
- Timeout handling for blocking operations

## Debugging and Monitoring

### Statistics
```c
// Get IPC system statistics
kos_ipc_get_stats();

// Get specific statistics
int active_pipes, active_shm;
kos_pipe_get_stats(&active_pipes, NULL, NULL);
kos_shm_get_stats(&active_shm, NULL);
```

### Debug Build
```bash
make -f simple_makefile CFLAGS="-DDEBUG -g"
```

## Limitations

1. **Resource Limits**: Bounded by system limits (ulimits)
2. **Platform Specific**: Currently Linux/Unix only
3. **Memory Overhead**: Each IPC object has metadata overhead
4. **Signal Limitations**: Some signals cannot be caught or blocked

## Future Enhancements

- [ ] Windows support via named pipes and file mapping
- [ ] Network-transparent IPC (TCP/UDP backing)
- [ ] Persistent message queues with disk backing
- [ ] Performance monitoring and profiling tools
- [ ] Integration with KOS process manager
- [ ] Automatic cleanup on process termination

## Testing

Run the comprehensive test suite:

```bash
# C tests
./test_ipc

# Python demonstration
python3 demo_ipc.py

# Performance tests (if available)
./benchmark_ipc
```

## Contributing

When contributing to the IPC system:

1. Maintain thread and process safety
2. Add comprehensive error handling
3. Update both C and Python APIs
4. Add tests for new functionality
5. Update documentation

## License

Part of the KOS operating system project. See main KOS license for details.

---

*This IPC system provides the foundation for all inter-process communication in KOS, enabling robust, scalable, and secure communication between system components and user applications.*
"""
KOS Kernel Python Wrapper

Provides Python interface to the KOS kernel core
"""

import ctypes
import os
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger('KOS.kernel')


class ProcessState(IntEnum):
    NEW = 0
    READY = 1
    RUNNING = 2
    BLOCKED = 3
    ZOMBIE = 4
    DEAD = 5


class ThreadState(IntEnum):
    NEW = 0
    READY = 1
    RUNNING = 2
    BLOCKED = 3
    SLEEPING = 4
    DEAD = 5


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    uid: int
    gid: int
    state: ProcessState
    thread_count: int
    cpu_time: int
    priority: int
    nice: int
    start_time: int


@dataclass
class ThreadInfo:
    tid: int
    pid: int
    state: ThreadState
    cpu_affinity: int
    runtime: int
    timeslice: int


class KOSKernel:
    """KOS Kernel interface"""
    
    def __init__(self):
        self.lib = None
        self._callbacks = {}
        self._load_library()
        self._initialize_kernel()
        
    def _load_library(self):
        """Load the kernel library"""
        lib_dir = os.path.dirname(__file__)
        lib_path = os.path.join(lib_dir, "libkos_kernel.so")
        
        if not os.path.exists(lib_path):
            self._compile_library()
            
        try:
            self.lib = ctypes.CDLL(lib_path)
            self._setup_functions()
            logger.info("KOS kernel library loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load kernel library: {e}")
            self.lib = None
            
    def _compile_library(self):
        """Compile the kernel library"""
        import subprocess
        
        lib_dir = os.path.dirname(__file__)
        
        # Create Makefile for kernel
        makefile_content = """
CC = gcc
CFLAGS = -shared -fPIC -Wall -O2 -pthread
LDFLAGS = -lpthread -lrt

SOURCES = kcore.c resource_monitor.c
HEADERS = kcore.h resource_monitor.h
TARGET = libkos_kernel.so

all: $(TARGET)

$(TARGET): $(SOURCES) $(HEADERS)
\t$(CC) $(CFLAGS) -o $@ $(SOURCES) $(LDFLAGS)

clean:
\trm -f $(TARGET)

.PHONY: all clean
"""
        
        makefile_path = os.path.join(lib_dir, "Makefile")
        with open(makefile_path, 'w') as f:
            f.write(makefile_content)
            
        try:
            subprocess.run(["make", "-C", lib_dir], check=True, capture_output=True)
            logger.info("Successfully compiled KOS kernel library")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to compile kernel: {e.stderr.decode()}")
            
    def _setup_functions(self):
        """Setup C function signatures"""
        if not self.lib:
            return
            
        # Kernel initialization
        self.lib.kos_kernel_init.argtypes = [ctypes.c_void_p]
        self.lib.kos_kernel_init.restype = ctypes.c_int
        
        # Process management
        self.lib.kos_process_create.argtypes = [ctypes.c_uint32, ctypes.c_char_p]
        self.lib.kos_process_create.restype = ctypes.c_void_p
        
        self.lib.kos_process_destroy.argtypes = [ctypes.c_uint32]
        self.lib.kos_process_destroy.restype = ctypes.c_int
        
        self.lib.kos_process_find.argtypes = [ctypes.c_uint32]
        self.lib.kos_process_find.restype = ctypes.c_void_p
        
        # Thread management
        self.lib.kos_thread_create.argtypes = [ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        self.lib.kos_thread_create.restype = ctypes.c_void_p
        
        self.lib.kos_thread_destroy.argtypes = [ctypes.c_uint32]
        self.lib.kos_thread_destroy.restype = ctypes.c_int
        
        # Memory management
        self.lib.kos_mem_alloc.argtypes = [ctypes.c_size_t]
        self.lib.kos_mem_alloc.restype = ctypes.c_void_p
        
        self.lib.kos_mem_free.argtypes = [ctypes.c_void_p]
        self.lib.kos_mem_free.restype = None
        
        # Time functions
        self.lib.kos_time_get_ticks.argtypes = []
        self.lib.kos_time_get_ticks.restype = ctypes.c_uint64
        
        self.lib.kos_time_get_unix.argtypes = []
        self.lib.kos_time_get_unix.restype = ctypes.c_uint64
        
        # System calls
        self.lib.kos_syscall.argtypes = [
            ctypes.c_uint32,  # syscall number
            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64,
            ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint64
        ]
        self.lib.kos_syscall.restype = ctypes.c_int64
        
    def _initialize_kernel(self):
        """Initialize the kernel"""
        if self.lib:
            ret = self.lib.kos_kernel_init(None)
            if ret == 0:
                logger.info("KOS kernel initialized successfully")
                
                # Start kernel thread
                self._kernel_thread = threading.Thread(
                    target=self._kernel_loop,
                    daemon=True
                )
                self._kernel_thread.start()
            else:
                logger.error("Failed to initialize KOS kernel")
        else:
            logger.warning("Kernel library not available, using mock implementation")
            
    def _kernel_loop(self):
        """Kernel main loop (runs in separate thread)"""
        # In real implementation, this would call kos_kernel_start()
        # For now, just a simple loop
        import time
        while True:
            time.sleep(0.001)  # 1ms tick
            
    def create_process(self, ppid: int = 0, name: str = "process") -> Optional[int]:
        """Create a new process"""
        if self.lib:
            proc_ptr = self.lib.kos_process_create(ppid, name.encode('utf-8'))
            if proc_ptr:
                # Extract PID from process structure
                # In real implementation, would properly parse the structure
                return 1  # Mock PID
        return None
        
    def destroy_process(self, pid: int) -> bool:
        """Destroy a process"""
        if self.lib:
            return self.lib.kos_process_destroy(pid) == 0
        return False
        
    def create_thread(self, pid: int, entry_func: Optional[Callable] = None) -> Optional[int]:
        """Create a new thread"""
        if self.lib:
            # For Python callbacks, we'd need to wrap them properly
            thread_ptr = self.lib.kos_thread_create(pid, None, None)
            if thread_ptr:
                return 1  # Mock TID
        return None
        
    def destroy_thread(self, tid: int) -> bool:
        """Destroy a thread"""
        if self.lib:
            return self.lib.kos_thread_destroy(tid) == 0
        return False
        
    def allocate_memory(self, size: int) -> Optional[int]:
        """Allocate kernel memory"""
        if self.lib:
            ptr = self.lib.kos_mem_alloc(size)
            if ptr:
                return int(ptr)
        return None
        
    def free_memory(self, ptr: int) -> None:
        """Free kernel memory"""
        if self.lib:
            self.lib.kos_mem_free(ctypes.c_void_p(ptr))
            
    def syscall(self, nr: int, *args) -> int:
        """Make a system call"""
        if self.lib:
            # Pad args to 6
            args_list = list(args) + [0] * (6 - len(args))
            return self.lib.kos_syscall(nr, *args_list[:6])
        return -1
        
    def get_ticks(self) -> int:
        """Get system ticks"""
        if self.lib:
            return self.lib.kos_time_get_ticks()
        return 0
        
    def get_unix_time(self) -> int:
        """Get Unix timestamp"""
        if self.lib:
            return self.lib.kos_time_get_unix()
        import time
        return int(time.time())
        
    def get_process_list(self) -> List[ProcessInfo]:
        """Get list of all processes"""
        # In real implementation, would iterate through kernel process list
        # For now, return mock data
        return [
            ProcessInfo(
                pid=1,
                ppid=0,
                uid=0,
                gid=0,
                state=ProcessState.RUNNING,
                thread_count=1,
                cpu_time=100,
                priority=20,
                nice=0,
                start_time=self.get_unix_time() - 3600
            )
        ]
        
    def get_thread_list(self, pid: Optional[int] = None) -> List[ThreadInfo]:
        """Get list of threads for a process or all threads"""
        # Mock implementation
        return [
            ThreadInfo(
                tid=1,
                pid=1,
                state=ThreadState.RUNNING,
                cpu_affinity=0xFFFFFFFF,
                runtime=100,
                timeslice=10
            )
        ]
        
    def set_process_limit(self, pid: int, resource: str, limit: int) -> bool:
        """Set resource limit for process"""
        # To be implemented with cgroup integration
        return True
        
    def get_kernel_stats(self) -> Dict[str, Any]:
        """Get kernel statistics"""
        return {
            'processes': len(self.get_process_list()),
            'threads': len(self.get_thread_list()),
            'uptime': self.get_unix_time() - (self.get_unix_time() - 3600),
            'ticks': self.get_ticks(),
            'memory': {
                'kernel': 0,  # To be implemented
                'user': 0
            }
        }


# Global kernel instance
_kernel_instance = None


def get_kernel() -> KOSKernel:
    """Get the global kernel instance"""
    global _kernel_instance
    if _kernel_instance is None:
        _kernel_instance = KOSKernel()
    return _kernel_instance
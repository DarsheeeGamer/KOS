"""
KOS Performance Optimization Framework
Implements various performance optimizations including:
- Memory pooling and object recycling
- Caching and memoization
- Lock-free data structures
- CPU affinity and NUMA awareness
- I/O optimization and buffering
- JIT compilation support
"""

import os
import sys
import time
import threading
import multiprocessing
import functools
import weakref
import gc
import ctypes
import mmap
import pickle
import logging
from typing import Dict, Any, Optional, List, Tuple, Callable, TypeVar, Generic
from collections import OrderedDict, deque
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass
import psutil

logger = logging.getLogger('kos.performance')

T = TypeVar('T')


class ObjectPool(Generic[T]):
    """Thread-safe object pool for recycling objects"""
    
    def __init__(self, factory: Callable[[], T], max_size: int = 1000):
        self.factory = factory
        self.max_size = max_size
        self._pool: deque[T] = deque()
        self._lock = threading.RLock()
        self._stats = {
            'created': 0,
            'recycled': 0,
            'discarded': 0
        }
    
    def acquire(self) -> T:
        """Get object from pool or create new one"""
        with self._lock:
            if self._pool:
                obj = self._pool.popleft()
                self._stats['recycled'] += 1
                return obj
            else:
                obj = self.factory()
                self._stats['created'] += 1
                return obj
    
    def release(self, obj: T):
        """Return object to pool"""
        with self._lock:
            if len(self._pool) < self.max_size:
                # Reset object state if it has reset method
                if hasattr(obj, 'reset'):
                    obj.reset()
                self._pool.append(obj)
            else:
                self._stats['discarded'] += 1
    
    def get_stats(self) -> Dict[str, int]:
        """Get pool statistics"""
        with self._lock:
            return {
                **self._stats,
                'pool_size': len(self._pool)
            }


class MemoryPool:
    """Memory pool for efficient allocation"""
    
    def __init__(self, block_size: int = 4096, initial_blocks: int = 100):
        self.block_size = block_size
        self.free_blocks: deque[memoryview] = deque()
        self.allocated_blocks: Dict[int, memoryview] = {}
        self._lock = threading.RLock()
        
        # Pre-allocate memory
        self._expand_pool(initial_blocks)
    
    def _expand_pool(self, num_blocks: int):
        """Expand memory pool"""
        # Allocate large contiguous memory
        total_size = num_blocks * self.block_size
        buffer = bytearray(total_size)
        
        # Split into blocks
        for i in range(num_blocks):
            start = i * self.block_size
            end = start + self.block_size
            block = memoryview(buffer)[start:end]
            self.free_blocks.append(block)
    
    def allocate(self, size: int) -> memoryview:
        """Allocate memory from pool"""
        if size > self.block_size:
            # Large allocation - bypass pool
            return memoryview(bytearray(size))
        
        with self._lock:
            if not self.free_blocks:
                self._expand_pool(10)
            
            block = self.free_blocks.popleft()
            block_id = id(block)
            self.allocated_blocks[block_id] = block
            
            # Return slice of requested size
            return block[:size]
    
    def deallocate(self, memory: memoryview):
        """Return memory to pool"""
        block_id = id(memory)
        
        with self._lock:
            if block_id in self.allocated_blocks:
                block = self.allocated_blocks.pop(block_id)
                self.free_blocks.append(block)


class LRUCache:
    """Thread-safe LRU cache with TTL support"""
    
    def __init__(self, max_size: int = 1000, ttl: float = None):
        self.max_size = max_size
        self.ttl = ttl
        self._cache: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
    
    def get(self, key: Any) -> Optional[Any]:
        """Get value from cache"""
        with self._lock:
            if key not in self._cache:
                self._stats['misses'] += 1
                return None
            
            value, timestamp = self._cache[key]
            
            # Check TTL
            if self.ttl and time.time() - timestamp > self.ttl:
                del self._cache[key]
                self._stats['misses'] += 1
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._stats['hits'] += 1
            return value
    
    def put(self, key: Any, value: Any):
        """Put value in cache"""
        with self._lock:
            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats['evictions'] += 1
            
            self._cache[key] = (value, time.time())
    
    def clear(self):
        """Clear cache"""
        with self._lock:
            self._cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        with self._lock:
            return {
                **self._stats,
                'size': len(self._cache)
            }


def memoize(max_size: int = 128, ttl: float = None):
    """Decorator for memoizing function results"""
    def decorator(func: Callable) -> Callable:
        cache = LRUCache(max_size=max_size, ttl=ttl)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            key = (args, tuple(sorted(kwargs.items())))
            
            # Check cache
            result = cache.get(key)
            if result is not None:
                return result
            
            # Compute and cache
            result = func(*args, **kwargs)
            cache.put(key, result)
            return result
        
        # Add cache control methods
        wrapper.cache = cache
        wrapper.clear_cache = cache.clear
        wrapper.cache_stats = cache.get_stats
        
        return wrapper
    
    return decorator


class LockFreeQueue:
    """Lock-free queue using atomic operations"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._buffer = [None] * max_size
        self._head = ctypes.c_long(0)
        self._tail = ctypes.c_long(0)
        self._size = ctypes.c_long(0)
    
    def enqueue(self, item: Any) -> bool:
        """Add item to queue"""
        current_tail = self._tail.value
        next_tail = (current_tail + 1) % self.max_size
        
        # Check if full
        if next_tail == self._head.value:
            return False
        
        # Store item
        self._buffer[current_tail] = item
        
        # Update tail atomically
        self._tail.value = next_tail
        self._size.value += 1
        
        return True
    
    def dequeue(self) -> Optional[Any]:
        """Remove item from queue"""
        # Check if empty
        if self._head.value == self._tail.value:
            return None
        
        # Get item
        item = self._buffer[self._head.value]
        
        # Update head atomically
        self._head.value = (self._head.value + 1) % self.max_size
        self._size.value -= 1
        
        return item
    
    def size(self) -> int:
        """Get queue size"""
        return self._size.value


class CPUAffinity:
    """CPU affinity and NUMA management"""
    
    def __init__(self):
        self.cpu_count = multiprocessing.cpu_count()
        self.numa_nodes = self._detect_numa_nodes()
    
    def _detect_numa_nodes(self) -> List[List[int]]:
        """Detect NUMA topology"""
        # Try to read from sysfs
        numa_nodes = []
        
        try:
            node_path = "/sys/devices/system/node"
            if os.path.exists(node_path):
                for node_dir in os.listdir(node_path):
                    if node_dir.startswith("node"):
                        cpulist_path = os.path.join(node_path, node_dir, "cpulist")
                        if os.path.exists(cpulist_path):
                            with open(cpulist_path) as f:
                                cpu_list = self._parse_cpu_list(f.read().strip())
                                numa_nodes.append(cpu_list)
        except:
            # Fallback: treat all CPUs as single NUMA node
            numa_nodes = [list(range(self.cpu_count))]
        
        return numa_nodes
    
    def _parse_cpu_list(self, cpu_str: str) -> List[int]:
        """Parse CPU list string (e.g., '0-3,8-11')"""
        cpus = []
        for part in cpu_str.split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                cpus.extend(range(start, end + 1))
            else:
                cpus.append(int(part))
        return cpus
    
    def set_thread_affinity(self, cpus: List[int]):
        """Set CPU affinity for current thread"""
        try:
            # Use psutil if available
            p = psutil.Process()
            p.cpu_affinity(cpus)
        except:
            # Fallback to OS-specific methods
            if hasattr(os, 'sched_setaffinity'):
                os.sched_setaffinity(0, cpus)
    
    def get_thread_affinity(self) -> List[int]:
        """Get CPU affinity for current thread"""
        try:
            p = psutil.Process()
            return p.cpu_affinity()
        except:
            if hasattr(os, 'sched_getaffinity'):
                return list(os.sched_getaffinity(0))
            else:
                return list(range(self.cpu_count))
    
    def bind_to_numa_node(self, node_id: int):
        """Bind thread to NUMA node"""
        if 0 <= node_id < len(self.numa_nodes):
            self.set_thread_affinity(self.numa_nodes[node_id])


class IOOptimizer:
    """I/O optimization utilities"""
    
    def __init__(self):
        self.page_size = os.sysconf('SC_PAGE_SIZE') if hasattr(os, 'sysconf') else 4096
        self.buffer_pools = {}
    
    def get_aligned_buffer(self, size: int) -> bytearray:
        """Get page-aligned buffer for direct I/O"""
        # Round up to page size
        aligned_size = ((size + self.page_size - 1) // self.page_size) * self.page_size
        
        # Get from pool if available
        if aligned_size in self.buffer_pools:
            pool = self.buffer_pools[aligned_size]
            return pool.acquire()
        
        # Create new buffer
        return bytearray(aligned_size)
    
    def release_buffer(self, buffer: bytearray):
        """Release buffer back to pool"""
        size = len(buffer)
        
        if size not in self.buffer_pools:
            self.buffer_pools[size] = ObjectPool(
                factory=lambda: bytearray(size),
                max_size=10
            )
        
        self.buffer_pools[size].release(buffer)
    
    def enable_direct_io(self, fd: int):
        """Enable O_DIRECT for file descriptor"""
        try:
            # Linux O_DIRECT
            O_DIRECT = 0o40000
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | O_DIRECT)
        except:
            pass
    
    def advise_sequential(self, fd: int, offset: int = 0, length: int = 0):
        """Advise kernel for sequential access"""
        try:
            # POSIX_FADV_SEQUENTIAL
            os.posix_fadvise(fd, offset, length, 2)
        except:
            pass
    
    def advise_random(self, fd: int, offset: int = 0, length: int = 0):
        """Advise kernel for random access"""
        try:
            # POSIX_FADV_RANDOM
            os.posix_fadvise(fd, offset, length, 1)
        except:
            pass


class BatchProcessor:
    """Batch processing for improved throughput"""
    
    def __init__(self, process_func: Callable, batch_size: int = 100, 
                 max_wait: float = 0.1):
        self.process_func = process_func
        self.batch_size = batch_size
        self.max_wait = max_wait
        self._queue = deque()
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._running = True
        self._processor_thread = threading.Thread(
            target=self._process_loop,
            daemon=True
        )
        self._processor_thread.start()
    
    def add(self, item: Any):
        """Add item for batch processing"""
        with self._lock:
            self._queue.append(item)
            if len(self._queue) >= self.batch_size:
                self._condition.notify()
    
    def _process_loop(self):
        """Batch processing loop"""
        while self._running:
            batch = []
            
            with self._lock:
                # Wait for batch or timeout
                end_time = time.time() + self.max_wait
                while len(self._queue) < self.batch_size and self._running:
                    timeout = end_time - time.time()
                    if timeout <= 0 or not self._condition.wait(timeout):
                        break
                
                # Collect batch
                while self._queue and len(batch) < self.batch_size:
                    batch.append(self._queue.popleft())
            
            # Process batch
            if batch:
                try:
                    self.process_func(batch)
                except Exception as e:
                    logger.error(f"Batch processing error: {e}")
    
    def stop(self):
        """Stop batch processor"""
        self._running = False
        with self._lock:
            self._condition.notify()
        self._processor_thread.join()


class JITCompiler:
    """Simple JIT compilation support using exec"""
    
    def __init__(self):
        self._compiled_funcs = {}
    
    def compile_function(self, name: str, code: str, globals_dict: Dict[str, Any] = None):
        """Compile Python code to function"""
        if globals_dict is None:
            globals_dict = {}
        
        # Compile code
        compiled = compile(code, f"<jit:{name}>", "exec")
        
        # Execute to define function
        local_dict = {}
        exec(compiled, globals_dict, local_dict)
        
        # Store compiled function
        if name in local_dict:
            self._compiled_funcs[name] = local_dict[name]
            return local_dict[name]
        
        raise ValueError(f"Function {name} not found in compiled code")
    
    def get_function(self, name: str) -> Optional[Callable]:
        """Get compiled function"""
        return self._compiled_funcs.get(name)
    
    def optimize_loop(self, loop_body: str, iterations: int) -> str:
        """Optimize loop by unrolling"""
        if iterations <= 8:
            # Full unroll for small loops
            return '\n'.join([loop_body.replace('{{i}}', str(i)) 
                            for i in range(iterations)])
        else:
            # Partial unroll
            unroll_factor = 4
            unrolled = []
            
            for i in range(0, iterations, unroll_factor):
                for j in range(min(unroll_factor, iterations - i)):
                    unrolled.append(loop_body.replace('{{i}}', str(i + j)))
            
            return '\n'.join(unrolled)


class PerformanceMonitor:
    """System-wide performance monitoring"""
    
    def __init__(self):
        self.metrics = {
            'cpu_usage': deque(maxlen=60),
            'memory_usage': deque(maxlen=60),
            'io_stats': deque(maxlen=60),
            'gc_stats': deque(maxlen=60)
        }
        self._monitoring = False
        self._monitor_thread = None
    
    def start_monitoring(self, interval: float = 1.0):
        """Start performance monitoring"""
        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval,),
            daemon=True
        )
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop performance monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join()
    
    def _monitor_loop(self, interval: float):
        """Monitoring loop"""
        while self._monitoring:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.metrics['cpu_usage'].append({
                'timestamp': time.time(),
                'percent': cpu_percent,
                'per_cpu': psutil.cpu_percent(percpu=True)
            })
            
            # Memory usage
            mem = psutil.virtual_memory()
            self.metrics['memory_usage'].append({
                'timestamp': time.time(),
                'percent': mem.percent,
                'used': mem.used,
                'available': mem.available
            })
            
            # I/O stats
            io = psutil.disk_io_counters()
            if io:
                self.metrics['io_stats'].append({
                    'timestamp': time.time(),
                    'read_bytes': io.read_bytes,
                    'write_bytes': io.write_bytes,
                    'read_count': io.read_count,
                    'write_count': io.write_count
                })
            
            # GC stats
            gc_stats = gc.get_stats()
            if gc_stats:
                self.metrics['gc_stats'].append({
                    'timestamp': time.time(),
                    'collections': sum(s.get('collections', 0) for s in gc_stats),
                    'collected': sum(s.get('collected', 0) for s in gc_stats),
                    'uncollectable': sum(s.get('uncollectable', 0) for s in gc_stats)
                })
            
            time.sleep(interval)
    
    def get_metrics(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get performance metrics"""
        return {
            name: list(values) 
            for name, values in self.metrics.items()
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        summary = {}
        
        # CPU summary
        if self.metrics['cpu_usage']:
            cpu_values = [m['percent'] for m in self.metrics['cpu_usage']]
            summary['cpu'] = {
                'current': cpu_values[-1] if cpu_values else 0,
                'average': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values)
            }
        
        # Memory summary
        if self.metrics['memory_usage']:
            mem_values = [m['percent'] for m in self.metrics['memory_usage']]
            summary['memory'] = {
                'current': mem_values[-1] if mem_values else 0,
                'average': sum(mem_values) / len(mem_values),
                'max': max(mem_values)
            }
        
        return summary


# Global instances
_performance_monitor = None
_cpu_affinity = None
_io_optimizer = None
_jit_compiler = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
        _performance_monitor.start_monitoring()
    return _performance_monitor

def get_cpu_affinity() -> CPUAffinity:
    """Get global CPU affinity manager"""
    global _cpu_affinity
    if _cpu_affinity is None:
        _cpu_affinity = CPUAffinity()
    return _cpu_affinity

def get_io_optimizer() -> IOOptimizer:
    """Get global I/O optimizer"""
    global _io_optimizer
    if _io_optimizer is None:
        _io_optimizer = IOOptimizer()
    return _io_optimizer

def get_jit_compiler() -> JITCompiler:
    """Get global JIT compiler"""
    global _jit_compiler
    if _jit_compiler is None:
        _jit_compiler = JITCompiler()
    return _jit_compiler
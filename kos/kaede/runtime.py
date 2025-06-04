"""
Kaede Runtime System
===================

Clean runtime environment combining essential features from:
- Python: Dynamic typing, built-ins, iterators, context managers
- C++: STL containers, memory management, templates
- Rust: Ownership, Option/Result types, traits, pattern matching
"""

import gc
import threading
import time
import asyncio
import weakref
from typing import Dict, List, Any, Optional, Callable, Union, Iterator
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum
from contextlib import contextmanager

# Import from our core language implementation
from .core_language import (
    KaedeRuntime as CoreRuntime,
    StdLibrary,
    Vector, Map, Set,
    RustOption, RustResult,
    Template, Trait,
    MemoryManager,
    KaedeType,
    runtime as core_runtime
)

class RuntimeMode(Enum):
    """Runtime execution modes"""
    DEVELOPMENT = "development"
    PRODUCTION = "production"
    DEBUG = "debug"

@dataclass
class RuntimeStatistics:
    """Runtime performance statistics"""
    objects_created: int = 0
    objects_destroyed: int = 0
    function_calls: int = 0
    gc_collections: int = 0
    memory_allocated: int = 0
    memory_freed: int = 0
    execution_time: float = 0.0

@dataclass
class MemoryInfo:
    """Memory usage information"""
    allocated: int = 0
    in_use: int = 0
    available: int = 0
    peak_usage: int = 0

class KaedeRuntime:
    """Main Kaede runtime system with all language features"""
    
    def __init__(self, mode: RuntimeMode = RuntimeMode.DEVELOPMENT):
        self.mode = mode
        self.global_scope = {}
        self.statistics = RuntimeStatistics()
        self.memory_info = MemoryInfo()
        
        # Use the core runtime from our complete implementation
        self.core_runtime = core_runtime
        self.memory_manager = self.core_runtime.memory
        self.stdlib = self.core_runtime.stdlib
        
        # Copy all built-ins from core runtime
        self.global_scope.update(self.core_runtime.global_scope)
        
        print(f"Kaede Runtime initialized in {self.mode.value} mode")
        print(f"Available features: Python built-ins, C++ STL, Rust types")
    
    # Enhanced built-in functions with all language features
    def _builtin_print(self, *args, **kwargs):
        """Python print with C++ iostream style"""
        self.statistics.function_calls += 1
        return self.core_runtime._builtin_print(*args, **kwargs)
    
    def _builtin_len(self, obj):
        """Universal len() supporting Python, C++, and Rust containers"""
        self.statistics.function_calls += 1
        return self.stdlib.len(obj)
    
    def _builtin_range(self, *args):
        """Enhanced range with all Python features"""
        self.statistics.function_calls += 1
        return self.stdlib.range(*args)
    
    # Python features
    def _builtin_list(self, iterable=None):
        return list(iterable) if iterable else []
    
    def _builtin_dict(self, *args, **kwargs):
        if args:
            return dict(args[0])
        return dict(**kwargs)
    
    def _builtin_str(self, obj=None):
        return str(obj) if obj is not None else ""
    
    def _builtin_int(self, obj=None, base=10):
        if obj is None:
            return 0
        return int(obj, base) if isinstance(obj, str) else int(obj)
    
    def _builtin_float(self, obj=None):
        return float(obj) if obj is not None else 0.0
    
    def _builtin_bool(self, obj=None):
        return bool(obj) if obj is not None else False
    
    def _builtin_enumerate(self, iterable, start=0):
        return enumerate(iterable, start)
    
    def _builtin_zip(self, *iterables):
        return zip(*iterables)
    
    def _builtin_map(self, func, *iterables):
        return map(func, *iterables)
    
    def _builtin_filter(self, func, iterable):
        return filter(func, iterable)
    
    def _builtin_sum(self, iterable, start=0):
        return sum(iterable, start)
    
    def _builtin_min(self, *args, **kwargs):
        return min(*args, **kwargs)
    
    def _builtin_max(self, *args, **kwargs):
        return max(*args, **kwargs)
    
    def _builtin_abs(self, x):
        return abs(x)
    
    def _builtin_round(self, number, ndigits=None):
        return round(number, ndigits)
    
    def _builtin_sorted(self, iterable, **kwargs):
        return sorted(iterable, **kwargs)
    
    def _builtin_reversed(self, iterable):
        return reversed(iterable)
    
    # C++ STL features
    def _create_vector(self, initial_data=None):
        """Create C++ style vector"""
        vec = Vector()
        if initial_data:
            for item in initial_data:
                vec.push_back(item)
        return vec
    
    def _create_map(self, initial_data=None):
        """Create C++ style map"""
        m = Map()
        if initial_data:
            for key, value in initial_data.items():
                m.insert(key, value)
        return m
    
    def _create_set(self, initial_data=None):
        """Create C++ style set"""
        s = Set()
        if initial_data:
            for item in initial_data:
                s.insert(item)
        return s
    
    def _make_unique(self, obj):
        """C++ make_unique"""
        return self.memory_manager.make_unique(obj)
    
    def _make_shared(self, obj):
        """C++ make_shared"""
        return self.memory_manager.make_shared(obj)
    
    # Rust features
    def _create_option(self, value=None):
        """Create Rust Option type"""
        return RustOption.Some(value) if value is not None else RustOption.None_()
    
    def _create_result_ok(self, value):
        """Create Rust Result::Ok"""
        return RustResult.Ok(value)
    
    def _create_result_err(self, error):
        """Create Rust Result::Err"""
        return RustResult.Err(error)
    
    # STL Algorithms
    def _stl_find(self, container, value):
        """std::find"""
        return self.stdlib.find(container, value)
    
    def _stl_sort(self, container, **kwargs):
        """std::sort"""
        return self.stdlib.sort(container, **kwargs)
    
    def _stl_transform(self, container, func):
        """std::transform"""
        return self.stdlib.transform(container, func)
    
    def _stl_count(self, container, value):
        """std::count"""
        return self.stdlib.count(container, value)
    
    def _stl_unique(self, container):
        """std::unique"""
        return self.stdlib.unique(container)
    
    # Rust iterators
    def _rust_collect(self, iterator):
        """Rust collect()"""
        return self.stdlib.collect(iterator)
    
    def _rust_fold(self, iterator, initial, func):
        """Rust fold()"""
        return self.stdlib.fold(iterator, initial, func)
    
    def _rust_take(self, iterator, n):
        """Rust take()"""
        return self.stdlib.take(iterator, n)
    
    def _rust_skip(self, iterator, n):
        """Rust skip()"""
        return self.stdlib.skip(iterator, n)
    
    # File I/O (all languages)
    def _open_file(self, filename, mode='r', encoding=None):
        """Universal file opening"""
        return open(filename, mode, encoding=encoding)
    
    @contextmanager
    def _file_context(self, filename, mode='r'):
        """RAII-style file context manager"""
        with self.stdlib.file_context(filename, mode) as f:
            yield f
    
    # Math functions
    def _math_sqrt(self, x):
        return self.stdlib.math_sqrt(x)
    
    def _math_sin(self, x):
        return self.stdlib.math_sin(x)
    
    def _math_cos(self, x):
        return self.stdlib.math_cos(x)
    
    def _math_log(self, x, base=None):
        import math
        return math.log(x) if base is None else math.log(x, base)
    
    # String operations
    def _string_format(self, template, *args, **kwargs):
        """String formatting"""
        return template.format(*args, **kwargs)
    
    def _regex_match(self, pattern, string):
        """Regular expression matching"""
        return self.stdlib.regex_match(pattern, string)
    
    def _regex_search(self, pattern, string):
        """Regular expression search"""
        return self.stdlib.regex_search(pattern, string)
    
    # JSON operations
    def _json_loads(self, s):
        """Parse JSON string"""
        return self.stdlib.json_loads(s)
    
    def _json_dumps(self, obj, indent=None):
        """Serialize to JSON"""
        return self.stdlib.json_dumps(obj, indent)
    
    # Threading and concurrency
    def _thread_lock(self):
        """Create thread lock"""
        return self.stdlib.thread_lock()
    
    def _thread_create(self, func, *args, **kwargs):
        """Create and start thread"""
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()
        return thread
    
    # Async operations
    async def _async_sleep(self, seconds):
        """Async sleep"""
        await self.stdlib.async_sleep(seconds)
    
    async def _async_gather(self, *awaitables):
        """Gather async operations"""
        return await self.stdlib.async_gather(*awaitables)
    
    # Memory management
    def _gc_collect(self):
        """Force garbage collection"""
        collected = self.memory_manager.collect_garbage()
        self.statistics.gc_collections += 1
        return collected
    
    def _get_memory_info(self):
        """Get memory usage information"""
        return {
            'allocated': self.memory_info.allocated,
            'in_use': self.memory_info.in_use,
            'available': self.memory_info.available,
            'peak_usage': self.memory_info.peak_usage,
        }
    
    # Type system operations
    def _create_type(self, name: str, **kwargs):
        """Create new type"""
        return self.core_runtime.create_type(name, **kwargs)
    
    def _create_trait(self, name: str):
        """Create new trait"""
        return self.core_runtime.create_trait(name)
    
    def _create_template(self, name: str, type_params: List[str]):
        """Create new template"""
        return self.core_runtime.create_template(name, type_params)
    
    # Runtime management
    def get_statistics(self) -> Dict[str, Any]:
        """Get runtime statistics"""
        return {
            'objects_created': self.statistics.objects_created,
            'objects_destroyed': self.statistics.objects_destroyed,
            'function_calls': self.statistics.function_calls,
            'gc_collections': self.statistics.gc_collections,
            'memory_allocated': self.statistics.memory_allocated,
            'memory_freed': self.statistics.memory_freed,
            'execution_time': self.statistics.execution_time,
        }
    
    def handle_exception(self, exception: Exception) -> bool:
        """Handle runtime exceptions"""
        print(f"Kaede Runtime Error: {exception}")
        return True
    
    def shutdown(self):
        """Shutdown runtime cleanly"""
        print("Shutting down Kaede Runtime...")
        
        # Final garbage collection
        self._gc_collect()
        
        print("Kaede Runtime shutdown complete.")

# Initialize global scope with all features
def initialize_runtime_scope():
    """Initialize the runtime with all built-in functions"""
    runtime = KaedeRuntime()
    
    # Add all built-in functions to global scope
    runtime.global_scope.update({
        # Python built-ins
        'print': runtime._builtin_print,
        'len': runtime._builtin_len,
        'range': runtime._builtin_range,
        'list': runtime._builtin_list,
        'dict': runtime._builtin_dict,
        'str': runtime._builtin_str,
        'int': runtime._builtin_int,
        'float': runtime._builtin_float,
        'bool': runtime._builtin_bool,
        'enumerate': runtime._builtin_enumerate,
        'zip': runtime._builtin_zip,
        'map': runtime._builtin_map,
        'filter': runtime._builtin_filter,
        'sum': runtime._builtin_sum,
        'min': runtime._builtin_min,
        'max': runtime._builtin_max,
        'abs': runtime._builtin_abs,
        'round': runtime._builtin_round,
        'sorted': runtime._builtin_sorted,
        'reversed': runtime._builtin_reversed,
        
        # C++ STL containers
        'vector': runtime._create_vector,
        'map': runtime._create_map,
        'set': runtime._create_set,
        'unique_ptr': runtime._make_unique,
        'shared_ptr': runtime._make_shared,
        
        # Rust types
        'Option': runtime._create_option,
        'Some': RustOption.Some,
        'None': RustOption.None_,
        'Ok': runtime._create_result_ok,
        'Err': runtime._create_result_err,
        'Result': RustResult,
        
        # STL algorithms
        'find': runtime._stl_find,
        'sort': runtime._stl_sort,
        'transform': runtime._stl_transform,
        'count': runtime._stl_count,
        'unique': runtime._stl_unique,
        
        # Rust iterators
        'collect': runtime._rust_collect,
        'fold': runtime._rust_fold,
        'take': runtime._rust_take,
        'skip': runtime._rust_skip,
        
        # File operations
        'open': runtime._open_file,
        'file_context': runtime._file_context,
        
        # Math
        'sqrt': runtime._math_sqrt,
        'sin': runtime._math_sin,
        'cos': runtime._math_cos,
        'log': runtime._math_log,
        
        # String operations
        'format': runtime._string_format,
        'regex_match': runtime._regex_match,
        'regex_search': runtime._regex_search,
        
        # JSON
        'json_loads': runtime._json_loads,
        'json_dumps': runtime._json_dumps,
        
        # Threading
        'Lock': runtime._thread_lock,
        'Thread': runtime._thread_create,
        
        # Async
        'async_sleep': runtime._async_sleep,
        'async_gather': runtime._async_gather,
        
        # Memory management
        'gc_collect': runtime._gc_collect,
        'memory_info': runtime._get_memory_info,
        
        # Type system
        'create_type': runtime._create_type,
        'create_trait': runtime._create_trait,
        'create_template': runtime._create_template,
    })
    
    return runtime

# Global runtime instance
_runtime = None

def get_runtime() -> Optional[KaedeRuntime]:
    """Get current runtime instance"""
    return _runtime

def initialize_runtime(mode: RuntimeMode = RuntimeMode.DEVELOPMENT) -> KaedeRuntime:
    """Initialize global runtime"""
    global _runtime
    _runtime = initialize_runtime_scope()
    _runtime.mode = mode
    return _runtime

def shutdown_runtime():
    """Shutdown global runtime"""
    global _runtime
    if _runtime:
        _runtime.shutdown()
        _runtime = None 
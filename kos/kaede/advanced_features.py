"""
Advanced Features for Kaede Programming Language
===============================================

This module implements advanced programming language features:
- Metaprogramming and reflection
- Decorators and function composition
- Generators and iterators
- Async/await and coroutines
- Pattern matching
- Macros and code generation
- Type system and annotations
- Memory management extensions
- Performance optimization
- Domain-specific languages (DSLs)
- Code analysis and transformation
"""

import ast
import inspect
import types
import functools
import asyncio
import weakref
import time
import gc
from typing import Any, Dict, List, Optional, Callable, Generator, Union, Tuple, Type
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
from contextlib import contextmanager
import logging

logger = logging.getLogger('KOS.kaede.advanced')

class KaedeType(Enum):
    """Kaede type system"""
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    BOOLEAN = auto()
    LIST = auto()
    DICT = auto()
    FUNCTION = auto()
    CLASS = auto()
    MODULE = auto()
    COROUTINE = auto()
    GENERATOR = auto()
    ASYNC_GENERATOR = auto()
    UNION = auto()
    OPTIONAL = auto()
    GENERIC = auto()

@dataclass
class TypeAnnotation:
    """Type annotation for Kaede values"""
    base_type: KaedeType
    generic_args: List['TypeAnnotation'] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    nullable: bool = False
    
    def __str__(self):
        type_str = self.base_type.name.lower()
        if self.generic_args:
            args_str = ', '.join(str(arg) for arg in self.generic_args)
            type_str += f"[{args_str}]"
        if self.nullable:
            type_str += "?"
        return type_str

class KaedeDecorator:
    """Base class for Kaede decorators"""
    
    def __init__(self, func: Callable):
        self.func = func
        self.metadata = {}
        functools.update_wrapper(self, func)
    
    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to decorated function"""
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default=None):
        """Get metadata from decorated function"""
        return self.metadata.get(key, default)

class MemoizeDecorator(KaedeDecorator):
    """Memoization decorator for caching function results"""
    
    def __init__(self, func: Callable, max_size: int = 128):
        super().__init__(func)
        self.cache = {}
        self.max_size = max_size
        self.access_times = {}
        self.call_count = 0
    
    def __call__(self, *args, **kwargs):
        # Create cache key
        key = self._make_key(args, kwargs)
        
        if key in self.cache:
            self.access_times[key] = time.time()
            return self.cache[key]
        
        # Calculate result
        result = self.func(*args, **kwargs)
        
        # Store in cache
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        self.cache[key] = result
        self.access_times[key] = time.time()
        self.call_count += 1
        
        return result
    
    def _make_key(self, args, kwargs):
        """Create cache key from arguments"""
        return str(args) + str(sorted(kwargs.items()))
    
    def _evict_oldest(self):
        """Evict least recently used item"""
        if not self.access_times:
            return
        
        oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
    
    def clear_cache(self):
        """Clear the cache"""
        self.cache.clear()
        self.access_times.clear()
    
    def cache_info(self):
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache),
            'max_size': self.max_size,
            'call_count': self.call_count,
            'hit_rate': 1 - (self.call_count / len(self.cache)) if self.cache else 0
        }

class TimingDecorator(KaedeDecorator):
    """Decorator for measuring function execution time"""
    
    def __init__(self, func: Callable, log_calls: bool = True):
        super().__init__(func)
        self.execution_times = []
        self.log_calls = log_calls
    
    def __call__(self, *args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = self.func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            self.execution_times.append(execution_time)
            
            if self.log_calls:
                logger.info(f"Function {self.func.__name__} executed in {execution_time:.6f} seconds")
    
    def get_stats(self):
        """Get execution time statistics"""
        if not self.execution_times:
            return {}
        
        times = self.execution_times
        return {
            'total_calls': len(times),
            'total_time': sum(times),
            'average_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times),
            'recent_times': times[-10:]  # Last 10 calls
        }

class RetryDecorator(KaedeDecorator):
    """Decorator for automatic retry with exponential backoff"""
    
    def __init__(self, func: Callable, max_retries: int = 3, delay: float = 1.0, 
                 backoff_factor: float = 2.0, exceptions: Tuple = (Exception,)):
        super().__init__(func)
        self.max_retries = max_retries
        self.delay = delay
        self.backoff_factor = backoff_factor
        self.exceptions = exceptions
        self.retry_count = 0
    
    def __call__(self, *args, **kwargs):
        last_exception = None
        current_delay = self.delay
        
        for attempt in range(self.max_retries + 1):
            try:
                result = self.func(*args, **kwargs)
                if attempt > 0:
                    logger.info(f"Function {self.func.__name__} succeeded on attempt {attempt + 1}")
                return result
            except self.exceptions as e:
                last_exception = e
                self.retry_count += 1
                
                if attempt < self.max_retries:
                    logger.warning(f"Function {self.func.__name__} failed (attempt {attempt + 1}), retrying in {current_delay}s")
                    time.sleep(current_delay)
                    current_delay *= self.backoff_factor
                else:
                    logger.error(f"Function {self.func.__name__} failed after {self.max_retries + 1} attempts")
        
        raise last_exception

class KaedeGenerator:
    """Enhanced generator with additional functionality"""
    
    def __init__(self, generator_func: Callable):
        self.generator_func = generator_func
        self.instances = weakref.WeakSet()
    
    def __call__(self, *args, **kwargs):
        """Create new generator instance"""
        generator = self.generator_func(*args, **kwargs)
        enhanced_gen = EnhancedGenerator(generator)
        self.instances.add(enhanced_gen)
        return enhanced_gen
    
    def close_all(self):
        """Close all active generator instances"""
        for gen in list(self.instances):
            try:
                gen.close()
            except:
                pass

class EnhancedGenerator:
    """Generator wrapper with additional methods"""
    
    def __init__(self, generator):
        self.generator = generator
        self.sent_values = []
        self.yielded_values = []
        self.is_closed = False
    
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.is_closed:
            raise StopIteration
        
        try:
            value = next(self.generator)
            self.yielded_values.append(value)
            return value
        except StopIteration:
            self.is_closed = True
            raise
    
    def send(self, value):
        """Send value to generator"""
        if self.is_closed:
            raise StopIteration
        
        self.sent_values.append(value)
        try:
            result = self.generator.send(value)
            self.yielded_values.append(result)
            return result
        except StopIteration:
            self.is_closed = True
            raise
    
    def close(self):
        """Close the generator"""
        if not self.is_closed:
            self.generator.close()
            self.is_closed = True
    
    def throw(self, exc_type, exc_value=None, traceback=None):
        """Throw exception into generator"""
        return self.generator.throw(exc_type, exc_value, traceback)
    
    def map(self, func):
        """Map function over generator values"""
        def mapped_gen():
            for value in self:
                yield func(value)
        return mapped_gen()
    
    def filter(self, predicate):
        """Filter generator values"""
        def filtered_gen():
            for value in self:
                if predicate(value):
                    yield value
        return filtered_gen()
    
    def take(self, n):
        """Take first n values"""
        def take_gen():
            count = 0
            for value in self:
                if count >= n:
                    break
                yield value
                count += 1
        return take_gen()
    
    def to_list(self):
        """Convert generator to list"""
        return list(self)

class AsyncGenerator:
    """Async generator implementation"""
    
    def __init__(self, async_gen_func):
        self.async_gen_func = async_gen_func
    
    def __call__(self, *args, **kwargs):
        return self.async_gen_func(*args, **kwargs)
    
    async def to_list(self, async_gen):
        """Convert async generator to list"""
        result = []
        async for item in async_gen:
            result.append(item)
        return result
    
    async def map(self, async_gen, func):
        """Map function over async generator"""
        async for item in async_gen:
            yield func(item)
    
    async def filter(self, async_gen, predicate):
        """Filter async generator values"""
        async for item in async_gen:
            if predicate(item):
                yield item

class PatternMatcher:
    """Pattern matching system for Kaede"""
    
    def __init__(self):
        self.patterns = []
    
    def match(self, value):
        """Match value against patterns"""
        for pattern, action in self.patterns:
            if self._matches_pattern(value, pattern):
                return action(value)
        return None
    
    def case(self, pattern, action):
        """Add a pattern-action pair"""
        self.patterns.append((pattern, action))
        return self
    
    def _matches_pattern(self, value, pattern):
        """Check if value matches pattern"""
        if pattern == '_':  # Wildcard
            return True
        elif isinstance(pattern, type):
            return isinstance(value, pattern)
        elif isinstance(pattern, (list, tuple)):
            if not isinstance(value, type(pattern)):
                return False
            if len(value) != len(pattern):
                return False
            return all(self._matches_pattern(v, p) for v, p in zip(value, pattern))
        elif isinstance(pattern, dict):
            if not isinstance(value, dict):
                return False
            return all(key in value and self._matches_pattern(value[key], pat) 
                      for key, pat in pattern.items())
        else:
            return value == pattern

class KaedeMacro:
    """Macro system for code generation"""
    
    def __init__(self, name: str, template: str):
        self.name = name
        self.template = template
        self.parameters = []
    
    def expand(self, **kwargs):
        """Expand macro with given parameters"""
        code = self.template
        for key, value in kwargs.items():
            placeholder = f"${{{key}}}"
            code = code.replace(placeholder, str(value))
        return code
    
    def add_parameter(self, name: str, default_value=None):
        """Add parameter to macro"""
        self.parameters.append((name, default_value))

class MacroProcessor:
    """Process and expand macros in code"""
    
    def __init__(self):
        self.macros = {}
    
    def define_macro(self, name: str, template: str):
        """Define a new macro"""
        self.macros[name] = KaedeMacro(name, template)
        return self.macros[name]
    
    def expand_macros(self, code: str):
        """Expand all macros in code"""
        # Simple macro expansion - in real implementation would use proper parsing
        for name, macro in self.macros.items():
            pattern = f"@{name}"
            if pattern in code:
                code = code.replace(pattern, macro.expand())
        return code

class MetaClass:
    """Metaclass for Kaede classes"""
    
    def __init__(self, name: str, bases: Tuple, namespace: Dict):
        self.name = name
        self.bases = bases
        self.namespace = namespace
        self.instances = weakref.WeakSet()
        self.creation_time = time.time()
    
    def __call__(self, *args, **kwargs):
        """Create instance of metaclass"""
        instance = object.__new__(type(self.name, self.bases, self.namespace))
        if hasattr(instance, '__init__'):
            instance.__init__(*args, **kwargs)
        self.instances.add(instance)
        return instance
    
    def get_instance_count(self):
        """Get number of active instances"""
        return len(self.instances)
    
    def get_instances(self):
        """Get all active instances"""
        return list(self.instances)

class ReflectionUtils:
    """Reflection and introspection utilities"""
    
    @staticmethod
    def get_function_signature(func):
        """Get function signature information"""
        sig = inspect.signature(func)
        return {
            'name': func.__name__,
            'parameters': [
                {
                    'name': param.name,
                    'annotation': param.annotation,
                    'default': param.default if param.default != inspect.Parameter.empty else None,
                    'kind': param.kind.name
                }
                for param in sig.parameters.values()
            ],
            'return_annotation': sig.return_annotation
        }
    
    @staticmethod
    def get_class_info(cls):
        """Get class information"""
        return {
            'name': cls.__name__,
            'bases': [base.__name__ for base in cls.__bases__],
            'methods': [name for name, method in inspect.getmembers(cls, inspect.isfunction)],
            'attributes': [name for name in dir(cls) if not name.startswith('_')],
            'docstring': cls.__doc__,
            'module': cls.__module__
        }
    
    @staticmethod
    def get_source_code(obj):
        """Get source code of object"""
        try:
            return inspect.getsource(obj)
        except:
            return None
    
    @staticmethod
    def call_with_introspection(func, *args, **kwargs):
        """Call function with detailed introspection"""
        start_time = time.perf_counter()
        
        # Get memory usage before
        gc.collect()
        mem_before = sum(sys.getsizeof(obj) for obj in gc.get_objects())
        
        try:
            result = func(*args, **kwargs)
            success = True
            exception = None
        except Exception as e:
            result = None
            success = False
            exception = e
        
        end_time = time.perf_counter()
        
        # Get memory usage after
        gc.collect()
        mem_after = sum(sys.getsizeof(obj) for obj in gc.get_objects())
        
        return {
            'result': result,
            'success': success,
            'exception': exception,
            'execution_time': end_time - start_time,
            'memory_delta': mem_after - mem_before,
            'function_info': ReflectionUtils.get_function_signature(func)
        }

class PerformanceProfiler:
    """Performance profiler for Kaede code"""
    
    def __init__(self):
        self.profiles = {}
        self.active_profile = None
    
    def start_profiling(self, name: str = "default"):
        """Start profiling session"""
        import cProfile
        self.active_profile = name
        self.profiles[name] = cProfile.Profile()
        self.profiles[name].enable()
    
    def stop_profiling(self):
        """Stop active profiling session"""
        if self.active_profile and self.active_profile in self.profiles:
            self.profiles[self.active_profile].disable()
    
    def get_profile_stats(self, name: str = None):
        """Get profiling statistics"""
        profile_name = name or self.active_profile
        if profile_name not in self.profiles:
            return None
        
        import pstats
        import io
        
        profile = self.profiles[profile_name]
        stats_stream = io.StringIO()
        stats = pstats.Stats(profile, stream=stats_stream)
        stats.sort_stats('cumulative')
        stats.print_stats()
        
        return stats_stream.getvalue()
    
    @contextmanager
    def profile(self, name: str = "context"):
        """Context manager for profiling"""
        self.start_profiling(name)
        try:
            yield
        finally:
            self.stop_profiling()

class DSLBuilder:
    """Domain-Specific Language builder"""
    
    def __init__(self, name: str):
        self.name = name
        self.keywords = {}
        self.operators = {}
        self.syntax_rules = []
        self.semantic_actions = {}
    
    def add_keyword(self, keyword: str, action: Callable):
        """Add keyword to DSL"""
        self.keywords[keyword] = action
    
    def add_operator(self, operator: str, precedence: int, action: Callable):
        """Add operator to DSL"""
        self.operators[operator] = {
            'precedence': precedence,
            'action': action
        }
    
    def add_syntax_rule(self, pattern: str, action: Callable):
        """Add syntax rule to DSL"""
        self.syntax_rules.append((pattern, action))
    
    def parse_and_execute(self, code: str):
        """Parse and execute DSL code"""
        # Simple implementation - real DSL would need proper parser
        lines = code.strip().split('\n')
        results = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check keywords
            for keyword, action in self.keywords.items():
                if line.startswith(keyword):
                    args = line[len(keyword):].strip()
                    result = action(args)
                    results.append(result)
                    break
        
        return results

class CodeAnalyzer:
    """Static code analysis for Kaede"""
    
    def __init__(self):
        self.metrics = {}
        self.issues = []
    
    def analyze_function(self, func):
        """Analyze function complexity and quality"""
        source = ReflectionUtils.get_source_code(func)
        if not source:
            return None
        
        # Parse source code
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            self.issues.append(f"Syntax error in {func.__name__}: {e}")
            return None
        
        # Calculate metrics
        complexity = self._calculate_complexity(tree)
        line_count = len(source.split('\n'))
        
        metrics = {
            'function_name': func.__name__,
            'line_count': line_count,
            'cyclomatic_complexity': complexity,
            'parameter_count': len(inspect.signature(func).parameters)
        }
        
        # Check for issues
        if complexity > 10:
            self.issues.append(f"High complexity in {func.__name__}: {complexity}")
        if line_count > 50:
            self.issues.append(f"Long function {func.__name__}: {line_count} lines")
        
        self.metrics[func.__name__] = metrics
        return metrics
    
    def _calculate_complexity(self, tree):
        """Calculate cyclomatic complexity"""
        complexity = 1  # Base complexity
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.While, ast.For, ast.With)):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1
        
        return complexity
    
    def get_report(self):
        """Get analysis report"""
        return {
            'metrics': self.metrics,
            'issues': self.issues,
            'summary': {
                'total_functions': len(self.metrics),
                'total_issues': len(self.issues),
                'average_complexity': sum(m['cyclomatic_complexity'] for m in self.metrics.values()) / len(self.metrics) if self.metrics else 0
            }
        }

class KaedeAdvancedFeatures:
    """Main class providing access to all advanced features"""
    
    def __init__(self):
        self.decorators = {
            'memoize': MemoizeDecorator,
            'timing': TimingDecorator,
            'retry': RetryDecorator
        }
        
        self.pattern_matcher = PatternMatcher()
        self.macro_processor = MacroProcessor()
        self.profiler = PerformanceProfiler()
        self.code_analyzer = CodeAnalyzer()
        self.dsl_builders = {}
    
    def create_decorator(self, decorator_type: str, **kwargs):
        """Create decorator of specified type"""
        if decorator_type in self.decorators:
            return lambda func: self.decorators[decorator_type](func, **kwargs)
        raise ValueError(f"Unknown decorator type: {decorator_type}")
    
    def create_generator(self, func):
        """Create enhanced generator"""
        return KaedeGenerator(func)
    
    def create_async_generator(self, func):
        """Create async generator"""
        return AsyncGenerator(func)
    
    def create_pattern_matcher(self):
        """Create new pattern matcher"""
        return PatternMatcher()
    
    def create_dsl(self, name: str):
        """Create new domain-specific language"""
        dsl = DSLBuilder(name)
        self.dsl_builders[name] = dsl
        return dsl
    
    def get_dsl(self, name: str):
        """Get existing DSL"""
        return self.dsl_builders.get(name)
    
    def analyze_code(self, obj):
        """Analyze code object"""
        return self.code_analyzer.analyze_function(obj)
    
    def profile_code(self, func, *args, **kwargs):
        """Profile code execution"""
        with self.profiler.profile():
            return func(*args, **kwargs)

# Global instance
advanced_features = KaedeAdvancedFeatures()

def get_advanced_features():
    """Get the advanced features instance"""
    return advanced_features

# Export main classes and functions
__all__ = [
    'KaedeAdvancedFeatures', 'get_advanced_features',
    'KaedeDecorator', 'MemoizeDecorator', 'TimingDecorator', 'RetryDecorator',
    'KaedeGenerator', 'EnhancedGenerator', 'AsyncGenerator',
    'PatternMatcher', 'KaedeMacro', 'MacroProcessor',
    'MetaClass', 'ReflectionUtils', 'PerformanceProfiler',
    'DSLBuilder', 'CodeAnalyzer', 'KaedeType', 'TypeAnnotation'
] 
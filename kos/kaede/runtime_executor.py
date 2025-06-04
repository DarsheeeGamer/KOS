"""
Kaede Runtime Executor
=====================

High-performance runtime executor supporting:
- Bytecode interpretation with optimizations
- Just-In-Time (JIT) compilation 
- Native code execution
- Call stack management
- Exception handling
- Async/await support
- Profiling and optimization
"""

import sys
import time
import threading
import asyncio
import struct
import ctypes
import dis
import gc
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass
from collections import deque
from enum import Enum

from .compiler import Opcode, Instruction, Module, Function
from .memory_manager import memory_manager, KaedeMemoryManager
from .exceptions import *

class ExecutionMode(Enum):
    """Execution modes."""
    BYTECODE = "bytecode"
    JIT = "jit"
    NATIVE = "native"
    HYBRID = "hybrid"

class CallFrame:
    """Represents a call frame on the execution stack."""
    
    def __init__(self, function: Function, locals_dict: Dict[str, Any] = None):
        self.function = function
        self.locals = locals_dict or {}
        self.stack: List[Any] = []
        self.pc = 0  # Program counter
        self.exception_handlers: List[Tuple[int, int, int]] = []  # (start, end, handler)
        self.line_number = 1
        
    def push(self, value: Any):
        """Push value onto the stack."""
        self.stack.append(value)
    
    def pop(self) -> Any:
        """Pop value from the stack."""
        if not self.stack:
            raise RuntimeError("Stack underflow")
        return self.stack.pop()
    
    def peek(self, depth: int = 0) -> Any:
        """Peek at stack value without popping."""
        if len(self.stack) <= depth:
            raise RuntimeError("Stack underflow")
        return self.stack[-(depth + 1)]
    
    def get_local(self, name: str) -> Any:
        """Get local variable."""
        if name not in self.locals:
            raise NameError(f"Local variable '{name}' not found")
        return self.locals[name]
    
    def set_local(self, name: str, value: Any):
        """Set local variable."""
        self.locals[name] = value

@dataclass
class ExecutionState:
    """Current execution state."""
    mode: ExecutionMode
    frames: List[CallFrame]
    globals: Dict[str, Any]
    exception: Optional[Exception] = None
    running: bool = True
    result: Any = None

class JITCompiler:
    """Just-In-Time compiler for hot code paths."""
    
    def __init__(self):
        self.hot_functions: Dict[str, int] = {}  # function_name -> call_count
        self.compiled_functions: Dict[str, Callable] = {}
        self.compilation_threshold = 100
        
    def should_compile(self, function_name: str) -> bool:
        """Check if function should be JIT compiled."""
        self.hot_functions[function_name] = self.hot_functions.get(function_name, 0) + 1
        return self.hot_functions[function_name] >= self.compilation_threshold
    
    def compile_function(self, function: Function) -> Callable:
        """Compile function to native code."""
        # Simplified JIT compilation - in reality this would generate machine code
        def jit_wrapper(*args, **kwargs):
            # This would execute optimized native code
            return self._execute_optimized(function, args, kwargs)
        
        self.compiled_functions[function.name] = jit_wrapper
        return jit_wrapper
    
    def _execute_optimized(self, function: Function, args: Tuple, kwargs: Dict) -> Any:
        """Execute optimized version of function."""
        # Placeholder for optimized execution
        # In a real implementation, this would execute compiled machine code
        return None

class ProfilerData:
    """Profiling data collection."""
    
    def __init__(self):
        self.function_calls: Dict[str, int] = {}
        self.execution_times: Dict[str, float] = {}
        self.instruction_counts: Dict[Opcode, int] = {}
        self.memory_allocations: int = 0
        self.gc_collections: int = 0
        
    def record_function_call(self, function_name: str, execution_time: float):
        """Record function call statistics."""
        self.function_calls[function_name] = self.function_calls.get(function_name, 0) + 1
        self.execution_times[function_name] = self.execution_times.get(function_name, 0.0) + execution_time
    
    def record_instruction(self, opcode: Opcode):
        """Record instruction execution."""
        self.instruction_counts[opcode] = self.instruction_counts.get(opcode, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get profiling statistics."""
        return {
            'function_calls': dict(self.function_calls),
            'execution_times': dict(self.execution_times),
            'instruction_counts': {op.name: count for op, count in self.instruction_counts.items()},
            'memory_allocations': self.memory_allocations,
            'gc_collections': self.gc_collections
        }

class KaedeRuntimeExecutor:
    """High-performance runtime executor for Kaede."""
    
    def __init__(self, memory_manager: KaedeMemoryManager = None):
        self.memory_manager = memory_manager or memory_manager
        self.execution_mode = ExecutionMode.BYTECODE
        self.jit_compiler = JITCompiler()
        self.profiler = ProfilerData()
        
        # Global state
        self.globals: Dict[str, Any] = {}
        self.modules: Dict[str, Module] = {}
        
        # Execution stack
        self.call_stack: List[CallFrame] = []
        self.max_stack_depth = 1000
        
        # Built-in functions
        self._init_builtins()
        
        # Exception handling
        self.exception_stack: List[Exception] = []
        
        # Async support
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None
        self.coroutines: List[Any] = []
        
        # Threading support
        self.lock = threading.RLock()
        
    def _init_builtins(self):
        """Initialize built-in functions and constants."""
        self.globals.update({
            'print': self._builtin_print,
            'len': self._builtin_len,
            'range': self._builtin_range,
            'int': self._builtin_int,
            'float': self._builtin_float,
            'str': self._builtin_str,
            'bool': self._builtin_bool,
            'list': self._builtin_list,
            'dict': self._builtin_dict,
            'True': True,
            'False': False,
            'None': None,
        })
    
    def execute_module(self, module: Module, mode: ExecutionMode = None) -> Any:
        """Execute a compiled module."""
        if mode:
            self.execution_mode = mode
            
        self.modules[module.name] = module
        
        # Find main function or execute module initialization
        main_function = module.functions.get('main') or module.functions.get('__init__')
        if main_function:
            return self.execute_function(main_function, [])
        else:
            # Execute module-level code
            return self._execute_module_init(module)
    
    def execute_function(self, function: Function, args: List[Any]) -> Any:
        """Execute a function."""
        with self.lock:
            start_time = time.time()
            
            try:
                # Check for JIT compilation
                if self.execution_mode in [ExecutionMode.JIT, ExecutionMode.HYBRID]:
                    if self.jit_compiler.should_compile(function.name):
                        compiled_func = self.jit_compiler.compile_function(function)
                        result = compiled_func(*args)
                        execution_time = time.time() - start_time
                        self.profiler.record_function_call(function.name, execution_time)
                        return result
                
                # Create call frame
                frame = CallFrame(function)
                
                # Set up parameters
                for i, param_name in enumerate(function.parameters):
                    if i < len(args):
                        frame.set_local(param_name, args[i])
                    else:
                        frame.set_local(param_name, None)
                
                # Push frame onto call stack
                if len(self.call_stack) >= self.max_stack_depth:
                    raise RecursionError("Maximum recursion depth exceeded")
                
                self.call_stack.append(frame)
                
                try:
                    # Execute function
                    if self.execution_mode == ExecutionMode.BYTECODE:
                        result = self._execute_bytecode(frame)
                    elif self.execution_mode == ExecutionMode.NATIVE:
                        result = self._execute_native(frame)
                    else:
                        result = self._execute_bytecode(frame)  # Default to bytecode
                    
                    execution_time = time.time() - start_time
                    self.profiler.record_function_call(function.name, execution_time)
                    return result
                    
                finally:
                    # Pop frame from call stack
                    if self.call_stack:
                        self.call_stack.pop()
                        
            except Exception as e:
                execution_time = time.time() - start_time
                self.profiler.record_function_call(function.name, execution_time)
                self._handle_exception(e)
                raise
    
    def _execute_bytecode(self, frame: CallFrame) -> Any:
        """Execute bytecode instructions."""
        function = frame.function
        
        # Get bytecode from basic blocks
        instructions = []
        for block in function.basic_blocks:
            instructions.extend(block.instructions)
        
        frame.pc = 0
        while frame.pc < len(instructions):
            instruction = instructions[frame.pc]
            self.profiler.record_instruction(instruction.opcode)
            
            try:
                self._execute_instruction(frame, instruction)
                frame.pc += 1
            except ReturnException as e:
                return e.value
            except BreakException:
                # Find matching loop end
                self._handle_break(frame)
            except ContinueException:
                # Find matching loop start
                self._handle_continue(frame)
            except Exception as e:
                self._handle_exception(e)
                break
        
        return None
    
    def _execute_instruction(self, frame: CallFrame, instruction: Instruction):
        """Execute a single bytecode instruction."""
        opcode = instruction.opcode
        operand = instruction.operand
        
        if opcode == Opcode.LOAD_CONST:
            frame.push(operand)
            
        elif opcode == Opcode.LOAD_VAR:
            if operand in frame.locals:
                frame.push(frame.locals[operand])
            elif operand in self.globals:
                frame.push(self.globals[operand])
            else:
                raise NameError(f"Variable '{operand}' not found")
                
        elif opcode == Opcode.STORE_VAR:
            value = frame.pop()
            frame.set_local(operand, value)
            
        elif opcode == Opcode.DUP:
            frame.push(frame.peek())
            
        elif opcode == Opcode.POP:
            frame.pop()
            
        elif opcode == Opcode.SWAP:
            a = frame.pop()
            b = frame.pop()
            frame.push(a)
            frame.push(b)
            
        # Arithmetic operations
        elif opcode == Opcode.ADD:
            b = frame.pop()
            a = frame.pop()
            frame.push(a + b)
            
        elif opcode == Opcode.SUB:
            b = frame.pop()
            a = frame.pop()
            frame.push(a - b)
            
        elif opcode == Opcode.MUL:
            b = frame.pop()
            a = frame.pop()
            frame.push(a * b)
            
        elif opcode == Opcode.DIV:
            b = frame.pop()
            a = frame.pop()
            if b == 0:
                raise ZeroDivisionError("Division by zero")
            frame.push(a / b)
            
        elif opcode == Opcode.MOD:
            b = frame.pop()
            a = frame.pop()
            frame.push(a % b)
            
        elif opcode == Opcode.POW:
            b = frame.pop()
            a = frame.pop()
            frame.push(a ** b)
            
        elif opcode == Opcode.NEG:
            a = frame.pop()
            frame.push(-a)
            
        # Comparison operations
        elif opcode == Opcode.EQ:
            b = frame.pop()
            a = frame.pop()
            frame.push(a == b)
            
        elif opcode == Opcode.NE:
            b = frame.pop()
            a = frame.pop()
            frame.push(a != b)
            
        elif opcode == Opcode.LT:
            b = frame.pop()
            a = frame.pop()
            frame.push(a < b)
            
        elif opcode == Opcode.LE:
            b = frame.pop()
            a = frame.pop()
            frame.push(a <= b)
            
        elif opcode == Opcode.GT:
            b = frame.pop()
            a = frame.pop()
            frame.push(a > b)
            
        elif opcode == Opcode.GE:
            b = frame.pop()
            a = frame.pop()
            frame.push(a >= b)
            
        # Logical operations
        elif opcode == Opcode.LOGICAL_AND:
            b = frame.pop()
            a = frame.pop()
            frame.push(a and b)
            
        elif opcode == Opcode.LOGICAL_OR:
            b = frame.pop()
            a = frame.pop()
            frame.push(a or b)
            
        elif opcode == Opcode.LOGICAL_NOT:
            a = frame.pop()
            frame.push(not a)
            
        # Control flow
        elif opcode == Opcode.JUMP:
            frame.pc = operand - 1  # -1 because pc will be incremented
            
        elif opcode == Opcode.JUMP_IF_TRUE:
            condition = frame.pop()
            if condition:
                frame.pc = operand - 1
                
        elif opcode == Opcode.JUMP_IF_FALSE:
            condition = frame.pop()
            if not condition:
                frame.pc = operand - 1
                
        elif opcode == Opcode.CALL:
            # Call function
            args_count = operand
            args = []
            for _ in range(args_count):
                args.insert(0, frame.pop())
            
            func = frame.pop()
            if callable(func):
                result = func(*args)
                frame.push(result)
            else:
                raise TypeError(f"'{type(func).__name__}' object is not callable")
                
        elif opcode == Opcode.RETURN:
            value = frame.pop() if frame.stack else None
            raise ReturnException(value)
            
        # Object operations
        elif opcode == Opcode.NEW_OBJECT:
            obj_type = frame.pop()
            args_count = operand or 0
            args = []
            for _ in range(args_count):
                args.insert(0, frame.pop())
            
            obj = obj_type(*args)
            frame.push(obj)
            
        elif opcode == Opcode.NEW_ARRAY:
            size = frame.pop()
            array = [None] * size
            frame.push(array)
            
        elif opcode == Opcode.NEW_LIST:
            size = operand or 0
            items = []
            for _ in range(size):
                items.insert(0, frame.pop())
            frame.push(items)
            
        elif opcode == Opcode.NEW_DICT:
            size = operand or 0
            dict_obj = {}
            for _ in range(size):
                value = frame.pop()
                key = frame.pop()
                dict_obj[key] = value
            frame.push(dict_obj)
            
        elif opcode == Opcode.GET_ATTR:
            obj = frame.pop()
            attr_name = operand
            if hasattr(obj, attr_name):
                frame.push(getattr(obj, attr_name))
            else:
                raise AttributeError(f"'{type(obj).__name__}' object has no attribute '{attr_name}'")
                
        elif opcode == Opcode.SET_ATTR:
            value = frame.pop()
            obj = frame.pop()
            attr_name = operand
            setattr(obj, attr_name, value)
            
        elif opcode == Opcode.GET_ITEM:
            index = frame.pop()
            obj = frame.pop()
            try:
                frame.push(obj[index])
            except (KeyError, IndexError) as e:
                raise e
                
        elif opcode == Opcode.SET_ITEM:
            value = frame.pop()
            index = frame.pop()
            obj = frame.pop()
            try:
                obj[index] = value
            except (KeyError, IndexError) as e:
                raise e
                
        # Memory operations
        elif opcode == Opcode.ALLOC:
            size = frame.pop()
            addr = self.memory_manager.malloc(size)
            frame.push(addr)
            
        elif opcode == Opcode.FREE:
            addr = frame.pop()
            self.memory_manager.free(addr)
            
        # Exception handling
        elif opcode == Opcode.THROW:
            exception = frame.pop()
            raise exception
            
        elif opcode == Opcode.NOP:
            pass  # No operation
            
        elif opcode == Opcode.HALT:
            raise SystemExit(0)
            
        else:
            raise NotImplementedError(f"Opcode {opcode} not implemented")
    
    def _execute_native(self, frame: CallFrame) -> Any:
        """Execute native code (placeholder)."""
        # In a real implementation, this would execute compiled machine code
        # For now, fall back to bytecode execution
        return self._execute_bytecode(frame)
    
    def _execute_module_init(self, module: Module) -> Any:
        """Execute module initialization code."""
        # Execute global variable initializations and module-level code
        return None
    
    def _handle_exception(self, exception: Exception):
        """Handle exception during execution."""
        # Find exception handler in current frame
        if self.call_stack:
            frame = self.call_stack[-1]
            for start, end, handler in frame.exception_handlers:
                if start <= frame.pc <= end:
                    frame.pc = handler
                    frame.push(exception)
                    return
        
        # If no handler found, propagate exception
        self.exception_stack.append(exception)
        raise exception
    
    def _handle_break(self, frame: CallFrame):
        """Handle break statement."""
        # Find matching loop end (simplified)
        # In a real implementation, this would use proper loop tracking
        pass
    
    def _handle_continue(self, frame: CallFrame):
        """Handle continue statement."""
        # Find matching loop start (simplified)
        # In a real implementation, this would use proper loop tracking
        pass
    
    # Built-in function implementations
    def _builtin_print(self, *args, **kwargs):
        """Built-in print function."""
        print(*args, **kwargs)
    
    def _builtin_len(self, obj):
        """Built-in len function."""
        return len(obj)
    
    def _builtin_range(self, *args):
        """Built-in range function."""
        return range(*args)
    
    def _builtin_int(self, obj=None, base=10):
        """Built-in int function."""
        if obj is None:
            return 0
        return int(obj, base) if isinstance(obj, str) else int(obj)
    
    def _builtin_float(self, obj=None):
        """Built-in float function."""
        return float(obj) if obj is not None else 0.0
    
    def _builtin_str(self, obj=None):
        """Built-in str function."""
        return str(obj) if obj is not None else ""
    
    def _builtin_bool(self, obj=None):
        """Built-in bool function."""
        return bool(obj) if obj is not None else False
    
    def _builtin_list(self, iterable=None):
        """Built-in list function."""
        return list(iterable) if iterable else []
    
    def _builtin_dict(self, *args, **kwargs):
        """Built-in dict function."""
        if args:
            return dict(args[0])
        return dict(**kwargs)
    
    def get_profiling_data(self) -> Dict[str, Any]:
        """Get profiling data."""
        stats = self.profiler.get_stats()
        stats.update({
            'memory_info': self.memory_manager.get_memory_info(),
            'call_stack_depth': len(self.call_stack),
            'modules_loaded': len(self.modules),
            'jit_compiled_functions': len(self.jit_compiler.compiled_functions)
        })
        return stats
    
    def set_execution_mode(self, mode: ExecutionMode):
        """Set execution mode."""
        self.execution_mode = mode
    
    def reset(self):
        """Reset executor state."""
        self.call_stack.clear()
        self.exception_stack.clear()
        self.globals.clear()
        self._init_builtins()
        self.profiler = ProfilerData()

class ReturnException(Exception):
    """Exception used for function returns."""
    
    def __init__(self, value: Any):
        self.value = value
        super().__init__()

class BreakException(Exception):
    """Exception used for break statements."""
    pass

class ContinueException(Exception):
    """Exception used for continue statements."""
    pass

# Global executor instance
executor = KaedeRuntimeExecutor()

# Convenience functions
def execute_module(module: Module, mode: ExecutionMode = None) -> Any:
    """Execute a module."""
    return executor.execute_module(module, mode)

def execute_function(function: Function, args: List[Any]) -> Any:
    """Execute a function."""
    return executor.execute_function(function, args)

def get_profiling_data() -> Dict[str, Any]:
    """Get profiling data."""
    return executor.get_profiling_data()

def set_execution_mode(mode: ExecutionMode):
    """Set execution mode."""
    executor.set_execution_mode(mode) 
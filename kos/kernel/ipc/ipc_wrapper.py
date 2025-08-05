#!/usr/bin/env python3
"""
KOS IPC Python Bindings
Comprehensive Inter-Process Communication wrapper for KOS kernel IPC functionality
Supports pipes, shared memory, message queues, semaphores, mutexes, condition variables, and signals
"""

import ctypes
import ctypes.util
import os
import sys
import threading
import time
from typing import Optional, Any, Tuple, List
from enum import IntEnum
import signal as py_signal

# Find and load the IPC library
def _find_ipc_library():
    """Find the KOS IPC library"""
    possible_paths = [
        "./libkos_ipc.so",
        "/usr/local/lib/libkos_ipc.so",
        "/usr/lib/libkos_ipc.so",
        os.path.join(os.path.dirname(__file__), "libkos_ipc.so")
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Try to find using ctypes.util
    lib_path = ctypes.util.find_library("kos_ipc")
    if lib_path:
        return lib_path
    
    raise ImportError("Could not find libkos_ipc.so library")

# Constants
class IPCError(IntEnum):
    SUCCESS = 0
    ERROR = -1
    TIMEOUT = -2
    INVALID_PARAM = -3
    RESOURCE_BUSY = -4
    NO_MEMORY = -5

class IPCException(Exception):
    """Base exception for IPC operations"""
    pass

class IPCTimeoutException(IPCException):
    """Timeout exception for IPC operations"""
    pass

class IPCResourceBusyException(IPCException):
    """Resource busy exception for IPC operations"""
    pass

# Load library
try:
    _lib_path = _find_ipc_library()
    _lib = ctypes.CDLL(_lib_path)
except ImportError:
    # For development/testing when library isn't built yet
    _lib = None
    print("Warning: KOS IPC library not found, using mock implementation")

# Structure definitions
class PipeStruct(ctypes.Structure):
    _fields_ = [
        ("read_fd", ctypes.c_int),
        ("write_fd", ctypes.c_int),
        ("name", ctypes.c_char * 256),
        ("is_named", ctypes.c_int),
        ("buffer_size", ctypes.c_size_t),
        ("mutex", ctypes.c_void_p)  # pthread_mutex_t placeholder
    ]

class ShmStruct(ctypes.Structure):
    _fields_ = [
        ("shm_id", ctypes.c_int),
        ("key", ctypes.c_int),
        ("addr", ctypes.c_void_p),
        ("size", ctypes.c_size_t),
        ("flags", ctypes.c_int),
        ("mutex", ctypes.c_void_p),
        ("name", ctypes.c_char * 256)
    ]

class MsgQueueStruct(ctypes.Structure):
    _fields_ = [
        ("msqid", ctypes.c_int),
        ("key", ctypes.c_int),
        ("posix_mq", ctypes.c_int),
        ("name", ctypes.c_char * 256),
        ("is_posix", ctypes.c_int),
        ("attr", ctypes.c_void_p)  # mq_attr placeholder
    ]

class SemaphoreStruct(ctypes.Structure):
    _fields_ = [
        ("semid", ctypes.c_int),
        ("key", ctypes.c_int),
        ("posix_sem", ctypes.c_void_p),
        ("name", ctypes.c_char * 256),
        ("is_posix", ctypes.c_int),
        ("value", ctypes.c_int),
        ("max_value", ctypes.c_int)
    ]

class MutexStruct(ctypes.Structure):
    _fields_ = [
        ("mutex", ctypes.c_void_p),  # pthread_mutex_t placeholder
        ("attr", ctypes.c_void_p),   # pthread_mutexattr_t placeholder
        ("initialized", ctypes.c_int),
        ("owner", ctypes.c_int)
    ]

class CondVarStruct(ctypes.Structure):
    _fields_ = [
        ("cond", ctypes.c_void_p),   # pthread_cond_t placeholder
        ("attr", ctypes.c_void_p),   # pthread_condattr_t placeholder
        ("initialized", ctypes.c_int)
    ]

# Function prototypes setup
def _setup_function_prototypes():
    """Setup C function prototypes"""
    if not _lib:
        return
    
    # Pipe functions
    _lib.kos_pipe_create.argtypes = [ctypes.POINTER(PipeStruct)]
    _lib.kos_pipe_create.restype = ctypes.c_int
    
    _lib.kos_pipe_create_named.argtypes = [ctypes.POINTER(PipeStruct), ctypes.c_char_p]
    _lib.kos_pipe_create_named.restype = ctypes.c_int
    
    _lib.kos_pipe_read.argtypes = [ctypes.POINTER(PipeStruct), ctypes.c_void_p, ctypes.c_size_t]
    _lib.kos_pipe_read.restype = ctypes.c_int
    
    _lib.kos_pipe_write.argtypes = [ctypes.POINTER(PipeStruct), ctypes.c_void_p, ctypes.c_size_t]
    _lib.kos_pipe_write.restype = ctypes.c_int
    
    _lib.kos_pipe_destroy.argtypes = [ctypes.POINTER(PipeStruct)]
    _lib.kos_pipe_destroy.restype = ctypes.c_int
    
    # Shared memory functions
    _lib.kos_shm_create.argtypes = [ctypes.POINTER(ShmStruct), ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
    _lib.kos_shm_create.restype = ctypes.c_int
    
    _lib.kos_shm_attach.argtypes = [ctypes.POINTER(ShmStruct), ctypes.c_char_p]
    _lib.kos_shm_attach.restype = ctypes.c_int
    
    _lib.kos_shm_detach.argtypes = [ctypes.POINTER(ShmStruct)]
    _lib.kos_shm_detach.restype = ctypes.c_int
    
    _lib.kos_shm_destroy.argtypes = [ctypes.POINTER(ShmStruct)]
    _lib.kos_shm_destroy.restype = ctypes.c_int
    
    _lib.kos_shm_get_addr.argtypes = [ctypes.POINTER(ShmStruct)]
    _lib.kos_shm_get_addr.restype = ctypes.c_void_p
    
    _lib.kos_shm_lock.argtypes = [ctypes.POINTER(ShmStruct)]
    _lib.kos_shm_lock.restype = ctypes.c_int
    
    _lib.kos_shm_unlock.argtypes = [ctypes.POINTER(ShmStruct)]
    _lib.kos_shm_unlock.restype = ctypes.c_int
    
    # Message queue functions
    _lib.kos_msgqueue_create.argtypes = [ctypes.POINTER(MsgQueueStruct), ctypes.c_char_p, ctypes.c_int]
    _lib.kos_msgqueue_create.restype = ctypes.c_int
    
    _lib.kos_msgqueue_send.argtypes = [ctypes.POINTER(MsgQueueStruct), ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    _lib.kos_msgqueue_send.restype = ctypes.c_int
    
    _lib.kos_msgqueue_receive.argtypes = [ctypes.POINTER(MsgQueueStruct), ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_int)]
    _lib.kos_msgqueue_receive.restype = ctypes.c_int
    
    _lib.kos_msgqueue_destroy.argtypes = [ctypes.POINTER(MsgQueueStruct)]
    _lib.kos_msgqueue_destroy.restype = ctypes.c_int
    
    # Semaphore functions
    _lib.kos_semaphore_create.argtypes = [ctypes.POINTER(SemaphoreStruct), ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
    _lib.kos_semaphore_create.restype = ctypes.c_int
    
    _lib.kos_semaphore_wait.argtypes = [ctypes.POINTER(SemaphoreStruct), ctypes.c_int]
    _lib.kos_semaphore_wait.restype = ctypes.c_int
    
    _lib.kos_semaphore_post.argtypes = [ctypes.POINTER(SemaphoreStruct)]
    _lib.kos_semaphore_post.restype = ctypes.c_int
    
    _lib.kos_semaphore_get_value.argtypes = [ctypes.POINTER(SemaphoreStruct)]
    _lib.kos_semaphore_get_value.restype = ctypes.c_int
    
    _lib.kos_semaphore_destroy.argtypes = [ctypes.POINTER(SemaphoreStruct)]
    _lib.kos_semaphore_destroy.restype = ctypes.c_int
    
    # Mutex functions
    _lib.kos_mutex_init.argtypes = [ctypes.POINTER(MutexStruct), ctypes.c_int]
    _lib.kos_mutex_init.restype = ctypes.c_int
    
    _lib.kos_mutex_lock.argtypes = [ctypes.POINTER(MutexStruct)]
    _lib.kos_mutex_lock.restype = ctypes.c_int
    
    _lib.kos_mutex_try_lock.argtypes = [ctypes.POINTER(MutexStruct)]
    _lib.kos_mutex_try_lock.restype = ctypes.c_int
    
    _lib.kos_mutex_unlock.argtypes = [ctypes.POINTER(MutexStruct)]
    _lib.kos_mutex_unlock.restype = ctypes.c_int
    
    _lib.kos_mutex_destroy.argtypes = [ctypes.POINTER(MutexStruct)]
    _lib.kos_mutex_destroy.restype = ctypes.c_int
    
    # Condition variable functions
    _lib.kos_condvar_init.argtypes = [ctypes.POINTER(CondVarStruct), ctypes.c_int]
    _lib.kos_condvar_init.restype = ctypes.c_int
    
    _lib.kos_condvar_wait.argtypes = [ctypes.POINTER(CondVarStruct), ctypes.POINTER(MutexStruct)]
    _lib.kos_condvar_wait.restype = ctypes.c_int
    
    _lib.kos_condvar_timed_wait.argtypes = [ctypes.POINTER(CondVarStruct), ctypes.POINTER(MutexStruct), ctypes.c_int]
    _lib.kos_condvar_timed_wait.restype = ctypes.c_int
    
    _lib.kos_condvar_signal.argtypes = [ctypes.POINTER(CondVarStruct)]
    _lib.kos_condvar_signal.restype = ctypes.c_int
    
    _lib.kos_condvar_broadcast.argtypes = [ctypes.POINTER(CondVarStruct)]
    _lib.kos_condvar_broadcast.restype = ctypes.c_int
    
    _lib.kos_condvar_destroy.argtypes = [ctypes.POINTER(CondVarStruct)]
    _lib.kos_condvar_destroy.restype = ctypes.c_int
    
    # Signal functions
    _lib.kos_signal_register.argtypes = [ctypes.c_int, ctypes.c_void_p]
    _lib.kos_signal_register.restype = ctypes.c_int
    
    _lib.kos_signal_unregister.argtypes = [ctypes.c_int]
    _lib.kos_signal_unregister.restype = ctypes.c_int
    
    _lib.kos_signal_send.argtypes = [ctypes.c_int, ctypes.c_int]
    _lib.kos_signal_send.restype = ctypes.c_int
    
    _lib.kos_signal_block.argtypes = [ctypes.c_int]
    _lib.kos_signal_block.restype = ctypes.c_int
    
    _lib.kos_signal_unblock.argtypes = [ctypes.c_int]
    _lib.kos_signal_unblock.restype = ctypes.c_int

# Setup function prototypes
_setup_function_prototypes()

def _check_result(result: int, operation: str = "IPC operation"):
    """Check result and raise appropriate exception"""
    if result == IPCError.SUCCESS:
        return
    elif result == IPCError.TIMEOUT:
        raise IPCTimeoutException(f"{operation} timed out")
    elif result == IPCError.RESOURCE_BUSY:
        raise IPCResourceBusyException(f"{operation} resource busy")
    elif result == IPCError.INVALID_PARAM:
        raise IPCException(f"{operation} invalid parameter")
    elif result == IPCError.NO_MEMORY:
        raise IPCException(f"{operation} out of memory")
    else:
        raise IPCException(f"{operation} failed with error {result}")

class Pipe:
    """KOS Pipe wrapper"""
    
    def __init__(self, name: Optional[str] = None):
        self._pipe = PipeStruct()
        self._name = name
        
        if _lib:
            if name:
                result = _lib.kos_pipe_create_named(ctypes.byref(self._pipe), name.encode('utf-8'))
            else:
                result = _lib.kos_pipe_create(ctypes.byref(self._pipe))
            _check_result(result, "Pipe creation")
        else:
            # Mock implementation
            self._mock_data = []
    
    def read(self, size: int = 1024) -> bytes:
        """Read data from pipe"""
        if _lib:
            buffer = ctypes.create_string_buffer(size)
            result = _lib.kos_pipe_read(ctypes.byref(self._pipe), buffer, size)
            if result < 0:
                _check_result(result, "Pipe read")
            return buffer.raw[:result]
        else:
            # Mock implementation
            if self._mock_data:
                return self._mock_data.pop(0)
            return b""
    
    def write(self, data: bytes) -> int:
        """Write data to pipe"""
        if _lib:
            result = _lib.kos_pipe_write(ctypes.byref(self._pipe), data, len(data))
            if result < 0:
                _check_result(result, "Pipe write")
            return result
        else:
            # Mock implementation
            self._mock_data.append(data)
            return len(data)
    
    def close(self):
        """Close pipe"""
        if _lib:
            result = _lib.kos_pipe_destroy(ctypes.byref(self._pipe))
            _check_result(result, "Pipe close")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class SharedMemory:
    """KOS Shared Memory wrapper"""
    
    def __init__(self, name: str, size: int, create: bool = True):
        self._shm = ShmStruct()
        self._name = name
        self._size = size
        
        if _lib:
            if create:
                result = _lib.kos_shm_create(ctypes.byref(self._shm), name.encode('utf-8'), size, 0)
            else:
                result = _lib.kos_shm_attach(ctypes.byref(self._shm), name.encode('utf-8'))
            _check_result(result, "Shared memory creation/attachment")
        else:
            # Mock implementation
            self._mock_data = bytearray(size)
    
    def get_address(self) -> ctypes.c_void_p:
        """Get shared memory address"""
        if _lib:
            return _lib.kos_shm_get_addr(ctypes.byref(self._shm))
        else:
            return ctypes.cast(ctypes.pointer(ctypes.c_char_p(bytes(self._mock_data))), ctypes.c_void_p)
    
    def lock(self):
        """Lock shared memory mutex"""
        if _lib:
            result = _lib.kos_shm_lock(ctypes.byref(self._shm))
            _check_result(result, "Shared memory lock")
    
    def unlock(self):
        """Unlock shared memory mutex"""
        if _lib:
            result = _lib.kos_shm_unlock(ctypes.byref(self._shm))
            _check_result(result, "Shared memory unlock")
    
    def read(self, offset: int = 0, size: Optional[int] = None) -> bytes:
        """Read data from shared memory"""
        if size is None:
            size = self._size - offset
        
        if _lib:
            addr = self.get_address()
            if not addr:
                raise IPCException("Invalid shared memory address")
            
            # Create buffer and copy data
            buffer = ctypes.create_string_buffer(size)
            ctypes.memmove(buffer, ctypes.c_void_p(addr.value + offset), size)
            return buffer.raw
        else:
            return bytes(self._mock_data[offset:offset + size])
    
    def write(self, data: bytes, offset: int = 0):
        """Write data to shared memory"""
        if offset + len(data) > self._size:
            raise IPCException("Data too large for shared memory segment")
        
        if _lib:
            addr = self.get_address()
            if not addr:
                raise IPCException("Invalid shared memory address")
            
            ctypes.memmove(ctypes.c_void_p(addr.value + offset), data, len(data))
        else:
            self._mock_data[offset:offset + len(data)] = data
    
    def close(self):
        """Detach from shared memory"""
        if _lib:
            result = _lib.kos_shm_detach(ctypes.byref(self._shm))
            _check_result(result, "Shared memory detach")
    
    def destroy(self):
        """Destroy shared memory segment"""
        if _lib:
            result = _lib.kos_shm_destroy(ctypes.byref(self._shm))
            _check_result(result, "Shared memory destroy")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class MessageQueue:
    """KOS Message Queue wrapper"""
    
    def __init__(self, name: str, posix: bool = True):
        self._mq = MsgQueueStruct()
        self._name = name
        self._posix = posix
        
        if _lib:
            result = _lib.kos_msgqueue_create(ctypes.byref(self._mq), name.encode('utf-8'), 1 if posix else 0)
            _check_result(result, "Message queue creation")
        else:
            # Mock implementation
            self._mock_messages = []
    
    def send(self, message: bytes, priority: int = 0):
        """Send message to queue"""
        if _lib:
            result = _lib.kos_msgqueue_send(ctypes.byref(self._mq), message, len(message), priority)
            _check_result(result, "Message queue send")
        else:
            # Mock implementation
            self._mock_messages.append((message, priority))
    
    def receive(self, max_size: int = 8192) -> Tuple[bytes, int]:
        """Receive message from queue"""
        if _lib:
            buffer = ctypes.create_string_buffer(max_size)
            priority = ctypes.c_int()
            result = _lib.kos_msgqueue_receive(ctypes.byref(self._mq), buffer, max_size, ctypes.byref(priority))
            if result < 0:
                _check_result(result, "Message queue receive")
            return buffer.raw[:result], priority.value
        else:
            # Mock implementation
            if self._mock_messages:
                return self._mock_messages.pop(0)
            return b"", 0
    
    def close(self):
        """Close message queue"""
        if _lib:
            result = _lib.kos_msgqueue_destroy(ctypes.byref(self._mq))
            _check_result(result, "Message queue close")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Semaphore:
    """KOS Semaphore wrapper"""
    
    def __init__(self, name: str, value: int = 1, posix: bool = True):
        self._sem = SemaphoreStruct()
        self._name = name
        self._posix = posix
        
        if _lib:
            result = _lib.kos_semaphore_create(ctypes.byref(self._sem), name.encode('utf-8'), value, 1 if posix else 0)
            _check_result(result, "Semaphore creation")
        else:
            # Mock implementation
            self._mock_value = value
            self._mock_lock = threading.Semaphore(value)
    
    def wait(self, timeout_ms: int = -1):
        """Wait on semaphore (P operation)"""
        if _lib:
            result = _lib.kos_semaphore_wait(ctypes.byref(self._sem), timeout_ms)
            _check_result(result, "Semaphore wait")
        else:
            # Mock implementation
            timeout = None if timeout_ms < 0 else timeout_ms / 1000.0
            if not self._mock_lock.acquire(timeout=timeout):
                raise IPCTimeoutException("Semaphore wait timed out")
    
    def post(self):
        """Post to semaphore (V operation)"""
        if _lib:
            result = _lib.kos_semaphore_post(ctypes.byref(self._sem))
            _check_result(result, "Semaphore post")
        else:
            # Mock implementation
            self._mock_lock.release()
    
    def try_wait(self) -> bool:
        """Try to wait on semaphore (non-blocking)"""
        try:
            self.wait(0)
            return True
        except (IPCTimeoutException, IPCResourceBusyException):
            return False
    
    def get_value(self) -> int:
        """Get semaphore value"""
        if _lib:
            result = _lib.kos_semaphore_get_value(ctypes.byref(self._sem))
            if result < 0:
                _check_result(result, "Semaphore get value")
            return result
        else:
            # Mock implementation (approximate)
            return self._mock_value
    
    def close(self):
        """Close semaphore"""
        if _lib:
            result = _lib.kos_semaphore_destroy(ctypes.byref(self._sem))
            _check_result(result, "Semaphore close")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class Mutex:
    """KOS Mutex wrapper"""
    
    def __init__(self, shared: bool = False):
        self._mutex = MutexStruct()
        self._shared = shared
        
        if _lib:
            result = _lib.kos_mutex_init(ctypes.byref(self._mutex), 1 if shared else 0)
            _check_result(result, "Mutex initialization")
        else:
            # Mock implementation
            self._mock_lock = threading.Lock()
    
    def lock(self):
        """Lock mutex"""
        if _lib:
            result = _lib.kos_mutex_lock(ctypes.byref(self._mutex))
            _check_result(result, "Mutex lock")
        else:
            self._mock_lock.acquire()
    
    def try_lock(self) -> bool:
        """Try to lock mutex (non-blocking)"""
        if _lib:
            result = _lib.kos_mutex_try_lock(ctypes.byref(self._mutex))
            if result == IPCError.RESOURCE_BUSY:
                return False
            _check_result(result, "Mutex try lock")
            return True
        else:
            return self._mock_lock.acquire(blocking=False)
    
    def unlock(self):
        """Unlock mutex"""
        if _lib:
            result = _lib.kos_mutex_unlock(ctypes.byref(self._mutex))
            _check_result(result, "Mutex unlock")
        else:
            self._mock_lock.release()
    
    def close(self):
        """Destroy mutex"""
        if _lib:
            result = _lib.kos_mutex_destroy(ctypes.byref(self._mutex))
            _check_result(result, "Mutex destroy")
    
    def __enter__(self):
        self.lock()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unlock()

class ConditionVariable:
    """KOS Condition Variable wrapper"""
    
    def __init__(self, shared: bool = False):
        self._condvar = CondVarStruct()
        self._shared = shared
        
        if _lib:
            result = _lib.kos_condvar_init(ctypes.byref(self._condvar), 1 if shared else 0)
            _check_result(result, "Condition variable initialization")
        else:
            # Mock implementation
            self._mock_cond = threading.Condition()
    
    def wait(self, mutex: Mutex):
        """Wait on condition variable"""
        if _lib:
            result = _lib.kos_condvar_wait(ctypes.byref(self._condvar), ctypes.byref(mutex._mutex))
            _check_result(result, "Condition variable wait")
        else:
            with self._mock_cond:
                self._mock_cond.wait()
    
    def timed_wait(self, mutex: Mutex, timeout_ms: int) -> bool:
        """Timed wait on condition variable"""
        if _lib:
            result = _lib.kos_condvar_timed_wait(ctypes.byref(self._condvar), ctypes.byref(mutex._mutex), timeout_ms)
            if result == IPCError.TIMEOUT:
                return False
            _check_result(result, "Condition variable timed wait")
            return True
        else:
            with self._mock_cond:
                return self._mock_cond.wait(timeout=timeout_ms / 1000.0)
    
    def signal(self):
        """Signal condition variable"""
        if _lib:
            result = _lib.kos_condvar_signal(ctypes.byref(self._condvar))
            _check_result(result, "Condition variable signal")
        else:
            with self._mock_cond:
                self._mock_cond.notify()
    
    def broadcast(self):
        """Broadcast condition variable"""
        if _lib:
            result = _lib.kos_condvar_broadcast(ctypes.byref(self._condvar))
            _check_result(result, "Condition variable broadcast")
        else:
            with self._mock_cond:
                self._mock_cond.notify_all()
    
    def close(self):
        """Destroy condition variable"""
        if _lib:
            result = _lib.kos_condvar_destroy(ctypes.byref(self._condvar))
            _check_result(result, "Condition variable destroy")

class SignalHandler:
    """KOS Signal Handler wrapper"""
    
    _handlers = {}  # Global handler registry
    
    @classmethod
    def register(cls, signal_num: int, handler_func):
        """Register signal handler"""
        if _lib:
            # Convert Python function to C callback
            c_handler = ctypes.CFUNCTYPE(None, ctypes.c_int)(handler_func)
            cls._handlers[signal_num] = c_handler  # Keep reference
            result = _lib.kos_signal_register(signal_num, c_handler)
            _check_result(result, f"Signal {signal_num} registration")
        else:
            # Mock implementation using Python signal module
            py_signal.signal(signal_num, handler_func)
    
    @classmethod
    def unregister(cls, signal_num: int):
        """Unregister signal handler"""
        if _lib:
            result = _lib.kos_signal_unregister(signal_num)
            _check_result(result, f"Signal {signal_num} unregistration")
            if signal_num in cls._handlers:
                del cls._handlers[signal_num]
        else:
            # Mock implementation
            py_signal.signal(signal_num, py_signal.SIG_DFL)
    
    @classmethod
    def send(cls, pid: int, signal_num: int):
        """Send signal to process"""
        if _lib:
            result = _lib.kos_signal_send(pid, signal_num)
            _check_result(result, f"Signal {signal_num} send")
        else:
            # Mock implementation
            os.kill(pid, signal_num)
    
    @classmethod
    def block(cls, signal_num: int):
        """Block signal"""
        if _lib:
            result = _lib.kos_signal_block(signal_num)
            _check_result(result, f"Signal {signal_num} block")
        else:
            # Mock implementation - limited capability
            pass
    
    @classmethod
    def unblock(cls, signal_num: int):
        """Unblock signal"""
        if _lib:
            result = _lib.kos_signal_unblock(signal_num)
            _check_result(result, f"Signal {signal_num} unblock")
        else:
            # Mock implementation - limited capability
            pass

# Utility functions
def ipc_init():
    """Initialize IPC system"""
    if _lib and hasattr(_lib, 'kos_ipc_init'):
        result = _lib.kos_ipc_init()
        _check_result(result, "IPC initialization")

def ipc_cleanup():
    """Cleanup IPC system"""
    if _lib and hasattr(_lib, 'kos_ipc_cleanup'):
        result = _lib.kos_ipc_cleanup()
        _check_result(result, "IPC cleanup")

def generate_key(pathname: str, proj_id: int) -> int:
    """Generate IPC key"""
    if _lib and hasattr(_lib, 'kos_ipc_generate_key'):
        return _lib.kos_ipc_generate_key(pathname.encode('utf-8'), proj_id)
    else:
        # Mock implementation
        return hash(pathname + str(proj_id)) & 0x7FFFFFFF

# Context managers and utilities
class IPCManager:
    """Context manager for IPC operations"""
    
    def __init__(self):
        self._resources = []
    
    def __enter__(self):
        ipc_init()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close all managed resources
        for resource in reversed(self._resources):
            try:
                resource.close()
            except:
                pass
        ipc_cleanup()
    
    def manage(self, resource):
        """Add resource to be managed"""
        self._resources.append(resource)
        return resource

# Example usage and testing
if __name__ == "__main__":
    print("KOS IPC Python Bindings")
    print("Available classes:")
    print("  - Pipe: Anonymous and named pipes")
    print("  - SharedMemory: POSIX and System V shared memory")
    print("  - MessageQueue: POSIX and System V message queues")  
    print("  - Semaphore: POSIX and System V semaphores")
    print("  - Mutex: Process-shared mutexes")
    print("  - ConditionVariable: Process-shared condition variables")
    print("  - SignalHandler: Signal handling and management")
    
    # Simple test
    try:
        with IPCManager() as ipc:
            # Test pipe
            pipe = ipc.manage(Pipe())
            pipe.write(b"Hello, KOS IPC!")
            data = pipe.read()
            print(f"Pipe test: {data}")
            
            # Test semaphore
            sem = ipc.manage(Semaphore("test_sem", 1))
            sem.wait()
            print(f"Semaphore value: {sem.get_value()}")
            sem.post()
            
            print("Basic IPC tests completed successfully!")
            
    except Exception as e:
        print(f"IPC test failed: {e}")
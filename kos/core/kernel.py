"""
KOS Kernel Core

This module provides the central kernel functionality for KOS,
coordinating between different subsystems and managing system resources.
"""

import os
import sys
import time
import logging
import threading
import signal
import atexit
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.core.kernel')

# Kernel state
_kernel_state = {
    'running': False,
    'start_time': 0.0,
    'pid': os.getpid(),
    'threads': {},
    'subsystems': {},
    'resources': {},
    'shutdown_callbacks': []
}

# Locks
_kernel_lock = threading.RLock()
_resource_lock = threading.RLock()


class KernelException(Exception):
    """Base class for kernel exceptions"""
    pass


class ResourceUnavailableException(KernelException):
    """Exception raised when a resource is unavailable"""
    pass


class PermissionDeniedException(KernelException):
    """Exception raised when permission is denied"""
    pass


class SubsystemManager:
    """Manager for kernel subsystems"""
    
    @classmethod
    def register(cls, name: str, subsystem: Any) -> bool:
        """
        Register a subsystem
        
        Args:
            name: Subsystem name
            subsystem: Subsystem object
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name in _kernel_state['subsystems']:
                logger.warning(f"Subsystem already registered: {name}")
                return False
            
            _kernel_state['subsystems'][name] = {
                'object': subsystem,
                'initialized': False,
                'status': 'registered'
            }
            
            logger.debug(f"Registered subsystem: {name}")
            
            return True
    
    @classmethod
    def initialize(cls, name: str) -> bool:
        """
        Initialize a subsystem
        
        Args:
            name: Subsystem name
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name not in _kernel_state['subsystems']:
                logger.error(f"Subsystem not registered: {name}")
                return False
            
            subsystem_info = _kernel_state['subsystems'][name]
            
            if subsystem_info['initialized']:
                logger.warning(f"Subsystem already initialized: {name}")
                return True
            
            logger.info(f"Initializing subsystem: {name}")
            
            try:
                # Call the subsystem's initialize method
                subsystem = subsystem_info['object']
                if hasattr(subsystem, 'initialize') and callable(subsystem.initialize):
                    success = subsystem.initialize()
                else:
                    # If the subsystem doesn't have an initialize method, assume success
                    success = True
                
                subsystem_info['initialized'] = success
                subsystem_info['status'] = 'initialized' if success else 'initialization_failed'
                
                logger.info(f"Subsystem initialized: {name} (success={success})")
                
                return success
            except Exception as e:
                logger.exception(f"Error initializing subsystem: {name}")
                subsystem_info['status'] = 'initialization_failed'
                return False
    
    @classmethod
    def start(cls, name: str) -> bool:
        """
        Start a subsystem
        
        Args:
            name: Subsystem name
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name not in _kernel_state['subsystems']:
                logger.error(f"Subsystem not registered: {name}")
                return False
            
            subsystem_info = _kernel_state['subsystems'][name]
            
            if not subsystem_info['initialized']:
                logger.error(f"Subsystem not initialized: {name}")
                return False
            
            logger.info(f"Starting subsystem: {name}")
            
            try:
                # Call the subsystem's start method
                subsystem = subsystem_info['object']
                if hasattr(subsystem, 'start') and callable(subsystem.start):
                    success = subsystem.start()
                else:
                    # If the subsystem doesn't have a start method, assume success
                    success = True
                
                subsystem_info['status'] = 'running' if success else 'start_failed'
                
                logger.info(f"Subsystem started: {name} (success={success})")
                
                return success
            except Exception as e:
                logger.exception(f"Error starting subsystem: {name}")
                subsystem_info['status'] = 'start_failed'
                return False
    
    @classmethod
    def stop(cls, name: str) -> bool:
        """
        Stop a subsystem
        
        Args:
            name: Subsystem name
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name not in _kernel_state['subsystems']:
                logger.error(f"Subsystem not registered: {name}")
                return False
            
            subsystem_info = _kernel_state['subsystems'][name]
            
            if not subsystem_info['initialized']:
                logger.error(f"Subsystem not initialized: {name}")
                return False
            
            logger.info(f"Stopping subsystem: {name}")
            
            try:
                # Call the subsystem's stop method
                subsystem = subsystem_info['object']
                if hasattr(subsystem, 'stop') and callable(subsystem.stop):
                    success = subsystem.stop()
                else:
                    # If the subsystem doesn't have a stop method, assume success
                    success = True
                
                subsystem_info['status'] = 'stopped' if success else 'stop_failed'
                
                logger.info(f"Subsystem stopped: {name} (success={success})")
                
                return success
            except Exception as e:
                logger.exception(f"Error stopping subsystem: {name}")
                subsystem_info['status'] = 'stop_failed'
                return False
    
    @classmethod
    def get(cls, name: str) -> Any:
        """
        Get a subsystem
        
        Args:
            name: Subsystem name
        
        Returns:
            Subsystem object
        """
        with _kernel_lock:
            if name not in _kernel_state['subsystems']:
                logger.error(f"Subsystem not registered: {name}")
                return None
            
            return _kernel_state['subsystems'][name]['object']
    
    @classmethod
    def get_status(cls, name: str) -> str:
        """
        Get subsystem status
        
        Args:
            name: Subsystem name
        
        Returns:
            Subsystem status
        """
        with _kernel_lock:
            if name not in _kernel_state['subsystems']:
                logger.error(f"Subsystem not registered: {name}")
                return 'unknown'
            
            return _kernel_state['subsystems'][name]['status']
    
    @classmethod
    def list(cls) -> Dict[str, Dict[str, Any]]:
        """
        List all subsystems
        
        Returns:
            Dictionary of subsystem information
        """
        with _kernel_lock:
            return {name: {
                'initialized': info['initialized'],
                'status': info['status']
            } for name, info in _kernel_state['subsystems'].items()}


class ResourceManager:
    """Manager for kernel resources"""
    
    @classmethod
    def register(cls, name: str, resource: Any) -> bool:
        """
        Register a resource
        
        Args:
            name: Resource name
            resource: Resource object
        
        Returns:
            Success status
        """
        with _resource_lock:
            if name in _kernel_state['resources']:
                logger.warning(f"Resource already registered: {name}")
                return False
            
            _kernel_state['resources'][name] = {
                'object': resource,
                'status': 'registered',
                'locks': 0,
                'last_accessed': time.time()
            }
            
            logger.debug(f"Registered resource: {name}")
            
            return True
    
    @classmethod
    def acquire(cls, name: str, timeout: float = None) -> Any:
        """
        Acquire a resource
        
        Args:
            name: Resource name
            timeout: Timeout in seconds
        
        Returns:
            Resource object
        
        Raises:
            ResourceUnavailableException: If the resource is unavailable
        """
        with _resource_lock:
            if name not in _kernel_state['resources']:
                logger.error(f"Resource not registered: {name}")
                raise ResourceUnavailableException(f"Resource not registered: {name}")
            
            resource_info = _kernel_state['resources'][name]
            
            # Check if the resource is locked
            if resource_info.get('exclusive_lock', False):
                # If we have a timeout, wait for the resource to become available
                if timeout is not None:
                    start_time = time.time()
                    while resource_info.get('exclusive_lock', False) and time.time() - start_time < timeout:
                        _resource_lock.release()
                        time.sleep(0.01)
                        _resource_lock.acquire()
                    
                    # Check if the resource is still locked
                    if resource_info.get('exclusive_lock', False):
                        logger.error(f"Resource unavailable (timeout): {name}")
                        raise ResourceUnavailableException(f"Resource unavailable (timeout): {name}")
                else:
                    logger.error(f"Resource unavailable (locked): {name}")
                    raise ResourceUnavailableException(f"Resource unavailable (locked): {name}")
            
            # Update resource info
            resource_info['locks'] += 1
            resource_info['last_accessed'] = time.time()
            
            logger.debug(f"Acquired resource: {name}")
            
            return resource_info['object']
    
    @classmethod
    def release(cls, name: str) -> bool:
        """
        Release a resource
        
        Args:
            name: Resource name
        
        Returns:
            Success status
        """
        with _resource_lock:
            if name not in _kernel_state['resources']:
                logger.error(f"Resource not registered: {name}")
                return False
            
            resource_info = _kernel_state['resources'][name]
            
            # Update resource info
            if resource_info['locks'] > 0:
                resource_info['locks'] -= 1
            
            logger.debug(f"Released resource: {name}")
            
            return True
    
    @classmethod
    def acquire_exclusive(cls, name: str, timeout: float = None) -> Any:
        """
        Acquire a resource with exclusive access
        
        Args:
            name: Resource name
            timeout: Timeout in seconds
        
        Returns:
            Resource object
        
        Raises:
            ResourceUnavailableException: If the resource is unavailable
        """
        with _resource_lock:
            if name not in _kernel_state['resources']:
                logger.error(f"Resource not registered: {name}")
                raise ResourceUnavailableException(f"Resource not registered: {name}")
            
            resource_info = _kernel_state['resources'][name]
            
            # Check if the resource is locked
            if resource_info['locks'] > 0 or resource_info.get('exclusive_lock', False):
                # If we have a timeout, wait for the resource to become available
                if timeout is not None:
                    start_time = time.time()
                    while (resource_info['locks'] > 0 or resource_info.get('exclusive_lock', False)) and time.time() - start_time < timeout:
                        _resource_lock.release()
                        time.sleep(0.01)
                        _resource_lock.acquire()
                    
                    # Check if the resource is still locked
                    if resource_info['locks'] > 0 or resource_info.get('exclusive_lock', False):
                        logger.error(f"Resource unavailable (timeout): {name}")
                        raise ResourceUnavailableException(f"Resource unavailable (timeout): {name}")
                else:
                    logger.error(f"Resource unavailable (locked): {name}")
                    raise ResourceUnavailableException(f"Resource unavailable (locked): {name}")
            
            # Update resource info
            resource_info['exclusive_lock'] = True
            resource_info['last_accessed'] = time.time()
            
            logger.debug(f"Acquired resource exclusively: {name}")
            
            return resource_info['object']
    
    @classmethod
    def release_exclusive(cls, name: str) -> bool:
        """
        Release an exclusively acquired resource
        
        Args:
            name: Resource name
        
        Returns:
            Success status
        """
        with _resource_lock:
            if name not in _kernel_state['resources']:
                logger.error(f"Resource not registered: {name}")
                return False
            
            resource_info = _kernel_state['resources'][name]
            
            # Update resource info
            resource_info['exclusive_lock'] = False
            
            logger.debug(f"Released resource exclusively: {name}")
            
            return True
    
    @classmethod
    def get(cls, name: str) -> Any:
        """
        Get a resource without acquiring it
        
        Args:
            name: Resource name
        
        Returns:
            Resource object
        """
        with _resource_lock:
            if name not in _kernel_state['resources']:
                logger.error(f"Resource not registered: {name}")
                return None
            
            return _kernel_state['resources'][name]['object']
    
    @classmethod
    def list(cls) -> Dict[str, Dict[str, Any]]:
        """
        List all resources
        
        Returns:
            Dictionary of resource information
        """
        with _resource_lock:
            return {name: {
                'status': info['status'],
                'locks': info['locks'],
                'exclusive_lock': info.get('exclusive_lock', False),
                'last_accessed': info['last_accessed']
            } for name, info in _kernel_state['resources'].items()}


class ThreadManager:
    """Manager for kernel threads"""
    
    @classmethod
    def register(cls, name: str, thread: threading.Thread) -> bool:
        """
        Register a thread
        
        Args:
            name: Thread name
            thread: Thread object
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name in _kernel_state['threads']:
                logger.warning(f"Thread already registered: {name}")
                return False
            
            _kernel_state['threads'][name] = {
                'thread': thread,
                'status': 'registered',
                'start_time': None,
                'alive': thread.is_alive()
            }
            
            logger.debug(f"Registered thread: {name}")
            
            return True
    
    @classmethod
    def start(cls, name: str) -> bool:
        """
        Start a thread
        
        Args:
            name: Thread name
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name not in _kernel_state['threads']:
                logger.error(f"Thread not registered: {name}")
                return False
            
            thread_info = _kernel_state['threads'][name]
            thread = thread_info['thread']
            
            if thread.is_alive():
                logger.warning(f"Thread already running: {name}")
                return True
            
            logger.info(f"Starting thread: {name}")
            
            try:
                thread.start()
                thread_info['status'] = 'running'
                thread_info['start_time'] = time.time()
                thread_info['alive'] = True
                
                logger.info(f"Thread started: {name}")
                
                return True
            except Exception as e:
                logger.exception(f"Error starting thread: {name}")
                thread_info['status'] = 'start_failed'
                return False
    
    @classmethod
    def join(cls, name: str, timeout: float = None) -> bool:
        """
        Join a thread
        
        Args:
            name: Thread name
            timeout: Timeout in seconds
        
        Returns:
            Success status
        """
        with _kernel_lock:
            if name not in _kernel_state['threads']:
                logger.error(f"Thread not registered: {name}")
                return False
            
            thread_info = _kernel_state['threads'][name]
            thread = thread_info['thread']
            
            if not thread.is_alive():
                logger.warning(f"Thread not running: {name}")
                return True
        
        # Release the lock while we join the thread
        try:
            thread.join(timeout)
            
            with _kernel_lock:
                thread_info['alive'] = thread.is_alive()
                if not thread.is_alive():
                    thread_info['status'] = 'stopped'
                
                logger.info(f"Thread joined: {name}")
                
                return True
        except Exception as e:
            logger.exception(f"Error joining thread: {name}")
            
            with _kernel_lock:
                thread_info['status'] = 'join_failed'
                
                return False
    
    @classmethod
    def is_alive(cls, name: str) -> bool:
        """
        Check if a thread is alive
        
        Args:
            name: Thread name
        
        Returns:
            Whether the thread is alive
        """
        with _kernel_lock:
            if name not in _kernel_state['threads']:
                logger.error(f"Thread not registered: {name}")
                return False
            
            thread_info = _kernel_state['threads'][name]
            thread = thread_info['thread']
            
            is_alive = thread.is_alive()
            thread_info['alive'] = is_alive
            
            return is_alive
    
    @classmethod
    def list(cls) -> Dict[str, Dict[str, Any]]:
        """
        List all threads
        
        Returns:
            Dictionary of thread information
        """
        with _kernel_lock:
            return {name: {
                'status': info['status'],
                'start_time': info['start_time'],
                'alive': info['thread'].is_alive()
            } for name, info in _kernel_state['threads'].items()}


def initialize() -> bool:
    """
    Initialize the kernel
    
    Returns:
        Success status
    """
    global _kernel_state
    
    with _kernel_lock:
        if _kernel_state['running']:
            logger.warning("Kernel already initialized")
            return True
        
        logger.info("Initializing kernel")
        
        # Record start time
        _kernel_state['start_time'] = time.time()
        
        # Register signal handlers
        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        
        # Register atexit handler
        atexit.register(_atexit_handler)
        
        # Mark kernel as running
        _kernel_state['running'] = True
        
        logger.info("Kernel initialized")
        
        return True


def shutdown() -> bool:
    """
    Shutdown the kernel
    
    Returns:
        Success status
    """
    global _kernel_state
    
    with _kernel_lock:
        if not _kernel_state['running']:
            logger.warning("Kernel not running")
            return True
        
        logger.info("Shutting down kernel")
        
        # Call shutdown callbacks
        for callback in _kernel_state['shutdown_callbacks']:
            try:
                callback()
            except Exception as e:
                logger.exception(f"Error in shutdown callback: {e}")
        
        # Stop all subsystems in reverse dependency order
        subsystems = list(_kernel_state['subsystems'].keys())
        subsystems.reverse()
        
        for name in subsystems:
            try:
                SubsystemManager.stop(name)
            except Exception as e:
                logger.exception(f"Error stopping subsystem {name}: {e}")
        
        # Mark kernel as not running
        _kernel_state['running'] = False
        
        logger.info("Kernel shutdown complete")
        
        return True


def register_shutdown_callback(callback: Callable) -> bool:
    """
    Register a callback to be called on kernel shutdown
    
    Args:
        callback: Callback function
    
    Returns:
        Success status
    """
    with _kernel_lock:
        _kernel_state['shutdown_callbacks'].append(callback)
        return True


def _signal_handler(signum, frame):
    """
    Signal handler
    
    Args:
        signum: Signal number
        frame: Stack frame
    """
    logger.info(f"Received signal {signum}")
    
    # Handle different signals
    if signum == signal.SIGINT:
        logger.info("Received SIGINT, shutting down")
        shutdown()
    elif signum == signal.SIGTERM:
        logger.info("Received SIGTERM, shutting down")
        shutdown()


def _atexit_handler():
    """
    Atexit handler
    """
    logger.info("Atexit handler called")
    
    # Shutdown the kernel if it's still running
    if _kernel_state['running']:
        shutdown()


def get_kernel_status() -> Dict[str, Any]:
    """
    Get kernel status
    
    Returns:
        Kernel status information
    """
    with _kernel_lock:
        return {
            'running': _kernel_state['running'],
            'start_time': _kernel_state['start_time'],
            'pid': _kernel_state['pid'],
            'uptime': time.time() - _kernel_state['start_time'] if _kernel_state['running'] else 0,
            'threads': len(_kernel_state['threads']),
            'subsystems': len(_kernel_state['subsystems']),
            'resources': len(_kernel_state['resources'])
        }

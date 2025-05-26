"""
KOS Semaphore IPC Implementation

Provides process synchronization primitives for coordinating access to shared resources.
Implements semaphores with proper persistence and cross-process synchronization.
"""

import os
import time
import json
import fcntl
import struct
import threading
import uuid
import logging
import errno
from typing import Dict, Any, Optional, Union, Tuple, List

# Get module logger
logger = logging.getLogger('KOS.ipc.semaphore')

# Base directory for semaphore files
_SEM_BASE_DIR = "/tmp/kos_ipc/semaphore"

# Semaphore registry
_semaphores = {}

class KOSSemaphore:
    """
    KOS Semaphore implementation
    
    Provides a counting semaphore for process synchronization with
    proper cross-process synchronization and persistence.
    """
    
    def __init__(self, sem_id=None, name=None, value=1, max_value=1, load_existing=False):
        """
        Initialize a KOS semaphore
        
        Args:
            sem_id: Unique semaphore ID (generated if None)
            name: Friendly name for the semaphore
            value: Initial semaphore value
            max_value: Maximum semaphore value
            load_existing: Whether to load an existing semaphore
        """
        self.sem_id = sem_id or str(uuid.uuid4())
        self.name = name or f"sem_{self.sem_id}"
        self.value = value
        self.max_value = max_value
        self.sem_path = os.path.join(_SEM_BASE_DIR, f"{self.sem_id}.sem")
        self.meta_path = os.path.join(_SEM_BASE_DIR, f"{self.sem_id}.meta")
        self.lock_path = os.path.join(_SEM_BASE_DIR, f"{self.sem_id}.lock")
        
        # Ensure semaphore directory exists
        os.makedirs(_SEM_BASE_DIR, exist_ok=True)
        
        self.closed = False
        self.error = False
        
        # For waiters tracking
        self.waiters = set()
        
        # For synchronization
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        
        # External lock file for cross-process synchronization
        self.lock_file = None
        
        if load_existing:
            self._load()
        else:
            self._create()
        
        # Register the semaphore
        _semaphores[self.sem_id] = self
    
    def _create(self):
        """Create a new semaphore"""
        try:
            # Create the metadata file
            metadata = {
                'sem_id': self.sem_id,
                'name': self.name,
                'value': self.value,
                'max_value': self.max_value,
                'created': time.time(),
                'creator_pid': os.getpid(),
                'waiters': 0
            }
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            # Create the lock file
            with open(self.lock_path, 'w') as f:
                f.write('')
            
            # Create and initialize the semaphore file
            with open(self.sem_path, 'wb') as f:
                # Write header: magic, version, value, max_value, waiters, last op time
                f.write(b'KSEM')  # Magic
                f.write(struct.pack('<I', 1))  # Version
                f.write(struct.pack('<I', self.value))  # Value
                f.write(struct.pack('<I', self.max_value))  # Max value
                f.write(struct.pack('<I', 0))  # Waiters
                f.write(struct.pack('<d', time.time()))  # Last operation time
            
            logger.debug(f"Created semaphore {self.sem_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error creating semaphore {self.sem_id}: {e}")
            self.error = True
            raise
    
    def _load(self):
        """Load an existing semaphore"""
        try:
            # Load metadata
            with open(self.meta_path, 'r') as f:
                metadata = json.load(f)
            
            self.name = metadata['name']
            self.max_value = metadata['max_value']
            
            # Read current value from semaphore file
            with open(self.sem_path, 'rb') as f:
                # Skip magic and version
                f.seek(8)
                # Read value
                self.value = struct.unpack('<I', f.read(4))[0]
            
            logger.debug(f"Loaded semaphore {self.sem_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error loading semaphore {self.sem_id}: {e}")
            self.error = True
            raise
    
    def _acquire_lock(self):
        """Acquire external lock for cross-process synchronization"""
        try:
            if not self.lock_file:
                self.lock_file = open(self.lock_path, 'r+')
            
            # Use fcntl to get an advisory lock
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX)
            return True
        except Exception as e:
            logger.error(f"Error acquiring lock for semaphore {self.sem_id}: {e}")
            return False
    
    def _release_lock(self):
        """Release external lock"""
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.error(f"Error releasing lock for semaphore {self.sem_id}: {e}")
            return False
    
    def _update_semaphore_file(self):
        """Update the semaphore file with current values"""
        try:
            with open(self.sem_path, 'r+b') as f:
                # Skip magic and version
                f.seek(8)
                # Write value, max_value, waiters, last op time
                f.write(struct.pack('<I', self.value))
                f.write(struct.pack('<I', self.max_value))
                f.write(struct.pack('<I', len(self.waiters)))
                f.write(struct.pack('<d', time.time()))
            
            # Update metadata
            with open(self.meta_path, 'r') as f:
                metadata = json.load(f)
            
            metadata['value'] = self.value
            metadata['max_value'] = self.max_value
            metadata['waiters'] = len(self.waiters)
            metadata['updated'] = time.time()
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            return True
        except Exception as e:
            logger.error(f"Error updating semaphore file {self.sem_id}: {e}")
            return False
    
    def acquire(self, blocking=True, timeout=None):
        """
        Acquire the semaphore
        
        Args:
            blocking: Whether to block if the semaphore is not available
            timeout: Maximum time to wait in seconds (None for no timeout)
        
        Returns:
            Success status
        """
        if self.closed:
            return False
        
        with self.lock:
            # Fast path: semaphore is available
            if self.value > 0:
                self.value -= 1
                
                # Get external lock
                if not self._acquire_lock():
                    # Failed to get external lock, revert decrement
                    self.value += 1
                    return False
                
                # Update semaphore file
                self._update_semaphore_file()
                
                # Release external lock
                self._release_lock()
                
                return True
            
            if not blocking:
                return False
            
            # Record current thread as a waiter
            current_thread = threading.current_thread()
            self.waiters.add(current_thread)
            
            # Update waiters count in file
            if self._acquire_lock():
                self._update_semaphore_file()
                self._release_lock()
            
            # Wait for semaphore to become available
            wait_start = time.time()
            try:
                while True:
                    # Wait on condition with timeout
                    if timeout is not None:
                        remaining = timeout - (time.time() - wait_start)
                        if remaining <= 0:
                            # Timeout expired
                            self.waiters.remove(current_thread)
                            
                            # Update waiters count in file
                            if self._acquire_lock():
                                self._update_semaphore_file()
                                self._release_lock()
                            
                            return False
                        
                        success = self.condition.wait(remaining)
                    else:
                        success = self.condition.wait(1.0)  # Use shorter timeout for responsiveness
                    
                    # Check if semaphore is available
                    if self.value > 0:
                        self.value -= 1
                        self.waiters.remove(current_thread)
                        
                        # Get external lock
                        if not self._acquire_lock():
                            # Failed to get external lock, revert changes
                            self.value += 1
                            self.waiters.add(current_thread)
                            continue
                        
                        # Update semaphore file
                        self._update_semaphore_file()
                        
                        # Release external lock
                        self._release_lock()
                        
                        return True
                    
                    # Check if timeout expired
                    if timeout is not None and (time.time() - wait_start) >= timeout:
                        self.waiters.remove(current_thread)
                        
                        # Update waiters count in file
                        if self._acquire_lock():
                            self._update_semaphore_file()
                            self._release_lock()
                        
                        return False
            
            except Exception as e:
                logger.error(f"Error acquiring semaphore {self.sem_id}: {e}")
                # Remove from waiters if exception
                if current_thread in self.waiters:
                    self.waiters.remove(current_thread)
                    
                    # Update waiters count in file
                    if self._acquire_lock():
                        self._update_semaphore_file()
                        self._release_lock()
                
                return False
    
    def release(self, count=1):
        """
        Release the semaphore
        
        Args:
            count: Number of times to release the semaphore
        
        Returns:
            Success status
        """
        if self.closed:
            return False
        
        if count <= 0:
            return False
        
        with self.lock:
            # Get external lock
            if not self._acquire_lock():
                return False
            
            # Calculate new value, ensuring it doesn't exceed max_value
            self.value = min(self.value + count, self.max_value)
            
            # Update semaphore file
            self._update_semaphore_file()
            
            # Release external lock
            self._release_lock()
            
            # Notify waiters
            self.condition.notify_all()
            
            return True
    
    def get_value(self):
        """
        Get the current semaphore value
        
        Returns:
            Current semaphore value
        """
        if self.closed:
            return 0
        
        with self.lock:
            return self.value
    
    def close(self):
        """Close the semaphore"""
        if self.closed:
            return
        
        try:
            with self.lock:
                # Notify all waiters
                self.condition.notify_all()
                
                # Close resources
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                
                self.closed = True
                
                logger.debug(f"Closed semaphore {self.sem_id} ({self.name})")
        
        except Exception as e:
            logger.error(f"Error closing semaphore {self.sem_id}: {e}")
            self.error = True
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        try:
            self.close()
        except:
            pass


def create_semaphore(name: str = None, value: int = 1, max_value: int = 1) -> str:
    """
    Create a new semaphore
    
    Args:
        name: Optional semaphore name
        value: Initial semaphore value
        max_value: Maximum semaphore value
    
    Returns:
        Semaphore ID
    """
    try:
        # Validate arguments
        if value < 0:
            logger.error("Semaphore value cannot be negative")
            raise ValueError("Semaphore value cannot be negative")
        
        if max_value < 1:
            logger.error("Maximum semaphore value must be at least 1")
            raise ValueError("Maximum semaphore value must be at least 1")
        
        if value > max_value:
            logger.error("Semaphore value cannot exceed maximum value")
            raise ValueError("Semaphore value cannot exceed maximum value")
        
        # Create the semaphore
        sem = KOSSemaphore(name=name, value=value, max_value=max_value)
        
        logger.info(f"Created semaphore {sem.sem_id} ({sem.name})")
        
        return sem.sem_id
    
    except Exception as e:
        logger.error(f"Error creating semaphore: {e}")
        raise


def delete_semaphore(sem_id: str) -> bool:
    """
    Delete a semaphore
    
    Args:
        sem_id: Semaphore ID
    
    Returns:
        Success status
    """
    try:
        # Check if the semaphore exists
        if sem_id not in _semaphores:
            logger.warning(f"Semaphore {sem_id} not found")
            return False
        
        # Close the semaphore
        sem = _semaphores[sem_id]
        sem.close()
        
        # Remove from registry
        del _semaphores[sem_id]
        
        # Delete semaphore files
        sem_path = os.path.join(_SEM_BASE_DIR, f"{sem_id}.sem")
        meta_path = os.path.join(_SEM_BASE_DIR, f"{sem_id}.meta")
        lock_path = os.path.join(_SEM_BASE_DIR, f"{sem_id}.lock")
        
        if os.path.exists(sem_path):
            os.unlink(sem_path)
        
        if os.path.exists(meta_path):
            os.unlink(meta_path)
        
        if os.path.exists(lock_path):
            os.unlink(lock_path)
        
        logger.info(f"Deleted semaphore {sem_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting semaphore {sem_id}: {e}")
        return False


def semaphore_acquire(sem_id: str, blocking: bool = True, timeout: float = None) -> bool:
    """
    Acquire a semaphore
    
    Args:
        sem_id: Semaphore ID
        blocking: Whether to block if the semaphore is not available
        timeout: Maximum time to wait in seconds (None for no timeout)
    
    Returns:
        Success status
    """
    try:
        # Check if the semaphore exists
        if sem_id not in _semaphores:
            logger.warning(f"Semaphore {sem_id} not found")
            return False
        
        # Acquire the semaphore
        sem = _semaphores[sem_id]
        result = sem.acquire(blocking, timeout)
        
        return result
    
    except Exception as e:
        logger.error(f"Error acquiring semaphore {sem_id}: {e}")
        return False


def semaphore_release(sem_id: str, count: int = 1) -> bool:
    """
    Release a semaphore
    
    Args:
        sem_id: Semaphore ID
        count: Number of times to release the semaphore
    
    Returns:
        Success status
    """
    try:
        # Check if the semaphore exists
        if sem_id not in _semaphores:
            logger.warning(f"Semaphore {sem_id} not found")
            return False
        
        # Release the semaphore
        sem = _semaphores[sem_id]
        result = sem.release(count)
        
        return result
    
    except Exception as e:
        logger.error(f"Error releasing semaphore {sem_id}: {e}")
        return False


def get_semaphore_value(sem_id: str) -> int:
    """
    Get the current value of a semaphore
    
    Args:
        sem_id: Semaphore ID
    
    Returns:
        Current semaphore value or -1 if error
    """
    try:
        # Check if the semaphore exists
        if sem_id not in _semaphores:
            logger.warning(f"Semaphore {sem_id} not found")
            return -1
        
        # Get semaphore value
        sem = _semaphores[sem_id]
        value = sem.get_value()
        
        return value
    
    except Exception as e:
        logger.error(f"Error getting semaphore value for {sem_id}: {e}")
        return -1

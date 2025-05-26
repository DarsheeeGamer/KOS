"""
KOS Message Queue IPC Implementation

Provides a message queue mechanism for structured communication between processes.
Implements persistent storage with proper synchronization and prioritization.
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
import pickle
from typing import Dict, Any, Optional, Union, Tuple, List

# Get module logger
logger = logging.getLogger('KOS.ipc.message_queue')

# Base directory for message queue files
_MSGQ_BASE_DIR = "/tmp/kos_ipc/message_queue"

# Message queue registry
_message_queues = {}

class KOSMessageQueue:
    """
    KOS Message Queue implementation
    
    Provides a POSIX-like message queue with persistence, priority levels,
    and proper cross-process synchronization.
    """
    
    def __init__(self, queue_id=None, name=None, max_messages=100, max_size=4096, load_existing=False):
        """
        Initialize a KOS message queue
        
        Args:
            queue_id: Unique queue ID (generated if None)
            name: Friendly name for the queue
            max_messages: Maximum number of messages in the queue
            max_size: Maximum message size in bytes
            load_existing: Whether to load an existing queue
        """
        self.queue_id = queue_id or str(uuid.uuid4())
        self.name = name or f"msgq_{self.queue_id}"
        self.max_messages = max_messages
        self.max_size = max_size
        self.queue_dir = os.path.join(_MSGQ_BASE_DIR, self.queue_id)
        self.meta_path = os.path.join(self.queue_dir, "metadata.json")
        self.lock_path = os.path.join(self.queue_dir, "lock")
        self.msg_dir = os.path.join(self.queue_dir, "messages")
        
        # Ensure queue directories exist
        os.makedirs(_MSGQ_BASE_DIR, exist_ok=True)
        
        self.closed = False
        self.error = False
        
        # Message sequence tracking
        self.next_msg_id = 1
        
        # For synchronization
        self.lock = threading.RLock()
        self.not_empty = threading.Condition(self.lock)
        self.not_full = threading.Condition(self.lock)
        
        # External lock file for cross-process synchronization
        self.lock_file = None
        
        if load_existing:
            self._load()
        else:
            self._create()
        
        # Register the queue
        _message_queues[self.queue_id] = self
    
    def _create(self):
        """Create a new message queue"""
        try:
            # Create queue directories
            os.makedirs(self.queue_dir, exist_ok=True)
            os.makedirs(self.msg_dir, exist_ok=True)
            
            # Create the metadata file
            metadata = {
                'queue_id': self.queue_id,
                'name': self.name,
                'max_messages': self.max_messages,
                'max_size': self.max_size,
                'created': time.time(),
                'creator_pid': os.getpid(),
                'next_msg_id': self.next_msg_id
            }
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            # Create the lock file
            with open(self.lock_path, 'w') as f:
                f.write('')
            
            logger.debug(f"Created message queue {self.queue_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error creating message queue {self.queue_id}: {e}")
            self.error = True
            raise
    
    def _load(self):
        """Load an existing message queue"""
        try:
            # Load metadata
            with open(self.meta_path, 'r') as f:
                metadata = json.load(f)
            
            self.name = metadata['name']
            self.max_messages = metadata['max_messages']
            self.max_size = metadata['max_size']
            self.next_msg_id = metadata.get('next_msg_id', 1)
            
            # Ensure message directory exists
            os.makedirs(self.msg_dir, exist_ok=True)
            
            logger.debug(f"Loaded message queue {self.queue_id} ({self.name})")
            
        except Exception as e:
            logger.error(f"Error loading message queue {self.queue_id}: {e}")
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
            logger.error(f"Error acquiring lock for queue {self.queue_id}: {e}")
            return False
    
    def _release_lock(self):
        """Release external lock"""
        try:
            if self.lock_file:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            return True
        except Exception as e:
            logger.error(f"Error releasing lock for queue {self.queue_id}: {e}")
            return False
    
    def _update_metadata(self):
        """Update metadata file"""
        try:
            metadata = {
                'queue_id': self.queue_id,
                'name': self.name,
                'max_messages': self.max_messages,
                'max_size': self.max_size,
                'updated': time.time(),
                'next_msg_id': self.next_msg_id
            }
            
            with open(self.meta_path, 'w') as f:
                json.dump(metadata, f)
            
            return True
        except Exception as e:
            logger.error(f"Error updating metadata for queue {self.queue_id}: {e}")
            return False
    
    def _get_message_count(self):
        """Get the number of messages in the queue"""
        try:
            return len(os.listdir(self.msg_dir))
        except Exception as e:
            logger.error(f"Error getting message count for queue {self.queue_id}: {e}")
            return 0
    
    def _get_messages(self, msg_type=0):
        """
        Get all messages in the queue, optionally filtered by type
        
        Args:
            msg_type: Message type filter (0 for all)
        
        Returns:
            List of message paths sorted by priority and time
        """
        try:
            messages = []
            
            for filename in os.listdir(self.msg_dir):
                # Parse filename: priority_type_id.msg
                parts = filename.split('_')
                if len(parts) >= 3 and filename.endswith('.msg'):
                    try:
                        priority = int(parts[0])
                        msg_type_val = int(parts[1])
                        msg_id = int(parts[2].split('.')[0])
                        
                        # Filter by type if specified
                        if msg_type == 0 or msg_type == msg_type_val:
                            messages.append({
                                'path': os.path.join(self.msg_dir, filename),
                                'priority': priority,
                                'type': msg_type_val,
                                'id': msg_id,
                                'filename': filename
                            })
                    except ValueError:
                        continue
            
            # Sort by priority (highest first) and then by ID (oldest first)
            return sorted(messages, key=lambda m: (-m['priority'], m['id']))
        
        except Exception as e:
            logger.error(f"Error getting messages for queue {self.queue_id}: {e}")
            return []
    
    def send(self, message, msg_type=0, priority=0, blocking=True):
        """
        Send a message to the queue
        
        Args:
            message: Message data (must be serializable)
            msg_type: Message type (0-255)
            priority: Message priority (0-255, higher is more important)
            blocking: Whether to wait if the queue is full
        
        Returns:
            Success status
        """
        if self.closed:
            return False
        
        # Validate message
        if not message:
            return False
        
        # Validate type and priority
        msg_type = max(0, min(255, int(msg_type)))
        priority = max(0, min(255, int(priority)))
        
        # Acquire lock for thread-safety
        with self.lock:
            try:
                # Get external lock for cross-process safety
                if not self._acquire_lock():
                    return False
                
                # Check if queue is full
                message_count = self._get_message_count()
                
                while message_count >= self.max_messages:
                    if not blocking:
                        self._release_lock()
                        return False
                    
                    # Release external lock while waiting
                    self._release_lock()
                    
                    if not self.not_full.wait(1.0):  # Wait with timeout
                        # Recheck conditions after timeout
                        if not self._acquire_lock():
                            return False
                        
                        message_count = self._get_message_count()
                        
                        if message_count >= self.max_messages:
                            if not blocking:
                                self._release_lock()
                                return False
                            # Release and continue waiting
                            self._release_lock()
                            continue
                        else:
                            # Space available, break out but keep lock
                            break
                    else:
                        # Woken up, reacquire lock and recheck
                        if not self._acquire_lock():
                            return False
                        
                        message_count = self._get_message_count()
                        
                        if message_count >= self.max_messages:
                            if not blocking:
                                self._release_lock()
                                return False
                            # Release and continue waiting
                            self._release_lock()
                            continue
                        else:
                            # Space available, keep lock and break out
                            break
                
                # We have the lock and space is available
                
                # Prepare message data
                msg_data = {
                    'type': msg_type,
                    'priority': priority,
                    'timestamp': time.time(),
                    'sender_pid': os.getpid(),
                    'data': message
                }
                
                # Get next message ID
                msg_id = self.next_msg_id
                self.next_msg_id += 1
                
                # Update metadata
                self._update_metadata()
                
                # Create message file: priority_type_id.msg
                msg_filename = f"{priority:03d}_{msg_type:03d}_{msg_id:010d}.msg"
                msg_path = os.path.join(self.msg_dir, msg_filename)
                
                # Write message data
                with open(msg_path, 'wb') as f:
                    pickle.dump(msg_data, f)
                
                # Release external lock
                self._release_lock()
                
                # Signal not empty
                self.not_empty.notify_all()
                
                return True
            
            except Exception as e:
                logger.error(f"Error sending message to queue {self.queue_id}: {e}")
                if self.lock_file:
                    try:
                        self._release_lock()
                    except:
                        pass
                return False
    
    def receive(self, msg_type=0, blocking=True):
        """
        Receive a message from the queue
        
        Args:
            msg_type: Message type filter (0 for any type)
            blocking: Whether to wait if no message is available
        
        Returns:
            Message data or None if no message is available
        """
        if self.closed:
            return None
        
        # Acquire lock for thread-safety
        with self.lock:
            try:
                # Get external lock for cross-process safety
                if not self._acquire_lock():
                    return None
                
                # Get messages of the specified type
                messages = self._get_messages(msg_type)
                
                while not messages:
                    if not blocking:
                        self._release_lock()
                        return None
                    
                    # Release external lock while waiting
                    self._release_lock()
                    
                    if not self.not_empty.wait(1.0):  # Wait with timeout
                        # Recheck conditions after timeout
                        if not self._acquire_lock():
                            return None
                        
                        messages = self._get_messages(msg_type)
                        
                        if not messages:
                            if not blocking:
                                self._release_lock()
                                return None
                            # Release and continue waiting
                            self._release_lock()
                            continue
                        else:
                            # Message available, break out but keep lock
                            break
                    else:
                        # Woken up, reacquire lock and recheck
                        if not self._acquire_lock():
                            return None
                        
                        messages = self._get_messages(msg_type)
                        
                        if not messages:
                            if not blocking:
                                self._release_lock()
                                return None
                            # Release and continue waiting
                            self._release_lock()
                            continue
                        else:
                            # Message available, keep lock and break out
                            break
                
                # We have the lock and a message is available
                
                # Get the highest priority message (or oldest if same priority)
                message = messages[0]
                
                # Read message data
                with open(message['path'], 'rb') as f:
                    msg_data = pickle.load(f)
                
                # Delete the message file
                os.unlink(message['path'])
                
                # Release external lock
                self._release_lock()
                
                # Signal not full
                self.not_full.notify_all()
                
                return msg_data
            
            except Exception as e:
                logger.error(f"Error receiving message from queue {self.queue_id}: {e}")
                if self.lock_file:
                    try:
                        self._release_lock()
                    except:
                        pass
                return None
    
    def close(self):
        """Close the message queue"""
        if self.closed:
            return
        
        try:
            with self.lock:
                # Signal any waiting threads
                self.not_empty.notify_all()
                self.not_full.notify_all()
                
                # Close resources
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                
                self.closed = True
                
                logger.debug(f"Closed message queue {self.queue_id} ({self.name})")
        
        except Exception as e:
            logger.error(f"Error closing message queue {self.queue_id}: {e}")
            self.error = True
            raise
    
    def __del__(self):
        """Destructor to ensure resources are released"""
        try:
            self.close()
        except:
            pass


def create_message_queue(name: str = None, max_messages: int = 100, max_size: int = 4096) -> str:
    """
    Create a new message queue
    
    Args:
        name: Optional queue name
        max_messages: Maximum number of messages in the queue
        max_size: Maximum message size in bytes
    
    Returns:
        Queue ID
    """
    try:
        # Create the message queue
        queue = KOSMessageQueue(name=name, max_messages=max_messages, max_size=max_size)
        
        logger.info(f"Created message queue {queue.queue_id} ({queue.name})")
        
        return queue.queue_id
    
    except Exception as e:
        logger.error(f"Error creating message queue: {e}")
        raise


def delete_message_queue(queue_id: str) -> bool:
    """
    Delete a message queue
    
    Args:
        queue_id: Queue ID
    
    Returns:
        Success status
    """
    try:
        # Check if the queue exists
        if queue_id not in _message_queues:
            logger.warning(f"Message queue {queue_id} not found")
            return False
        
        # Close the queue
        queue = _message_queues[queue_id]
        queue.close()
        
        # Remove from registry
        del _message_queues[queue_id]
        
        # Delete queue directory
        import shutil
        queue_dir = os.path.join(_MSGQ_BASE_DIR, queue_id)
        if os.path.exists(queue_dir):
            shutil.rmtree(queue_dir)
        
        logger.info(f"Deleted message queue {queue_id}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error deleting message queue {queue_id}: {e}")
        return False


def send_message(queue_id: str, message: Any, msg_type: int = 0, 
                priority: int = 0, blocking: bool = True) -> bool:
    """
    Send a message to a message queue
    
    Args:
        queue_id: Queue ID
        message: Message data (must be serializable)
        msg_type: Message type (0-255)
        priority: Message priority (0-255, higher is more important)
        blocking: Whether to wait if the queue is full
    
    Returns:
        Success status
    """
    try:
        # Check if the queue exists
        if queue_id not in _message_queues:
            logger.warning(f"Message queue {queue_id} not found")
            return False
        
        # Send the message
        queue = _message_queues[queue_id]
        result = queue.send(message, msg_type, priority, blocking)
        
        return result
    
    except Exception as e:
        logger.error(f"Error sending message to queue {queue_id}: {e}")
        return False


def receive_message(queue_id: str, msg_type: int = 0, blocking: bool = True) -> Any:
    """
    Receive a message from a message queue
    
    Args:
        queue_id: Queue ID
        msg_type: Message type filter (0 for any type)
        blocking: Whether to wait if no message is available
    
    Returns:
        Message data or None if no message is available
    """
    try:
        # Check if the queue exists
        if queue_id not in _message_queues:
            logger.warning(f"Message queue {queue_id} not found")
            return None
        
        # Receive a message
        queue = _message_queues[queue_id]
        message = queue.receive(msg_type, blocking)
        
        return message
    
    except Exception as e:
        logger.error(f"Error receiving message from queue {queue_id}: {e}")
        return None

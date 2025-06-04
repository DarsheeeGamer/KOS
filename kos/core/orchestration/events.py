"""
Events System for KOS Orchestration

This module implements an events system for the KOS orchestration system,
recording important system events for auditing and troubleshooting.
"""

import os
import json
import logging
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
EVENTS_PATH = os.path.join(ORCHESTRATION_ROOT, 'events')

# Ensure directories exist
os.makedirs(EVENTS_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class EventType:
    """Event types."""
    NORMAL = "Normal"
    WARNING = "Warning"
    ERROR = "Error"


class Event:
    """
    Event in the KOS orchestration system.
    
    An Event is a report of an event somewhere in the system.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 involved_object: Dict[str, str] = None,
                 reason: str = "",
                 message: str = "",
                 source: Dict[str, str] = None,
                 first_timestamp: Optional[float] = None,
                 last_timestamp: Optional[float] = None,
                 count: int = 1,
                 type: str = EventType.NORMAL):
        """
        Initialize an Event.
        
        Args:
            name: Event name
            namespace: Namespace
            involved_object: Object involved in the event
            reason: Short, machine understandable reason
            message: Human-readable description
            source: Component reporting the event
            first_timestamp: Time when the event was first observed
            last_timestamp: Time when the event was last observed
            count: Number of times this event has occurred
            type: Event type (Normal, Warning, Error)
        """
        self.name = name
        self.namespace = namespace
        self.involved_object = involved_object or {}
        self.reason = reason
        self.message = message
        self.source = source or {"component": "orchestration"}
        self.first_timestamp = first_timestamp or time.time()
        self.last_timestamp = last_timestamp or self.first_timestamp
        self.count = count
        self.type = type
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this Event."""
        return os.path.join(EVENTS_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the Event from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update event fields
            self.involved_object = data.get("involvedObject", {})
            self.reason = data.get("reason", "")
            self.message = data.get("message", "")
            self.source = data.get("source", {"component": "orchestration"})
            self.first_timestamp = data.get("firstTimestamp", time.time())
            self.last_timestamp = data.get("lastTimestamp", self.first_timestamp)
            self.count = data.get("count", 1)
            self.type = data.get("type", EventType.NORMAL)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Event {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Event to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "Event",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "involvedObject": self.involved_object,
                    "reason": self.reason,
                    "message": self.message,
                    "source": self.source,
                    "firstTimestamp": self.first_timestamp,
                    "lastTimestamp": self.last_timestamp,
                    "count": self.count,
                    "type": self.type
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Event {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Event.
        
        Returns:
            bool: Success or failure
        """
        try:
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Event {self.namespace}/{self.name}: {e}")
            return False
    
    def update(self, message: Optional[str] = None) -> bool:
        """
        Update the Event.
        
        Args:
            message: New message (optional)
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update timestamp and count
                self.last_timestamp = time.time()
                self.count += 1
                
                # Update message if provided
                if message:
                    self.message = message
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to update Event {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_events(namespace: Optional[str] = None,
                   involved_object: Optional[Dict[str, str]] = None,
                   event_type: Optional[str] = None,
                   since: Optional[float] = None,
                   limit: int = 100) -> List['Event']:
        """
        List Events.
        
        Args:
            namespace: Namespace to filter by
            involved_object: Involved object to filter by
            event_type: Event type to filter by
            since: Only include events after this time
            limit: Maximum number of events to return
            
        Returns:
            List of Events
        """
        events = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = EVENTS_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List Events in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(EVENTS_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    # Skip if we've reached the limit
                    if len(events) >= limit:
                        break
                    
                    event_name = filename[:-5]  # Remove .json extension
                    event = Event(event_name, ns)
                    
                    # Apply filters
                    if involved_object:
                        match = True
                        for key, value in involved_object.items():
                            if event.involved_object.get(key) != value:
                                match = False
                                break
                        
                        if not match:
                            continue
                    
                    if event_type and event.type != event_type:
                        continue
                    
                    if since and event.last_timestamp < since:
                        continue
                    
                    events.append(event)
            
            # Sort by last timestamp (most recent first)
            events.sort(key=lambda e: e.last_timestamp, reverse=True)
            
            # Apply limit
            if len(events) > limit:
                events = events[:limit]
        except Exception as e:
            logger.error(f"Failed to list Events: {e}")
        
        return events
    
    @staticmethod
    def get_event(name: str, namespace: str = "default") -> Optional['Event']:
        """
        Get an Event by name and namespace.
        
        Args:
            name: Event name
            namespace: Namespace
            
        Returns:
            Event object or None if not found
        """
        event = Event(name, namespace)
        
        if os.path.exists(event._file_path()):
            return event
        
        return None


class EventRecorder:
    """
    Event recorder for the KOS orchestration system.
    
    This class provides methods to record events.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventRecorder, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the event recorder."""
        if self._initialized:
            return
        
        self._initialized = True
        self._component = "orchestration"
        self._cleanup_thread = None
        self._stop_event = threading.Event()
        
        # Start cleanup thread
        self._start_cleanup()
    
    def set_component(self, component: str) -> None:
        """
        Set the component name.
        
        Args:
            component: Component name
        """
        self._component = component
    
    def record_event(self, involved_object: Dict[str, str],
                    event_type: str, reason: str, message: str,
                    namespace: str = "default") -> Optional[Event]:
        """
        Record an event.
        
        Args:
            involved_object: Object involved in the event
            event_type: Event type (Normal, Warning, Error)
            reason: Short, machine understandable reason
            message: Human-readable description
            namespace: Namespace
            
        Returns:
            Created or updated Event
        """
        try:
            # Generate event name
            object_kind = involved_object.get("kind", "Unknown")
            object_name = involved_object.get("name", "unknown")
            timestamp = int(time.time())
            event_name = f"{object_kind.lower()}-{object_name}-{timestamp}"
            
            # Check if there's a similar event
            existing_events = Event.list_events(
                namespace=namespace,
                involved_object=involved_object,
                event_type=event_type,
                since=time.time() - 300  # Last 5 minutes
            )
            
            for event in existing_events:
                if event.reason == reason:
                    # Update existing event
                    event.update(message)
                    return event
            
            # Create new event
            event = Event(
                name=event_name,
                namespace=namespace,
                involved_object=involved_object,
                reason=reason,
                message=message,
                source={"component": self._component},
                type=event_type
            )
            
            event.save()
            return event
        except Exception as e:
            logger.error(f"Failed to record event: {e}")
            return None
    
    def _start_cleanup(self) -> None:
        """Start the cleanup thread."""
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True
        )
        self._cleanup_thread.start()
    
    def _cleanup_loop(self) -> None:
        """Cleanup loop for old events."""
        while not self._stop_event.is_set():
            try:
                self._cleanup_old_events()
            except Exception as e:
                logger.error(f"Error in event cleanup loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(3600)  # Cleanup once per hour
    
    def _cleanup_old_events(self) -> None:
        """Clean up old events."""
        try:
            # Get all events
            all_events = []
            for namespace_dir in os.listdir(EVENTS_PATH):
                namespace_path = os.path.join(EVENTS_PATH, namespace_dir)
                if not os.path.isdir(namespace_path):
                    continue
                
                for filename in os.listdir(namespace_path):
                    if not filename.endswith('.json'):
                        continue
                    
                    event_name = filename[:-5]  # Remove .json extension
                    event = Event(event_name, namespace_dir)
                    all_events.append(event)
            
            # Get current time
            now = time.time()
            
            # Delete events older than 1 hour for non-warning/error events
            for event in all_events:
                if event.type == EventType.NORMAL:
                    if now - event.last_timestamp > 3600:  # 1 hour
                        event.delete()
                else:
                    if now - event.last_timestamp > 86400:  # 24 hours
                        event.delete()
        except Exception as e:
            logger.error(f"Failed to clean up old events: {e}")
    
    def stop(self) -> None:
        """Stop the event recorder."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_event.set()
            self._cleanup_thread.join(timeout=5)
    
    @staticmethod
    def instance() -> 'EventRecorder':
        """
        Get the singleton instance.
        
        Returns:
            EventRecorder instance
        """
        return EventRecorder()


def record_event(involved_object: Dict[str, str],
                event_type: str, reason: str, message: str,
                namespace: str = "default") -> Optional[Event]:
    """
    Record an event.
    
    Args:
        involved_object: Object involved in the event
        event_type: Event type (Normal, Warning, Error)
        reason: Short, machine understandable reason
        message: Human-readable description
        namespace: Namespace
        
    Returns:
        Created or updated Event
    """
    recorder = EventRecorder.instance()
    return recorder.record_event(involved_object, event_type, reason, message, namespace)


def record_for_object(obj: Any, event_type: str, reason: str, message: str) -> Optional[Event]:
    """
    Record an event for an object.
    
    Args:
        obj: Object to record event for
        event_type: Event type (Normal, Warning, Error)
        reason: Short, machine understandable reason
        message: Human-readable description
        
    Returns:
        Created or updated Event
    """
    try:
        # Extract object info
        if not hasattr(obj, 'metadata'):
            return None
        
        metadata = getattr(obj, 'metadata')
        if not isinstance(metadata, dict):
            return None
        
        name = metadata.get('name', '')
        namespace = metadata.get('namespace', 'default')
        uid = metadata.get('uid', '')
        
        # Get object kind
        kind = ""
        if hasattr(obj, 'kind'):
            kind = getattr(obj, 'kind')
        else:
            kind = obj.__class__.__name__
        
        involved_object = {
            "kind": kind,
            "name": name,
            "namespace": namespace,
            "uid": uid
        }
        
        return record_event(involved_object, event_type, reason, message, namespace)
    except Exception as e:
        logger.error(f"Failed to record event for object: {e}")
        return None

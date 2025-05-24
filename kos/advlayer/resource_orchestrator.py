"""
Resource Orchestrator Component for KADVLayer

This module provides advanced resource orchestration capabilities for KOS,
allowing for dynamic resource allocation, prioritization, and throttling.
"""

import os
import sys
import time
import logging
import threading
import json
import psutil
from typing import Dict, List, Any, Optional, Union, Callable, Tuple

logger = logging.getLogger('KOS.advlayer.resource_orchestrator')

class ResourceConstraint:
    """Defines constraints for resource usage"""
    
    def __init__(self, resource_type: str, min_value: float, max_value: float, priority: int = 0):
        """Initialize a resource constraint"""
        self.resource_type = resource_type  # cpu, memory, disk, network
        self.min_value = min_value  # Minimum guaranteed value
        self.max_value = max_value  # Maximum allowed value
        self.priority = priority  # Higher priority gets resources first
        self.current_value = min_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "resource_type": self.resource_type,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "current_value": self.current_value,
            "priority": self.priority
        }

class ResourceAllocation:
    """Represents an allocation of resources to a consumer"""
    
    def __init__(self, consumer_id: str, constraints: Dict[str, ResourceConstraint]):
        """Initialize a resource allocation"""
        self.consumer_id = consumer_id
        self.constraints = constraints
        self.last_update = time.time()
        self.creation_time = self.last_update
        self.active = True
    
    def update_constraint(self, resource_type: str, current_value: float) -> None:
        """Update the current value for a constraint"""
        if resource_type in self.constraints:
            self.constraints[resource_type].current_value = current_value
            self.last_update = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "consumer_id": self.consumer_id,
            "constraints": {k: v.to_dict() for k, v in self.constraints.items()},
            "last_update": self.last_update,
            "creation_time": self.creation_time,
            "age": time.time() - self.creation_time,
            "active": self.active
        }

class ResourceOrchestrator:
    """
    Orchestrates resource allocation and constraints for KOS
    
    This component allows KOS to manage and prioritize resource allocation
    to different consumers (applications, services, processes).
    """
    
    def __init__(self):
        """Initialize the resource orchestrator"""
        self.lock = threading.RLock()
        self.allocations = {}  # Map of consumer_id -> ResourceAllocation
        self.available_resources = {
            "cpu": 100.0,  # Percentage
            "memory": psutil.virtual_memory().total,  # Bytes
            "disk_io": 100.0,  # Percentage
            "network_io": 100.0  # Percentage
        }
        self.throttling_enabled = True
        self.prioritization_enabled = True
        self.update_interval = 5.0  # Seconds
        self.callbacks = {}  # Map of event_type -> list of callbacks
        
        # Start background updater
        self.update_thread = threading.Thread(target=self._background_updater, daemon=True)
        self.update_thread.start()
        
        logger.debug("ResourceOrchestrator initialized")
    
    def _background_updater(self):
        """Background thread to update resource allocations"""
        while True:
            try:
                # Sleep for update interval
                time.sleep(self.update_interval)
                
                # Update resource allocations
                self.update_allocations()
            except Exception as e:
                logger.error(f"Error in background updater: {e}")
    
    def register_callback(self, event_type: str, callback: Callable) -> None:
        """
        Register a callback for resource events
        
        Args:
            event_type: Type of event (allocation_change, constraint_violation, etc.)
            callback: Callback function
        """
        with self.lock:
            if event_type not in self.callbacks:
                self.callbacks[event_type] = []
            
            self.callbacks[event_type].append(callback)
    
    def _notify_callbacks(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify callbacks for an event"""
        if event_type not in self.callbacks:
            return
        
        for callback in self.callbacks[event_type]:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in resource callback: {e}")
    
    def add_allocation(self, consumer_id: str, constraints: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Add a new resource allocation for a consumer
        
        Args:
            consumer_id: ID of the consumer (app ID, process ID, etc.)
            constraints: Dictionary of resource constraints
                {resource_type: {min_value, max_value, priority}}
                
        Returns:
            Dictionary with allocation status
        """
        with self.lock:
            if consumer_id in self.allocations:
                return {
                    "success": False,
                    "error": f"Consumer already has an allocation: {consumer_id}"
                }
            
            # Validate and create constraints
            constraint_objects = {}
            for resource_type, constraint_data in constraints.items():
                if resource_type not in self.available_resources:
                    return {
                        "success": False,
                        "error": f"Unknown resource type: {resource_type}"
                    }
                
                min_value = constraint_data.get("min_value", 0)
                max_value = constraint_data.get("max_value", self.available_resources[resource_type])
                priority = constraint_data.get("priority", 0)
                
                constraint_objects[resource_type] = ResourceConstraint(
                    resource_type, min_value, max_value, priority
                )
            
            # Create allocation
            allocation = ResourceAllocation(consumer_id, constraint_objects)
            self.allocations[consumer_id] = allocation
            
            # Update allocations
            self.update_allocations()
            
            # Notify callbacks
            self._notify_callbacks("allocation_added", {
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            })
            
            return {
                "success": True,
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            }
    
    def remove_allocation(self, consumer_id: str) -> Dict[str, Any]:
        """
        Remove a resource allocation
        
        Args:
            consumer_id: ID of the consumer
            
        Returns:
            Dictionary with removal status
        """
        with self.lock:
            if consumer_id not in self.allocations:
                return {
                    "success": False,
                    "error": f"No allocation found for consumer: {consumer_id}"
                }
            
            allocation = self.allocations.pop(consumer_id)
            
            # Update allocations
            self.update_allocations()
            
            # Notify callbacks
            self._notify_callbacks("allocation_removed", {
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            })
            
            return {
                "success": True,
                "consumer_id": consumer_id
            }
    
    def update_allocation(self, consumer_id: str, constraints: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update an existing resource allocation
        
        Args:
            consumer_id: ID of the consumer
            constraints: Dictionary of resource constraints to update
                
        Returns:
            Dictionary with update status
        """
        with self.lock:
            if consumer_id not in self.allocations:
                return {
                    "success": False,
                    "error": f"No allocation found for consumer: {consumer_id}"
                }
            
            allocation = self.allocations[consumer_id]
            
            # Update constraints
            for resource_type, constraint_data in constraints.items():
                if resource_type not in self.available_resources:
                    continue
                
                if resource_type in allocation.constraints:
                    # Update existing constraint
                    constraint = allocation.constraints[resource_type]
                    
                    if "min_value" in constraint_data:
                        constraint.min_value = constraint_data["min_value"]
                    
                    if "max_value" in constraint_data:
                        constraint.max_value = constraint_data["max_value"]
                    
                    if "priority" in constraint_data:
                        constraint.priority = constraint_data["priority"]
                else:
                    # Create new constraint
                    min_value = constraint_data.get("min_value", 0)
                    max_value = constraint_data.get("max_value", self.available_resources[resource_type])
                    priority = constraint_data.get("priority", 0)
                    
                    allocation.constraints[resource_type] = ResourceConstraint(
                        resource_type, min_value, max_value, priority
                    )
            
            # Update allocations
            self.update_allocations()
            
            # Notify callbacks
            self._notify_callbacks("allocation_updated", {
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            })
            
            return {
                "success": True,
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            }
    
    def get_allocation(self, consumer_id: str) -> Dict[str, Any]:
        """
        Get the current resource allocation for a consumer
        
        Args:
            consumer_id: ID of the consumer
            
        Returns:
            Dictionary with allocation info
        """
        with self.lock:
            if consumer_id not in self.allocations:
                return {
                    "success": False,
                    "error": f"No allocation found for consumer: {consumer_id}"
                }
            
            allocation = self.allocations[consumer_id]
            
            return {
                "success": True,
                "consumer_id": consumer_id,
                "allocation": allocation.to_dict()
            }
    
    def list_allocations(self) -> Dict[str, Any]:
        """
        List all resource allocations
        
        Returns:
            Dictionary with allocations list
        """
        with self.lock:
            allocations = []
            
            for consumer_id, allocation in self.allocations.items():
                allocations.append(allocation.to_dict())
            
            return {
                "success": True,
                "count": len(allocations),
                "allocations": allocations
            }
    
    def update_allocations(self) -> Dict[str, Any]:
        """
        Update all resource allocations based on priorities and current usage
        
        Returns:
            Dictionary with update status
        """
        with self.lock:
            if not self.prioritization_enabled:
                return {"success": True, "prioritization": False}
            
            # Get active allocations
            active_allocations = [a for a in self.allocations.values() if a.active]
            
            # No allocations to update
            if not active_allocations:
                return {"success": True, "allocations_updated": 0}
            
            # Process each resource type
            resources_updated = 0
            
            for resource_type, total_available in self.available_resources.items():
                # Get allocations with this resource type
                allocations_for_resource = [
                    a for a in active_allocations 
                    if resource_type in a.constraints
                ]
                
                if not allocations_for_resource:
                    continue
                
                # Sort by priority (higher priority first)
                allocations_for_resource.sort(
                    key=lambda a: a.constraints[resource_type].priority, reverse=True
                )
                
                # First pass: allocate minimum guaranteed resources
                remaining = total_available
                
                for allocation in allocations_for_resource:
                    constraint = allocation.constraints[resource_type]
                    min_value = constraint.min_value
                    
                    # Allocate minimum value
                    constraint.current_value = min_value
                    remaining -= min_value
                
                # Second pass: allocate remaining resources based on priority
                if remaining > 0:
                    for allocation in allocations_for_resource:
                        constraint = allocation.constraints[resource_type]
                        
                        # Calculate fair share based on priority
                        total_priority = sum(a.constraints[resource_type].priority 
                                            for a in allocations_for_resource)
                        
                        if total_priority > 0:
                            fair_share = (constraint.priority / total_priority) * remaining
                        else:
                            fair_share = remaining / len(allocations_for_resource)
                        
                        # Calculate new value, respecting maximum
                        new_value = min(constraint.min_value + fair_share, constraint.max_value)
                        
                        # Update constraint
                        constraint.current_value = new_value
                        remaining -= (new_value - constraint.min_value)
                        
                        if remaining <= 0:
                            break
                
                resources_updated += 1
            
            # Notify callbacks
            self._notify_callbacks("allocations_updated", {
                "resources_updated": resources_updated,
                "allocations_count": len(active_allocations)
            })
            
            return {
                "success": True,
                "resources_updated": resources_updated,
                "allocations_updated": len(active_allocations)
            }
    
    def set_prioritization(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable resource prioritization
        
        Args:
            enabled: Whether prioritization is enabled
            
        Returns:
            Dictionary with status
        """
        with self.lock:
            self.prioritization_enabled = enabled
            
            return {
                "success": True,
                "prioritization_enabled": enabled
            }
    
    def set_throttling(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable resource throttling
        
        Args:
            enabled: Whether throttling is enabled
            
        Returns:
            Dictionary with status
        """
        with self.lock:
            self.throttling_enabled = enabled
            
            return {
                "success": True,
                "throttling_enabled": enabled
            }
    
    def throttle_consumer(self, consumer_id: str, resource_type: str, value: float) -> Dict[str, Any]:
        """
        Throttle a specific consumer's resource usage
        
        Args:
            consumer_id: ID of the consumer
            resource_type: Type of resource to throttle
            value: Maximum allowed value
            
        Returns:
            Dictionary with throttle status
        """
        with self.lock:
            if not self.throttling_enabled:
                return {
                    "success": False,
                    "error": "Throttling is disabled"
                }
            
            if consumer_id not in self.allocations:
                return {
                    "success": False,
                    "error": f"No allocation found for consumer: {consumer_id}"
                }
            
            allocation = self.allocations[consumer_id]
            
            if resource_type not in allocation.constraints:
                return {
                    "success": False,
                    "error": f"No constraint for resource type: {resource_type}"
                }
            
            constraint = allocation.constraints[resource_type]
            old_max = constraint.max_value
            constraint.max_value = min(constraint.max_value, value)
            
            # Update allocation
            self.update_allocations()
            
            # Notify callbacks
            self._notify_callbacks("consumer_throttled", {
                "consumer_id": consumer_id,
                "resource_type": resource_type,
                "old_max": old_max,
                "new_max": constraint.max_value
            })
            
            return {
                "success": True,
                "consumer_id": consumer_id,
                "resource_type": resource_type,
                "old_max": old_max,
                "new_max": constraint.max_value
            }
    
    def get_available_resources(self) -> Dict[str, Any]:
        """
        Get available resources
        
        Returns:
            Dictionary with available resources
        """
        with self.lock:
            # Update available memory from system
            try:
                mem = psutil.virtual_memory()
                self.available_resources["memory"] = mem.total
            except:
                pass
            
            return {
                "success": True,
                "resources": self.available_resources.copy()
            }
    
    def update_available_resource(self, resource_type: str, value: float) -> Dict[str, Any]:
        """
        Update the available amount of a resource
        
        Args:
            resource_type: Type of resource
            value: New available value
            
        Returns:
            Dictionary with update status
        """
        with self.lock:
            if resource_type not in self.available_resources:
                return {
                    "success": False,
                    "error": f"Unknown resource type: {resource_type}"
                }
            
            old_value = self.available_resources[resource_type]
            self.available_resources[resource_type] = value
            
            # Update allocations
            self.update_allocations()
            
            return {
                "success": True,
                "resource_type": resource_type,
                "old_value": old_value,
                "new_value": value
            }
    
    def get_consumer_usage(self, consumer_id: str) -> Dict[str, Any]:
        """
        Get the current resource usage for a consumer
        
        Args:
            consumer_id: ID of the consumer
            
        Returns:
            Dictionary with usage info
        """
        # This would normally query the actual resource usage
        # Here we'll just return the allocation
        return self.get_allocation(consumer_id)
    
    def get_total_usage(self) -> Dict[str, Any]:
        """
        Get the total resource usage across all consumers
        
        Returns:
            Dictionary with total usage
        """
        with self.lock:
            # Calculate total usage per resource type
            total_usage = {resource_type: 0.0 for resource_type in self.available_resources}
            
            for allocation in self.allocations.values():
                if not allocation.active:
                    continue
                
                for resource_type, constraint in allocation.constraints.items():
                    if resource_type in total_usage:
                        total_usage[resource_type] += constraint.current_value
            
            # Calculate percentages
            percentages = {}
            for resource_type, usage in total_usage.items():
                available = self.available_resources[resource_type]
                if available > 0:
                    percentages[resource_type] = (usage / available) * 100
                else:
                    percentages[resource_type] = 0
            
            return {
                "success": True,
                "total_usage": total_usage,
                "available_resources": self.available_resources.copy(),
                "usage_percent": percentages
            }
    
    def set_update_interval(self, interval: float) -> Dict[str, Any]:
        """
        Set the update interval for background updates
        
        Args:
            interval: Update interval in seconds
            
        Returns:
            Dictionary with status
        """
        with self.lock:
            if interval <= 0:
                return {
                    "success": False,
                    "error": "Update interval must be positive"
                }
            
            self.update_interval = interval
            
            return {
                "success": True,
                "update_interval": interval
            }

# Create a singleton instance
resource_orchestrator = ResourceOrchestrator()

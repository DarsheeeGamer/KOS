"""
KOS PID Manager - Process ID allocation and management
"""

import threading
from typing import Optional, Set, Dict, Any
import random

class PIDManager:
    """
    Process ID manager for KOS
    Manages allocation and deallocation of PIDs
    """
    
    def __init__(self, max_pid: int = 32768):
        self.max_pid = max_pid
        self.next_pid = 1  # PID 0 reserved for kernel
        self.used_pids: Set[int] = {0}  # PID 0 is always used
        self.lock = threading.Lock()
        
        # PID recycling
        self.recycled_pids = []
        
        # Statistics
        self.total_allocated = 0
        self.total_freed = 0
        
    def alloc_pid(self) -> Optional[int]:
        """
        Allocate a new PID
        Returns None if no PIDs available
        """
        with self.lock:
            # Try recycled PIDs first
            if self.recycled_pids:
                pid = self.recycled_pids.pop(0)
                self.used_pids.add(pid)
                self.total_allocated += 1
                return pid
                
            # Find next available PID
            start_pid = self.next_pid
            
            while self.next_pid in self.used_pids:
                self.next_pid += 1
                
                # Wrap around if we reach max
                if self.next_pid >= self.max_pid:
                    self.next_pid = 1
                    
                # If we've checked all PIDs, no more available
                if self.next_pid == start_pid:
                    return None
                    
            pid = self.next_pid
            self.used_pids.add(pid)
            self.next_pid += 1
            
            # Wrap around
            if self.next_pid >= self.max_pid:
                self.next_pid = 1
                
            self.total_allocated += 1
            return pid
            
    def free_pid(self, pid: int) -> bool:
        """
        Free a PID for reuse
        """
        if pid == 0:  # Can't free kernel PID
            return False
            
        with self.lock:
            if pid in self.used_pids:
                self.used_pids.remove(pid)
                
                # Add to recycled list for later reuse
                if pid not in self.recycled_pids:
                    self.recycled_pids.append(pid)
                    
                self.total_freed += 1
                return True
                
        return False
        
    def is_pid_used(self, pid: int) -> bool:
        """Check if PID is currently in use"""
        with self.lock:
            return pid in self.used_pids
            
    def get_used_count(self) -> int:
        """Get number of PIDs in use"""
        with self.lock:
            return len(self.used_pids)
            
    def get_available_count(self) -> int:
        """Get number of available PIDs"""
        with self.lock:
            return self.max_pid - len(self.used_pids)
            
    def get_stats(self) -> Dict[str, Any]:
        """Get PID manager statistics"""
        with self.lock:
            return {
                'max_pid': self.max_pid,
                'used_pids': len(self.used_pids),
                'available_pids': self.max_pid - len(self.used_pids),
                'recycled_pids': len(self.recycled_pids),
                'total_allocated': self.total_allocated,
                'total_freed': self.total_freed,
                'next_pid': self.next_pid
            }
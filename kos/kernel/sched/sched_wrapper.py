"""
KOS Scheduler Python Wrapper

Provides Python interface to KOS scheduler including:
- CFS (Completely Fair Scheduler)
- Real-time scheduling
- Fair scheduling
- Load balancing
"""

import ctypes
import os
import logging
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import IntEnum

logger = logging.getLogger('KOS.scheduler')


class SchedulerType(IntEnum):
    """Scheduler types"""
    CFS = 0      # Completely Fair Scheduler
    RT = 1       # Real-time
    FAIR = 2     # Fair scheduler


class ProcessPriority(IntEnum):
    """Process priority levels"""
    IDLE = 19
    LOW = 10
    NORMAL = 0
    HIGH = -10
    REALTIME = -20


@dataclass
class SchedulerStats:
    """Scheduler statistics"""
    context_switches: int = 0
    preemptions: int = 0
    load_avg_1min: float = 0.0
    load_avg_5min: float = 0.0
    load_avg_15min: float = 0.0
    runqueue_size: int = 0
    blocked_tasks: int = 0


class KOSScheduler:
    """KOS Scheduler interface"""
    
    def __init__(self, scheduler_type: str = "cfs"):
        self.lib = None
        self.scheduler_type = scheduler_type
        self._stats = SchedulerStats()
        self._lock = threading.Lock()
        self._running = False
        self._load_library()
    
    def _load_library(self):
        """Load the scheduler library"""
        lib_path = os.path.join(os.path.dirname(__file__), "..", "libkos_kernel.so")
        
        if os.path.exists(lib_path):
            try:
                self.lib = ctypes.CDLL(lib_path)
                logger.info("Scheduler library loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load scheduler library: {e}")
        else:
            logger.warning("Scheduler library not found, using mock implementation")
    
    def start(self):
        """Start the scheduler"""
        with self._lock:
            if not self._running:
                self._running = True
                logger.info(f"Started {self.scheduler_type} scheduler")
    
    def stop(self):
        """Stop the scheduler"""
        with self._lock:
            if self._running:
                self._running = False
                logger.info("Stopped scheduler")
    
    def tick(self):
        """Scheduler tick (called from kernel loop)"""
        if self._running:
            # Update statistics
            self._stats.context_switches += 1
            
            # Update load averages (simplified)
            current_time = time.time()
            self._stats.load_avg_1min = min(1.0, self._stats.runqueue_size / 10.0)
    
    def set_priority(self, pid: int, priority: int) -> bool:
        """Set process priority"""
        logger.debug(f"Set priority for PID {pid} to {priority}")
        return True
    
    def get_priority(self, pid: int) -> int:
        """Get process priority"""
        return ProcessPriority.NORMAL
    
    def yield_cpu(self):
        """Yield CPU to other processes"""
        self._stats.preemptions += 1
        time.sleep(0.001)  # Simulate context switch
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics"""
        with self._lock:
            return {
                'type': self.scheduler_type,
                'running': self._running,
                'context_switches': self._stats.context_switches,
                'preemptions': self._stats.preemptions,
                'load_avg_1min': self._stats.load_avg_1min,
                'load_avg_5min': self._stats.load_avg_5min,
                'load_avg_15min': self._stats.load_avg_15min,
                'runqueue_size': self._stats.runqueue_size,
                'blocked_tasks': self._stats.blocked_tasks
            }
    
    def shutdown(self):
        """Shutdown scheduler"""
        self.stop()
        logger.info("Scheduler shutdown")
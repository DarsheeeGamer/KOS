"""
KOS Thread - Thread implementation for KOS
"""

import threading
import time
from typing import Optional, Any, Callable

from .process import KOSProcess

class KOSThread:
    """
    KOS Thread implementation
    Wrapper around Python threads for process threading
    """
    
    def __init__(self, process: KOSProcess, target: Callable = None, args: tuple = (), kwargs: dict = None):
        self.process = process
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.thread = None
        self.tid = None  # Thread ID
        
    def start(self):
        """Start the thread"""
        if not self.thread:
            self.thread = threading.Thread(
                target=self.target,
                args=self.args,
                kwargs=self.kwargs,
                name=f"{self.process.name}-thread"
            )
            self.thread.start()
            self.tid = self.thread.ident
            
    def join(self, timeout: Optional[float] = None):
        """Wait for thread to complete"""
        if self.thread:
            self.thread.join(timeout)
            
    def is_alive(self) -> bool:
        """Check if thread is alive"""
        return self.thread.is_alive() if self.thread else False
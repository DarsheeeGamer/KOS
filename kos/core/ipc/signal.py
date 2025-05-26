"""
KOS Signal IPC Implementation

Provides a signal mechanism for asynchronous communication between processes.
Implements proper signal delivery, handling and registration.
"""

import os
import time
import json
import threading
import signal
import uuid
import logging
import errno
from typing import Dict, Any, Optional, Union, Tuple, List, Callable

# Get module logger
logger = logging.getLogger('KOS.ipc.signal')

# Signal registry (maps process IDs to signal handlers)
_signal_handlers = {}

# KOS-specific signal definitions
class KOSSignal:
    """KOS signal constants"""
    # Standard POSIX signals
    SIGHUP = signal.SIGHUP          # 1: Hangup
    SIGINT = signal.SIGINT          # 2: Interrupt
    SIGQUIT = signal.SIGQUIT        # 3: Quit
    SIGILL = signal.SIGILL          # 4: Illegal instruction
    SIGTRAP = signal.SIGTRAP        # 5: Trace/breakpoint trap
    SIGABRT = signal.SIGABRT        # 6: Abort
    SIGBUS = signal.SIGBUS          # 7: Bus error
    SIGFPE = signal.SIGFPE          # 8: Floating point exception
    SIGKILL = signal.SIGKILL        # 9: Kill (cannot be caught or ignored)
    SIGUSR1 = signal.SIGUSR1        # 10: User-defined signal 1
    SIGSEGV = signal.SIGSEGV        # 11: Segmentation fault
    SIGUSR2 = signal.SIGUSR2        # 12: User-defined signal 2
    SIGPIPE = signal.SIGPIPE        # 13: Broken pipe
    SIGALRM = signal.SIGALRM        # 14: Alarm clock
    SIGTERM = signal.SIGTERM        # 15: Termination
    
    # KOS-specific signals (using high numbers to avoid conflict)
    SIGPROC = 64     # Process state change
    SIGMEM = 65      # Memory threshold reached
    SIGFS = 66       # Filesystem event
    SIGNET = 67      # Network event
    SIGIPC = 68      # IPC event
    SIGSYS = 69      # System event
    SIGTASK = 70     # Task completed
    SIGUSER = 71     # Custom user event


class SignalHandler:
    """
    Signal handler registration and management
    
    Tracks registered signal handlers for a process and
    provides an interface for delivering signals.
    """
    
    def __init__(self, pid):
        """
        Initialize a signal handler for a process
        
        Args:
            pid: Process ID
        """
        self.pid = pid
        self.handlers = {}  # Map of signal numbers to handler functions
        self.pending = {}   # Map of signal numbers to pending counts
        self.blocked = set() # Set of blocked signals
        self.lock = threading.RLock()
        self.created = time.time()
    
    def register_handler(self, signum, handler):
        """
        Register a handler for a signal
        
        Args:
            signum: Signal number
            handler: Handler function or None to reset to default
        
        Returns:
            Previous handler or None
        """
        with self.lock:
            previous = self.handlers.get(signum)
            
            if handler is None:
                # Reset to default
                if signum in self.handlers:
                    del self.handlers[signum]
            else:
                self.handlers[signum] = handler
            
            return previous
    
    def block_signal(self, signum):
        """
        Block a signal
        
        Args:
            signum: Signal number
        
        Returns:
            Success status
        """
        with self.lock:
            self.blocked.add(signum)
            return True
    
    def unblock_signal(self, signum):
        """
        Unblock a signal
        
        Args:
            signum: Signal number
        
        Returns:
            Success status
        """
        with self.lock:
            if signum in self.blocked:
                self.blocked.remove(signum)
            return True
    
    def is_blocked(self, signum):
        """
        Check if a signal is blocked
        
        Args:
            signum: Signal number
        
        Returns:
            Whether the signal is blocked
        """
        with self.lock:
            return signum in self.blocked
    
    def deliver_signal(self, signum, data=None):
        """
        Deliver a signal to the process
        
        Args:
            signum: Signal number
            data: Optional signal data
        
        Returns:
            Success status
        """
        with self.lock:
            # Check if signal is blocked
            if signum in self.blocked:
                # Add to pending signals
                self.pending[signum] = self.pending.get(signum, 0) + 1
                return True
            
            # Check if we have a handler
            if signum in self.handlers:
                handler = self.handlers[signum]
                
                try:
                    # Execute handler in a new thread to avoid blocking
                    def run_handler():
                        try:
                            handler(signum, data)
                        except Exception as e:
                            logger.error(f"Error in signal handler for process {self.pid}, signal {signum}: {e}")
                    
                    thread = threading.Thread(target=run_handler)
                    thread.daemon = True
                    thread.start()
                    
                    return True
                
                except Exception as e:
                    logger.error(f"Error delivering signal {signum} to process {self.pid}: {e}")
                    return False
            
            # No handler, use system default handler if applicable
            if signum in (KOSSignal.SIGKILL, KOSSignal.SIGTERM):
                from .. import process
                if process.process_exists(self.pid):
                    process.terminate_process(self.pid, force=signum == KOSSignal.SIGKILL)
                    return True
            
            # No handler and no default action
            return True
    
    def process_pending_signals(self):
        """
        Process any pending signals
        
        Returns:
            Number of signals processed
        """
        with self.lock:
            count = 0
            
            # Copy pending signals to avoid modification during iteration
            pending = dict(self.pending)
            
            for signum, num_pending in pending.items():
                # Check if still blocked
                if signum not in self.blocked:
                    # Process the signal
                    if signum in self.handlers:
                        handler = self.handlers[signum]
                        
                        try:
                            # Execute handler in a new thread to avoid blocking
                            def run_handler():
                                try:
                                    handler(signum, None)
                                except Exception as e:
                                    logger.error(f"Error in signal handler for process {self.pid}, signal {signum}: {e}")
                            
                            thread = threading.Thread(target=run_handler)
                            thread.daemon = True
                            thread.start()
                            
                            count += 1
                        
                        except Exception as e:
                            logger.error(f"Error processing pending signal {signum} for process {self.pid}: {e}")
                    
                    # Remove from pending
                    if signum in self.pending:
                        if self.pending[signum] > 1:
                            self.pending[signum] -= 1
                        else:
                            del self.pending[signum]
            
            return count


def register_signal_handler(pid: int, signum: int, handler: Callable) -> bool:
    """
    Register a handler for a signal
    
    Args:
        pid: Process ID
        signum: Signal number
        handler: Handler function (or None to reset to default)
    
    Returns:
        Success status
    """
    try:
        # Get or create signal handler for process
        if pid not in _signal_handlers:
            _signal_handlers[pid] = SignalHandler(pid)
        
        # Register handler
        _signal_handlers[pid].register_handler(signum, handler)
        
        logger.debug(f"Registered handler for signal {signum} in process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error registering signal handler for process {pid}, signal {signum}: {e}")
        return False


def block_signal(pid: int, signum: int) -> bool:
    """
    Block a signal for a process
    
    Args:
        pid: Process ID
        signum: Signal number
    
    Returns:
        Success status
    """
    try:
        # Get or create signal handler for process
        if pid not in _signal_handlers:
            _signal_handlers[pid] = SignalHandler(pid)
        
        # Block signal
        _signal_handlers[pid].block_signal(signum)
        
        logger.debug(f"Blocked signal {signum} for process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error blocking signal {signum} for process {pid}: {e}")
        return False


def unblock_signal(pid: int, signum: int) -> bool:
    """
    Unblock a signal for a process
    
    Args:
        pid: Process ID
        signum: Signal number
    
    Returns:
        Success status
    """
    try:
        # Check if process has a signal handler
        if pid not in _signal_handlers:
            return False
        
        # Unblock signal
        _signal_handlers[pid].unblock_signal(signum)
        
        # Process any pending signals
        _signal_handlers[pid].process_pending_signals()
        
        logger.debug(f"Unblocked signal {signum} for process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error unblocking signal {signum} for process {pid}: {e}")
        return False


def send_signal(pid: int, signum: int, data: Any = None) -> bool:
    """
    Send a signal to a process
    
    Args:
        pid: Process ID
        signum: Signal number
        data: Optional signal data
    
    Returns:
        Success status
    """
    try:
        # Check if process exists
        from .. import process
        if not process.process_exists(pid):
            logger.warning(f"Process {pid} not found")
            return False
        
        # Handle special cases for system signals that map to OS signals
        if signum in (KOSSignal.SIGKILL, KOSSignal.SIGTERM, KOSSignal.SIGINT):
            # Use OS-level signals for termination
            try:
                os.kill(pid, signum)
                return True
            except OSError as e:
                if e.errno == errno.ESRCH:  # No such process
                    logger.warning(f"Process {pid} not found")
                    return False
                else:
                    raise
        
        # Check if process has a signal handler
        if pid not in _signal_handlers:
            # No handler, but might be a system process
            # For now, just log a warning and return success
            logger.warning(f"No signal handler registered for process {pid}")
            return True
        
        # Deliver signal
        result = _signal_handlers[pid].deliver_signal(signum, data)
        
        if result:
            logger.debug(f"Sent signal {signum} to process {pid}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error sending signal {signum} to process {pid}: {e}")
        return False


def process_pending_signals(pid: int) -> int:
    """
    Process pending signals for a process
    
    Args:
        pid: Process ID
    
    Returns:
        Number of signals processed
    """
    try:
        # Check if process has a signal handler
        if pid not in _signal_handlers:
            return 0
        
        # Process pending signals
        count = _signal_handlers[pid].process_pending_signals()
        
        return count
    
    except Exception as e:
        logger.error(f"Error processing pending signals for process {pid}: {e}")
        return 0


def cleanup_process(pid: int) -> bool:
    """
    Clean up signal handlers for a terminated process
    
    Args:
        pid: Process ID
    
    Returns:
        Success status
    """
    try:
        # Check if process has a signal handler
        if pid in _signal_handlers:
            # Remove signal handler
            del _signal_handlers[pid]
            
            logger.debug(f"Cleaned up signal handlers for process {pid}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error cleaning up signal handlers for process {pid}: {e}")
        return False

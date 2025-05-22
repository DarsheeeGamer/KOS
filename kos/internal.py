"""
KOS Internal System Module
Provides core system-level functionality for the KOS environment
"""
import logging
import sys
import os
import signal
import traceback
from typing import Optional, Any, Callable

logger = logging.getLogger('KOS.internal')

class KOSSystemManager:
    """
    Manages system-level operations for KOS including:
    - Exit handling
    - Signal management
    - Shell lifecycle
    """
    
    def __init__(self):
        self.exit_handlers = []
        self.original_exit = sys.exit
        self.running = False
        self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Set up signal handlers to prevent unexpected termination"""
        if os.name != 'nt':  # For non-Windows systems
            signal.signal(signal.SIGINT, self._handle_interrupt)
            signal.signal(signal.SIGTERM, self._handle_terminate)
    
    def _handle_interrupt(self, signum, frame):
        """Handle interrupt signals (Ctrl+C)"""
        logger.warning("Interrupt signal received, ignoring to keep KOS running")
        print("\nInterrupt received. Use 'exit' command to exit KOS properly.")
        
    def _handle_terminate(self, signum, frame):
        """Handle termination signals"""
        logger.warning("Termination signal received, performing graceful shutdown")
        self.exit(1)
    
    def register_exit_handler(self, handler: Callable):
        """Register a function to be called when KOS exits"""
        if handler not in self.exit_handlers:
            self.exit_handlers.append(handler)
            
    def remove_exit_handler(self, handler: Callable):
        """Remove a previously registered exit handler"""
        if handler in self.exit_handlers:
            self.exit_handlers.remove(handler)
    
    def install_exit_hook(self):
        """Install the KOS exit hook to prevent direct system exits"""
        def kos_exit_hook(code=0):
            logger.warning(f"Application attempted to call sys.exit({code})")
            print("Use the 'exit' command to exit KOS properly.")
            return None
        
        # Save original exit and replace with our hook
        sys.exit = kos_exit_hook
        
    def restore_exit_hook(self):
        """Restore the original sys.exit function"""
        sys.exit = self.original_exit
        
    def start(self):
        """Mark the KOS system as running and install exit hooks"""
        self.running = True
        self.install_exit_hook()
        logger.info("KOS system started")
        
    def exit(self, code: int = 0):
        """Properly exit KOS with cleanup"""
        if not self.running:
            return
            
        logger.info(f"KOS exiting with code {code}")
        self.running = False
        
        # Run all registered exit handlers
        for handler in reversed(self.exit_handlers):
            try:
                handler()
            except Exception as e:
                logger.error(f"Error in exit handler: {str(e)}")
                logger.debug(traceback.format_exc())
        
        # Restore original exit function
        self.restore_exit_hook()
        
        # Now it's safe to exit
        print("Goodbye!")

# Create a global instance
system_manager = KOSSystemManager()

# Convenience functions
def exit(code: int = 0):
    """Properly exit KOS"""
    system_manager.exit(code)
    
def register_exit_handler(handler: Callable):
    """Register a function to be called when KOS exits"""
    system_manager.register_exit_handler(handler)
    
def remove_exit_handler(handler: Callable):
    """Remove a previously registered exit handler"""
    system_manager.remove_exit_handler(handler)
    
def start_system():
    """Start the KOS system and install exit hooks"""
    system_manager.start()

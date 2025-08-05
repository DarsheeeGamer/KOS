#!/usr/bin/env python3
"""
KADCM Systemd Service Wrapper
Provides proper systemd integration for KADCM daemon
"""

import os
import sys
import signal
import time
import logging
import argparse
import threading
from pathlib import Path

# Add KOS to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kos.kadcm.manager import KADCMManager
from kos.core.base import KernelBase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kadcm.service')

# Global manager instance
manager = None
kernel = None
shutdown_event = threading.Event()


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()
    
    if manager:
        manager.stop()
    
    # Notify systemd we're stopping
    try:
        import systemd.daemon
        systemd.daemon.notify("STOPPING=1")
    except ImportError:
        pass


def setup_service_environment():
    """Setup service runtime environment"""
    # Create required directories
    runtime_dirs = [
        "/var/run/kos/runtime/kadcm",
        "/var/lib/kos/kadcm",
        "/var/log/kos"
    ]
    
    for dir_path in runtime_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Set proper permissions
    os.chmod("/var/run/kos/runtime/kadcm", 0o750)
    os.chmod("/var/lib/kos/kadcm", 0o750)


def run_daemon():
    """Main daemon loop"""
    global manager, kernel
    
    logger.info("Starting KADCM daemon...")
    
    # Setup environment
    setup_service_environment()
    
    # Initialize kernel (minimal for service)
    kernel = KernelBase()
    
    # Create and start manager
    manager = KADCMManager(kernel)
    
    try:
        # Start manager
        if not manager.start():
            logger.error("Failed to start KADCM manager")
            return 1
        
        # Notify systemd we're ready
        try:
            import systemd.daemon
            systemd.daemon.notify("READY=1")
            logger.info("Notified systemd: ready")
        except ImportError:
            logger.warning("systemd module not available")
        
        # Send periodic watchdog notifications
        watchdog_interval = 30  # seconds
        last_watchdog = time.time()
        
        # Main loop
        while not shutdown_event.is_set():
            # Check manager health
            if not manager.is_running():
                logger.error("Manager stopped unexpectedly")
                break
            
            # Send watchdog notification
            if time.time() - last_watchdog > watchdog_interval:
                try:
                    import systemd.daemon
                    systemd.daemon.notify("WATCHDOG=1")
                except ImportError:
                    pass
                last_watchdog = time.time()
            
            # Sleep briefly
            shutdown_event.wait(1)
        
        logger.info("Daemon shutting down...")
        
    except Exception as e:
        logger.exception(f"Daemon error: {e}")
        return 1
    
    finally:
        # Cleanup
        if manager:
            manager.stop()
        
        # Notify systemd we're stopped
        try:
            import systemd.daemon
            systemd.daemon.notify("STOPPING=1")
        except ImportError:
            pass
    
    return 0


def main():
    """Service entry point"""
    parser = argparse.ArgumentParser(description="KADCM Systemd Service")
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='/etc/kos/kadcm.conf',
        help='Configuration file path'
    )
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)
    
    # Run daemon
    sys.exit(run_daemon())


if __name__ == "__main__":
    main()
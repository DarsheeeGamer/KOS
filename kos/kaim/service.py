#!/usr/bin/env python3
"""
KAIM Systemd Service Wrapper
Provides proper systemd integration for KAIM daemon
"""

import os
import sys
import signal
import time
import logging
import argparse
import threading
import socket
import select
import json
from pathlib import Path

# Add KOS to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kos.kaim.manager import KAIMManager
from kos.security.fingerprint import get_fingerprint_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kaim.service')

# Global manager instance
manager = None
shutdown_event = threading.Event()
server_socket = None


def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    shutdown_event.set()
    
    if server_socket:
        try:
            server_socket.close()
        except:
            pass


def setup_service_environment():
    """Setup service runtime environment"""
    # Create required directories
    runtime_dirs = [
        "/var/run/kos/runtime/kaim",
        "/var/lib/kaim",
        "/var/log/kos"
    ]
    
    for dir_path in runtime_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    # Set proper permissions
    os.chmod("/var/run/kos/runtime/kaim", 0o750)
    os.chmod("/var/lib/kaim", 0o750)
    
    # Check kernel module
    if not Path("/dev/kaim").exists():
        logger.error("/dev/kaim not found - is the kernel module loaded?")
        # Try to load it
        os.system("modprobe kaim")
        time.sleep(1)
        if not Path("/dev/kaim").exists():
            raise RuntimeError("KAIM kernel module not loaded")


def handle_client_request(client_socket, manager):
    """Handle a client request"""
    try:
        # Receive request
        data = client_socket.recv(4096)
        if not data:
            return
        
        # Parse request
        try:
            request = json.loads(data.decode('utf-8'))
        except:
            response = {"error": "Invalid JSON request"}
            client_socket.send(json.dumps(response).encode())
            return
        
        # Process request
        command = request.get("command")
        params = request.get("params", {})
        
        response = {}
        
        if command == "elevate":
            # Elevate privileges
            pid = params.get("pid", os.getpid())
            flags = params.get("flags", [])
            duration = params.get("duration", 900)
            
            success = manager.elevate_process(pid, flags, duration)
            response = {"success": success}
            
        elif command == "check_permission":
            # Check permission
            pid = params.get("pid", os.getpid())
            flag = params.get("flag")
            
            has_perm = manager.check_permission(pid, flag)
            response = {"has_permission": has_perm}
            
        elif command == "device_open":
            # Open device
            device = params.get("device")
            mode = params.get("mode", "r")
            app_name = params.get("app_name", "unknown")
            fingerprint = params.get("fingerprint", "")
            
            fd = manager.device_open(device, mode, app_name, fingerprint)
            response = {"fd": fd}
            
        elif command == "status":
            # Get status
            status = manager.get_status()
            response = {"status": status}
            
        else:
            response = {"error": f"Unknown command: {command}"}
        
        # Send response
        client_socket.send(json.dumps(response).encode())
        
    except Exception as e:
        logger.error(f"Error handling client request: {e}")
        try:
            error_response = {"error": str(e)}
            client_socket.send(json.dumps(error_response).encode())
        except:
            pass
    
    finally:
        client_socket.close()


def run_daemon():
    """Main daemon loop"""
    global manager, server_socket
    
    logger.info("Starting KAIM daemon...")
    
    # Setup environment
    setup_service_environment()
    
    # Initialize manager
    manager = KAIMManager()
    
    # Create Unix socket for IPC
    socket_path = "/var/run/kaim.sock"
    
    # Remove old socket if exists
    if os.path.exists(socket_path):
        os.unlink(socket_path)
    
    # Create socket
    server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server_socket.bind(socket_path)
    server_socket.listen(5)
    server_socket.setblocking(False)
    
    # Set socket permissions
    os.chmod(socket_path, 0o660)
    
    logger.info(f"Listening on {socket_path}")
    
    try:
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
            # Check for new connections
            readable, _, _ = select.select([server_socket], [], [], 1.0)
            
            if server_socket in readable:
                try:
                    client_socket, _ = server_socket.accept()
                    # Handle in thread for concurrency
                    client_thread = threading.Thread(
                        target=handle_client_request,
                        args=(client_socket, manager)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
            
            # Send watchdog notification
            if time.time() - last_watchdog > watchdog_interval:
                try:
                    import systemd.daemon
                    systemd.daemon.notify("WATCHDOG=1")
                except ImportError:
                    pass
                last_watchdog = time.time()
            
            # Log status periodically
            if int(time.time()) % 60 == 0:
                status = manager.get_status()
                logger.info(f"Status: {status}")
        
        logger.info("Daemon shutting down...")
        
    except Exception as e:
        logger.exception(f"Daemon error: {e}")
        return 1
    
    finally:
        # Cleanup
        if server_socket:
            server_socket.close()
        
        if os.path.exists(socket_path):
            os.unlink(socket_path)
        
        # Notify systemd we're stopped
        try:
            import systemd.daemon
            systemd.daemon.notify("STOPPING=1")
        except ImportError:
            pass
    
    return 0


def main():
    """Service entry point"""
    parser = argparse.ArgumentParser(description="KAIM Systemd Service")
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='/etc/kos/kaim.conf',
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
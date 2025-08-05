"""
KAIM Daemon - Userspace daemon managing kernel interface
"""

import os
import sys
import pwd
import grp
import socket
import threading
import logging
import json
import time
import struct
import fcntl
from typing import Dict, Optional, Callable, Any, Tuple
from pathlib import Path

from .protocol import KAIMProtocol, MessageType, RequestType, Message
from .device import DeviceManager
from .errors import KAIMError, KAIMPermissionError, KAIMAuthError
from ..security.fingerprint import FingerprintManager
from ..security.permissions import PermissionFlags, PermissionChecker
from ..security.rbac import RBACManager

logger = logging.getLogger('kaim')

# ioctl commands for /dev/kaim
KAIM_IOCTL_BASE = 0x4B41  # 'KA'
KAIM_IOCTL_ELEVATE = KAIM_IOCTL_BASE + 1
KAIM_IOCTL_STATUS = KAIM_IOCTL_BASE + 2
KAIM_IOCTL_SESSION = KAIM_IOCTL_BASE + 3
KAIM_IOCTL_DEVICE = KAIM_IOCTL_BASE + 4


class KAIMDaemon:
    """KAIM daemon managing application-kernel interface"""
    
    SOCKET_PATH = "/var/run/kaim.sock"
    DEVICE_PATH = "/dev/kaim"
    PID_FILE = "/var/run/kaim.pid"
    CONFIG_PATH = "/etc/kos/kaim.conf"
    
    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.device_fd: Optional[int] = None
        self.protocol = KAIMProtocol()
        
        # Managers
        self.device_manager = DeviceManager()
        self.fingerprint_manager = FingerprintManager()
        self.permission_checker = PermissionChecker()
        self.rbac_manager = RBACManager()
        
        # State
        self.running = False
        self.sessions: Dict[str, dict] = {}  # token -> session info
        self.handlers: Dict[RequestType, Callable] = {}
        
        # Configuration
        self.config = self._load_config()
        
        # Setup
        self._setup_handlers()
        self._check_privileges()
        
    def _load_config(self) -> dict:
        """Load daemon configuration"""
        if Path(self.CONFIG_PATH).exists():
            with open(self.CONFIG_PATH) as f:
                return json.load(f)
                
        # Default configuration
        return {
            "socket_permissions": 0o660,
            "socket_group": "kaim",
            "log_level": "INFO",
            "session_timeout": 3600,  # 1 hour
            "max_connections": 100,
            "device_whitelist": [],
            "audit_log": "/var/log/kaim.log"
        }
    
    def _check_privileges(self):
        """Check if daemon has required privileges"""
        # Must run as _kaim user
        try:
            kaim_user = pwd.getpwnam("_kaim")
            if os.getuid() != kaim_user.pw_uid:
                logger.error("KAIM daemon must run as _kaim user")
                sys.exit(1)
        except KeyError:
            logger.error("_kaim user not found")
            sys.exit(1)
        
        # Check group memberships
        required_groups = ["kaim", "disk", "netdev"]
        current_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
        
        for group in required_groups:
            if group not in current_groups:
                logger.warning(f"Not in {group} group - some features may not work")
    
    def _setup_handlers(self):
        """Setup request handlers"""
        self.handlers[RequestType.OPEN] = self._handle_open
        self.handlers[RequestType.CONTROL] = self._handle_control
        self.handlers[RequestType.ELEVATE] = self._handle_elevate
        self.handlers[RequestType.CLOSE] = self._handle_close
        self.handlers[RequestType.STATUS] = self._handle_status
        self.handlers[RequestType.AUTHENTICATE] = self._handle_authenticate
    
    def start(self):
        """Start KAIM daemon"""
        logger.info("Starting KAIM daemon")
        
        # Write PID file
        with open(self.PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        
        try:
            # Open kernel device
            self._open_device()
            
            # Create Unix socket
            self._create_socket()
            
            # Start main loop
            self.running = True
            self._main_loop()
            
        except Exception as e:
            logger.error(f"Failed to start daemon: {e}")
            self.stop()
            raise
    
    def stop(self):
        """Stop KAIM daemon"""
        logger.info("Stopping KAIM daemon")
        self.running = False
        
        # Close socket
        if self.socket:
            try:
                self.socket.close()
                os.unlink(self.SOCKET_PATH)
            except:
                pass
        
        # Close device
        if self.device_fd is not None:
            try:
                os.close(self.device_fd)
            except:
                pass
        
        # Remove PID file
        try:
            os.unlink(self.PID_FILE)
        except:
            pass
    
    def _open_device(self):
        """Open /dev/kaim kernel device"""
        try:
            self.device_fd = os.open(self.DEVICE_PATH, os.O_RDWR)
            logger.info(f"Opened {self.DEVICE_PATH}")
        except OSError as e:
            logger.error(f"Failed to open {self.DEVICE_PATH}: {e}")
            raise
    
    def _create_socket(self):
        """Create Unix domain socket"""
        # Remove existing socket
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
        
        # Create socket
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(self.SOCKET_PATH)
        self.socket.listen(self.config["max_connections"])
        
        # Set permissions
        os.chmod(self.SOCKET_PATH, self.config["socket_permissions"])
        
        # Set group
        try:
            group = grp.getgrnam(self.config["socket_group"])
            os.chown(self.SOCKET_PATH, -1, group.gr_gid)
        except:
            logger.warning(f"Could not set socket group to {self.config['socket_group']}")
        
        logger.info(f"Listening on {self.SOCKET_PATH}")
    
    def _main_loop(self):
        """Main daemon loop"""
        # Start session cleanup thread
        cleanup_thread = threading.Thread(target=self._session_cleanup_loop, daemon=True)
        cleanup_thread.start()
        
        while self.running:
            try:
                # Accept connection
                client_socket, _ = self.socket.accept()
                
                # Handle in separate thread
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                thread.start()
                
            except Exception as e:
                if self.running:
                    logger.error(f"Error in main loop: {e}")
    
    def _handle_client(self, client_socket: socket.socket):
        """Handle client connection"""
        peer_creds = None
        session_token = None
        
        try:
            # Get peer credentials
            peer_creds = self._get_peer_credentials(client_socket)
            logger.info(f"Client connected: PID={peer_creds['pid']}, UID={peer_creds['uid']}")
            
            while True:
                # Receive message
                msg = self._receive_message(client_socket)
                if not msg:
                    break
                
                # Process request
                response = self._process_request(msg, peer_creds, session_token)
                
                # Update session token if authenticated
                if msg.type == MessageType.REQUEST and \
                   msg.request_type == RequestType.AUTHENTICATE and \
                   response.success:
                    session_token = response.data.get("token")
                
                # Send response
                self._send_message(client_socket, response)
                
        except Exception as e:
            logger.error(f"Client handler error: {e}")
            
        finally:
            client_socket.close()
            
            # Clean up session
            if session_token and session_token in self.sessions:
                del self.sessions[session_token]
    
    def _get_peer_credentials(self, sock: socket.socket) -> dict:
        """Get credentials of connected process"""
        # Get peer credentials using SO_PEERCRED
        creds = sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        pid, uid, gid = struct.unpack("III", creds)
        
        # Get process info
        try:
            with open(f"/proc/{pid}/cmdline", 'r') as f:
                cmdline = f.read().replace('\0', ' ').strip()
        except:
            cmdline = "unknown"
        
        return {
            "pid": pid,
            "uid": uid,
            "gid": gid,
            "cmdline": cmdline
        }
    
    def _receive_message(self, sock: socket.socket) -> Optional[Message]:
        """Receive message from client"""
        try:
            # Read length (4 bytes)
            length_data = sock.recv(4)
            if not length_data:
                return None
                
            length = struct.unpack(">I", length_data)[0]
            
            # Read message data
            data = b""
            while len(data) < length:
                chunk = sock.recv(min(length - len(data), 4096))
                if not chunk:
                    return None
                data += chunk
            
            # Decode message
            return self.protocol.decode_message(data)
            
        except Exception as e:
            logger.error(f"Message receive error: {e}")
            return None
    
    def _send_message(self, sock: socket.socket, msg: Message):
        """Send message to client"""
        data = self.protocol.encode_message(msg)
        sock.sendall(struct.pack(">I", len(data)) + data)
    
    def _process_request(self, msg: Message, peer_creds: dict,
                        session_token: Optional[str]) -> Message:
        """Process client request"""
        if msg.type != MessageType.REQUEST:
            return self.protocol.create_error_response(
                msg.id, KAIMError.INVALID_REQUEST, "Not a request message"
            )
        
        # Get handler
        handler = self.handlers.get(msg.request_type)
        if not handler:
            return self.protocol.create_error_response(
                msg.id, KAIMError.UNKNOWN_REQUEST, 
                f"Unknown request type: {msg.request_type}"
            )
        
        # Check if authentication required
        if msg.request_type != RequestType.AUTHENTICATE and not session_token:
            return self.protocol.create_error_response(
                msg.id, KAIMError.AUTH_REQUIRED, "Authentication required"
            )
        
        # Verify session
        session = None
        if session_token:
            session = self.sessions.get(session_token)
            if not session or session["expires"] < time.time():
                return self.protocol.create_error_response(
                    msg.id, KAIMError.SESSION_EXPIRED, "Session expired"
                )
        
        try:
            # Call handler
            return handler(msg, peer_creds, session)
            
        except KAIMPermissionError as e:
            return self.protocol.create_error_response(
                msg.id, KAIMError.PERMISSION_DENIED, str(e)
            )
        except Exception as e:
            logger.error(f"Handler error: {e}")
            return self.protocol.create_error_response(
                msg.id, KAIMError.INTERNAL_ERROR, "Internal error"
            )
    
    def _handle_authenticate(self, msg: Message, peer_creds: dict,
                           session: Optional[dict]) -> Message:
        """Handle authentication request"""
        try:
            # Extract fingerprint
            fingerprint = msg.data.get("fingerprint")
            app_name = msg.data.get("app_name", "unknown")
            
            if not fingerprint:
                raise KAIMAuthError("No fingerprint provided")
            
            # Verify fingerprint
            if not self.fingerprint_manager.verify(fingerprint, "app"):
                raise KAIMAuthError("Invalid fingerprint")
            
            # Get app permissions from RBAC
            app_perms = self.rbac_manager.get_app_permissions(app_name, peer_creds["uid"])
            
            # Create session
            session_token = os.urandom(32).hex()
            self.sessions[session_token] = {
                "token": session_token,
                "app_name": app_name,
                "fingerprint": fingerprint,
                "peer_creds": peer_creds,
                "permissions": app_perms,
                "created": time.time(),
                "expires": time.time() + self.config["session_timeout"]
            }
            
            logger.info(f"Authenticated app {app_name} (PID={peer_creds['pid']})")
            
            # Log to audit
            self._audit_log("AUTH", peer_creds, {"app": app_name, "result": "success"})
            
            return self.protocol.create_response(
                msg.id,
                success=True,
                data={
                    "token": session_token,
                    "expires": self.sessions[session_token]["expires"],
                    "permissions": app_perms
                }
            )
            
        except Exception as e:
            self._audit_log("AUTH", peer_creds, {"app": app_name, "result": "failed", "error": str(e)})
            raise
    
    def _handle_open(self, msg: Message, peer_creds: dict,
                    session: dict) -> Message:
        """Handle device open request"""
        device = msg.data.get("device")
        mode = msg.data.get("mode", "r")
        
        # Check permission
        if not self._check_permission(session, PermissionFlags.KDEV):
            raise KAIMPermissionError("Missing KDEV permission")
        
        # Check device whitelist
        if self.config["device_whitelist"] and \
           device not in self.config["device_whitelist"]:
            raise KAIMPermissionError(f"Device {device} not in whitelist")
        
        # Perform kernel ioctl to open device
        request_data = struct.pack("64s4s", device.encode(), mode.encode())
        result = fcntl.ioctl(self.device_fd, KAIM_IOCTL_DEVICE, request_data)
        
        fd = struct.unpack("i", result[:4])[0]
        if fd < 0:
            raise KAIMError(f"Failed to open device {device}")
        
        # Log access
        self._audit_log("DEVICE_OPEN", peer_creds, {"device": device, "mode": mode})
        
        return self.protocol.create_response(
            msg.id,
            success=True,
            data={"fd": fd, "device": device}
        )
    
    def _handle_control(self, msg: Message, peer_creds: dict,
                       session: dict) -> Message:
        """Handle device control request"""
        device = msg.data.get("device")
        command = msg.data.get("command")
        params = msg.data.get("params", {})
        
        # Check permission
        if not self._check_permission(session, PermissionFlags.KDEV):
            raise KAIMPermissionError("Missing KDEV permission")
        
        # Execute device control
        result = self.device_manager.control_device(device, command, params)
        
        # Log control operation
        self._audit_log("DEVICE_CONTROL", peer_creds, {
            "device": device,
            "command": command,
            "result": "success" if result.get("success") else "failed"
        })
        
        return self.protocol.create_response(
            msg.id,
            success=True,
            data=result
        )
    
    def _handle_elevate(self, msg: Message, peer_creds: dict,
                       session: dict) -> Message:
        """Handle privilege elevation request"""
        target_pid = msg.data.get("pid", peer_creds["pid"])
        requested_flags = msg.data.get("flags", [])
        
        # Verify user has permission to elevate
        user_info = pwd.getpwuid(peer_creds["uid"])
        if not self.rbac_manager.can_elevate(user_info.pw_name, requested_flags):
            raise KAIMPermissionError("User cannot elevate to requested permissions")
        
        # Perform kernel ioctl to elevate
        flags_int = 0
        for flag in requested_flags:
            flags_int |= getattr(PermissionFlags, flag, 0)
        
        request_data = struct.pack("II", target_pid, flags_int)
        result = fcntl.ioctl(self.device_fd, KAIM_IOCTL_ELEVATE, request_data)
        
        # Log elevation
        self._audit_log("ELEVATE", peer_creds, {
            "target_pid": target_pid,
            "flags": requested_flags,
            "result": "success"
        })
        
        # Update session with elevated permissions
        session["elevated"] = True
        session["elevated_flags"] = requested_flags
        session["elevated_until"] = time.time() + 900  # 15 minutes
        
        return self.protocol.create_response(
            msg.id,
            success=True,
            data={
                "elevated": True,
                "flags": requested_flags,
                "expires": session["elevated_until"]
            }
        )
    
    def _handle_status(self, msg: Message, peer_creds: dict,
                      session: dict) -> Message:
        """Handle status request"""
        # Get daemon status via ioctl
        status_buf = bytearray(256)
        fcntl.ioctl(self.device_fd, KAIM_IOCTL_STATUS, status_buf)
        
        # Parse status
        status = {
            "daemon_version": __version__,
            "kernel_module": "loaded",
            "active_sessions": len(self.sessions),
            "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
        }
        
        return self.protocol.create_response(
            msg.id,
            success=True,
            data=status
        )
    
    def _handle_close(self, msg: Message, peer_creds: dict,
                     session: dict) -> Message:
        """Handle close request"""
        # Close any open resources for this session
        # This is handled when client disconnects
        
        return self.protocol.create_response(
            msg.id,
            success=True,
            data={"closed": True}
        )
    
    def _check_permission(self, session: dict, flag: PermissionFlags) -> bool:
        """Check if session has permission flag"""
        # Check base permissions
        if flag.name in session["permissions"]:
            return True
        
        # Check elevated permissions
        if session.get("elevated") and session.get("elevated_until", 0) > time.time():
            return flag.name in session.get("elevated_flags", [])
        
        return False
    
    def _session_cleanup_loop(self):
        """Periodic cleanup of expired sessions"""
        while self.running:
            time.sleep(60)  # Check every minute
            
            expired = []
            for token, session in self.sessions.items():
                if session["expires"] < time.time():
                    expired.append(token)
            
            for token in expired:
                logger.info(f"Cleaning up expired session for {self.sessions[token]['app_name']}")
                del self.sessions[token]
    
    def _audit_log(self, action: str, peer_creds: dict, details: dict):
        """Log to audit file"""
        try:
            log_entry = {
                "timestamp": time.time(),
                "action": action,
                "pid": peer_creds["pid"],
                "uid": peer_creds["uid"],
                "cmdline": peer_creds["cmdline"],
                "details": details
            }
            
            with open(self.config["audit_log"], 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
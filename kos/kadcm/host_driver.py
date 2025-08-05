"""
KADCM Host Driver - Runs on host OS to communicate with KOS
Full implementation for both Windows and Linux
"""

import os
import sys
import ssl
import socket
import struct
import threading
import time
import json
import yaml
import hashlib
import logging
import platform
import subprocess
from typing import Optional, Dict, Any, Callable, Tuple
from pathlib import Path
from queue import Queue, Empty
import select

if platform.system() == "Windows":
    import win32pipe
    import win32file
    import win32api
    import win32con
    import win32security
    import pywintypes

from .protocol import KADCMProtocol
from .messages import Message, MessageType, MessageFlags

logger = logging.getLogger('kadcm.host_driver')


class HostDriver:
    """Host-side driver for KADCM communication"""
    
    def __init__(self, kos_instance_id: str, host_fingerprint: str):
        self.kos_instance_id = kos_instance_id
        self.host_fingerprint = host_fingerprint
        self.protocol = KADCMProtocol()
        
        # Platform detection
        self.is_windows = platform.system() == "Windows"
        self.is_linux = platform.system() == "Linux"
        
        # Connection state
        self.connection = None
        self.connected = False
        self.session_id = None
        self.session_token = None
        
        # Configuration
        self.config = self._load_config()
        
        # Message handling
        self.response_queue = Queue()
        self.event_handlers: Dict[str, Callable] = {}
        self.pending_requests: Dict[str, threading.Event] = {}
        self.responses: Dict[str, Message] = {}
        
        # Threads
        self.receive_thread = None
        self.heartbeat_thread = None
        self.running = False
        
        # Security
        self.ssl_context = None
        self._setup_ssl()
        
    def _load_config(self) -> dict:
        """Load host driver configuration"""
        config_paths = [
            Path.home() / ".kos" / "kadcm_host.json",
            Path("/etc/kos/kadcm_host.json"),
            Path("C:\\ProgramData\\KOS\\kadcm_host.json")
        ]
        
        for path in config_paths:
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        
        # Default config
        return {
            "kos_pipe_path": self._get_default_pipe_path(),
            "cert_path": str(Path.home() / ".kos" / "certs" / "host.crt"),
            "key_path": str(Path.home() / ".kos" / "certs" / "host.key"),
            "ca_path": str(Path.home() / ".kos" / "certs" / "ca.crt"),
            "heartbeat_interval": 30,
            "connection_timeout": 10,
            "retry_attempts": 3,
            "retry_delay": 5
        }
    
    def _get_default_pipe_path(self) -> str:
        """Get default pipe path based on platform"""
        if self.is_windows:
            return r"\\.\pipe\kos\runtime\kadcm\kadcm"
        else:
            return "/var/run/kos/runtime/kadcm/kadcm.pipe"
    
    def _setup_ssl(self):
        """Setup SSL context"""
        self.ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        self.ssl_context.minimum_version = ssl.TLSVersion.TLSv1_3
        
        # Load certificates
        cert_path = Path(self.config["cert_path"])
        key_path = Path(self.config["key_path"])
        ca_path = Path(self.config["ca_path"])
        
        if cert_path.exists() and key_path.exists():
            self.ssl_context.load_cert_chain(str(cert_path), str(key_path))
        
        if ca_path.exists():
            self.ssl_context.load_verify_locations(str(ca_path))
        else:
            # For testing, allow self-signed
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
    
    def connect(self) -> bool:
        """Connect to KOS KADCM"""
        for attempt in range(self.config["retry_attempts"]):
            try:
                logger.info(f"Connecting to KOS (attempt {attempt + 1})")
                
                if self.is_windows:
                    self._connect_windows()
                else:
                    self._connect_unix()
                
                # Perform TLS handshake
                self._perform_handshake()
                
                # Authenticate
                if not self._authenticate():
                    self.disconnect()
                    continue
                
                # Start threads
                self.running = True
                self.receive_thread = threading.Thread(
                    target=self._receive_loop, daemon=True
                )
                self.receive_thread.start()
                
                self.heartbeat_thread = threading.Thread(
                    target=self._heartbeat_loop, daemon=True
                )
                self.heartbeat_thread.start()
                
                self.connected = True
                logger.info("Connected to KOS successfully")
                return True
                
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                if attempt < self.config["retry_attempts"] - 1:
                    time.sleep(self.config["retry_delay"])
        
        return False
    
    def _connect_windows(self):
        """Connect using Windows named pipe"""
        pipe_path = self.config["kos_pipe_path"]
        
        # Try to open existing pipe
        try:
            handle = win32file.CreateFile(
                pipe_path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,  # No sharing
                None,  # Default security
                win32file.OPEN_EXISTING,
                0,  # No special flags
                None  # No template
            )
            
            # Set pipe mode
            win32pipe.SetNamedPipeHandleState(
                handle,
                win32pipe.PIPE_READMODE_MESSAGE,
                None,
                None
            )
            
            # Create socket-like wrapper
            self.connection = WindowsPipeConnection(handle)
            
        except pywintypes.error as e:
            # Pipe doesn't exist, try TCP fallback
            logger.warning(f"Named pipe failed: {e}, trying TCP fallback")
            self._connect_tcp_fallback()
    
    def _connect_unix(self):
        """Connect using Unix domain socket"""
        pipe_path = self.config["kos_pipe_path"]
        
        # Create Unix socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.config["connection_timeout"])
        sock.connect(pipe_path)
        
        # Wrap with SSL
        self.connection = self.ssl_context.wrap_socket(
            sock, server_hostname="kadcm.kos.local"
        )
    
    def _connect_tcp_fallback(self):
        """TCP fallback for Windows"""
        # Try localhost ports
        for port in [9876, 9877, 9878]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config["connection_timeout"])
                sock.connect(("127.0.0.1", port))
                
                # Wrap with SSL
                self.connection = self.ssl_context.wrap_socket(
                    sock, server_hostname="kadcm.kos.local"
                )
                return
                
            except:
                continue
        
        raise ConnectionError("No available connection method")
    
    def _perform_handshake(self):
        """Perform TLS handshake"""
        if hasattr(self.connection, 'do_handshake'):
            self.connection.do_handshake()
    
    def _authenticate(self) -> bool:
        """Authenticate with KADCM"""
        try:
            # Wait for challenge
            challenge_msg = self._receive_message(timeout=5)
            if not challenge_msg or challenge_msg.type != MessageType.CONTROL:
                logger.error("No challenge received")
                return False
            
            challenge = bytes.fromhex(challenge_msg.body)
            
            # Create signature
            signature = hashlib.sha256(
                challenge + self.host_fingerprint.encode()
            ).hexdigest()
            
            # Send AUTH response
            auth_msg = self.protocol.create_auth_message(
                fingerprint=self.host_fingerprint,
                entity_id=platform.node(),
                entity_type="host",
                challenge_response=signature
            )
            
            self._send_message(auth_msg)
            
            # Wait for auth response
            response = self._wait_for_response(auth_msg.id, timeout=5)
            if response and response.header.get("status") == "already_authenticated":
                # Extract session info
                self.session_id = response.header.get("session_id")
                self.session_token = response.header.get("token")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from KOS"""
        self.running = False
        self.connected = False
        
        # Send close control message
        try:
            if self.connection and self.session_id:
                close_msg = Message(
                    type=MessageType.CONTROL,
                    id=self._generate_msg_id(),
                    priority=0,
                    flags=0,
                    header={"type": "close"},
                    body=""
                )
                self._send_message(close_msg)
        except:
            pass
        
        # Close connection
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
        
        # Wait for threads
        if self.receive_thread:
            self.receive_thread.join(timeout=1)
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=1)
        
        logger.info("Disconnected from KOS")
    
    def execute_command(self, command: str, args: list = None,
                       env: dict = None, cwd: str = None) -> Dict[str, Any]:
        """Execute command in KOS"""
        if not self.connected:
            raise ConnectionError("Not connected to KOS")
        
        # Create command message
        msg = self.protocol.create_command_message(
            command=command,
            args=args,
            env=env,
            cwd=cwd
        )
        
        # Send and wait for response
        self._send_message(msg)
        response = self._wait_for_response(msg.id)
        
        if not response:
            raise TimeoutError("Command execution timeout")
        
        if response.header.get("status") == "error":
            raise RuntimeError(f"Command failed: {response.body}")
        
        # Parse response
        result = yaml.safe_load(response.body)
        return {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "returncode": result.get("returncode", -1)
        }
    
    def read_file(self, file_path: str) -> str:
        """Read file from KOS"""
        if not self.connected:
            raise ConnectionError("Not connected to KOS")
        
        msg = self.protocol.create_data_message(
            operation="read",
            path=file_path
        )
        
        self._send_message(msg)
        response = self._wait_for_response(msg.id)
        
        if not response:
            raise TimeoutError("File read timeout")
        
        if response.header.get("status") == "error":
            raise IOError(f"Read failed: {response.body}")
        
        return response.body
    
    def write_file(self, file_path: str, content: str) -> bool:
        """Write file to KOS"""
        if not self.connected:
            raise ConnectionError("Not connected to KOS")
        
        msg = self.protocol.create_data_message(
            operation="write",
            path=file_path,
            content=content
        )
        
        self._send_message(msg)
        response = self._wait_for_response(msg.id)
        
        if not response:
            raise TimeoutError("File write timeout")
        
        return response.header.get("status") == "success"
    
    def list_processes(self) -> list:
        """List KOS processes"""
        result = self.execute_command("ps", ["-ef"])
        return result["stdout"].splitlines()
    
    def manage_service(self, service: str, action: str) -> bool:
        """Manage KOS service"""
        result = self.execute_command("systemctl", [action, service])
        return result["returncode"] == 0
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get KOS system information"""
        info = {}
        
        # Get various system info
        commands = {
            "hostname": ["hostname"],
            "uname": ["uname", "-a"],
            "uptime": ["uptime"],
            "memory": ["free", "-h"],
            "disk": ["df", "-h"]
        }
        
        for key, cmd in commands.items():
            try:
                result = self.execute_command(cmd[0], cmd[1:] if len(cmd) > 1 else None)
                info[key] = result["stdout"].strip()
            except:
                info[key] = "N/A"
        
        return info
    
    def install_package(self, package: str) -> bool:
        """Install package in KOS"""
        result = self.execute_command("kpm", ["install", "-y", package])
        return result["returncode"] == 0
    
    def set_event_handler(self, event_type: str, handler: Callable):
        """Set handler for async events"""
        self.event_handlers[event_type] = handler
    
    def _receive_loop(self):
        """Main receive loop"""
        while self.running:
            try:
                msg = self._receive_message(timeout=1)
                if not msg:
                    continue
                
                # Handle different message types
                if msg.type == MessageType.HEARTBEAT:
                    # Echo heartbeat
                    self._send_message(msg)
                    
                elif msg.type == MessageType.NOTIFY:
                    # Handle async notification
                    self._handle_notification(msg)
                    
                elif msg.type in [MessageType.COMMAND, MessageType.DATA, 
                                 MessageType.CONTROL, MessageType.ERROR]:
                    # Response to our request
                    if msg.id in self.pending_requests:
                        self.responses[msg.id] = msg
                        self.pending_requests[msg.id].set()
                
            except Exception as e:
                if self.running:
                    logger.error(f"Receive error: {e}")
    
    def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        interval = self.config["heartbeat_interval"]
        
        while self.running:
            try:
                # Send heartbeat
                hb_msg = self.protocol.create_heartbeat_message()
                self._send_message(hb_msg)
                
                # Wait for echo (with timeout)
                response = self._wait_for_response(hb_msg.id, timeout=5)
                if not response:
                    logger.warning("Heartbeat timeout")
                    # Handle connection loss
                    self.connected = False
                    self.authenticated = False
                    
                    # Try to reconnect
                    logger.info("Attempting to reconnect...")
                    try:
                        self.disconnect()
                        time.sleep(2)
                        if self.connect():
                            logger.info("Reconnected successfully")
                            # Re-authenticate if we have saved credentials
                            if hasattr(self, '_last_fingerprint'):
                                self.authenticate(
                                    fingerprint=self._last_fingerprint,
                                    entity_id=self._last_entity_id,
                                    entity_type=self._last_entity_type
                                )
                        else:
                            logger.error("Failed to reconnect")
                            self.running = False
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                        self.running = False
                
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
            
            time.sleep(interval)
    
    def _send_message(self, msg: Message):
        """Send message to KOS"""
        if not self.connection:
            raise ConnectionError("Not connected")
        
        data = self.protocol.encode_message(msg)
        
        if self.is_windows and isinstance(self.connection, WindowsPipeConnection):
            self.connection.write(data)
        else:
            self.connection.sendall(data)
    
    def _receive_message(self, timeout: Optional[float] = None) -> Optional[Message]:
        """Receive message from KOS"""
        if not self.connection:
            return None
        
        try:
            # Set timeout
            if hasattr(self.connection, 'settimeout'):
                self.connection.settimeout(timeout)
            
            # Read header
            if self.is_windows and isinstance(self.connection, WindowsPipeConnection):
                header_data = self.connection.read(5)
            else:
                header_data = self._recv_exact(5)
            
            if not header_data or len(header_data) < 5:
                return None
            
            length, flags = struct.unpack(">IB", header_data)
            
            # Read body
            if self.is_windows and isinstance(self.connection, WindowsPipeConnection):
                msg_data = self.connection.read(length)
            else:
                msg_data = self._recv_exact(length)
            
            if not msg_data or len(msg_data) < length:
                return None
            
            # Decode message
            return self.protocol.decode_message(header_data + msg_data)
            
        except (socket.timeout, TimeoutError):
            return None
        except Exception as e:
            logger.error(f"Receive error: {e}")
            return None
    
    def _recv_exact(self, size: int) -> bytes:
        """Receive exact amount of data"""
        data = b""
        while len(data) < size:
            chunk = self.connection.recv(size - len(data))
            if not chunk:
                break
            data += chunk
        return data
    
    def _wait_for_response(self, msg_id: str, timeout: float = 30) -> Optional[Message]:
        """Wait for response to specific message"""
        event = threading.Event()
        self.pending_requests[msg_id] = event
        
        try:
            if event.wait(timeout):
                return self.responses.pop(msg_id, None)
            return None
        finally:
            self.pending_requests.pop(msg_id, None)
    
    def _handle_notification(self, msg: Message):
        """Handle async notification"""
        try:
            notification = yaml.safe_load(msg.body)
            event_type = notification.get("event_type")
            
            handler = self.event_handlers.get(event_type)
            if handler:
                handler(notification)
            else:
                logger.info(f"Unhandled notification: {event_type}")
                
        except Exception as e:
            logger.error(f"Notification handling error: {e}")
    
    def _generate_msg_id(self) -> str:
        """Generate unique message ID"""
        return f"host-{int(time.time() * 1000)}-{os.urandom(4).hex()}"


class WindowsPipeConnection:
    """Windows named pipe connection wrapper"""
    
    def __init__(self, handle):
        self.handle = handle
        self.timeout = None
        
    def write(self, data: bytes) -> int:
        """Write data to pipe"""
        try:
            _, bytes_written = win32file.WriteFile(self.handle, data)
            return bytes_written
        except pywintypes.error as e:
            raise IOError(f"Pipe write error: {e}")
    
    def read(self, size: int) -> bytes:
        """Read data from pipe"""
        try:
            # Read available data
            _, data = win32file.ReadFile(self.handle, size)
            return data
        except pywintypes.error as e:
            if e.args[0] == 109:  # ERROR_BROKEN_PIPE
                return b""
            raise IOError(f"Pipe read error: {e}")
    
    def close(self):
        """Close pipe"""
        try:
            win32api.CloseHandle(self.handle)
        except:
            pass
    
    def settimeout(self, timeout: Optional[float]):
        """Set timeout (not fully implemented for pipes)"""
        self.timeout = timeout


# High-level API
class KOSConnection:
    """High-level API for host-KOS communication"""
    
    def __init__(self, kos_instance: str = "default"):
        self.kos_instance = kos_instance
        self.driver = None
        
    def connect(self, fingerprint: Optional[str] = None) -> bool:
        """Connect to KOS instance"""
        if not fingerprint:
            fingerprint = self._load_host_fingerprint()
        
        self.driver = HostDriver(self.kos_instance, fingerprint)
        return self.driver.connect()
    
    def disconnect(self):
        """Disconnect from KOS"""
        if self.driver:
            self.driver.disconnect()
    
    def execute(self, command: str, **kwargs) -> Dict[str, Any]:
        """Execute command in KOS"""
        if not self.driver:
            raise RuntimeError("Not connected")
        return self.driver.execute_command(command, **kwargs)
    
    def read_file(self, path: str) -> str:
        """Read file from KOS"""
        if not self.driver:
            raise RuntimeError("Not connected")
        return self.driver.read_file(path)
    
    def write_file(self, path: str, content: str) -> bool:
        """Write file to KOS"""
        if not self.driver:
            raise RuntimeError("Not connected")
        return self.driver.write_file(path, content)
    
    def _load_host_fingerprint(self) -> str:
        """Load or generate host fingerprint"""
        fingerprint_file = Path.home() / ".kos" / "host_fingerprint"
        
        if fingerprint_file.exists():
            return fingerprint_file.read_text().strip()
        
        # Generate new fingerprint
        import uuid
        fingerprint = hashlib.sha256(
            f"{platform.node()}-{uuid.getnode()}".encode()
        ).hexdigest()
        
        fingerprint_file.parent.mkdir(parents=True, exist_ok=True)
        fingerprint_file.write_text(fingerprint)
        
        return fingerprint
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()
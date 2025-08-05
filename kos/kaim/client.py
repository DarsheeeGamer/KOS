"""
KAIM Client Library - Application-side interface
"""

import os
import socket
import struct
import time
import threading
import logging
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path

from .protocol import KAIMProtocol, MessageType, RequestType, Message
from .errors import KAIMError, KAIMPermissionError, KAIMAuthError

logger = logging.getLogger('kaim.client')


class KAIMClient:
    """Client library for applications to interact with KAIM"""
    
    SOCKET_PATH = "/var/run/kaim.sock"
    
    def __init__(self, app_name: str, fingerprint: str):
        self.app_name = app_name
        self.fingerprint = fingerprint
        self.socket: Optional[socket.socket] = None
        self.protocol = KAIMProtocol()
        self.session_token: Optional[str] = None
        self.permissions: Dict[str, bool] = {}
        self.connected = False
        self._lock = threading.RLock()
        self._callbacks: Dict[str, Callable] = {}
        
    def connect(self) -> bool:
        """Connect to KAIM daemon"""
        with self._lock:
            if self.connected:
                return True
            
            try:
                # Create socket
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.socket.connect(self.SOCKET_PATH)
                
                # Authenticate
                if not self._authenticate():
                    self.disconnect()
                    return False
                
                self.connected = True
                logger.info(f"Connected to KAIM as {self.app_name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to connect to KAIM: {e}")
                return False
    
    def disconnect(self):
        """Disconnect from KAIM daemon"""
        with self._lock:
            if self.socket:
                try:
                    # Send close message
                    if self.connected and self.session_token:
                        self._send_request(RequestType.CLOSE, {})
                except:
                    pass
                
                try:
                    self.socket.close()
                except:
                    pass
                
                self.socket = None
            
            self.connected = False
            self.session_token = None
            self.permissions = {}
    
    def _authenticate(self) -> bool:
        """Authenticate with KAIM daemon"""
        try:
            response = self._send_request(RequestType.AUTHENTICATE, {
                "fingerprint": self.fingerprint,
                "app_name": self.app_name
            })
            
            if response.success:
                self.session_token = response.data.get("token")
                self.permissions = response.data.get("permissions", {})
                return True
            
            logger.error(f"Authentication failed: {response.error}")
            return False
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def kaim_device_open(self, device: str, mode: str = "r") -> int:
        """Open a device with permission checks"""
        if not self.connected:
            raise KAIMError("Not connected to KAIM")
        
        response = self._send_request(RequestType.OPEN, {
            "device": device,
            "mode": mode
        })
        
        if not response.success:
            raise KAIMError(f"Failed to open device: {response.error}")
        
        return response.data.get("fd")
    
    def kaim_device_control(self, device: str, command: str, 
                           params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Control a device"""
        if not self.connected:
            raise KAIMError("Not connected to KAIM")
        
        response = self._send_request(RequestType.CONTROL, {
            "device": device,
            "command": command,
            "params": params or {}
        })
        
        if not response.success:
            raise KAIMError(f"Device control failed: {response.error}")
        
        return response.data
    
    def kaim_process_elevate(self, pid: Optional[int] = None,
                            flags: Optional[List[str]] = None) -> bool:
        """Request privilege elevation for a process"""
        if not self.connected:
            raise KAIMError("Not connected to KAIM")
        
        request_data = {}
        if pid is not None:
            request_data["pid"] = pid
        if flags:
            request_data["flags"] = flags
        
        response = self._send_request(RequestType.ELEVATE, request_data)
        
        if not response.success:
            if "PERMISSION_DENIED" in response.error:
                raise KAIMPermissionError(response.error)
            raise KAIMError(f"Elevation failed: {response.error}")
        
        # Update local permissions
        if flags:
            for flag in flags:
                self.permissions[flag] = True
        
        return True
    
    def kaim_get_status(self) -> Dict[str, Any]:
        """Get KAIM daemon status"""
        if not self.connected:
            raise KAIMError("Not connected to KAIM")
        
        response = self._send_request(RequestType.STATUS, {})
        
        if not response.success:
            raise KAIMError(f"Status request failed: {response.error}")
        
        return response.data
    
    def kaim_check_permission(self, flag: str) -> bool:
        """Check if we have a specific permission"""
        return self.permissions.get(flag, False)
    
    def kaim_list_permissions(self) -> List[str]:
        """List all permissions granted to this app"""
        return [k for k, v in self.permissions.items() if v]
    
    def kaim_set_callback(self, event: str, callback: Callable):
        """Set callback for events (future feature)"""
        self._callbacks[event] = callback
    
    def _send_request(self, request_type: RequestType, 
                     data: Dict[str, Any]) -> Message:
        """Send request and wait for response"""
        if not self.socket:
            raise KAIMError("Not connected")
        
        # Create request
        request = self.protocol.create_request(
            request_type=request_type,
            data=data
        )
        
        # Send message
        self._send_message(request)
        
        # Receive response
        response = self._receive_message()
        if not response:
            raise KAIMError("No response from daemon")
        
        return response
    
    def _send_message(self, msg: Message):
        """Send message to daemon"""
        data = self.protocol.encode_message(msg)
        self.socket.sendall(struct.pack(">I", len(data)) + data)
    
    def _receive_message(self) -> Optional[Message]:
        """Receive message from daemon"""
        try:
            # Read length
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            
            length = struct.unpack(">I", length_data)[0]
            
            # Read data
            data = b""
            while len(data) < length:
                chunk = self.socket.recv(min(length - len(data), 4096))
                if not chunk:
                    return None
                data += chunk
            
            return self.protocol.decode_message(data)
            
        except Exception as e:
            logger.error(f"Receive error: {e}")
            return None
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.disconnect()


# C-style wrapper functions for compatibility
_global_client: Optional[KAIMClient] = None


def kaim_init(app_name: str, fingerprint: str) -> bool:
    """Initialize KAIM client (C-style API)"""
    global _global_client
    try:
        _global_client = KAIMClient(app_name, fingerprint)
        return _global_client.connect()
    except:
        return False


def kaim_cleanup():
    """Cleanup KAIM client (C-style API)"""
    global _global_client
    if _global_client:
        _global_client.disconnect()
        _global_client = None


def kaim_device_open(device: str, mode: str = "r") -> int:
    """Open device (C-style API)"""
    if not _global_client:
        return -1
    try:
        return _global_client.kaim_device_open(device, mode)
    except:
        return -1


def kaim_device_control(device: str, command: str, params: dict = None) -> dict:
    """Control device (C-style API)"""
    if not _global_client:
        return {"success": False, "error": "Not initialized"}
    try:
        return _global_client.kaim_device_control(device, command, params)
    except Exception as e:
        return {"success": False, "error": str(e)}


def kaim_process_elevate(pid: int = 0, flags: list = None) -> bool:
    """Elevate process privileges (C-style API)"""
    if not _global_client:
        return False
    try:
        return _global_client.kaim_process_elevate(
            pid if pid > 0 else None, flags
        )
    except:
        return False


def kaim_get_status() -> dict:
    """Get status (C-style API)"""
    if not _global_client:
        return {}
    try:
        return _global_client.kaim_get_status()
    except:
        return {}
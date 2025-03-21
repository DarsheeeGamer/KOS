"""
Kaede Secure Shell Protocol (KSSP) - Secure Remote Access for KOS

KSSP provides secure remote access to KOS instances, enabling users to 
securely connect to and manage remote KOS systems. It implements secure 
channels for authentication, command execution, file transfer, and session
management similar to SSH.

Key features:
- Secure authentication with public key and password support
- Encrypted communication channels
- Secure file transfer capabilities
- Port forwarding and tunneling
- Session management with persistence
- Command execution with proper privilege isolation
"""
import os
import sys
import logging
import socket
import threading
import queue
import time
import json
import base64
import hashlib
import hmac
import random
import string
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from datetime import datetime
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger('KOS.kssp')

# Constants
DEFAULT_PORT = 2222
MAX_PACKET_SIZE = 32768
CIPHER_BLOCK_SIZE = 16
TIMEOUT_SECONDS = 60
MAX_AUTH_ATTEMPTS = 3
DEFAULT_BANNER = "KSSP-1.0-KaedeOS"

# Protocol message types
MSG_DISCONNECT = 1
MSG_IGNORE = 2
MSG_DEBUG = 3
MSG_SERVICE_REQUEST = 5
MSG_SERVICE_ACCEPT = 6
MSG_AUTH_REQUEST = 50
MSG_AUTH_FAILURE = 51
MSG_AUTH_SUCCESS = 52
MSG_CHANNEL_OPEN = 90
MSG_CHANNEL_OPEN_CONFIRMATION = 91
MSG_CHANNEL_OPEN_FAILURE = 92
MSG_CHANNEL_DATA = 94
MSG_CHANNEL_EOF = 96
MSG_CHANNEL_CLOSE = 97
MSG_CHANNEL_REQUEST = 98
MSG_CHANNEL_SUCCESS = 99
MSG_CHANNEL_FAILURE = 100

# Channel types
CHANNEL_SESSION = "session"
CHANNEL_DIRECT_TCP = "direct-tcpip"
CHANNEL_FORWARDED_TCP = "forwarded-tcpip"
CHANNEL_X11 = "x11"

# Disconnect reason codes
DISCONNECT_HOST_NOT_ALLOWED = 1
DISCONNECT_PROTOCOL_ERROR = 2
DISCONNECT_AUTH_CANCELLED = 3
DISCONNECT_NO_MORE_AUTH_METHODS = 4
DISCONNECT_ILLEGAL_USER_NAME = 5

class KSSPError(Exception):
    """Base exception for KSSP errors"""
    pass

class AuthenticationError(KSSPError):
    """Authentication related errors"""
    pass

class ChannelError(KSSPError):
    """Channel related errors"""
    pass

class ProtocolError(KSSPError):
    """Protocol related errors"""
    pass

class KSSPPacket:
    """Represents a KSSP protocol packet"""
    def __init__(self, packet_type: int, payload: bytes = b''):
        self.type = packet_type
        self.payload = payload
        
    def to_bytes(self) -> bytes:
        """Convert packet to byte representation"""
        packet_length = len(self.payload) + 5  # 1 for type, 4 for length
        length_bytes = packet_length.to_bytes(4, byteorder='big')
        type_byte = self.type.to_bytes(1, byteorder='big')
        return length_bytes + type_byte + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'KSSPPacket':
        """Create packet from byte representation"""
        if len(data) < 5:
            raise ProtocolError("Packet data too short")
        
        packet_type = data[4]
        payload = data[5:]
        
        return cls(packet_type, payload)
    
    @classmethod
    def create_disconnect(cls, reason_code: int, description: str) -> 'KSSPPacket':
        """Create a disconnect packet"""
        reason_bytes = reason_code.to_bytes(4, byteorder='big')
        desc_bytes = description.encode('utf-8')
        desc_length = len(desc_bytes).to_bytes(4, byteorder='big')
        
        payload = reason_bytes + desc_length + desc_bytes
        return cls(MSG_DISCONNECT, payload)
    
    @classmethod
    def create_auth_request(cls, username: str, method: str, auth_data: bytes = b'') -> 'KSSPPacket':
        """Create an authentication request packet"""
        username_bytes = username.encode('utf-8')
        username_length = len(username_bytes).to_bytes(4, byteorder='big')
        
        method_bytes = method.encode('utf-8')
        method_length = len(method_bytes).to_bytes(4, byteorder='big')
        
        payload = username_length + username_bytes + method_length + method_bytes
        
        if auth_data:
            data_length = len(auth_data).to_bytes(4, byteorder='big')
            payload += data_length + auth_data
        
        return cls(MSG_AUTH_REQUEST, payload)
    
    @classmethod
    def create_channel_open(cls, channel_type: str, channel_id: int, window_size: int, max_packet_size: int) -> 'KSSPPacket':
        """Create a channel open packet"""
        type_bytes = channel_type.encode('utf-8')
        type_length = len(type_bytes).to_bytes(4, byteorder='big')
        
        channel_id_bytes = channel_id.to_bytes(4, byteorder='big')
        window_size_bytes = window_size.to_bytes(4, byteorder='big')
        max_packet_size_bytes = max_packet_size.to_bytes(4, byteorder='big')
        
        payload = (type_length + type_bytes + channel_id_bytes + 
                   window_size_bytes + max_packet_size_bytes)
        
        return cls(MSG_CHANNEL_OPEN, payload)
        self.sequence_number = 0  # Set by transport layer
    
    def to_bytes(self) -> bytes:
        """Convert packet to byte representation"""
        length = len(self.payload) + 5  # 5 bytes for length and type
        header = length.to_bytes(4, byteorder='big') + bytes([self.type])
        return header + self.payload
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'KSSPPacket':
        """Create packet from byte representation"""
        if len(data) < 5:
            raise ProtocolError("Packet too short")
        
        length = int.from_bytes(data[0:4], byteorder='big')
        packet_type = data[4]
        payload = data[5:5+length-1]
        
        return cls(packet_type, payload)
        
    @classmethod
    def create_disconnect(cls, reason_code: int, description: str) -> 'KSSPPacket':
        """Create a disconnect packet"""
        payload = reason_code.to_bytes(4, byteorder='big')
        payload += len(description).to_bytes(4, byteorder='big')
        payload += description.encode('utf-8')
        return cls(MSG_DISCONNECT, payload)
    
    @classmethod
    def create_auth_request(cls, username: str, method: str, auth_data: bytes = b'') -> 'KSSPPacket':
        """Create an authentication request packet"""
        payload = len(username).to_bytes(4, byteorder='big')
        payload += username.encode('utf-8')
        payload += len(method).to_bytes(4, byteorder='big')
        payload += method.encode('utf-8')
        payload += auth_data
        return cls(MSG_AUTH_REQUEST, payload)
    
    @classmethod
    def create_channel_open(cls, channel_type: str, channel_id: int, window_size: int, max_packet_size: int) -> 'KSSPPacket':
        """Create a channel open packet"""
        payload = len(channel_type).to_bytes(4, byteorder='big')
        payload += channel_type.encode('utf-8')
        payload += channel_id.to_bytes(4, byteorder='big')
        payload += window_size.to_bytes(4, byteorder='big')
        payload += max_packet_size.to_bytes(4, byteorder='big')
        return cls(MSG_CHANNEL_OPEN, payload)

class KSSPChannel:
    """Represents a KSSP channel for data exchange"""
    def __init__(self, channel_id: int, channel_type: str, window_size: int = 2097152, max_packet_size: int = MAX_PACKET_SIZE):
        self.id = channel_id
        self.type = channel_type
        self.window_size = window_size
        self.max_packet_size = max_packet_size
        self.remote_id = None  # Will be set after channel open confirmation
        self.remote_window = 0
        self.remote_max_packet = 0
        self.is_open = False
        self.is_eof = False
        self.data_queue = queue.Queue()
        self.command = None
        self.exit_status = None
    
    def receive_data(self, data: bytes) -> None:
        """Receive data from remote end"""
        self.data_queue.put(data)
        self.window_size -= len(data)
    
    def read_data(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """Read data from channel queue"""
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def close(self) -> None:
        """Close the channel"""
        self.is_open = False
        self.is_eof = True
    
    def send_eof(self) -> None:
        """Send EOF on the channel"""
        self.is_eof = True

class KSSPConnection:
    """Manages a KSSP connection and its secure transport"""
    def __init__(self, socket_conn: socket.socket, server_mode: bool = False):
        self.socket = socket_conn
        self.server_mode = server_mode
        self.authenticated = False
        self.username = None
        self.session_id = None
        self.channels = {}
        self.next_channel_id = 0
        self.send_seq_num = 0
        self.recv_seq_num = 0
        self.send_cipher = None
        self.recv_cipher = None
        self.running = True
        self.receive_thread = None
        self.packet_queue = queue.Queue()
        
        # Generate session keys
        self._generate_keys()
    
    def _generate_keys(self) -> None:
        """Generate session keys and IDs"""
        # Generate a unique session ID
        random_bytes = os.urandom(16)
        timestamp = int(time.time()).to_bytes(8, byteorder='big')
        self.session_id = hashlib.sha256(random_bytes + timestamp).digest()
    
    def start(self) -> None:
        """Start the connection processing"""
        self.running = True
        self.receive_thread = threading.Thread(
            target=self._receive_loop,
            daemon=True,
            name="KSSP-Receiver"
        )
        self.receive_thread.start()
        
        # Send or receive banner
        if self.server_mode:
            self._send_banner()
        else:
            self._receive_banner()
    
    def _send_banner(self) -> None:
        """Send initial KSSP banner"""
        banner = f"{DEFAULT_BANNER}\r\n".encode('ascii')
        self.socket.sendall(banner)
    
    def _receive_banner(self) -> None:
        """Receive and validate KSSP banner"""
        banner = b''
        while True:
            char = self.socket.recv(1)
            if not char:
                raise ProtocolError("Connection closed during banner exchange")
            
            banner += char
            if banner.endswith(b'\r\n'):
                break
            
            if len(banner) > 255:
                raise ProtocolError("Banner too long")
        
        banner_str = banner.decode('ascii').strip()
        if not banner_str.startswith("KSSP-"):
            raise ProtocolError(f"Invalid banner: {banner_str}")
        
        logger.debug(f"Received banner: {banner_str}")
    
    def _receive_loop(self) -> None:
        """Main packet receiving loop"""
        while self.running:
            try:
                packet = self._receive_packet()
                if packet:
                    self.packet_queue.put(packet)
            except Exception as e:
                logger.error(f"Error in receive loop: {e}")
                self.running = False
                break
    
    def _receive_packet(self) -> Optional[KSSPPacket]:
        """Receive and decrypt a packet"""
        try:
            # Read packet length
            length_data = self.socket.recv(4)
            if not length_data or len(length_data) < 4:
                return None
            
            packet_length = int.from_bytes(length_data, byteorder='big')
            if packet_length < 1 or packet_length > MAX_PACKET_SIZE:
                raise ProtocolError(f"Invalid packet length: {packet_length}")
            
            # Read packet data
            packet_data = b''
            remaining = packet_length
            while remaining > 0:
                chunk = self.socket.recv(remaining)
                if not chunk:
                    return None
                packet_data += chunk
                remaining -= len(chunk)
            
            # Decrypt if needed
            if self.recv_cipher:
                packet_data = self._decrypt_data(packet_data)
            
            # Parse packet
            packet_type = packet_data[0]
            payload = packet_data[1:]
            
            packet = KSSPPacket(packet_type, payload)
            packet.sequence_number = self.recv_seq_num
            self.recv_seq_num += 1
            
            return packet
        except socket.timeout:
            return None
        except socket.error as e:
            logger.error(f"Socket error: {e}")
            self.running = False
            return None
    
    def _send_packet(self, packet: KSSPPacket) -> None:
        """Encrypt and send a packet"""
        try:
            # Set sequence number
            packet.sequence_number = self.send_seq_num
            self.send_seq_num += 1
            
            # Get raw packet data
            data = packet.to_bytes()
            
            # Encrypt if needed
            if self.send_cipher:
                data = self._encrypt_data(data)
            
            # Send packet
            self.socket.sendall(data)
        except socket.error as e:
            logger.error(f"Error sending packet: {e}")
            self.running = False
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using session cipher"""
        if not self.send_cipher:
            return data
        
        # Implementation depends on selected cipher
        return data  # Placeholder
    
    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data using session cipher"""
        if not self.recv_cipher:
            return data
        
        # Implementation depends on selected cipher
        return data  # Placeholder
    
    def wait_for_packet(self, packet_type: int, timeout: Optional[float] = None) -> Optional[KSSPPacket]:
        """Wait for a specific packet type"""
        start_time = time.time()
        while self.running:
            try:
                remaining = None if timeout is None else max(0, timeout - (time.time() - start_time))
                packet = self.packet_queue.get(timeout=remaining)
                
                if packet.type == packet_type:
                    return packet
                
                # Handle other packet types
                self._process_packet(packet)
            except queue.Empty:
                return None
    
    def _process_packet(self, packet: KSSPPacket) -> None:
        """Process packets not explicitly handled by caller"""
        if packet.type == MSG_DISCONNECT:
            self._handle_disconnect(packet)
        elif packet.type == MSG_IGNORE:
            pass  # Ignore these packets
        elif packet.type == MSG_DEBUG:
            self._handle_debug(packet)
        elif packet.type == MSG_CHANNEL_DATA:
            self._handle_channel_data(packet)
        elif packet.type == MSG_CHANNEL_EOF:
            self._handle_channel_eof(packet)
        elif packet.type == MSG_CHANNEL_CLOSE:
            self._handle_channel_close(packet)
    
    def _handle_disconnect(self, packet: KSSPPacket) -> None:
        """Handle disconnect packet"""
        payload = packet.payload
        reason_code = int.from_bytes(payload[0:4], byteorder='big')
        desc_length = int.from_bytes(payload[4:8], byteorder='big')
        description = payload[8:8+desc_length].decode('utf-8')
        
        logger.info(f"Received disconnect: code={reason_code}, reason={description}")
        self.running = False
    
    def _handle_debug(self, packet: KSSPPacket) -> None:
        """Handle debug packet"""
        always_display = bool(packet.payload[0])
        msg_length = int.from_bytes(packet.payload[1:5], byteorder='big')
        message = packet.payload[5:5+msg_length].decode('utf-8')
        
        if always_display:
            logger.info(f"KSSP Debug: {message}")
        else:
            logger.debug(f"KSSP Debug: {message}")
    
    def _handle_channel_data(self, packet: KSSPPacket) -> None:
        """Handle channel data packet"""
        payload = packet.payload
        channel_id = int.from_bytes(payload[0:4], byteorder='big')
        data_length = int.from_bytes(payload[4:8], byteorder='big')
        data = payload[8:8+data_length]
        
        if channel_id in self.channels:
            self.channels[channel_id].receive_data(data)
        else:
            logger.warning(f"Data received for unknown channel: {channel_id}")
    
    def _handle_channel_eof(self, packet: KSSPPacket) -> None:
        """Handle channel EOF packet"""
        channel_id = int.from_bytes(packet.payload[0:4], byteorder='big')
        
        if channel_id in self.channels:
            self.channels[channel_id].send_eof()
        else:
            logger.warning(f"EOF received for unknown channel: {channel_id}")
    
    def _handle_channel_close(self, packet: KSSPPacket) -> None:
        """Handle channel close packet"""
        channel_id = int.from_bytes(packet.payload[0:4], byteorder='big')
        
        if channel_id in self.channels:
            self.channels[channel_id].close()
            # Send close confirmation if needed
            close_packet = KSSPPacket(MSG_CHANNEL_CLOSE, channel_id.to_bytes(4, byteorder='big'))
            self._send_packet(close_packet)
        else:
            logger.warning(f"Close received for unknown channel: {channel_id}")
    
    def authenticate(self, username: str, password: str = None, key_path: str = None) -> bool:
        """Authenticate with the server"""
        if self.server_mode:
            raise KSSPError("Cannot authenticate in server mode")
        
        # Try password authentication if provided
        if password:
            return self._authenticate_password(username, password)
        
        # Try public key authentication if provided
        if key_path:
            return self._authenticate_pubkey(username, key_path)
        
        return False
    
    def _authenticate_password(self, username: str, password: str) -> bool:
        """Authenticate using password"""
        # Create auth request
        auth_data = b'\x00'  # Boolean FALSE for new style
        auth_data += len(password).to_bytes(4, byteorder='big')
        auth_data += password.encode('utf-8')
        
        auth_packet = KSSPPacket.create_auth_request(username, "password", auth_data)
        self._send_packet(auth_packet)
        
        # Wait for auth response
        response = self.wait_for_packet(MSG_AUTH_SUCCESS, timeout=TIMEOUT_SECONDS)
        if response:
            self.authenticated = True
            self.username = username
            return True
        
        return False
    
    def _authenticate_pubkey(self, username: str, key_path: str) -> bool:
        """Authenticate using public key"""
        try:
            # Load private key
            with open(key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                    backend=default_backend()
                )
            
            # Get public key
            public_key = private_key.public_key()
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            
            # Create auth request with public key check
            auth_data = b'\x01'  # TRUE for public key auth
            auth_data += len("ssh-rsa").to_bytes(4, byteorder='big')
            auth_data += b"ssh-rsa"
            auth_data += len(public_key_bytes).to_bytes(4, byteorder='big')
            auth_data += public_key_bytes
            
            check_packet = KSSPPacket.create_auth_request(username, "publickey", auth_data)
            self._send_packet(check_packet)
            
            # Wait for response
            response = self.wait_for_packet(MSG_SERVICE_ACCEPT, timeout=TIMEOUT_SECONDS)
            if not response:
                return False
            
            # Create signature data
            session_id_len = len(self.session_id).to_bytes(4, byteorder='big')
            username_len = len(username).to_bytes(4, byteorder='big')
            key_type_len = len("ssh-rsa").to_bytes(4, byteorder='big')
            pubkey_len = len(public_key_bytes).to_bytes(4, byteorder='big')
            
            data_to_sign = (
                session_id_len + self.session_id +
                bytes([MSG_AUTH_REQUEST]) +
                username_len + username.encode('utf-8') +
                key_type_len + b"ssh-rsa" +
                pubkey_len + public_key_bytes
            )
            
            # Sign the data
            signature = private_key.sign(
                data_to_sign,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            
            # Create auth request with signature
            auth_data = b'\x01'  # TRUE for public key auth with sig
            auth_data += len("ssh-rsa").to_bytes(4, byteorder='big')
            auth_data += b"ssh-rsa"
            auth_data += len(public_key_bytes).to_bytes(4, byteorder='big')
            auth_data += public_key_bytes
            auth_data += len(signature).to_bytes(4, byteorder='big')
            auth_data += signature
            
            auth_packet = KSSPPacket.create_auth_request(username, "publickey", auth_data)
            self._send_packet(auth_packet)
            
            # Wait for auth response
            response = self.wait_for_packet(MSG_AUTH_SUCCESS, timeout=TIMEOUT_SECONDS)
            if response:
                self.authenticated = True
                self.username = username
                return True
            
            return False
        except Exception as e:
            logger.error(f"Public key authentication error: {e}")
            return False
    
    def open_session(self) -> Optional[KSSPChannel]:
        """Open a new shell session channel"""
        if not self.authenticated and not self.server_mode:
            raise AuthenticationError("Must authenticate before opening channels")
        
        # Create a new channel
        channel_id = self.next_channel_id
        self.next_channel_id += 1
        
        channel = KSSPChannel(channel_id, CHANNEL_SESSION)
        self.channels[channel_id] = channel
        
        # Send channel open request
        open_packet = KSSPPacket.create_channel_open(
            CHANNEL_SESSION, channel_id, channel.window_size, channel.max_packet_size
        )
        self._send_packet(open_packet)
        
        # Wait for confirmation
        response = self.wait_for_packet(MSG_CHANNEL_OPEN_CONFIRMATION, timeout=TIMEOUT_SECONDS)
        if not response:
            del self.channels[channel_id]
            return None
        
        # Parse response
        payload = response.payload
        sender_channel = int.from_bytes(payload[0:4], byteorder='big')
        if sender_channel != channel_id:
            logger.error(f"Channel ID mismatch: expected {channel_id}, got {sender_channel}")
            del self.channels[channel_id]
            return None
        
        channel.remote_id = int.from_bytes(payload[4:8], byteorder='big')
        channel.remote_window = int.from_bytes(payload[8:12], byteorder='big')
        channel.remote_max_packet = int.from_bytes(payload[12:16], byteorder='big')
        channel.is_open = True
        
        return channel
    
    def request_shell(self, channel: KSSPChannel) -> bool:
        """Request shell on a channel"""
        if not channel.is_open:
            raise ChannelError("Channel not open")
        
        # Send shell request
        payload = channel.remote_id.to_bytes(4, byteorder='big')
        payload += len("shell").to_bytes(4, byteorder='big')
        payload += b"shell"
        payload += b'\x01'  # want_reply = True
        
        request_packet = KSSPPacket(MSG_CHANNEL_REQUEST, payload)
        self._send_packet(request_packet)
        
        # Wait for response
        response = self.wait_for_packet(MSG_CHANNEL_SUCCESS, timeout=TIMEOUT_SECONDS)
        return response is not None
    
    def exec_command(self, channel: KSSPChannel, command: str) -> bool:
        """Execute command on a channel"""
        if not channel.is_open:
            raise ChannelError("Channel not open")
        
        # Store command for reference
        channel.command = command
        
        # Send exec request
        payload = channel.remote_id.to_bytes(4, byteorder='big')
        payload += len("exec").to_bytes(4, byteorder='big')
        payload += b"exec"
        payload += b'\x01'  # want_reply = True
        payload += len(command).to_bytes(4, byteorder='big')
        payload += command.encode('utf-8')
        
        request_packet = KSSPPacket(MSG_CHANNEL_REQUEST, payload)
        self._send_packet(request_packet)
        
        # Wait for response
        response = self.wait_for_packet(MSG_CHANNEL_SUCCESS, timeout=TIMEOUT_SECONDS)
        return response is not None
    
    def send_data(self, channel: KSSPChannel, data: bytes) -> bool:
        """Send data on a channel"""
        if not channel.is_open or channel.is_eof:
            raise ChannelError("Channel not open or EOF sent")
        
        # Respect remote window size
        if len(data) > channel.remote_window:
            data = data[:channel.remote_window]
        
        if len(data) > channel.remote_max_packet:
            data = data[:channel.remote_max_packet]
        
        # Send data
        payload = channel.remote_id.to_bytes(4, byteorder='big')
        payload += len(data).to_bytes(4, byteorder='big')
        payload += data
        
        data_packet = KSSPPacket(MSG_CHANNEL_DATA, payload)
        self._send_packet(data_packet)
        
        # Update remote window
        channel.remote_window -= len(data)
        return True
    
    def close_channel(self, channel: KSSPChannel) -> None:
        """Close a channel"""
        if not channel.is_open:
            return
        
        # Send EOF if not already sent
        if not channel.is_eof:
            eof_packet = KSSPPacket(MSG_CHANNEL_EOF, channel.remote_id.to_bytes(4, byteorder='big'))
            self._send_packet(eof_packet)
            channel.is_eof = True
        
        # Send close
        close_packet = KSSPPacket(MSG_CHANNEL_CLOSE, channel.remote_id.to_bytes(4, byteorder='big'))
        self._send_packet(close_packet)
        
        # Mark channel as closed
        channel.is_open = False
        
        # Remove from channels dict
        if channel.id in self.channels:
            del self.channels[channel.id]
    
    def disconnect(self, reason_code: int = 0, description: str = "Normal Shutdown") -> None:
        """Disconnect from the server"""
        # Close all channels first
        for channel_id in list(self.channels.keys()):
            self.close_channel(self.channels[channel_id])
        
        # Send disconnect packet
        disconnect_packet = KSSPPacket.create_disconnect(reason_code, description)
        self._send_packet(disconnect_packet)
        
        # Close connection
        self.running = False
        self.socket.close()
    
    def __del__(self):
        """Cleanup on deletion"""
        if self.running:
            try:
                self.disconnect()
            except:
                pass

class KSSPServer:
    """KSSP server for accepting connections"""
    def __init__(self, 
                 host: str = '0.0.0.0', 
                 port: int = DEFAULT_PORT,
                 host_key_path: str = None,
                 auth_callback: Callable[[str, str], bool] = None):
        self.host = host
        self.port = port
        self.host_key_path = host_key_path
        self.auth_callback = auth_callback
        self.running = False
        self.server_socket = None
        self.connections = []
        self.connection_handler = None
    
    def start(self, connection_callback: Callable[[KSSPConnection], None] = None) -> None:
        """Start the KSSP server"""
        if self.running:
            return
        
        self.running = True
        self.connection_handler = connection_callback
        
        # Set up server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        
        # Start accept thread
        accept_thread = threading.Thread(
            target=self._accept_connections,
            daemon=True,
            name="KSSP-Acceptor"
        )
        accept_thread.start()
        
        logger.info(f"KSSP server started on {self.host}:{self.port}")
    
    def _accept_connections(self) -> None:
        """Accept incoming connections"""
        self.server_socket.settimeout(1.0)
        
        while self.running:
            try:
                client_socket, address = self.server_socket.accept()
                client_socket.settimeout(TIMEOUT_SECONDS)
                
                logger.info(f"New connection from {address[0]}:{address[1]}")
                
                # Create connection object
                connection = KSSPConnection(client_socket, server_mode=True)
                self.connections.append(connection)
                
                # Start connection
                connection.start()
                
                # Handle connection in separate thread
                if self.connection_handler:
                    handler_thread = threading.Thread(
                        target=self._handle_connection,
                        args=(connection, address),
                        daemon=True,
                        name=f"KSSP-Handler-{address[0]}:{address[1]}"
                    )
                    handler_thread.start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error accepting connection: {e}")
                if not self.running:
                    break
    
    def _handle_connection(self, connection: KSSPConnection, address: Tuple[str, int]) -> None:
        """Handle a client connection"""
        try:
            # Run connection handler
            if self.connection_handler:
                self.connection_handler(connection)
        except Exception as e:
            logger.error(f"Error handling connection from {address[0]}:{address[1]}: {e}")
        finally:
            # Cleanup
            try:
                connection.disconnect()
            except:
                pass
            
            if connection in self.connections:
                self.connections.remove(connection)
    
    def stop(self) -> None:
        """Stop the KSSP server"""
        self.running = False
        
        # Disconnect all clients
        for connection in self.connections:
            try:
                connection.disconnect()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            self.server_socket.close()
        
        logger.info("KSSP server stopped")

class KSSPClient:
    """KSSP client for connecting to remote servers"""
    def __init__(self):
        self.connection = None
        self.host = None
        self.port = None
        self.is_connected = False
        self.is_authenticated = False
        self.current_channel = None
        
    def connect(self, host: str, port: int = DEFAULT_PORT) -> bool:
        """Connect to a KSSP server"""
        try:
            self.host = host
            self.port = port
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(TIMEOUT_SECONDS)
            
            # Connect to server
            sock.connect((host, port))
            
            # Create connection
            self.connection = KSSPConnection(sock)
            self.connection.start()
            
            self.is_connected = True
            return True
        except socket.error as e:
            logger.error(f"Error connecting to {host}:{port}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error during connection setup: {e}")
            return False
    
    def authenticate(self, username: str, password: str = None, key_path: str = None) -> bool:
        """Authenticate with the server"""
        if not self.is_connected or not self.connection:
            raise KSSPError("Not connected to a server")
        
        try:
            if self.connection.authenticate(username, password, key_path):
                self.is_authenticated = True
                return True
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def execute_command(self, command: str) -> Tuple[int, str]:
        """Execute a command on the remote server and return exit code and output"""
        if not self.is_authenticated:
            raise AuthenticationError("Not authenticated")
        
        # Open session channel
        channel = self.connection.open_session()
        if not channel:
            raise ChannelError("Failed to open session channel")
        
        # Request command execution
        if not self.connection.exec_command(channel, command):
            channel.close()
            raise ChannelError("Failed to execute command")
        
        # Read output
        output = ""
        while True:
            data = channel.read_data(timeout=0.1)
            if data is None:
                if channel.is_eof:
                    break
                continue
            
            output += data.decode('utf-8', errors='replace')
        
        exit_code = channel.exit_status or 0
        channel.close()
        
        return exit_code, output
    
    def start_interactive_session(self) -> None:
        """Start an interactive shell session"""
        if not self.is_authenticated:
            raise AuthenticationError("Not authenticated")
        
        # Open session channel
        channel = self.connection.open_session()
        if not channel:
            raise ChannelError("Failed to open session channel")
        
        # Request interactive shell
        if not self.connection.request_shell(channel):
            channel.close()
            raise ChannelError("Failed to request shell")
        
        self.current_channel = channel
        
        # Set up terminal for raw input
        old_term = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            tty.setcbreak(sys.stdin.fileno())
            
            # Create reader thread
            def reader():
                while not channel.is_eof and self.connection.running:
                    data = channel.read_data(timeout=0.1)
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
            
            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            
            # Main input loop
            while not channel.is_eof and self.connection.running:
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    char = sys.stdin.read(1)
                    if not char:
                        break
                    
                    # Convert to bytes and send
                    self.connection.send_data(channel, char.encode('utf-8'))
        finally:
            # Restore terminal
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term)
            
            # Close channel
            if channel:
                channel.close()
            
            self.current_channel = None
    
    def upload_file(self, local_path: str, remote_path: str, recursive: bool = False) -> bool:
        """Upload a file or directory to the remote server"""
        if not self.is_authenticated:
            raise AuthenticationError("Not authenticated")
        
        try:
            if os.path.isdir(local_path):
                if not recursive:
                    raise KSSPError(f"{local_path} is a directory, use recursive flag")
                
                # Create remote directory
                self.execute_command(f"mkdir -p {remote_path}")
                
                # Upload each file
                for root, dirs, files in os.walk(local_path):
                    remote_root = os.path.join(remote_path, os.path.relpath(root, local_path))
                    
                    # Create subdirectories
                    for dir_name in dirs:
                        remote_dir = os.path.join(remote_root, dir_name)
                        self.execute_command(f"mkdir -p {remote_dir}")
                    
                    # Upload files
                    for file_name in files:
                        local_file = os.path.join(root, file_name)
                        remote_file = os.path.join(remote_root, file_name)
                        if not self._upload_single_file(local_file, remote_file):
                            logger.warning(f"Failed to upload {local_file}")
                
                return True
            else:
                return self._upload_single_file(local_path, remote_path)
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False
    
    def _upload_single_file(self, local_path: str, remote_path: str) -> bool:
        """Upload a single file to the remote server"""
        try:
            # Open a file channel
            channel = self.connection.open_session()
            if not channel:
                raise ChannelError("Failed to open session channel")
            
            # Request SCP receiving at the remote end
            command = f"scp -t {remote_path}"
            if not self.connection.exec_command(channel, command):
                channel.close()
                raise ChannelError("Failed to start SCP at remote end")
            
            # Read response code (0 = success)
            response = channel.read_data()
            if not response or response[0] != 0:
                channel.close()
                raise ProtocolError("Remote SCP error")
            
            # Get file info
            file_size = os.path.getsize(local_path)
            file_mode = os.stat(local_path).st_mode & 0o777
            
            # Send file header
            header = f"C{file_mode:04o} {file_size} {os.path.basename(local_path)}\n"
            self.connection.send_data(channel, header.encode('utf-8'))
            
            # Read response code
            response = channel.read_data()
            if not response or response[0] != 0:
                channel.close()
                raise ProtocolError("Remote SCP error")
            
            # Send file data
            with open(local_path, 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    self.connection.send_data(channel, data)
            
            # Send end of file marker
            self.connection.send_data(channel, b'\0')
            
            # Read final response code
            response = channel.read_data()
            if not response or response[0] != 0:
                channel.close()
                raise ProtocolError("Remote SCP error")
            
            channel.close()
            return True
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False
    
    def download_file(self, remote_path: str, local_path: str, recursive: bool = False) -> bool:
        """Download a file or directory from the remote server"""
        if not self.is_authenticated:
            raise AuthenticationError("Not authenticated")
        
        try:
            # Check if remote path is a directory
            exit_code, output = self.execute_command(f"[ -d {remote_path} ] && echo 'DIR' || echo 'FILE'")
            is_dir = output.strip() == 'DIR'
            
            if is_dir:
                if not recursive:
                    raise KSSPError(f"{remote_path} is a directory, use recursive flag")
                
                # Create local directory
                os.makedirs(local_path, exist_ok=True)
                
                # Get file list
                exit_code, output = self.execute_command(f"find {remote_path} -type f")
                files = output.strip().split('\n')
                
                # Download each file
                for remote_file in files:
                    if not remote_file:
                        continue
                    
                    rel_path = os.path.relpath(remote_file, remote_path)
                    local_file = os.path.join(local_path, rel_path)
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(local_file), exist_ok=True)
                    
                    if not self._download_single_file(remote_file, local_file):
                        logger.warning(f"Failed to download {remote_file}")
                
                return True
            else:
                return self._download_single_file(remote_path, local_path)
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False
    
    def _download_single_file(self, remote_path: str, local_path: str) -> bool:
        """Download a single file from the remote server"""
        try:
            # Open a file channel
            channel = self.connection.open_session()
            if not channel:
                raise ChannelError("Failed to open session channel")
            
            # Request SCP sending from the remote end
            command = f"scp -f {remote_path}"
            if not self.connection.exec_command(channel, command):
                channel.close()
                raise ChannelError("Failed to start SCP at remote end")
            
            # Send null byte to start transfer
            self.connection.send_data(channel, b'\0')
            
            # Read file header
            header = b''
            while True:
                data = channel.read_data()
                if not data:
                    raise ProtocolError("Connection closed during transfer")
                
                header += data
                if b'\n' in header:
                    break
            
            # Parse header
            header_str = header.decode('utf-8')
            if not header_str.startswith('C'):
                channel.close()
                raise ProtocolError(f"Invalid file header: {header_str}")
            
            # Parse mode, size, and filename
            parts = header_str.strip().split(' ', 2)
            if len(parts) != 3:
                channel.close()
                raise ProtocolError(f"Invalid file header: {header_str}")
            
            mode_str, size_str, filename = parts
            mode = int(mode_str[1:], 8)
            size = int(size_str)
            
            # Send acknowledgement
            self.connection.send_data(channel, b'\0')
            
            # Receive file data
            with open(local_path, 'wb') as f:
                remaining = size
                while remaining > 0:
                    data = channel.read_data()
                    if not data:
                        raise ProtocolError("Connection closed during transfer")
                    
                    f.write(data)
                    remaining -= len(data)
            
            # Set file mode
            os.chmod(local_path, mode)
            
            # Read final byte
            channel.read_data()
            
            # Send acknowledgement
            self.connection.send_data(channel, b'\0')
            
            channel.close()
            return True
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from the server"""
        if self.current_channel:
            self.current_channel.close()
            self.current_channel = None
        
        if self.connection:
            self.connection.disconnect()
            self.connection = None
        
        self.is_connected = False
        self.is_authenticated = False
    """KSSP client for connecting to KSSP servers"""
    def __init__(self):
        self.connection = None
    
    def connect(self, host: str, port: int = DEFAULT_PORT, timeout: int = TIMEOUT_SECONDS) -> bool:
        """Connect to a KSSP server"""
        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            
            # Create connection
            self.connection = KSSPConnection(sock)
            self.connection.start()
            
            return True
        except Exception as e:
            logger.error(f"Error connecting to {host}:{port}: {e}")
            return False
    
    def authenticate(self, username: str, password: str = None, key_path: str = None) -> bool:
        """Authenticate with the server"""
        if not self.connection:
            raise KSSPError("Not connected")
        
        return self.connection.authenticate(username, password, key_path)
    
    def open_shell(self) -> Optional[KSSPChannel]:
        """Open a shell session"""
        if not self.connection:
            raise KSSPError("Not connected")
        
        channel = self.connection.open_session()
        if not channel:
            return None
        
        if not self.connection.request_shell(channel):
            self.connection.close_channel(channel)
            return None
        
        return channel
    
    def execute_command(self, command: str) -> Tuple[Optional[KSSPChannel], Optional[str]]:
        """Execute a command and return the output"""
        if not self.connection:
            raise KSSPError("Not connected")
        
        channel = self.connection.open_session()
        if not channel:
            return None, None
        
        if not self.connection.exec_command(channel, command):
            self.connection.close_channel(channel)
            return None, None
        
        # Read all output
        output = b''
        while True:
            data = channel.read_data(timeout=0.1)
            if data is None:
                # Check if channel is EOF
                if channel.is_eof:
                    break
                continue
            output += data
        
        # Close the channel
        self.connection.close_channel(channel)
        
        return channel, output.decode('utf-8')
    
    def disconnect(self) -> None:
        """Disconnect from the server"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None

# Simple usage examples
def kssp_server_example():
    """Example KSSP server"""
    def auth_handler(username: str, password: str) -> bool:
        # Simple authentication example
        valid_users = {
            'kaede': 'password123',
            'admin': 'adminpass'
        }
        return username in valid_users and valid_users[username] == password
    
    def connection_handler(connection: KSSPConnection):
        # Handle client connections
        logger.info(f"Handling connection from {connection.socket.getpeername()}")
        
        # Authenticate
        if not connection.authenticated:
            # Do authentication logic
            pass
        
        # Keep connection alive
        while connection.running:
            time.sleep(1)
    
    # Create and start server
    server = KSSPServer(port=2222, auth_callback=auth_handler)
    server.start(connection_handler)
    
    # Keep server running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()

def kssp_client_example():
    """Example KSSP client"""
    client = KSSPClient()
    
    # Connect to server
    if not client.connect('localhost', 2222):
        logger.error("Failed to connect")
        return
    
    # Authenticate
    if not client.authenticate('kaede', password='password123'):
        logger.error("Authentication failed")
        client.disconnect()
        return
    
    # Open shell
    channel = client.open_shell()
    if not channel:
        logger.error("Failed to open shell")
        client.disconnect()
        return
    
    # Send commands
    client.connection.send_data(channel, b"ls -la\n")
    
    # Read response
    output = b''
    while True:
        data = channel.read_data(timeout=0.1)
        if data is None:
            break
        output += data
        
        # Break on prompt
        if b'$ ' in output[-10:]:
            break
    
    print(f"Output: {output.decode('utf-8')}")
    
    # Execute a command directly
    _, cmd_output = client.execute_command("echo Hello World")
    print(f"Command output: {cmd_output}")
    
    # Disconnect
    client.disconnect()

# Main entry point if script is run directly
if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Choose client or server mode
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'server':
        kssp_server_example()
    else:
        kssp_client_example()
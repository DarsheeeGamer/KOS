"""
TLS Tunnel implementation for KADCM
"""

import os
import ssl
import socket
import threading
import logging
import time
from typing import Optional, Union
import platform

logger = logging.getLogger('kadcm.tunnel')


class TLSConnection:
    """Wrapper for TLS connection"""
    
    def __init__(self, socket_obj: Union[socket.socket, 'NamedPipeConnection'], 
                 ssl_socket: Optional[ssl.SSLSocket] = None):
        self.socket = socket_obj
        self.ssl_socket = ssl_socket or socket_obj
        self.active = True
        
    def send(self, data: bytes) -> int:
        """Send data through connection"""
        if not self.active:
            raise ConnectionError("Connection is not active")
        return self.ssl_socket.send(data)
    
    def receive(self, size: int) -> bytes:
        """Receive data from connection"""
        if not self.active:
            raise ConnectionError("Connection is not active")
        return self.ssl_socket.recv(size)
    
    def close(self):
        """Close connection"""
        self.active = False
        try:
            self.ssl_socket.close()
        except:
            pass
        try:
            if self.socket != self.ssl_socket:
                self.socket.close()
        except:
            pass
    
    def is_active(self) -> bool:
        """Check if connection is active"""
        return self.active


class TLSTunnel:
    """TLS tunnel for secure communication"""
    
    def __init__(self, pipe_path: str, cert_path: str, key_path: str, ca_path: str):
        self.pipe_path = pipe_path
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        
        self.server_socket = None
        self.ssl_context = None
        self.running = False
        self.is_windows = platform.system() == "Windows"
        
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS 1.3"""
        # Create context with TLS 1.3
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        
        # Load certificates
        context.load_cert_chain(self.cert_path, self.key_path)
        context.load_verify_locations(self.ca_path)
        
        # Set verification mode
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Set strong ciphers only
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context
    
    def start(self):
        """Start TLS tunnel"""
        logger.info(f"Starting TLS tunnel on {self.pipe_path}")
        
        # Create SSL context
        self.ssl_context = self._create_ssl_context()
        
        # Create appropriate socket based on platform
        if self.is_windows:
            self._start_windows_pipe()
        else:
            self._start_unix_pipe()
        
        self.running = True
        
    def _start_unix_pipe(self):
        """Start Unix domain socket"""
        # Remove existing socket
        if os.path.exists(self.pipe_path):
            os.unlink(self.pipe_path)
        
        # Create Unix domain socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.pipe_path)
        self.server_socket.listen(5)
        
        # Set permissions
        os.chmod(self.pipe_path, 0o600)
        
    def _start_windows_pipe(self):
        """Start Windows named pipe"""
        # Windows implementation would use pywin32
        # For now, fall back to TCP socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('127.0.0.1', 0))  # Random port
        self.server_socket.listen(5)
        
        # Store actual address for clients
        self.actual_address = self.server_socket.getsockname()
        logger.info(f"Windows pipe fallback: listening on {self.actual_address}")
        
    def stop(self):
        """Stop TLS tunnel"""
        logger.info("Stopping TLS tunnel")
        self.running = False
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Clean up Unix socket
        if not self.is_windows and os.path.exists(self.pipe_path):
            try:
                os.unlink(self.pipe_path)
            except:
                pass
    
    def accept_connection(self) -> Optional[TLSConnection]:
        """Accept new connection"""
        if not self.running:
            return None
        
        try:
            # Set timeout to allow checking running flag
            self.server_socket.settimeout(1.0)
            
            # Accept connection
            client_socket, address = self.server_socket.accept()
            
            # Wrap with SSL
            ssl_socket = self.ssl_context.wrap_socket(
                client_socket,
                server_side=True,
                do_handshake_on_connect=False
            )
            
            # Perform handshake with timeout
            ssl_socket.settimeout(5.0)
            ssl_socket.do_handshake()
            ssl_socket.settimeout(None)
            
            logger.info(f"Accepted TLS connection from {address}")
            return TLSConnection(client_socket, ssl_socket)
            
        except socket.timeout:
            return None
        except ssl.SSLError as e:
            logger.error(f"SSL handshake failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Accept error: {e}")
            return None


class NamedPipeConnection:
    """Windows named pipe connection wrapper"""
    
    def __init__(self, pipe_handle):
        self.pipe_handle = pipe_handle
        self.active = True
        
    def send(self, data: bytes) -> int:
        """Send data through pipe"""
        # Windows implementation with pywin32
        raise NotImplementedError("Windows named pipes require pywin32")
    
    def receive(self, size: int) -> bytes:
        """Receive data from pipe"""
        # Windows implementation with pywin32
        raise NotImplementedError("Windows named pipes require pywin32")
    
    def close(self):
        """Close pipe"""
        self.active = False
        # Close pipe handle
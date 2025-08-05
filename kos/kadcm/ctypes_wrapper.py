"""
KADCM Python ctypes wrapper
Provides Python bindings for the KADCM C/C++ library
"""

import ctypes
import os
import sys
import json
import yaml
import logging
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

logger = logging.getLogger('kadcm.ctypes')

# Find library
def _find_kadcm_lib():
    """Find the KADCM shared library"""
    lib_names = ['libkadcm.so', 'kadcm.dll', 'libkadcm.dylib']
    
    # Check common paths
    search_paths = [
        '/usr/lib',
        '/usr/local/lib',
        '/usr/lib/x86_64-linux-gnu',
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build'),
    ]
    
    for path in search_paths:
        for name in lib_names:
            lib_path = os.path.join(path, name)
            if os.path.exists(lib_path):
                return lib_path
    
    # Try system default
    for name in lib_names:
        try:
            return ctypes.util.find_library('kadcm')
        except:
            pass
    
    return None

# Load library
_lib_path = _find_kadcm_lib()
if _lib_path:
    try:
        _kadcm_lib = ctypes.CDLL(_lib_path)
    except Exception as e:
        logger.warning(f"Failed to load KADCM library from {_lib_path}: {e}")
        _kadcm_lib = None
else:
    logger.warning("KADCM library not found")
    _kadcm_lib = None

# Constants
KADCM_SUCCESS = 0
KADCM_ERROR_GENERAL = -1
KADCM_ERROR_AUTH = -2
KADCM_ERROR_CONNECT = -3
KADCM_ERROR_TIMEOUT = -4
KADCM_ERROR_PROTOCOL = -5
KADCM_ERROR_PERMISSION = -6
KADCM_ERROR_INVALID = -7
KADCM_ERROR_NOMEM = -8
KADCM_ERROR_BUSY = -9
KADCM_ERROR_TLS = -10

# Message types
KADCM_MSG_COMMAND = 1
KADCM_MSG_DATA = 2
KADCM_MSG_AUTH = 3
KADCM_MSG_CONTROL = 4
KADCM_MSG_HEARTBEAT = 5
KADCM_MSG_ERROR = 6
KADCM_MSG_NOTIFY = 7

# Priority levels
KADCM_PRIORITY_LOW = 0
KADCM_PRIORITY_NORMAL = 1
KADCM_PRIORITY_HIGH = 2
KADCM_PRIORITY_URGENT = 3

# Flags
KADCM_FLAG_COMPRESSED = 0x01
KADCM_FLAG_ENCRYPTED = 0x02
KADCM_FLAG_RESPONSE = 0x04


# C structures
class KADCMConfig(ctypes.Structure):
    """KADCM configuration structure"""
    _fields_ = [
        ('pipe_path', ctypes.c_char_p),
        ('tcp_host', ctypes.c_char_p),
        ('tcp_port', ctypes.c_uint16),
        ('tls_cert', ctypes.c_char_p),
        ('tls_key', ctypes.c_char_p),
        ('verify_peer', ctypes.c_bool),
        ('timeout_ms', ctypes.c_uint32),
        ('heartbeat_interval', ctypes.c_uint32),
    ]


class KADCMMessage(ctypes.Structure):
    """KADCM message structure"""
    _fields_ = [
        ('id', ctypes.c_uint32),
        ('type', ctypes.c_int),
        ('priority', ctypes.c_int),
        ('flags', ctypes.c_uint8),
        ('header_data', ctypes.c_void_p),
        ('header_size', ctypes.c_size_t),
        ('body_data', ctypes.c_void_p),
        ('body_size', ctypes.c_size_t),
    ]


# Function prototypes
if _kadcm_lib:
    # Initialize/cleanup
    _kadcm_lib.kadcm_init.argtypes = []
    _kadcm_lib.kadcm_init.restype = ctypes.c_int
    
    _kadcm_lib.kadcm_cleanup.argtypes = []
    _kadcm_lib.kadcm_cleanup.restype = None
    
    # Connection management
    _kadcm_lib.kadcm_create.argtypes = [ctypes.POINTER(KADCMConfig)]
    _kadcm_lib.kadcm_create.restype = ctypes.c_void_p
    
    _kadcm_lib.kadcm_destroy.argtypes = [ctypes.c_void_p]
    _kadcm_lib.kadcm_destroy.restype = None
    
    _kadcm_lib.kadcm_connect.argtypes = [ctypes.c_void_p]
    _kadcm_lib.kadcm_connect.restype = ctypes.c_int
    
    _kadcm_lib.kadcm_disconnect.argtypes = [ctypes.c_void_p]
    _kadcm_lib.kadcm_disconnect.restype = None
    
    _kadcm_lib.kadcm_is_connected.argtypes = [ctypes.c_void_p]
    _kadcm_lib.kadcm_is_connected.restype = ctypes.c_bool
    
    # Authentication
    _kadcm_lib.kadcm_authenticate.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p
    ]
    _kadcm_lib.kadcm_authenticate.restype = ctypes.c_int
    
    # Message handling
    _kadcm_lib.kadcm_send_message.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(KADCMMessage)
    ]
    _kadcm_lib.kadcm_send_message.restype = ctypes.c_int
    
    _kadcm_lib.kadcm_recv_message.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(KADCMMessage), ctypes.c_uint32
    ]
    _kadcm_lib.kadcm_recv_message.restype = ctypes.c_int
    
    # Command execution
    _kadcm_lib.kadcm_exec_command.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p),
        ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_size_t)
    ]
    _kadcm_lib.kadcm_exec_command.restype = ctypes.c_int
    
    # Utility
    _kadcm_lib.kadcm_error_string.argtypes = [ctypes.c_int]
    _kadcm_lib.kadcm_error_string.restype = ctypes.c_char_p
    
    _kadcm_lib.kadcm_free_string.argtypes = [ctypes.c_char_p]
    _kadcm_lib.kadcm_free_string.restype = None
    
    _kadcm_lib.kadcm_message_free.argtypes = [ctypes.POINTER(KADCMMessage)]
    _kadcm_lib.kadcm_message_free.restype = None


class KADCMError(Exception):
    """KADCM error exception"""
    def __init__(self, code: int, message: str = None):
        self.code = code
        if message is None and _kadcm_lib:
            message = _kadcm_lib.kadcm_error_string(code).decode('utf-8')
        super().__init__(message)


class KADCMClient:
    """KADCM Python client using ctypes"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize KADCM client"""
        self.handle = None
        self._connected = False
        self._authenticated = False
        
        if not _kadcm_lib:
            raise RuntimeError("KADCM library not loaded")
        
        # Initialize library
        result = _kadcm_lib.kadcm_init()
        if result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        # Setup configuration
        self.config = KADCMConfig()
        if config:
            if 'pipe_path' in config:
                self.config.pipe_path = config['pipe_path'].encode('utf-8')
            if 'tcp_host' in config:
                self.config.tcp_host = config['tcp_host'].encode('utf-8')
            if 'tcp_port' in config:
                self.config.tcp_port = config['tcp_port']
            if 'tls_cert' in config:
                self.config.tls_cert = config['tls_cert'].encode('utf-8')
            if 'tls_key' in config:
                self.config.tls_key = config['tls_key'].encode('utf-8')
            self.config.verify_peer = config.get('verify_peer', False)
            self.config.timeout_ms = config.get('timeout_ms', 5000)
            self.config.heartbeat_interval = config.get('heartbeat_interval', 30)
        else:
            # Default configuration
            if sys.platform == 'win32':
                self.config.pipe_path = b'\\\\.\\pipe\\kos\\runtime\\kadcm\\kadcm'
            else:
                self.config.pipe_path = b'/var/run/kos/runtime/kadcm/kadcm.pipe'
            self.config.tcp_host = b'localhost'
            self.config.tcp_port = 9876
            self.config.verify_peer = False
            self.config.timeout_ms = 5000
            self.config.heartbeat_interval = 30
        
        # Create handle
        self.handle = _kadcm_lib.kadcm_create(ctypes.byref(self.config))
        if not self.handle:
            raise KADCMError(KADCM_ERROR_NOMEM, "Failed to create handle")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.close()
    
    def __enter__(self):
        """Context manager support"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.close()
    
    def connect(self) -> bool:
        """Connect to KADCM server"""
        if not self.handle:
            raise RuntimeError("Client not initialized")
        
        result = _kadcm_lib.kadcm_connect(self.handle)
        if result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        self._connected = True
        return True
    
    def disconnect(self):
        """Disconnect from server"""
        if self.handle and self._connected:
            _kadcm_lib.kadcm_disconnect(self.handle)
            self._connected = False
            self._authenticated = False
    
    def close(self):
        """Close and cleanup client"""
        if self.handle:
            self.disconnect()
            _kadcm_lib.kadcm_destroy(self.handle)
            self.handle = None
    
    def is_connected(self) -> bool:
        """Check if connected"""
        if not self.handle:
            return False
        return _kadcm_lib.kadcm_is_connected(self.handle)
    
    def authenticate(self, entity_type: str, entity_id: str, 
                    fingerprint: str) -> bool:
        """Authenticate with server"""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        result = _kadcm_lib.kadcm_authenticate(
            self.handle,
            entity_type.encode('utf-8'),
            entity_id.encode('utf-8'),
            fingerprint.encode('utf-8')
        )
        
        if result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        self._authenticated = True
        return True
    
    def execute_command(self, command: str, args: Optional[List[str]] = None) -> str:
        """Execute command on server"""
        if not self._authenticated:
            raise RuntimeError("Not authenticated")
        
        # Prepare arguments
        if args:
            c_args = (ctypes.c_char_p * (len(args) + 1))()
            for i, arg in enumerate(args):
                c_args[i] = arg.encode('utf-8')
            c_args[len(args)] = None
        else:
            c_args = None
        
        # Execute
        output_ptr = ctypes.c_char_p()
        output_size = ctypes.c_size_t()
        
        result = _kadcm_lib.kadcm_exec_command(
            self.handle,
            command.encode('utf-8'),
            c_args,
            ctypes.byref(output_ptr),
            ctypes.byref(output_size)
        )
        
        if result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        # Get output
        output = output_ptr.value.decode('utf-8') if output_ptr.value else ""
        _kadcm_lib.kadcm_free_string(output_ptr)
        
        return output
    
    def send_message(self, msg_type: int, header: Dict[str, Any], 
                    body: Optional[Any] = None, priority: int = KADCM_PRIORITY_NORMAL,
                    flags: int = 0) -> int:
        """Send a message to server"""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        # Create message
        msg = KADCMMessage()
        msg.type = msg_type
        msg.priority = priority
        msg.flags = flags
        
        # Encode header as JSON
        header_json = json.dumps(header).encode('utf-8')
        msg.header_data = ctypes.cast(
            ctypes.create_string_buffer(header_json), 
            ctypes.c_void_p
        )
        msg.header_size = len(header_json)
        
        # Encode body as YAML if provided
        if body is not None:
            body_yaml = yaml.dump(body).encode('utf-8')
            msg.body_data = ctypes.cast(
                ctypes.create_string_buffer(body_yaml),
                ctypes.c_void_p
            )
            msg.body_size = len(body_yaml)
        
        # Send
        result = _kadcm_lib.kadcm_send_message(self.handle, ctypes.byref(msg))
        if result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        return msg.id
    
    def receive_message(self, timeout_ms: int = 0) -> Optional[Dict[str, Any]]:
        """Receive a message from server"""
        if not self._connected:
            raise RuntimeError("Not connected")
        
        msg = KADCMMessage()
        result = _kadcm_lib.kadcm_recv_message(
            self.handle, 
            ctypes.byref(msg), 
            timeout_ms
        )
        
        if result == KADCM_ERROR_TIMEOUT:
            return None
        elif result != KADCM_SUCCESS:
            raise KADCMError(result)
        
        # Parse message
        message_data = {
            'id': msg.id,
            'type': msg.type,
            'priority': msg.priority,
            'flags': msg.flags
        }
        
        # Parse header
        if msg.header_size > 0:
            header_data = ctypes.string_at(msg.header_data, msg.header_size)
            message_data['header'] = json.loads(header_data.decode('utf-8'))
        
        # Parse body
        if msg.body_size > 0:
            body_data = ctypes.string_at(msg.body_data, msg.body_size)
            message_data['body'] = yaml.safe_load(body_data.decode('utf-8'))
        
        # Free message
        _kadcm_lib.kadcm_message_free(ctypes.byref(msg))
        
        return message_data


# High-level convenience functions
def connect_kadcm(entity_type: str = "host", entity_id: str = "localhost",
                 fingerprint: str = "", config: Optional[Dict[str, Any]] = None) -> KADCMClient:
    """Connect and authenticate to KADCM server"""
    client = KADCMClient(config)
    try:
        client.connect()
        client.authenticate(entity_type, entity_id, fingerprint)
        return client
    except:
        client.close()
        raise


def execute_kos_command(command: str, args: Optional[List[str]] = None,
                       config: Optional[Dict[str, Any]] = None) -> str:
    """Execute a single command on KOS"""
    with connect_kadcm(config=config) as client:
        return client.execute_command(command, args)


# Test function
def test_kadcm_ctypes():
    """Test KADCM ctypes wrapper"""
    print("Testing KADCM ctypes wrapper...")
    
    try:
        # Create client
        client = KADCMClient()
        print("✓ Client created")
        
        # Connect
        client.connect()
        print("✓ Connected")
        
        # Authenticate
        client.authenticate("test", "test_client", "test_fingerprint")
        print("✓ Authenticated")
        
        # Execute command
        result = client.execute_command("echo", ["Hello from ctypes!"])
        print(f"✓ Command executed: {result}")
        
        # Send custom message
        msg_id = client.send_message(
            KADCM_MSG_DATA,
            {"action": "test"},
            {"data": "test payload"}
        )
        print(f"✓ Message sent: ID={msg_id}")
        
        # Cleanup
        client.close()
        print("✓ Client closed")
        
        print("\nAll tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


if __name__ == "__main__":
    test_kadcm_ctypes()
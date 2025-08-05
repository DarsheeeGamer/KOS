"""
KAIM Protocol - Binary protocol for client-daemon communication
"""

import json
import struct
import time
import uuid
from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class MessageType(IntEnum):
    """KAIM message types"""
    REQUEST = 1
    RESPONSE = 2
    EVENT = 3
    ERROR = 4


class RequestType(IntEnum):
    """KAIM request types"""
    AUTHENTICATE = 1
    OPEN = 2
    CONTROL = 3
    ELEVATE = 4
    CLOSE = 5
    STATUS = 6


class KAIMError(IntEnum):
    """KAIM error codes"""
    NONE = 0
    UNKNOWN_REQUEST = 1
    INVALID_REQUEST = 2
    PERMISSION_DENIED = 3
    AUTH_REQUIRED = 4
    AUTH_FAILED = 5
    SESSION_EXPIRED = 6
    DEVICE_ERROR = 7
    INTERNAL_ERROR = 8


@dataclass
class Message:
    """KAIM message structure"""
    type: MessageType
    id: str
    request_type: Optional[RequestType] = None
    data: Dict[str, Any] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    error_code: Optional[KAIMError] = None
    
    def __post_init__(self):
        if self.data is None:
            self.data = {}


class KAIMProtocol:
    """KAIM binary protocol implementation"""
    
    VERSION = 1
    MAGIC = b"KAIM"
    
    def encode_message(self, msg: Message) -> bytes:
        """Encode message to binary format"""
        # Create message dict
        msg_dict = {
            "version": self.VERSION,
            "type": msg.type,
            "id": msg.id,
            "data": msg.data
        }
        
        if msg.request_type is not None:
            msg_dict["request_type"] = msg.request_type
        
        if msg.success is not None:
            msg_dict["success"] = msg.success
            
        if msg.error is not None:
            msg_dict["error"] = msg.error
            
        if msg.error_code is not None:
            msg_dict["error_code"] = msg.error_code
        
        # Encode to JSON
        json_data = json.dumps(msg_dict, separators=(',', ':')).encode('utf-8')
        
        # Create binary message
        # [4 bytes: MAGIC][2 bytes: version][2 bytes: reserved][json data]
        header = self.MAGIC + struct.pack(">HH", self.VERSION, 0)
        
        return header + json_data
    
    def decode_message(self, data: bytes) -> Optional[Message]:
        """Decode message from binary format"""
        if len(data) < 8:
            return None
        
        # Check magic
        if data[:4] != self.MAGIC:
            return None
        
        # Parse header
        version, _ = struct.unpack(">HH", data[4:8])
        if version != self.VERSION:
            return None
        
        # Parse JSON
        try:
            msg_dict = json.loads(data[8:].decode('utf-8'))
            
            # Create message
            msg = Message(
                type=MessageType(msg_dict["type"]),
                id=msg_dict["id"],
                data=msg_dict.get("data", {})
            )
            
            if "request_type" in msg_dict:
                msg.request_type = RequestType(msg_dict["request_type"])
            
            if "success" in msg_dict:
                msg.success = msg_dict["success"]
                
            if "error" in msg_dict:
                msg.error = msg_dict["error"]
                
            if "error_code" in msg_dict:
                msg.error_code = KAIMError(msg_dict["error_code"])
            
            return msg
            
        except Exception:
            return None
    
    def create_request(self, request_type: RequestType,
                      data: Dict[str, Any] = None) -> Message:
        """Create request message"""
        return Message(
            type=MessageType.REQUEST,
            id=str(uuid.uuid4()),
            request_type=request_type,
            data=data or {}
        )
    
    def create_response(self, request_id: str, success: bool,
                       data: Dict[str, Any] = None,
                       error: Optional[str] = None) -> Message:
        """Create response message"""
        return Message(
            type=MessageType.RESPONSE,
            id=request_id,
            success=success,
            data=data or {},
            error=error
        )
    
    def create_error_response(self, request_id: str,
                             error_code: KAIMError,
                             error_msg: str) -> Message:
        """Create error response"""
        return Message(
            type=MessageType.ERROR,
            id=request_id,
            success=False,
            error=error_msg,
            error_code=error_code
        )
    
    def create_event(self, event_type: str,
                    data: Dict[str, Any] = None) -> Message:
        """Create event message"""
        return Message(
            type=MessageType.EVENT,
            id=str(uuid.uuid4()),
            data={
                "event_type": event_type,
                "timestamp": time.time(),
                **(data or {})
            }
        )
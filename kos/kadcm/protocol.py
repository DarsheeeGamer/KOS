"""
KADCM Protocol - Message encoding/decoding and protocol handling
"""

import json
import yaml
import struct
import zlib
from typing import Optional, Union
from dataclasses import dataclass

from .messages import Message, MessageType, MessageFlags


class KADCMProtocol:
    """KADCM binary protocol implementation"""
    
    PROTOCOL_VERSION = 1
    HEADER_SIZE = 5  # 4 bytes length + 1 byte flags
    
    def encode_message(self, msg: Message) -> bytes:
        """Encode message to binary format"""
        # Create JSON header + YAML body structure
        message_data = {
            "header": {
                "version": self.PROTOCOL_VERSION,
                "type": msg.type.value,
                "id": msg.id,
                "priority": msg.priority,
                **msg.header
            },
            "body": msg.body
        }
        
        # Convert to JSON
        json_data = json.dumps(message_data, separators=(',', ':')).encode('utf-8')
        
        # Compress if needed
        if msg.flags & MessageFlags.COMPRESSED:
            json_data = zlib.compress(json_data)
        
        # Additional encryption layer if flagged
        if msg.flags & MessageFlags.ENCRYPTED:
            # Additional encryption is handled at the TLS layer
            # This flag indicates the message should only be sent over encrypted channels
            pass
        
        # Create binary frame
        # [4 bytes: message length][1 byte: flags][message data]
        length = len(json_data)
        header = struct.pack(">IB", length, msg.flags)
        
        return header + json_data
    
    def decode_message(self, data: bytes) -> Optional[Message]:
        """Decode message from binary format"""
        if len(data) < self.HEADER_SIZE:
            return None
        
        # Parse header
        length, flags = struct.unpack(">IB", data[:self.HEADER_SIZE])
        message_data = data[self.HEADER_SIZE:]
        
        if len(message_data) != length:
            return None
        
        # Handle decryption if needed
        if flags & MessageFlags.ENCRYPTED:
            # Decryption is handled at the TLS layer
            # This flag indicates the message was sent over encrypted channels
            pass
        
        # Handle decompression
        if flags & MessageFlags.COMPRESSED:
            try:
                message_data = zlib.decompress(message_data)
            except:
                return None
        
        # Parse JSON
        try:
            parsed = json.loads(message_data.decode('utf-8'))
            header = parsed.get("header", {})
            body = parsed.get("body", "")
            
            # Extract standard fields
            msg_type = MessageType(header.pop("type", 0))
            msg_id = header.pop("id", "")
            priority = header.pop("priority", 0)
            version = header.pop("version", 0)
            
            # Version check
            if version != self.PROTOCOL_VERSION:
                return None
            
            # Create message
            return Message(
                type=msg_type,
                id=msg_id,
                priority=priority,
                flags=flags,
                header=header,
                body=body
            )
            
        except Exception as e:
            return None
    
    def create_auth_message(self, fingerprint: str, entity_id: str, 
                          entity_type: str, challenge_response: str) -> Message:
        """Create authentication message"""
        auth_data = {
            "fingerprint": fingerprint,
            "entity_id": entity_id,
            "entity_type": entity_type,
            "signature": challenge_response
        }
        
        return Message(
            type=MessageType.AUTH,
            id=f"auth-{entity_id}",
            priority=0,
            flags=0,
            header={"auth": True},
            body=yaml.dump(auth_data)
        )
    
    def create_command_message(self, command: str, args: list = None,
                             env: dict = None, cwd: str = None) -> Message:
        """Create command execution message"""
        cmd_data = {
            "command": command,
            "args": args or [],
            "env": env or {},
            "cwd": cwd
        }
        
        return Message(
            type=MessageType.COMMAND,
            id=f"cmd-{hash(command)}",
            priority=1,
            flags=0,
            header={"command": True},
            body=yaml.dump(cmd_data)
        )
    
    def create_data_message(self, operation: str, path: str,
                          content: Optional[str] = None) -> Message:
        """Create data transfer message"""
        data_info = {
            "operation": operation,
            "path": path
        }
        
        if content is not None:
            data_info["content"] = content
        
        flags = 0
        if content and len(content) > 1024:
            flags |= MessageFlags.COMPRESSED
        
        return Message(
            type=MessageType.DATA,
            id=f"data-{path}",
            priority=2,
            flags=flags,
            header={"data_transfer": True},
            body=yaml.dump(data_info)
        )
    
    def create_heartbeat_message(self) -> Message:
        """Create heartbeat message"""
        return Message(
            type=MessageType.HEARTBEAT,
            id="heartbeat",
            priority=0,
            flags=0,
            header={"heartbeat": True},
            body=""
        )
    
    def validate_message(self, msg: Message) -> bool:
        """Validate message structure and content"""
        # Check required fields
        if not msg.id or msg.type is None:
            return False
        
        # Check message size based on type
        if msg.type == MessageType.HEARTBEAT and len(msg.body) > 0:
            return False
        
        # Validate flags
        if msg.flags > 0x0F:  # All flags OR'd together
            return False
        
        # Type-specific validation
        if msg.type == MessageType.AUTH:
            try:
                auth_data = yaml.safe_load(msg.body)
                return all(k in auth_data for k in ["fingerprint", "entity_id", "signature"])
            except:
                return False
        
        return True
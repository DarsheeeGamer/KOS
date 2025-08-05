"""
KADCM Message definitions and types
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Dict, Any, Optional


class MessageType(IntEnum):
    """KADCM message types"""
    COMMAND = 1      # Execute host/KOS commands
    DATA = 2         # File transfers
    AUTH = 3         # Authentication/fingerprint exchange
    CONTROL = 4      # Tunnel management
    HEARTBEAT = 5    # Keepalive
    ERROR = 6        # Error reporting
    NOTIFY = 7       # Asynchronous alerts


class MessageFlags(IntEnum):
    """Message flags (can be OR'd together)"""
    COMPRESSED = 0x01      # Message is compressed
    ENCRYPTED = 0x02       # Additional encryption layer
    FRAGMENTED = 0x04      # Message split across frames
    REQUIRES_ACK = 0x08    # Needs acknowledgment


@dataclass
class Message:
    """KADCM message structure"""
    type: MessageType
    id: str
    priority: int  # 0=CRITICAL, 1=HIGH, 2=NORMAL, 3=LOW
    flags: int
    header: Dict[str, Any]
    body: str
    
    def is_compressed(self) -> bool:
        return bool(self.flags & MessageFlags.COMPRESSED)
    
    def is_encrypted(self) -> bool:
        return bool(self.flags & MessageFlags.ENCRYPTED)
    
    def is_fragmented(self) -> bool:
        return bool(self.flags & MessageFlags.FRAGMENTED)
    
    def requires_ack(self) -> bool:
        return bool(self.flags & MessageFlags.REQUIRES_ACK)
    
    def set_flag(self, flag: MessageFlags):
        self.flags |= flag
    
    def clear_flag(self, flag: MessageFlags):
        self.flags &= ~flag
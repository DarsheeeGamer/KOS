"""
KADCM - Kaede Advanced Device Communication Manager
Handles secure bidirectional communication between host OS and KOS
"""

from .manager import KADCMManager
from .protocol import KADCMProtocol
from .tunnel import TLSTunnel
from .messages import MessageType, MessageFlags

__all__ = [
    'KADCMManager',
    'KADCMProtocol', 
    'TLSTunnel',
    'MessageType',
    'MessageFlags'
]

__version__ = '1.0.0'
"""
KAIM - Kaede Application Interface Manager
Provides controlled kernel access for applications
"""

from .daemon import KAIMDaemon
from .client import KAIMClient
from .protocol import KAIMProtocol, MessageType, RequestType
from .errors import KAIMError, KAIMPermissionError, KAIMAuthError

__all__ = [
    'KAIMDaemon',
    'KAIMClient',
    'KAIMProtocol',
    'MessageType',
    'RequestType',
    'KAIMError',
    'KAIMPermissionError',
    'KAIMAuthError'
]

__version__ = '1.0.0'
"""
Pluggable Authentication Modules (PAM) for KOS

This module provides a PAM-like authentication framework for KOS, allowing flexible 
authentication mechanisms to be configured for different services.

Features:
- Pluggable authentication modules
- Configurable authentication stacks
- Service-specific authentication policies
- Session management
"""

from .manager import PAMManager
from .modules import PAMResult, PAMModule, PasswordModule, TokenModule, BiometricModule
from .session import PAMSession

__all__ = [
    'PAMManager', 'PAMResult', 'PAMModule', 'PasswordModule', 
    'TokenModule', 'BiometricModule', 'PAMSession'
]

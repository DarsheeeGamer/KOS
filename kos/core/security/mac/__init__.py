"""
Mandatory Access Control (MAC) for KOS

This module provides MAC security features for KOS, including:
- SELinux-like security context management
- AppArmor-like profile-based confinement
- Security policy enforcement
- Container security isolation

These MAC systems provide protection beyond traditional DAC (Discretionary Access Control)
permissions by enforcing system-wide security policies.
"""

from .selinux import SELinuxManager, SecurityContext, Transition
from .apparmor import AppArmorManager, SecurityProfile, ProfileMode

__all__ = [
    'SELinuxManager', 'SecurityContext', 'Transition',
    'AppArmorManager', 'SecurityProfile', 'ProfileMode'
]

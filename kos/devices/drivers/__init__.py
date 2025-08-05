"""
KOS Device Drivers
Actual hardware device driver implementations
"""

from .storage_driver import StorageDevice, ATADevice, NVMeDevice, StorageDriverManager, get_storage_manager
from .network_driver import NetworkInterface, EthernetInterface, WiFiInterface, NetworkDriverManager, get_network_manager
from .input_driver import InputDevice, KeyboardDevice, MouseDevice, TouchpadDevice, InputDriverManager, get_input_manager

__all__ = [
    # Storage
    'StorageDevice', 'ATADevice', 'NVMeDevice', 'StorageDriverManager', 'get_storage_manager',
    # Network
    'NetworkInterface', 'EthernetInterface', 'WiFiInterface', 'NetworkDriverManager', 'get_network_manager',
    # Input
    'InputDevice', 'KeyboardDevice', 'MouseDevice', 'TouchpadDevice', 'InputDriverManager', 'get_input_manager'
]
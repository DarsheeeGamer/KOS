"""
KOS Memory Management - Virtual memory management for KOS
"""

from .manager import KOSMemoryManager
from .allocator import BuddyAllocator, SlabAllocator
from .page import Page, PageFrame
from .swap import SwapManager
from .swap_manager import (
    SwapManager as AdvancedSwapManager, SwapInfo, SwapType, SwapCache,
    SwapDevice, SwapFile, ZramDevice, get_swap_manager
)

__all__ = [
    'KOSMemoryManager', 'BuddyAllocator', 'SlabAllocator', 
    'Page', 'PageFrame', 'SwapManager',
    'AdvancedSwapManager', 'SwapInfo', 'SwapType', 'SwapCache',
    'SwapDevice', 'SwapFile', 'ZramDevice', 'get_swap_manager'
]
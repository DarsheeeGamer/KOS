"""
KOS Shell Module

This module provides the shell interface for KOS, including command parsing,
command execution, and the interactive shell interface.
"""

# Import shell components
from .shell import KaedeShell
from .command_parser import CommandParser
from .command_dispatcher import CommandDispatcher
from .history_manager import HistoryManager

# Import commands
from .commands import *  # This will import all commands

__all__ = [
    'KaedeShell',
    'CommandParser',
    'CommandDispatcher',
    'HistoryManager',
]

# Initialize the shell components
shell = KaedeShell()

# Export the shell instance
__all__.append('shell')

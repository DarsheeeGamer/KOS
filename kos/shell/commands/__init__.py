"""
KOS Shell Commands

This package contains all the built-in commands for the KOS shell.
"""

# Import all command modules here to make them available
from .nano import nano as nano_cmd
from .text_processing import register_commands as register_text_commands
from .text_processing import TextProcessingCommands
from .archive import register_commands as register_archive_commands
from .archive import ArchiveCommands
from .sysmon import register_commands as register_sysmon_commands
from .sysmon import SystemMonitorCommands
from .network import register_commands as register_network_commands
from .network import NetworkCommands
from .package_manager import register_commands as register_package_commands
from .package_manager import PackageManagementCommands

# Export all commands
__all__ = [
    'nano_cmd',
    'register_text_commands',
    'TextProcessingCommands',
    'register_archive_commands',
    'ArchiveCommands',
    'register_sysmon_commands',
    'SystemMonitorCommands',
    'register_network_commands',
    'NetworkCommands',
    'register_package_commands',
    'PackageManagementCommands',
]

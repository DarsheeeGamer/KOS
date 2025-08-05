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

def register_all(shell):
    """Register all available commands with the shell"""
    try:
        register_text_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register text commands: {e}")
    
    try:
        register_archive_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register archive commands: {e}")
    
    try:
        register_sysmon_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register sysmon commands: {e}")
    
    try:
        register_network_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register network commands: {e}")
    
    try:
        register_package_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register package commands: {e}")
    
    try:
        from .ksudo_cmd import register_commands as register_ksudo_commands
        register_ksudo_commands(shell)
    except Exception as e:
        print(f"Warning: Failed to register ksudo commands: {e}")

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
    'register_all',
]

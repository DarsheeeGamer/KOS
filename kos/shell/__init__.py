"""
KOS Shell Module

This module provides the shell interface for KOS, including command parsing,
command execution, and the interactive shell interface.
"""

# Import shell components
from .shell import KaedeShell
from .commands.text_processing import register_commands as register_text_processing_commands
from .commands.archive import register_commands as register_archive_commands
from .commands.sysmon import register_commands as register_sysmon_commands
from .commands.network import register_commands as register_network_commands
from .commands.package_manager import register_commands as register_package_commands
from .command_parser import CommandParser
from .command_dispatcher import CommandDispatcher
from .history_manager import HistoryManager

# Import commands
from .commands import register_all
import logging

__all__ = [
    'KaedeShell',
    'CommandParser',
    'CommandDispatcher',
    'HistoryManager',
]

def init_shell():
    """Initialize the KOS shell"""
    shell = KaedeShell()
    
    # Register all command modules
    register_all(shell)
    register_text_processing_commands(shell)
    register_archive_commands(shell)
    register_sysmon_commands(shell)
    register_network_commands(shell)
    register_package_commands(shell)
    
    # Register repository management commands
    try:
        from .commands.repo_management import register_commands as register_repo_commands
        register_repo_commands(shell)
    except ImportError:
        logging.warning("Repository management commands not available")
    
    # Register application management commands
    try:
        from .commands.app_management import register_commands as register_app_commands
        register_app_commands(shell)
    except ImportError:
        logging.warning("Application management commands not available")
    
    # Register Linux-style file system utilities
    try:
        from .commands.fs_utils import register_commands as register_fs_utils
        register_fs_utils(shell)
        logging.info("Registered Linux-style file system commands")
    except ImportError:
        logging.warning("Linux-style file system commands not available")
    
    # Register Linux-style process utilities
    try:
        from .commands.proc_utils import register_commands as register_proc_utils
        register_proc_utils(shell)
        logging.info("Registered Linux-style process commands")
    except ImportError:
        logging.warning("Linux-style process commands not available")
    
    # Register Linux-style network utilities
    try:
        from .commands.net_utils import register_commands as register_net_utils
        register_net_utils(shell)
        logging.info("Registered Linux-style network commands")
    except ImportError:
        logging.warning("Linux-style network commands not available")

    return shell

# Initialize the shell components
shell = init_shell()

# Export the shell instance
__all__.append('shell')

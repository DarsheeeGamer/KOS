"""
KOS Shell Module

This module provides the shell interface for KOS, including command parsing,
command execution, and the interactive shell interface.
"""

# Import shell components
from .shell import KaedeShell
from .commands.text_processing import register_commands as register_text_processing_commands
from .commands.basic_commands import register_commands as register_basic_commands
from .commands.package_management import register_commands as register_kpm_commands
from .commands.system_utils import register_commands as register_system_commands
from .commands.hardware_utils import register_commands as register_hardware_commands
from .commands.network_utils import register_commands as register_network_commands
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
    register_package_commands(shell)
    
    # Register our new Linux-style utilities
    try:
        register_basic_commands(shell)
        logging.info("Registered basic commands")
    except Exception as e:
        logging.warning(f"Basic commands not available: {e}")
    
    try:
        register_kpm_commands(shell)
        logging.info("Registered KPM commands")
    except Exception as e:
        logging.warning(f"KPM commands not available: {e}")
    
    # Register system utilities commands
    try:
        register_system_commands(shell)
        logging.info("Registered system utilities commands")
    except Exception as e:
        logging.warning(f"System utilities commands not available: {e}")
    
    # Register hardware utilities commands
    try:
        register_hardware_commands(shell)
        logging.info("Registered hardware utilities commands")
    except Exception as e:
        logging.warning(f"Hardware utilities commands not available: {e}")
    
    # Register network utilities commands
    try:
        register_network_commands(shell)
        logging.info("Registered network utilities commands")
    except Exception as e:
        logging.warning(f"Network utilities commands not available: {e}")
    
    # Register advanced filesystem commands
    try:
        from .commands.advanced_fs import register_commands as register_advanced_fs_commands
        register_advanced_fs_commands(shell)
        logging.info("Registered advanced filesystem commands")
    except Exception as e:
        logging.warning(f"Advanced filesystem commands not available: {e}")
    
    # Register Unix-like file utilities
    try:
        from .commands.unix_file_utils import register_commands as register_unix_file_commands
        register_unix_file_commands(shell)
        logging.info("Registered Unix file utilities")
    except Exception as e:
        logging.warning(f"Unix file utilities not available: {e}")
        
    # Register Unix-like text utilities
    try:
        from .commands.unix_text_utils import register_commands as register_unix_text_commands
        register_unix_text_commands(shell)
        logging.info("Registered Unix text utilities")
    except Exception as e:
        logging.warning(f"Unix text utilities not available: {e}")
        
    # Register Unix-like process utilities
    try:
        from .commands.unix_process_utils import register_commands as register_unix_process_commands
        register_unix_process_commands(shell)
        logging.info("Registered Unix process utilities")
    except Exception as e:
        logging.warning(f"Unix process utilities not available: {e}")
        
    # Register Unix-like user utilities
    try:
        from .commands.unix_user_utils import register_commands as register_unix_user_commands
        register_unix_user_commands(shell)
        logging.info("Registered Unix user utilities")
    except Exception as e:
        logging.warning(f"Unix user utilities not available: {e}")
        
    # Register Unix-like network utilities
    try:
        from .commands.unix_network_utils import register_commands as register_unix_network_commands
        register_unix_network_commands(shell)
        logging.info("Registered Unix network utilities")
    except Exception as e:
        logging.warning(f"Unix network utilities not available: {e}")
        
    # Register Unix-like system utilities
    try:
        from .commands.unix_sys_utils import register_commands as register_unix_sys_commands
        register_unix_sys_commands(shell)
        logging.info("Registered Unix system utilities")
    except Exception as e:
        logging.warning(f"Unix system utilities not available: {e}")
        
    # Register Unix-like package utilities
    try:
        from .commands.unix_package_utils import register_commands as register_unix_package_commands
        register_unix_package_commands(shell)
        logging.info("Registered Unix package utilities")
    except Exception as e:
        logging.warning(f"Unix package utilities not available: {e}")
        
    # Register Unix-like shell utilities
    try:
        from .commands.unix_shell_utils import register_commands as register_unix_shell_commands
        register_unix_shell_commands(shell)
        logging.info("Registered Unix shell utilities")
    except Exception as e:
        logging.warning(f"Unix shell utilities not available: {e}")
        
    # Register Unix-like init system utilities
    try:
        from .commands.unix_init_utils import register_commands as register_unix_init_commands
        register_unix_init_commands(shell)
        logging.info("Registered Unix init system utilities")
    except Exception as e:
        logging.warning(f"Unix init system utilities not available: {e}")
        
    # Register container utilities
    try:
        from .commands.container_utils import register_commands as register_container_commands
        register_container_commands(shell)
        logging.info("Registered container utilities")
    except Exception as e:
        logging.warning(f"Container utilities not available: {e}")
        
    # Register network management utilities
    try:
        from .commands.network_manager import register_commands as register_network_commands
        register_network_commands(shell)
        logging.info("Registered network management utilities")
    except Exception as e:
        logging.warning(f"Network management utilities not available: {e}")
        
    # Register firewall management utilities
    try:
        from .commands.firewall_manager import register_commands as register_firewall_commands
        register_firewall_commands(shell)
        logging.info("Registered firewall management utilities")
    except Exception as e:
        logging.warning(f"Firewall management utilities not available: {e}")
        
    # Register service management utilities
    try:
        from .commands.service_manager import register_commands as register_service_commands
        register_service_commands(shell)
        logging.info("Registered service management utilities")
    except Exception as e:
        logging.warning(f"Service management utilities not available: {e}")
        
    # Register service monitoring utilities
    try:
        from .commands.service_monitor_utils import register_commands as register_service_monitor_commands
        register_service_monitor_commands(shell)
        logging.info("Registered service monitoring utilities")
    except Exception as e:
        logging.warning(f"Service monitoring utilities not available: {e}")
        
    # Register scheduler utilities
    try:
        from .commands.scheduler_utils import register_commands as register_scheduler_commands
        register_scheduler_commands(shell)
        logging.info("Registered scheduler utilities")
    except Exception as e:
        logging.warning(f"Scheduler utilities not available: {e}")
        
    # Register user management utilities
    try:
        from .commands.user_management import register_commands as register_user_commands
        register_user_commands(shell)
        logging.info("Registered user management utilities")
    except Exception as e:
        logging.warning(f"User management utilities not available: {e}")
        
    # Register authentication utilities
    try:
        from .commands.auth_utils import register_commands as register_auth_commands
        register_auth_commands(shell)
        logging.info("Registered authentication utilities")
    except Exception as e:
        logging.warning(f"Authentication utilities not available: {e}")
        
    # Register job control utilities
    try:
        from .commands.job_control import register_commands as register_job_commands
        register_job_commands(shell)
        logging.info("Registered job control utilities")
    except Exception as e:
        logging.warning(f"Job control utilities not available: {e}")
        
    # Register accounting utilities
    try:
        from .commands.accounting_utils import register_commands as register_accounting_commands
        register_accounting_commands(shell)
        logging.info("Registered accounting utilities")
    except Exception as e:
        logging.warning(f"Accounting utilities not available: {e}")
    
    # Register repository management commands
    try:
        from .commands.repo_management import register_commands as register_repo_commands
        register_repo_commands(shell)
        logging.info("Registered repository management commands")
    except ImportError:
        logging.warning("Repository management commands not available")
    
    # Register application management commands
    try:
        from .commands.app_management import register_commands as register_app_commands
        register_app_commands(shell)
        logging.info("Registered application management commands")
    except ImportError:
        logging.warning("Application management commands not available")

    return shell

# Initialize the shell components
shell = init_shell()

# Export the shell instance
__all__.append('shell')

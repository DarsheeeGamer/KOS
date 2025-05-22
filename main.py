#!/usr/bin/env python3

"""
Kaede Operating System (KOS) - Main Entry Point

Usage:
    python main.py [--debug] [--show-logs]

Options:
    --debug      Enable debug mode (verbose logging)
    --show-logs  Show logs in console (implied by --debug)
"""

import logging
import sys
import argparse
from kos.filesystem import FileSystem
from kos.user_system import UserSystem
from kos.package_manager import KpmManager
from kos.commands import KaedeShell
from kos.auth_manager import AuthenticationManager
from kos.internal import system_manager, start_system, register_exit_handler

def setup_logging(debug=False, show_logs=False):
    """Configure logging based on debug and show_logs flags"""
    log_level = logging.DEBUG if debug else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # Always log to file
    handlers = [logging.FileHandler('kos.log')]
    
    # Only add console handler if in debug mode or explicitly requested
    if debug or show_logs:
        handlers.append(logging.StreamHandler())
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    # Set log level for specific loggers if needed
    if not debug:
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('asyncio').setLevel(logging.WARNING)
logger = logging.getLogger('KOS')

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Kaede Operating System (KOS)')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode (verbose logging)')
    parser.add_argument('--show-logs', action='store_true', 
                       help='Show logs in console (implied by --debug)')
    return parser.parse_args()

def main():
    """Initialize and start the Kaede Operating System"""
    # Parse command line arguments
    args = parse_arguments()
    
    # Configure logging based on arguments
    setup_logging(debug=args.debug, show_logs=args.show_logs)
    
    try:
        # Initialize KOS internal system manager first
        # This will install exit hooks to prevent unexpected exits
        start_system()
        
        # Initialize core systems
        logger.info("Initializing KOS components...")

        # Initialize filesystem first
        filesystem = FileSystem(disk_size_mb=100)
        logger.info("FileSystem initialized")

        # Initialize authentication manager
        auth_manager = AuthenticationManager()
        logger.info("Authentication Manager initialized")

        # Initialize user system with filesystem reference
        user_system = UserSystem(filesystem, auth_manager)
        logger.info("User System initialized")

        # Initialize package manager
        kpm_manager = KpmManager()
        logger.info("Package Manager initialized")

        # Start the shell with all required components
        logger.debug("Creating KaedeShell instance")
        shell = KaedeShell(
            filesystem=filesystem,
            kpm_manager=kpm_manager,
            user_system=user_system
        )
        logger.debug("KaedeShell instance created")
        
        # Register shell cleanup as an exit handler
        def shell_cleanup():
            logger.info("Performing shell cleanup during KOS exit")
            try:
                if hasattr(shell, '_cleanup'):
                    shell._cleanup()
                logger.info("Shell cleanup completed")
            except Exception as e:
                logger.error(f"Error during shell cleanup: {e}", exc_info=True)
        
        register_exit_handler(shell_cleanup)
        
        # Set debug flag on shell if debug mode is enabled
        shell.debug = args.debug
        
        # Import and use our custom shell loop
        logger.debug("Importing ShellLoop")
        from kos.shell_loop import ShellLoop
        
        logger.debug("Creating ShellLoop instance")
        shell_loop = ShellLoop(shell, debug=args.debug)
        
        try:
            logger.debug("Starting shell loop")
            shell_loop.run()
        except Exception as e:
            logger.error(f"Error in shell loop: {e}", exc_info=True)
            raise
        finally:
            logger.debug("Shell loop ended")

    except Exception as e:
        logger.error(f"Failed to start KOS: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
#!/usr/bin/env python3

"""
Kaede Operating System (KOS) - Main Entry Point
"""

import logging
from kos.filesystem import FileSystem
from kos.user_system import UserSystem
from kos.package_manager import KpmManager
from kos.commands import KaedeShell
from kos.auth_manager import AuthenticationManager
from kos.internal import system_manager, start_system, register_exit_handler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('kos.log')
    ]
)
logger = logging.getLogger('KOS')

def main():
    """Initialize and start the Kaede Operating System"""
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
                    logger.debug("Calling shell._cleanup()")
                    shell._cleanup()
                    logger.debug("shell._cleanup() completed")
            except Exception as e:
                logger.error(f"Error during shell cleanup: {e}", exc_info=True)
        
        logger.debug("Registering exit handler")
        register_exit_handler(shell_cleanup)
        
        # Import and use our custom shell loop
        logger.debug("Importing ShellLoop")
        from kos.shell_loop import ShellLoop
        
        logger.info("Shell initialized, starting command loop...")
        logger.debug("Creating ShellLoop instance")
        shell_loop = ShellLoop(shell)
        logger.debug("Starting ShellLoop")
        try:
            shell_loop.run()
            logger.debug("ShellLoop completed successfully")
        except Exception as e:
            logger.critical(f"ShellLoop crashed: {e}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Failed to start KOS: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
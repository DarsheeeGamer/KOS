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
        shell = KaedeShell(
            filesystem=filesystem,
            kpm_manager=kpm_manager,
            user_system=user_system
        )
        logger.info("Shell initialized, starting command loop...")
        shell.cmdloop()

    except Exception as e:
        logger.error(f"Failed to start KOS: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
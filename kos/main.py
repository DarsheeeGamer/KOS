#!/usr/bin/env python3

"""
Kaede Operating System (KOS) - Main Entry Point
"""

import logging
from .filesystem import FileSystem
from .user_system import UserSystem
from .package_manager import KappManager
from .commands import KaedeShell
from .auth_manager import AuthenticationManager

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
        kapp_manager = KappManager()
        logger.info("Package Manager initialized")

        # Start the shell with all required components
        shell = KaedeShell(
            filesystem=filesystem,
            kapp_manager=kapp_manager,
            user_system=user_system
        )
        logger.info("Shell initialized, starting command loop...")
        shell.cmdloop()

    except Exception as e:
        logger.error(f"Failed to start KOS: {e}")
        raise

if __name__ == "__main__":
    main()
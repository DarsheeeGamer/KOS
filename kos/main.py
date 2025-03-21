#!/usr/bin/env python3

"""
Kaede Operating System (KOS) - Main Entry Point
"""

import logging
import os
from .filesystem import FileSystem
from .user_system import UserSystem
from .package_manager import PackageManager
from .commands import KaedeShell
from .auth_manager import AuthenticationManager
from .klayer import initialize_klayer
from .process.manager import ProcessManager
from .boot.bootloader import KOSBootloader
from .kadv_layer import get_kadv_layer
from .kernel.core import KOSKernel

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
        # Create basic directory structure
        os.makedirs('kos_apps', exist_ok=True)
        os.makedirs('repo', exist_ok=True)
        logger.info("Basic directory structure created")
        
        # Initialize bootloader
        bootloader = KOSBootloader()
        bootloader.boot_stage_1()  # Perform basic initialization
        
        # Initialize core components
        filesystem = FileSystem(disk_size_mb=100)
        process_manager = ProcessManager()
        auth_manager = AuthenticationManager()
        user_system = UserSystem(filesystem, auth_manager)
        package_manager = PackageManager()
        
        # Initialize kLayer for application integration
        initialize_klayer(filesystem, package_manager, user_system, process_manager)
        
        # Initialize kernel
        kernel = KOSKernel(process_manager)
        kernel.initialize()
        
        # Initialize advanced layer
        kadv_layer = get_kadv_layer()
        
        # Complete boot process
        bootloader.boot_stage_2(user_system)  # User authentication stage
        
        # Start the shell with all required components
        shell = KaedeShell(
            filesystem=filesystem,
            kpm_manager=package_manager,
            user_system=user_system,
            process_manager=process_manager
        )
        
        bootloader.boot_complete()  # Finalize boot process
        logger.info("Shell initialized, starting command loop...")
        shell.cmdloop()

    except Exception as e:
        logger.error(f"Failed to start KOS: {e}")
        raise

if __name__ == "__main__":
    main()
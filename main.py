#!/usr/bin/env python3
"""
Kaede Operating System (KOS) - A Python-based Linux-like OS simulation
Main entry point
"""

import logging
import os
import sys
import signal
from kos.filesystem import FileSystem
from kos.user_system import UserSystem
from kos.package_manager import PackageManager
from kos.commands import KaedeShell
from kos.auth_manager import AuthenticationManager
from kos.klayer import initialize_klayer
from kos.process.manager import ProcessManager
from kos.boot.bootloader import KOSBootloader
from kos.kadv_layer import get_kadv_layer
from kos.kernel.core import KOSKernel

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

# Define virtual disk constants
VIRTUAL_DISK_FILE = "disk.kdsk"
VIRTUAL_DISK_SIZE_MB = 256  # 256 MB disk size

def reboot_system():
    """Reboot the KOS system"""
    logger.info("Rebooting KOS system...")
    python = sys.executable
    os.execl(python, python, *sys.argv)

def handle_reboot_signal(signum, frame):
    """Handle reboot signal"""
    logger.info("Received reboot signal")
    reboot_system()

def main():
    """Initialize and start KOS"""
    try:
        # Register reboot signal handler
        try:
            signal.signal(signal.SIGUSR1, handle_reboot_signal)
            logger.info("Registered reboot signal handler")
        except (AttributeError, ValueError) as e:
            # SIGUSR1 might not be available on all platforms
            logger.warning(f"Failed to register reboot signal handler: {e}")
        
        # Create basic directory structure
        os.makedirs('kos_apps', exist_ok=True)
        os.makedirs('repo', exist_ok=True)
        logger.info("Basic directory structure created")
        
        # Initialize bootloader
        bootloader = KOSBootloader()
        bootloader.boot_stage_1()  # Perform basic initialization
        
        # Initialize core components with encrypted virtual disk
        filesystem = FileSystem(disk_size_mb=VIRTUAL_DISK_SIZE_MB)
        filesystem.disk_file = VIRTUAL_DISK_FILE
        
        # Explicitly load filesystem from disk to ensure it's always loaded during boot
        logger.info("Loading filesystem state from disk...")
        if hasattr(filesystem, 'load_filesystem'):
            success = filesystem.load_filesystem()
            if success:
                logger.info("Successfully loaded filesystem state from disk")
            else:
                logger.warning("No existing filesystem state found, using fresh filesystem")
        
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
        
        # Add system reboot command function
        shell.reboot_function = reboot_system
        
        bootloader.boot_complete()  # Finalize boot process
        shell.cmdloop()
    except Exception as e:
        logger.error(f"Failed to start KOS: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()
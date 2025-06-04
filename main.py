#!/usr/bin/env python3

"""
KOS (Kaede Operating System) Main Entry Point
==============================================

Comprehensive Unix-like operating system with advanced features:
- Kaede programming language integration
- Advanced security and authentication
- Kernel-level system management
- Package management with repository support
- Real-time system monitoring
- Comprehensive shell environment
"""

import os
import sys
import logging
import argparse
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('KOS')

# Core KOS imports
try:
    from kos.base import get_system_state, get_service_manager, get_config_manager
    from kos.filesystem.base import FileSystem
    from kos.process.manager import ProcessManager
    from kos.package_manager import KpmManager
    from kos.user_system import UserSystem
    from kos.shell import KaedeShell
    from kos.repo_config import get_repository_manager
    CORE_AVAILABLE = True
except ImportError as e:
    logger.error(f"Critical KOS core components missing: {e}")
    print(f"Error: Cannot initialize KOS - {e}")
    CORE_AVAILABLE = False

# Try to import Kaede language components
try:
    from kos.kaede.stdlib import get_stdlib
    from kos.kaede import create_kaede_environment
    KAEDE_AVAILABLE = True
    logger.info("Kaede language components loaded successfully")
except ImportError as e:
    logger.warning(f"Kaede language not available: {e}")
    KAEDE_AVAILABLE = False
    create_kaede_environment = lambda: None

# Try to import KLayer and KADVLayer
try:
    from kos.layer import get_klayer
    from kos.advlayer import get_kadvlayer
    ADVANCED_LAYERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Advanced layers not fully available: {e}")
    ADVANCED_LAYERS_AVAILABLE = False
    get_klayer = lambda: None
    get_kadvlayer = lambda: None

# Try to import shell system
try:
    from kos.commands import KaedeShell as AlternativeShell
    SHELL_COMMANDS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Alternative shell commands not available: {e}")
    SHELL_COMMANDS_AVAILABLE = False
    AlternativeShell = None

class KOSSystem:
    """Main KOS System Controller"""
    
    def __init__(self, debug: bool = False, show_logs: bool = False):
        self.debug = debug
        self.show_logs = show_logs
        
        if self.debug:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Debug mode enabled")
        
        if not self.show_logs:
            logging.getLogger().setLevel(logging.WARNING)
        
        # Core components
        self.filesystem: Optional[FileSystem] = None
        self.process_manager: Optional[ProcessManager] = None
        self.user_system: Optional[UserSystem] = None
        self.package_manager: Optional[KpmManager] = None
        self.shell: Optional[KaedeShell] = None
        
        # Advanced components
        self.repository_manager = None
        self.klayer = None
        self.kadvlayer = None
        
        # Kaede environment
        self.kaede_env = None
        
        # System state
        self.system_state = None
        self.service_manager = None
        self.config_manager = None
        
        logger.info("KOS system started")
        
    def initialize(self) -> bool:
        """Initialize all KOS components"""
        try:
            logger.info("Initializing KOS components...")
            
            if not CORE_AVAILABLE:
                logger.error("Core components not available - cannot initialize")
                return False
            
            # Initialize base system
            self._init_base_system()
            
            # Initialize core components
            self._init_core_components()
            
            # Initialize repository system
            self._init_repository_system()
            
            # Initialize advanced layers
            if ADVANCED_LAYERS_AVAILABLE:
                self._init_advanced_layers()
            
            # Initialize Kaede environment
            if KAEDE_AVAILABLE:
                self._init_kaede_environment()
            
            # Initialize shell
            self._init_shell()
            
            logger.info("KOS initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"KOS initialization failed: {e}")
            return False
    
    def _init_base_system(self):
        """Initialize base system components"""
        logger.debug("Initializing base system...")
        
        self.system_state = get_system_state()
        self.service_manager = get_service_manager()
        self.config_manager = get_config_manager()
        
        # Set system state to running
        self.system_state.set_state("running")
        
        logger.debug("Base system initialized")
    
    def _init_core_components(self):
        """Initialize core system components"""
        logger.debug("Initializing core components...")
        
        # Filesystem
        try:
            self.filesystem = FileSystem()
            logger.debug("FileSystem initialized")
        except Exception as e:
            logger.error(f"Failed to initialize FileSystem: {e}")
            raise
        
        # Process manager
        try:
            self.process_manager = ProcessManager()
            logger.debug("ProcessManager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize ProcessManager: {e}")
            # Continue without process manager
            self.process_manager = None
        
        # User system
        try:
            self.user_system = UserSystem(self.filesystem, self.process_manager)
            logger.debug("UserSystem initialized")
        except Exception as e:
            logger.error(f"Failed to initialize UserSystem: {e}")
            # Continue without user system
            self.user_system = None
        
        # Package manager
        try:
            self.package_manager = KpmManager()
            logger.info("Package Manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Package Manager: {e}")
            # Continue without package manager
            self.package_manager = None
        
    def _init_repository_system(self):
        """Initialize repository management system"""
        try:
            logger.debug("Initializing repository system...")
            self.repository_manager = get_repository_manager()
            
            # Check if we need to update repositories
            stats = self.repository_manager.get_statistics()
            logger.info(f"Repository system initialized - {stats['repositories']['total']} repositories configured")
            
        except Exception as e:
            logger.error(f"Repository system initialization failed: {e}")
            # Don't fail completely - package manager can work without repos
            self.repository_manager = None
    
    def _init_advanced_layers(self):
        """Initialize advanced kernel layers"""
        try:
            logger.debug("Initializing advanced layers...")
            
            # KLayer - Kernel application layer
            self.klayer = get_klayer()
            if self.klayer:
                logger.debug("KLayer initialized")
            
            # KADVLayer - Advanced system layer
            self.kadvlayer = get_kadvlayer()
            if self.kadvlayer:
                logger.debug("KADVLayer initialized")
            
            if self.klayer or self.kadvlayer:
                logger.info("Advanced kernel layers initialized")
            
        except Exception as e:
            logger.warning(f"Advanced layers initialization failed: {e}")
            self.klayer = None
            self.kadvlayer = None
    
    def _init_kaede_environment(self):
        """Initialize Kaede programming environment"""
        try:
            logger.debug("Initializing Kaede environment...")
            
            # Create Kaede environment
            self.kaede_env = create_kaede_environment()
            
            if self.kaede_env:
                logger.info("Kaede programming environment initialized")
            else:
                logger.warning("Kaede environment creation failed")
                
        except Exception as e:
            logger.warning(f"Kaede environment initialization failed: {e}")
            self.kaede_env = None
    
    def _init_shell(self):
        """Initialize KOS shell"""
        try:
            logger.debug("Initializing shell...")
            
            # Try main shell first
            try:
                self.shell = KaedeShell(
                    filesystem=self.filesystem,
                    package_manager=self.package_manager,
                    process_manager=self.process_manager,
                    user_system=self.user_system
                )
                logger.info("Main shell initialized")
                return
            except Exception as e:
                logger.warning(f"Main shell initialization failed: {e}")
            
            # Try alternative shell if available
            if SHELL_COMMANDS_AVAILABLE and AlternativeShell:
                try:
                    self.shell = AlternativeShell(
                        filesystem=self.filesystem,
                        package_manager=self.package_manager,
                        process_manager=self.process_manager,
                        user_system=self.user_system
                    )
                    logger.info("Alternative shell initialized")
                    return
                except Exception as e:
                    logger.warning(f"Alternative shell initialization failed: {e}")
            
            # Create minimal shell if all else fails
            logger.warning("Creating minimal shell fallback")
            from kos.shell.minimal import MinimalShell
            self.shell = MinimalShell()
            
        except Exception as e:
            logger.error(f"Shell initialization failed completely: {e}")
            raise
    
    def run_interactive(self):
        """Run KOS in interactive shell mode"""
        if not self.shell:
            logger.error("Shell not initialized")
            return False
        
        try:
            logger.info("Starting interactive shell")
            self.shell.cmdloop()
            return True
            
        except KeyboardInterrupt:
            print("\nExiting KOS...")
            return True
        except Exception as e:
            logger.error(f"Shell execution failed: {e}")
            return False
    
    def run_command(self, command: str) -> bool:
        """Run a single command"""
        if not self.shell:
            logger.error("Shell not initialized")
            return False
        
        try:
            result = self.shell.onecmd(command)
            return result is not True  # Shell returns True to exit
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return False
    
    def get_system_status(self) -> dict:
        """Get comprehensive system status"""
        status = {
            "core": {
                "filesystem": self.filesystem is not None,
                "process_manager": self.process_manager is not None,
                "user_system": self.user_system is not None,
                "package_manager": self.package_manager is not None,
                "shell": self.shell is not None
            },
            "features": {
                "kaede_available": KAEDE_AVAILABLE,
                "advanced_layers": ADVANCED_LAYERS_AVAILABLE,
                "kaede_env": self.kaede_env is not None,
                "klayer": self.klayer is not None,
                "kadvlayer": self.kadvlayer is not None,
                "shell_commands": SHELL_COMMANDS_AVAILABLE
            },
            "availability": {
                "core_components": CORE_AVAILABLE,
                "kaede_language": KAEDE_AVAILABLE,
                "advanced_layers": ADVANCED_LAYERS_AVAILABLE,
                "shell_commands": SHELL_COMMANDS_AVAILABLE
            }
        }
        
        # Add repository statistics if available
        if self.repository_manager:
            try:
                repo_stats = self.repository_manager.get_statistics()
                status["repositories"] = repo_stats
            except Exception as e:
                logger.debug(f"Could not get repository stats: {e}")
        
        # Add package statistics if available
        if self.package_manager:
            try:
                packages = self.package_manager.list_packages()
                status["packages"] = {
                    "installed": len([p for p in packages.get("installed", {}).values() if p.get("installed", False)]),
                    "available": len(packages.get("available", []))
                }
            except Exception as e:
                logger.debug(f"Could not get package stats: {e}")
        
        # Add system state if available
        if self.system_state:
            try:
                sys_info = self.system_state.get_system_info()
                status["system_state"] = sys_info
            except Exception as e:
                logger.debug(f"Could not get system state: {e}")
        
        return status
    
    def cleanup(self):
        """Cleanup system resources"""
        logger.info("Cleaning up KOS system...")
        
        try:
            # Cleanup advanced layers
            if self.kadvlayer and hasattr(self.kadvlayer, 'shutdown'):
                self.kadvlayer.shutdown()
            
            if self.klayer and hasattr(self.klayer, 'shutdown'):
                self.klayer.shutdown()
            
            # Cleanup repository manager
            if self.repository_manager and hasattr(self.repository_manager, 'cleanup'):
                self.repository_manager.cleanup()
            
            # Cleanup other components
            if self.process_manager and hasattr(self.process_manager, 'cleanup'):
                self.process_manager.cleanup()
            
            # Cleanup service manager
            if self.service_manager:
                self.service_manager.stop_all_services()
            
            # Set final system state
            if self.system_state:
                self.system_state.set_state("shutdown")
            
            logger.info("KOS cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="KOS - Kaede Operating System")
    
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--show-logs", action="store_true", help="Show system logs")
    parser.add_argument("--command", "-c", help="Run a single command")
    parser.add_argument("--status", action="store_true", help="Show system status and exit")
    parser.add_argument("--check", action="store_true", help="Run system check and exit")
    parser.add_argument("--version", action="store_true", help="Show version information")
    parser.add_argument("--minimal", action="store_true", help="Start in minimal mode")
    
    return parser.parse_args()

def show_version():
    """Show version information"""
    print("KOS (Kaede Operating System) v1.0.0")
    print("A comprehensive Unix-like operating system with advanced features")
    print("Built around the Kaede programming language")
    print()
    print("Components:")
    print(f"  - Core Components: {'Available' if CORE_AVAILABLE else 'Not Available'}")
    print(f"  - Kaede Language: {'Available' if KAEDE_AVAILABLE else 'Not Available'}")
    print(f"  - Advanced Layers: {'Available' if ADVANCED_LAYERS_AVAILABLE else 'Not Available'}")
    print(f"  - Shell Commands: {'Available' if SHELL_COMMANDS_AVAILABLE else 'Not Available'}")
    print(f"  - Repository System: Available")
    print(f"  - Package Manager: Available")

def run_system_check():
    """Run system verification"""
    try:
        import subprocess
        result = subprocess.run([sys.executable, "system_check.py"], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to run system check: {e}")
        return False

def main():
    """Main entry point"""
    args = parse_arguments()
    
    if args.version:
        show_version()
        return 0
    
    if args.check:
        success = run_system_check()
        return 0 if success else 1
    
    if not CORE_AVAILABLE:
        print("ERROR: Core KOS components are not available!")
        print("Please ensure all required modules are installed and accessible.")
        return 1
    
    # Initialize KOS system
    kos = KOSSystem(debug=args.debug, show_logs=args.show_logs)
    
    if not kos.initialize():
        print("Failed to initialize KOS system")
        return 1
    
    if args.status:
        # Show system status
        status = kos.get_system_status()
        print("KOS System Status:")
        print("=" * 40)
        
        for category, items in status.items():
            print(f"\n{category.upper()}:")
            if isinstance(items, dict):
                for item, value in items.items():
                    if isinstance(value, bool):
                        status_str = "✓" if value else "✗"
                        print(f"  {status_str} {item}")
                    else:
                        print(f"  {item}: {value}")
            else:
                print(f"  {items}")
        
        return 0
    
    if args.command:
        # Run single command
        success = kos.run_command(args.command)
        return 0 if success else 1
    
    # Run interactive shell
    try:
        success = kos.run_interactive()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\nGoodbye!")
        return 0
    finally:
        kos.cleanup()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.error(f"Critical error: {e}")
        sys.exit(2)
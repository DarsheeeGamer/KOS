#!/usr/bin/env python3
"""
hello_py - KOS Python Application

This is a template KOS application written in Python.
"""

import sys
import argparse
import logging
from typing import Optional, List

# KOS API imports (when available)
# from kos import api
# from kos import system

# Application version
__version__ = "1.0.0"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class hello_pyApp:
    """Main application class for hello_py"""
    
    def __init__(self, debug: bool = False):
        self.app_name = "hello_py"
        self.version = __version__
        self.debug = debug
        
        if debug:
            logger.setLevel(logging.DEBUG)
            
    def run(self, args: List[str]) -> int:
        """Run the application"""
        
        logger.info(f"Starting {self.app_name} v{self.version}")
        
        # Initialize KOS runtime (when available)
        # kos.initialize()
        
        # Your application logic here
        print(f"Hello from {self.app_name}!")
        print("This is a KOS Python application template.")
        
        # Example: Get system information
        # try:
        #     info = kos.system.get_info()
        #     print(f"KOS Version: {info.version}")
        #     print(f"Platform: {info.platform}")
        # except Exception as e:
        #     logger.error(f"Failed to get system info: {e}")
        
        # Process any additional arguments
        if args:
            print(f"Arguments received: {args}")
        
        # Cleanup
        # kos.cleanup()
        
        logger.info(f"{self.app_name} completed successfully")
        return 0


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description=f"{name} - KOS Python Application",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '-v', '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='Enable debug mode'
    )
    
    parser.add_argument(
        'args',
        nargs='*',
        help='Additional arguments'
    )
    
    return parser.parse_args()


def main():
    """Main entry point"""
    # Parse arguments
    args = parse_arguments()
    
    # Create and run application
    app = hello_pyApp(debug=args.debug)
    
    try:
        sys.exit(app.run(args.args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

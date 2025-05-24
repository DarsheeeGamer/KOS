#!/usr/bin/env python
"""
KOS Command Line Interface

This module provides the command-line entry point for KOS when installed as a pip package.
"""

import os
import sys
import argparse
import logging
from typing import List, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('KOS.cli')

def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='KOS - Advanced Python-based Shell System',
        epilog='For more information, visit: https://github.com/DarsheeeGamer/KOS'
    )
    
    parser.add_argument(
        '-c', '--command',
        help='Execute a single command and exit',
        type=str
    )
    
    parser.add_argument(
        '-f', '--file',
        help='Execute commands from a file',
        type=str
    )
    
    parser.add_argument(
        '-i', '--interactive',
        help='Start in interactive mode even after executing commands',
        action='store_true'
    )
    
    parser.add_argument(
        '-d', '--debug',
        help='Enable debug logging',
        action='store_true'
    )
    
    parser.add_argument(
        '-v', '--version',
        help='Show version and exit',
        action='store_true'
    )
    
    return parser.parse_args(args)

def main(args: Optional[List[str]] = None) -> int:
    """Main entry point for the KOS CLI"""
    parsed_args = parse_args(args)
    
    # Configure logging level
    if parsed_args.debug:
        logging.getLogger('KOS').setLevel(logging.DEBUG)
    
    # Show version and exit if requested
    if parsed_args.version:
        from kos import __version__
        print(f"KOS version {__version__}")
        return 0
    
    # Import shell components
    from kos.shell import shell as kos_shell
    
    # Execute a single command if provided
    if parsed_args.command:
        result = kos_shell.execute_command(parsed_args.command)
        print(result)
        
        # Exit if not in interactive mode
        if not parsed_args.interactive:
            return 0
    
    # Execute commands from a file if provided
    if parsed_args.file:
        if not os.path.exists(parsed_args.file):
            print(f"Error: File '{parsed_args.file}' not found")
            return 1
        
        try:
            with open(parsed_args.file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        result = kos_shell.execute_command(line)
                        print(result)
        except Exception as e:
            print(f"Error executing commands from file: {e}")
            return 1
        
        # Exit if not in interactive mode
        if not parsed_args.interactive:
            return 0
    
    # Start interactive shell
    try:
        kos_shell.run_interactive()
    except KeyboardInterrupt:
        print("\nExiting KOS...")
    except Exception as e:
        logger.error(f"Error in interactive mode: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

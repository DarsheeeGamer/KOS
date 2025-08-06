#!/usr/bin/env python3
"""
KOS - Kaede Operating System v2.0
Clean architecture, actually works
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.WARNING,  # Only show warnings and errors
    format='%(levelname)s: %(message)s'
)

class KOS:
    """
    Main KOS System
    Clean, simple, functional
    """
    
    def __init__(self):
        self.vfs = None
        self.klayer = None
        self.kadvlayer = None
        self.kpm = None
        self.python_env = None
        self.shell = None
        self.config = None
    
    def initialize(self, verbose=False):
        """Initialize all KOS components"""
        if verbose:
            logging.getLogger().setLevel(logging.INFO)
        
        try:
            print("Initializing KOS v2.0...")
            
            # 1. Load configuration
            from kos.core import Config
            self.config = Config()
            
            # 2. Initialize VFS
            print("  → Loading Virtual File System...")
            from kos.core import get_vfs
            self.vfs = get_vfs(self.config.get('vfs.disk_path', 'kaede.kdsk'))
            
            # 3. Initialize KLayer
            print("  → Starting KLayer...")
            from kos.layers import KLayer
            self.klayer = KLayer(vfs=self.vfs)
            
            # 4. Initialize KADVLayer  
            print("  → Starting KADVLayer...")
            from kos.layers import KADVLayer
            self.kadvlayer = KADVLayer(klayer=self.klayer, vfs=self.vfs)
            
            # 5. Initialize KPM
            print("  → Loading Package Manager...")
            from kos.packages import KPM
            self.kpm = KPM(vfs=self.vfs)
            
            # 6. Initialize Python VFS Environment
            print("  → Setting up Python VFS environment...")
            from kos.packages import PythonVFSEnvironment
            self.python_env = PythonVFSEnvironment(vfs=self.vfs)
            
            # 7. Initialize Shell
            print("  → Preparing shell...")
            from kos.shell import KOSShell
            self.shell = KOSShell(
                vfs=self.vfs,
                klayer=self.klayer,
                kadvlayer=self.kadvlayer,
                kpm=self.kpm,
                python_env=self.python_env
            )
            
            print("✓ KOS initialized successfully!\n")
            return True
            
        except Exception as e:
            print(f"\n✗ Failed to initialize: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            return False
    
    def run_shell(self):
        """Run interactive shell"""
        if not self.shell:
            print("Error: Shell not initialized")
            return 1
        
        try:
            self.shell.cmdloop()
            return 0
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit")
            return self.run_shell()
        except Exception as e:
            print(f"Shell error: {e}")
            return 1
    
    def run_command(self, command):
        """Run a single command"""
        if not self.shell:
            print("Error: Shell not initialized")
            return 1
        
        try:
            self.shell.onecmd(command)
            return 0
        except Exception as e:
            print(f"Command error: {e}")
            return 1
    
    def show_status(self):
        """Show system status"""
        print("\n" + "="*50)
        print("KOS System Status")
        print("="*50)
        
        # Component status
        components = [
            ("VFS", self.vfs),
            ("KLayer", self.klayer),
            ("KADVLayer", self.kadvlayer),
            ("KPM", self.kpm),
            ("Python VFS", self.python_env),
            ("Shell", self.shell),
            ("Config", self.config)
        ]
        
        for name, component in components:
            status = "✓ Active" if component else "✗ Not loaded"
            print(f"{name:<15} {status}")
        
        # VFS info
        if self.vfs:
            print(f"\nVFS Disk: {self.vfs.disk_path}")
            try:
                root_entries = len(self.vfs.listdir('/'))
                print(f"Root entries: {root_entries}")
            except:
                pass
        
        # KLayer info
        if self.klayer:
            info = self.klayer.get_system_info()
            print(f"\nSystem Info:")
            print(f"  Hostname: {info['hostname']}")
            print(f"  Uptime: {info['uptime_str']}")
            print(f"  Processes: {info['process_count']}")
        
        return 0
    
    def shutdown(self):
        """Clean shutdown"""
        print("\nShutting down KOS...")
        
        # Shutdown layers
        if self.kadvlayer:
            self.kadvlayer.shutdown()
        
        if self.klayer:
            self.klayer.shutdown()
        
        # Unmount VFS
        if self.vfs:
            self.vfs.unmount()
        
        print("Goodbye!")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='KOS - Kaede Operating System v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py              # Start interactive shell
  python3 main.py -c "ls /"    # Run single command
  python3 main.py --status     # Show system status
        """
    )
    
    parser.add_argument('-c', '--command',
                       help='Execute a single command and exit')
    parser.add_argument('-s', '--status',
                       action='store_true',
                       help='Show system status and exit')
    parser.add_argument('-v', '--verbose',
                       action='store_true',
                       help='Enable verbose output')
    parser.add_argument('--version',
                       action='store_true',
                       help='Show version and exit')
    parser.add_argument('--clean',
                       action='store_true',
                       help='Start with clean VFS (delete existing)')
    
    args = parser.parse_args()
    
    # Show version
    if args.version:
        print("KOS - Kaede Operating System")
        print("Version 2.0 - Clean Architecture")
        print("Built with actual working code")
        return 0
    
    # Clean VFS if requested
    if args.clean:
        if os.path.exists('kaede.kdsk'):
            print("Removing existing VFS...")
            os.remove('kaede.kdsk')
            print("Starting with clean VFS")
    
    # Initialize KOS
    kos = KOS()
    if not kos.initialize(verbose=args.verbose):
        return 1
    
    try:
        # Execute requested action
        if args.status:
            return kos.show_status()
        elif args.command:
            return kos.run_command(args.command)
        else:
            return kos.run_shell()
    
    finally:
        kos.shutdown()

if __name__ == '__main__':
    sys.exit(main())
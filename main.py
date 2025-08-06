#!/usr/bin/env python3
"""
KOS - Kaede Operating System v3.0
Complete OS with KLayer and KADVLayer
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
        self.auth = None
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
            print("Initializing KOS v3.0...")
            
            # 1. Initialize KLayer (Core OS Layer)
            print("  → Starting KLayer (Core OS)...")
            from kos.layers.klayer import KLayer
            self.klayer = KLayer(disk_file='kaede.kdsk')
            self.vfs = self.klayer.vfs
            self.auth = self.klayer.auth
            
            # 2. Initialize KADVLayer (Advanced OS Layer)
            print("  → Starting KADVLayer (Advanced Services)...")
            from kos.layers.kadvlayer import KADVLayer
            self.kadvlayer = KADVLayer(klayer=self.klayer)
            
            # 3. Login as root for initialization
            print("  → Setting up root user...")
            if not self.klayer.user_login('root', 'root'):
                # Create root user if doesn't exist
                self.klayer.auth.create_user('root', 'root', 'ROOT')
                self.klayer.user_login('root', 'root')
            
            # 4. Initialize Shell
            print("  → Preparing shell...")
            from kos.shell.shell import Shell
            self.shell = Shell(self.vfs, self.auth, self.klayer.executor)
            
            # 5. Initialize Package Manager
            print("  → Loading Package Manager...")
            from kos.package.cli_integration import PackageManagerCLI
            self.kpm = PackageManagerCLI(self.vfs)
            
            # 6. Initialize Python Environment
            print("  → Setting up Python environment...")
            from kos.python_env import PythonVFSEnvironment
            self.python_env = PythonVFSEnvironment(self.vfs)
            
            print("✓ KOS initialized successfully!")
            print("✓ KLayer provides: filesystem, processes, users, devices")
            print("✓ KADVLayer provides: networking, services, monitoring, containers\n")
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
            ("Auth", self.auth),
            ("KLayer", self.klayer),
            ("KADVLayer", self.kadvlayer),
            ("KPM", self.kpm),
            ("Python VFS", self.python_env),
            ("Shell", self.shell)
        ]
        
        for name, component in components:
            status = "✓ Active" if component else "✗ Not loaded"
            print(f"{name:<15} {status}")
        
        # VFS info
        if self.vfs:
            print(f"\nVFS Disk: {self.vfs.disk_file}")
            try:
                root_entries = len(self.vfs.listdir('/'))
                print(f"Root entries: {root_entries}")
            except:
                pass
        
        # KLayer info
        if self.klayer:
            sys_info = self.klayer.sys_info()
            uptime = self.klayer.sys_uptime()
            mem_info = self.klayer.sys_memory_info()
            cpu_info = self.klayer.sys_cpu_info()
            
            print(f"\nKLayer System Info:")
            print(f"  Name: {sys_info['name']}")
            print(f"  Version: {sys_info['version']}")
            print(f"  Kernel: {sys_info['kernel']}")
            print(f"  Architecture: {sys_info['architecture']}")
            print(f"  Hostname: {sys_info['hostname']}")
            print(f"  Uptime: {int(uptime)} seconds")
            print(f"  CPU Cores: {cpu_info['cores']}")
            print(f"  Memory: {mem_info['used']/1024/1024:.0f}MB / {mem_info['total']/1024/1024:.0f}MB")
            
            if self.klayer.current_user:
                print(f"  Current User: {self.klayer.current_user.username}")
        
        # KADVLayer info
        if self.kadvlayer:
            print(f"\nKADVLayer Services:")
            print(f"  Network: {self.kadvlayer.network is not None}")
            print(f"  Firewall: {self.kadvlayer.firewall is not None}")
            print(f"  Web Server: {self.kadvlayer.web_server is not None}")
            print(f"  Database: {self.kadvlayer.database is not None}")
            print(f"  Containers: {len(self.kadvlayer.containers)}")
            print(f"  Apps: {len(self.kadvlayer.app_manager.apps) if self.kadvlayer.app_manager else 0}")
        
        return 0
    
    def shutdown(self):
        """Clean shutdown"""
        print("\nShutting down KOS...")
        
        # Stop services in KADVLayer
        if self.kadvlayer:
            try:
                self.kadvlayer.monitor.stop() if hasattr(self.kadvlayer.monitor, 'stop') else None
                self.kadvlayer.cron.stop() if hasattr(self.kadvlayer.cron, 'stop') else None
                self.kadvlayer.syslog.stop() if hasattr(self.kadvlayer.syslog, 'stop') else None
            except:
                pass
        
        # Shutdown KLayer
        if self.klayer:
            self.klayer.shutdown()
        
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
        print("Version 3.0 - Complete OS")
        print("KLayer: Core OS Services")
        print("KADVLayer: Advanced Services")
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
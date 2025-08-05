#!/usr/bin/env python3
"""
KOS (Kaede Operating System) Main Launcher
A Python-based Virtual Operating System

Usage:
    python kos_launcher.py [options]
    
Options:
    --memory SIZE       Set total memory (default: 4GB)
    --cpus COUNT        Set CPU count (default: 4)
    --init PATH         Set init process (default: /sbin/init)
    --debug             Enable debug output
    --interactive       Start in interactive mode
    --shell             Start KOS shell directly
    --version           Show version information
    
Examples:
    python kos_launcher.py                    # Normal boot
    python kos_launcher.py --shell            # Direct shell
    python kos_launcher.py --debug            # Debug boot
    python kos_launcher.py --memory 2GB       # Custom memory
"""

import sys
import os
import argparse
import signal
import time
from typing import Optional

# Add KOS to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class KOSLauncher:
    """Main KOS launcher and manager"""
    
    def __init__(self):
        self.kernel = None
        self.running = False
        
    def parse_args(self):
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(
            prog='KOS',
            description='KOS (Kaede Operating System) - Python Virtual OS',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=__doc__.split('Usage:')[1]
        )
        
        parser.add_argument('--memory', default='4GB',
                          help='Total memory size (default: 4GB)')
        parser.add_argument('--cpus', type=int, default=4,
                          help='Number of CPUs (default: 4)')
        parser.add_argument('--init', default='/sbin/init',
                          help='Init process path (default: /sbin/init)')
        parser.add_argument('--debug', action='store_true',
                          help='Enable debug output')
        parser.add_argument('--interactive', action='store_true',
                          help='Start in interactive mode')
        parser.add_argument('--shell', action='store_true',
                          help='Start KOS shell directly')
        parser.add_argument('--version', action='version',
                          version='KOS 1.0.0-Kaede (Python Virtual OS)')
        
        return parser.parse_args()
        
    def parse_memory_size(self, size_str: str) -> int:
        """Parse memory size string to bytes"""
        size_str = size_str.upper()
        if size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        else:
            return int(size_str)
            
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, shutting down KOS...")
            self.shutdown()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    def boot_kos(self, args) -> 'KOSKernel':
        """Boot KOS with given configuration"""
        from kos.boot.bootloader import KOSBootloader
        
        print("=" * 60)
        print("KOS (Kaede Operating System) Launcher")
        print("Python-based Virtual Operating System")
        print("Version: 1.0.0-Kaede")
        print("=" * 60)
        print()
        
        # Parse memory size
        memory_size = self.parse_memory_size(args.memory)
        
        # Create hardware configuration
        hardware_config = {
            'memory': {'total': memory_size},
            'cpu': {
                'cores': args.cpus,
                'model': 'KOS Virtual CPU',
                'frequency': 2400
            },
            'storage': [
                {
                    'device': '/dev/vda',
                    'size': 20 * 1024 * 1024 * 1024,  # 20GB
                    'type': 'virtio'
                }
            ]
        }
        
        # Create boot parameters
        boot_params = {
            'init': args.init,
            'root': '/dev/vda1',
            'quiet': not args.debug,
            'runlevel': 5,
            'ro': True
        }
        
        # Boot KOS
        print("Booting KOS...")
        bootloader = KOSBootloader()
        
        # Override hardware detection for custom config
        bootloader.hardware_info = hardware_config
        bootloader.boot_params = boot_params
        
        kernel = bootloader.boot()
        
        print(f"\n✓ KOS booted successfully in {kernel.get_uptime():.3f} seconds!")
        print(f"Memory: {memory_size // (1024*1024)}MB")
        print(f"CPUs: {args.cpus}")
        print(f"Init: {args.init}")
        print()
        
        return kernel
        
    def start_shell(self, kernel):
        """Start KOS shell"""
        from kos.shell.shell import KOSShell
        
        print("Starting KOS Shell...")
        print("Type 'help' for available commands, 'exit' to quit")
        print("-" * 50)
        
        shell = KOSShell(kernel)
        shell.run()
        
    def interactive_mode(self, kernel):
        """Run KOS in interactive mode"""
        print("KOS Interactive Mode")
        print("Available commands:")
        print("  shell     - Start KOS shell")
        print("  status    - Show system status")
        print("  network   - Show network status")
        print("  memory    - Show memory status")
        print("  processes - Show process status")
        print("  shutdown  - Shutdown KOS")
        print("  help      - Show this help")
        print()
        
        while self.running:
            try:
                cmd = input("KOS> ").strip().lower()
                
                if cmd == 'shell':
                    self.start_shell(kernel)
                elif cmd == 'status':
                    self.show_status(kernel)
                elif cmd == 'network':
                    self.show_network_status(kernel)
                elif cmd == 'memory':
                    self.show_memory_status(kernel)
                elif cmd == 'processes':
                    self.show_process_status(kernel)
                elif cmd == 'shutdown':
                    break
                elif cmd == 'help':
                    print("Available commands: shell, status, network, memory, processes, shutdown, help")
                elif cmd == '':
                    continue
                else:
                    print(f"Unknown command: {cmd}")
                    
            except (EOFError, KeyboardInterrupt):
                break
                
        self.shutdown()
        
    def show_status(self, kernel):
        """Show system status"""
        print("\n=== KOS System Status ===")
        print(f"Kernel: {kernel.system_info['kernel_version']}")
        print(f"Uptime: {kernel.get_uptime():.1f} seconds")
        print(f"State: {kernel.state.value}")
        print(f"Load Average: {', '.join(map(str, kernel.get_load_average()))}")
        
        # Memory info
        mem_info = kernel.get_memory_info()
        if mem_info:
            print(f"Memory: {mem_info['used']//1024//1024}MB / {mem_info['total']//1024//1024}MB used")
            
        # Process info
        proc_info = kernel.get_process_count()
        print(f"Processes: {proc_info['total']} total, {proc_info['running']} running")
        print()
        
    def show_network_status(self, kernel):
        """Show network status"""
        if not kernel.network_stack:
            print("Network stack not available")
            return
            
        print("\n=== Network Status ===")
        print(str(kernel.network_stack))
        
        print("\nInterfaces:")
        for name, iface in kernel.network_stack.get_interfaces().items():
            print(f"  {name}: {iface.ip} ({iface.state.value}) MAC: {iface.mac}")
            
        print("\nRoutes:")
        for route in kernel.network_stack.get_routes()[:5]:  # Show first 5
            print(f"  {route.destination} via {route.gateway} dev {route.interface}")
        print()
        
    def show_memory_status(self, kernel):
        """Show memory status"""
        print("\n=== Memory Status ===")
        if kernel.memory_manager:
            mem_info = kernel.get_memory_info()
            print(f"Total:    {mem_info['total']//1024//1024:>8} MB")
            print(f"Used:     {mem_info['used']//1024//1024:>8} MB")
            print(f"Free:     {mem_info['free']//1024//1024:>8} MB")
            print(f"Cached:   {mem_info['cached']//1024//1024:>8} MB")
            print(f"Buffers:  {mem_info['buffers']//1024//1024:>8} MB")
        print()
        
    def show_process_status(self, kernel):
        """Show process status"""
        print("\n=== Process Status ===")
        if kernel.process_manager:
            stats = kernel.get_process_count()
            print(f"Total processes: {stats['total']}")
            print(f"Running: {stats['running']}")
            print(f"Sleeping: {stats['sleeping']}")
        print()
        
    def shutdown(self):
        """Shutdown KOS"""
        self.running = False
        if self.kernel:
            print("Shutting down KOS...")
            self.kernel.halt()
            
    def run(self):
        """Main launcher entry point"""
        args = self.parse_args()
        self.setup_signal_handlers()
        
        try:
            # Boot KOS
            self.kernel = self.boot_kos(args)
            self.running = True
            
            # Choose mode
            if args.shell:
                self.start_shell(self.kernel)
            elif args.interactive:
                self.interactive_mode(self.kernel)
            else:
                # Default: show status and exit
                self.show_status(self.kernel)
                print("KOS is running. Use --interactive or --shell for interaction.")
                print("Press Ctrl+C to shutdown.")
                
                # Keep running until signal
                try:
                    while self.running:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
                    
        except Exception as e:
            print(f"Error: {e}")
            if args.debug:
                import traceback
                traceback.print_exc()
            return 1
        finally:
            self.shutdown()
            
        return 0

def main():
    """Main entry point"""
    launcher = KOSLauncher()
    return launcher.run()

if __name__ == "__main__":
    sys.exit(main())
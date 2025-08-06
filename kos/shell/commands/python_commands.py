"""
Python and pip commands for KOS shell
"""

from typing import List, Optional

class PythonCommands:
    """Python-related shell commands"""
    
    def __init__(self, shell):
        self.shell = shell
        self.vfs = shell.vfs
        self.klayer = getattr(shell, 'klayer', None)
    
    def do_python(self, args: str) -> None:
        """Run Python interpreter or execute Python code
        Usage: python [file.py | -c "code"]
        """
        if not self.klayer:
            print("Python not available")
            return
        
        if not args:
            # Start REPL
            self.klayer.python_repl()
        elif args.startswith('-c '):
            # Execute code
            code = args[3:].strip('"\'')
            result = self.klayer.python_execute(code)
            if result['success']:
                if result['stdout']:
                    print(result['stdout'], end='')
                if result['stderr']:
                    print(result['stderr'], end='')
            else:
                print(f"Error: {result['error']}")
        else:
            # Execute file
            filepath = args.strip()
            if not filepath.startswith('/'):
                filepath = f"{self.shell.current_dir}/{filepath}"
            
            result = self.klayer.python_execute_file(filepath)
            if result['success']:
                if result['stdout']:
                    print(result['stdout'], end='')
                if result['stderr']:
                    print(result['stderr'], end='')
            else:
                print(f"Error: {result['error']}")
    
    def do_pip(self, args: str) -> None:
        """Python package manager
        Usage: pip install|uninstall|list [package]
        """
        if not self.klayer:
            print("pip not available")
            return
        
        parts = args.split()
        if not parts:
            print("Usage: pip install|uninstall|list [package]")
            return
        
        command = parts[0]
        
        if command == 'install':
            if len(parts) < 2:
                print("Usage: pip install <package> [version]")
                return
            
            package = parts[1]
            version = parts[2] if len(parts) > 2 else None
            
            print(f"Installing {package}...")
            if self.klayer.python_install_package(package, version):
                print(f"Successfully installed {package}")
            else:
                print(f"Failed to install {package}")
        
        elif command == 'uninstall':
            if len(parts) < 2:
                print("Usage: pip uninstall <package>")
                return
            
            package = parts[1]
            
            print(f"Uninstalling {package}...")
            if self.klayer.python_uninstall_package(package):
                print(f"Successfully uninstalled {package}")
            else:
                print(f"Failed to uninstall {package}")
        
        elif command == 'list':
            packages = self.klayer.python_list_packages()
            if packages:
                print("Installed packages:")
                for pkg in packages:
                    print(f"  {pkg['name']} {pkg.get('version', 'unknown')}")
            else:
                print("No packages installed")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: pip install|uninstall|list [package]")
    
    def do_venv(self, args: str) -> None:
        """Create or manage Python virtual environments
        Usage: venv create <name> [path]
        """
        if not self.klayer:
            print("venv not available")
            return
        
        parts = args.split()
        if not parts:
            print("Usage: venv create <name> [path]")
            return
        
        command = parts[0]
        
        if command == 'create':
            if len(parts) < 2:
                print("Usage: venv create <name> [path]")
                return
            
            name = parts[1]
            path = parts[2] if len(parts) > 2 else None
            
            print(f"Creating virtual environment '{name}'...")
            if self.klayer.python_create_venv(name, path):
                print(f"Virtual environment '{name}' created")
                if not path:
                    path = f"/home/user/venvs/{name}"
                print(f"To activate: source {path}/bin/activate")
            else:
                print(f"Failed to create virtual environment")
        
        else:
            print(f"Unknown command: {command}")
            print("Usage: venv create <name> [path]")


class MemoryCommands:
    """Memory management commands"""
    
    def __init__(self, shell):
        self.shell = shell
        self.klayer = getattr(shell, 'klayer', None)
    
    def do_free(self, args: str) -> None:
        """Display memory usage
        Usage: free [-h]
        """
        if not self.klayer:
            print("Memory info not available")
            return
        
        mem_info = self.klayer.sys_memory_info()
        
        human = '-h' in args
        
        def format_bytes(b):
            if not human:
                return str(b)
            
            for unit in ['B', 'K', 'M', 'G', 'T']:
                if b < 1024:
                    return f"{b:.1f}{unit}"
                b /= 1024
            return f"{b:.1f}P"
        
        print("              total        used        free      shared  buff/cache   available")
        print(f"Mem:    {format_bytes(mem_info['total']):>11} "
              f"{format_bytes(mem_info['used']):>11} "
              f"{format_bytes(mem_info['free']):>11} "
              f"{format_bytes(mem_info.get('shared', 0)):>11} "
              f"{format_bytes(mem_info.get('buffers', 0) + mem_info.get('cached', 0)):>11} "
              f"{format_bytes(mem_info['available']):>11}")
        
        if mem_info.get('swap_total', 0) > 0:
            print(f"Swap:   {format_bytes(mem_info['swap_total']):>11} "
                  f"{format_bytes(mem_info.get('swap_used', 0)):>11} "
                  f"{format_bytes(mem_info.get('swap_free', 0)):>11}")
    
    def do_memstat(self, args: str) -> None:
        """Show detailed memory statistics
        Usage: memstat [pid]
        """
        if not self.klayer:
            print("Memory stats not available")
            return
        
        if args:
            # Show process memory
            try:
                pid = int(args)
                mem_usage = self.klayer.mem_get_process_usage(pid)
                print(f"Memory usage for PID {pid}:")
                print(f"  Total:  {mem_usage['total']} bytes")
                print(f"  Heap:   {mem_usage['heap']} bytes")
                print(f"  Stack:  {mem_usage['stack']} bytes")
                print(f"  Shared: {mem_usage['shared']} bytes")
                print(f"  Mapped: {mem_usage['mapped']} bytes")
            except ValueError:
                print("Invalid PID")
        else:
            # Show system memory
            stats = self.klayer.memory.get_stats()
            print("System Memory Statistics:")
            print(f"  Total:     {stats.total:,} bytes")
            print(f"  Used:      {stats.used:,} bytes")
            print(f"  Free:      {stats.free:,} bytes")
            print(f"  Available: {stats.available:,} bytes")
            print(f"  Percent:   {stats.percent:.1f}%")
            
            # Show allocations
            allocations = self.klayer.memory.allocator.dump_allocations()
            if allocations:
                print(f"\nActive allocations: {len(allocations)}")
                print(f"Total allocated: {sum(a['size'] for a in allocations):,} bytes")
    
    def do_gc(self, args: str) -> None:
        """Run garbage collection
        Usage: gc
        """
        if not self.klayer:
            print("Garbage collection not available")
            return
        
        print("Running garbage collection...")
        freed = self.klayer.mem_garbage_collect()
        print(f"Freed {freed:,} bytes")


def register_commands(shell):
    """Register Python and memory commands with shell"""
    python_cmds = PythonCommands(shell)
    memory_cmds = MemoryCommands(shell)
    
    # Register Python commands
    shell.do_python = python_cmds.do_python
    shell.do_pip = python_cmds.do_pip
    shell.do_venv = python_cmds.do_venv
    
    # Register memory commands
    shell.do_free = memory_cmds.do_free
    shell.do_memstat = memory_cmds.do_memstat
    shell.do_gc = memory_cmds.do_gc
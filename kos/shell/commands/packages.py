"""
Package management commands for KOS Shell
"""

import shlex

def register_commands(shell):
    """Register package commands with shell"""
    
    def do_kpm(self, arg):
        """KOS Package Manager
        Usage:
            kpm install <package>  - Install a package
            kpm uninstall <package> - Uninstall a package
            kpm list [--installed]  - List packages
            kpm search <query>      - Search packages
            kpm info <package>      - Show package info
            kpm upgrade [package]   - Upgrade package(s)
        """
        if not self.kpm:
            print("KPM not available")
            return
        
        args = shlex.split(arg)
        
        if not args:
            print(self.do_kpm.__doc__)
            return
        
        command = args[0]
        
        if command == 'install':
            if len(args) < 2:
                print("Usage: kpm install <package>")
                return
            
            for pkg in args[1:]:
                success, message = self.kpm.install(pkg)
                print(message)
        
        elif command == 'uninstall' or command == 'remove':
            if len(args) < 2:
                print("Usage: kpm uninstall <package>")
                return
            
            for pkg in args[1:]:
                success, message = self.kpm.uninstall(pkg)
                print(message)
        
        elif command == 'list':
            installed_only = '--installed' in args
            packages = self.kpm.list_packages(installed_only)
            
            if not packages:
                print("No packages found")
            else:
                print(f"{'Package':<20} {'Version':<10} {'Status':<12} {'Description'}")
                print("-" * 70)
                for pkg in packages:
                    status = 'installed' if pkg.installed else 'available'
                    desc = pkg.description[:35] + '...' if len(pkg.description) > 35 else pkg.description
                    print(f"{pkg.name:<20} {pkg.version:<10} {status:<12} {desc}")
        
        elif command == 'search':
            if len(args) < 2:
                print("Usage: kpm search <query>")
                return
            
            query = ' '.join(args[1:])
            results = self.kpm.search(query)
            
            if not results:
                print(f"No packages found for '{query}'")
            else:
                print(f"Found {len(results)} package(s):")
                for pkg in results:
                    status = '[installed]' if pkg.installed else ''
                    print(f"  {pkg.name} ({pkg.version}) {status} - {pkg.description}")
        
        elif command == 'info':
            if len(args) < 2:
                print("Usage: kpm info <package>")
                return
            
            pkg = self.kpm.info(args[1])
            if not pkg:
                print(f"Package '{args[1]}' not found")
            else:
                print(f"Package: {pkg.name}")
                print(f"Version: {pkg.version}")
                print(f"Author: {pkg.author}")
                print(f"Description: {pkg.description}")
                print(f"Status: {'Installed' if pkg.installed else 'Not installed'}")
                if pkg.installed and pkg.install_date:
                    from datetime import datetime
                    install_time = datetime.fromtimestamp(pkg.install_date)
                    print(f"Installed: {install_time.strftime('%Y-%m-%d %H:%M')}")
                if pkg.dependencies:
                    print(f"Dependencies: {', '.join(pkg.dependencies)}")
                if pkg.size > 0:
                    print(f"Size: {pkg.size // 1024} KB")
        
        elif command == 'upgrade':
            if len(args) > 1:
                # Upgrade specific package
                success, message = self.kpm.upgrade(args[1])
            else:
                # Upgrade all
                success, message = self.kpm.upgrade()
            print(message)
        
        else:
            print(f"Unknown kpm command: {command}")
            print("Type 'kpm' for usage")
    
    def do_pip(self, arg):
        """Python package manager for VFS
        Usage:
            pip install <package>    - Install Python package to VFS
            pip uninstall <package>  - Uninstall Python package
            pip list                 - List installed packages
            pip show <package>       - Show package info
        """
        if not self.python_env:
            print("Python VFS environment not available")
            return
        
        args = shlex.split(arg)
        
        if not args:
            print(self.do_pip.__doc__)
            return
        
        command = args[0]
        
        if command == 'install':
            if len(args) < 2:
                print("Usage: pip install <package>")
                return
            
            for pkg in args[1:]:
                upgrade = '--upgrade' in args or '-U' in args
                print(f"Installing {pkg} to VFS...")
                success, message = self.python_env.pip_install(pkg, upgrade)
                print(message)
        
        elif command == 'uninstall':
            if len(args) < 2:
                print("Usage: pip uninstall <package>")
                return
            
            for pkg in args[1:]:
                success, message = self.python_env.pip_uninstall(pkg)
                print(message)
        
        elif command == 'list':
            packages = self.python_env.pip_list()
            
            if not packages:
                print("No Python packages installed in VFS")
            else:
                print(f"{'Package':<30} {'Version':<15} {'Location'}")
                print("-" * 70)
                for pkg in packages:
                    print(f"{pkg.name:<30} {pkg.version:<15} {pkg.location}")
        
        elif command == 'show':
            if len(args) < 2:
                print("Usage: pip show <package>")
                return
            
            pkg = self.python_env.pip_show(args[1])
            if not pkg:
                print(f"Package '{args[1]}' not found")
            else:
                print(f"Name: {pkg.name}")
                print(f"Version: {pkg.version}")
                print(f"Location: {pkg.location}")
                if pkg.install_date:
                    from datetime import datetime
                    install_time = datetime.fromtimestamp(pkg.install_date)
                    print(f"Installed: {install_time.strftime('%Y-%m-%d %H:%M')}")
                if pkg.size > 0:
                    print(f"Size: {pkg.size // 1024} KB")
        
        else:
            print(f"Unknown pip command: {command}")
            print("Type 'pip' for usage")
    
    # Register commands
    shell.do_kpm = do_kpm
    shell.do_pip = do_pip
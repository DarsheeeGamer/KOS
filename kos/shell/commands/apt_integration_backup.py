"""
APT Package Manager Integration for KOS
=======================================

Provides APT (Advanced Package Tool) integration:
- apt and apt-get command wrappers
- sudo support for privileged operations
- Package management through host system
- Repository management
- Dependency handling
"""

import os
import sys
import subprocess
import json
import time
import re
import threading
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger('KOS.shell.apt_integration')

class AptOperation(Enum):
    """APT operation types"""
    UPDATE = "update"
    UPGRADE = "upgrade"
    INSTALL = "install"
    REMOVE = "remove"
    PURGE = "purge"
    SEARCH = "search"
    SHOW = "show"
    LIST = "list"
    AUTOREMOVE = "autoremove"
    AUTOCLEAN = "autoclean"
    CLEAN = "clean"

@dataclass
class PackageInfo:
    """APT package information"""
    name: str
    version: str = ""
    installed_version: str = ""
    description: str = ""
    maintainer: str = ""
    homepage: str = ""
    section: str = ""
    priority: str = ""
    size: int = 0
    installed_size: int = 0
    depends: List[str] = None
    recommends: List[str] = None
    suggests: List[str] = None
    conflicts: List[str] = None
    status: str = ""
    
    def __post_init__(self):
        if self.depends is None:
            self.depends = []
        if self.recommends is None:
            self.recommends = []
        if self.suggests is None:
            self.suggests = []
        if self.conflicts is None:
            self.conflicts = []

class SudoManager:
    """Handle sudo operations for APT"""
    
    def __init__(self):
        self.sudo_timeout = 300  # 5 minutes
        self.last_sudo_time = 0
        self.has_sudo = self._check_sudo_available()
    
    def _check_sudo_available(self) -> bool:
        """Check if sudo is available"""
        try:
            result = subprocess.run(
                ['which', 'sudo'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def can_sudo(self) -> bool:
        """Check if current user can use sudo"""
        if not self.has_sudo:
            return False
        
        try:
            result = subprocess.run(
                ['sudo', '-n', 'true'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def run_with_sudo(self, command: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """Run command with sudo"""
        if not self.has_sudo:
            raise RuntimeError("sudo is not available")
        
        # Check if we need to refresh sudo credentials
        current_time = time.time()
        if current_time - self.last_sudo_time > self.sudo_timeout:
            if not self.can_sudo():
                # Try to authenticate
                print("KOS requires sudo privileges for this operation.")
                try:
                    subprocess.run(['sudo', 'true'], check=True, timeout=30)
                    self.last_sudo_time = current_time
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    raise RuntimeError("sudo authentication failed")
        
        # Run command with sudo
        sudo_command = ['sudo'] + command
        return subprocess.run(
            sudo_command,
            capture_output=True,
            text=True,
            timeout=timeout
        )

class AptCache:
    """APT package cache management"""
    
    def __init__(self):
        self.cache_dir = os.path.expanduser("~/.kos/apt_cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        self.package_cache = {}
        self.last_update = 0
        self.cache_validity = 3600  # 1 hour
    
    def is_cache_valid(self) -> bool:
        """Check if cache is still valid"""
        return (time.time() - self.last_update) < self.cache_validity
    
    def update_cache(self):
        """Update package cache"""
        try:
            # Get installed packages
            result = subprocess.run(
                ['dpkg', '-l'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self._parse_dpkg_output(result.stdout)
            
            # Get available packages (simplified)
            result = subprocess.run(
                ['apt', 'list', '--available'],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                self._parse_apt_list_output(result.stdout)
            
            self.last_update = time.time()
            
        except Exception as e:
            logger.error(f"Failed to update APT cache: {e}")
    
    def _parse_dpkg_output(self, output: str):
        """Parse dpkg -l output"""
        lines = output.split('\n')
        for line in lines:
            if line.startswith('ii'):  # Installed packages
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[1]
                    version = parts[2]
                    description = ' '.join(parts[3:]) if len(parts) > 3 else ""
                    
                    if name not in self.package_cache:
                        self.package_cache[name] = PackageInfo(name)
                    
                    self.package_cache[name].installed_version = version
                    self.package_cache[name].description = description
                    self.package_cache[name].status = "installed"
    
    def _parse_apt_list_output(self, output: str):
        """Parse apt list output"""
        lines = output.split('\n')
        for line in lines:
            if '/' in line and not line.startswith('WARNING'):
                parts = line.split()
                if len(parts) >= 2:
                    name_arch = parts[0]
                    name = name_arch.split('/')[0]
                    version = parts[1]
                    
                    if name not in self.package_cache:
                        self.package_cache[name] = PackageInfo(name)
                    
                    self.package_cache[name].version = version
    
    def get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Get package information"""
        if not self.is_cache_valid():
            self.update_cache()
        
        return self.package_cache.get(package_name)
    
    def search_packages(self, query: str) -> List[PackageInfo]:
        """Search for packages"""
        if not self.is_cache_valid():
            self.update_cache()
        
        results = []
        query_lower = query.lower()
        
        for pkg in self.package_cache.values():
            if (query_lower in pkg.name.lower() or 
                query_lower in pkg.description.lower()):
                results.append(pkg)
        
        return sorted(results, key=lambda p: p.name)

class AptInterface:
    """Main APT interface"""
    
    def __init__(self):
        self.sudo_manager = SudoManager()
        self.cache = AptCache()
        self.dry_run = False
        self.verbose = False
        self.assume_yes = False
    
    def update(self) -> Tuple[bool, str]:
        """Update package lists"""
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt update"
            
            print("Updating package lists...")
            
            result = self.sudo_manager.run_with_sudo(['apt', 'update'])
            
            if result.returncode == 0:
                self.cache.update_cache()
                return True, "Package lists updated successfully"
            else:
                return False, f"Failed to update package lists: {result.stderr}"
                
        except Exception as e:
            return False, f"Error updating package lists: {e}"
    
    def upgrade(self, packages: List[str] = None) -> Tuple[bool, str]:
        """Upgrade packages"""
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt upgrade"
            
            cmd = ['apt', 'upgrade']
            if self.assume_yes:
                cmd.append('-y')
            if packages:
                cmd.extend(packages)
            
            if self.dry_run:
                cmd.append('--dry-run')
                print("DRY RUN: Would execute:", ' '.join(cmd))
                return True, "Dry run completed"
            
            print("Upgrading packages...")
            result = self.sudo_manager.run_with_sudo(cmd, timeout=600)
            
            if result.returncode == 0:
                self.cache.update_cache()
                return True, "Packages upgraded successfully"
            else:
                return False, f"Failed to upgrade packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error upgrading packages: {e}"
    
    def install(self, packages: List[str]) -> Tuple[bool, str]:
        """Install packages"""
        if not packages:
            return False, "No packages specified"
        
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt install"
            
            cmd = ['apt', 'install']
            if self.assume_yes:
                cmd.append('-y')
            cmd.extend(packages)
            
            if self.dry_run:
                cmd.append('--dry-run')
                print("DRY RUN: Would execute:", ' '.join(cmd))
                return True, "Dry run completed"
            
            print(f"Installing packages: {', '.join(packages)}")
            result = self.sudo_manager.run_with_sudo(cmd, timeout=600)
            
            if result.returncode == 0:
                self.cache.update_cache()
                return True, f"Packages installed successfully: {', '.join(packages)}"
            else:
                return False, f"Failed to install packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error installing packages: {e}"
    
    def remove(self, packages: List[str], purge: bool = False) -> Tuple[bool, str]:
        """Remove packages"""
        if not packages:
            return False, "No packages specified"
        
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt remove"
            
            cmd = ['apt', 'purge' if purge else 'remove']
            if self.assume_yes:
                cmd.append('-y')
            cmd.extend(packages)
            
            if self.dry_run:
                cmd.append('--dry-run')
                print("DRY RUN: Would execute:", ' '.join(cmd))
                return True, "Dry run completed"
            
            action = "Purging" if purge else "Removing"
            print(f"{action} packages: {', '.join(packages)}")
            result = self.sudo_manager.run_with_sudo(cmd, timeout=300)
            
            if result.returncode == 0:
                self.cache.update_cache()
                return True, f"Packages {action.lower()} successfully: {', '.join(packages)}"
            else:
                return False, f"Failed to {action.lower()} packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error {action.lower()} packages: {e}"
    
    def search(self, query: str) -> Tuple[bool, str]:
        """Search for packages"""
        try:
            # Use cache for quick search
            cached_results = self.cache.search_packages(query)
            
            if cached_results:
                output = []
                for pkg in cached_results[:20]:  # Limit results
                    status = "installed" if pkg.installed_version else "available"
                    version = pkg.installed_version or pkg.version
                    output.append(f"{pkg.name}/{status} {version} - {pkg.description}")
                
                return True, '\n'.join(output)
            
            # Fall back to apt search
            result = subprocess.run(
                ['apt', 'search', query],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Search failed: {result.stderr}"
                
        except Exception as e:
            return False, f"Error searching packages: {e}"
    
    def show(self, package: str) -> Tuple[bool, str]:
        """Show package information"""
        try:
            # Try cache first
            cached_info = self.cache.get_package_info(package)
            if cached_info:
                output = f"""Package: {cached_info.name}
Version: {cached_info.version}
Installed-Version: {cached_info.installed_version or 'Not installed'}
Description: {cached_info.description}
Status: {cached_info.status}"""
                
                if cached_info.depends:
                    output += f"\nDepends: {', '.join(cached_info.depends)}"
                
                return True, output
            
            # Fall back to apt show
            result = subprocess.run(
                ['apt', 'show', package],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Package '{package}' not found"
                
        except Exception as e:
            return False, f"Error showing package info: {e}"
    
    def list_packages(self, installed_only: bool = False, upgradable_only: bool = False) -> Tuple[bool, str]:
        """List packages"""
        try:
            cmd = ['apt', 'list']
            
            if installed_only:
                cmd.append('--installed')
            elif upgradable_only:
                cmd.append('--upgradable')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Failed to list packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error listing packages: {e}"
    
    def autoremove(self) -> Tuple[bool, str]:
        """Remove automatically installed unused packages"""
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt autoremove"
            
            cmd = ['apt', 'autoremove']
            if self.assume_yes:
                cmd.append('-y')
            
            if self.dry_run:
                cmd.append('--dry-run')
                print("DRY RUN: Would execute:", ' '.join(cmd))
                return True, "Dry run completed"
            
            print("Removing unused packages...")
            result = self.sudo_manager.run_with_sudo(cmd, timeout=300)
            
            if result.returncode == 0:
                return True, "Unused packages removed successfully"
            else:
                return False, f"Failed to remove unused packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error removing unused packages: {e}"
    
    def clean(self, autoclean: bool = False) -> Tuple[bool, str]:
        """Clean package cache"""
        try:
            if not self.sudo_manager.can_sudo():
                return False, "Error: sudo privileges required for apt clean"
            
            cmd = ['apt', 'autoclean' if autoclean else 'clean']
            
            result = self.sudo_manager.run_with_sudo(cmd, timeout=60)
            
            if result.returncode == 0:
                action = "autocleaned" if autoclean else "cleaned"
                return True, f"Package cache {action} successfully"
            else:
                return False, f"Failed to clean package cache: {result.stderr}"
                
        except Exception as e:
            return False, f"Error cleaning package cache: {e}"

def register_apt_commands(shell):
    """Register APT commands with the shell"""
    
    apt_interface = AptInterface()
    
    def apt_command(args):
        """Main apt command"""
        if not args:
            return """Usage: apt [options] command [packages...]

Commands:
  update              Update package lists
  upgrade             Upgrade all packages
  install <packages>  Install packages
  remove <packages>   Remove packages
  purge <packages>    Remove packages and configuration files
  search <query>      Search for packages
  show <package>      Show package information
  list                List packages
  autoremove          Remove unused packages
  autoclean           Clean package cache
  clean               Clean all cached packages

Options:
  -y, --yes          Assume yes to all prompts
  -s, --dry-run      Simulate operation
  -v, --verbose      Verbose output
  -h, --help         Show this help

Examples:
  apt update
  apt install vim git
  apt search python
  apt show firefox
  apt remove --purge old-package
"""
        
        # Parse options
        assume_yes = False
        dry_run = False
        verbose = False
        purge = False
        
        filtered_args = []
        for arg in args:
            if arg in ['-y', '--yes']:
                assume_yes = True
            elif arg in ['-s', '--dry-run']:
                dry_run = True
            elif arg in ['-v', '--verbose']:
                verbose = True
            elif arg == '--purge':
                purge = True
            elif arg in ['-h', '--help']:
                return apt_command([])
            else:
                filtered_args.append(arg)
        
        if not filtered_args:
            return apt_command([])
        
        # Configure APT interface
        apt_interface.assume_yes = assume_yes
        apt_interface.dry_run = dry_run
        apt_interface.verbose = verbose
        
        command = filtered_args[0]
        packages = filtered_args[1:] if len(filtered_args) > 1 else []
        
        # Execute command
        success = False
        output = ""
        
        try:
            if command == 'update':
                success, output = apt_interface.update()
            elif command == 'upgrade':
                success, output = apt_interface.upgrade(packages)
            elif command == 'install':
                if not packages:
                    output = "Error: No packages specified for installation"
                else:
                    success, output = apt_interface.install(packages)
            elif command in ['remove', 'purge']:
                if not packages:
                    output = "Error: No packages specified for removal"
                else:
                    success, output = apt_interface.remove(packages, command == 'purge' or purge)
            elif command == 'search':
                if not packages:
                    output = "Error: No search query specified"
                else:
                    success, output = apt_interface.search(' '.join(packages))
            elif command == 'show':
                if not packages:
                    output = "Error: No package specified"
                else:
                    success, output = apt_interface.show(packages[0])
            elif command == 'list':
                installed = '--installed' in args
                upgradable = '--upgradable' in args
                success, output = apt_interface.list_packages(installed, upgradable)
            elif command == 'autoremove':
                success, output = apt_interface.autoremove()
            elif command in ['clean', 'autoclean']:
                success, output = apt_interface.clean(command == 'autoclean')
            else:
                output = f"Error: Unknown command '{command}'"
            
            print(output)
            return success
            
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return False
        except Exception as e:
            print(f"apt: {e}", file=sys.stderr)
            return False
    
    def apt_get_command(args):
        """apt-get command (wrapper for apt)"""
        if not args:
            return """Usage: apt-get [options] command [packages...]

This is a compatibility wrapper for apt-get.
See 'apt --help' for full documentation.

Common commands:
  update              Update package lists
  upgrade             Upgrade packages
  install <packages>  Install packages
  remove <packages>   Remove packages
  autoremove          Remove unused packages
  clean               Clean package cache
"""
        
        # Map apt-get commands to apt commands
        command_map = {
            'dist-upgrade': 'upgrade',
            'build-dep': 'build-dep',  # Not supported in simplified version
        }
        
        # Convert apt-get args to apt args
        apt_args = []
        for arg in args:
            apt_args.append(command_map.get(arg, arg))
        
        return apt_command(apt_args)
    
    def sudo_command(args):
        """sudo command implementation"""
        if not args:
            return """Usage: sudo [options] command [args...]

Execute commands as another user (typically root).

Options:
  -u user    Execute command as specified user
  -i         Login shell
  -s         Shell
  -k         Invalidate timestamp
  -l         List allowed commands
  -v         Validate timestamp
  -h         Show help

Note: This is a simplified sudo implementation for KOS.
Only basic functionality is supported.
"""
        
        sudo_manager = SudoManager()
        
        if not sudo_manager.has_sudo:
            print("sudo: command not found or not available", file=sys.stderr)
            return False
        
        # Handle sudo options
        if args[0] == '-v':
            # Validate/refresh timestamp
            try:
                result = subprocess.run(['sudo', '-v'], timeout=30)
                return result.returncode == 0
            except Exception:
                return False
        elif args[0] == '-k':
            # Invalidate timestamp
            try:
                subprocess.run(['sudo', '-k'], timeout=5)
                return True
            except Exception:
                return False
        elif args[0] == '-l':
            # List allowed commands
            try:
                result = subprocess.run(
                    ['sudo', '-l'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                print(result.stdout)
                return result.returncode == 0
            except Exception:
                return False
        
        # Execute command with sudo
        try:
            result = sudo_manager.run_with_sudo(args)
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"sudo: {e}", file=sys.stderr)
            return False
    
    def dpkg_command(args):
        """dpkg command wrapper"""
        if not args:
            return """Usage: dpkg [options] action [packages...]

Package management with dpkg.

Actions:
  -l, --list         List packages
  -s, --status       Show package status
  -L, --listfiles    List files in package
  -S, --search       Search for files
  -i, --install      Install package file
  -r, --remove       Remove package

Options:
  --get-selections   Get package selections
  --set-selections   Set package selections
"""
        
        try:
            # Pass through to system dpkg
            result = subprocess.run(
                ['dpkg'] + args,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"dpkg: {e}", file=sys.stderr)
            return False
    
def register_commands(shell):
    """Register APT integration commands with the shell"""
    
    def apt_command(shell, args):
        """apt command wrapper"""
        if not args:
            return """Usage: apt [options] command [packages...]

Package management with apt.

Commands:
  update             Update package index
  upgrade            Upgrade packages
  install <pkg>      Install package
  remove <pkg>       Remove package
  search <query>     Search packages
  show <pkg>         Show package info
  list               List packages
  autoremove         Remove unused packages
"""
        
        try:
            # Pass through to system apt with sudo
            result = subprocess.run(
                ['sudo', 'apt'] + args.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"apt: {e}", file=sys.stderr)
            return False
    
    def apt_get_command(shell, args):
        """apt-get command wrapper"""
        if not args:
            return """Usage: apt-get [options] command [packages...]

Package management with apt-get.
"""
        
        try:
            result = subprocess.run(
                ['sudo', 'apt-get'] + args.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"apt-get: {e}", file=sys.stderr)
            return False
    
    def sudo_command(shell, args):
        """sudo command wrapper"""
        if not args:
            return """Usage: sudo [options] command [args...]

Execute commands with superuser privileges.
"""
        
        try:
            result = subprocess.run(
                ['sudo'] + args.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"sudo: {e}", file=sys.stderr)
            return False
    
    def dpkg_command(shell, args):
        """dpkg command wrapper"""
        if not args:
            return """Usage: dpkg [options] action [packages...]

Package management with dpkg.
"""
        
        try:
            result = subprocess.run(
                ['dpkg'] + args.split(),
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"dpkg: {e}", file=sys.stderr)
            return False
    
    # Register commands with the shell
    shell.register_command('apt', apt_command, "Advanced Package Tool - package manager")
    shell.register_command('apt-get', apt_get_command, "APT package handling utility")
    shell.register_command('sudo', sudo_command, "Execute commands as another user")
    shell.register_command('dpkg', dpkg_command, "Package manager for Debian")

__all__ = ['register_commands']
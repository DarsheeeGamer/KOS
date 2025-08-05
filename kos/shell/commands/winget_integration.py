"""
Windows Package Manager (winget) Integration for KOS
===================================================

Provides winget integration for Windows systems:
- Package installation and management
- Source management
- Search and show functionality
- Cross-platform compatibility layer
- Unified package management interface
"""

import os
import sys
import subprocess
import json
import time
import re
import threading
import platform
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger('KOS.shell.winget_integration')

class WingetOperation(Enum):
    """Winget operation types"""
    INSTALL = "install"
    UNINSTALL = "uninstall"
    UPGRADE = "upgrade"
    SEARCH = "search"
    SHOW = "show"
    LIST = "list"
    SOURCE = "source"
    HASH = "hash"
    VALIDATE = "validate"
    SETTINGS = "settings"
    FEATURES = "features"
    EXPORT = "export"
    IMPORT = "import"

@dataclass
class WingetPackageInfo:
    """Windows package information"""
    name: str
    id: str = ""
    version: str = ""
    available_version: str = ""
    publisher: str = ""
    description: str = ""
    homepage: str = ""
    license: str = ""
    license_url: str = ""
    copyright: str = ""
    short_description: str = ""
    tags: List[str] = None
    source: str = ""
    installer_type: str = ""
    silent_switch: str = ""
    interactive_switch: str = ""
    log_switch: str = ""
    install_location: str = ""
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

class WingetManager:
    """Windows Package Manager interface"""
    
    def __init__(self):
        self.winget_available = self._check_winget_available()
        self.sources = {}
        self.package_cache = {}
        self.last_cache_update = 0
        self.cache_validity = 3600  # 1 hour
        
        if self.winget_available:
            self._load_sources()
    
    def _check_winget_available(self) -> bool:
        """Check if winget is available"""
        if platform.system() != 'Windows':
            return False
        
        try:
            result = subprocess.run(
                ['winget', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _load_sources(self):
        """Load configured sources"""
        try:
            result = subprocess.run(
                ['winget', 'source', 'list'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self._parse_source_list(result.stdout)
                
        except Exception as e:
            logger.error(f"Failed to load winget sources: {e}")
    
    def _parse_source_list(self, output: str):
        """Parse winget source list output"""
        lines = output.split('\n')
        in_sources = False
        
        for line in lines:
            line = line.strip()
            if 'Name' in line and 'Argument' in line:
                in_sources = True
                continue
            
            if in_sources and line and not line.startswith('-'):
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    url = parts[1] if len(parts) > 1 else ""
                    self.sources[name] = {
                        'name': name,
                        'url': url,
                        'enabled': True
                    }
    
    def install(self, package_id: str, version: str = None, source: str = None, 
                silent: bool = False, interactive: bool = False, 
                accept_license: bool = False, accept_source_agreements: bool = False) -> Tuple[bool, str]:
        """Install a package"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'install', package_id]
            
            if version:
                cmd.extend(['--version', version])
            
            if source:
                cmd.extend(['--source', source])
            
            if silent:
                cmd.append('--silent')
            
            if interactive:
                cmd.append('--interactive')
            
            if accept_license:
                cmd.append('--accept-package-agreements')
            
            if accept_source_agreements:
                cmd.append('--accept-source-agreements')
            
            print(f"Installing {package_id}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                return True, f"Successfully installed {package_id}"
            else:
                return False, f"Failed to install {package_id}: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, f"Installation of {package_id} timed out"
        except Exception as e:
            return False, f"Error installing {package_id}: {e}"
    
    def uninstall(self, package_id: str, version: str = None, source: str = None, 
                  silent: bool = False, interactive: bool = False) -> Tuple[bool, str]:
        """Uninstall a package"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'uninstall', package_id]
            
            if version:
                cmd.extend(['--version', version])
            
            if source:
                cmd.extend(['--source', source])
            
            if silent:
                cmd.append('--silent')
            
            if interactive:
                cmd.append('--interactive')
            
            print(f"Uninstalling {package_id}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                return True, f"Successfully uninstalled {package_id}"
            else:
                return False, f"Failed to uninstall {package_id}: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, f"Uninstallation of {package_id} timed out"
        except Exception as e:
            return False, f"Error uninstalling {package_id}: {e}"
    
    def upgrade(self, package_id: str = None, all_packages: bool = False, 
                include_unknown: bool = False, accept_license: bool = False,
                accept_source_agreements: bool = False) -> Tuple[bool, str]:
        """Upgrade packages"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'upgrade']
            
            if package_id:
                cmd.append(package_id)
            elif all_packages:
                cmd.append('--all')
            
            if include_unknown:
                cmd.append('--include-unknown')
            
            if accept_license:
                cmd.append('--accept-package-agreements')
            
            if accept_source_agreements:
                cmd.append('--accept-source-agreements')
            
            action = f"Upgrading {package_id}" if package_id else "Upgrading all packages"
            print(f"{action}...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                return True, f"Successfully completed upgrade"
            else:
                return False, f"Failed to upgrade: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Upgrade operation timed out"
        except Exception as e:
            return False, f"Error during upgrade: {e}"
    
    def search(self, query: str, source: str = None, count: int = None, 
               exact: bool = False, id_only: bool = False, name_only: bool = False) -> Tuple[bool, str]:
        """Search for packages"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'search', query]
            
            if source:
                cmd.extend(['--source', source])
            
            if count:
                cmd.extend(['--count', str(count)])
            
            if exact:
                cmd.append('--exact')
            
            if id_only:
                cmd.append('--id')
            
            if name_only:
                cmd.append('--name')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Search failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Search operation timed out"
        except Exception as e:
            return False, f"Error during search: {e}"
    
    def show(self, package_id: str, source: str = None, version: str = None) -> Tuple[bool, str]:
        """Show package information"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'show', package_id]
            
            if source:
                cmd.extend(['--source', source])
            
            if version:
                cmd.extend(['--version', version])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Package '{package_id}' not found"
                
        except subprocess.TimeoutExpired:
            return False, "Show operation timed out"
        except Exception as e:
            return False, f"Error showing package info: {e}"
    
    def list_packages(self, upgrade_available: bool = False, source: str = None, 
                     name: str = None, id_filter: str = None) -> Tuple[bool, str]:
        """List installed packages"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'list']
            
            if upgrade_available:
                cmd.append('--upgrade-available')
            
            if source:
                cmd.extend(['--source', source])
            
            if name:
                cmd.extend(['--name', name])
            
            if id_filter:
                cmd.extend(['--id', id_filter])
            
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
                
        except subprocess.TimeoutExpired:
            return False, "List operation timed out"
        except Exception as e:
            return False, f"Error listing packages: {e}"
    
    def add_source(self, name: str, url: str, trust_level: str = None) -> Tuple[bool, str]:
        """Add a package source"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'source', 'add', '--name', name, '--arg', url]
            
            if trust_level:
                cmd.extend(['--trust-level', trust_level])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self._load_sources()  # Reload sources
                return True, f"Successfully added source '{name}'"
            else:
                return False, f"Failed to add source: {result.stderr}"
                
        except Exception as e:
            return False, f"Error adding source: {e}"
    
    def remove_source(self, name: str) -> Tuple[bool, str]:
        """Remove a package source"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'source', 'remove', '--name', name]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self._load_sources()  # Reload sources
                return True, f"Successfully removed source '{name}'"
            else:
                return False, f"Failed to remove source: {result.stderr}"
                
        except Exception as e:
            return False, f"Error removing source: {e}"
    
    def update_sources(self) -> Tuple[bool, str]:
        """Update package sources"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'source', 'update']
            
            print("Updating package sources...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                return True, "Successfully updated package sources"
            else:
                return False, f"Failed to update sources: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Source update timed out"
        except Exception as e:
            return False, f"Error updating sources: {e}"
    
    def export_packages(self, output_file: str, source: str = None, 
                       include_versions: bool = False) -> Tuple[bool, str]:
        """Export installed packages to file"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'export', '--output', output_file]
            
            if source:
                cmd.extend(['--source', source])
            
            if include_versions:
                cmd.append('--include-versions')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                return True, f"Successfully exported packages to {output_file}"
            else:
                return False, f"Failed to export packages: {result.stderr}"
                
        except Exception as e:
            return False, f"Error exporting packages: {e}"
    
    def import_packages(self, input_file: str, ignore_unavailable: bool = False,
                       ignore_versions: bool = False, accept_license: bool = False,
                       accept_source_agreements: bool = False) -> Tuple[bool, str]:
        """Import packages from file"""
        if not self.winget_available:
            return False, "winget is not available on this system"
        
        try:
            cmd = ['winget', 'import', '--import-file', input_file]
            
            if ignore_unavailable:
                cmd.append('--ignore-unavailable')
            
            if ignore_versions:
                cmd.append('--ignore-versions')
            
            if accept_license:
                cmd.append('--accept-package-agreements')
            
            if accept_source_agreements:
                cmd.append('--accept-source-agreements')
            
            print(f"Importing packages from {input_file}...")
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode == 0:
                return True, f"Successfully imported packages from {input_file}"
            else:
                return False, f"Failed to import packages: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Import operation timed out"
        except Exception as e:
            return False, f"Error importing packages: {e}"

def register_winget_commands(shell):
    """Register winget commands with the shell"""
    
    winget_manager = WingetManager()
    
    def winget_command(args):
        """Main winget command"""
        if not args:
            return """Usage: winget [command] [options]

Windows Package Manager

Commands:
  install    Install packages
  uninstall  Uninstall packages
  upgrade    Upgrade packages
  search     Search for packages
  show       Show package information
  list       List installed packages
  source     Manage package sources
  export     Export installed packages
  import     Import packages from file
  hash       Generate hash for installer
  validate   Validate manifest files
  settings   Modify winget settings
  features   Show available features

Examples:
  winget search firefox
  winget install Mozilla.Firefox
  winget upgrade --all
  winget list --upgrade-available
  winget source add myrepo https://example.com/repo

For detailed help on a command, use: winget [command] --help
"""
        
        if not winget_manager.winget_available:
            print("winget: Windows Package Manager is not available on this system", file=sys.stderr)
            return False
        
        command = args[0]
        command_args = args[1:] if len(args) > 1 else []
        
        # Parse common options
        silent = '--silent' in command_args or '-s' in command_args
        interactive = '--interactive' in command_args or '-i' in command_args
        accept_license = '--accept-package-agreements' in command_args
        accept_source_agreements = '--accept-source-agreements' in command_args
        source = None
        version = None
        
        # Extract source and version options
        i = 0
        filtered_args = []
        while i < len(command_args):
            arg = command_args[i]
            if arg == '--source' and i + 1 < len(command_args):
                source = command_args[i + 1]
                i += 2
            elif arg == '--version' and i + 1 < len(command_args):
                version = command_args[i + 1]
                i += 2
            elif not arg.startswith('--'):
                filtered_args.append(arg)
                i += 1
            else:
                i += 1
        
        success = False
        output = ""
        
        try:
            if command == 'install':
                if not filtered_args:
                    output = "Error: No package specified for installation"
                else:
                    package_id = filtered_args[0]
                    success, output = winget_manager.install(
                        package_id, version, source, silent, interactive,
                        accept_license, accept_source_agreements
                    )
            
            elif command == 'uninstall':
                if not filtered_args:
                    output = "Error: No package specified for uninstallation"
                else:
                    package_id = filtered_args[0]
                    success, output = winget_manager.uninstall(
                        package_id, version, source, silent, interactive
                    )
            
            elif command == 'upgrade':
                if '--all' in command_args:
                    success, output = winget_manager.upgrade(
                        all_packages=True,
                        include_unknown='--include-unknown' in command_args,
                        accept_license=accept_license,
                        accept_source_agreements=accept_source_agreements
                    )
                elif filtered_args:
                    package_id = filtered_args[0]
                    success, output = winget_manager.upgrade(
                        package_id=package_id,
                        accept_license=accept_license,
                        accept_source_agreements=accept_source_agreements
                    )
                else:
                    # Show upgradable packages
                    success, output = winget_manager.list_packages(upgrade_available=True)
            
            elif command == 'search':
                if not filtered_args:
                    output = "Error: No search query specified"
                else:
                    query = ' '.join(filtered_args)
                    count = None
                    if '--count' in command_args:
                        count_idx = command_args.index('--count')
                        if count_idx + 1 < len(command_args):
                            count = int(command_args[count_idx + 1])
                    
                    success, output = winget_manager.search(
                        query, source, count,
                        exact='--exact' in command_args,
                        id_only='--id' in command_args,
                        name_only='--name' in command_args
                    )
            
            elif command == 'show':
                if not filtered_args:
                    output = "Error: No package specified"
                else:
                    package_id = filtered_args[0]
                    success, output = winget_manager.show(package_id, source, version)
            
            elif command == 'list':
                success, output = winget_manager.list_packages(
                    upgrade_available='--upgrade-available' in command_args,
                    source=source,
                    name=None,  # Could be enhanced to parse --name option
                    id_filter=None  # Could be enhanced to parse --id option
                )
            
            elif command == 'source':
                if not filtered_args:
                    # List sources
                    sources_list = []
                    for name, info in winget_manager.sources.items():
                        sources_list.append(f"{name:<20} {info['url']}")
                    
                    if sources_list:
                        output = "Name                 Argument\n" + "-" * 40 + "\n" + '\n'.join(sources_list)
                        success = True
                    else:
                        output = "No sources configured"
                        success = True
                
                else:
                    subcommand = filtered_args[0]
                    if subcommand == 'add':
                        if len(filtered_args) >= 3:
                            name = filtered_args[1]
                            url = filtered_args[2]
                            trust_level = None
                            if '--trust-level' in command_args:
                                trust_idx = command_args.index('--trust-level')
                                if trust_idx + 1 < len(command_args):
                                    trust_level = command_args[trust_idx + 1]
                            
                            success, output = winget_manager.add_source(name, url, trust_level)
                        else:
                            output = "Error: source add requires name and URL"
                    
                    elif subcommand == 'remove':
                        if len(filtered_args) >= 2:
                            name = filtered_args[1]
                            success, output = winget_manager.remove_source(name)
                        else:
                            output = "Error: source remove requires name"
                    
                    elif subcommand == 'update':
                        success, output = winget_manager.update_sources()
                    
                    else:
                        output = f"Error: Unknown source subcommand '{subcommand}'"
            
            elif command == 'export':
                if '--output' in command_args:
                    output_idx = command_args.index('--output')
                    if output_idx + 1 < len(command_args):
                        output_file = command_args[output_idx + 1]
                        success, output = winget_manager.export_packages(
                            output_file, source,
                            include_versions='--include-versions' in command_args
                        )
                    else:
                        output = "Error: --output requires a filename"
                else:
                    output = "Error: export requires --output option"
            
            elif command == 'import':
                if '--import-file' in command_args:
                    import_idx = command_args.index('--import-file')
                    if import_idx + 1 < len(command_args):
                        input_file = command_args[import_idx + 1]
                        success, output = winget_manager.import_packages(
                            input_file,
                            ignore_unavailable='--ignore-unavailable' in command_args,
                            ignore_versions='--ignore-versions' in command_args,
                            accept_license=accept_license,
                            accept_source_agreements=accept_source_agreements
                        )
                    else:
                        output = "Error: --import-file requires a filename"
                else:
                    output = "Error: import requires --import-file option"
            
            elif command in ['hash', 'validate', 'settings', 'features']:
                # Pass through to system winget for these commands
                try:
                    result = subprocess.run(
                        ['winget', command] + command_args,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    output = result.stdout + result.stderr
                    success = result.returncode == 0
                    
                except Exception as e:
                    output = f"Error executing winget {command}: {e}"
                    success = False
            
            else:
                output = f"Error: Unknown command '{command}'"
            
            print(output)
            return success
            
        except KeyboardInterrupt:
            print("\nOperation cancelled by user")
            return False
        except Exception as e:
            print(f"winget: {e}", file=sys.stderr)
            return False
    
    def chocolatey_command(args):
        """Chocolatey package manager wrapper (Windows)"""
        if not args:
            return """Usage: choco [command] [options]

Chocolatey Package Manager wrapper for Windows.

This is a compatibility wrapper that maps chocolatey commands to winget where possible.

Commands:
  install     Install packages
  uninstall   Uninstall packages
  upgrade     Upgrade packages
  search      Search for packages
  list        List installed packages

Note: For full chocolatey functionality, install chocolatey separately.
"""
        
        if platform.system() != 'Windows':
            print("choco: Chocolatey is only available on Windows", file=sys.stderr)
            return False
        
        # Map chocolatey commands to winget
        command = args[0]
        
        if command == 'install':
            return winget_command(['install'] + args[1:])
        elif command == 'uninstall':
            return winget_command(['uninstall'] + args[1:])
        elif command == 'upgrade':
            if 'all' in args:
                return winget_command(['upgrade', '--all'])
            else:
                return winget_command(['upgrade'] + args[1:])
        elif command == 'search':
            return winget_command(['search'] + args[1:])
        elif command == 'list':
            return winget_command(['list'] + args[1:])
        else:
            # Try to use actual chocolatey if available
            try:
                result = subprocess.run(['choco'] + args, timeout=60)
                return result.returncode == 0
            except Exception:
                print(f"choco: command '{command}' not supported in winget wrapper", file=sys.stderr)
                return False
    
    def scoop_command(args):
        """Scoop package manager wrapper (Windows)"""
        if not args:
            return """Usage: scoop [command] [options]

Scoop Package Manager wrapper for Windows.

This is a compatibility wrapper that maps scoop commands to winget where possible.

Commands:
  install     Install packages
  uninstall   Uninstall packages
  update      Update packages
  search      Search for packages
  list        List installed packages

Note: For full scoop functionality, install scoop separately.
"""
        
        if platform.system() != 'Windows':
            print("scoop: Scoop is only available on Windows", file=sys.stderr)
            return False
        
        # Map scoop commands to winget
        command = args[0]
        
        if command == 'install':
            return winget_command(['install'] + args[1:])
        elif command == 'uninstall':
            return winget_command(['uninstall'] + args[1:])
        elif command == 'update':
            if '*' in args or 'all' in args:
                return winget_command(['upgrade', '--all'])
            else:
                return winget_command(['upgrade'] + args[1:])
        elif command == 'search':
            return winget_command(['search'] + args[1:])
        elif command == 'list':
            return winget_command(['list'] + args[1:])
        else:
            # Try to use actual scoop if available
            try:
                result = subprocess.run(['scoop'] + args, timeout=60)
                return result.returncode == 0
            except Exception:
                print(f"scoop: command '{command}' not supported in winget wrapper", file=sys.stderr)
                return False
    
    # Register commands
    shell.register_command('winget', winget_command)
    
    # Register compatibility wrappers for Windows
    if platform.system() == 'Windows':
        shell.register_command('choco', chocolatey_command)
        shell.register_command('chocolatey', chocolatey_command)
        shell.register_command('scoop', scoop_command)

__all__ = ['WingetManager', 'register_winget_commands']
"""
KOS Package Registry
===================

Real package registry system with default packages and repository management.
Provides a curated set of useful packages for KOS.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger('KOS.package.registry')

class PackageRegistry:
    """Registry of available packages with metadata"""
    
    def __init__(self):
        self.registry_file = os.path.expanduser("~/.kos/kpm/registry.json")
        self.packages: Dict[str, Dict[str, Any]] = {}
        self._load_registry()
        self._sync_with_repositories()
        self._ensure_default_packages()
    
    def _load_registry(self):
        """Load package registry from file"""
        try:
            if os.path.exists(self.registry_file):
                with open(self.registry_file, 'r') as f:
                    data = json.load(f)
                    self.packages = data.get('packages', {})
                logger.info(f"Loaded {len(self.packages)} packages from registry")
            else:
                os.makedirs(os.path.dirname(self.registry_file), exist_ok=True)
                self._save_registry()
        except Exception as e:
            logger.error(f"Error loading registry: {e}")
    
    def _save_registry(self):
        """Save package registry to file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'packages': self.packages
            }
            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving registry: {e}")
    
    def _sync_with_repositories(self):
        """Sync registry with repository manager"""
        try:
            from ..repo_config import get_repository_manager
            rm = get_repository_manager()
            
            # Update all repositories first
            rm.update_all_repositories()
            
            # Clear existing packages from repositories
            # Keep only manually added packages
            packages_to_keep = {k: v for k, v in self.packages.items() 
                              if v.get('repository', '') == 'manual'}
            self.packages = packages_to_keep
            
            # Add packages from all enabled repositories
            for repo_name, repo in rm.list_repositories().items():
                if repo.enabled:
                    packages = rm.get_repository_packages(repo_name)
                    for pkg in packages:
                        # Convert repository package to registry format
                        self.packages[pkg.name] = {
                            "name": pkg.name,
                            "version": pkg.version,
                            "description": pkg.description,
                            "author": pkg.author,
                            "main": pkg.entry_point,
                            "dependencies": pkg.dependencies,
                            "cli_aliases": [],
                            "cli_function": "main",
                            "tags": pkg.tags,
                            "homepage": pkg.homepage,
                            "license": pkg.license,
                            "url": f"{repo.url}/files/{pkg.name}/{pkg.name}.tar.gz",
                            "checksum": pkg.checksum,
                            "size": pkg.size,
                            "repository": repo_name,
                            "install_type": "download"
                        }
            
            logger.info(f"Synced {len(self.packages)} packages from repositories")
            self._save_registry()
            
        except Exception as e:
            logger.warning(f"Could not sync with repositories: {e}")
    
    def _ensure_default_packages(self):
        """Ensure default packages are available in registry"""
        # Don't add default packages if we have packages from repositories
        if any(p.get('repository') != 'manual' for p in self.packages.values()):
            return
            
        default_packages = self._get_default_packages()
        
        for pkg_name, pkg_info in default_packages.items():
            if pkg_name not in self.packages:
                self.packages[pkg_name] = pkg_info
        
        self._save_registry()
    
    def _get_default_packages(self) -> Dict[str, Dict[str, Any]]:
        """Get default KOS packages"""
        return {
            "calc": {
                "name": "calc",
                "version": "1.0.0",
                "description": "Advanced calculator with mathematical functions",
                "author": "KOS Team",
                "main": "calc.py",
                "dependencies": [],
                "cli_aliases": ["calculator", "math"],
                "cli_function": "cli_app",
                "tags": ["math", "calculator", "utility"],
                "homepage": "https://github.com/kos-packages/calc",
                "license": "MIT",
                "url": "https://github.com/kos-packages/calc/archive/v1.0.0.zip",
                "checksum": "mock_checksum_calc",
                "size": 45000,
                "repository": "official",
                "install_type": "simulated"
            },
            "text-editor": {
                "name": "text-editor",
                "version": "2.1.0",
                "description": "Advanced text editor with syntax highlighting",
                "author": "KOS Team",
                "main": "editor.py",
                "dependencies": [],
                "cli_aliases": ["edit", "editor"],
                "cli_function": "cli_app",
                "tags": ["editor", "text", "development"],
                "homepage": "https://github.com/kos-packages/text-editor",
                "license": "MIT",
                "url": "https://github.com/kos-packages/text-editor/archive/v2.1.0.zip",
                "checksum": "mock_checksum_editor",
                "size": 120000,
                "repository": "official",
                "install_type": "simulated"
            },
            "file-manager": {
                "name": "file-manager",
                "version": "1.5.0",
                "description": "Visual file manager with tree view and operations",
                "author": "KOS Team",
                "main": "filemgr.py",
                "dependencies": [],
                "cli_aliases": ["fm", "files"],
                "cli_function": "cli_app",
                "tags": ["files", "manager", "utility"],
                "homepage": "https://github.com/kos-packages/file-manager",
                "license": "MIT",
                "url": "https://github.com/kos-packages/file-manager/archive/v1.5.0.zip",
                "checksum": "mock_checksum_fm",
                "size": 89000,
                "repository": "official",
                "install_type": "simulated"
            },
            "network-tools": {
                "name": "network-tools",
                "version": "1.2.0",
                "description": "Network diagnostic and monitoring tools",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/network-tools/archive/v1.2.0.zip",
                "checksum": "mock_checksum_net",
                "dependencies": [],
                "entry_point": "nettools.py",
                "cli_aliases": ["nettools", "network", "ping"],
                "tags": ["network", "tools", "diagnostic"],
                "size": 67000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "system-monitor": {
                "name": "system-monitor",
                "version": "3.0.1",
                "description": "Real-time system monitoring and resource viewer",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/system-monitor/archive/v3.0.1.zip",
                "checksum": "mock_checksum_sysmon",
                "dependencies": [],
                "entry_point": "sysmon.py",
                "cli_aliases": ["sysmon", "monitor", "htop"],
                "tags": ["system", "monitor", "performance"],
                "size": 156000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "json-tool": {
                "name": "json-tool",
                "version": "1.0.0",
                "description": "JSON parser, formatter, and validator",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/json-tool/archive/v1.0.0.zip",
                "checksum": "mock_checksum_json",
                "dependencies": [],
                "entry_point": "jsontool.py",
                "cli_aliases": ["json", "jq"],
                "tags": ["json", "parser", "utility"],
                "size": 34000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "image-viewer": {
                "name": "image-viewer",
                "version": "1.3.0",
                "description": "Terminal-based image viewer with ASCII art conversion",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/image-viewer/archive/v1.3.0.zip",
                "checksum": "mock_checksum_img",
                "dependencies": [],
                "entry_point": "imgview.py",
                "cli_aliases": ["img", "view", "imgview"],
                "tags": ["image", "viewer", "graphics"],
                "size": 78000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "crypto-tools": {
                "name": "crypto-tools",
                "version": "2.0.0",
                "description": "Cryptographic utilities and hash functions",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/crypto-tools/archive/v2.0.0.zip",
                "checksum": "mock_checksum_crypto",
                "dependencies": [],
                "entry_point": "crypto.py",
                "cli_aliases": ["crypto", "hash", "encrypt"],
                "tags": ["crypto", "security", "hash"],
                "size": 92000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "weather": {
                "name": "weather",
                "version": "1.1.0",
                "description": "Command-line weather information tool",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/weather/archive/v1.1.0.zip",
                "checksum": "mock_checksum_weather",
                "dependencies": [],
                "entry_point": "weather.py",
                "cli_aliases": ["wttr"],
                "tags": ["weather", "api", "utility"],
                "size": 41000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            },
            "log-analyzer": {
                "name": "log-analyzer",
                "version": "1.4.0",
                "description": "Log file analyzer and parser with filtering",
                "author": "KOS Team",
                "url": "https://github.com/kos-packages/log-analyzer/archive/v1.4.0.zip",
                "checksum": "mock_checksum_log",
                "dependencies": [],
                "entry_point": "loganalyzer.py",
                "cli_aliases": ["logs", "analyze"],
                "tags": ["logs", "analyzer", "parsing"],
                "size": 63000,
                "license": "MIT",
                "repository": "official",
                "install_type": "simulated"
            }
        }
    
    def get_package(self, name: str) -> Optional[Dict[str, Any]]:
        """Get package information by name"""
        return self.packages.get(name)
    
    def refresh(self):
        """Force refresh registry from repositories"""
        self._sync_with_repositories()
        return len(self.packages)
    
    def search_packages(self, query: str) -> List[Dict[str, Any]]:
        """Search packages by name, description, or tags"""
        query = query.lower()
        results = []
        
        for pkg_info in self.packages.values():
            if (query in pkg_info['name'].lower() or
                query in pkg_info['description'].lower() or
                any(query in tag.lower() for tag in pkg_info.get('tags', []))):
                results.append(pkg_info)
        
        return results
    
    def list_packages(self) -> List[Dict[str, Any]]:
        """List all available packages"""
        return list(self.packages.values())
    
    def add_package(self, package_info: Dict[str, Any]):
        """Add a package to the registry"""
        self.packages[package_info['name']] = package_info
        self._save_registry()
    
    def remove_package(self, name: str) -> bool:
        """Remove a package from the registry"""
        if name in self.packages:
            del self.packages[name]
            self._save_registry()
            return True
        return False
    
    def update_package(self, name: str, package_info: Dict[str, Any]):
        """Update package information"""
        if name in self.packages:
            self.packages[name].update(package_info)
            self._save_registry()

class SimulatedPackageInstaller:
    """Simulated package installer for development/demo purposes"""
    
    def __init__(self):
        self.installed_packages_file = os.path.expanduser("~/.kos/kpm/installed.json")
        self.installed_packages: Dict[str, Dict[str, Any]] = {}
        self.commands_dir = os.path.expanduser("~/.kos/kpm/commands")
        
        os.makedirs(os.path.dirname(self.installed_packages_file), exist_ok=True)
        os.makedirs(self.commands_dir, exist_ok=True)
        
        self._load_installed()
    
    def _load_installed(self):
        """Load installed packages list"""
        try:
            if os.path.exists(self.installed_packages_file):
                with open(self.installed_packages_file, 'r') as f:
                    self.installed_packages = json.load(f)
        except Exception as e:
            logger.error(f"Error loading installed packages: {e}")
    
    def _save_installed(self):
        """Save installed packages list"""
        try:
            with open(self.installed_packages_file, 'w') as f:
                json.dump(self.installed_packages, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving installed packages: {e}")
    
    def install_package(self, package_info: Dict[str, Any]) -> bool:
        """Simulate package installation"""
        try:
            package_name = package_info['name']
            
            # Mark as installed
            self.installed_packages[package_name] = {
                **package_info,
                'install_date': datetime.now().isoformat(),
                'installed': True
            }
            
            # Create command scripts for CLI aliases
            self._create_command_scripts(package_info)
            
            self._save_installed()
            logger.info(f"Simulated installation of: {package_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error simulating package installation: {e}")
            return False
    
    def _create_command_scripts(self, package_info: Dict[str, Any]):
        """Create command scripts for the package"""
        try:
            # Create main command
            main_cmd = package_info['name']
            self._create_command_script(main_cmd, package_info)
            
            # Create alias commands
            for alias in package_info.get('cli_aliases', []):
                self._create_command_script(alias, package_info)
                
        except Exception as e:
            logger.warning(f"Failed to create command scripts: {e}")
    
    def _create_command_script(self, command_name: str, package_info: Dict[str, Any]):
        """Create a single command script"""
        script_path = os.path.join(self.commands_dir, f"{command_name}.py")
        
        script_content = f'''#!/usr/bin/env python3
"""
Simulated command for {package_info['name']}
{package_info['description']}
"""

import sys
import os

def main():
    print(f"🚀 {package_info['name']} v{package_info['version']}")
    print(f"📝 {package_info['description']}")
    print(f"👤 Author: {package_info['author']}")
    print()
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            print("Available options:")
            print("  --help, -h    Show this help message")
            print("  --version     Show version information")
            print("  --info        Show package information")
            return
        elif sys.argv[1] == '--version':
            print(f"{package_info['name']} version {package_info['version']}")
            return
        elif sys.argv[1] == '--info':
            print(f"Package: {package_info['name']}")
            print(f"Version: {package_info['version']}")
            print(f"Description: {package_info['description']}")
            print(f"Author: {package_info['author']}")
            print(f"License: {package_info.get('license', 'Unknown')}")
            print(f"Tags: {', '.join(package_info.get('tags', []))}")
            return
    
    print("This is a simulated command. In a real implementation,")
    print("this would run the actual {package_info['name']} application.")
    
    if package_info['name'] == 'calc':
        print("\\nTry: calc 2+2, calc sin(45), calc sqrt(16)")
        if len(sys.argv) > 1:
            expression = ' '.join(sys.argv[1:])
            try:
                # Simple calculator simulation
                import math
                result = eval(expression.replace('sin', 'math.sin').replace('cos', 'math.cos').replace('sqrt', 'math.sqrt'))
                print(f"Result: {result}")
            except:
                print(f"Cannot evaluate: {expression}")
    
    elif package_info['name'] == 'text-editor':
        print("\\nThis would open a text editor with the specified file.")
        if len(sys.argv) > 1:
            print(f"Would edit file: {sys.argv[1]}")
    
    elif package_info['name'] == 'weather':
        print("\\nCurrent weather: Sunny, 22°C (Simulated)")
        print("This would fetch real weather data from an API.")

if __name__ == '__main__':
    main()
'''
        
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        os.chmod(script_path, 0o755)
    
    def uninstall_package(self, package_name: str) -> bool:
        """Simulate package uninstallation"""
        try:
            if package_name in self.installed_packages:
                package_info = self.installed_packages[package_name]
                
                # Remove command scripts
                self._remove_command_scripts(package_info)
                
                # Remove from installed list
                del self.installed_packages[package_name]
                self._save_installed()
                
                logger.info(f"Simulated uninstallation of: {package_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error simulating package uninstallation: {e}")
            return False
    
    def _remove_command_scripts(self, package_info: Dict[str, Any]):
        """Remove command scripts for the package"""
        try:
            # Remove main command
            main_cmd_path = os.path.join(self.commands_dir, f"{package_info['name']}.py")
            if os.path.exists(main_cmd_path):
                os.remove(main_cmd_path)
            
            # Remove alias commands
            for alias in package_info.get('cli_aliases', []):
                alias_path = os.path.join(self.commands_dir, f"{alias}.py")
                if os.path.exists(alias_path):
                    os.remove(alias_path)
                    
        except Exception as e:
            logger.warning(f"Failed to remove command scripts: {e}")
    
    def is_installed(self, package_name: str) -> bool:
        """Check if a package is installed"""
        return package_name in self.installed_packages
    
    def list_installed(self) -> List[Dict[str, Any]]:
        """List installed packages"""
        return list(self.installed_packages.values())
    
    def get_installed_package(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get installed package information"""
        return self.installed_packages.get(package_name)

# Global instances
_registry = None
_installer = None

def get_registry() -> PackageRegistry:
    """Get global package registry instance"""
    global _registry
    if _registry is None:
        _registry = PackageRegistry()
    return _registry

def get_installer() -> SimulatedPackageInstaller:
    """Get global package installer instance"""
    global _installer
    if _installer is None:
        _installer = SimulatedPackageInstaller()
    return _installer

# Export main classes and functions
__all__ = ['PackageRegistry', 'SimulatedPackageInstaller', 'get_registry', 'get_installer']
"""
Basic PIP Manager for KOS Package Management

Provides core pip functionality for package installation and management.
"""

import os
import sys
import json
import subprocess
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger('KOS.package.pip_manager')

@dataclass
class PipPackage:
    """Represents a pip package"""
    name: str
    version: str
    installed_by: Optional[str] = None  # Which app installed this
    dependencies: List[str] = None
    location: Optional[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'version': self.version,
            'installed_by': self.installed_by,
            'dependencies': self.dependencies,
            'location': self.location
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PipPackage':
        """Create from dictionary"""
        return cls(**data)


class PipManager:
    """Basic pip package manager"""
    
    def __init__(self, venv_dir: str = None):
        """Initialize pip manager"""
        self.venv_dir = venv_dir or os.path.expanduser('~/.kos/venv')
        self.python_executable = sys.executable
        self.pip_executable = None
        self.installed_packages: Dict[str, PipPackage] = {}
        
        # Setup paths
        self._setup_paths()
        
    def _setup_paths(self):
        """Setup pip and python paths"""
        if self.venv_dir and os.path.exists(self.venv_dir):
            # Use venv python and pip
            if sys.platform == 'win32':
                self.python_executable = os.path.join(self.venv_dir, 'Scripts', 'python.exe')
                self.pip_executable = os.path.join(self.venv_dir, 'Scripts', 'pip.exe')
            else:
                self.python_executable = os.path.join(self.venv_dir, 'bin', 'python')
                self.pip_executable = os.path.join(self.venv_dir, 'bin', 'pip')
        else:
            # Use system pip
            self.pip_executable = 'pip3' if sys.platform != 'win32' else 'pip'
    
    def install(self, package_name: str, version: Optional[str] = None, 
                upgrade: bool = False, force: bool = False) -> Tuple[bool, str]:
        """Install a pip package"""
        try:
            cmd = [self.pip_executable or 'pip3', 'install']
            
            if upgrade:
                cmd.append('--upgrade')
            if force:
                cmd.append('--force-reinstall')
            
            # Add package specification
            if version:
                cmd.append(f"{package_name}=={version}")
            else:
                cmd.append(package_name)
            
            # Run pip install
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Track installed package
                self._update_package_info(package_name)
                return True, result.stdout
            else:
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Failed to install {package_name}: {e}")
            return False, str(e)
    
    def uninstall(self, package_name: str) -> Tuple[bool, str]:
        """Uninstall a pip package"""
        try:
            cmd = [self.pip_executable or 'pip3', 'uninstall', '-y', package_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Remove from tracked packages
                if package_name in self.installed_packages:
                    del self.installed_packages[package_name]
                return True, result.stdout
            else:
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Failed to uninstall {package_name}: {e}")
            return False, str(e)
    
    def list_installed(self) -> List[PipPackage]:
        """List all installed packages"""
        packages = []
        try:
            cmd = [self.pip_executable or 'pip3', 'list', '--format=json']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                installed = json.loads(result.stdout)
                for pkg in installed:
                    packages.append(PipPackage(
                        name=pkg['name'],
                        version=pkg['version']
                    ))
            
        except Exception as e:
            logger.error(f"Failed to list packages: {e}")
        
        return packages
    
    def show_package(self, package_name: str) -> Optional[Dict]:
        """Get detailed information about a package"""
        try:
            cmd = [self.pip_executable or 'pip3', 'show', package_name]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                info = {}
                for line in result.stdout.strip().split('\n'):
                    if ': ' in line:
                        key, value = line.split(': ', 1)
                        info[key.lower().replace('-', '_')] = value
                return info
            
        except Exception as e:
            logger.error(f"Failed to show package {package_name}: {e}")
        
        return None
    
    def search(self, query: str) -> List[Dict]:
        """Search for packages on PyPI"""
        results = []
        try:
            # Note: pip search is deprecated, using alternative approach
            # Could use PyPI API instead
            import urllib.request
            import urllib.parse
            
            url = f"https://pypi.org/pypi/{urllib.parse.quote(query)}/json"
            with urllib.request.urlopen(url) as response:
                data = json.loads(response.read())
                results.append({
                    'name': data['info']['name'],
                    'version': data['info']['version'],
                    'summary': data['info']['summary']
                })
                
        except Exception as e:
            logger.debug(f"Failed to search for {query}: {e}")
        
        return results
    
    def freeze(self) -> List[str]:
        """Get requirements in pip freeze format"""
        requirements = []
        try:
            cmd = [self.pip_executable or 'pip3', 'freeze']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                requirements = result.stdout.strip().split('\n')
                
        except Exception as e:
            logger.error(f"Failed to freeze requirements: {e}")
        
        return requirements
    
    def install_requirements(self, requirements_file: str) -> Tuple[bool, str]:
        """Install packages from requirements file"""
        try:
            if not os.path.exists(requirements_file):
                return False, f"Requirements file not found: {requirements_file}"
            
            cmd = [self.pip_executable or 'pip3', 'install', '-r', requirements_file]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Update package tracking
                self._refresh_packages()
                return True, result.stdout
            else:
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Failed to install requirements: {e}")
            return False, str(e)
    
    def _update_package_info(self, package_name: str):
        """Update information for a specific package"""
        info = self.show_package(package_name)
        if info:
            deps = info.get('requires', '').split(', ') if info.get('requires') else []
            self.installed_packages[package_name] = PipPackage(
                name=package_name,
                version=info.get('version', 'unknown'),
                dependencies=[d.strip() for d in deps if d.strip()],
                location=info.get('location')
            )
    
    def _refresh_packages(self):
        """Refresh the list of installed packages"""
        self.installed_packages.clear()
        for pkg in self.list_installed():
            self.installed_packages[pkg.name] = pkg
    
    def check_installed(self, package_name: str) -> bool:
        """Check if a package is installed"""
        if package_name in self.installed_packages:
            return True
        
        # Double-check with pip
        info = self.show_package(package_name)
        return info is not None
    
    def upgrade_all(self) -> Tuple[bool, str]:
        """Upgrade all installed packages"""
        try:
            # Get list of outdated packages
            cmd = [self.pip_executable or 'pip3', 'list', '--outdated', '--format=json']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                return False, "Failed to get outdated packages"
            
            outdated = json.loads(result.stdout)
            
            if not outdated:
                return True, "All packages are up to date"
            
            # Upgrade each package
            upgraded = []
            failed = []
            
            for pkg in outdated:
                success, _ = self.install(pkg['name'], upgrade=True)
                if success:
                    upgraded.append(pkg['name'])
                else:
                    failed.append(pkg['name'])
            
            message = f"Upgraded: {', '.join(upgraded)}" if upgraded else ""
            if failed:
                message += f"\nFailed: {', '.join(failed)}"
            
            return len(failed) == 0, message
            
        except Exception as e:
            logger.error(f"Failed to upgrade packages: {e}")
            return False, str(e)
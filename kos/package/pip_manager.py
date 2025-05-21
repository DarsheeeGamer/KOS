"""
PIP dependency manager for KOS applications
"""
import os
import sys
import subprocess
import json
import logging
import importlib
import importlib.util
from typing import Dict, List, Optional, Union, Tuple
from .manager import Package, PackageDependency

logger = logging.getLogger('KOS.package.pip')

class PipPackage:
    """Represents a pip package with metadata"""
    def __init__(self, name: str, version: str = None, required_by: str = None):
        self.name = name
        self.version = version
        self.required_by = required_by or []
        if required_by and isinstance(required_by, str):
            self.required_by = [required_by]
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'version': self.version,
            'required_by': self.required_by
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'PipPackage':
        pkg = PipPackage(data['name'], data.get('version'))
        pkg.required_by = data.get('required_by', [])
        return pkg

    def __str__(self):
        return f"{self.name}" + (f"=={self.version}" if self.version else "")

class PipManager:
    """Manages Python package dependencies using pip"""
    def __init__(self, venv_dir: str = None):
        """
        Initialize the PIP manager
        
        Args:
            venv_dir: Optional path to a virtual environment directory
        """
        self.venv_dir = venv_dir
        self.pip_registry_file = "kos_pip_packages.json"
        self.installed_packages = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load the pip package registry"""
        try:
            if os.path.exists(self.pip_registry_file):
                with open(self.pip_registry_file, 'r') as f:
                    data = json.load(f)
                    for name, pkg_data in data.items():
                        self.installed_packages[name] = PipPackage.from_dict(pkg_data)
            logger.debug(f"Loaded {len(self.installed_packages)} pip packages from registry")
        except Exception as e:
            logger.error(f"Error loading pip registry: {e}")
    
    def _save_registry(self):
        """Save the pip package registry"""
        try:
            registry_data = {name: pkg.to_dict() for name, pkg in self.installed_packages.items()}
            with open(self.pip_registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)
            logger.debug(f"Saved {len(self.installed_packages)} pip packages to registry")
        except Exception as e:
            logger.error(f"Error saving pip registry: {e}")
    
    def _get_pip_command(self) -> List[str]:
        """Get the appropriate pip command based on venv configuration"""
        if self.venv_dir and os.path.exists(os.path.join(self.venv_dir, 'bin', 'pip')):
            return [os.path.join(self.venv_dir, 'bin', 'pip')]
        elif self.venv_dir and os.path.exists(os.path.join(self.venv_dir, 'Scripts', 'pip.exe')):
            return [os.path.join(self.venv_dir, 'Scripts', 'pip.exe')]
        else:
            return [sys.executable, '-m', 'pip']
    
    def install_requirements(self, requirements_file: str) -> Tuple[bool, str]:
        """
        Install packages from a requirements.txt file
        
        Args:
            requirements_file: Path to the requirements.txt file
            
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(requirements_file):
            return False, f"Requirements file not found: {requirements_file}"
        
        try:
            # Parse requirements file to track dependencies
            app_name = os.path.basename(os.path.dirname(requirements_file))
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Handle basic requirement specs (ignoring complex constraints for now)
                    if '>=' in line:
                        name = line.split('>=')[0].strip()
                        version = None  # We'll get the actual version after install
                    elif '==' in line:
                        name = line.split('==')[0].strip()
                        version = line.split('==')[1].strip()
                    else:
                        name = line.strip()
                        version = None
                    
                    # Track the package as required by this app
                    if name in self.installed_packages:
                        if app_name not in self.installed_packages[name].required_by:
                            self.installed_packages[name].required_by.append(app_name)
                    else:
                        pkg = PipPackage(name, version, app_name)
                        self.installed_packages[name] = pkg
            
            # Run pip install
            cmd = self._get_pip_command() + ['install', '-r', requirements_file]
            logger.info(f"Installing requirements: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                # Update installed versions
                self._update_installed_versions()
                self._save_registry()
                return True, "Requirements installed successfully"
            else:
                logger.error(f"Pip install failed: {result.stderr}")
                return False, f"Pip install failed: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return False, f"Error installing requirements: {str(e)}"
    
    def install_package(self, package_spec: str, app_name: str = None) -> Tuple[bool, str]:
        """
        Install a single package
        
        Args:
            package_spec: Package specification (e.g., "requests" or "requests==2.28.1")
            app_name: Name of the app requiring this package
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Parse package spec
            if '>=' in package_spec:
                name = package_spec.split('>=')[0].strip()
                version = None
            elif '==' in package_spec:
                name = package_spec.split('==')[0].strip()
                version = package_spec.split('==')[1].strip()
            else:
                name = package_spec.strip()
                version = None
            
            # Track the package
            if name in self.installed_packages:
                if app_name and app_name not in self.installed_packages[name].required_by:
                    self.installed_packages[name].required_by.append(app_name)
            else:
                pkg = PipPackage(name, version)
                if app_name:
                    pkg.required_by = [app_name]
                self.installed_packages[name] = pkg
            
            # Run pip install
            cmd = self._get_pip_command() + ['install', package_spec]
            logger.info(f"Installing package: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                # Update the installed version
                self._update_package_version(name)
                self._save_registry()
                return True, f"Package {name} installed successfully"
            else:
                logger.error(f"Pip install failed: {result.stderr}")
                return False, f"Pip install failed: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error installing package: {e}")
            return False, f"Error installing package: {str(e)}"
    
    def uninstall_package(self, package_name: str, app_name: str = None) -> Tuple[bool, str]:
        """
        Uninstall a package if it's no longer required
        
        Args:
            package_name: Name of the package to uninstall
            app_name: Name of the app that no longer requires this package
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if package_name not in self.installed_packages:
                return False, f"Package {package_name} is not installed"
            
            # Remove the app from required_by list
            if app_name and app_name in self.installed_packages[package_name].required_by:
                self.installed_packages[package_name].required_by.remove(app_name)
            
            # If package is still required by other apps, don't uninstall
            if self.installed_packages[package_name].required_by:
                other_apps = ", ".join(self.installed_packages[package_name].required_by)
                return True, f"Package {package_name} is still required by: {other_apps}"
            
            # Run pip uninstall
            cmd = self._get_pip_command() + ['uninstall', '-y', package_name]
            logger.info(f"Uninstalling package: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                # Remove from registry
                del self.installed_packages[package_name]
                self._save_registry()
                return True, f"Package {package_name} uninstalled successfully"
            else:
                logger.error(f"Pip uninstall failed: {result.stderr}")
                return False, f"Pip uninstall failed: {result.stderr}"
                
        except Exception as e:
            logger.error(f"Error uninstalling package: {e}")
            return False, f"Error uninstalling package: {str(e)}"
    
    def list_packages(self) -> List[PipPackage]:
        """List all installed pip packages"""
        return list(self.installed_packages.values())
    
    def _update_installed_versions(self):
        """Update the versions of all installed packages"""
        try:
            cmd = self._get_pip_command() + ['list', '--format=json']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                for pkg in packages:
                    name = pkg['name'].lower()
                    if name in self.installed_packages:
                        self.installed_packages[name].version = pkg['version']
        except Exception as e:
            logger.error(f"Error updating package versions: {e}")
    
    def _update_package_version(self, package_name: str):
        """Update the version of a specific installed package"""
        try:
            cmd = self._get_pip_command() + ['show', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith('Version:'):
                        version = line.split(':', 1)[1].strip()
                        if package_name.lower() in self.installed_packages:
                            self.installed_packages[package_name.lower()].version = version
                        break
        except Exception as e:
            logger.error(f"Error updating package version: {e}")
    
    def check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed"""
        try:
            # Try importing the package
            spec = importlib.util.find_spec(package_name)
            return spec is not None
        except (ImportError, ModuleNotFoundError):
            return False
    
    def get_requirements_from_package(self, package: Package) -> List[str]:
        """
        Extract pip requirements from a KOS Package
        
        Args:
            package: The KOS Package object
            
        Returns:
            List of pip package requirements
        """
        pip_deps = []
        for dep in package.dependencies:
            if dep.name.startswith('pip:'):
                # Handle direct pip dependencies in format "pip:package_name==version"
                pip_deps.append(dep.name[4:])  # Remove 'pip:' prefix
        
        return pip_deps

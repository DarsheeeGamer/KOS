"""
Advanced PIP Integration for KOS Package Manager

This module provides enhanced integration with pip for Python package management,
including virtual environment support, requirements handling, and package synchronization.
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
import shutil
import re
import venv
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from datetime import datetime
from pathlib import Path

from .pip_manager import PipManager, PipPackage

logger = logging.getLogger('KOS.package.pip_integration')

# Default locations
DEFAULT_VENV_DIR = os.path.expanduser('~/.kos/kpm/venv')
DEFAULT_REQ_DIR = os.path.expanduser('~/.kos/kpm/requirements')
DEFAULT_CACHE_DIR = os.path.expanduser('~/.kos/kpm/cache/pip')

class PipEnvironment:
    """Virtual environment manager for pip packages"""
    def __init__(self, venv_dir: str = DEFAULT_VENV_DIR):
        self.venv_dir = venv_dir
        self.is_ready = False
        self._ensure_venv()
    
    def _ensure_venv(self) -> bool:
        """Ensure virtual environment exists"""
        if os.path.exists(self.venv_dir):
            # Check if it's a valid venv
            if self._is_valid_venv():
                self.is_ready = True
                return True
        
        # Create virtual environment
        logger.info(f"Creating virtual environment at {self.venv_dir}")
        try:
            # Create parent directory if needed
            os.makedirs(os.path.dirname(self.venv_dir), exist_ok=True)
            
            # Create venv
            venv.create(self.venv_dir, with_pip=True)
            self.is_ready = True
            return True
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False
    
    def _is_valid_venv(self) -> bool:
        """Check if the directory is a valid virtual environment"""
        # Check for key directories and files that should exist in a venv
        pip_exe = self._get_pip_path()
        python_exe = self._get_python_path()
        
        return os.path.exists(pip_exe) and os.path.exists(python_exe)
    
    def _get_pip_path(self) -> str:
        """Get path to pip executable in the virtual environment"""
        if os.name == 'nt':  # Windows
            return os.path.join(self.venv_dir, 'Scripts', 'pip.exe')
        else:  # Unix-like
            return os.path.join(self.venv_dir, 'bin', 'pip')
    
    def _get_python_path(self) -> str:
        """Get path to Python executable in the virtual environment"""
        if os.name == 'nt':  # Windows
            return os.path.join(self.venv_dir, 'Scripts', 'python.exe')
        else:  # Unix-like
            return os.path.join(self.venv_dir, 'bin', 'python')
    
    def run_pip_command(self, command: List[str], capture_output: bool = True) -> Tuple[bool, str, str]:
        """
        Run a pip command in the virtual environment
        
        Args:
            command: Pip command and arguments
            capture_output: Whether to capture and return output
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        if not self.is_ready:
            if not self._ensure_venv():
                return False, "", "Virtual environment not available"
        
        pip_path = self._get_pip_path()
        cmd = [pip_path] + command
        
        try:
            if capture_output:
                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return process.returncode == 0, process.stdout, process.stderr
            else:
                process = subprocess.run(cmd)
                return process.returncode == 0, "", ""
        except Exception as e:
            logger.error(f"Error running pip command: {e}")
            return False, "", str(e)
    
    def run_python_command(self, command: List[str], capture_output: bool = True) -> Tuple[bool, str, str]:
        """
        Run a Python command in the virtual environment
        
        Args:
            command: Python command and arguments
            capture_output: Whether to capture and return output
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        if not self.is_ready:
            if not self._ensure_venv():
                return False, "", "Virtual environment not available"
        
        python_path = self._get_python_path()
        cmd = [python_path] + command
        
        try:
            if capture_output:
                process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                return process.returncode == 0, process.stdout, process.stderr
            else:
                process = subprocess.run(cmd)
                return process.returncode == 0, "", ""
        except Exception as e:
            logger.error(f"Error running Python command: {e}")
            return False, "", str(e)

class AdvancedPipManager(PipManager):
    """Enhanced pip manager with advanced features"""
    def __init__(self, venv_dir: str = DEFAULT_VENV_DIR):
        super().__init__(venv_dir)
        self.env = PipEnvironment(venv_dir)
        self.requirements_dir = DEFAULT_REQ_DIR
        self.cache_dir = DEFAULT_CACHE_DIR
        
        # Create directories if needed
        os.makedirs(self.requirements_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def install_package(self, package_spec: str, app_name: str = None, 
                      options: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Install a single package with advanced options
        
        Args:
            package_spec: Package specification (e.g., "requests" or "requests==2.28.1")
            app_name: Name of the app requiring this package
            options: Dictionary of installation options
                - upgrade: Upgrade package if already installed
                - user: Install to user site-packages
                - ignore_deps: Don't install dependencies
                - index_url: Use alternative package index
                - find_links: Look for archives in this directory
                - cache_dir: Cache directory
                - quiet: Don't display output
                
        Returns:
            Tuple of (success, message)
        """
        # Set default options
        if options is None:
            options = {}
        
        # Build command
        cmd = ['install', package_spec]
        
        # Add options
        if options.get('upgrade'):
            cmd.append('--upgrade')
        
        if options.get('user'):
            cmd.append('--user')
        
        if options.get('ignore_deps'):
            cmd.append('--no-deps')
        
        if options.get('index_url'):
            cmd.extend(['--index-url', options['index_url']])
        
        if options.get('find_links'):
            cmd.extend(['--find-links', options['find_links']])
        
        if options.get('cache_dir'):
            cache_dir = options['cache_dir']
        else:
            cache_dir = self.cache_dir
        cmd.extend(['--cache-dir', cache_dir])
        
        if options.get('quiet'):
            cmd.append('--quiet')
        
        # Run pip install
        success, stdout, stderr = self.env.run_pip_command(cmd)
        
        if success:
            # Extract package name and version from spec
            if '==' in package_spec:
                name, version = package_spec.split('==', 1)
            else:
                name = package_spec
                version = None
            
            # Update version if needed
            name = name.lower()
            if not version:
                self._update_package_version(name)
                if name in self.installed_packages:
                    version = self.installed_packages[name].version
            
            # Track dependency
            if app_name:
                if name not in self.installed_packages:
                    self.installed_packages[name] = PipPackage(name, version, app_name)
                elif app_name not in self.installed_packages[name].required_by:
                    self.installed_packages[name].required_by.append(app_name)
            
            # Save registry
            self._save_registry()
            
            return True, f"Successfully installed {name}" + (f" {version}" if version else "")
        else:
            return False, f"Pip install failed: {stderr}"
    
    def uninstall_package(self, package_name: str, app_name: str = None,
                        options: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Uninstall a package with advanced options
        
        Args:
            package_name: Name of the package to uninstall
            app_name: Name of the app that no longer requires this package
            options: Dictionary of uninstallation options
                - yes: Don't ask for confirmation
                - ignore_deps: Don't uninstall dependencies
                - quiet: Don't display output
                
        Returns:
            Tuple of (success, message)
        """
        # Set default options
        if options is None:
            options = {}
        
        # Check if package is installed
        package_name = package_name.lower()
        if package_name not in self.installed_packages:
            return False, f"Package {package_name} is not installed"
        
        # Remove the app from required_by list
        if app_name and app_name in self.installed_packages[package_name].required_by:
            self.installed_packages[package_name].required_by.remove(app_name)
        
        # If package is still required by other apps, don't uninstall
        if self.installed_packages[package_name].required_by:
            other_apps = ", ".join(self.installed_packages[package_name].required_by)
            return True, f"Package {package_name} is still required by: {other_apps}"
        
        # Build command
        cmd = ['uninstall', package_name]
        
        # Add options
        if options.get('yes') or True:  # Always yes for now
            cmd.append('-y')
        
        if options.get('quiet'):
            cmd.append('--quiet')
        
        # Run pip uninstall
        success, stdout, stderr = self.env.run_pip_command(cmd)
        
        if success:
            # Remove from registry
            if package_name in self.installed_packages:
                del self.installed_packages[package_name]
                self._save_registry()
            
            # Uninstall dependencies if requested
            if not options.get('ignore_deps') and 'dependencies' in locals() and dependencies:
                for dep in dependencies:
                    if dep in self.installed_packages and app_name in self.installed_packages[dep].required_by:
                        self.uninstall_package(dep, app_name, options)
            
            return True, f"Successfully uninstalled {package_name}"
        else:
            return False, f"Pip uninstall failed: {stderr}"
    
    def install_requirements(self, requirements_file: str, app_name: str = None,
                           options: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Install packages from a requirements file with advanced options
        
        Args:
            requirements_file: Path to the requirements.txt file
            app_name: Name of the app requiring these packages
            options: Dictionary of installation options
                - upgrade: Upgrade packages if already installed
                - user: Install to user site-packages
                - index_url: Use alternative package index
                - find_links: Look for archives in this directory
                - cache_dir: Cache directory
                - quiet: Don't display output
                
        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(requirements_file):
            return False, f"Requirements file not found: {requirements_file}"
        
        # Set default options
        if options is None:
            options = {}
        
        # Build command
        cmd = ['install', '-r', requirements_file]
        
        # Add options
        if options.get('upgrade'):
            cmd.append('--upgrade')
        
        if options.get('user'):
            cmd.append('--user')
        
        if options.get('index_url'):
            cmd.extend(['--index-url', options['index_url']])
        
        if options.get('find_links'):
            cmd.extend(['--find-links', options['find_links']])
        
        if options.get('cache_dir'):
            cache_dir = options['cache_dir']
        else:
            cache_dir = self.cache_dir
        cmd.extend(['--cache-dir', cache_dir])
        
        if options.get('quiet'):
            cmd.append('--quiet')
        
        # Run pip install
        success, stdout, stderr = self.env.run_pip_command(cmd)
        
        if success:
            # Parse requirements file to track dependencies
            if app_name:
                self._track_requirements(requirements_file, app_name)
            
            return True, f"Successfully installed packages from {requirements_file}"
        else:
            return False, f"Pip install failed: {stderr}"
    
    def _track_requirements(self, requirements_file: str, app_name: str):
        """
        Parse requirements file and track dependencies
        
        Args:
            requirements_file: Path to the requirements.txt file
            app_name: Name of the app requiring these packages
        """
        try:
            with open(requirements_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Handle basic requirement specs (ignoring complex constraints for now)
                    if '==' in line:
                        name, version = line.split('==', 1)
                    else:
                        # Extract package name (without version specifiers)
                        name = re.split(r'[<>=~!]', line)[0].strip()
                        version = None
                    
                    name = name.lower()
                    
                    # Update version if needed
                    if not version:
                        self._update_package_version(name)
                        if name in self.installed_packages:
                            version = self.installed_packages[name].version
                    
                    # Track dependency
                    if name not in self.installed_packages:
                        self.installed_packages[name] = PipPackage(name, version, app_name)
                    elif app_name not in self.installed_packages[name].required_by:
                        self.installed_packages[name].required_by.append(app_name)
            
            # Save registry
            self._save_registry()
        except Exception as e:
            logger.error(f"Error tracking requirements: {e}")
    
    def generate_requirements(self, app_name: str = None, include_version: bool = True) -> Tuple[bool, str, List[str]]:
        """
        Generate requirements list for an app or all installed packages
        
        Args:
            app_name: Name of the app to generate requirements for (None for all)
            include_version: Whether to include version specifiers
            
        Returns:
            Tuple of (success, message, requirements list)
        """
        requirements = []
        
        try:
            if app_name:
                # Generate requirements for specific app
                for name, pkg in self.installed_packages.items():
                    if app_name in pkg.required_by:
                        if include_version and pkg.version:
                            requirements.append(f"{name}=={pkg.version}")
                        else:
                            requirements.append(name)
            else:
                # Generate requirements for all packages
                cmd = ['freeze']
                success, stdout, stderr = self.env.run_pip_command(cmd)
                
                if success:
                    requirements = stdout.splitlines()
                else:
                    return False, f"Failed to generate requirements: {stderr}", []
            
            requirements.sort()
            return True, f"Generated {len(requirements)} requirements", requirements
        except Exception as e:
            logger.error(f"Error generating requirements: {e}")
            return False, f"Error generating requirements: {str(e)}", []
    
    def save_requirements(self, requirements: List[str], output_file: str) -> Tuple[bool, str]:
        """
        Save requirements to a file
        
        Args:
            requirements: List of requirement strings
            output_file: Path to output file
            
        Returns:
            Tuple of (success, message)
        """
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'w') as f:
                f.write("\n".join(requirements) + "\n")
            
            return True, f"Saved {len(requirements)} requirements to {output_file}"
        except Exception as e:
            logger.error(f"Error saving requirements: {e}")
            return False, f"Error saving requirements: {str(e)}"
    
    def generate_requirements_file(self, app_name: str = None, output_file: str = None,
                                 include_version: bool = True) -> Tuple[bool, str]:
        """
        Generate a requirements.txt file for an app or all installed packages
        
        Args:
            app_name: Name of the app to generate requirements for (None for all)
            output_file: Path to output file (None for auto-generate)
            include_version: Whether to include version specifiers
            
        Returns:
            Tuple of (success, message)
        """
        # Generate requirements list
        success, message, requirements = self.generate_requirements(app_name, include_version)
        
        if not success:
            return success, message
        
        # Auto-generate output file name if not provided
        if output_file is None:
            if app_name:
                filename = f"{app_name}_requirements.txt"
            else:
                filename = "requirements.txt"
            output_file = os.path.join(self.requirements_dir, filename)
        
        # Save requirements to file
        return self.save_requirements(requirements, output_file)
    
    def check_outdated_packages(self) -> Tuple[bool, str, Dict[str, Dict[str, str]]]:
        """
        Check for outdated packages
        
        Returns:
            Tuple of (success, message, {package_name: {current_version, latest_version}})
        """
        # Run pip list --outdated
        cmd = ['list', '--outdated', '--format=json']
        success, stdout, stderr = self.env.run_pip_command(cmd)
        
        if not success:
            return False, f"Failed to check outdated packages: {stderr}", {}
        
        try:
            packages = json.loads(stdout)
            outdated = {}
            
            for pkg in packages:
                name = pkg['name'].lower()
                outdated[name] = {
                    'current_version': pkg['version'],
                    'latest_version': pkg['latest_version']
                }
            
            return True, f"Found {len(outdated)} outdated packages", outdated
        except Exception as e:
            logger.error(f"Error parsing outdated packages: {e}")
            return False, f"Error parsing outdated packages: {str(e)}", {}
    
    def search_pypi(self, query: str) -> Tuple[bool, str, List[Dict[str, str]]]:
        """
        Search PyPI for packages
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (success, message, [package_info])
        """
        # Create a temporary Python script to search PyPI
        script = f"""
import json
import xmlrpc.client

client = xmlrpc.client.ServerProxy('https://pypi.org/pypi')
results = client.search({{'name': '{query}'}})
print(json.dumps(results))
"""
        
        # Create temporary file
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as f:
            f.write(script)
            script_path = f.name
        
        try:
            # Run the script
            success, stdout, stderr = self.env.run_python_command([script_path])
            
            # Clean up
            os.unlink(script_path)
            
            if not success:
                return False, f"Failed to search PyPI: {stderr}", []
            
            # Parse results
            results = json.loads(stdout)
            
            # Format results
            packages = []
            for pkg in results:
                packages.append({
                    'name': pkg['name'],
                    'version': pkg['version'],
                    'summary': pkg['summary']
                })
            
            return True, f"Found {len(packages)} packages matching '{query}'", packages
        except Exception as e:
            # Clean up on error
            if os.path.exists(script_path):
                os.unlink(script_path)
            
            logger.error(f"Error searching PyPI: {e}")
            return False, f"Error searching PyPI: {str(e)}", []
    
    def get_package_info(self, package_name: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Get detailed information about a package
        
        Args:
            package_name: Name of the package
            
        Returns:
            Tuple of (success, message, package_info)
        """
        # Run pip show
        cmd = ['show', package_name]
        success, stdout, stderr = self.env.run_pip_command(cmd)
        
        if not success:
            return False, f"Failed to get package info: {stderr}", {}
        
        # Parse output
        info = {}
        for line in stdout.splitlines():
            if not line.strip():
                continue
            
            key, value = line.split(':', 1)
            info[key.strip().lower()] = value.strip()
        
        return True, f"Retrieved information for {package_name}", info
    
    def create_virtual_environment(self, env_dir: str, system_site_packages: bool = False) -> Tuple[bool, str]:
        """
        Create a new virtual environment
        
        Args:
            env_dir: Directory for the virtual environment
            system_site_packages: Whether to include system site packages
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Create parent directory if needed
            os.makedirs(os.path.dirname(env_dir), exist_ok=True)
            
            # Create venv
            venv.create(env_dir, with_pip=True, system_site_packages=system_site_packages)
            
            return True, f"Created virtual environment at {env_dir}"
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {e}")
            return False, f"Failed to create virtual environment: {str(e)}"

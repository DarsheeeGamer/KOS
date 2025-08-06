"""
Python VFS Environment
Python and pip integration with KOS VFS
"""

import sys
import json
import io
import zipfile
import urllib.request
import urllib.error
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time

from ..core.errors import PackageError

@dataclass 
class PythonPackage:
    """Python package metadata"""
    name: str
    version: str
    location: str
    install_date: float
    size: int = 0

class PythonVFSEnvironment:
    """
    Python environment that installs everything to VFS
    Clean implementation that actually works
    """
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.site_packages = "/usr/lib/python3/site-packages"
        self.pip_cache = "/var/cache/pip"
        self.packages_index = "/var/lib/kpm/python_packages.json"
        self.packages: Dict[str, PythonPackage] = {}
        
        self._init_directories()
        self._load_packages()
    
    def _init_directories(self):
        """Initialize Python directories in VFS"""
        if not self.vfs:
            return
        
        dirs = [
            "/usr/lib/python3",
            self.site_packages,
            "/var/cache",
            self.pip_cache,
            "/var/lib/kpm"
        ]
        
        for dir_path in dirs:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path)
                except:
                    pass
    
    def _load_packages(self):
        """Load installed Python packages"""
        if not self.vfs or not self.vfs.exists(self.packages_index):
            return
        
        try:
            with self.vfs.open(self.packages_index, 'r') as f:
                data = json.loads(f.read().decode())
                for pkg_name, pkg_info in data.items():
                    self.packages[pkg_name] = PythonPackage(**pkg_info)
        except:
            pass
    
    def _save_packages(self):
        """Save package index"""
        if not self.vfs:
            return
        
        try:
            data = {
                name: {
                    'name': pkg.name,
                    'version': pkg.version,
                    'location': pkg.location,
                    'install_date': pkg.install_date,
                    'size': pkg.size
                }
                for name, pkg in self.packages.items()
            }
            
            with self.vfs.open(self.packages_index, 'w') as f:
                f.write(json.dumps(data, indent=2).encode())
        except:
            pass
    
    def pip_install(self, package_spec: str, upgrade: bool = False) -> Tuple[bool, str]:
        """
        Install a Python package to VFS
        Simplified but functional
        """
        # Parse package spec (name==version or just name)
        if '==' in package_spec:
            pkg_name, version = package_spec.split('==')
        else:
            pkg_name = package_spec
            version = None
        
        # Check if already installed
        if pkg_name in self.packages and not upgrade:
            return True, f"Package '{pkg_name}' is already installed. Use --upgrade to update."
        
        # Download package info from PyPI
        try:
            pypi_url = f"https://pypi.org/pypi/{pkg_name}/json"
            with urllib.request.urlopen(pypi_url, timeout=10) as response:
                data = json.loads(response.read())
            
            # Get version
            if not version:
                version = data['info']['version']
            
            # Find wheel URL
            wheel_url = None
            if version in data['releases']:
                for file_info in data['releases'][version]:
                    if file_info['packagetype'] == 'bdist_wheel':
                        # Prefer universal wheels
                        if 'py3-none-any' in file_info['filename'] or 'py2.py3-none-any' in file_info['filename']:
                            wheel_url = file_info['url']
                            break
            
            if not wheel_url:
                # Try to find any wheel
                for file_info in data['releases'][version]:
                    if file_info['packagetype'] == 'bdist_wheel':
                        wheel_url = file_info['url']
                        break
            
            if not wheel_url:
                return False, f"No wheel distribution found for {pkg_name}=={version}"
            
            # Download wheel
            print(f"Downloading {pkg_name}=={version}...")
            with urllib.request.urlopen(wheel_url, timeout=30) as response:
                wheel_data = response.read()
            
            # Install to VFS
            return self._install_wheel(pkg_name, version, wheel_data)
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False, f"Package '{pkg_name}' not found on PyPI"
            return False, f"HTTP error: {e}"
        except Exception as e:
            return False, f"Error installing package: {e}"
    
    def _install_wheel(self, pkg_name: str, version: str, wheel_data: bytes) -> Tuple[bool, str]:
        """Install wheel to VFS"""
        if not self.vfs:
            return False, "VFS not available"
        
        try:
            # Open wheel as zip
            wheel_zip = zipfile.ZipFile(io.BytesIO(wheel_data))
            
            pkg_dir = f"{self.site_packages}/{pkg_name}"
            installed_files = []
            total_size = 0
            
            # Extract files to VFS
            for file_info in wheel_zip.filelist:
                file_path = file_info.filename
                
                # Skip metadata files for now
                if '.dist-info/' in file_path:
                    continue
                
                # Determine target path
                target_path = f"{self.site_packages}/{file_path}"
                
                if file_path.endswith('/'):
                    # Directory
                    if not self.vfs.exists(target_path):
                        self.vfs.mkdir(target_path)
                else:
                    # File
                    # Ensure parent directory exists
                    parent = '/'.join(target_path.split('/')[:-1])
                    if parent and not self.vfs.exists(parent):
                        self._create_parent_dirs(parent)
                    
                    # Write file
                    file_data = wheel_zip.read(file_info.filename)
                    with self.vfs.open(target_path, 'w') as f:
                        f.write(file_data)
                    
                    installed_files.append(target_path)
                    total_size += len(file_data)
            
            wheel_zip.close()
            
            # Update package registry
            self.packages[pkg_name] = PythonPackage(
                name=pkg_name,
                version=version,
                location=pkg_dir,
                install_date=time.time(),
                size=total_size
            )
            self._save_packages()
            
            return True, f"Successfully installed {pkg_name}=={version} to VFS"
            
        except Exception as e:
            return False, f"Error installing wheel: {e}"
    
    def pip_uninstall(self, package_name: str) -> Tuple[bool, str]:
        """Uninstall a Python package from VFS"""
        if package_name not in self.packages:
            return False, f"Package '{package_name}' is not installed"
        
        pkg = self.packages[package_name]
        
        # Remove package directory
        if self.vfs and self.vfs.exists(pkg.location):
            self._remove_directory(pkg.location)
        
        # Remove from registry
        del self.packages[package_name]
        self._save_packages()
        
        return True, f"Successfully uninstalled {package_name}"
    
    def pip_list(self) -> List[PythonPackage]:
        """List installed Python packages"""
        return sorted(self.packages.values(), key=lambda p: p.name)
    
    def pip_show(self, package_name: str) -> Optional[PythonPackage]:
        """Show package info"""
        return self.packages.get(package_name)
    
    def get_python_path(self) -> List[str]:
        """Get Python path for VFS"""
        return [
            self.site_packages,
            "/usr/lib/python3",
            "/usr/local/lib/python3"
        ]
    
    def _create_parent_dirs(self, path: str):
        """Create parent directories recursively"""
        if not self.vfs:
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current = f"/{part}" if not current else f"{current}/{part}"
            if not self.vfs.exists(current):
                try:
                    self.vfs.mkdir(current)
                except:
                    pass
    
    def _remove_directory(self, path: str):
        """Remove directory recursively"""
        if not self.vfs:
            return
        
        try:
            # List contents
            for name in self.vfs.listdir(path):
                child_path = f"{path}/{name}"
                if self.vfs.isdir(child_path):
                    self._remove_directory(child_path)
                else:
                    self.vfs.unlink(child_path)
            
            # Remove the directory itself
            self.vfs.rmdir(path)
        except:
            pass
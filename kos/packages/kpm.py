"""
KPM - KOS Package Manager
Simple, working package management for KOS
"""

import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..core.errors import PackageError

@dataclass
class Package:
    """Package metadata"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    installed: bool = False
    install_date: Optional[float] = None
    size: int = 0

class KPM:
    """
    KOS Package Manager
    Actually simple and functional
    """
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.packages: Dict[str, Package] = {}
        self.package_dir = "/var/lib/kpm/packages"
        self.index_file = "/var/lib/kpm/index.json"
        self.cache_dir = "/var/cache/kpm"
        
        self._init_directories()
        self._load_index()
        self._init_builtin_packages()
    
    def _init_directories(self):
        """Create KPM directories in VFS"""
        if not self.vfs:
            return
        
        dirs = [
            "/var",
            "/var/lib",
            "/var/lib/kpm",
            self.package_dir,
            "/var/cache",
            self.cache_dir
        ]
        
        for dir_path in dirs:
            if not self.vfs.exists(dir_path):
                try:
                    self.vfs.mkdir(dir_path)
                except:
                    pass
    
    def _load_index(self):
        """Load package index from VFS"""
        if not self.vfs or not self.vfs.exists(self.index_file):
            return
        
        try:
            with self.vfs.open(self.index_file, 'r') as f:
                data = json.loads(f.read().decode())
                for pkg_data in data.get('packages', []):
                    pkg = Package(**pkg_data)
                    self.packages[pkg.name] = pkg
        except Exception:
            pass
    
    def _save_index(self):
        """Save package index to VFS"""
        if not self.vfs:
            return
        
        try:
            data = {
                'version': '1.0',
                'updated': time.time(),
                'packages': [asdict(pkg) for pkg in self.packages.values()]
            }
            
            with self.vfs.open(self.index_file, 'w') as f:
                f.write(json.dumps(data, indent=2).encode())
        except Exception:
            pass
    
    def _init_builtin_packages(self):
        """Initialize built-in packages"""
        builtin = [
            Package(
                name="kos-core",
                version="2.0",
                description="KOS Core System",
                author="KOS Team",
                installed=True,
                install_date=time.time()
            ),
            Package(
                name="kos-shell",
                version="2.0",
                description="KOS Interactive Shell",
                author="KOS Team",
                installed=True,
                install_date=time.time()
            ),
            Package(
                name="text-editor",
                version="1.0",
                description="Simple text editor for KOS",
                author="KOS Team",
                files=["/usr/bin/edit"],
                size=10240
            ),
            Package(
                name="file-manager",
                version="1.0",
                description="File management utilities",
                author="KOS Team",
                files=["/usr/bin/fm"],
                size=15360
            ),
            Package(
                name="network-tools",
                version="1.0",
                description="Network utilities (ping, curl, wget)",
                author="KOS Team",
                dependencies=["kos-core"],
                files=["/usr/bin/ping", "/usr/bin/curl", "/usr/bin/wget"],
                size=25600
            ),
            Package(
                name="python3",
                version="3.10",
                description="Python 3 interpreter",
                author="Python Software Foundation",
                files=["/usr/bin/python3"],
                size=51200
            ),
            Package(
                name="git",
                version="2.40",
                description="Version control system",
                author="Git Team",
                files=["/usr/bin/git"],
                size=40960
            )
        ]
        
        for pkg in builtin:
            if pkg.name not in self.packages:
                self.packages[pkg.name] = pkg
        
        self._save_index()
    
    def install(self, package_name: str, force: bool = False) -> Tuple[bool, str]:
        """Install a package"""
        if package_name not in self.packages:
            # Try to find similar packages
            similar = self._find_similar(package_name)
            if similar:
                return False, f"Package '{package_name}' not found. Did you mean: {', '.join(similar)}?"
            return False, f"Package '{package_name}' not found"
        
        pkg = self.packages[package_name]
        
        if pkg.installed and not force:
            return True, f"Package '{package_name}' is already installed"
        
        # Check dependencies
        for dep in pkg.dependencies:
            if dep not in self.packages or not self.packages[dep].installed:
                return False, f"Dependency '{dep}' is not installed"
        
        # Simulate installation
        if self.vfs:
            # Create package files in VFS
            for file_path in pkg.files:
                if not self.vfs.exists(file_path):
                    # Create parent directories
                    parent = '/'.join(file_path.split('/')[:-1])
                    if parent and not self.vfs.exists(parent):
                        self._create_parent_dirs(parent)
                    
                    # Create file with placeholder content
                    try:
                        with self.vfs.open(file_path, 'w') as f:
                            f.write(f"#!/usr/bin/env python3\n# {pkg.name} v{pkg.version}\nprint('{pkg.description}')\n".encode())
                    except:
                        pass
        
        # Mark as installed
        pkg.installed = True
        pkg.install_date = time.time()
        self._save_index()
        
        return True, f"Successfully installed '{package_name}' v{pkg.version}"
    
    def uninstall(self, package_name: str) -> Tuple[bool, str]:
        """Uninstall a package"""
        if package_name not in self.packages:
            return False, f"Package '{package_name}' not found"
        
        pkg = self.packages[package_name]
        
        if not pkg.installed:
            return False, f"Package '{package_name}' is not installed"
        
        # Check if other packages depend on this
        dependents = []
        for other_pkg in self.packages.values():
            if package_name in other_pkg.dependencies and other_pkg.installed:
                dependents.append(other_pkg.name)
        
        if dependents:
            return False, f"Cannot uninstall: required by {', '.join(dependents)}"
        
        # Remove package files from VFS
        if self.vfs:
            for file_path in pkg.files:
                if self.vfs.exists(file_path):
                    try:
                        self.vfs.unlink(file_path)
                    except:
                        pass
        
        # Mark as uninstalled
        pkg.installed = False
        pkg.install_date = None
        self._save_index()
        
        return True, f"Successfully uninstalled '{package_name}'"
    
    def list_packages(self, installed_only: bool = False) -> List[Package]:
        """List packages"""
        packages = list(self.packages.values())
        
        if installed_only:
            packages = [pkg for pkg in packages if pkg.installed]
        
        return sorted(packages, key=lambda p: p.name)
    
    def search(self, query: str) -> List[Package]:
        """Search for packages"""
        query = query.lower()
        results = []
        
        for pkg in self.packages.values():
            if (query in pkg.name.lower() or 
                query in pkg.description.lower() or
                query in pkg.author.lower()):
                results.append(pkg)
        
        return sorted(results, key=lambda p: p.name)
    
    def info(self, package_name: str) -> Optional[Package]:
        """Get package information"""
        return self.packages.get(package_name)
    
    def upgrade(self, package_name: str = None) -> Tuple[bool, str]:
        """Upgrade package(s)"""
        if package_name:
            if package_name not in self.packages:
                return False, f"Package '{package_name}' not found"
            
            # Simulate upgrade
            pkg = self.packages[package_name]
            if not pkg.installed:
                return False, f"Package '{package_name}' is not installed"
            
            return True, f"Package '{package_name}' is up to date"
        else:
            # Upgrade all packages
            upgraded = []
            for pkg in self.packages.values():
                if pkg.installed:
                    upgraded.append(pkg.name)
            
            if upgraded:
                return True, f"Checked {len(upgraded)} packages, all up to date"
            else:
                return True, "No packages to upgrade"
    
    def _find_similar(self, name: str, max_results: int = 3) -> List[str]:
        """Find similar package names"""
        similar = []
        name_lower = name.lower()
        
        for pkg_name in self.packages.keys():
            if name_lower in pkg_name.lower() or pkg_name.lower() in name_lower:
                similar.append(pkg_name)
                if len(similar) >= max_results:
                    break
        
        return similar
    
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
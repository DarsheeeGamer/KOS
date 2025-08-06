"""
Package repository and dependency resolution for KOS
"""

import json
import time
import hashlib
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

class PackageStatus(Enum):
    """Package installation status"""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATING = "updating"
    BROKEN = "broken"

@dataclass
class PackageVersion:
    """Package version information"""
    major: int
    minor: int
    patch: int
    
    def __str__(self):
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def __lt__(self, other):
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
    
    def __eq__(self, other):
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)
    
    @classmethod
    def parse(cls, version_str: str) -> 'PackageVersion':
        """Parse version string"""
        parts = version_str.split('.')
        return cls(
            major=int(parts[0]) if len(parts) > 0 else 0,
            minor=int(parts[1]) if len(parts) > 1 else 0,
            patch=int(parts[2]) if len(parts) > 2 else 0
        )

@dataclass
class Dependency:
    """Package dependency"""
    package_name: str
    version_constraint: str  # >=1.0.0, <2.0.0, ==1.2.3
    optional: bool = False
    
    def satisfies(self, version: PackageVersion) -> bool:
        """Check if version satisfies constraint"""
        if not self.version_constraint:
            return True
        
        # Parse constraint
        if self.version_constraint.startswith('>='):
            min_version = PackageVersion.parse(self.version_constraint[2:])
            return version >= min_version
        elif self.version_constraint.startswith('<='):
            max_version = PackageVersion.parse(self.version_constraint[2:])
            return version <= max_version
        elif self.version_constraint.startswith('>'):
            min_version = PackageVersion.parse(self.version_constraint[1:])
            return version > min_version
        elif self.version_constraint.startswith('<'):
            max_version = PackageVersion.parse(self.version_constraint[1:])
            return version < max_version
        elif self.version_constraint.startswith('=='):
            exact_version = PackageVersion.parse(self.version_constraint[2:])
            return version == exact_version
        else:
            # No operator, assume exact match
            exact_version = PackageVersion.parse(self.version_constraint)
            return version == exact_version

@dataclass
class Package:
    """Package metadata"""
    name: str
    version: PackageVersion
    description: str
    author: str
    license: str
    size: int
    checksum: str
    dependencies: List[Dependency] = field(default_factory=list)
    files: List[str] = field(default_factory=list)
    scripts: Dict[str, str] = field(default_factory=dict)  # pre-install, post-install, etc.
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'version': str(self.version),
            'description': self.description,
            'author': self.author,
            'license': self.license,
            'size': self.size,
            'checksum': self.checksum,
            'dependencies': [
                {
                    'package': dep.package_name,
                    'version': dep.version_constraint,
                    'optional': dep.optional
                }
                for dep in self.dependencies
            ],
            'files': self.files,
            'scripts': self.scripts
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Package':
        """Create from dictionary"""
        return cls(
            name=data['name'],
            version=PackageVersion.parse(data['version']),
            description=data.get('description', ''),
            author=data.get('author', ''),
            license=data.get('license', ''),
            size=data.get('size', 0),
            checksum=data.get('checksum', ''),
            dependencies=[
                Dependency(
                    package_name=dep['package'],
                    version_constraint=dep.get('version', ''),
                    optional=dep.get('optional', False)
                )
                for dep in data.get('dependencies', [])
            ],
            files=data.get('files', []),
            scripts=data.get('scripts', {})
        )

class Repository:
    """Package repository"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.repo_dir = "/var/kpm/repository"
        self.packages: Dict[str, List[Package]] = {}  # name -> versions
        self.index_file = f"{self.repo_dir}/index.json"
        
        self._init_repository()
    
    def _init_repository(self):
        """Initialize repository"""
        if not self.vfs:
            return
        
        # Create repository directory
        if not self.vfs.exists(self.repo_dir):
            try:
                self.vfs.mkdir(self.repo_dir)
            except:
                pass
        
        # Load package index
        self._load_index()
    
    def _load_index(self):
        """Load package index"""
        if not self.vfs or not self.vfs.exists(self.index_file):
            return
        
        try:
            with self.vfs.open(self.index_file, 'r') as f:
                index_data = json.loads(f.read().decode())
            
            for package_data in index_data.get('packages', []):
                package = Package.from_dict(package_data)
                
                if package.name not in self.packages:
                    self.packages[package.name] = []
                
                self.packages[package.name].append(package)
        except:
            pass
    
    def _save_index(self):
        """Save package index"""
        if not self.vfs:
            return
        
        # Prepare index data
        packages_list = []
        for versions in self.packages.values():
            for package in versions:
                packages_list.append(package.to_dict())
        
        index_data = {
            'version': '1.0',
            'updated': time.time(),
            'packages': packages_list
        }
        
        try:
            with self.vfs.open(self.index_file, 'w') as f:
                f.write(json.dumps(index_data, indent=2).encode())
        except:
            pass
    
    def add_package(self, package: Package, package_data: bytes) -> bool:
        """Add package to repository"""
        # Verify checksum
        if hashlib.sha256(package_data).hexdigest() != package.checksum:
            return False
        
        # Add to index
        if package.name not in self.packages:
            self.packages[package.name] = []
        
        # Check if version exists
        for existing in self.packages[package.name]:
            if existing.version == package.version:
                return False  # Version already exists
        
        self.packages[package.name].append(package)
        
        # Save package file
        package_file = f"{self.repo_dir}/{package.name}-{package.version}.kpkg"
        
        try:
            if self.vfs:
                with self.vfs.open(package_file, 'wb') as f:
                    f.write(package_data)
        except:
            return False
        
        # Update index
        self._save_index()
        
        return True
    
    def get_package(self, name: str, version: Optional[PackageVersion] = None) -> Optional[Package]:
        """Get package metadata"""
        if name not in self.packages:
            return None
        
        versions = self.packages[name]
        
        if version:
            # Get specific version
            for pkg in versions:
                if pkg.version == version:
                    return pkg
        else:
            # Get latest version
            return max(versions, key=lambda p: p.version)
        
        return None
    
    def search_packages(self, query: str) -> List[Package]:
        """Search packages"""
        results = []
        
        for versions in self.packages.values():
            for package in versions:
                if (query.lower() in package.name.lower() or
                    query.lower() in package.description.lower()):
                    results.append(package)
        
        return results
    
    def list_packages(self) -> List[Package]:
        """List all packages"""
        all_packages = []
        for versions in self.packages.values():
            all_packages.extend(versions)
        return all_packages

class DependencyResolver:
    """Dependency resolution engine"""
    
    def __init__(self, repository: Repository):
        self.repository = repository
        self.installed_packages: Dict[str, PackageVersion] = {}
    
    def resolve(self, package_name: str, 
                version: Optional[PackageVersion] = None) -> List[Package]:
        """Resolve package dependencies"""
        to_install = []
        visited = set()
        
        # Get package
        package = self.repository.get_package(package_name, version)
        if not package:
            raise ValueError(f"Package {package_name} not found")
        
        # Resolve dependencies recursively
        self._resolve_recursive(package, to_install, visited)
        
        return to_install
    
    def _resolve_recursive(self, package: Package, 
                          to_install: List[Package], 
                          visited: Set[str]):
        """Recursively resolve dependencies"""
        if package.name in visited:
            return
        
        visited.add(package.name)
        
        # Check dependencies
        for dependency in package.dependencies:
            if dependency.optional:
                continue
            
            # Check if already installed
            if dependency.package_name in self.installed_packages:
                installed_version = self.installed_packages[dependency.package_name]
                if dependency.satisfies(installed_version):
                    continue
            
            # Get dependency package
            dep_package = self._find_satisfying_version(
                dependency.package_name,
                dependency.version_constraint
            )
            
            if not dep_package:
                raise ValueError(f"Cannot satisfy dependency: {dependency.package_name} {dependency.version_constraint}")
            
            # Resolve its dependencies
            self._resolve_recursive(dep_package, to_install, visited)
        
        # Add package to install list
        to_install.append(package)
    
    def _find_satisfying_version(self, package_name: str, 
                                 constraint: str) -> Optional[Package]:
        """Find package version that satisfies constraint"""
        if package_name not in self.repository.packages:
            return None
        
        versions = self.repository.packages[package_name]
        dependency = Dependency(package_name, constraint)
        
        # Find best matching version
        satisfying = [pkg for pkg in versions if dependency.satisfies(pkg.version)]
        
        if satisfying:
            return max(satisfying, key=lambda p: p.version)
        
        return None
    
    def check_conflicts(self, packages: List[Package]) -> List[str]:
        """Check for conflicts between packages"""
        conflicts = []
        installed = self.installed_packages.copy()
        
        for package in packages:
            # Check if different version is already marked for install
            if package.name in installed:
                if installed[package.name] != package.version:
                    conflicts.append(
                        f"Conflict: {package.name} {package.version} conflicts with {installed[package.name]}"
                    )
            
            installed[package.name] = package.version
        
        return conflicts

class PackageInstaller:
    """Package installation manager"""
    
    def __init__(self, vfs=None, repository: Repository = None):
        self.vfs = vfs
        self.repository = repository
        self.install_dir = "/usr/local"
        self.installed_db = "/var/kpm/installed.db"
        self.installed: Dict[str, Package] = {}
        
        self._load_installed()
    
    def _load_installed(self):
        """Load installed packages database"""
        if not self.vfs or not self.vfs.exists(self.installed_db):
            return
        
        try:
            with self.vfs.open(self.installed_db, 'r') as f:
                data = json.loads(f.read().decode())
            
            for package_data in data.get('packages', []):
                package = Package.from_dict(package_data)
                self.installed[package.name] = package
        except:
            pass
    
    def _save_installed(self):
        """Save installed packages database"""
        if not self.vfs:
            return
        
        data = {
            'version': '1.0',
            'packages': [pkg.to_dict() for pkg in self.installed.values()]
        }
        
        try:
            # Ensure directory exists
            db_dir = '/'.join(self.installed_db.split('/')[:-1])
            if not self.vfs.exists(db_dir):
                self.vfs.mkdir(db_dir)
            
            with self.vfs.open(self.installed_db, 'w') as f:
                f.write(json.dumps(data, indent=2).encode())
        except:
            pass
    
    def install_package(self, package: Package) -> bool:
        """Install package"""
        if not self.vfs or not self.repository:
            return False
        
        # Check if already installed
        if package.name in self.installed:
            if self.installed[package.name].version >= package.version:
                return True  # Already have same or newer version
        
        # Get package file
        package_file = f"{self.repository.repo_dir}/{package.name}-{package.version}.kpkg"
        
        if not self.vfs.exists(package_file):
            return False
        
        try:
            # Read package data
            with self.vfs.open(package_file, 'rb') as f:
                package_data = f.read()
            
            # Run pre-install script
            if 'pre-install' in package.scripts:
                # Would execute script
                pass
            
            # Extract files (simplified - would use tar/zip)
            # For now, just mark as installed
            
            # Run post-install script
            if 'post-install' in package.scripts:
                # Would execute script
                pass
            
            # Update installed database
            self.installed[package.name] = package
            self._save_installed()
            
            return True
        except:
            return False
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall package"""
        if package_name not in self.installed:
            return False
        
        package = self.installed[package_name]
        
        # Run pre-uninstall script
        if 'pre-uninstall' in package.scripts:
            # Would execute script
            pass
        
        # Remove files
        for file_path in package.files:
            full_path = f"{self.install_dir}/{file_path}"
            if self.vfs and self.vfs.exists(full_path):
                try:
                    self.vfs.remove(full_path)
                except:
                    pass
        
        # Run post-uninstall script
        if 'post-uninstall' in package.scripts:
            # Would execute script
            pass
        
        # Update database
        del self.installed[package_name]
        self._save_installed()
        
        return True
    
    def upgrade_package(self, package_name: str) -> bool:
        """Upgrade package to latest version"""
        if not self.repository:
            return False
        
        # Get latest version
        latest = self.repository.get_package(package_name)
        if not latest:
            return False
        
        # Check if upgrade needed
        if package_name in self.installed:
            if self.installed[package_name].version >= latest.version:
                return True  # Already up to date
        
        # Install new version
        return self.install_package(latest)
    
    def list_installed(self) -> List[Package]:
        """List installed packages"""
        return list(self.installed.values())
    
    def is_installed(self, package_name: str) -> bool:
        """Check if package is installed"""
        return package_name in self.installed
    
    def get_installed_version(self, package_name: str) -> Optional[PackageVersion]:
        """Get installed package version"""
        if package_name in self.installed:
            return self.installed[package_name].version
        return None
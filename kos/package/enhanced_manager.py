"""
Enhanced Package Manager for KOS
=================================

Advanced package management system supporting:
- Cross-platform package distribution
- Dependency resolution and management
- Remote repository synchronization
- Security and signature verification
- Version management and updates
- Integration with Kaede compilation system
"""

import os
import json
import time
import hashlib
import logging
import requests
import tempfile
import subprocess
import threading
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import shutil
import tarfile
import zipfile

from .manager import KpmManager  # Import existing manager
from ..core.platform_compat import PlatformType, ArchitectureType, get_current_platform
from ..core.kaede_integration import KaedeIntegrationEngine

logger = logging.getLogger('KOS.package.enhanced_manager')

class PackageType(Enum):
    """Package types"""
    APPLICATION = "application"
    LIBRARY = "library"
    MODULE = "module"
    TOOL = "tool"
    RUNTIME = "runtime"
    EXTENSION = "extension"

class PackageSource(Enum):
    """Package sources"""
    OFFICIAL = "official"
    COMMUNITY = "community"
    PRIVATE = "private"
    LOCAL = "local"

class PackageStatus(Enum):
    """Package installation status"""
    NOT_INSTALLED = auto()
    INSTALLED = auto()
    OUTDATED = auto()
    BROKEN = auto()
    INSTALLING = auto()
    UPDATING = auto()

@dataclass
class PackageMetadata:
    """Enhanced package metadata"""
    name: str
    version: str
    type: PackageType
    source: PackageSource
    description: str = ""
    author: str = ""
    license: str = ""
    homepage: str = ""
    repository: str = ""
    keywords: List[str] = field(default_factory=list)
    
    # Platform support
    supported_platforms: List[PlatformType] = field(default_factory=list)
    supported_architectures: List[ArchitectureType] = field(default_factory=list)
    
    # Dependencies
    dependencies: Dict[str, str] = field(default_factory=dict)  # name -> version spec
    optional_dependencies: Dict[str, str] = field(default_factory=dict)
    build_dependencies: Dict[str, str] = field(default_factory=dict)
    
    # Files and installation
    files: List[str] = field(default_factory=list)
    install_scripts: List[str] = field(default_factory=list)
    uninstall_scripts: List[str] = field(default_factory=list)
    
    # Security
    checksum: str = ""
    signature: str = ""
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    size: int = 0
    download_count: int = 0

@dataclass
class Repository:
    """Package repository"""
    name: str
    url: str
    type: str = "http"  # http, git, local
    enabled: bool = True
    priority: int = 100
    cache_ttl: int = 3600  # Cache time-to-live in seconds
    last_sync: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PackageInstallation:
    """Package installation record"""
    package: PackageMetadata
    installed_at: float
    installed_by: str = "system"
    install_path: str = ""
    status: PackageStatus = PackageStatus.INSTALLED
    files_manifest: List[str] = field(default_factory=list)

class DependencyResolver:
    """Advanced dependency resolution system"""
    
    def __init__(self, package_manager):
        self.package_manager = package_manager
        self.resolution_cache = {}
        
    def resolve_dependencies(self, package_name: str, version_spec: str = "*") -> List[Tuple[str, str]]:
        """Resolve package dependencies"""
        cache_key = f"{package_name}:{version_spec}"
        if cache_key in self.resolution_cache:
            return self.resolution_cache[cache_key]
        
        try:
            # Get package metadata
            package = self.package_manager.get_package_metadata(package_name, version_spec)
            if not package:
                raise ValueError(f"Package not found: {package_name}")
            
            resolved = []
            to_resolve = [(package_name, version_spec)]
            resolved_packages = set()
            
            while to_resolve:
                current_name, current_version = to_resolve.pop(0)
                
                if current_name in resolved_packages:
                    continue
                
                current_package = self.package_manager.get_package_metadata(current_name, current_version)
                if not current_package:
                    continue
                
                resolved.append((current_name, current_package.version))
                resolved_packages.add(current_name)
                
                # Add dependencies to resolution queue
                for dep_name, dep_version in current_package.dependencies.items():
                    if dep_name not in resolved_packages:
                        to_resolve.append((dep_name, dep_version))
            
            self.resolution_cache[cache_key] = resolved
            return resolved
            
        except Exception as e:
            logger.error(f"Dependency resolution failed for {package_name}: {e}")
            return []
    
    def check_conflicts(self, packages: List[Tuple[str, str]]) -> List[str]:
        """Check for dependency conflicts"""
        conflicts = []
        package_versions = {}
        
        for name, version in packages:
            if name in package_versions:
                if package_versions[name] != version:
                    conflicts.append(f"Version conflict for {name}: {package_versions[name]} vs {version}")
            else:
                package_versions[name] = version
        
        return conflicts

class PackageCache:
    """Package cache management"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.metadata_cache = {}
        self.download_cache = {}
        
    def get_package_cache_path(self, package_name: str, version: str) -> Path:
        """Get cache path for package"""
        return self.cache_dir / f"{package_name}-{version}.pkg"
    
    def is_cached(self, package_name: str, version: str) -> bool:
        """Check if package is cached"""
        cache_path = self.get_package_cache_path(package_name, version)
        return cache_path.exists()
    
    def cache_package(self, package_name: str, version: str, data: bytes) -> bool:
        """Cache package data"""
        try:
            cache_path = self.get_package_cache_path(package_name, version)
            with open(cache_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            logger.error(f"Failed to cache package {package_name}-{version}: {e}")
            return False
    
    def get_cached_package(self, package_name: str, version: str) -> Optional[bytes]:
        """Get cached package data"""
        try:
            cache_path = self.get_package_cache_path(package_name, version)
            if cache_path.exists():
                with open(cache_path, 'rb') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to read cached package {package_name}-{version}: {e}")
        return None
    
    def clear_cache(self):
        """Clear package cache"""
        try:
            for file_path in self.cache_dir.glob("*.pkg"):
                file_path.unlink()
            logger.info("Package cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")

class SecurityManager:
    """Package security and verification"""
    
    def __init__(self):
        self.trusted_keys = set()
        self.verification_enabled = True
        
    def verify_package(self, package: PackageMetadata, data: bytes) -> bool:
        """Verify package integrity and signature"""
        try:
            # Verify checksum
            if package.checksum:
                calculated_checksum = hashlib.sha256(data).hexdigest()
                if calculated_checksum != package.checksum:
                    logger.error(f"Checksum mismatch for {package.name}")
                    return False
            
            # Verify signature (simplified implementation)
            if package.signature and self.verification_enabled:
                # In a real implementation, this would verify cryptographic signatures
                logger.debug(f"Signature verification for {package.name} (placeholder)")
            
            return True
            
        except Exception as e:
            logger.error(f"Package verification failed for {package.name}: {e}")
            return False
    
    def is_trusted_source(self, source: PackageSource) -> bool:
        """Check if package source is trusted"""
        if source == PackageSource.OFFICIAL:
            return True
        elif source == PackageSource.COMMUNITY:
            return True  # Could be configurable
        elif source == PackageSource.PRIVATE:
            return True  # Would check private key trust
        else:
            return False

class EnhancedPackageManager:
    """Enhanced package manager with advanced features"""
    
    def __init__(self, config_dir: str = None):
        # Initialize paths
        self.config_dir = Path(config_dir or os.path.expanduser("~/.kos/packages"))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_dir = self.config_dir / "cache"
        self.packages_dir = self.config_dir / "packages"
        self.repos_file = self.config_dir / "repositories.json"
        self.installed_file = self.config_dir / "installed.json"
        
        # Initialize components
        self.cache = PackageCache(str(self.cache_dir))
        self.security = SecurityManager()
        self.dependency_resolver = DependencyResolver(self)
        self.kaede_engine = KaedeIntegrationEngine()
        
        # Load configuration
        self.repositories = self._load_repositories()
        self.installed_packages = self._load_installed_packages()
        
        # Platform info
        self.platform_info = get_current_platform()
        
        # Repository cache
        self.repo_cache = {}
        self.repo_cache_lock = threading.RLock()
        
    def _load_repositories(self) -> List[Repository]:
        """Load repository configuration"""
        try:
            if self.repos_file.exists():
                with open(self.repos_file, 'r') as f:
                    repos_data = json.load(f)
                
                repositories = []
                for repo_data in repos_data:
                    repo = Repository(
                        name=repo_data["name"],
                        url=repo_data["url"],
                        type=repo_data.get("type", "http"),
                        enabled=repo_data.get("enabled", True),
                        priority=repo_data.get("priority", 100),
                        cache_ttl=repo_data.get("cache_ttl", 3600),
                        last_sync=repo_data.get("last_sync", 0),
                        metadata=repo_data.get("metadata", {})
                    )
                    repositories.append(repo)
                
                return repositories
                
        except Exception as e:
            logger.error(f"Failed to load repositories: {e}")
        
        # Return default repositories
        return [
            Repository(
                name="official",
                url="https://packages.kos.dev/official",
                type="http",
                priority=1
            ),
            Repository(
                name="community",
                url="https://packages.kos.dev/community",
                type="http",
                priority=10
            )
        ]
    
    def _save_repositories(self):
        """Save repository configuration"""
        try:
            repos_data = []
            for repo in self.repositories:
                repos_data.append({
                    "name": repo.name,
                    "url": repo.url,
                    "type": repo.type,
                    "enabled": repo.enabled,
                    "priority": repo.priority,
                    "cache_ttl": repo.cache_ttl,
                    "last_sync": repo.last_sync,
                    "metadata": repo.metadata
                })
            
            with open(self.repos_file, 'w') as f:
                json.dump(repos_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save repositories: {e}")
    
    def _load_installed_packages(self) -> Dict[str, PackageInstallation]:
        """Load installed packages"""
        try:
            if self.installed_file.exists():
                with open(self.installed_file, 'r') as f:
                    installed_data = json.load(f)
                
                installed = {}
                for pkg_name, pkg_data in installed_data.items():
                    # Reconstruct PackageMetadata
                    metadata = PackageMetadata(
                        name=pkg_data["package"]["name"],
                        version=pkg_data["package"]["version"],
                        type=PackageType(pkg_data["package"]["type"]),
                        source=PackageSource(pkg_data["package"]["source"]),
                        description=pkg_data["package"].get("description", ""),
                        dependencies=pkg_data["package"].get("dependencies", {}),
                        **{k: v for k, v in pkg_data["package"].items() 
                           if k not in ["name", "version", "type", "source", "description", "dependencies"]}
                    )
                    
                    installation = PackageInstallation(
                        package=metadata,
                        installed_at=pkg_data["installed_at"],
                        installed_by=pkg_data.get("installed_by", "system"),
                        install_path=pkg_data.get("install_path", ""),
                        status=PackageStatus(pkg_data.get("status", "INSTALLED")),
                        files_manifest=pkg_data.get("files_manifest", [])
                    )
                    
                    installed[pkg_name] = installation
                
                return installed
                
        except Exception as e:
            logger.error(f"Failed to load installed packages: {e}")
        
        return {}
    
    def _save_installed_packages(self):
        """Save installed packages"""
        try:
            installed_data = {}
            for pkg_name, installation in self.installed_packages.items():
                # Convert to serializable format
                pkg_data = installation.package.__dict__.copy()
                pkg_data["type"] = pkg_data["type"].value
                pkg_data["source"] = pkg_data["source"].value
                
                installed_data[pkg_name] = {
                    "package": pkg_data,
                    "installed_at": installation.installed_at,
                    "installed_by": installation.installed_by,
                    "install_path": installation.install_path,
                    "status": installation.status.value,
                    "files_manifest": installation.files_manifest
                }
            
            with open(self.installed_file, 'w') as f:
                json.dump(installed_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save installed packages: {e}")
    
    def add_repository(self, name: str, url: str, repo_type: str = "http", priority: int = 100) -> bool:
        """Add a new repository"""
        try:
            # Check if repository already exists
            for repo in self.repositories:
                if repo.name == name:
                    logger.warning(f"Repository {name} already exists")
                    return False
            
            # Create new repository
            new_repo = Repository(
                name=name,
                url=url,
                type=repo_type,
                priority=priority
            )
            
            self.repositories.append(new_repo)
            self.repositories.sort(key=lambda r: r.priority)
            
            self._save_repositories()
            logger.info(f"Added repository: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add repository {name}: {e}")
            return False
    
    def remove_repository(self, name: str) -> bool:
        """Remove a repository"""
        try:
            self.repositories = [r for r in self.repositories if r.name != name]
            self._save_repositories()
            logger.info(f"Removed repository: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove repository {name}: {e}")
            return False
    
    def sync_repositories(self, force: bool = False) -> bool:
        """Synchronize repository metadata"""
        try:
            current_time = time.time()
            success_count = 0
            
            for repo in self.repositories:
                if not repo.enabled:
                    continue
                
                # Check if sync is needed
                if not force and (current_time - repo.last_sync) < repo.cache_ttl:
                    continue
                
                logger.info(f"Syncing repository: {repo.name}")
                
                if self._sync_repository(repo):
                    repo.last_sync = current_time
                    success_count += 1
                else:
                    logger.error(f"Failed to sync repository: {repo.name}")
            
            self._save_repositories()
            logger.info(f"Synced {success_count} repositories")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"Repository sync failed: {e}")
            return False
    
    def _sync_repository(self, repo: Repository) -> bool:
        """Sync individual repository"""
        try:
            if repo.type == "http":
                return self._sync_http_repository(repo)
            elif repo.type == "git":
                return self._sync_git_repository(repo)
            elif repo.type == "local":
                return self._sync_local_repository(repo)
            else:
                logger.error(f"Unsupported repository type: {repo.type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to sync repository {repo.name}: {e}")
            return False
    
    def _sync_http_repository(self, repo: Repository) -> bool:
        """Sync HTTP repository"""
        try:
            # Fetch repository index
            index_url = f"{repo.url}/index.json"
            response = requests.get(index_url, timeout=30)
            response.raise_for_status()
            
            repo_index = response.json()
            
            # Cache repository metadata
            with self.repo_cache_lock:
                self.repo_cache[repo.name] = repo_index
            
            logger.debug(f"Synced {len(repo_index.get('packages', []))} packages from {repo.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync HTTP repository {repo.name}: {e}")
            return False
    
    def _sync_git_repository(self, repo: Repository) -> bool:
        """Sync Git repository"""
        try:
            # Clone or update git repository
            repo_dir = self.cache_dir / "repos" / repo.name
            
            if repo_dir.exists():
                # Update existing repository
                subprocess.run(
                    ["git", "pull"],
                    cwd=repo_dir,
                    check=True,
                    capture_output=True
                )
            else:
                # Clone new repository
                repo_dir.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["git", "clone", repo.url, str(repo_dir)],
                    check=True,
                    capture_output=True
                )
            
            # Load repository index
            index_file = repo_dir / "index.json"
            if index_file.exists():
                with open(index_file, 'r') as f:
                    repo_index = json.load(f)
                
                with self.repo_cache_lock:
                    self.repo_cache[repo.name] = repo_index
                
                return True
            
        except Exception as e:
            logger.error(f"Failed to sync Git repository {repo.name}: {e}")
        
        return False
    
    def _sync_local_repository(self, repo: Repository) -> bool:
        """Sync local repository"""
        try:
            repo_path = Path(repo.url)
            index_file = repo_path / "index.json"
            
            if index_file.exists():
                with open(index_file, 'r') as f:
                    repo_index = json.load(f)
                
                with self.repo_cache_lock:
                    self.repo_cache[repo.name] = repo_index
                
                return True
            
        except Exception as e:
            logger.error(f"Failed to sync local repository {repo.name}: {e}")
        
        return False
    
    def search_packages(self, query: str, package_type: PackageType = None) -> List[PackageMetadata]:
        """Search for packages"""
        matches = []
        
        with self.repo_cache_lock:
            for repo_name, repo_data in self.repo_cache.items():
                packages = repo_data.get("packages", [])
                
                for pkg_data in packages:
                    try:
                        # Create package metadata
                        package = self._create_package_metadata(pkg_data)
                        
                        # Check platform compatibility
                        if not self._is_platform_compatible(package):
                            continue
                        
                        # Filter by type
                        if package_type and package.type != package_type:
                            continue
                        
                        # Search in name, description, keywords
                        search_text = f"{package.name} {package.description} {' '.join(package.keywords)}".lower()
                        if query.lower() in search_text:
                            matches.append(package)
                            
                    except Exception as e:
                        logger.debug(f"Error processing package metadata: {e}")
                        continue
        
        # Sort by relevance (name matches first)
        matches.sort(key=lambda p: (
            0 if query.lower() in p.name.lower() else 1,
            p.name.lower()
        ))
        
        return matches
    
    def get_package_metadata(self, package_name: str, version_spec: str = "*") -> Optional[PackageMetadata]:
        """Get package metadata"""
        with self.repo_cache_lock:
            for repo_name, repo_data in self.repo_cache.items():
                packages = repo_data.get("packages", [])
                
                for pkg_data in packages:
                    if pkg_data.get("name") == package_name:
                        package = self._create_package_metadata(pkg_data)
                        
                        # Check version compatibility
                        if self._version_matches(package.version, version_spec):
                            return package
        
        return None
    
    def install_package(self, package_name: str, version_spec: str = "*", force: bool = False) -> bool:
        """Install a package"""
        try:
            logger.info(f"Installing package: {package_name}")
            
            # Check if already installed
            if package_name in self.installed_packages and not force:
                logger.info(f"Package {package_name} is already installed")
                return True
            
            # Get package metadata
            package = self.get_package_metadata(package_name, version_spec)
            if not package:
                logger.error(f"Package not found: {package_name}")
                return False
            
            # Check platform compatibility
            if not self._is_platform_compatible(package):
                logger.error(f"Package {package_name} is not compatible with current platform")
                return False
            
            # Resolve dependencies
            dependencies = self.dependency_resolver.resolve_dependencies(package_name, version_spec)
            logger.info(f"Resolved {len(dependencies)} dependencies")
            
            # Check for conflicts
            conflicts = self.dependency_resolver.check_conflicts(dependencies)
            if conflicts:
                logger.error(f"Dependency conflicts: {conflicts}")
                return False
            
            # Install dependencies first
            for dep_name, dep_version in dependencies:
                if dep_name == package_name:
                    continue  # Skip self
                
                if dep_name not in self.installed_packages:
                    logger.info(f"Installing dependency: {dep_name}")
                    if not self.install_package(dep_name, dep_version):
                        logger.error(f"Failed to install dependency: {dep_name}")
                        return False
            
            # Download and install package
            if self._download_and_install_package(package):
                logger.info(f"Successfully installed {package_name}")
                return True
            else:
                logger.error(f"Failed to install {package_name}")
                return False
                
        except Exception as e:
            logger.error(f"Installation failed for {package_name}: {e}")
            return False
    
    def uninstall_package(self, package_name: str, force: bool = False) -> bool:
        """Uninstall a package"""
        try:
            if package_name not in self.installed_packages:
                logger.warning(f"Package {package_name} is not installed")
                return True
            
            installation = self.installed_packages[package_name]
            
            # Check for dependents
            if not force:
                dependents = self._find_dependents(package_name)
                if dependents:
                    logger.error(f"Cannot uninstall {package_name}, required by: {', '.join(dependents)}")
                    return False
            
            # Run uninstall scripts
            for script in installation.package.uninstall_scripts:
                try:
                    self._run_script(script, installation.install_path)
                except Exception as e:
                    logger.warning(f"Uninstall script failed: {e}")
            
            # Remove files
            for file_path in installation.files_manifest:
                try:
                    file_path_obj = Path(file_path)
                    if file_path_obj.exists():
                        if file_path_obj.is_file():
                            file_path_obj.unlink()
                        elif file_path_obj.is_dir():
                            shutil.rmtree(file_path_obj)
                except Exception as e:
                    logger.warning(f"Failed to remove file {file_path}: {e}")
            
            # Remove from installed packages
            del self.installed_packages[package_name]
            self._save_installed_packages()
            
            logger.info(f"Successfully uninstalled {package_name}")
            return True
            
        except Exception as e:
            logger.error(f"Uninstallation failed for {package_name}: {e}")
            return False
    
    def update_package(self, package_name: str) -> bool:
        """Update a package to the latest version"""
        try:
            if package_name not in self.installed_packages:
                logger.error(f"Package {package_name} is not installed")
                return False
            
            current_version = self.installed_packages[package_name].package.version
            latest_package = self.get_package_metadata(package_name)
            
            if not latest_package:
                logger.error(f"Package {package_name} not found in repositories")
                return False
            
            if current_version == latest_package.version:
                logger.info(f"Package {package_name} is already at latest version")
                return True
            
            logger.info(f"Updating {package_name} from {current_version} to {latest_package.version}")
            
            # Uninstall current version and install new version
            if self.uninstall_package(package_name, force=True):
                return self.install_package(package_name)
            
            return False
            
        except Exception as e:
            logger.error(f"Update failed for {package_name}: {e}")
            return False
    
    def list_installed_packages(self) -> List[PackageInstallation]:
        """List all installed packages"""
        return list(self.installed_packages.values())
    
    def list_available_packages(self) -> List[PackageMetadata]:
        """List all available packages"""
        packages = []
        
        with self.repo_cache_lock:
            for repo_name, repo_data in self.repo_cache.items():
                for pkg_data in repo_data.get("packages", []):
                    try:
                        package = self._create_package_metadata(pkg_data)
                        if self._is_platform_compatible(package):
                            packages.append(package)
                    except Exception as e:
                        logger.debug(f"Error processing package: {e}")
        
        return packages
    
    def get_package_status(self, package_name: str) -> PackageStatus:
        """Get package installation status"""
        if package_name not in self.installed_packages:
            return PackageStatus.NOT_INSTALLED
        
        installation = self.installed_packages[package_name]
        current_version = installation.package.version
        
        # Check if there's a newer version available
        latest_package = self.get_package_metadata(package_name)
        if latest_package and latest_package.version != current_version:
            return PackageStatus.OUTDATED
        
        return installation.status
    
    def _create_package_metadata(self, pkg_data: Dict[str, Any]) -> PackageMetadata:
        """Create PackageMetadata from dictionary"""
        return PackageMetadata(
            name=pkg_data["name"],
            version=pkg_data["version"],
            type=PackageType(pkg_data.get("type", "application")),
            source=PackageSource(pkg_data.get("source", "community")),
            description=pkg_data.get("description", ""),
            author=pkg_data.get("author", ""),
            license=pkg_data.get("license", ""),
            homepage=pkg_data.get("homepage", ""),
            repository=pkg_data.get("repository", ""),
            keywords=pkg_data.get("keywords", []),
            supported_platforms=[PlatformType(p) for p in pkg_data.get("supported_platforms", [])],
            supported_architectures=[ArchitectureType(a) for a in pkg_data.get("supported_architectures", [])],
            dependencies=pkg_data.get("dependencies", {}),
            optional_dependencies=pkg_data.get("optional_dependencies", {}),
            build_dependencies=pkg_data.get("build_dependencies", {}),
            files=pkg_data.get("files", []),
            install_scripts=pkg_data.get("install_scripts", []),
            uninstall_scripts=pkg_data.get("uninstall_scripts", []),
            checksum=pkg_data.get("checksum", ""),
            signature=pkg_data.get("signature", ""),
            size=pkg_data.get("size", 0),
            download_count=pkg_data.get("download_count", 0)
        )
    
    def _is_platform_compatible(self, package: PackageMetadata) -> bool:
        """Check if package is compatible with current platform"""
        if not package.supported_platforms:
            return True  # No restrictions
        
        if self.platform_info.platform not in package.supported_platforms:
            return False
        
        if package.supported_architectures:
            if self.platform_info.architecture not in package.supported_architectures:
                return False
        
        return True
    
    def _version_matches(self, version: str, version_spec: str) -> bool:
        """Check if version matches specification"""
        if version_spec == "*":
            return True
        
        # Simple version matching (could be enhanced with semantic versioning)
        if version_spec.startswith(">="):
            return version >= version_spec[2:]
        elif version_spec.startswith("<="):
            return version <= version_spec[2:]
        elif version_spec.startswith(">"):
            return version > version_spec[1:]
        elif version_spec.startswith("<"):
            return version < version_spec[1:]
        elif version_spec.startswith("=="):
            return version == version_spec[2:]
        else:
            return version == version_spec
    
    def _download_and_install_package(self, package: PackageMetadata) -> bool:
        """Download and install package"""
        try:
            # Check cache first
            if self.cache.is_cached(package.name, package.version):
                logger.debug(f"Using cached package: {package.name}")
                package_data = self.cache.get_cached_package(package.name, package.version)
            else:
                # Download package
                package_data = self._download_package(package)
                if not package_data:
                    return False
                
                # Cache package
                self.cache.cache_package(package.name, package.version, package_data)
            
            # Verify package
            if not self.security.verify_package(package, package_data):
                logger.error(f"Package verification failed: {package.name}")
                return False
            
            # Extract and install
            install_path = self.packages_dir / package.name
            if self._extract_package(package_data, install_path):
                # Run install scripts
                for script in package.install_scripts:
                    try:
                        self._run_script(script, str(install_path))
                    except Exception as e:
                        logger.warning(f"Install script failed: {e}")
                
                # Record installation
                installation = PackageInstallation(
                    package=package,
                    installed_at=time.time(),
                    install_path=str(install_path),
                    files_manifest=self._get_installed_files(install_path)
                )
                
                self.installed_packages[package.name] = installation
                self._save_installed_packages()
                
                return True
            
        except Exception as e:
            logger.error(f"Failed to install package {package.name}: {e}")
        
        return False
    
    def _download_package(self, package: PackageMetadata) -> Optional[bytes]:
        """Download package from repository"""
        try:
            # Find repository containing this package
            for repo in self.repositories:
                if not repo.enabled:
                    continue
                
                package_url = f"{repo.url}/packages/{package.name}/{package.version}.pkg"
                
                try:
                    response = requests.get(package_url, timeout=60)
                    if response.status_code == 200:
                        logger.info(f"Downloaded {package.name} from {repo.name}")
                        return response.content
                except requests.RequestException:
                    continue
            
            logger.error(f"Failed to download package: {package.name}")
            return None
            
        except Exception as e:
            logger.error(f"Download failed for {package.name}: {e}")
            return None
    
    def _extract_package(self, package_data: bytes, install_path: Path) -> bool:
        """Extract package to installation directory"""
        try:
            install_path.mkdir(parents=True, exist_ok=True)
            
            with tempfile.NamedTemporaryFile(suffix='.pkg') as temp_file:
                temp_file.write(package_data)
                temp_file.flush()
                
                # Try different archive formats
                try:
                    with tarfile.open(temp_file.name, 'r:*') as tar:
                        tar.extractall(install_path)
                    return True
                except tarfile.TarError:
                    pass
                
                try:
                    with zipfile.ZipFile(temp_file.name, 'r') as zip_file:
                        zip_file.extractall(install_path)
                    return True
                except zipfile.BadZipFile:
                    pass
            
            logger.error("Unsupported package format")
            return False
            
        except Exception as e:
            logger.error(f"Package extraction failed: {e}")
            return False
    
    def _run_script(self, script: str, working_dir: str):
        """Run installation/uninstallation script"""
        try:
            # For security, only allow whitelisted script commands
            allowed_commands = ["python", "python3", "bash", "sh"]
            
            script_parts = script.split()
            if script_parts and script_parts[0] in allowed_commands:
                subprocess.run(
                    script_parts,
                    cwd=working_dir,
                    check=True,
                    timeout=300
                )
            else:
                logger.warning(f"Script command not allowed: {script}")
                
        except subprocess.TimeoutExpired:
            logger.error("Script execution timed out")
            raise
        except subprocess.CalledProcessError as e:
            logger.error(f"Script execution failed: {e}")
            raise
    
    def _get_installed_files(self, install_path: Path) -> List[str]:
        """Get list of installed files"""
        files = []
        try:
            for root, dirs, filenames in os.walk(install_path):
                for filename in filenames:
                    file_path = Path(root) / filename
                    files.append(str(file_path))
        except Exception as e:
            logger.error(f"Failed to enumerate files: {e}")
        
        return files
    
    def _find_dependents(self, package_name: str) -> List[str]:
        """Find packages that depend on given package"""
        dependents = []
        
        for installed_name, installation in self.installed_packages.items():
            if package_name in installation.package.dependencies:
                dependents.append(installed_name)
        
        return dependents

# Global enhanced package manager instance
_enhanced_package_manager = None

def get_enhanced_package_manager() -> EnhancedPackageManager:
    """Get the global enhanced package manager instance"""
    global _enhanced_package_manager
    if _enhanced_package_manager is None:
        _enhanced_package_manager = EnhancedPackageManager()
    return _enhanced_package_manager

__all__ = [
    'PackageType', 'PackageSource', 'PackageStatus',
    'PackageMetadata', 'Repository', 'PackageInstallation',
    'DependencyResolver', 'PackageCache', 'SecurityManager',
    'EnhancedPackageManager', 'get_enhanced_package_manager'
]
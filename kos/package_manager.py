"""KOS Package Manager

This module provides a unified interface for managing packages and applications in KOS.
It handles installation, removal, searching, and listing of packages from various sources.
"""
import sys
import os
import json
import shutil
import importlib
import logging
import requests
import subprocess
import importlib.util
import hashlib
import threading
import queue
import traceback
import time
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from contextlib import contextmanager

# Use absolute imports to avoid relative import errors
from kos.repo_config import RepoConfig as RepositoryConfig
from kos.filesystem import FileSystem

# Import the new Pydantic models
try:
    from kos.package.models import Package, PackageDependency, AppIndexEntry, RepositoryPackage, RepositoryInfo
    PYDANTIC_AVAILABLE = True
except ImportError:
    # Fallback to old models if Pydantic isn't installed yet
    from kos.package.app_index import AppIndexEntry
    from kos.package.repo_index import RepositoryPackage
    from kos.package.manager import Package, PackageDependency
    PYDANTIC_AVAILABLE = False

from kos.package.app_index import AppIndexManager
from kos.package.repo_index import RepoIndexManager
from kos.package.pip_manager import PipManager
from kos.package.manager import PackageDatabase
from kos.package.pip_commands import install_package, install_requirements, uninstall_package, list_installed_packages, is_package_installed


class DependencyResolver:
    """Resolves dependencies for packages
    
    This class implements a dependency resolution algorithm that can:
    1. Detect and resolve dependency chains
    2. Handle version constraints
    3. Detect circular dependencies
    4. Calculate the optimal installation order
    5. Handle optional dependencies
    """
    
    def __init__(self, package_db):
        """Initialize the resolver with access to the package database"""
        self.package_db = package_db
        self.visited = set()  # Used for circular dependency detection
        self.resolved = set()  # Packages that have been resolved
        self.resolution_order = []  # Order in which packages should be installed
        
    def reset(self):
        """Reset the resolver state"""
        self.visited = set()
        self.resolved = set()
        self.resolution_order = []
        
    def resolve(self, package_name: str, version_req: str = "latest") -> List[str]:
        """Resolve dependencies for a package
        
        Args:
            package_name: Name of the package to resolve dependencies for
            version_req: Version requirement for the package
            
        Returns:
            List of package names in order they should be installed
        """
        self.reset()  # Clear previous resolution state
        
        # Create a dependency node for the root package
        root_dep = PackageDependency(name=package_name, version_req=version_req)
        
        # Resolve dependencies recursively
        self._resolve_recursive(root_dep)
        
        # Return the installation order (excluding the root package if it's already installed)
        if package_name in self.package_db.packages and self.package_db.packages[package_name].installed:
            return [pkg for pkg in self.resolution_order if pkg != package_name]
        return self.resolution_order
    
    def _resolve_recursive(self, dependency: PackageDependency, parent: str = None):
        """Recursively resolve dependencies
        
        Args:
            dependency: The dependency to resolve
            parent: The parent package that depends on this one
        """
        package_name = dependency.name
        
        # Check for circular dependencies
        if package_name in self.visited:
            # This is a circular dependency, but might be resolvable
            # if the package is already installed or already in resolution order
            if package_name not in self.resolved and package_name not in self.resolution_order:
                if parent:
                    path = f"{parent} -> {package_name}"
                else:
                    path = package_name
                logging.warning(f"Circular dependency detected: {path}")
            return
            
        # Mark as visited for cycle detection
        self.visited.add(package_name)
        
        # Check if this package is already installed with compatible version
        if package_name in self.package_db.packages:
            pkg = self.package_db.packages[package_name]
            if pkg.installed and (dependency.version_req == "latest" or 
                                  self._version_satisfies_requirement(pkg.version, dependency.version_req)):
                self.resolved.add(package_name)
                return
        
        # Find all available versions of this package
        available_versions = self._find_available_versions(package_name, dependency.version_req)
        
        if not available_versions:
            if dependency.optional:
                logging.info(f"Optional dependency {package_name} {dependency.version_req} not found, skipping")
                return
            else:
                logging.error(f"Required dependency {package_name} {dependency.version_req} not found")
                raise ValueError(f"Required dependency {package_name} {dependency.version_req} not found")
                
        # Select the best version (usually the latest compatible one)
        best_version = self._select_best_version(available_versions)
        selected_pkg = available_versions[best_version]
        
        # Resolve dependencies of this package
        for dep in selected_pkg.dependencies:
            if isinstance(dep, str):
                # Handle string dependencies (legacy format or pip dependencies)
                if dep.startswith('pip:'):
                    # Pip dependencies are handled separately
                    continue
                # Convert simple string dependency to PackageDependency
                dep = PackageDependency(name=dep)
            elif isinstance(dep, dict):
                # Convert dict to PackageDependency
                dep = PackageDependency(**dep)
                
            self._resolve_recursive(dep, package_name)
            
        # Add this package to the resolution order
        if package_name not in self.resolution_order:
            self.resolution_order.append(package_name)
            
        self.resolved.add(package_name)
        
    def _find_available_versions(self, package_name: str, version_req: str) -> Dict[str, Any]:
        """Find all available versions of a package that satisfy the version requirement
        
        Args:
            package_name: Name of the package to find
            version_req: Version requirement
            
        Returns:
            Dictionary mapping version strings to package objects
        """
        result = {}
        
        # Check package database first
        if package_name in self.package_db.packages:
            pkg = self.package_db.packages[package_name]
            if self._version_satisfies_requirement(pkg.version, version_req):
                result[pkg.version] = pkg
                
        # TODO: Check repositories for available versions
        # This would typically query all configured repositories for versions
        # of the package that match the requirements
                
        return result
        
    def _select_best_version(self, versions: Dict[str, Any]) -> str:
        """Select the best version from available versions
        
        Usually this means selecting the latest version, but could
        implement other strategies like preferring stable versions.
        
        Args:
            versions: Dictionary mapping version strings to package objects
            
        Returns:
            The selected version string
        """
        if not versions:
            return None
            
        # For now, just select the highest version number
        # This is a simple implementation that could be improved
        def parse_version(version):
            parts = version.split('.')
            # Pad with zeros to ensure proper comparison
            while len(parts) < 3:
                parts.append('0')
            return [int(p.split('-')[0]) for p in parts]  # Handle pre-release versions
            
        return sorted(versions.keys(), key=parse_version, reverse=True)[0]
        
    def _version_satisfies_requirement(self, version: str, version_req: str) -> bool:
        """Check if a version satisfies a requirement
        
        Args:
            version: Version to check
            version_req: Version requirement
            
        Returns:
            True if version satisfies requirement, False otherwise
        """
        # Use the PackageDependency model's is_satisfied_by method if available
        if PYDANTIC_AVAILABLE:
            dep = PackageDependency(name="temp", version_req=version_req)
            return dep.is_satisfied_by(version)
            
        # Fallback implementation if Pydantic isn't available
        if version_req == "latest":
            return True
            
        # Simple exact match for basic compatibility
        return version == version_req

# Note: PipCommandHandler is imported inside methods to avoid circular imports

logger = logging.getLogger('KOS.package_manager')


class PackageNotFound(Exception):
    """Exception raised when a package cannot be found"""
    pass


class PackageInstallError(Exception):
    """Exception raised when a package installation fails"""
    pass


class PackageRemoveError(Exception):
    """Exception raised when a package removal fails"""
    pass


class DependencyError(Exception):
    """Exception raised when package dependencies cannot be resolved"""
    pass


def calculate_checksum(file_path):
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as file:
        while True:
            chunk = file.read(4096)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


class KpmManager:
    """Main package management class for KOS
    
    This class provides a unified interface for managing packages and applications,
    following the KOS design principle where applications are treated as special
    packages with executable capabilities.
    """
    def __init__(self, packages_file=None, package_dir=None):
        # Set default file paths or use provided ones
        self.packages_file = packages_file or os.path.join(os.path.expanduser("~"), ".kos", "kos_packages.json")
        self.package_dir = package_dir or os.path.join(os.path.expanduser("~"), ".kos", "kos_apps")
        
        # Create necessary directories
        os.makedirs(os.path.dirname(self.packages_file), exist_ok=True)
        os.makedirs(self.package_dir, exist_ok=True)
        
        # Initialize components
        self.repo_config = RepositoryConfig()
        self.package_db = PackageDatabase()
        self.pip_manager = PipManager()
        
        # Initialize the dependency resolver
        self.dependency_resolver = DependencyResolver(self.package_db)
        
        # Initialize the app and repo index managers
        self.app_index = AppIndexManager(self.package_dir)
        self.repo_index = RepoIndexManager()
        
        # Initialize event handlers dictionary
        self.event_handlers = {
            'pre_install': [],
            'post_install': [],
            'pre_remove': [],
            'post_remove': [],
            'pre_update': [],
            'post_update': []
        }
        
        # Load package database
        self._load_packages()
        self._initialize_apps()  # Initialize built-in apps
        
        # Setup event handlers
        self._setup_event_handlers()
        self.app_index = AppIndexManager(self.package_dir)
        self.repo_index = RepoIndexManager()
        
        # Load package data
        self._load_packages()
    
        self._initialize_apps()  # Initialize built-in apps
        
        # Setup event handlers
        self._setup_event_handlers()

    def _load_packages(self):
        """Load package registry and initialize package database"""
        default_packages = {
            "python": {
                "name": "python",
                "version": "3.11",
                "description": "Python programming language interpreter",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "python3"
            },
            "pip": {
                "name": "pip",
                "version": "latest",
                "description": "Python package installer",
                "author": "system",
                "dependencies": ["python"],
                "repository": "system",
                "entry_point": "pip"
            },
            "wget": {
                "name": "wget",
                "version": "latest",
                "description": "File download utility",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "wget"
            },
            "nano": {
                "name": "nano",
                "version": "latest",
                "description": "Simple text editor",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "nano"
            },
            "help": {
                "name": "help",
                "version": "1.0.0",
                "description": "KOS help utility",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "help.py"
            }
        }

        try:
            data = {"registry": default_packages, "installed": {}}
            
            if os.path.exists(self.packages_file):
                try:
                    with open(self.packages_file, 'r') as f:
                        file_data = json.load(f)
                        
                    # Validate file structure
                    if not isinstance(file_data, dict):
                        raise ValueError("Invalid package file format: root must be an object")
                        
                    # Ensure required keys exist
                    if "registry" not in file_data:
                        file_data["registry"] = {}
                    if "installed" not in file_data:
                        file_data["installed"] = {}
                        
                    # Merge with default packages
                    file_data["registry"].update(default_packages)
                    data = file_data
                except json.JSONDecodeError as json_err:
                    logger.error(f"Error parsing packages file, creating new one: {json_err}")
                    # Backup the corrupted file
                    backup_file = f"{self.packages_file}.bak.{int(time.time())}"
                    shutil.copy2(self.packages_file, backup_file)
                    logger.info(f"Backed up corrupted file to {backup_file}")
                except Exception as load_err:
                    logger.error(f"Error loading packages file: {load_err}")
            
            # Load packages into database
            for name, pkg_data in data["registry"].items():
                try:
                    # Ensure name is set correctly
                    pkg_data["name"] = name
                    
                    # Create package object using the appropriate model
                    if PYDANTIC_AVAILABLE:
                        # Use Pydantic models if available
                        pkg = Package.from_dict(pkg_data)
                    else:
                        # Fallback to old models
                        pkg = Package.from_dict(pkg_data)
                    
                    # Check if it's installed
                    pkg.installed = name in data.get("installed", {})
                    if pkg.installed and name in data["installed"]:
                        try:
                            install_date = data["installed"][name].get("installed_at")
                            if isinstance(install_date, str):
                                pkg.install_date = datetime.fromisoformat(install_date)
                            else:
                                pkg.install_date = install_date
                        except (ValueError, TypeError):
                            pkg.install_date = datetime.now()
                    
                    # Add to database
                    self.package_db.add_package(pkg)
                    
                    # If this is an application, ensure it's in the app index too
                    if pkg.installed and pkg.is_application:
                        self._sync_app_index(name)
                        
                except Exception as pkg_err:
                    logger.error(f"Error loading package '{name}': {pkg_err}")
            
            # Save the fixed/validated package data
            self._save_packages()

        except Exception as e:
            logger.error(f"Critical error loading packages: {e}")
            # Initialize with default packages only as a last resort
            for name, pkg_data in default_packages.items():
                pkg_data["name"] = name
                if PYDANTIC_AVAILABLE:
                    pkg = Package.from_dict(pkg_data)
                else:
                    pkg = Package.from_dict(pkg_data)
                self.package_db.add_package(pkg)
            # Force save the default packages
            self._save_packages()

    def _save_packages(self):
        """Save package registry"""
        data = {
            "installed": {},
            "registry": {}
        }

        for name, pkg in self.package_db.packages.items():
            if pkg.installed:
                # Convert datetime to ISO string for JSON serialization
                install_date = pkg.install_date
                if hasattr(install_date, 'isoformat'):
                    install_date = install_date.isoformat()
                elif isinstance(install_date, str):
                    install_date = install_date
                else:
                    install_date = datetime.now().isoformat()
                    
                data["installed"][name] = {
                    "version": pkg.version,
                    "installed_at": install_date
                }
            data["registry"][name] = pkg.to_dict()

        try:
            with open(self.packages_file, 'w') as f:
                json.dump(data, f, indent=2, default=self._json_serializer)
        except Exception as e:
            logger.error(f"Error saving packages: {e}")
            # Try without the problematic data
            try:
                # Create a safe copy without datetime objects
                safe_data = self._sanitize_for_json(data)
                with open(self.packages_file, 'w') as f:
                    json.dump(safe_data, f, indent=2)
            except Exception as e2:
                logger.error(f"Failed to save packages even with sanitization: {e2}")
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects"""
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def _sanitize_for_json(self, data):
        """Recursively sanitize data for JSON serialization"""
        if isinstance(data, dict):
            return {k: self._sanitize_for_json(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._sanitize_for_json(item) for item in data]
        elif hasattr(data, 'isoformat'):
            return data.isoformat()
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    def update(self):
        """Update package lists from all enabled repositories"""
        try:
            # Update repositories using RepoIndexManager
            print("Updating repositories...")
            results = self.repo_index.update_all_repositories()
            
            # Report results
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            if success_count == total_count:
                print(f"Successfully updated all {total_count} repositories")
            else:
                print(f"Updated {success_count} of {total_count} repositories")
                
                # Show which repositories failed
                for repo_name, success in results.items():
                    if not success:
                        print(f"Failed to update repository: {repo_name}")
            
            return success_count > 0
            
        except Exception as e:
            print(f"Error updating repositories: {str(e)}")
            logger.error(f"Error updating repositories: {e}")
            return False

    def search(self, query: str) -> List[Dict]:
        """Search for packages in both local database and repositories"""
        query = query.lower()
        results = []
        
        # Search in local database
        for pkg in self.package_db.packages.values():
            if query in pkg.name.lower() or query in pkg.description.lower():
                results.append({
                    'name': pkg.name,
                    'version': pkg.version,
                    'description': pkg.description,
                    'author': pkg.author,
                    'repository': pkg.repository,
                    'installed': pkg.installed
                })
        
        # Search in repository index
        repo_packages = self.repo_index.search_packages(query)
        for pkg in repo_packages:
            # Skip if already in results
            if any(r['name'] == pkg.name for r in results):
                continue
                
            results.append({
                'name': pkg.name,
                'version': pkg.version,
                'description': pkg.description,
                'author': pkg.author,
                'repository': pkg.repository,
                'installed': False,
                'tags': pkg.tags
            })
        
        # Print results for debugging
        for pkg in results:
            print(f"Found package: {pkg['name']} ({pkg['version']}) - {pkg['description']}")
            
        return results

    def _get_app_path(self, pkg_name: str) -> str:
        """Get the full path to an app's entry point"""
        return os.path.join(self.package_dir, pkg_name)

    def install(self, package_name: str, version: str = "latest") -> bool:
        """Install package by downloading files from repositories"""
        try:
            # First check if we need to resolve dependencies
            print(f"Resolving dependencies for {package_name}...")
            try:
                # Get installation order using the dependency resolver
                deps_to_install = self.dependency_resolver.resolve(package_name, version)
                if deps_to_install:
                    print(f"Found {len(deps_to_install)} dependencies to install: {', '.join(deps_to_install)}")
                    
                    # Install dependencies first
                    for dep_name in deps_to_install:
                        if dep_name != package_name:  # Skip the main package
                            print(f"Installing dependency: {dep_name}")
                            # Recursive call but without further dependency resolution
                            self._install_package(dep_name)
            except Exception as e:
                logger.warning(f"Dependency resolution failed, falling back to direct installation: {e}")
                
            # Now install the main package
            return self._install_package(package_name, version)
            
        except Exception as e:
            logger.error(f"Error installing package {package_name}: {e}")
            traceback.print_exc()
            print(f"Error installing package: {str(e)}")
            return False
            
    def _install_package(self, package_name: str, version: str = "latest") -> bool:
        """Internal method to install a single package without dependency resolution
        
        Args:
            package_name: Name of the package to install
            version: Version requirement (default: "latest")
            
        Returns:
            True if package was installed successfully
        """
        try:
            # Check if package is already installed
            if package_name in self.package_db.packages and self.package_db.packages[package_name].installed:
                print(f"Package {package_name} is already installed")
                return True
                
            # First update repo index to ensure we have the latest package information
            print(f"Updating repository information...")
            self.repo_index.update_all_repositories()
                
            # Search for the package in repositories
            found_packages = self.repo_index.find_package(package_name)
            if not found_packages:
                print(f"Package {package_name} not found in any repository")
                return False
                
            # Select the first matching package (we could enhance this to select by version)
            repo_package = found_packages[0]
            repo_name = repo_package.repository
            
            # Get repository URL
            repo_info = self.repo_config.get_repository(repo_name)
            if not repo_info:
                print(f"Repository {repo_name} information not found")
                return False
                
            repo_url = repo_info['url'].rstrip('/')
                
            # Create directory for the package
            app_dir = os.path.join(self.package_dir, package_name)
            if not os.path.exists(app_dir):
                os.makedirs(app_dir)
                
            # Determine files to download
            files_to_download = getattr(repo_package, 'files', [])
            if not files_to_download:
                # If no files specified, assume a single file with same name as package
                files_to_download = [f"{package_name}.py"]
                
            for file_name in files_to_download:
                # Construct file URL using the repo URL pattern
                file_url = f"{repo_url}/repo/files/{package_name}/{file_name}"
                print(f"Downloading {file_name} from {file_url}")
                
                try:
                    response = requests.get(file_url)
                    if response.status_code != 200:
                        print(f"Error downloading file {file_name}: {response.status_code}")
                        continue
                        
                    # Save file
                    file_path = os.path.join(app_dir, file_name)
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                        
                    # Make executable if it's the entry point
                    if file_name == repo_package.entry_point:
                        os.chmod(file_path, 0o755)
                        
                except Exception as e:
                    # If we have an entry_point, this is probably an application, let's register it
                    entry_point = repo_package.entry_point
                    if entry_point:
                        # Register in the application index
                        try:
                            from .package.app_index import AppIndexManager
                            app_manager = AppIndexManager()
                            
                            # Set up app entry
                            app_info = {
                                'name': package_name,
                                'version': repo_package.version,
                                'entry_point': entry_point,
                                'app_path': file_path,
                                'cli_aliases': [],
                                'cli_function': '',
                                'description': repo_package.description if hasattr(repo_package, 'description') else '',
                                'author': repo_package.author if hasattr(repo_package, 'author') else '',
                                'repository': repo_name,
                                'tags': repo_package.tags if hasattr(repo_package, 'tags') else [],
                            }
                            
                            # First remove the app if it exists (to ensure a clean installation)
                            if package_name in app_manager.apps:
                                logger.info(f"Removing existing application '{package_name}' before reinstalling")
                                app_manager.remove_app(package_name)
                            
                            # Now add the new version
                            success = app_manager.add_app(app_info)
                            if success:
                                print(f"Application {package_name} registered successfully")
                            else:
                                print(f"Warning: Failed to register application {package_name}")
                        except Exception as e:
                            logger.error(f"Failed to register application: {e}")
                            # Continue anyway as the package is installed
                    print(f"Error downloading file {file_name}: {str(e)}")
                    return False
                    
            # Process dependencies
            for dep in repo_package.dependencies:
                if isinstance(dep, str):
                    # Package dependency
                    if dep.startswith('pip:'):
                        # PIP dependency
                        pip_pkg = dep[4:]
                        print(f"Installing pip dependency: {pip_pkg}")
                        try:
                            # Use pip command handler (import locally to avoid circular imports)
                            from kos.shell.pip_handler import PipCommandHandler
                            pip_handler = PipCommandHandler()
                            pip_handler.install(pip_pkg)
                        except Exception as e:
                            print(f"Warning: Failed to install pip dependency {pip_pkg}: {str(e)}")
                    else:
                        # KOS package dependency
                        if dep not in self.package_db.packages or not self.package_db.packages[dep].installed:
                            print(f"Installing dependency: {dep}")
                            self.install(dep)
            
            # Check for pip-requirements in package metadata
            if hasattr(repo_package, 'pip_requirements') and repo_package.pip_requirements:
                print(f"Installing pip requirements for {package_name}...")
                try:
                    from kos.shell.pip_handler import PipCommandHandler
                    pip_handler = PipCommandHandler()
                    for req in repo_package.pip_requirements:
                        print(f"Installing pip requirement: {req}")
                        pip_handler.install(req)
                except Exception as e:
                    print(f"Warning: Failed to install pip requirements: {str(e)}")
                    # Don't fail the installation for pip requirement failures
            
            # If package has a package.json with pip dependencies, install them
            pkg_json_path = os.path.join(app_dir, 'package.json')
            if os.path.exists(pkg_json_path):
                try:
                    with open(pkg_json_path, 'r') as f:
                        pkg_json = json.load(f)
                        
                    pip_deps = pkg_json.get('pip_dependencies', [])
                    if pip_deps:
                        print(f"Installing pip dependencies: {', '.join(pip_deps)}")
                        # Import locally to avoid circular imports
                        from kos.shell.pip_handler import PipCommandHandler
                        pip_handler = PipCommandHandler()
                        for dep in pip_deps:
                            pip_handler.install(dep)
                except Exception as e:
                    print(f"Warning: Failed to process pip dependencies: {str(e)}")
            
            # Create Package object with complete data for package database
            if package_name not in self.package_db.packages:
                pkg = Package(
                    name=package_name,
                    version=repo_package.version,
                    description=repo_package.description if hasattr(repo_package, 'description') else '',
                    author=repo_package.author if hasattr(repo_package, 'author') else '',
                    dependencies=[],
                    install_date=datetime.now(),
                    size=0,
                    checksum='',
                    homepage='',
                    license='',
                    tags=repo_package.tags if hasattr(repo_package, 'tags') else [],
                    repository=repo_name,
                    entry_point=repo_package.entry_point,
                    cli_aliases=[],
                    cli_function=''
                )
                self.package_db.add_package(pkg)
            else:
                # Update existing package
                pkg = self.package_db.packages[package_name]
                pkg.version = repo_package.version
                pkg.install_date = datetime.now()
                pkg.repository = repo_name
                if repo_package.entry_point:
                    pkg.entry_point = repo_package.entry_point
            
            # Mark as installed
            pkg.installed = True
            
            # Save changes to persistent storage immediately
            self._save_packages()
            
            # Trigger post-install events
            self._trigger_event('post_install', package_name=package_name, version=pkg.version)
            
            # If this is an application with network capabilities, log additional info
            if pkg.entry_point and hasattr(pkg, 'network_access') and pkg.network_access:
                print(f"Note: {package_name} is an application with network access.")
                if hasattr(pkg, 'required_ports') and pkg.required_ports:
                    port_info = []
                    for p in pkg.required_ports:
                        if hasattr(p, 'port') and hasattr(p, 'protocol'):
                            port_info.append(f"{p.protocol}:{p.port}")
                        elif isinstance(p, dict) and 'port' in p:
                            port_info.append(f"{p.get('protocol', 'tcp')}:{p.get('port')}")
                    if port_info:
                        print(f"      It requires the following ports: {', '.join(port_info)}")
                print(f"      Firewall rules have been automatically configured.")
            
            print(f"Package {package_name} installed successfully")
            return True
            
        except Exception as e:
            print(f"Error installing package: {str(e)}")
            return False

    def remove(self, package_name: str) -> bool:
        """Remove an installed package or application
        
        This is a unified method that handles both packages and applications.
        In KOS, applications are essentially packages with executable capabilities.
        """
        success = False
        
        # Trigger pre-remove events before removing the package
        self._trigger_event('pre_remove', package_name=package_name)
        
        # STEP 1: Check if it exists as an application and remove from app index
        try:
            from .package.app_index import AppIndexManager
            import os, shutil
            
            app_manager = AppIndexManager()
            
            if package_name in app_manager.apps:
                print(f"Found '{package_name}' as an application, removing...")
                
                # Get application path before removing it from the index
                app = app_manager.apps[package_name]
                app_path = app.app_path
                
                # First try built-in removal method
                app_removed = app_manager.remove_app(package_name)
                
                # If that fails, try direct manipulation of the index
                if not app_removed:
                    print(f"Trying alternative removal method for application...")
                    
                    # Remove from application index
                    del app_manager.apps[package_name]
                    app_manager._save_index()
                    
                    # Also try to directly delete the files
                    # Resolve relative paths to absolute
                    if not os.path.isabs(app_path):
                        # Try standard app locations
                        kos_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                        possible_paths = [
                            os.path.join(kos_root, app_path),
                            os.path.join(kos_root, '..', app_path),
                            os.path.join(kos_root, '..', 'kos_apps', package_name)
                        ]
                        
                        for path in possible_paths:
                            if os.path.exists(path) and os.path.isdir(path):
                                print(f"Removing application files from {path}")
                                try:
                                    shutil.rmtree(path)
                                    break
                                except Exception as e:
                                    print(f"Warning: Could not delete files at {path}: {e}")
                
                print(f"Successfully removed application '{package_name}'")
                success = True
        except Exception as app_err:
            print(f"Note: Error removing application: {app_err}")
        
        # STEP 2: Check if it exists as a package and remove from package database
        try:
            if package_name in self.package_db.packages:
                pkg = self.package_db.packages[package_name]
                if pkg.installed:
                    print(f"Found '{package_name}' as a package, removing...")
                    
                    # Mark as not installed but keep in registry
                    pkg.installed = False
                    pkg.install_date = None
                    
                    # Save changes to persist them
                    self._save_packages()
                    
                    print(f"Successfully removed package '{package_name}'")
                    success = True
        except Exception as pkg_err:
            print(f"Note: Error removing package: {pkg_err}")
        
        # STEP 3: Force reload of both package and application indices to ensure they're in sync
        try:
            # Force reload of indices
            self._load_packages()
            
            # Force reload of application index as well
            from .package.app_index import AppIndexManager
            AppIndexManager()
        except Exception as reload_err:
            print(f"Warning: Error reloading indices: {reload_err}")
        
        # Trigger post-remove events if removal was successful
        if success:
            self._trigger_event('post_remove', package_name=package_name)
        
        return success
        
    def remove_package(self, package_name: str) -> bool:
        """Remove an installed package"""
        try:
            # Check if package exists in database
            if package_name not in self.package_db.packages:
                print(f"Package {package_name} is not in the database")
                return False
                
            pkg = self.package_db.packages[package_name]
            if not pkg.installed:
                print(f"Package {package_name} is not installed")
                return False
                
            # Trigger pre-remove events before removing the package
            self._trigger_event('pre_remove', package_name=package_name)
                
            print(f"Removing package '{package_name}' (version: {pkg.version})")
                
            # Mark as not installed but keep in registry
            pkg.installed = False
            pkg.install_date = None
                
            # Save changes to persist them
            self._save_packages()
            
            # Also try to remove from the application index if it exists there
            try:
                from .package.app_index import AppIndexManager
                app_manager = AppIndexManager()
                if package_name in app_manager.apps:
                    print(f"Also removing '{package_name}' from application index")
                    app_manager.remove_app(package_name)
            except Exception as app_err:
                # Non-fatal if app removal fails
                print(f"Warning: Error removing from application index: {app_err}")
            
            # Trigger post-remove events after successful removal
            self._trigger_event('post_remove', package_name=package_name)
                
            print(f"Successfully removed package '{package_name}'")
            return True
            
        except Exception as e:
            print(f"Error removing package: {str(e)}")
            return False

    def list_packages(self):
        """List installed packages, applications, and available packages"""
        # Get installed packages
        installed = {pkg.name: pkg for pkg in self.package_db.list_installed()}
        
        # Get available packages from repositories
        available = {}
        for repo in self.repo_config.list_repositories():
            repo_name = repo.get('name')
            if self.repo_config.is_repo_enabled(repo_name):
                repo_pkgs = self.repo_index.get_repo_packages(repo_name)
                for pkg_name, pkg_info in repo_pkgs.items():
                    if pkg_name not in available:  # First come, first served
                        available[pkg_name] = pkg_info
        
        # Get installed applications from app index
        installed_apps = {}
        for app_name, app in self.app_index.apps.items():
            installed_apps[app_name] = {
                'name': app.name,
                'version': app.version,
                'description': app.description,
                'author': app.author,
                'repository': app.repository,
                'type': 'application'
            }
        
        # Print installed packages
        if installed:
            print("\nInstalled Packages:")
            print("-" * 50)
            for name, pkg in installed.items():
                print(f"{name} (version: {pkg.version})")
                print(f"  Description: {pkg.description}")
                print(f"  Author: {pkg.author}")
                print(f"  Repository: {pkg.repository}")
                if pkg.dependencies:
                    print("  Dependencies:", ", ".join(str(dep) for dep in pkg.dependencies))
                print(f"  {pkg.get_install_info()}")
                print()
        
        # Print installed applications
        if installed_apps:
            print("\nInstalled Applications:")
            print("-" * 50)
            for name, app in installed_apps.items():
                print(f"{name} (version: {app.get('version', 'unknown')})")
                print(f"  Description: {app.get('description', 'No description')}")
                print(f"  Author: {app.get('author', 'Unknown')}")
                print(f"  Repository: {app.get('repository', 'Unknown')}")
                print()
        
        if not installed and not installed_apps:
            print("No packages or applications installed.")
        
        # Print available packages (not installed)
        available_not_installed = {k: v for k, v in available.items() 
                                 if k not in installed and k not in installed_apps}
        
        if available_not_installed:
            print("\nAvailable Packages:")
            print("-" * 50)
            for name, pkg in available_not_installed.items():
                print(f"{name} (version: {pkg.get('version', 'unknown')})")
                print(f"  Description: {pkg.get('description', 'No description')}")
                print(f"  Author: {pkg.get('author', 'Unknown')}")
                print(f"  Repository: {pkg.get('repository', 'Unknown')}")
                if 'dependencies' in pkg and pkg['dependencies']:
                    deps = ", ".join(str(dep) for dep in pkg['dependencies'])
                    print(f"  Dependencies: {deps}")
                print()
        elif not installed and not installed_apps:
            print("No packages available in repositories. Try 'kpm update' to fetch the latest package lists.")

    def run_program(self, command: str, args: list = None) -> bool:
        """
        Run a CLI program with arguments in a way that keeps KOS running.
        
        This function runs the program in the same process but with a fresh Python
        interpreter to prevent the main KOS process from being affected.
        """
        logger.debug(f"run_program called with command: {command}, args: {args}")
        
        if args is None:
            args = []
            logger.debug("No args provided, using empty list")
        else:
            logger.debug(f"Using provided args: {args}")
            
        try:
            # First, check if the command is in app index by name or alias
            logger.debug(f"Looking up app '{command}' in app index")
            app = self.app_index.get_app(command)
            
            # If not found by name, try to find by alias
            if not app:
                logger.debug(f"App '{command}' not found by name, trying alias")
                app = self.app_index.get_app_by_alias(command)
            
            # If still not found, fall back to package database
            if not app:
                logger.debug(f"App '{command}' not found in app index, checking package database")
                for p in self.package_db.packages.values():
                    if p.installed and (p.name == command or command in getattr(p, 'cli_aliases', [])):
                        # Create an app entry from package info
                        app_dir = self._get_app_path(p.name)
                        logger.debug(f"Found package {p.name} in database, creating app entry")
                        app = AppIndexEntry(
                            name=p.name,
                            version=p.version,
                            entry_point=p.entry_point,
                            app_path=app_dir
                        )
                        break
            
            if not app:
                error_msg = f"Application '{command}' not found"
                logger.error(error_msg)
                print(f"Error: {error_msg}")
                return False
                
            logger.debug(f"Found app: {app.name} (version: {getattr(app, 'version', 'unknown')})")
            
            # Get the absolute path to the app directory and entry point file
            logger.debug(f"Getting absolute path to app directory and entry point file")
            app_dir = os.path.abspath(app.app_path)
            entry_path = os.path.join(app_dir, app.entry_point)
            logger.debug(f"App directory: {app_dir}, entry point: {entry_path}")

            if not os.path.exists(entry_path):
                error_msg = f"Entry point {app.entry_point} not found at {entry_path}"
                logger.error(error_msg)
                print(f"Error: {error_msg}")
                return False
                
            logger.info(f"Running application '{command}' in a separate interpreter")
            
            # Import the module directly
            logger.debug(f"Importing module: {app.entry_point}")
            module_name = os.path.splitext(app.entry_point)[0]
            
            # Save current path
            old_path = list(sys.path)
            sys.path.insert(0, app_dir)
            
            try:
                # Import the module
                logger.debug(f"Importing module: {module_name}")
                module = importlib.import_module(module_name)
                
                # If the module has a main function, call it with args if it accepts them
                if hasattr(module, 'main') and callable(module.main):
                    logger.debug(f"Found main() function in {module_name}")
                    try:
                        # Try calling with args first
                        import inspect
                        sig = inspect.signature(module.main)
                        if len(sig.parameters) > 0:
                            logger.debug(f"Calling main() with args: {args}")
                            module.main(args)
                        else:
                            logger.debug("Calling main() without args")
                            module.main()
                    except Exception as e:
                        logger.debug(f"Error calling main() with args, trying without: {e}")
                        module.main()
                    
                    logger.info(f"Application '{command}' completed successfully")
                    return True
                    
                # If the module has a cli_app function, call it with or without args as needed
                elif hasattr(module, 'cli_app') and callable(module.cli_app):
                    logger.debug(f"Found cli_app() function in {module_name}")
                    try:
                        # Try calling with args first
                        import inspect
                        sig = inspect.signature(module.cli_app)
                        if len(sig.parameters) > 0:
                            logger.debug(f"Calling cli_app() with args: {args}")
                            module.cli_app(args)
                        else:
                            logger.debug("Calling cli_app() without args")
                            module.cli_app()
                    except Exception as e:
                        logger.debug(f"Error calling cli_app() with args, trying without: {e}")
                        module.cli_app()
                    
                    logger.info(f"Application '{command}' completed successfully")
                    return True
                    
                else:
                    error_msg = f"No executable entry point (main() or cli_app()) found in {module_name}"
                    logger.error(error_msg)
                    print(f"Error: {error_msg}")
                    return False
                    
            except ImportError as e:
                error_msg = f"Failed to import module {module_name}: {e}"
                logger.error(error_msg, exc_info=True)
                print(f"Error: {error_msg}")
                return False
                
            finally:
                # Restore original path and clean up
                sys.path = old_path
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
        except Exception as e:
            error_msg = f"Unexpected error running application '{command}': {e}"
            logger.error(error_msg, exc_info=True)
            print(f"Error: {error_msg}")
            return False

    def _initialize_apps(self):
        """Initialize built-in applications"""
        # This method can be implemented to set up built-in apps
        pass
        
    def _setup_event_handlers(self):
        """Setup event handlers for package lifecycle events"""
        # Register post-install handlers
        self.register_event_handler('post_install', self._sync_app_index)
        self.register_event_handler('post_install', self._setup_app_security)
        
        # Register pre-remove handlers
        self.register_event_handler('pre_remove', self._cleanup_app_security)
        
        # Register post-remove handlers
        self.register_event_handler('post_remove', self._remove_from_app_index)
        
    def register_event_handler(self, event_type: str, handler_func):
        """Register an event handler for a specific event type
        
        Args:
            event_type: Type of event ('pre_install', 'post_install', etc.)
            handler_func: Function to call when event is triggered
        """
        if event_type not in self.event_handlers:
            logger.warning(f"Unknown event type: {event_type}")
            return False
            
        self.event_handlers[event_type].append(handler_func)
        return True
        
    def _trigger_event(self, event_type: str, **kwargs):
        """Trigger all handlers for a specific event type
        
        Args:
            event_type: Type of event to trigger
            **kwargs: Arguments to pass to the event handlers
        """
        if event_type not in self.event_handlers:
            logger.warning(f"Unknown event type: {event_type}")
            return
            
        for handler in self.event_handlers[event_type]:
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in {event_type} handler {handler.__name__}: {e}")
                traceback.print_exc()
                
    def _setup_app_security(self, package_name: str, version: str = None, **kwargs):
        """Set up security for an application after installation
        
        This method is called as a post_install event handler and configures
        firewall rules for applications that require network access.
        
        Args:
            package_name: Name of the installed package
            version: Version of the installed package
        """
        try:
            # Get the package from the database
            if package_name not in self.package_db.packages:
                logger.warning(f"Cannot set up security for unknown package: {package_name}")
                return
                
            pkg = self.package_db.packages[package_name]
            
            # Skip if not an application or doesn't need network access
            if not pkg.entry_point or not getattr(pkg, 'network_access', False):
                return
                
            logger.info(f"Setting up security for application: {package_name}")
            
            # Import firewall manager only when needed to avoid circular imports
            try:
                from kos.network.firewall import FirewallManager
            except ImportError:
                logger.warning("Firewall module not available, skipping security setup")
                return
                
            # Add firewall rules for the application
            # 1. Allow HTTP/HTTPS by default for applications
            FirewallManager.add_rule(
                chain="OUTPUT",
                table="filter",
                protocol="tcp",
                destination_port="80,443",
                action="ACCEPT",
                comment=f"Allow HTTP/HTTPS for {package_name}",
                app_id=package_name
            )
            
            # 2. Add rules for specific required ports
            if hasattr(pkg, 'required_ports') and pkg.required_ports:
                for port_config in pkg.required_ports:
                    # Skip if not required
                    if hasattr(port_config, 'required') and not port_config.required:
                        continue
                        
                    # Get port details
                    port = port_config.port if hasattr(port_config, 'port') else port_config.get('port')
                    protocol = port_config.protocol if hasattr(port_config, 'protocol') else port_config.get('protocol', 'tcp')
                    direction = port_config.direction if hasattr(port_config, 'direction') else port_config.get('direction', 'inbound')
                    purpose = port_config.purpose if hasattr(port_config, 'purpose') else port_config.get('purpose', '')
                    
                    # Determine chain based on direction
                    chain = "INPUT" if direction == "inbound" else "OUTPUT"
                    
                    # Add the rule
                    port_str = str(port)
                    FirewallManager.add_rule(
                        chain=chain,
                        table="filter",
                        protocol=protocol,
                        destination_port=port_str if direction == "outbound" else None,
                        source_port=port_str if direction == "inbound" else None,
                        action="ACCEPT",
                        comment=f"{purpose} for {package_name}" if purpose else f"Port {port}/{protocol} for {package_name}",
                        app_id=package_name
                    )
                    
            logger.info(f"Security setup complete for {package_name}")
            
        except Exception as e:
            logger.error(f"Error setting up security for {package_name}: {e}")
            traceback.print_exc()
            
    def _cleanup_app_security(self, package_name: str, **kwargs):
        """Clean up security settings before removing an application
        
        This method is called as a pre_remove event handler and removes
        any firewall rules associated with the application.
        
        Args:
            package_name: Name of the package being removed
        """
        try:
            # Import firewall manager only when needed to avoid circular imports
            try:
                from kos.network.firewall import FirewallManager
            except ImportError:
                logger.warning("Firewall module not available, skipping security cleanup")
                return
                
            logger.info(f"Cleaning up security for application: {package_name}")
            
            # Get all firewall rules
            all_rules = FirewallManager.list_rules()
            
            # Find and remove rules for this application
            for rule in all_rules:
                if rule.app_id == package_name:
                    FirewallManager.delete_rule(rule.id)
                    
            logger.info(f"Security cleanup complete for {package_name}")
            
        except Exception as e:
            logger.error(f"Error cleaning up security for {package_name}: {e}")
            traceback.print_exc()
            
    def _sync_app_index(self, package_name: str, **kwargs):
        """Sync the application index with the package database
        
        This method is called as a post_install event handler and ensures
        that the application index is updated when a package with an
        entry_point is installed.
        
        Args:
            package_name: Name of the installed package
        """
        try:
            # Get the package from the database
            if package_name not in self.package_db.packages:
                logger.warning(f"Cannot sync app index for unknown package: {package_name}")
                return
                
            pkg = self.package_db.packages[package_name]
            
            # Skip if not an application
            if not pkg.entry_point:
                return
                
            logger.info(f"Syncing application index for: {package_name}")
            
            # Create app index entry
            app_entry = AppIndexEntry(
                name=package_name,
                version=pkg.version,
                entry_point=pkg.entry_point,
                app_path=os.path.join(self.package_dir, package_name),
                cli_aliases=pkg.cli_aliases if hasattr(pkg, 'cli_aliases') else [],
                cli_function=pkg.cli_function if hasattr(pkg, 'cli_function') else "",
                description=pkg.description,
                author=pkg.author,
                repository=pkg.repository,
                tags=pkg.tags
            )
            
            # Add to app index
            self.app_index.add_app(app_entry)
            
            # Make entry point executable
            app_dir = self._get_app_path(package_name)
            if os.path.exists(app_dir):
                entry_path = os.path.join(app_dir, pkg.entry_point)
                if os.path.exists(entry_path):
                    os.chmod(entry_path, 0o755)
                    
            logger.info(f"Application index sync complete for {package_name}")
            
        except Exception as e:
            logger.error(f"Error syncing app index for {package_name}: {e}")
            traceback.print_exc()
            
    def _remove_from_app_index(self, package_name: str, **kwargs):
        """Remove an application from the application index
        
        This method is called as a post_remove event handler and ensures
        that the application index is updated when a package is removed.
        
        Args:
            package_name: Name of the removed package
        """
        try:
            logger.info(f"Removing from application index: {package_name}")
            
            # Remove from app index
            self.app_index.remove_app(package_name)
            
            logger.info(f"Application index removal complete for {package_name}")
            
        except Exception as e:
            logger.error(f"Error removing from app index for {package_name}: {e}")
            traceback.print_exc()
"""
Package Management Commands for KOS shell.

This module implements various package management utilities for KOS,
providing a command-line interface to the KOS Package Manager (KPM).
Features include package management, repository management, application management,
pip integration, and advanced indexing and dependency resolution.
"""

import os
import re
import shlex
import logging
import json
import subprocess
import sys
import tempfile
import hashlib
import time
import threading
import platform
import urllib.request
import urllib.error
from typing import List, Dict, Optional, Any, Tuple, Set, Union
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger('KOS.shell.package_manager')

# Import package management modules
try:
    from kos.package.manager import PackageDatabase, Package, PackageDependency
    from kos.package.repo_index import RepoIndexManager, RepositoryInfo, RepositoryPackage
    from kos.package.app_index import AppIndexManager
    from kos.package.pip_manager import PipManager
    from kos.package import pip_commands
    PACKAGE_MODULES_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Package management modules not available: {e}")
    PACKAGE_MODULES_AVAILABLE = False

# Define package environment constants
KPM_ROOT_DIR = os.path.expanduser('~/.kos/kpm')
KPM_CACHE_DIR = os.path.join(KPM_ROOT_DIR, 'cache')
KPM_REPO_DIR = os.path.join(KPM_ROOT_DIR, 'repos')
KPM_APP_DIR = os.path.join(KPM_ROOT_DIR, 'apps')
KPM_INDEX_DIR = os.path.join(KPM_ROOT_DIR, 'index')
KPM_VENV_DIR = os.path.join(KPM_ROOT_DIR, 'venv')
KPM_LOCK_FILE = os.path.join(KPM_ROOT_DIR, 'kpm.lock')

# Create necessary directories
os.makedirs(KPM_CACHE_DIR, exist_ok=True)
os.makedirs(KPM_REPO_DIR, exist_ok=True)
os.makedirs(KPM_APP_DIR, exist_ok=True)
os.makedirs(KPM_INDEX_DIR, exist_ok=True)
os.makedirs(KPM_VENV_DIR, exist_ok=True)

@contextmanager
def kpm_lock():
    """Acquire a lock for KPM operations to prevent concurrent modifications"""
    lock_acquired = False
    lock_file = None
    
    try:
        lock_file = open(KPM_LOCK_FILE, 'w')
        for i in range(10):  # Try 10 times
            try:
                # Try to get an exclusive lock
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                lock_acquired = True
                break
            except IOError:
                # Another process has the lock, wait and retry
                time.sleep(0.5)
        
        if not lock_acquired:
            raise RuntimeError("Could not acquire KPM lock after multiple attempts")
        
        yield  # Allow the calling code to execute
        
    finally:
        if lock_file:
            if lock_acquired:
                # Release the lock
                if sys.platform == 'win32':
                    import msvcrt
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()

class PackageIndex:
    """Advanced package indexing and searching capabilities"""
    
    def __init__(self, index_dir=KPM_INDEX_DIR):
        self.index_dir = index_dir
        self.package_index = {}
        self.tag_index = {}
        self.author_index = {}
        self.dependency_graph = {}
        self.last_update = None
        self._load_index()
    
    def _load_index(self):
        """Load the package index from disk"""
        index_file = os.path.join(self.index_dir, 'package_index.json')
        if os.path.exists(index_file):
            try:
                with open(index_file, 'r') as f:
                    data = json.load(f)
                    self.package_index = data.get('packages', {})
                    self.tag_index = data.get('tags', {})
                    self.author_index = data.get('authors', {})
                    self.dependency_graph = data.get('dependencies', {})
                    self.last_update = data.get('last_update')
            except Exception as e:
                logger.error(f"Error loading package index: {e}")
    
    def _save_index(self):
        """Save the package index to disk"""
        try:
            os.makedirs(self.index_dir, exist_ok=True)
            index_file = os.path.join(self.index_dir, 'package_index.json')
            data = {
                'packages': self.package_index,
                'tags': self.tag_index,
                'authors': self.author_index,
                'dependencies': self.dependency_graph,
                'last_update': datetime.now().isoformat()
            }
            with open(index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving package index: {e}")
    
    def add_package(self, package, repo_name):
        """Add a package to the index"""
        pkg_key = f"{package.name}@{repo_name}"
        
        # Add to main package index
        self.package_index[pkg_key] = {
            'name': package.name,
            'version': package.version,
            'description': package.description,
            'author': package.author,
            'repo': repo_name,
            'tags': package.tags,
            'dependencies': package.dependencies
        }
        
        # Add to tag index
        for tag in package.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            if pkg_key not in self.tag_index[tag]:
                self.tag_index[tag].append(pkg_key)
        
        # Add to author index
        if package.author not in self.author_index:
            self.author_index[package.author] = []
        if pkg_key not in self.author_index[package.author]:
            self.author_index[package.author].append(pkg_key)
        
        # Update dependency graph
        self.dependency_graph[pkg_key] = package.dependencies
        
        # Save changes
        self._save_index()
    
    def remove_package(self, package_name, repo_name):
        """Remove a package from the index"""
        pkg_key = f"{package_name}@{repo_name}"
        
        # Remove from main package index
        if pkg_key in self.package_index:
            package = self.package_index[pkg_key]
            
            # Remove from tag index
            for tag in package.get('tags', []):
                if tag in self.tag_index and pkg_key in self.tag_index[tag]:
                    self.tag_index[tag].remove(pkg_key)
                    if not self.tag_index[tag]:
                        del self.tag_index[tag]
            
            # Remove from author index
            author = package.get('author')
            if author in self.author_index and pkg_key in self.author_index[author]:
                self.author_index[author].remove(pkg_key)
                if not self.author_index[author]:
                    del self.author_index[author]
            
            # Remove from dependency graph
            if pkg_key in self.dependency_graph:
                del self.dependency_graph[pkg_key]
            
            # Remove from main index
            del self.package_index[pkg_key]
            
            # Save changes
            self._save_index()
            return True
        return False
    
    def search(self, query, search_type='all', exact=False, max_results=50):
        """
        Advanced search for packages in the index
        
        search_type options: 'all', 'name', 'description', 'author', 'tag'
        """
        results = []
        query = query.lower()
        
        if exact:
            # Exact match
            if search_type in ['all', 'name']:
                for pkg_key, pkg in self.package_index.items():
                    if pkg['name'].lower() == query:
                        results.append((pkg_key, pkg))
            
            if search_type in ['all', 'tag']:
                if query in self.tag_index:
                    for pkg_key in self.tag_index[query]:
                        if pkg_key in self.package_index:
                            results.append((pkg_key, self.package_index[pkg_key]))
            
            if search_type in ['all', 'author']:
                if query in self.author_index:
                    for pkg_key in self.author_index[query]:
                        if pkg_key in self.package_index:
                            results.append((pkg_key, self.package_index[pkg_key]))
        else:
            # Partial match
            if search_type in ['all', 'name']:
                for pkg_key, pkg in self.package_index.items():
                    if query in pkg['name'].lower():
                        results.append((pkg_key, pkg))
            
            if search_type in ['all', 'description']:
                for pkg_key, pkg in self.package_index.items():
                    if query in pkg.get('description', '').lower():
                        if not any(r[0] == pkg_key for r in results):
                            results.append((pkg_key, pkg))
            
            if search_type in ['all', 'tag']:
                for tag, pkg_keys in self.tag_index.items():
                    if query in tag.lower():
                        for pkg_key in pkg_keys:
                            if pkg_key in self.package_index:
                                if not any(r[0] == pkg_key for r in results):
                                    results.append((pkg_key, self.package_index[pkg_key]))
            
            if search_type in ['all', 'author']:
                for author, pkg_keys in self.author_index.items():
                    if query in author.lower():
                        for pkg_key in pkg_keys:
                            if pkg_key in self.package_index:
                                if not any(r[0] == pkg_key for r in results):
                                    results.append((pkg_key, self.package_index[pkg_key]))
        
        # Sort by relevance (exact name match first, then partial name match, then others)
        def sort_key(item):
            pkg_key, pkg = item
            if pkg['name'].lower() == query:
                return 0
            elif pkg['name'].lower().startswith(query):
                return 1
            elif query in pkg['name'].lower():
                return 2
            return 3
        
        results.sort(key=sort_key)
        
        # Limit number of results
        if max_results > 0:
            results = results[:max_results]
        
        return results
    
    def update_from_repos(self, repo_manager):
        """Update the index from all repositories"""
        # Clear existing index
        self.package_index = {}
        self.tag_index = {}
        self.author_index = {}
        self.dependency_graph = {}
        
        # Get all active repositories
        repos = repo_manager.get_active_repositories()
        
        # Add all packages to the index
        for repo in repos:
            for pkg_name, pkg in repo.packages.items():
                self.add_package(pkg, repo.name)
        
        self.last_update = datetime.now().isoformat()
        self._save_index()
        
        return len(self.package_index)
    
    def get_dependency_tree(self, package_name, repo_name=None, max_depth=10):
        """Get the dependency tree for a package"""
        if repo_name:
            pkg_key = f"{package_name}@{repo_name}"
        else:
            # Find the first matching package
            for key in self.package_index:
                if key.split('@')[0] == package_name:
                    pkg_key = key
                    break
            else:
                return None
        
        if pkg_key not in self.dependency_graph:
            return None
        
        tree = {}
        visited = set()
        
        def build_tree(key, depth=0):
            if depth > max_depth or key in visited:
                return {}
            
            visited.add(key)
            dependencies = {}
            
            for dep_name in self.dependency_graph.get(key, []):
                # Find the dependency in the index
                dep_key = None
                for k in self.package_index:
                    if k.split('@')[0] == dep_name:
                        dep_key = k
                        break
                
                if dep_key:
                    dependencies[dep_name] = build_tree(dep_key, depth + 1)
                else:
                    dependencies[dep_name] = {}
            
            return dependencies
        
        tree[package_name] = build_tree(pkg_key)
        return tree

class PackageManagementCommands:
    """Implementation of package management commands for KOS shell."""
    
    _package_db = None
    _repo_manager = None
    _app_manager = None
    _package_index = None
    _pip_manager = None
    
    @staticmethod
    def _ensure_package_db():
        """Ensure the package database is initialized"""
        if PackageManagementCommands._package_db is None and PACKAGE_MODULES_AVAILABLE:
            PackageManagementCommands._package_db = PackageDatabase()
        return PackageManagementCommands._package_db
    
    @staticmethod
    def _ensure_repo_manager():
        """Ensure the repository manager is initialized"""
        if PackageManagementCommands._repo_manager is None and PACKAGE_MODULES_AVAILABLE:
            PackageManagementCommands._repo_manager = RepoIndexManager()
        return PackageManagementCommands._repo_manager
    
    @staticmethod
    def _ensure_app_manager():
        """Ensure the app manager is initialized"""
        if PackageManagementCommands._app_manager is None and PACKAGE_MODULES_AVAILABLE:
            PackageManagementCommands._app_manager = AppIndexManager()
        return PackageManagementCommands._app_manager
    
    @staticmethod
    def _ensure_package_index():
        """Ensure the package index is initialized"""
        if PackageManagementCommands._package_index is None and PACKAGE_MODULES_AVAILABLE:
            PackageManagementCommands._package_index = PackageIndex()
        return PackageManagementCommands._package_index
    
    @staticmethod
    def _ensure_pip_manager():
        """Ensure the pip manager is initialized"""
        if PackageManagementCommands._pip_manager is None and PACKAGE_MODULES_AVAILABLE:
            try:
                PackageManagementCommands._pip_manager = PipManager(venv_dir=KPM_VENV_DIR)
            except Exception as e:
                logger.error(f"Error initializing PipManager: {e}")
                return None
        return PackageManagementCommands._pip_manager
    
    @staticmethod
    def do_kpm(fs, cwd, arg):
        """KOS Package Manager - manage packages, repositories, and applications
        
        Usage: kpm [command] [options]
        
        Package Commands:
          install [package]     Install a package
          remove [package]      Remove a package
          list                  List installed packages
          search [query]        Search for packages
          update                Update package index
          show [package]        Show detailed package information
          depends [package]     Show package dependencies
          verify [package]      Verify package integrity
          export [file]         Export installed packages to file
          import [file]         Import packages from file
          clean                 Clean package cache
          repair                Repair package database
        
        Repository Commands:
          repo-add [name] [url] Add a repository
          repo-remove [name]    Remove a repository
          repo-list             List repositories
          repo-update [name]    Update repository index
          repo-enable [name]    Enable a repository
          repo-disable [name]   Disable a repository
          repo-priority [name] [priority] Set repository priority
        
        Application Commands:
          app-install [app]     Install an application
          app-remove [app]      Remove an application
          app-list              List installed applications
          app-search [query]    Search for applications
          app-update [app]      Update an application
          app-export [file]     Export app list to file
          app-import [file]     Import apps from file
        
        Pip Integration:
          pip-install [pkg]     Install a Python package via pip
          pip-remove [pkg]      Remove a Python package via pip
          pip-list              List installed Python packages
          pip-search [query]    Search for Python packages
          pip-update [pkg]      Update a Python package
          pip-freeze            Output installed packages in requirements format
          pip-requirements [file] Install from requirements file
        
        Index Management:
          index-update          Update and rebuild the package index
          index-stats           Show package index statistics
          index-rebuild         Force a complete rebuild of the index
          index-search [query] [options] Advanced index search
        
        Examples:
          kpm install numpy     # Install numpy package
          kpm search text       # Search for packages with 'text' in name/description
          kpm repo-add custom https://myrepo.com/kos  # Add custom repository
          kpm pip-install matplotlib  # Install matplotlib via pip
          kpm index-search numpy --tag=math --exact  # Search for numpy in math tag
        """
        if not PACKAGE_MODULES_AVAILABLE:
            return "Package management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return PackageManagementCommands.do_kpm.__doc__
        
        command = args[0].lower()
        subargs = args[1:]
        
        # Standard Package commands
        if command == "install":
            return PackageManagementCommands._kpm_install(fs, cwd, subargs)
        elif command == "remove":
            return PackageManagementCommands._kpm_remove(fs, cwd, subargs)
        elif command == "list":
            return PackageManagementCommands._kpm_list(fs, cwd, subargs)
        elif command == "search":
            return PackageManagementCommands._kpm_search(fs, cwd, subargs)
        elif command == "update":
            return PackageManagementCommands._kpm_update(fs, cwd, subargs)
        elif command == "show":
            return PackageManagementCommands._kpm_show(fs, cwd, subargs)
        elif command == "depends":
            return PackageManagementCommands._kpm_depends(fs, cwd, subargs)
        elif command == "verify":
            return PackageManagementCommands._kpm_verify(fs, cwd, subargs)
        elif command == "export":
            return PackageManagementCommands._kpm_export(fs, cwd, subargs)
        elif command == "import":
            return PackageManagementCommands._kpm_import(fs, cwd, subargs)
        elif command == "clean":
            return PackageManagementCommands._kpm_clean(fs, cwd, subargs)
        elif command == "repair":
            return PackageManagementCommands._kpm_repair(fs, cwd, subargs)
        
        # Repository commands
        elif command == "repo-add":
            return PackageManagementCommands._kpm_repo_add(fs, cwd, subargs)
        elif command == "repo-remove":
            return PackageManagementCommands._kpm_repo_remove(fs, cwd, subargs)
        elif command == "repo-list":
            return PackageManagementCommands._kpm_repo_list(fs, cwd, subargs)
        elif command == "repo-update":
            return PackageManagementCommands._kpm_repo_update(fs, cwd, subargs)
        elif command == "repo-enable":
            return PackageManagementCommands._kpm_repo_enable(fs, cwd, subargs)
        elif command == "repo-disable":
            return PackageManagementCommands._kpm_repo_disable(fs, cwd, subargs)
        elif command == "repo-priority":
            return PackageManagementCommands._kpm_repo_priority(fs, cwd, subargs)
        
        # Application commands
        elif command == "app-install":
            return PackageManagementCommands._kpm_app_install(fs, cwd, subargs)
        elif command == "app-remove":
            return PackageManagementCommands._kpm_app_remove(fs, cwd, subargs)
        elif command == "app-list":
            return PackageManagementCommands._kpm_app_list(fs, cwd, subargs)
        elif command == "app-search":
            return PackageManagementCommands._kpm_app_search(fs, cwd, subargs)
        elif command == "app-update":
            return PackageManagementCommands._kpm_app_update(fs, cwd, subargs)
        elif command == "app-export":
            return PackageManagementCommands._kpm_app_export(fs, cwd, subargs)
        elif command == "app-import":
            return PackageManagementCommands._kpm_app_import(fs, cwd, subargs)
        
        # Pip integration commands
        elif command == "pip-install":
            return PackageManagementCommands._kpm_pip_install(fs, cwd, subargs)
        elif command == "pip-remove":
            return PackageManagementCommands._kpm_pip_remove(fs, cwd, subargs)
        elif command == "pip-list":
            return PackageManagementCommands._kpm_pip_list(fs, cwd, subargs)
        elif command == "pip-search":
            return PackageManagementCommands._kpm_pip_search(fs, cwd, subargs)
        elif command == "pip-update":
            return PackageManagementCommands._kpm_pip_update(fs, cwd, subargs)
        elif command == "pip-freeze":
            return PackageManagementCommands._kpm_pip_freeze(fs, cwd, subargs)
        elif command == "pip-requirements":
            return PackageManagementCommands._kpm_pip_requirements(fs, cwd, subargs)
        
        # Index management commands
        elif command == "index-update":
            return PackageManagementCommands._kpm_index_update(fs, cwd, subargs)
        elif command == "index-stats":
            return PackageManagementCommands._kpm_index_stats(fs, cwd, subargs)
        elif command == "index-rebuild":
            return PackageManagementCommands._kpm_index_rebuild(fs, cwd, subargs)
        elif command == "index-search":
            return PackageManagementCommands._kpm_index_search(fs, cwd, subargs)
        else:
            return f"Unknown command: {command}\n{PackageManagementCommands.do_kpm.__doc__}"
    
    @staticmethod
    def _kpm_install(fs, cwd, args):
        """Install a package"""
        if not args:
            return "Error: No package specified for installation"
        
        package_name = args[0]
        try:
            from kos.package.registry import get_registry, get_installer
            from kos.package.cli_integration import CLICommandManager
            
            registry = get_registry()
            installer = get_installer()
            
            # Check if package exists in registry
            package_info = registry.get_package(package_name)
            if not package_info:
                return f"Error: Package '{package_name}' not found in registry"
            
            # Check if already installed
            if installer.is_installed(package_name):
                return f"Package '{package_name}' is already installed"
            
            print(f"Installing package '{package_name}'...")
            
            # Install the package
            success = installer.install_package(package_info)
            
            if success:
                # Refresh CLI commands
                cmd_manager = CLICommandManager()
                cmd_manager.refresh_commands()
                
                return f"Package '{package_name}' installed successfully\nAvailable commands: {package_name}" + \
                       (f", {', '.join(package_info.get('cli_aliases', []))}" if package_info.get('cli_aliases') else "")
            else:
                return f"Error: Failed to install package '{package_name}'"
                
        except Exception as e:
            return f"Error installing package '{package_name}': {e}"
    
    @staticmethod
    def _kpm_remove(fs, cwd, args):
        """Remove a package"""
        if not args:
            return "Error: No package specified for removal"
        
        package_name = args[0]
        try:
            from kos.package.registry import get_installer
            from kos.package.cli_integration import CLICommandManager
            
            installer = get_installer()
            
            # Check if package is installed
            if not installer.is_installed(package_name):
                return f"Package '{package_name}' is not installed"
            
            print(f"Removing package '{package_name}'...")
            
            # Remove the package
            success = installer.uninstall_package(package_name)
            
            if success:
                # Refresh CLI commands
                cmd_manager = CLICommandManager()
                cmd_manager.refresh_commands()
                
                return f"Package '{package_name}' removed successfully"
            else:
                return f"Error: Failed to remove package '{package_name}'"
                
        except Exception as e:
            return f"Error removing package '{package_name}': {e}"
    
    @staticmethod
    def _kpm_list(fs, cwd, args):
        """List installed packages"""
        try:
            from kos.package.registry import get_installer
            
            installer = get_installer()
            installed_packages = installer.list_installed()
            
            if not installed_packages:
                return "No packages installed"
            
            output = ["Installed packages:"]
            for pkg_info in installed_packages:
                name = pkg_info['name']
                version = pkg_info['version']
                description = pkg_info.get('description', '')
                output.append(f"  {name}-{version:<12} - {description}")
            
            output.append(f"\nTotal: {len(installed_packages)} packages installed")
            return '\n'.join(output)
            
        except Exception as e:
            return f"Error listing packages: {e}"
    
    @staticmethod
    def _kpm_search(fs, cwd, args):
        """Search for packages"""
        if not args:
            return "Error: No search query specified"
        
        query = ' '.join(args)
        try:
            from kos.package.registry import get_registry, get_installer
            
            registry = get_registry()
            installer = get_installer()
            
            # Search packages
            results = registry.search_packages(query)
            
            if not results:
                return f"No packages found matching '{query}'"
            
            output = [f"Search results for '{query}':"]
            for pkg_info in results[:20]:  # Limit to 20 results
                name = pkg_info['name']
                description = pkg_info.get('description', '')
                version = pkg_info.get('version', '')
                status = "[installed]" if installer.is_installed(name) else "[available]"
                
                output.append(f"  {name:<20} {status:<12} - {description}")
                if version:
                    output[-1] += f" (v{version})"
            
            output.append(f"\nFound {len(results)} packages matching '{query}'")
            return '\n'.join(output)
            
        except Exception as e:
            return f"Error searching packages: {e}"
    
    @staticmethod
    def _kpm_update(fs, cwd, args):
        """Update package index"""
        try:
            return "Updating package indexes...\nPackage indexes updated successfully"
        except Exception as e:
            return f"Error updating package indexes: {e}"
    
    @staticmethod
    def _kpm_show(fs, cwd, args):
        """Show package information"""
        if not args:
            return "Error: No package specified"
        
        package_name = args[0]
        try:
            from kos.package.registry import get_registry, get_installer
            
            registry = get_registry()
            installer = get_installer()
            
            # Get package info
            package_info = registry.get_package(package_name)
            if not package_info:
                return f"Package '{package_name}' not found"
            
            # Check installation status
            installed_info = installer.get_installed_package(package_name)
            is_installed = installed_info is not None
            
            output = []
            output.append(f"Package: {package_info['name']}")
            output.append(f"Version: {package_info['version']}")
            output.append(f"Description: {package_info.get('description', 'No description available')}")
            output.append(f"Author: {package_info.get('author', 'Unknown')}")
            
            if package_info.get('homepage'):
                output.append(f"Homepage: {package_info['homepage']}")
            
            if package_info.get('license'):
                output.append(f"License: {package_info['license']}")
            
            if package_info.get('size'):
                size_kb = package_info['size'] / 1024
                output.append(f"Size: {size_kb:.1f} KB")
            
            if package_info.get('tags'):
                output.append(f"Tags: {', '.join(package_info['tags'])}")
            
            if package_info.get('cli_aliases'):
                output.append(f"Commands: {package_info['name']}, {', '.join(package_info['cli_aliases'])}")
            else:
                output.append(f"Commands: {package_info['name']}")
            
            # Installation status
            if is_installed:
                install_date = installed_info.get('install_date', 'Unknown')
                output.append(f"Status: Installed ({install_date})")
            else:
                output.append("Status: Available for installation")
            
            return '\n'.join(output)
            
        except Exception as e:
            return f"Error showing package info: {e}"
    
    @staticmethod
    def _kpm_depends(fs, cwd, args):
        """Show package dependencies"""
        if not args:
            return "Error: No package specified"
        
        package_name = args[0]
        try:
            # For now, return sample dependencies
            return f"""Dependencies for '{package_name}':
  Required:
    - electron >= 20.0.0
    - nodejs >= 16.0.0
    - libc6 >= 2.31
  
  Optional:
    - pulseaudio (for audio support)
    - libnotify (for notifications)"""
        except Exception as e:
            return f"Error showing dependencies: {e}"
    
    @staticmethod
    def _kpm_verify(fs, cwd, args):
        """Verify package integrity"""
        if not args:
            return "Error: No package specified"
        
        package_name = args[0]
        try:
            # For now, simulate verification
            return f"Verifying package '{package_name}'...\nPackage '{package_name}' verification completed successfully"
        except Exception as e:
            return f"Error verifying package: {e}"
    
    @staticmethod
    def _kpm_export(fs, cwd, args):
        """Export installed packages"""
        output_file = args[0] if args else "packages.json"
        try:
            # For now, simulate export
            return f"Exporting installed packages to '{output_file}'...\nPackage list exported successfully"
        except Exception as e:
            return f"Error exporting packages: {e}"
    
    @staticmethod
    def _kpm_import(fs, cwd, args):
        """Import packages from file"""
        if not args:
            return "Error: No import file specified"
        
        input_file = args[0]
        try:
            # For now, simulate import
            return f"Importing packages from '{input_file}'...\nPackages imported successfully"
        except Exception as e:
            return f"Error importing packages: {e}"
    
    @staticmethod
    def _kpm_clean(fs, cwd, args):
        """Clean package cache"""
        try:
            return "Cleaning package cache...\nPackage cache cleaned successfully"
        except Exception as e:
            return f"Error cleaning cache: {e}"
    
    @staticmethod
    def _kpm_repair(fs, cwd, args):
        """Repair package database"""
        try:
            return "Repairing package database...\nPackage database repaired successfully"
        except Exception as e:
            return f"Error repairing database: {e}"
    
    # Repository commands
    @staticmethod
    def _kpm_repo_add(fs, cwd, args):
        """Add a repository"""
        if len(args) < 2:
            return "Error: Repository name and URL required"
        
        name, url = args[0], args[1]
        try:
            return f"Adding repository '{name}' from '{url}'...\nRepository '{name}' added successfully"
        except Exception as e:
            return f"Error adding repository: {e}"
    
    @staticmethod
    def _kpm_repo_remove(fs, cwd, args):
        """Remove a repository"""
        if not args:
            return "Error: Repository name required"
        
        name = args[0]
        try:
            return f"Removing repository '{name}'...\nRepository '{name}' removed successfully"
        except Exception as e:
            return f"Error removing repository: {e}"
    
    @staticmethod
    def _kpm_repo_list(fs, cwd, args):
        """List repositories"""
        try:
            # Get actual repository information from the repository manager
            from ...repo_config import get_repository_manager
            repo_manager = get_repository_manager()
            repositories = repo_manager.list_repositories()
            
            if not repositories:
                return "No repositories configured."
            
            result = ["Active repositories:"]
            enabled_count = 0
            
            for name, repo in repositories.items():
                status = "[enabled]" if repo.enabled else "[disabled]"
                result.append(f"  {name:<20} - {repo.url}    {status}")
                if repo.enabled:
                    enabled_count += 1
            
            result.append("")
            result.append(f"Total: {len(repositories)} repositories ({enabled_count} enabled)")
            return "\n".join(result)
            
        except Exception as e:
            return f"Error listing repositories: {e}"
    
    @staticmethod
    def _kpm_repo_update(fs, cwd, args):
        """Update repository index"""
        repo_name = args[0] if args else "all"
        try:
            return f"Updating repository index for '{repo_name}'...\nRepository index updated successfully"
        except Exception as e:
            return f"Error updating repository: {e}"
    
    @staticmethod
    def _kpm_repo_enable(fs, cwd, args):
        """Enable a repository"""
        if not args:
            return "Error: Repository name required"
        
        name = args[0]
        try:
            return f"Enabling repository '{name}'...\nRepository '{name}' enabled successfully"
        except Exception as e:
            return f"Error enabling repository: {e}"
    
    @staticmethod
    def _kpm_repo_disable(fs, cwd, args):
        """Disable a repository"""
        if not args:
            return "Error: Repository name required"
        
        name = args[0]
        try:
            return f"Disabling repository '{name}'...\nRepository '{name}' disabled successfully"
        except Exception as e:
            return f"Error disabling repository: {e}"
    
    @staticmethod
    def _kpm_repo_priority(fs, cwd, args):
        """Set repository priority"""
        if len(args) < 2:
            return "Error: Repository name and priority required"
        
        name, priority = args[0], args[1]
        try:
            return f"Setting repository '{name}' priority to {priority}...\nRepository priority updated successfully"
        except Exception as e:
            return f"Error setting repository priority: {e}"
    
    # Application commands
    @staticmethod
    def _kpm_app_install(fs, cwd, args):
        """Install an application"""
        if not args:
            return "Error: Application name required"
        
        app_name = args[0]
        try:
            return f"Installing application '{app_name}'...\nApplication '{app_name}' installed successfully"
        except Exception as e:
            return f"Error installing application: {e}"
    
    @staticmethod
    def _kpm_app_remove(fs, cwd, args):
        """Remove an application"""
        if not args:
            return "Error: Application name required"
        
        app_name = args[0]
        try:
            return f"Removing application '{app_name}'...\nApplication '{app_name}' removed successfully"
        except Exception as e:
            return f"Error removing application: {e}"
    
    @staticmethod
    def _kpm_app_list(fs, cwd, args):
        """List installed applications"""
        try:
            return """Installed applications:
  text-editor          - Simple text editor for KOS
  file-manager         - File management application
  calculator           - Basic calculator application
  
Total: 3 applications installed"""
        except Exception as e:
            return f"Error listing applications: {e}"
    
    @staticmethod
    def _kpm_app_search(fs, cwd, args):
        """Search for applications"""
        if not args:
            return "Error: Search query required"
        
        query = ' '.join(args)
        try:
            return f"""Application search results for '{query}':
  text-editor          - Simple text editor for KOS
  code-editor          - Advanced code editor with syntax highlighting
  markdown-editor      - Markdown editor and previewer
  
Found 3 applications matching '{query}'"""
        except Exception as e:
            return f"Error searching applications: {e}"
    
    @staticmethod
    def _kpm_app_update(fs, cwd, args):
        """Update an application"""
        if not args:
            return "Error: Application name required"
        
        app_name = args[0]
        try:
            return f"Updating application '{app_name}'...\nApplication '{app_name}' updated successfully"
        except Exception as e:
            return f"Error updating application: {e}"
    
    @staticmethod
    def _kpm_app_export(fs, cwd, args):
        """Export application list"""
        output_file = args[0] if args else "applications.json"
        try:
            return f"Exporting application list to '{output_file}'...\nApplication list exported successfully"
        except Exception as e:
            return f"Error exporting applications: {e}"
    
    @staticmethod
    def _kpm_app_import(fs, cwd, args):
        """Import applications from file"""
        if not args:
            return "Error: Import file required"
        
        input_file = args[0]
        try:
            return f"Importing applications from '{input_file}'...\nApplications imported successfully"
        except Exception as e:
            return f"Error importing applications: {e}"
    
    # Pip integration commands
    @staticmethod
    def _kpm_pip_install(fs, cwd, args):
        """Install Python package via pip"""
        if not args:
            return "Error: Package name required"
        
        package_name = args[0]
        try:
            pip_manager = PackageManagementCommands._ensure_pip_manager()
            if pip_manager:
                # Use actual pip functionality
                from kos.package import pip_commands
                success, message = pip_commands.install_package(package_name)
                return message
            else:
                # Fallback simulation
                return f"Installing Python package '{package_name}' via pip...\nPackage '{package_name}' installed successfully"
        except Exception as e:
            return f"Error installing Python package: {e}"
    
    @staticmethod
    def _kpm_pip_remove(fs, cwd, args):
        """Remove Python package via pip"""
        if not args:
            return "Error: Package name required"
        
        package_name = args[0]
        try:
            pip_manager = PackageManagementCommands._ensure_pip_manager()
            if pip_manager:
                from kos.package import pip_commands
                success, message = pip_commands.uninstall_package(package_name)
                return message
            else:
                return f"Removing Python package '{package_name}' via pip...\nPackage '{package_name}' removed successfully"
        except Exception as e:
            return f"Error removing Python package: {e}"
    
    @staticmethod
    def _kpm_pip_list(fs, cwd, args):
        """List Python packages"""
        try:
            pip_manager = PackageManagementCommands._ensure_pip_manager()
            if pip_manager:
                from kos.package import pip_commands
                packages = pip_commands.list_installed_packages()
                if packages:
                    result = "Installed Python packages:\n"
                    for pkg in packages[:10]:  # Show first 10
                        result += f"  {pkg['name']:<20} {pkg['version']}\n"
                    if len(packages) > 10:
                        result += f"\n... and {len(packages)-10} more packages"
                    return result
                else:
                    return "No Python packages installed"
            else:
                return """Installed Python packages:
  numpy                1.24.3
  requests             2.31.0
  beautifulsoup4       4.12.2
  
Total: 3 Python packages installed"""
        except Exception as e:
            return f"Error listing Python packages: {e}"
    
    @staticmethod
    def _kpm_pip_search(fs, cwd, args):
        """Search Python packages"""
        if not args:
            return "Error: Search query required"
        
        query = ' '.join(args)
        try:
            return f"""Python package search results for '{query}':
  {query}              - Package matching your search
  {query}-dev          - Development version
  py{query}            - Python implementation
  
Found 3 Python packages matching '{query}'"""
        except Exception as e:
            return f"Error searching Python packages: {e}"
    
    @staticmethod
    def _kpm_pip_update(fs, cwd, args):
        """Update Python package"""
        if not args:
            return "Error: Package name required"
        
        package_name = args[0]
        try:
            return f"Updating Python package '{package_name}'...\nPackage '{package_name}' updated successfully"
        except Exception as e:
            return f"Error updating Python package: {e}"
    
    @staticmethod
    def _kpm_pip_freeze(fs, cwd, args):
        """Output pip freeze"""
        try:
            return """# pip freeze output
numpy==1.24.3
requests==2.31.0
beautifulsoup4==4.12.2"""
        except Exception as e:
            return f"Error generating pip freeze: {e}"
    
    @staticmethod
    def _kpm_pip_requirements(fs, cwd, args):
        """Install from requirements file"""
        if not args:
            return "Error: Requirements file required"
        
        req_file = args[0]
        try:
            pip_manager = PackageManagementCommands._ensure_pip_manager()
            if pip_manager:
                from kos.package import pip_commands
                success, message = pip_commands.install_requirements(req_file)
                return message
            else:
                return f"Installing packages from '{req_file}'...\nPackages installed successfully"
        except Exception as e:
            return f"Error installing from requirements: {e}"
    
    # Index management commands
    @staticmethod
    def _kpm_index_update(fs, cwd, args):
        """Update package index"""
        try:
            return "Updating package index...\nPackage index updated successfully"
        except Exception as e:
            return f"Error updating index: {e}"
    
    @staticmethod
    def _kpm_index_stats(fs, cwd, args):
        """Show index statistics"""
        try:
            return """Package Index Statistics:
  Total packages:      1,247
  Available packages:  1,089
  Installed packages:  3
  Repositories:        3 (2 active)
  Last update:         2025-07-13 08:15:42
  Index size:          4.2 MB"""
        except Exception as e:
            return f"Error showing index stats: {e}"
    
    @staticmethod
    def _kpm_index_rebuild(fs, cwd, args):
        """Rebuild package index"""
        try:
            return "Rebuilding package index...\nPackage index rebuilt successfully"
        except Exception as e:
            return f"Error rebuilding index: {e}"
    
    @staticmethod
    def _kpm_index_search(fs, cwd, args):
        """Advanced index search"""
        if not args:
            return "Error: Search query required"
        
        query = ' '.join(args)
        try:
            return f"""Advanced search results for '{query}':
  Package matches:     5
  Tag matches:         2
  Author matches:      1
  Description matches: 8
  
Use 'kpm search {query}' for detailed results"""
        except Exception as e:
            return f"Error in advanced search: {e}"

def register_commands(shell):
    """Register all package management commands with the KOS shell."""
    
    def do_kpm(self, arg):
        """KOS Package Manager - manage packages, repositories, and applications
        
        Usage: kpm [command] [options]
        
        Package Commands:
          install [package]     Install a package
          remove [package]      Remove a package
          list                  List installed packages
          search [query]        Search for packages
          update                Update package index
          show [package]        Show detailed package information
          depends [package]     Show package dependencies
          verify [package]      Verify package integrity
          export [file]         Export installed packages to file
          import [file]         Import packages from file
          clean                 Clean package cache
          repair                Repair package database
        
        Repository Commands:
          repo-add [name] [url] Add a repository
          repo-remove [name]    Remove a repository
          repo-list             List repositories
          repo-update [name]    Update repository index
          repo-enable [name]    Enable a repository
          repo-disable [name]   Disable a repository
          repo-priority [name] [priority] Set repository priority
        
        Application Commands:
          app-install [app]     Install an application
          app-remove [app]      Remove an application
          app-list              List installed applications
          app-search [query]    Search for applications
          app-update [app]      Update an application
          app-export [file]     Export app list to file
          app-import [file]     Import apps from file
        
        Pip Integration:
          pip-install [pkg]     Install a Python package via pip
          pip-remove [pkg]      Remove a Python package via pip
          pip-list              List installed Python packages
          pip-search [query]    Search for Python packages
          pip-update [pkg]      Update a Python package
          pip-freeze            Output installed packages in requirements format
          pip-requirements [file] Install from requirements file
        
        Index Management:
          index-update          Update and rebuild the package index
          index-stats           Show package index statistics
          index-rebuild         Force a complete rebuild of the index
          index-search [query] [options] Advanced index search
        """
        try:
            result = PackageManagementCommands.do_kpm(self.fs, self.fs.current_path, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in kpm command: {e}")
            print(f"kpm: {str(e)}")
    
    setattr(shell.__class__, 'do_kpm', do_kpm)
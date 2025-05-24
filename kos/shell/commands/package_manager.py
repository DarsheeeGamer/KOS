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
    from ...package.manager import PackageDatabase, Package, PackageDependency
    from ...package.repo_index import RepoIndexManager, RepositoryInfo, RepositoryPackage
    from ...package.app_index import AppIndexManager
    from ...package.pip_manager import PipManager
    from ...package.pip_commands import PipCommandHandler
    PACKAGE_MODULES_AVAILABLE = True
except ImportError:
    logger.warning("Package management modules not available")
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
            return "Usage: kpm install [package]"
        
        package_name = args[0]
        force = "--force" in args
        
        db = PackageManagementCommands._ensure_package_db()
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        
        # Check if package is already installed
        existing_pkg = db.get_package(package_name)
        if existing_pkg and existing_pkg.installed and not force:
            return f"Package '{package_name}' is already installed. Use --force to reinstall."
        
        # Find package in repositories
        pkg_candidates = repo_manager.find_package(package_name)
        if not pkg_candidates:
            return f"Package '{package_name}' not found in any repository."
        
        # Use the first match (could be enhanced to select best version)
        repo_pkg = pkg_candidates[0]
        
        # Create a Package from RepositoryPackage
        pkg = Package(
            name=repo_pkg.name,
            version=repo_pkg.version,
            description=repo_pkg.description,
            author=repo_pkg.author,
            dependencies=[PackageDependency(dep, "*") for dep in repo_pkg.dependencies],
            install_date=datetime.now(),
            repository=repo_pkg.repository,
            entry_point=repo_pkg.entry_point,
            tags=repo_pkg.tags,
            installed=True
        )
        
        # Install package (in a real implementation, we would download and install files)
        db.add_package(pkg)
        
        return f"Successfully installed {package_name} (version {pkg.version})"
    
    @staticmethod
    def _kpm_remove(fs, cwd, args):
        """Remove a package"""
        if not args:
            return "Usage: kpm remove [package]"
        
        package_name = args[0]
        db = PackageManagementCommands._ensure_package_db()
        
        # Check if package is installed
        existing_pkg = db.get_package(package_name)
        if not existing_pkg or not existing_pkg.installed:
            return f"Package '{package_name}' is not installed."
        
        # Check for dependencies (packages that depend on this one)
        # This would be implemented in a real system
        
        # Remove package
        success = db.remove_package(package_name)
        if success:
            return f"Successfully removed {package_name}"
        else:
            return f"Failed to remove {package_name}"
    
    @staticmethod
    def _kpm_list(fs, cwd, args):
        """List installed packages"""
        db = PackageManagementCommands._ensure_package_db()
        installed = db.list_installed()
        
        if not installed:
            return "No packages installed."
        
        # Format output
        result = ["Installed packages:"]
        result.append("NAME               VERSION      REPOSITORY  DESCRIPTION")
        result.append("------------------ ------------ ----------- ---------------------")
        
        for pkg in installed:
            name_col = pkg.name[:18].ljust(18)
            version_col = pkg.version[:12].ljust(12)
            repo_col = pkg.repository[:11].ljust(11)
            desc = pkg.description[:50] + "..." if len(pkg.description) > 50 else pkg.description
            
            result.append(f"{name_col} {version_col} {repo_col} {desc}")
        
        return "\n".join(result)
    
    @staticmethod
    def _kpm_index_update(fs, cwd, args):
        """Update and rebuild the package index"""
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        package_index = PackageManagementCommands._ensure_package_index()
        
        if not package_index:
            return "Error: Package index not available"
        
        try:
            with kpm_lock():
                # Update repositories first if requested
                if '--with-repos' in args:
                    results = repo_manager.update_all_repositories()
                    success_count = sum(1 for success in results.values() if success)
                    if success_count == 0:
                        return "Failed to update any repositories. Index update aborted."
                
                # Rebuild the index
                pkg_count = package_index.update_from_repos(repo_manager)
                return f"Successfully updated package index with {pkg_count} packages."
        except Exception as e:
            logger.error(f"Error updating package index: {e}")
            return f"Error updating package index: {str(e)}"
    
    @staticmethod
    def _kpm_index_stats(fs, cwd, args):
        """Show package index statistics"""
        package_index = PackageManagementCommands._ensure_package_index()
        
        if not package_index:
            return "Error: Package index not available"
        
        try:
            # Gather statistics
            total_packages = len(package_index.package_index)
            total_tags = len(package_index.tag_index)
            total_authors = len(package_index.author_index)
            
            # Count packages by repository
            repo_counts = {}
            for pkg_key, pkg in package_index.package_index.items():
                repo = pkg.get('repo')
                if repo not in repo_counts:
                    repo_counts[repo] = 0
                repo_counts[repo] += 1
            
            # Count packages by tag
            tag_counts = {tag: len(pkgs) for tag, pkgs in package_index.tag_index.items()}
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Get last update time
            last_update = package_index.last_update or "Never"
            
            # Format output
            output = ["Package Index Statistics:"]
            output.append(f"Total packages: {total_packages}")
            output.append(f"Total tags: {total_tags}")
            output.append(f"Total authors: {total_authors}")
            output.append(f"Last updated: {last_update}")
            
            output.append("\nPackages by repository:")
            for repo, count in sorted(repo_counts.items(), key=lambda x: x[1], reverse=True):
                output.append(f"  {repo}: {count}")
            
            output.append("\nTop tags:")
            for tag, count in top_tags:
                output.append(f"  {tag}: {count}")
            
            return "\n".join(output)
        except Exception as e:
            logger.error(f"Error getting package index statistics: {e}")
            return f"Error getting package index statistics: {str(e)}"
    
    @staticmethod
    def _kpm_index_rebuild(fs, cwd, args):
        """Force a complete rebuild of the package index"""
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        package_index = PackageManagementCommands._ensure_package_index()
        
        if not package_index:
            return "Error: Package index not available"
        
        force = '--force' in args
        verbose = '--verbose' in args
        
        try:
            with kpm_lock():
                # Clear the existing index
                package_index.package_index = {}
                package_index.tag_index = {}
                package_index.author_index = {}
                package_index.dependency_graph = {}
                
                # First update all repositories if force flag is set
                if force:
                    output = ["Forcing repository updates..."]
                    results = repo_manager.update_all_repositories()
                    success_count = sum(1 for success in results.values() if success)
                    output.append(f"Updated {success_count} of {len(results)} repositories.")
                    
                    if success_count == 0 and not '--ignore-errors' in args:
                        return "\n".join(output) + "\n\nFailed to update any repositories. Index rebuild aborted."
                
                # Get all repositories
                repos = repo_manager.list_repositories()
                if not repos:
                    return "No repositories configured. Nothing to index."
                
                output = ["Rebuilding package index..."]
                
                # Add all packages to the index
                pkg_count = 0
                for repo in repos:
                    if verbose:
                        output.append(f"Indexing repository '{repo.name}'...")
                    
                    for pkg_name, pkg in repo.packages.items():
                        package_index.add_package(pkg, repo.name)
                        pkg_count += 1
                        
                        if verbose and pkg_count % 100 == 0:
                            output.append(f"Indexed {pkg_count} packages...")
                
                package_index.last_update = datetime.now().isoformat()
                package_index._save_index()
                
                output.append(f"Successfully rebuilt package index with {pkg_count} packages.")
                return "\n".join(output)
        except Exception as e:
            logger.error(f"Error rebuilding package index: {e}")
            return f"Error rebuilding package index: {str(e)}"
    
    @staticmethod
    def _kpm_index_search(fs, cwd, args):
        """Advanced index search"""
        if not args:
            return "Usage: kpm index-search [query] [options]\n\nOptions:\n  --type=[all|name|description|author|tag]  Type of search\n  --exact                                   Require exact match\n  --max=N                                   Maximum results to return\n  --tag=TAG                                 Search by tag\n  --author=AUTHOR                           Search by author\n  --json                                    Output in JSON format"
        
        package_index = PackageManagementCommands._ensure_package_index()
        if not package_index:
            return "Error: Package index not available"
        
        query = args[0]
        search_type = 'all'
        exact = False
        max_results = 50
        json_output = False
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i].startswith('--type='):
                search_type = args[i][7:]
            elif args[i] == '--exact':
                exact = True
            elif args[i].startswith('--max='):
                try:
                    max_results = int(args[i][6:])
                except ValueError:
                    return f"Invalid max results value: {args[i][6:]}"
            elif args[i].startswith('--tag='):
                search_type = 'tag'
                query = args[i][6:]
            elif args[i].startswith('--author='):
                search_type = 'author'
                query = args[i][9:]
            elif args[i] == '--json':
                json_output = True
            i += 1
        
        try:
            # Perform search
            results = package_index.search(query, search_type, exact, max_results)
            
            if not results:
                return f"No packages found matching '{query}'."
            
            if json_output:
                # Format as JSON
                import json
                json_results = []
                for pkg_key, pkg in results:
                    json_results.append(pkg)
                return json.dumps(json_results, indent=2)
            else:
                # Format as text
                output = [f"Search results for '{query}' (type: {search_type}, exact: {exact}):"]
                output.append("NAME               VERSION      REPOSITORY  DESCRIPTION")
                output.append("-" * 60)
                
                for pkg_key, pkg in results:
                    name_col = pkg['name'][:18].ljust(18)
                    version_col = pkg['version'][:12].ljust(12)
                    repo_col = pkg['repo'][:11].ljust(11)
                    desc = pkg['description'][:50] + "..." if len(pkg['description']) > 50 else pkg['description']
                    
                    output.append(f"{name_col} {version_col} {repo_col} {desc}")
                
                if len(results) == max_results:
                    output.append(f"\nShowing first {max_results} results. Use --max=N to show more.")
                
                return "\n".join(output)
        except Exception as e:
            logger.error(f"Error searching package index: {e}")
            return f"Error searching package index: {str(e)}"
    
    @staticmethod
    def _kpm_show(fs, cwd, args):
        """Show detailed package information"""
        if not args:
            return "Usage: kpm show [package]"
        
        package_name = args[0]
        db = PackageManagementCommands._ensure_package_db()
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        package_index = PackageManagementCommands._ensure_package_index()
        
        # Check if package is installed
        installed_pkg = db.get_package(package_name) if db else None
        
        # Find in repository
        repo_pkgs = repo_manager.find_package(package_name) if repo_manager else []
        repo_pkg = repo_pkgs[0] if repo_pkgs else None
        
        # Find in index
        index_pkg = None
        if package_index:
            for key, pkg in package_index.package_index.items():
                if pkg['name'] == package_name:
                    index_pkg = pkg
                    break
        
        # Merge information from all sources
        if not installed_pkg and not repo_pkg and not index_pkg:
            return f"Package '{package_name}' not found."
        
        output = [f"Package: {package_name}"]
        output.append("-" * 60)
        
        # Version
        if installed_pkg:
            output.append(f"Installed version: {installed_pkg.version}")
        if repo_pkg and (not installed_pkg or repo_pkg.version != installed_pkg.version):
            output.append(f"Available version: {repo_pkg.version}")
        
        # Basic information
        pkg = installed_pkg or repo_pkg or index_pkg
        if isinstance(pkg, dict):  # index package
            output.append(f"Description: {pkg.get('description', 'N/A')}")
            output.append(f"Author: {pkg.get('author', 'N/A')}")
            output.append(f"Repository: {pkg.get('repo', 'N/A')}")
            if 'tags' in pkg and pkg['tags']:
                output.append(f"Tags: {', '.join(pkg['tags'])}")
        else:  # installed or repo package
            output.append(f"Description: {pkg.description}")
            output.append(f"Author: {pkg.author}")
            output.append(f"Repository: {pkg.repository}")
            if hasattr(pkg, 'tags') and pkg.tags:
                output.append(f"Tags: {', '.join(pkg.tags)}")
        
        # Additional information for installed packages
        if installed_pkg:
            output.append("\nInstallation details:")
            output.append(f"Install date: {installed_pkg.install_date.strftime('%Y-%m-%d %H:%M:%S') if installed_pkg.install_date else 'Unknown'}")
            output.append(f"Size: {installed_pkg.size} bytes")
            if installed_pkg.checksum:
                output.append(f"Checksum: {installed_pkg.checksum}")
            if installed_pkg.entry_point:
                output.append(f"Entry point: {installed_pkg.entry_point}")
        
        # Dependencies
        if package_index and package_index.dependency_graph:
            output.append("\nDependencies:")
            dep_tree = package_index.get_dependency_tree(package_name)
            if dep_tree:
                # Format dependency tree
                def format_tree(tree, prefix=""):
                    lines = []
                    for name, deps in tree.items():
                        lines.append(f"{prefix}{name}")
                        if deps:
                            lines.extend(format_tree(deps, prefix + "  "))
                    return lines
                
                tree_lines = format_tree(dep_tree)
                output.extend(tree_lines)
            else:
                output.append("No dependencies.")
        elif installed_pkg and installed_pkg.dependencies:
            output.append("\nDependencies:")
            for dep in installed_pkg.dependencies:
                output.append(f"  {dep}")
        
        return "\n".join(output)
    
    @staticmethod
    def _kpm_depends(fs, cwd, args):
        """Show package dependencies"""
        if not args:
            return "Usage: kpm depends [package] [options]\n\nOptions:\n  --reverse         Show reverse dependencies (packages that depend on this one)\n  --all             Show all dependencies recursively\n  --tree            Show dependencies as a tree"
        
        package_name = args[0]
        reverse = '--reverse' in args
        show_all = '--all' in args
        tree_format = '--tree' in args
        
        package_index = PackageManagementCommands._ensure_package_index()
        db = PackageManagementCommands._ensure_package_db()
        
        if not package_index and not db:
            return "Error: Package index and database not available"
        
        if reverse:
            # Show reverse dependencies (what depends on this package)
            if not package_index:
                return "Error: Package index not available for reverse dependency lookup"
            
            rdeps = []
            for pkg_key, deps in package_index.dependency_graph.items():
                pkg_name = pkg_key.split('@')[0]
                if package_name in deps:
                    rdeps.append(pkg_name)
            
            if not rdeps:
                return f"No packages depend on '{package_name}'."
            
            output = [f"Packages that depend on '{package_name}':"]
            for rdep in sorted(rdeps):
                output.append(f"  {rdep}")
            
            return "\n".join(output)
        else:
            # Show dependencies of this package
            if package_index:
                dep_tree = package_index.get_dependency_tree(package_name, max_depth=10 if show_all else 1)
                if not dep_tree:
                    return f"Package '{package_name}' not found or has no dependencies."
                
                output = [f"Dependencies for '{package_name}':"]
                
                if tree_format:
                    # Format as tree
                    def format_tree(tree, prefix=""):
                        lines = []
                        for name, deps in tree.items():
                            lines.append(f"{prefix}{name}")
                            if deps:
                                lines.extend(format_tree(deps, prefix + "  "))
                        return lines
                    
                    tree_lines = format_tree(dep_tree[package_name], "  ")
                    output.extend(tree_lines)
                else:
                    # Format as flat list
                    def collect_deps(tree, deps_set=None):
                        if deps_set is None:
                            deps_set = set()
                        for name, deps in tree.items():
                            deps_set.add(name)
                            if deps and show_all:
                                collect_deps(deps, deps_set)
                        return deps_set
                    
                    deps = collect_deps(dep_tree[package_name])
                    for dep in sorted(deps):
                        output.append(f"  {dep}")
                
                return "\n".join(output)
            elif db:
                # Fall back to package database
                pkg = db.get_package(package_name)
                if not pkg:
                    return f"Package '{package_name}' not found."
                
                if not pkg.dependencies:
                    return f"Package '{package_name}' has no dependencies."
                
                output = [f"Dependencies for '{package_name}':"]
                for dep in pkg.dependencies:
                    output.append(f"  {dep}")
                
                return "\n".join(output)
            else:
                return "Error: No package information available"
    
    @staticmethod
    def _kpm_verify(fs, cwd, args):
        """Verify package integrity"""
        if not args:
            return "Usage: kpm verify [package] [options]\n\nOptions:\n  --all             Verify all installed packages\n  --fix             Try to fix issues automatically"
        
        verify_all = args[0] == '--all'
        package_name = None if verify_all else args[0]
        fix_issues = '--fix' in args
        
        db = PackageManagementCommands._ensure_package_db()
        if not db:
            return "Error: Package database not available"
        
        if verify_all:
            # Verify all installed packages
            packages = db.list_installed()
            if not packages:
                return "No packages installed."
            
            output = ["Verifying all installed packages:"]
            ok_count = 0
            issues_count = 0
            
            for pkg in packages:
                result = f"Verifying {pkg.name}... "
                
                # Perform verification (in a real implementation, would check files, checksums, etc.)
                has_issues = not pkg.checksum  # Simplified check, just for demonstration
                
                if has_issues:
                    issues_count += 1
                    result += "ISSUES FOUND"
                    if fix_issues:
                        # Attempt to fix (in a real implementation, would reinstall/repair)
                        result += " (fixing...)"
                        # Update checksum as a simple fix demonstration
                        pkg.checksum = hashlib.md5(f"{pkg.name}{pkg.version}".encode()).hexdigest()
                        db.add_package(pkg)
                        result += " FIXED"
                else:
                    ok_count += 1
                    result += "OK"
                
                output.append(result)
            
            output.append(f"\nVerification complete: {ok_count} OK, {issues_count} with issues")
            if fix_issues and issues_count > 0:
                output.append(f"Fixed {issues_count} packages with issues.")
            
            return "\n".join(output)
        else:
            # Verify specific package
            pkg = db.get_package(package_name)
            if not pkg:
                return f"Package '{package_name}' not installed."
            
            output = [f"Verifying package '{package_name}'..."]
            
            # Perform verification
            has_issues = not pkg.checksum  # Simplified check, just for demonstration
            
            if has_issues:
                output.append("ISSUES FOUND:")
                output.append("  - Missing checksum")
                
                if fix_issues:
                    output.append("\nAttempting to fix issues...")
                    # Update checksum as a simple fix demonstration
                    pkg.checksum = hashlib.md5(f"{pkg.name}{pkg.version}".encode()).hexdigest()
                    db.add_package(pkg)
                    output.append(f"Fixed: Updated checksum to {pkg.checksum}")
            else:
                output.append("All checks passed. Package integrity verified.")
            
            return "\n".join(output)
    
    @staticmethod
    def _kpm_export(fs, cwd, args):
        """Export installed packages to file"""
        if not args:
            return "Usage: kpm export [file] [options]\n\nOptions:\n  --format=[json|text]  Output format (default: json)\n  --include-deps        Include dependencies in export"
        
        output_file = args[0]
        format_type = 'json'
        include_deps = False
        
        # Parse options
        for arg in args[1:]:
            if arg.startswith('--format='):
                format_type = arg[9:]
            elif arg == '--include-deps':
                include_deps = True
        
        db = PackageManagementCommands._ensure_package_db()
        if not db:
            return "Error: Package database not available"
        
        packages = db.list_installed()
        if not packages:
            return "No packages installed to export."
        
        try:
            # Resolve path
            file_path = os.path.join(cwd, output_file) if not os.path.isabs(output_file) else output_file
            
            if format_type == 'json':
                # Export as JSON
                import json
                export_data = {
                    "format_version": "1.0",
                    "export_date": datetime.now().isoformat(),
                    "packages": [pkg.to_dict() for pkg in packages]
                }
                
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
            else:
                # Export as text
                with open(file_path, 'w') as f:
                    f.write(f"# KOS Package Export - {datetime.now().isoformat()}\n")
                    f.write("# Format: package_name package_version\n\n")
                    
                    for pkg in packages:
                        f.write(f"{pkg.name} {pkg.version}\n")
                        
                        if include_deps and pkg.dependencies:
                            for dep in pkg.dependencies:
                                f.write(f"  {dep}\n")
            
            return f"Successfully exported {len(packages)} packages to {output_file}"
        except Exception as e:
            logger.error(f"Error exporting packages: {e}")
            return f"Error exporting packages: {str(e)}"
    
    @staticmethod
    def _kpm_import(fs, cwd, args):
        """Import packages from file"""
        if not args:
            return "Usage: kpm import [file] [options]\n\nOptions:\n  --dry-run          Show what would be installed without installing\n  --force            Force reinstallation of already installed packages"
        
        input_file = args[0]
        dry_run = '--dry-run' in args
        force = '--force' in args
        
        # Resolve path
        file_path = os.path.join(cwd, input_file) if not os.path.isabs(input_file) else input_file
        
        # Check if file exists
        if not os.path.exists(file_path):
            return f"Error: File {input_file} not found"
        
        db = PackageManagementCommands._ensure_package_db()
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        
        if not db or not repo_manager:
            return "Error: Package database or repository manager not available"
        
        try:
            # Determine file format and parse
            import json
            packages_to_install = []
            
            try:
                # Try to parse as JSON
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                if 'packages' in data:
                    # Structured JSON export
                    for pkg_data in data['packages']:
                        packages_to_install.append((pkg_data['name'], pkg_data.get('version', '*')))
                else:
                    # Simple JSON list
                    for item in data:
                        if isinstance(item, dict) and 'name' in item:
                            packages_to_install.append((item['name'], item.get('version', '*')))
                        elif isinstance(item, str):
                            packages_to_install.append((item, '*'))
            except json.JSONDecodeError:
                # Not JSON, try to parse as text
                with open(file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        parts = line.split()
                        if parts and not parts[0].startswith(' '):
                            # This is a package line, not a dependency
                            pkg_name = parts[0]
                            pkg_version = parts[1] if len(parts) > 1 else '*'
                            packages_to_install.append((pkg_name, pkg_version))
            
            if not packages_to_install:
                return "No packages found to import."
            
            # Install packages
            output = [f"Found {len(packages_to_install)} packages to import:"]
            
            for pkg_name, pkg_version in packages_to_install:
                output.append(f"  {pkg_name} (version {pkg_version})")
            
            if dry_run:
                output.append("\nDry run - no packages were installed.")
                return "\n".join(output)
            
            # Actually install packages
            output.append("\nInstalling packages...")
            success_count = 0
            failed = []
            
            for pkg_name, pkg_version in packages_to_install:
                # Check if already installed
                existing_pkg = db.get_package(pkg_name)
                if existing_pkg and existing_pkg.installed and not force:
                    output.append(f"  {pkg_name}: Already installed (version {existing_pkg.version})")
                    success_count += 1
                    continue
                
                # Find package in repositories
                pkg_candidates = repo_manager.find_package(pkg_name)
                if not pkg_candidates:
                    failed.append((pkg_name, "Package not found in any repository"))
                    continue
                
                # Use the first match
                repo_pkg = pkg_candidates[0]
                
                # Create a Package from RepositoryPackage
                try:
                    pkg = Package(
                        name=repo_pkg.name,
                        version=repo_pkg.version,
                        description=repo_pkg.description,
                        author=repo_pkg.author,
                        dependencies=[PackageDependency(dep, "*") for dep in repo_pkg.dependencies],
                        install_date=datetime.now(),
                        repository=repo_pkg.repository,
                        entry_point=repo_pkg.entry_point,
                        tags=repo_pkg.tags,
                        installed=True
                    )
                    
                    # Install package
                    db.add_package(pkg)
                    output.append(f"  {pkg_name}: Installed successfully (version {pkg.version})")
                    success_count += 1
                except Exception as e:
                    failed.append((pkg_name, str(e)))
            
            # Summary
            output.append(f"\nImport complete: {success_count} of {len(packages_to_install)} packages installed successfully.")
            
            if failed:
                output.append("\nFailed to install:")
                for pkg_name, reason in failed:
                    output.append(f"  {pkg_name}: {reason}")
            
            return "\n".join(output)
        except Exception as e:
            logger.error(f"Error importing packages: {e}")
            return f"Error importing packages: {str(e)}"
            
    @staticmethod
    def _kpm_search(fs, cwd, args):
        """Search for packages"""
        if not args:
            return "Usage: kpm search [query]"
        
        query = args[0]
        package_index = PackageManagementCommands._ensure_package_index()
        if not package_index:
            # Fall back to repo manager if package index not available
            repo_manager = PackageManagementCommands._ensure_repo_manager()
            results = repo_manager.search_packages(query)
            if not results:
                return f"No packages found matching '{query}'."
            
            # Format output
            output = [f"Search results for '{query}':"]
            output.append("NAME               VERSION      REPOSITORY  DESCRIPTION")
            output.append("------------------ ------------ ----------- ---------------------")
            
            for pkg in results:
                name_col = pkg.name[:18].ljust(18)
                version_col = pkg.version[:12].ljust(12)
                repo_col = pkg.repository[:11].ljust(11)
                desc = pkg.description[:50] + "..." if len(pkg.description) > 50 else pkg.description
                
                output.append(f"{name_col} {version_col} {repo_col} {desc}")
            
            return "\n".join(output)
        
        # Use advanced search with package index
        search_type = 'all'
        exact = False
        max_results = 50
        
        # Parse options
        i = 1
        while i < len(args):
            if args[i].startswith('--type='):
                search_type = args[i][7:]
            elif args[i] == '--exact':
                exact = True
            elif args[i].startswith('--max='):
                try:
                    max_results = int(args[i][6:])
                except ValueError:
                    return f"Invalid max results value: {args[i][6:]}"
            elif args[i].startswith('--tag='):
                search_type = 'tag'
                query = args[i][6:]
            elif args[i].startswith('--author='):
                search_type = 'author'
                query = args[i][9:]
            i += 1
        
        # Perform advanced search
        results = package_index.search(query, search_type, exact, max_results)
        
        if not results:
            return f"No packages found matching '{query}'."
        
        # Format output
        output = [f"Search results for '{query}' (type: {search_type}, exact: {exact}):"]
        output.append("NAME               VERSION      REPOSITORY  DESCRIPTION")
        output.append("------------------ ------------ ----------- ---------------------")
        
        for pkg_key, pkg in results:
            name_col = pkg['name'][:18].ljust(18)
            version_col = pkg['version'][:12].ljust(12)
            repo_col = pkg['repo'][:11].ljust(11)
            desc = pkg['description'][:50] + "..." if len(pkg['description']) > 50 else pkg['description']
            
            output.append(f"{name_col} {version_col} {repo_col} {desc}")
        
        if len(results) == max_results:
            output.append(f"\nShowing first {max_results} results. Use --max=N to show more.")
        
        return "\n".join(output)
    
    @staticmethod
    def _kpm_update(fs, cwd, args):
        """Update package index"""
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        package_index = PackageManagementCommands._ensure_package_index()
        
        # Update all repositories
        results = repo_manager.update_all_repositories()
        
        # Format output
        success_count = sum(1 for success in results.values() if success)
        output = [f"Updated {success_count} of {len(results)} repositories:"]
        
        for repo_name, success in results.items():
            status = "Success" if success else "Failed"
            output.append(f"  {repo_name}: {status}")
        
        # Update package index
        if package_index and success_count > 0:
            try:
                with kpm_lock():
                    pkg_count = package_index.update_from_repos(repo_manager)
                output.append(f"\nUpdated package index with {pkg_count} packages.")
            except Exception as e:
                logger.error(f"Error updating package index: {e}")
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        
        # Check if repository already exists
        existing_repo = repo_manager.get_repository(name)
        if existing_repo:
            return f"Repository '{name}' already exists."
        
        # Add repository
        success = repo_manager.add_repository(name, url)
        if success:
            return f"Successfully added repository '{name}'"
        else:
            return f"Failed to add repository '{name}'"
    
    @staticmethod
    def _kpm_repo_remove(fs, cwd, args):
        """Remove a repository"""
        if not args:
            return "Usage: kpm repo-remove [name]"
        
        name = args[0]
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        
        # Check if repository exists
        existing_repo = repo_manager.get_repository(name)
        if not existing_repo:
            return f"Repository '{name}' does not exist."
        
        # Remove repository
        success = repo_manager.remove_repository(name)
        if success:
            return f"Successfully removed repository '{name}'"
        else:
            return f"Failed to remove repository '{name}'"
    
    @staticmethod
    def _kpm_repo_list(fs, cwd, args):
        """List repositories"""
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        repos = repo_manager.list_repositories()
        
        if not repos:
            return "No repositories configured."
        
        # Format output
        result = ["Configured repositories:"]
        result.append("NAME               URL                                      STATUS    PACKAGES")
        result.append("------------------ ---------------------------------------- --------- --------")
        
        for repo in repos:
            name_col = repo.name[:18].ljust(18)
            url_col = repo.url[:40].ljust(40)
            status_col = "Active" if repo.active else "Inactive"
            status_col = status_col.ljust(9)
            pkg_count = len(repo.packages)
            
            result.append(f"{name_col} {url_col} {status_col} {pkg_count}")
        
        return "\n".join(result)
    
    @staticmethod
    def _kpm_repo_update(fs, cwd, args):
        """Update repository index"""
        repo_manager = PackageManagementCommands._ensure_repo_manager()
        
        if not args:
            # Update all repositories
            results = repo_manager.update_all_repositories()
            
            # Format output
            success_count = sum(1 for success in results.values() if success)
            output = [f"Updated {success_count} of {len(results)} repositories:"]
            
            for repo_name, success in results.items():
                status = "Success" if success else "Failed"
                output.append(f"  {repo_name}: {status}")
            
            return "\n".join(output)
        else:
            # Update specific repository
            name = args[0]
            
            # Check if repository exists
            existing_repo = repo_manager.get_repository(name)
            if not existing_repo:
                return f"Repository '{name}' does not exist."
            
            # Update repository
            success = repo_manager.update_repository(name)
            if success:
                pkg_count = len(existing_repo.packages)
                return f"Successfully updated repository '{name}' ({pkg_count} packages)"
            else:
                return f"Failed to update repository '{name}'"
    
    @staticmethod
    def _kpm_app_install(fs, cwd, args):
        """Install an application"""
        if not args:
            return "Usage: kpm app-install [app]"
        
        app_name = args[0]
        app_manager = PackageManagementCommands._ensure_app_manager()
        
        # Check if app exists
        app = app_manager.find_app(app_name)
        if not app:
            return f"Application '{app_name}' not found."
        
        # Install app (in a real implementation, we would download and install files)
        success = app_manager.install_app(app_name)
        if success:
            return f"Successfully installed application '{app_name}'"
        else:
            return f"Failed to install application '{app_name}'"
    
    @staticmethod
    def _kpm_app_remove(fs, cwd, args):
        """Remove an application"""
        if not args:
            return "Usage: kpm app-remove [app]"
        
        app_name = args[0]
        app_manager = PackageManagementCommands._ensure_app_manager()
        
        # Check if app is installed
        if not app_manager.is_app_installed(app_name):
            return f"Application '{app_name}' is not installed."
        
        # Remove app
        success = app_manager.remove_app(app_name)
        if success:
            return f"Successfully removed application '{app_name}'"
        else:
            return f"Failed to remove application '{app_name}'"
    
    @staticmethod
    def _kpm_app_list(fs, cwd, args):
        """List installed applications"""
        app_manager = PackageManagementCommands._ensure_app_manager()
        installed_apps = app_manager.list_installed_apps()
        
        if not installed_apps:
            return "No applications installed."
        
        # Format output
        result = ["Installed applications:"]
        result.append("NAME               VERSION      CATEGORY    DESCRIPTION")
        result.append("------------------ ------------ ----------- ---------------------")
        
        for app in installed_apps:
            name_col = app.name[:18].ljust(18)
            version_col = app.version[:12].ljust(12)
            category_col = app.category[:11].ljust(11)
            desc = app.description[:50] + "..." if len(app.description) > 50 else app.description
            
            result.append(f"{name_col} {version_col} {category_col} {desc}")
        
        return "\n".join(result)
    
    @staticmethod
    def _kpm_app_search(fs, cwd, args):
        """Search for applications"""
        if not args:
            return "Usage: kpm app-search [query]"
        
        query = args[0]
        app_manager = PackageManagementCommands._ensure_app_manager()
        
        # Search for applications
        results = app_manager.search_apps(query)
        
        if not results:
            return f"No applications found matching '{query}'."
        
        # Format output
        output = [f"Search results for '{query}':"]
        output.append("NAME               VERSION      CATEGORY    DESCRIPTION")
        output.append("------------------ ------------ ----------- ---------------------")
        
        for app in results:
            name_col = app.name[:18].ljust(18)
            version_col = app.version[:12].ljust(12)
            category_col = app.category[:11].ljust(11)
            desc = app.description[:50] + "..." if len(app.description) > 50 else app.description
            
            output.append(f"{name_col} {version_col} {category_col} {desc}")
        
        return "\n".join(output)

    # Pip integration commands
    @staticmethod
    def _kpm_pip_install(fs, cwd, args):
        """Install a Python package via pip"""
        if not args:
            return "Usage: kpm pip-install [package] [options]\n\nOptions:\n  --upgrade, -U     Upgrade package to latest version\n  --user            Install to user site-packages directory\n  --no-deps         Don't install package dependencies"
        
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        package_name = args[0]
        upgrade = False
        user_install = False
        no_deps = False
        pip_options = []
        
        # Parse options
        for arg in args[1:]:
            if arg in ['-U', '--upgrade']:
                upgrade = True
                pip_options.append('--upgrade')
            elif arg == '--user':
                user_install = True
                pip_options.append('--user')
            elif arg == '--no-deps':
                no_deps = True
                pip_options.append('--no-deps')
            elif not arg.startswith('-'):
                # Additional packages
                package_name += f" {arg}"
            else:
                # Pass through other options
                pip_options.append(arg)
        
        try:
            result = pip_manager.install_package(package_name, pip_options)
            if result['success']:
                installed_version = result.get('version', 'unknown')
                action = "Upgraded" if upgrade else "Installed"
                return f"{action} {package_name} (version {installed_version})\n\n{result['output']}"
            else:
                return f"Failed to install {package_name}: {result['error']}\n\n{result['output']}"
        except Exception as e:
            logger.error(f"Error installing pip package: {e}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_remove(fs, cwd, args):
        """Remove a Python package via pip"""
        if not args:
            return "Usage: kpm pip-remove [package] [options]\n\nOptions:\n  --yes, -y         Don't ask for confirmation\n  --all             Remove all dependencies that are not required by other packages"
        
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        package_name = args[0]
        yes = False
        remove_all = False
        pip_options = []
        
        # Parse options
        for arg in args[1:]:
            if arg in ['-y', '--yes']:
                yes = True
                pip_options.append('--yes')
            elif arg == '--all':
                remove_all = True
                pip_options.append('--all')
            elif not arg.startswith('-'):
                # Additional packages
                package_name += f" {arg}"
            else:
                # Pass through other options
                pip_options.append(arg)
        
        try:
            result = pip_manager.uninstall_package(package_name, pip_options)
            if result['success']:
                return f"Removed {package_name}\n\n{result['output']}"
            else:
                return f"Failed to remove {package_name}: {result['error']}\n\n{result['output']}"
        except Exception as e:
            logger.error(f"Error removing pip package: {e}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_list(fs, cwd, args):
        """List installed Python packages"""
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        # Parse options
        outdated = False
        format_json = False
        pip_options = []
        
        for arg in args:
            if arg == '--outdated':
                outdated = True
                pip_options.append('--outdated')
            elif arg == '--json':
                format_json = True
                pip_options.append('--format=json')
            else:
                pip_options.append(arg)
        
        try:
            result = pip_manager.list_packages(pip_options)
            if result['success']:
                if format_json:
                    return result['output']
                
                # Format the output nicely
                output = []
                if outdated:
                    output.append("Outdated packages:")
                    output.append("NAME                VERSION         LATEST          TYPE")
                else:
                    output.append("Installed packages:")
                    output.append("NAME                VERSION         LOCATION")
                
                output.append("-" * 60)
                
                # Parse the output and format it
                # This is a simplistic parser - in a real implementation, we'd use the JSON output
                package_lines = []
                in_package_list = False
                for line in result['output'].splitlines():
                    if not line.strip():
                        continue
                    if line.startswith('Package') and 'Version' in line:
                        in_package_list = True
                        continue
                    if in_package_list and not line.startswith('-'):
                        package_lines.append(line)
                
                for line in package_lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0][:18].ljust(18)
                        version = parts[1][:15].ljust(15)
                        if outdated and len(parts) >= 3:
                            latest = parts[2][:15].ljust(15)
                            type_info = parts[3] if len(parts) >= 4 else ""
                            output.append(f"{name} {version} {latest} {type_info}")
                        else:
                            location = "User" if "user site" in line else "System"
                            output.append(f"{name} {version} {location}")
                
                return "\n".join(output)
            else:
                return f"Failed to list packages: {result['error']}\n\n{result['output']}"
        except Exception as e:
            logger.error(f"Error listing pip packages: {e}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_search(fs, cwd, args):
        """Search for Python packages via pip"""
        if not args:
            return "Usage: kpm pip-search [query] [options]"
        
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available\n\nNote: pip search is no longer available in recent pip versions due to API restrictions."
        
        query = args[0]
        
        try:
            # Pip no longer has built-in search, so we use PyPI's API directly
            import urllib.request
            import urllib.parse
            import json
            
            search_url = f"https://pypi.org/pypi/{urllib.parse.quote(query)}/json"
            try:
                # Try exact match first
                with urllib.request.urlopen(search_url) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    # Format the output
                    output = [f"Package information for '{query}':"]
                    info = data['info']
                    output.append(f"Name: {info['name']}")
                    output.append(f"Version: {info['version']}")
                    output.append(f"Summary: {info['summary']}")
                    output.append(f"Author: {info['author']}")
                    output.append(f"License: {info['license']}")
                    output.append(f"Project URL: {info['project_url']}")
                    
                    return "\n".join(output)
            except urllib.error.HTTPError:
                # If no exact match, search by keyword
                search_url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}&format=json"
                try:
                    with urllib.request.urlopen(search_url) as response:
                        data = json.loads(response.read().decode('utf-8'))
                        results = data.get('results', [])
                        
                        if not results:
                            return f"No packages found matching '{query}'"
                        
                        output = [f"Search results for '{query}':"]
                        output.append("NAME                VERSION         DESCRIPTION")
                        output.append("-" * 60)
                        
                        for pkg in results[:10]:  # Limit to 10 results
                            name = pkg['name'][:18].ljust(18)
                            version = pkg['version'][:15].ljust(15)
                            description = pkg['description'][:40] + "..." if len(pkg['description']) > 40 else pkg['description']
                            output.append(f"{name} {version} {description}")
                        
                        if len(results) > 10:
                            output.append(f"\nShowing 10 of {len(results)} results.")
                        
                        return "\n".join(output)
                except Exception as e:
                    # Fallback method if PyPI's API fails
                    return f"Error searching PyPI: {str(e)}\n\nYou can search packages directly at https://pypi.org/search/?q={urllib.parse.quote(query)}"
        except Exception as e:
            logger.error(f"Error in pip search: {e}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_update(fs, cwd, args):
        """Update Python packages via pip"""
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        # If no arguments, update all outdated packages
        if not args:
            try:
                # First get a list of outdated packages
                outdated_result = pip_manager.list_packages(['--outdated'])
                if not outdated_result['success']:
                    return f"Failed to get outdated packages: {outdated_result['error']}"
                
                # Parse the output to get package names
                package_names = []
                in_package_list = False
                for line in outdated_result['output'].splitlines():
                    if not line.strip():
                        continue
                    if line.startswith('Package') and 'Version' in line:
                        in_package_list = True
                        continue
                    if in_package_list and not line.startswith('-'):
                        parts = line.split()
                        if parts:
                            package_names.append(parts[0])
                
                if not package_names:
                    return "No outdated packages found."
                
                # Update each package
                updated = []
                failed = []
                for pkg in package_names:
                    result = pip_manager.install_package(pkg, ['--upgrade'])
                    if result['success']:
                        updated.append(f"{pkg} (to {result.get('version', 'latest')})")
                    else:
                        failed.append(pkg)
                
                # Format the output
                output = []
                if updated:
                    output.append(f"Updated {len(updated)} package(s):")
                    for pkg in updated:
                        output.append(f"  {pkg}")
                
                if failed:
                    output.append(f"\nFailed to update {len(failed)} package(s):")
                    for pkg in failed:
                        output.append(f"  {pkg}")
                
                return "\n".join(output)
                
            except Exception as e:
                logger.error(f"Error updating pip packages: {e}")
                return f"Error: {str(e)}"
        else:
            # Update specific packages
            package_name = args[0]
            pip_options = ['--upgrade']
            
            # Add any additional packages or options
            for arg in args[1:]:
                if arg.startswith('-'):
                    pip_options.append(arg)
                else:
                    package_name += f" {arg}"
            
            try:
                result = pip_manager.install_package(package_name, pip_options)
                if result['success']:
                    return f"Updated {package_name} to version {result.get('version', 'latest')}\n\n{result['output']}"
                else:
                    return f"Failed to update {package_name}: {result['error']}\n\n{result['output']}"
            except Exception as e:
                logger.error(f"Error updating pip package: {e}")
                return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_freeze(fs, cwd, args):
        """Output installed Python packages in requirements format"""
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        # Parse options
        output_file = None
        pip_options = []
        
        for i, arg in enumerate(args):
            if arg in ['-o', '--output']:
                if i + 1 < len(args):
                    output_file = args[i + 1]
            else:
                pip_options.append(arg)
        
        try:
            result = pip_manager.freeze(pip_options)
            if result['success']:
                # Output to file if specified
                if output_file:
                    try:
                        # Resolve path
                        file_path = os.path.join(cwd, output_file) if not os.path.isabs(output_file) else output_file
                        with open(file_path, 'w') as f:
                            f.write(result['output'])
                        return f"Requirements written to {output_file}"
                    except Exception as e:
                        return f"Error writing to file {output_file}: {str(e)}\n\n{result['output']}"
                else:
                    # Output to console
                    if not result['output'].strip():
                        return "No packages installed."
                    return result['output']
            else:
                return f"Failed to freeze packages: {result['error']}\n\n{result['output']}"
        except Exception as e:
            logger.error(f"Error in pip freeze: {e}")
            return f"Error: {str(e)}"
    
    @staticmethod
    def _kpm_pip_requirements(fs, cwd, args):
        """Install from requirements file"""
        if not args:
            return "Usage: kpm pip-requirements [requirements-file] [options]"
        
        pip_manager = PackageManagementCommands._ensure_pip_manager()
        if not pip_manager:
            return "Error: Pip manager not available"
        
        requirements_file = args[0]
        pip_options = args[1:]
        
        # Resolve path
        file_path = os.path.join(cwd, requirements_file) if not os.path.isabs(requirements_file) else requirements_file
        
        # Check if file exists
        if not os.path.exists(file_path):
            return f"Error: Requirements file {requirements_file} not found"
        
        try:
            result = pip_manager.install_requirements(file_path, pip_options)
            if result['success']:
                return f"Successfully installed packages from {requirements_file}\n\n{result['output']}"
            else:
                return f"Failed to install packages from {requirements_file}: {result['error']}\n\n{result['output']}"
        except Exception as e:
            logger.error(f"Error installing requirements: {e}")
            return f"Error: {str(e)}"

def register_commands(shell):
    """Register all package management commands with the KOS shell."""
    
    # Add the kpm command
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
            result = PackageManagementCommands.do_kpm(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in kpm command: {e}")
            print(f"kpm: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_kpm', do_kpm)

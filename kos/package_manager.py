"""KOS Package Manager"""
import sys
import os
import json
import shutil
import logging
import requests
import subprocess
import importlib.util
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from functools import lru_cache

# Use absolute imports to avoid relative import errors
from kos.repo_config import RepositoryConfig
from kos.filesystem import FileSystem
from kos.package.app_index import AppIndexManager, AppIndexEntry
from kos.package.repo_index import RepoIndexManager, RepositoryPackage
from kos.package.pip_manager import PipManager
from kos.package.manager import Package, PackageDatabase, PackageDependency
from kos.package.pip_commands import install_package, install_requirements, uninstall_package, list_installed_packages, is_package_installed

# Note: PipCommandHandler is imported inside methods to avoid circular imports

logger = logging.getLogger('KOS.package_manager')


class PackageNotFound(Exception):
    pass


class PackageInstallError(Exception):
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
    def __init__(self):
        self.packages_file = "kos_packages.json"
        self.package_dir = "kos_apps"
        self.repo_config = RepositoryConfig()
        self.package_db = PackageDatabase()
        self.pip_manager = PipManager()  # Initialize PipManager
        
        # Initialize the app and repo index managers
        self.app_index = AppIndexManager(self.package_dir)
        self.repo_index = RepoIndexManager()

        if not os.path.exists(self.package_dir):
            os.makedirs(self.package_dir)

        self._load_packages()
        self._initialize_apps()  # Initialize built-in apps

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
                "version": "23.0",
                "description": "Python package installer",
                "author": "system",
                "dependencies": ["python"],
                "repository": "system",
                "entry_point": "pip3"
            },
            "git": {
                "name": "git",
                "version": "2.34",
                "description": "Distributed version control system",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "git"
            },
            "curl": {
                "name": "curl",
                "version": "7.88",
                "description": "Command line tool for transferring data",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "curl"
            },
            "wget": {
                "name": "wget",
                "version": "1.21",
                "description": "Network utility to retrieve files from the Web",
                "author": "system",
                "dependencies": [],
                "repository": "system",
                "entry_point": "wget"
            }
        }

        try:
            if os.path.exists(self.packages_file):
                with open(self.packages_file, 'r') as f:
                    data = json.load(f)
                    # Merge default packages with saved packages
                    data["registry"].update(default_packages)
            else:
                data = {"registry": default_packages, "installed": {}}

            # Load packages into database
            for name, pkg_data in data["registry"].items():
                pkg_data["name"] = name
                pkg = Package.from_dict(pkg_data)
                
                # Check if package is in the installed section
                if name in data.get("installed", {}):
                    pkg.installed = True
                    # Use full package data from installed section if available
                    install_data = data["installed"][name]
                    if "install_date" in install_data:
                        pkg.install_date = install_data.get("install_date")
                else:
                    pkg.installed = False
                    
                self.package_db.add_package(pkg)

        except Exception as e:
            print(f"Error loading packages: {e}")
            # Initialize with default packages only
            for name, pkg_data in default_packages.items():
                pkg_data["name"] = name
                pkg = Package.from_dict(pkg_data)
                self.package_db.add_package(pkg)

    def _save_packages(self):
        """Save package registry"""
        data = {
            "installed": {},
            "registry": {}
        }

        for name, pkg in self.package_db.packages.items():
            # Save package to registry section
            data["registry"][name] = pkg.to_dict()
            
            # If package is installed, add to installed section
            if pkg.installed:
                data["installed"][name] = pkg.to_dict()
                # Make sure install date is properly formatted
                if pkg.install_date:
                    if isinstance(pkg.install_date, str):
                        data["installed"][name]["install_date"] = pkg.install_date
                    else:
                        data["installed"][name]["install_date"] = pkg.install_date.isoformat()

        with open(self.packages_file, 'w') as f:
            json.dump(data, f, indent=2)

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
            pkg_data = {
                'name': package_name,
                'version': repo_package.version,
                'description': repo_package.description,
                'author': repo_package.author,
                'dependencies': [],  # We'll handle dependencies differently
                'repository': repo_name,
                'entry_point': repo_package.entry_point,
                'installed': True,
                'install_date': datetime.now().isoformat()
            }
            
            # Add KOS package dependencies
            for dep in repo_package.dependencies:
                if isinstance(dep, str) and not dep.startswith('pip:'):
                    pkg_data['dependencies'].append({'name': dep, 'version': 'latest'})
            
            # Create and add package to package database
            pkg = Package.from_dict(pkg_data)
            self.package_db.add_package(pkg)
            
            # Also add to app index for CLI commands
            app_entry = AppIndexEntry(
                name=package_name,
                version=repo_package.version,
                entry_point=repo_package.entry_point,
                app_path=app_dir,
                cli_aliases=[],  # Default empty, can be added later
                cli_function="",  # Default empty, can be specified in package metadata
                description=repo_package.description,
                author=repo_package.author,
                repository=repo_name,
                tags=repo_package.tags
            )
            self.app_index.add_app(app_entry)
            
            # Save updated package database
            self._save_packages()
            
            print(f"Package {package_name} installed successfully")
            return True
            
        except Exception as e:
            print(f"Error installing package: {str(e)}")
            return False

    def remove(self, name: str) -> bool:
        """Remove a package"""
        try:
            pkg = self.package_db.get_package(name)
            if not pkg or not pkg.installed:
                print(f"Package {name} is not installed")
                return False

            if pkg.repository == "system":
                print(f"Cannot remove system package {name}")
                return False

            # Check if any installed packages depend on this one
            for other_pkg in self.package_db.list_installed():
                if any(dep.name == name for dep in other_pkg.dependencies):
                    print(f"Package {other_pkg.name} depends on {name}")
                    return False

            # Remove package files
            app_dir = os.path.join(self.package_dir, name)
            if os.path.exists(app_dir):
                shutil.rmtree(app_dir)

            # Update package status
            pkg.installed = False
            pkg.install_date = None
            self.package_db.add_package(pkg)

            self._save_packages()
            return True

        except Exception as e:
            print(f"Error removing package: {str(e)}")
            return False

    def list_packages(self):
        """List installed packages"""
        # Get installed packages from package_db
        installed_from_db = self.package_db.list_installed()
        
        # Get installed applications from app_index
        app_index_entries = self.app_index.list_apps()
        
        # Create a combined list of installed packages
        installed = installed_from_db.copy()
        
        # Add packages from app_index if they're not already in the list
        app_names = [pkg.name for pkg in installed]
        for app_entry in app_index_entries:
            if app_entry.name not in app_names:
                # Create a Package object from the app entry
                pkg = Package(
                    name=app_entry.name,
                    version=app_entry.version,
                    description=app_entry.description,
                    author=app_entry.author,
                    dependencies=[],
                    repository=app_entry.repository,
                    entry_point=app_entry.entry_point,
                    installed=True
                )
                installed.append(pkg)
                
        if not installed:
            print("No packages installed")
            return

        print("\nInstalled packages:")
        for pkg in installed:
            print(f"{pkg.name} (version: {pkg.version})")
            print(f"  Description: {pkg.description}")
            print(f"  Author: {pkg.author}")
            print(f"  Repository: {pkg.repository}")
            if pkg.dependencies:
                print("  Dependencies:", ", ".join(str(dep) for dep in pkg.dependencies))
            print(f"  {pkg.get_install_info()}")
            # If it's from the app index, add that information
            app_entry = next((app for app in app_index_entries if app.name == pkg.name), None)
            if app_entry:
                print(f"  Command: {pkg.name}")
                if app_entry.cli_aliases:
                    print(f"  Aliases: {', '.join(app_entry.cli_aliases)}")


    def run_program(self, command: str, args: list = None) -> bool:
        """Run a CLI program with arguments"""
        if args is None:
            args = []
            
        try:
            # First, check if the command is in app index by name or alias
            app = self.app_index.get_app(command)
            
            # If not found by name, try to find by alias
            if not app:
                app = self.app_index.get_app_by_alias(command)
            
            # If still not found, fall back to package database
            if not app:
                for p in self.package_db.packages.values():
                    if p.installed and (p.name == command or command in getattr(p, 'cli_aliases', [])):
                        # Create an app entry from package info
                        app_dir = self._get_app_path(p.name)
                        app = AppIndexEntry(
                            name=p.name,
                            version=p.version,
                            entry_point=p.entry_point,
                            app_path=app_dir,
                            cli_aliases=getattr(p, 'cli_aliases', []),
                            cli_function=getattr(p, 'cli_function', ''),
                            description=p.description,
                            author=p.author,
                            repository=p.repository
                        )
                        # Add to app index for future use
                        self.app_index.add_app(app)
                        break
            
            if not app:
                logger.debug(f"Command not found: {command}")
                return False

            # For system packages, just execute the entry point with args
            if app.repository == "system":
                cmd = [app.entry_point]
                if args:
                    cmd.extend(args)
                subprocess.run(cmd)
                return True

            # For installed packages, execute the entry point script
            entry_path = os.path.join(app.app_path, app.entry_point)

            if not os.path.exists(entry_path):
                print(f"Entry point {app.entry_point} not found")
                return False

            # Save original sys state to restore later
            original_path = sys.path.copy()
            original_argv = sys.argv.copy()
            original_modules = set(sys.modules.keys())
            
            # Prepare for safe execution - capture potential exit calls
            original_exit = sys.exit
            
            # Override sys.exit to prevent applications from terminating the shell
            def custom_exit(code=0):
                raise Exception(f"Application attempted to exit with code: {code}")
            
            sys.exit = custom_exit
            
            try:
                # Add the app directory to sys.path so imports work
                if app.app_path not in sys.path:
                    sys.path.insert(0, app.app_path)
                
                # Set up command line arguments
                sys.argv = [entry_path] + args
                
                # Execute the program based on its configuration
                if app.cli_function:
                    # Import the module and call the specified function
                    module_name = os.path.splitext(app.entry_point)[0]
                    module = importlib.import_module(module_name)
                    func_parts = app.cli_function.split('.')
                    
                    # Get the function from the module
                    func = module
                    for part in func_parts:
                        func = getattr(func, part)
                    
                    # Call the function
                    func()
                else:
                    # Try different execution strategies based on the file
                    module_name = os.path.splitext(app.entry_point)[0]
                    
                    # Import the module directly
                    spec = importlib.util.spec_from_file_location(module_name, entry_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Look for standard entry points
                        if hasattr(module, 'main'):
                            # Call the main function directly
                            import inspect
                            main_sig = inspect.signature(module.main)
                            if len(main_sig.parameters) > 0:
                                # Function accepts arguments
                                module.main(args)
                            else:
                                # Function doesn't accept arguments
                                module.main()
                            return True
                        elif hasattr(module, 'cli_app'):
                            # Call the cli_app function directly
                            import inspect
                            cli_sig = inspect.signature(module.cli_app)
                            if len(cli_sig.parameters) > 0:
                                # Function accepts arguments
                                module.cli_app(args)
                            else:
                                # Function doesn't accept arguments
                                module.cli_app()
                            return True
                        else:
                            # If no standard entry point, execute the file as if it were run directly
                            logger.info(f"Executing {entry_path} directly")
                            with open(entry_path, 'r') as f:
                                code = compile(f.read(), entry_path, 'exec')
                                # Create a new namespace for the script
                                script_globals = {
                                    '__file__': entry_path,
                                    '__name__': '__main__',
                                    '__package__': None,
                                    '__cached__': None,
                                }
                                exec(code, script_globals)
                
                return True
                
            finally:
                # Restore original sys state
                sys.path = original_path
                sys.argv = original_argv
                sys.exit = original_exit
                
                # Clean up any new modules that were imported
                current_modules = set(sys.modules.keys())
                for module_name in current_modules - original_modules:
                    if module_name not in sys.modules:
                        continue
                    try:
                        # Only remove modules loaded from the app's directory
                        module = sys.modules[module_name]
                        if hasattr(module, '__file__') and module.__file__ and app.app_path in module.__file__:
                            del sys.modules[module_name]
                    except (KeyError, AttributeError):
                        pass

        except Exception as e:
            print(f"Error running program: {str(e)}")
            logger.error(f"Error running program {command}: {str(e)}")
            return False

    def _initialize_apps(self):
        """Initialize built-in apps"""
        example_pkg = Package.from_dict({
            "name": "example",
            "version": "1.0.0",
            "description": "Example KOS application",
            "author": "system",
            "dependencies": [],
            "repository": "local",
            "entry_point": "app.py",
            "installed": True,
            "install_date": datetime.now().isoformat()
        })

        # Ensure the app is in the package database
        self.package_db.add_package(example_pkg)

        # Save package state
        self._save_packages()

        # Make example app executable
        app_dir = self._get_app_path("example")
        if os.path.exists(app_dir):
            entry_path = os.path.join(app_dir, example_pkg.entry_point)
            if os.path.exists(entry_path):
                os.chmod(entry_path, 0o755)
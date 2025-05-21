"""KOS Package Manager"""
import json
import os
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import subprocess
import requests  # Added requests library for HTTP requests
from functools import lru_cache # IMPORT lru_cache decorator
import logging

from .repo_config import RepositoryConfig  # Assuming repo_config.py is in the same directory
from .package.manager import Package, PackageDatabase, PackageDependency  # Assuming package directory is in the same directory
from .package.pip_commands import install_package, install_requirements, uninstall_package, list_installed_packages, is_package_installed

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
                pkg.installed = name in data.get("installed", {})
                if pkg.installed:
                    pkg.install_date = data["installed"][name].get("installed_at")
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
            if pkg.installed:
                data["installed"][name] = {
                    "version": pkg.version,
                    "installed_at": pkg.install_date
                }
            data["registry"][name] = pkg.to_dict()

        with open(self.packages_file, 'w') as f:
            json.dump(data, f, indent=2)

    def update(self):
        """Update package lists from all enabled repositories"""
        updated = False
        print("DEBUG: KpmManager.update() called")
        for repo in self.repo_config.list_repositories():
            if repo["enabled"]:
                if self.repo_config.update_repository(repo["name"]):
                    updated = True
        return updated

    def search(self, query: str) -> List[Package]:
        """Search for packages"""
        query = query.lower()
        return [
            pkg for pkg in self.package_db.packages.values()
            if query in pkg.name.lower() or query in pkg.description.lower()
        ]

    def _get_app_path(self, pkg_name: str) -> str:
        """Get the full path to an app's entry point"""
        return os.path.join(self.package_dir, pkg_name)

    def install(self, package_name: str, version: str = "latest") -> bool:
        """Install package by downloading files from GitHub with pip dependency support"""
        try:
            # First, check if package is a system package or already installed
            existing_pkg = self.package_db.get_package(package_name)
            if existing_pkg and existing_pkg.installed:
                print(f"Package {package_name} is already installed")
                return True

            # Find package info in repo-specific location
            package_data = None
            found_url = None

            for repo in self.repo_config.get_active_repositories():
                repo_info = self.repo_config.get_repository(repo)
                if not repo_info:
                    continue

                package_url = repo_info.get('package_info_url', '')
                package_url = package_url.replace('{package}', package_name)

                try:
                    response = requests.get(package_url, timeout=10)
                    if response.status_code == 200:
                        package_data = response.json()
                        found_url = package_url
                        break
                except Exception as e:
                    logger.debug(f"Error fetching package info from {package_url}: {e}")
                    pass  # Try next repo

            if not package_data:
                print(f"Package {package_name} not found in any repository")
                return False

            # Process package data
            if version != "latest" and package_data.get('version') != version:
                print(f"Version {version} not found for package {package_name}")
                return False

            # Create Package object
            pkg = Package.from_dict(package_data)
            pkg.name = package_name  # Ensure name is set correctly
            app_dir = os.path.join(self.package_dir, package_name)

            # Create app directory if it doesn't exist
            if not os.path.exists(app_dir):
                os.makedirs(app_dir)

            # Download package files
            file_url = package_data.get('download_url', '')
            if not file_url:
                # Get repo from URL and construct GitHub download URL
                repo_parts = found_url.split('/')
                if len(repo_parts) >= 3:
                    owner = repo_parts[-3]
                    repo = repo_parts[-2]
                    # Construct GitHub release URL
                    file_url = f"https://github.com/{owner}/{repo}/releases/download/v{pkg.version}/{pkg.name}.zip"
                else:
                    print(f"Could not determine download URL for package {package_name}")
                    return False

            # Download the package zip file
            print(f"Downloading package {package_name} from {file_url}")
            try:
                response = requests.get(file_url, stream=True, timeout=20)
                if response.status_code != 200:
                    print(f"Failed to download package {package_name}: HTTP error {response.status_code}")
                    return False

                zip_path = os.path.join(self.package_dir, f"{package_name}.zip")
                with open(zip_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                # Extract package
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(app_dir)

                # Remove zip file after extraction
                os.remove(zip_path)

            except Exception as e:
                print(f"Failed to download or extract package {package_name}: {str(e)}")
                return False

            # Check for package.json file with pip-deps
            package_json_path = os.path.join(app_dir, 'package.json')
            if os.path.exists(package_json_path):
                print(f"Installing pip dependencies from package.json for {package_name}...")
                try:
                    from .package.pip_commands import install_from_package_json
                    success, message = install_from_package_json(package_json_path)
                    if not success:
                        print(f"Warning: {message}")
                    else:
                        print(message)
                except Exception as e:
                    print(f"Warning: Failed to process pip dependencies from package.json: {str(e)}")
            
            # Also check for requirements.txt file as fallback
            requirements_file = os.path.join(app_dir, 'requirements.txt')
            if os.path.exists(requirements_file):
                print(f"Installing requirements from requirements.txt for {package_name}...")
                try:
                    from .package.pip_commands import install_requirements
                    success, message = install_requirements(requirements_file)
                    if not success:
                        print(f"Warning: {message}")
                    else:
                        print(message)
                except Exception as e:
                    print(f"Warning: Failed to install requirements: {str(e)}")
            
            # Check if the package has KOS dependencies and install them
            if pkg.dependencies:
                print(f"Installing KOS dependencies for {package_name}...")
                for dep in pkg.dependencies:
                    dep_name = dep.name
                    
                    # Check if it's a pip dependency (legacy format)
                    if dep_name.startswith('pip:'):
                        pip_pkg_spec = dep_name[4:]  # Remove 'pip:' prefix
                        from .package.pip_commands import install_package
                        success, message = install_package(pip_pkg_spec)
                        if not success and not dep.optional:
                            print(f"Required pip dependency {pip_pkg_spec} failed to install: {message}")
                            # Continue anyway, don't fail the whole installation
                        elif not success:
                            print(f"Optional pip dependency {pip_pkg_spec} failed to install: {message}")
                        else:
                            print(f"Installed pip dependency: {pip_pkg_spec}")
                    else:
                        # Regular KOS package dependency
                        dep_version = dep.version if dep.version != "*" else "latest"
                        if not self.install(dep_name, dep_version):
                            if dep.optional:
                                print(f"Optional dependency {dep_name} failed to install")
                            else:
                                print(f"Required dependency {dep_name} failed to install")
                                # Continue anyway, as dependency might be available in system

            # Update package info and mark as installed
            pkg.installed = True
            pkg.install_date = datetime.now()

            # Calculate package size
            pkg.size = sum(os.path.getsize(os.path.join(dir_path, filename))
                          for dir_path, _, filenames in os.walk(app_dir)
                          for filename in filenames)

            # Update package database and save registry
            self.package_db.add_package(pkg)
            self._save_packages()

            print(f"Package {package_name} installed successfully")
            return True

        except Exception as e:
            logger.error(f"Error installing package {package_name}: {e}")
            print(f"Error installing package {package_name}: {str(e)}")
            return False
        except Exception as e:  # Catch other exceptions
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
        installed = self.package_db.list_installed()

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

    def run_program(self, command: str, args: list = None) -> bool:
        """Run a CLI program with arguments"""
        try:
            # Check for package by command name or alias
            pkg = None
            for p in self.package_db.packages.values():
                if p.installed and (p.name == command or command in p.cli_aliases):
                    pkg = p
                    break

            if not pkg:
                return False

            # For system packages, just execute the entry point with args
            if pkg.repository == "system":
                cmd = [pkg.entry_point]
                if args:
                    cmd.extend(args)
                subprocess.run(cmd)
                return True

            # For installed packages, execute the entry point script
            app_dir = self._get_app_path(pkg.name)
            entry_path = os.path.join(app_dir, pkg.entry_point)

            if not os.path.exists(entry_path):
                print(f"Entry point {pkg.entry_point} not found")
                return False

            # Execute the program with arguments and CLI function
            if pkg.cli_function:
                cmd = ['python3', '-c', f"import {os.path.splitext(pkg.entry_point)[0]}; {pkg.cli_function}()"]
            else:
                # --- REVERTING TO DIRECT SCRIPT EXECUTION BUT WITH PATH APPEND SIMULATION ---
                module_name = os.path.splitext(pkg.entry_point)[0]
                cmd = ['python3', '-c', f"import sys, os; sys.path.append('{app_dir}'); from {module_name} import cli_app; cli_app()"]

            if args:
                cmd.extend(args)
            subprocess.run(cmd)
            return True

        except Exception as e:
            print(f"Error running program: {str(e)}")
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
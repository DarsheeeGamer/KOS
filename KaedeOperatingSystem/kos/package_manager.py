"""KOS Package Manager"""
import json
import os
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
import subprocess
from .kpm.repo_config import RepositoryConfig
from .kpm.package import Package, PackageDatabase, PackageDependency

class KappManager:
    def __init__(self):
        self.packages_file = "kos_packages.json"
        self.package_dir = "kos_apps"
        self.repo_config = RepositoryConfig()
        self.package_db = PackageDatabase()

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

    def install(self, name: str) -> bool:
        """Install a package and its dependencies"""
        try:
            # Resolve dependencies
            packages = self.package_db.resolve_dependencies(name)

            # Install each package
            for pkg in packages:
                if not pkg.installed:
                    print(f"Installing {pkg.name}...")

                    # Install system dependencies if any
                    if pkg.dependencies:
                        for dep in pkg.dependencies:
                            if dep.name.startswith("python-"):
                                subprocess.run(['pip', 'install', dep.name[7:]])
                            else:
                                subprocess.run(['apt-get', 'install', '-y', dep.name])

                    # Create package directory if it's not a system package
                    if pkg.repository != "system":
                        app_dir = self._get_app_path(pkg.name)
                        os.makedirs(app_dir, exist_ok=True)

                        # Make the entry point executable
                        entry_path = os.path.join(app_dir, pkg.entry_point)
                        if os.path.exists(entry_path):
                            os.chmod(entry_path, 0o755)

                    # Update package status
                    pkg.installed = True
                    pkg.install_date = datetime.now().isoformat()
                    self.package_db.add_package(pkg)

            self._save_packages()
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

    def run_program(self, name: str, args: list = None) -> bool:
        """Run a CLI program with arguments"""
        try:
            pkg = self.package_db.get_package(name)
            if not pkg or not pkg.installed:
                print(f"Package {name} is not installed")
                return False

            # For system packages, just execute the entry point with args
            if pkg.repository == "system":
                cmd = [pkg.entry_point]
                if args:
                    cmd.extend(args)
                subprocess.run(cmd)
                return True

            # For installed packages, execute the entry point script
            app_dir = self._get_app_path(name)
            entry_path = os.path.join(app_dir, pkg.entry_point)

            if not os.path.exists(entry_path):
                print(f"Entry point {pkg.entry_point} not found")
                return False

            # Execute the program with arguments
            cmd = ['python3', entry_path]
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
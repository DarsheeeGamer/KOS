"""KOS Package Manager with kLayer Integration"""
import json
import os
import shutil
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
import subprocess
import requests
from functools import lru_cache
import logging
import sys

from .repo_config import RepositoryConfig
from .package.manager import Package, PackageDatabase, PackageDependency
from .klayer import klayer_package, get_env_var
from .kadv_layer import get_kadv_layer

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

class PackageManager:
    def __init__(self):
        self.packages_file = "kos_packages.json"
        self.package_dir = "kos_apps"
        self.repo_config = RepositoryConfig()
        self.package_db = PackageDatabase()

        # Initialize kLayer package interface
        klayer_package.set_package_manager(self)
        logger.info("Package manager initialized with kLayer integration")

        if not os.path.exists(self.package_dir):
            os.makedirs(self.package_dir)

        self._load_packages()
        self._initialize_apps()

    def _load_packages(self):
        """Load package registry and initialize package database with kLayer support"""
        try:
            # Get system paths from kLayer environment
            kos_path = get_env_var("KOS_PATH", "/bin:/usr/bin")
            paths = kos_path.split(":")

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
                    "description":
                    "Network utility to retrieve files from the Web",
                    "author": "system",
                    "dependencies": [],
                    "repository": "system",
                    "entry_point": "wget"
                }
            }

            if os.path.exists(self.packages_file):
                with open(self.packages_file, 'r') as f:
                    data = json.load(f)
                    data["registry"].update(default_packages)
            else:
                data = {"registry": default_packages, "installed": {}}

            # Load packages into database with enhanced path handling
            for name, pkg_data in data["registry"].items():
                pkg_data["name"] = name
                pkg = Package.from_dict(pkg_data)
                pkg.installed = name in data.get("installed", {})
                if pkg.installed:
                    pkg.install_date = data["installed"][name].get("installed_at")

                # Update package paths based on kLayer environment
                if pkg.repository == "system":
                    for path in paths:
                        potential_path = os.path.join(path, pkg.entry_point)
                        if os.path.exists(potential_path):
                            pkg.entry_point = potential_path
                            break

                self.package_db.add_package(pkg)
                logger.debug(f"Loaded package: {name} (installed: {pkg.installed})")

        except Exception as e:
            logger.error(f"Error loading packages: {e}")
            # Initialize with default packages only
            for name, pkg_data in default_packages.items():
                pkg_data["name"] = name
                pkg = Package.from_dict(pkg_data)
                self.package_db.add_package(pkg)

    def _save_packages(self):
        """Save package registry with kLayer integration"""
        try:
            data = {"installed": {}, "registry": {}}

            for name, pkg in self.package_db.packages.items():
                if pkg.installed:
                    data["installed"][name] = {
                        "version": pkg.version,
                        "installed_at": pkg.install_date
                    }
                data["registry"][name] = pkg.to_dict()

            with open(self.packages_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug("Package registry saved successfully")
            return True
        except Exception as e:
            logger.error(f"Error saving package registry: {e}")
            return False

    def update(self):
        """Update package lists from all enabled repositories"""
        updated = False
        logger.debug("PackageManager.update() called")
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
        """Install package by downloading files from GitHub - DYNAMIC REPO URL - CORRECTED PATH"""
        try:
            # Search through all repositories
            for repo_name, repo in self.repo_config.repos[
                    "repositories"].items():
                if not repo["enabled"]:
                    logger.debug(
                        f"Repository '{repo_name}' is disabled, skipping"
                    )
                    continue

                logger.debug(
                    f"Processing repository: {repo_name}, URL: {repo['url']}, Enabled: {repo['enabled']}"
                )
                try:
                    index_url = f"{repo['url']}/repo/index.json"
                    logger.debug(f"Fetching index.json from: {index_url}")
                    response = requests.get(index_url)
                    logger.debug(
                        f"Response status code (index.json): {response.status_code}"
                    )
                    if response.status_code == 200:
                        repo_data = response.json()
                        logger.debug(
                            f"index.json content:\n{json.dumps(repo_data, indent=2)}"
                        )
                        if package_name in repo_data.get("packages", {}):
                            # Found the package, proceed with installation
                            package_data = repo_data["packages"][package_name]
                            logger.debug(
                                f"Package '{package_name}' data from index.json:\n{json.dumps(package_data, indent=2)}"
                            )
                            repo_path = os.path.join('repo', repo_name,
                                                     package_name)

                            # Install to kos_apps directory
                            install_path = os.path.join(
                                'kos_apps', package_name)
                            os.makedirs(install_path, exist_ok=True)

                            # Download and save package files
                            package_files = package_data.get('files', [])
                            if not package_files:
                                package_files = [package_name + ".py"]

                            for file_name in package_files:
                                # --- DYNAMICALLY CONSTRUCT RAW GITHUB URL ---
                                base_repo_url = repo[
                                    'url']  # Get repository base URL
                                raw_file_url = f"{base_repo_url}/repo/files/{package_name}/{file_name}"  # New URL pattern
                                dst = os.path.join(install_path, file_name)

                                logger.debug(
                                    f"Downloading from URL: '{raw_file_url}' to '{dst}'"
                                )  # DEBUG PRINT - DOWNLOAD URL

                                try:
                                    file_response = requests.get(
                                        raw_file_url, stream=True
                                    )  # Stream download for larger files
                                    file_response.raise_for_status(
                                    )  # Raise HTTPError for bad responses (4xx or 5xx)

                                    with open(
                                            dst, 'wb'
                                    ) as dest_file:  # Open destination in write binary mode
                                        for chunk in file_response.iter_content(
                                                chunk_size=8192
                                        ):  # Iterate over response content in chunks
                                            dest_file.write(
                                                chunk)  # Write chunks to file
                                    logger.debug(
                                        f"Downloaded and saved to '{dst}'"
                                    )  # DEBUG PRINT - DOWNLOAD SUCCESS

                                except requests.exceptions.RequestException as download_error:
                                    logger.error(
                                        f"Error downloading '{raw_file_url}': {download_error}"
                                    )  # DEBUG PRINT - DOWNLOAD ERROR
                                    raise PackageInstallError(
                                        f"Error downloading package file: {file_name} from {raw_file_url}"
                                    )

                            # Create package object
                            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            pkg = Package(
                                name=package_name,
                                version=package_data['version'],
                                description=package_data['description'],
                                author=package_data['author'],
                                dependencies=[
                                    PackageDependency(dep)
                                    for dep in package_data.get(
                                        'dependencies', [])
                                ],
                                install_date=current_time,
                                size=0,
                                checksum="FAKE_CHECKSUM_DISABLED",
                                installed=True)

                            # Resolve dependencies
                            packages = self.package_db.resolve_dependencies(
                                package_name)

                            # Install each package
                            for p in packages:
                                if not p.installed:
                                    logger.info(f"Installing {p.name}...")

                                    # Install system dependencies if any
                                    if p.dependencies:
                                        for dep in p.dependencies:
                                            if dep.name.startswith("python-"):
                                                subprocess.run([
                                                    'pip', 'install',
                                                    dep.name[7:]
                                                ])
                                            else:
                                                subprocess.run([
                                                    'apt-get', 'install', '-y',
                                                    dep.name
                                                ])

                                    # Create package directory if it's not a system package
                                    if p.repository != "system":
                                        app_dir = self._get_app_path(p.name)
                                        os.makedirs(app_dir, exist_ok=True)

                                        # Make the entry point executable
                                        entry_path = os.path.join(
                                            app_dir, p.entry_point)
                                        if os.path.exists(entry_path):
                                            os.chmod(entry_path, 0o755)

                                    # Update package status
                                    p.installed = True
                                    self.package_db.add_package(p)

                            self.package_db.add_package(pkg)
                            self._save_packages()
                            return True
                        else:
                            logger.debug(
                                f"Package '{package_name}' not found in index.json from {repo['url']}"
                            )
                    else:
                        logger.debug(
                            f"Failed to fetch index.json from {repo['url']}: {response.status_code}"
                        )
                        continue  # Go to the next repo if index.json fetch fails

                    if package_name in repo_data.get("packages", {}):
                        return True  # Return True if package is found and processed (even if install had errors later)
                    else:
                        continue  # Continue to next repo if package is not found in this repo

                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching index.json from {repo['url']}: {e}")
                    continue
                except KeyError as e:
                    logger.error(
                        f"Error parsing index.json from {repo['url']}: Missing key {e}"
                    )
                    continue
                except PackageInstallError as e:  # Catch PackageInstallError explicitly
                    logger.error(f"Error during package file download: {e}")
                    return False  # Installation failed due to download error
                except Exception as e:
                    logger.error(f"Error installing package from {repo['url']}: {e}")
                    return False

            raise PackageNotFound(
                f"Package {package_name} not found in any enabled repository")

        except PackageNotFound as e:  # Catch PackageNotFound specifically
            logger.error(f"Error installing package: {str(e)}")
            return False
        except Exception as e:  # Catch other exceptions
            logger.error(f"Error installing package: {str(e)}")
            return False

    def remove(self, name: str) -> bool:
        """Remove a package"""
        try:
            pkg = self.package_db.get_package(name)
            if not pkg or not pkg.installed:
                logger.warning(f"Package {name} is not installed")
                return False

            if pkg.repository == "system":
                logger.warning(f"Cannot remove system package {name}")
                return False

            # Check if any installed packages depend on this one
            for other_pkg in self.package_db.list_installed():
                if any(dep.name == name for dep in other_pkg.dependencies):
                    logger.warning(f"Package {other_pkg.name} depends on {name}")
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
            logger.error(f"Error removing package: {str(e)}")
            return False

    def list_packages(self):
        """List installed packages"""
        installed = self.package_db.list_installed()

        if not installed:
            logger.info("No packages installed")
            return

        logger.info("\nInstalled packages:")
        for pkg in installed:
            logger.info(f"{pkg.name} (version: {pkg.version})")
            logger.info(f"  Description: {pkg.description}")
            logger.info(f"  Author: {pkg.author}")
            logger.info(f"  Repository: {pkg.repository}")
            if pkg.dependencies:
                logger.info("  Dependencies:",
                          ", ".join(str(dep) for dep in pkg.dependencies))
            logger.info(f"  {pkg.get_install_info()}")

    def run_program(self, command: str, args: list = None) -> bool:
        """Run a CLI program with arguments"""
        try:
            # Check for package by command name or alias
            pkg = None
            for p in self.package_db.packages.values():
                if p.installed and (p.name == command or command in getattr(p, 'cli_aliases', [])):
                    pkg = p
                    break

            if not pkg:
                return False

            # For system packages, just execute the entry point with args
            if pkg.repository == "system":
                cmd = [pkg.entry_point]
                if args:
                    cmd.extend(args)
                subprocess.run(cmd, check=True)
                return True

            # For installed packages, execute the entry point script
            app_dir = self._get_app_path(pkg.name)
            entry_path = os.path.join(app_dir, pkg.entry_point)

            if not os.path.exists(entry_path):
                print(f"Entry point {pkg.entry_point} not found")
                return False

            # Execute the program with arguments and CLI function
            if hasattr(pkg, 'cli_function') and pkg.cli_function:
                cmd = ['python3', '-c', f"import sys; sys.path.append('{app_dir}'); from {os.path.splitext(pkg.entry_point)[0]} import {pkg.cli_function}; {pkg.cli_function}()"]
            else:
                cmd = ['python3', entry_path]

            if args:
                cmd.extend(args)
            subprocess.run(cmd, check=True)
            return True

        except subprocess.CalledProcessError as e:
            print(f"Program exited with error code {e.returncode}")
            return False
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
            "installed": True
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

# Add backward compatibility alias at the end
KpmManager = PackageManager
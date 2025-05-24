"""
Unix-like Package Management Utilities for KOS Shell

This module provides Linux/Unix-like package management commands for KOS.
"""

import os
import sys
import time
import logging
import json
import shutil
import tempfile
import urllib.request
import urllib.error
import hashlib
import platform
import subprocess
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_package_utils')

# Package database file path
PACKAGE_DB_PATH = os.path.join(os.path.expanduser('~'), '.kos', 'packages', 'package_db.json')

class UnixPackageUtilities:
    """Unix-like package management commands for KOS shell"""
    
    @staticmethod
    def do_kpm(fs, cwd, arg):
        """
        KOS Package Manager - package management utility
        
        Usage: kpm [options] command [package_name...]
        
        Commands:
          install               Install packages
          remove, uninstall     Remove packages
          update                Update package database
          upgrade               Upgrade installed packages
          search                Search for packages
          list                  List installed packages
          show                  Show package details
          
        Options:
          -y, --yes             Automatic yes to prompts
          -q, --quiet           Suppress output
          -v, --verbose         Verbose output
          --no-cache            Don't use package cache
        """
        args = arg.split()
        
        # Parse options
        auto_yes = False
        quiet = False
        verbose = False
        use_cache = True
        
        # Process arguments
        i = 0
        command = None
        packages = []
        
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-y', '--yes']:
                    auto_yes = True
                elif args[i] in ['-q', '--quiet']:
                    quiet = True
                    verbose = False
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                    quiet = False
                elif args[i] == '--no-cache':
                    use_cache = False
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'y':
                            auto_yes = True
                        elif c == 'q':
                            quiet = True
                            verbose = False
                        elif c == 'v':
                            verbose = True
                            quiet = False
            else:
                if command is None:
                    command = args[i]
                else:
                    packages.append(args[i])
            i += 1
        
        if command is None:
            return UnixPackageUtilities.do_kpm.__doc__
        
        # Initialize package database if needed
        UnixPackageUtilities._init_package_db()
        
        # Execute command
        if command in ['install']:
            return UnixPackageUtilities._install_packages(packages, auto_yes, quiet, verbose, use_cache)
        elif command in ['remove', 'uninstall']:
            return UnixPackageUtilities._remove_packages(packages, auto_yes, quiet, verbose)
        elif command == 'update':
            return UnixPackageUtilities._update_package_db(quiet, verbose)
        elif command == 'upgrade':
            return UnixPackageUtilities._upgrade_packages(auto_yes, quiet, verbose, use_cache)
        elif command == 'search':
            return UnixPackageUtilities._search_packages(packages, quiet, verbose)
        elif command == 'list':
            return UnixPackageUtilities._list_packages(quiet, verbose)
        elif command == 'show':
            return UnixPackageUtilities._show_packages(packages, quiet, verbose)
        else:
            return f"kpm: unknown command: {command}\nTry 'kpm --help' for more information."
    
    @staticmethod
    def do_kget(fs, cwd, arg):
        """
        Download files from the network
        
        Usage: kget [options] url [url...]
        
        Options:
          -O, --output-document=FILE  Write documents to FILE
          -c, --continue              Resume getting a partially-downloaded file
          -q, --quiet                 Quiet (no output)
          -v, --verbose               Verbose output
          --progress=TYPE             Select progress meter type
        """
        args = arg.split()
        
        # Parse options
        output_file = None
        continue_download = False
        quiet = False
        verbose = False
        show_progress = True
        
        # Process arguments
        urls = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i].startswith('-O=') or args[i].startswith('--output-document='):
                    output_file = args[i].split('=')[1]
                elif args[i] == '-O' or args[i] == '--output-document':
                    if i + 1 < len(args):
                        output_file = args[i+1]
                        i += 1
                    else:
                        return "kget: option requires an argument -- 'O'"
                elif args[i] in ['-c', '--continue']:
                    continue_download = True
                elif args[i] in ['-q', '--quiet']:
                    quiet = True
                    verbose = False
                    show_progress = False
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                    quiet = False
                elif args[i].startswith('--progress='):
                    show_progress = args[i].split('=')[1].lower() != 'off'
                else:
                    # Process combined options
                    for c in args[i][1:]:
                        if c == 'c':
                            continue_download = True
                        elif c == 'q':
                            quiet = True
                            verbose = False
                            show_progress = False
                        elif c == 'v':
                            verbose = True
                            quiet = False
            else:
                urls.append(args[i])
            i += 1
        
        if not urls:
            return "kget: missing URL\nTry 'kget --help' for more information."
        
        # Download files
        results = []
        
        for url in urls:
            try:
                # Determine output file name
                if output_file:
                    out_file = output_file
                else:
                    out_file = os.path.basename(url.split('?')[0])
                
                # Resolve output path
                if not os.path.isabs(out_file):
                    out_path = os.path.join(cwd, out_file)
                else:
                    out_path = out_file
                
                # Check if file exists and we're not continuing
                if os.path.exists(out_path) and not continue_download:
                    if not quiet:
                        results.append(f"File '{out_file}' already exists, skipping download")
                    continue
                
                # Create parent directories if they don't exist
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                
                # Download file
                if not quiet:
                    results.append(f"Downloading {url} to {out_file}...")
                
                # Use existing file size if continuing
                existing_size = 0
                if continue_download and os.path.exists(out_path):
                    existing_size = os.path.getsize(out_path)
                    if not quiet:
                        results.append(f"Continuing from byte {existing_size}")
                
                # Set up request
                request = urllib.request.Request(url)
                if continue_download and existing_size > 0:
                    request.add_header('Range', f'bytes={existing_size}-')
                
                # Start download
                with urllib.request.urlopen(request) as response:
                    # Get file size
                    file_size = int(response.info().get('Content-Length', -1))
                    if file_size == -1:
                        file_size = None
                    
                    # Open output file
                    with open(out_path, 'ab' if continue_download else 'wb') as out_file:
                        # Download file
                        downloaded = 0
                        block_size = 8192
                        last_progress = 0
                        
                        while True:
                            buffer = response.read(block_size)
                            if not buffer:
                                break
                            
                            downloaded += len(buffer)
                            out_file.write(buffer)
                            
                            # Show progress
                            if show_progress and file_size and not quiet:
                                progress = int((downloaded + existing_size) * 100 / (file_size + existing_size))
                                if progress >= last_progress + 10:
                                    results.append(f"Downloaded {progress}%")
                                    last_progress = progress
                
                if not quiet:
                    results.append(f"Download complete: {out_file}")
            except urllib.error.URLError as e:
                results.append(f"Error downloading {url}: {str(e)}")
            except Exception as e:
                results.append(f"Error: {str(e)}")
        
        return "\n".join(results)
    
    @staticmethod
    def _init_package_db():
        """Initialize package database if it doesn't exist"""
        try:
            # Create package directory if it doesn't exist
            package_dir = os.path.dirname(PACKAGE_DB_PATH)
            os.makedirs(package_dir, exist_ok=True)
            
            # Create package DB if it doesn't exist
            if not os.path.exists(PACKAGE_DB_PATH):
                package_db = {
                    "available": {},
                    "installed": {},
                    "last_update": time.time()
                }
                
                # Create some sample packages
                package_db["available"] = {
                    "kos-core": {
                        "name": "kos-core",
                        "version": "1.0.0",
                        "description": "KOS core package",
                        "dependencies": [],
                        "size": 1024,
                        "installed_size": 2048
                    },
                    "kos-utils": {
                        "name": "kos-utils",
                        "version": "1.0.0",
                        "description": "KOS utilities",
                        "dependencies": ["kos-core"],
                        "size": 512,
                        "installed_size": 1024
                    },
                    "kos-dev": {
                        "name": "kos-dev",
                        "version": "1.0.0",
                        "description": "KOS development tools",
                        "dependencies": ["kos-core", "kos-utils"],
                        "size": 2048,
                        "installed_size": 4096
                    }
                }
                
                # Add some pre-installed packages
                package_db["installed"] = {
                    "kos-core": {
                        "name": "kos-core",
                        "version": "1.0.0",
                        "description": "KOS core package",
                        "dependencies": [],
                        "size": 1024,
                        "installed_size": 2048,
                        "install_date": time.time()
                    }
                }
                
                # Write package DB
                with open(PACKAGE_DB_PATH, 'w') as f:
                    json.dump(package_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error initializing package database: {str(e)}")
    
    @staticmethod
    def _get_package_db():
        """Get package database"""
        try:
            with open(PACKAGE_DB_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading package database: {str(e)}")
            return {"available": {}, "installed": {}, "last_update": 0}
    
    @staticmethod
    def _write_package_db(package_db):
        """Write package database"""
        try:
            with open(PACKAGE_DB_PATH, 'w') as f:
                json.dump(package_db, f, indent=2)
        except Exception as e:
            logger.error(f"Error writing package database: {str(e)}")
    
    @staticmethod
    def _install_packages(packages, auto_yes, quiet, verbose, use_cache):
        """Install packages"""
        if not packages:
            return "kpm: no packages specified for installation"
        
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Check if packages exist
        not_found = []
        to_install = []
        already_installed = []
        
        for package in packages:
            if package not in package_db["available"]:
                not_found.append(package)
            elif package in package_db["installed"]:
                already_installed.append(package)
            else:
                to_install.append(package)
                
                # Add dependencies
                deps = package_db["available"][package].get("dependencies", [])
                for dep in deps:
                    if dep not in package_db["installed"] and dep not in to_install:
                        to_install.append(dep)
        
        # Show what will be installed
        results = []
        
        if not_found:
            results.append(f"The following packages could not be found: {', '.join(not_found)}")
        
        if already_installed:
            results.append(f"The following packages are already installed: {', '.join(already_installed)}")
        
        if not to_install:
            results.append("Nothing to install")
            return "\n".join(results)
        
        # Calculate total size
        total_size = sum(package_db["available"][p]["size"] for p in to_install)
        total_installed_size = sum(package_db["available"][p]["installed_size"] for p in to_install)
        
        results.append(f"The following packages will be installed: {', '.join(to_install)}")
        results.append(f"Total download size: {total_size // 1024} KB")
        results.append(f"Total installed size: {total_installed_size // 1024} KB")
        
        # Confirm installation
        if not auto_yes:
            results.append("\nDo you want to continue? [Y/n]")
            return "\n".join(results)
        
        # Install packages
        for package in to_install:
            if not quiet:
                results.append(f"Installing {package}...")
            
            # Simulate download and installation
            if verbose:
                results.append(f"Downloading {package}...")
                results.append(f"Extracting {package}...")
                results.append(f"Setting up {package}...")
            
            # Add to installed packages
            package_db["installed"][package] = package_db["available"][package].copy()
            package_db["installed"][package]["install_date"] = time.time()
        
        # Write package database
        UnixPackageUtilities._write_package_db(package_db)
        
        if not quiet:
            results.append("Installation complete")
        
        return "\n".join(results)
    
    @staticmethod
    def _remove_packages(packages, auto_yes, quiet, verbose):
        """Remove packages"""
        if not packages:
            return "kpm: no packages specified for removal"
        
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Check if packages exist
        not_found = []
        not_installed = []
        to_remove = []
        dependents = {}
        
        for package in packages:
            if package not in package_db["available"]:
                not_found.append(package)
            elif package not in package_db["installed"]:
                not_installed.append(package)
            else:
                to_remove.append(package)
                
                # Check if other packages depend on this one
                for p, info in package_db["installed"].items():
                    if p != package and "dependencies" in info and package in info["dependencies"]:
                        if package not in dependents:
                            dependents[package] = []
                        dependents[package].append(p)
        
        # Show what will be removed
        results = []
        
        if not_found:
            results.append(f"The following packages could not be found: {', '.join(not_found)}")
        
        if not_installed:
            results.append(f"The following packages are not installed: {', '.join(not_installed)}")
        
        if dependents:
            for package, deps in dependents.items():
                results.append(f"Warning: The following packages depend on {package}: {', '.join(deps)}")
        
        if not to_remove:
            results.append("Nothing to remove")
            return "\n".join(results)
        
        # Calculate total size
        total_installed_size = sum(package_db["installed"][p]["installed_size"] for p in to_remove)
        
        results.append(f"The following packages will be removed: {', '.join(to_remove)}")
        results.append(f"Total space to be freed: {total_installed_size // 1024} KB")
        
        # Confirm removal
        if not auto_yes:
            results.append("\nDo you want to continue? [Y/n]")
            return "\n".join(results)
        
        # Remove packages
        for package in to_remove:
            if not quiet:
                results.append(f"Removing {package}...")
            
            # Simulate removal
            if verbose:
                results.append(f"Removing files for {package}...")
                results.append(f"Purging configuration for {package}...")
            
            # Remove from installed packages
            del package_db["installed"][package]
        
        # Write package database
        UnixPackageUtilities._write_package_db(package_db)
        
        if not quiet:
            results.append("Removal complete")
        
        return "\n".join(results)
    
    @staticmethod
    def _update_package_db(quiet, verbose):
        """Update package database"""
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Update last update time
        package_db["last_update"] = time.time()
        
        # Simulate update
        results = []
        
        if not quiet:
            results.append("Updating package database...")
        
        if verbose:
            results.append("Fetching package lists...")
            results.append("Reading package information...")
        
        # Add some new packages
        new_packages = {
            "kos-games": {
                "name": "kos-games",
                "version": "1.0.0",
                "description": "KOS games package",
                "dependencies": ["kos-core"],
                "size": 4096,
                "installed_size": 8192
            },
            "kos-net": {
                "name": "kos-net",
                "version": "1.0.0",
                "description": "KOS networking tools",
                "dependencies": ["kos-core"],
                "size": 2048,
                "installed_size": 4096
            }
        }
        
        package_db["available"].update(new_packages)
        
        # Write package database
        UnixPackageUtilities._write_package_db(package_db)
        
        if not quiet:
            results.append("Update complete")
        
        return "\n".join(results)
    
    @staticmethod
    def _upgrade_packages(auto_yes, quiet, verbose, use_cache):
        """Upgrade packages"""
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Check for upgradable packages
        to_upgrade = []
        
        for package, info in package_db["installed"].items():
            if package in package_db["available"]:
                available = package_db["available"][package]
                if available["version"] != info["version"]:
                    to_upgrade.append(package)
        
        # Show what will be upgraded
        results = []
        
        if not to_upgrade:
            results.append("All packages are up to date")
            return "\n".join(results)
        
        # Calculate total size
        total_size = sum(package_db["available"][p]["size"] for p in to_upgrade)
        total_installed_size = sum(package_db["available"][p]["installed_size"] for p in to_upgrade)
        
        results.append(f"The following packages will be upgraded: {', '.join(to_upgrade)}")
        results.append(f"Total download size: {total_size // 1024} KB")
        results.append(f"Total installed size: {total_installed_size // 1024} KB")
        
        # Confirm upgrade
        if not auto_yes:
            results.append("\nDo you want to continue? [Y/n]")
            return "\n".join(results)
        
        # Upgrade packages
        for package in to_upgrade:
            if not quiet:
                results.append(f"Upgrading {package}...")
            
            # Simulate download and installation
            if verbose:
                results.append(f"Downloading {package}...")
                results.append(f"Extracting {package}...")
                results.append(f"Setting up {package}...")
            
            # Update installed package
            package_db["installed"][package] = package_db["available"][package].copy()
            package_db["installed"][package]["install_date"] = time.time()
        
        # Write package database
        UnixPackageUtilities._write_package_db(package_db)
        
        if not quiet:
            results.append("Upgrade complete")
        
        return "\n".join(results)
    
    @staticmethod
    def _search_packages(terms, quiet, verbose):
        """Search for packages"""
        if not terms:
            return "kpm: no search terms specified"
        
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Search for packages
        results = []
        matches = []
        
        for package, info in package_db["available"].items():
            for term in terms:
                if (term.lower() in package.lower() or
                    term.lower() in info.get("description", "").lower()):
                    matches.append((package, info))
                    break
        
        if not matches:
            results.append(f"No packages found matching: {', '.join(terms)}")
            return "\n".join(results)
        
        results.append(f"Found {len(matches)} packages:")
        
        for package, info in sorted(matches, key=lambda x: x[0]):
            installed = package in package_db["installed"]
            installed_str = "[installed]" if installed else ""
            results.append(f"{package} ({info['version']}) {installed_str}")
            if verbose:
                results.append(f"  {info['description']}")
                results.append(f"  Size: {info['size'] // 1024} KB")
                if "dependencies" in info and info["dependencies"]:
                    results.append(f"  Dependencies: {', '.join(info['dependencies'])}")
                results.append("")
            else:
                results.append(f"  {info['description']}")
        
        return "\n".join(results)
    
    @staticmethod
    def _list_packages(quiet, verbose):
        """List installed packages"""
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # List installed packages
        results = []
        installed = list(package_db["installed"].items())
        
        if not installed:
            results.append("No packages installed")
            return "\n".join(results)
        
        results.append(f"Installed packages ({len(installed)}):")
        
        for package, info in sorted(installed, key=lambda x: x[0]):
            results.append(f"{package} ({info['version']})")
            if verbose:
                results.append(f"  {info['description']}")
                results.append(f"  Size: {info['installed_size'] // 1024} KB")
                if "dependencies" in info and info["dependencies"]:
                    results.append(f"  Dependencies: {', '.join(info['dependencies'])}")
                results.append(f"  Installed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['install_date']))}")
                results.append("")
            elif not quiet:
                results.append(f"  {info['description']}")
        
        return "\n".join(results)
    
    @staticmethod
    def _show_packages(packages, quiet, verbose):
        """Show package details"""
        if not packages:
            return "kpm: no packages specified"
        
        # Get package database
        package_db = UnixPackageUtilities._get_package_db()
        
        # Show package details
        results = []
        
        for package in packages:
            if package not in package_db["available"]:
                results.append(f"Package {package} not found")
                continue
            
            info = package_db["available"][package]
            installed = package in package_db["installed"]
            
            results.append(f"Package: {package}")
            results.append(f"Version: {info['version']}")
            results.append(f"Status: {'installed' if installed else 'not installed'}")
            results.append(f"Description: {info['description']}")
            results.append(f"Size: {info['size'] // 1024} KB")
            results.append(f"Installed Size: {info['installed_size'] // 1024} KB")
            
            if "dependencies" in info and info["dependencies"]:
                results.append(f"Dependencies: {', '.join(info['dependencies'])}")
            
            if installed:
                inst_info = package_db["installed"][package]
                results.append(f"Installed: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(inst_info['install_date']))}")
            
            results.append("")
        
        return "\n".join(results)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("kpm", UnixPackageUtilities.do_kpm)
    shell.register_command("kget", UnixPackageUtilities.do_kget)

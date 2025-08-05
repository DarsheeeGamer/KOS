"""
Application Management Commands for KOS shell.

This module implements application management for the KOS Package Manager (KPM),
providing functionality to install, remove, update, and search for applications.
"""

import os
import re
import shlex
import logging
import json
import time
import threading
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

logger = logging.getLogger('KOS.shell.app_management')

# Try to use VFS if available, fallback to host filesystem
try:
    from ...vfs.vfs_wrapper import get_vfs, VFS_O_RDONLY, VFS_O_WRONLY, VFS_O_CREAT, VFS_O_APPEND
    USE_VFS = True
    logger.info("Using KOS VFS for application management")
except Exception as e:
    USE_VFS = False
    logger.warning(f"VFS not available, using host filesystem: {e}")

# Import package management modules
try:
    from ...package.app_index import AppIndexManager, AppInfo
    from ...package.manager import PackageManager, PackageDatabase
    from .package_manager import kpm_lock, KPM_ROOT_DIR
    MODULES_AVAILABLE = True
except ImportError as e:
    logger.debug(f"Application management modules not available: {e}")
    MODULES_AVAILABLE = False
    # Define fallback values
    KPM_ROOT_DIR = os.path.expanduser('~/.kos/kpm')
    
    # Create simple fallback lock
    import threading
    _fallback_lock = threading.Lock()
    def kpm_lock():
        return _fallback_lock

# Application configuration constants
APP_DIR = os.path.join(KPM_ROOT_DIR, 'apps')
APP_INDEX_DIR = os.path.join(KPM_ROOT_DIR, 'index')
APP_INDEX_FILE = os.path.join(APP_INDEX_DIR, 'app_index.json')

class ApplicationManagementCommands:
    """Implementation of application management commands for KOS shell."""
    
    _app_manager = None
    _package_db = None
    
    @staticmethod
    def _ensure_app_manager():
        """Ensure the application manager is initialized"""
        if ApplicationManagementCommands._app_manager is None and MODULES_AVAILABLE:
            ApplicationManagementCommands._app_manager = AppIndexManager()
        return ApplicationManagementCommands._app_manager
    
    @staticmethod
    def _ensure_package_db():
        """Ensure the package database is initialized"""
        if ApplicationManagementCommands._package_db is None and MODULES_AVAILABLE:
            ApplicationManagementCommands._package_db = PackageDatabase()
        return ApplicationManagementCommands._package_db
    
    @staticmethod
    def do_app_install(fs, cwd, arg):
        """Install an application from the app index
        
        Usage: app-install [name] [options]
        
        Options:
          --version=VERSION    Install specific version
          --force              Force reinstall if already installed
          --no-deps            Do not install dependencies
          --user               Install in user directory
          
        Examples:
          app-install myapp
          app-install myapp --version=1.2.3
          app-install myapp --force
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return ApplicationManagementCommands.do_app_install.__doc__
        
        app_name = args[0]
        
        # Parse options
        version = None
        force = False
        no_deps = False
        user_install = False
        
        for arg in args[1:]:
            if arg.startswith('--version='):
                version = arg[10:]
            elif arg == '--force':
                force = True
            elif arg == '--no-deps':
                no_deps = True
            elif arg == '--user':
                user_install = True
        
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Check if app exists in index
        app_info = app_manager.get_app_info(app_name, version)
        if not app_info:
            return f"Application '{app_name}' not found in app index."
        
        # Check if already installed
        if app_manager.is_app_installed(app_name) and not force:
            installed_version = app_manager.get_installed_app_version(app_name)
            return f"Application '{app_name}' is already installed (version {installed_version}).\nUse --force to reinstall."
        
        try:
            # Install the application
            with kpm_lock():
                success, message = app_manager.install_app(
                    app_name, 
                    version=version, 
                    force=force, 
                    install_deps=not no_deps,
                    user_install=user_install
                )
            
            if success:
                installed_version = app_manager.get_installed_app_version(app_name)
                output = [f"Successfully installed '{app_name}' (version {installed_version})"]
                
                # Add app usage information
                usage_info = app_info.usage_info if hasattr(app_info, 'usage_info') else None
                if usage_info:
                    output.append("\nUsage information:")
                    output.append(usage_info)
                
                return "\n".join(output)
            else:
                return f"Failed to install '{app_name}': {message}"
        except Exception as e:
            logger.error(f"Error installing application: {e}")
            return f"Error installing application: {str(e)}"
    
    @staticmethod
    def do_app_remove(fs, cwd, arg):
        """Remove an installed application
        
        Usage: app-remove [name] [options]
        
        Options:
          --purge              Remove configuration files as well
          --keep-deps          Keep dependencies installed
          
        Examples:
          app-remove myapp
          app-remove myapp --purge
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return ApplicationManagementCommands.do_app_remove.__doc__
        
        app_name = args[0]
        
        # Parse options
        purge = '--purge' in args
        keep_deps = '--keep-deps' in args
        
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Check if app is installed
        if not app_manager.is_app_installed(app_name):
            return f"Application '{app_name}' is not installed."
        
        try:
            # Remove the application
            with kpm_lock():
                success, message = app_manager.remove_app(
                    app_name, 
                    purge=purge, 
                    keep_deps=keep_deps
                )
            
            if success:
                return f"Successfully removed '{app_name}'"
            else:
                return f"Failed to remove '{app_name}': {message}"
        except Exception as e:
            logger.error(f"Error removing application: {e}")
            return f"Error removing application: {str(e)}"
    
    @staticmethod
    def do_app_list(fs, cwd, arg):
        """List installed applications
        
        Usage: app-list [options]
        
        Options:
          --verbose        Show detailed information
          --upgradable     Show only upgradable applications
          --json           Output in JSON format
          
        Examples:
          app-list
          app-list --verbose
          app-list --upgradable
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        
        # Parse options
        verbose = '--verbose' in args
        upgradable_only = '--upgradable' in args
        json_output = '--json' in args
        
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Get installed apps
        installed_apps = app_manager.list_installed_apps()
        
        if not installed_apps:
            return "No applications installed."
        
        # Check for upgrades if needed
        upgradable_apps = {}
        if upgradable_only or verbose:
            upgradable_apps = app_manager.get_upgradable_apps()
            
            if upgradable_only:
                installed_apps = {name: info for name, info in installed_apps.items() 
                                 if name in upgradable_apps}
                
                if not installed_apps:
                    return "No upgradable applications found."
        
        if json_output:
            # Format as JSON
            app_data = []
            for name, info in installed_apps.items():
                data = {
                    "name": name,
                    "version": info.version,
                    "install_date": info.install_date.isoformat() if hasattr(info, 'install_date') else None,
                    "description": info.description,
                    "path": info.install_path
                }
                
                if name in upgradable_apps:
                    data["upgradable"] = True
                    data["available_version"] = upgradable_apps[name]
                
                app_data.append(data)
                
            return json.dumps(app_data, indent=2)
        
        # Format output
        if verbose:
            result = ["Installed applications:"]
            
            for name, info in installed_apps.items():
                result.append(f"\n{name}:")
                result.append(f"  Version: {info.version}")
                
                if hasattr(info, 'install_date') and info.install_date:
                    result.append(f"  Installed: {info.install_date}")
                    
                if info.description:
                    result.append(f"  Description: {info.description}")
                    
                result.append(f"  Path: {info.install_path}")
                
                # Show upgrade info if available
                if name in upgradable_apps:
                    result.append(f"  Upgrade available: {upgradable_apps[name]}")
        else:
            result = ["NAME               VERSION    STATUS     DESCRIPTION"]
            result.append("------------------ ---------- ---------- -------------------------")
            
            for name, info in installed_apps.items():
                name_col = name[:18].ljust(18)
                version_col = info.version[:10].ljust(10)
                
                status = "Upgradable" if name in upgradable_apps else "Installed"
                status_col = status.ljust(10)
                
                desc = info.description[:25] if info.description else ""
                
                result.append(f"{name_col} {version_col} {status_col} {desc}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_app_search(fs, cwd, arg):
        """Search for applications in the app index
        
        Usage: app-search [query] [options]
        
        Options:
          --verbose        Show detailed information
          --exact          Match exact name only
          --tag=TAG        Search by tag
          --category=CAT   Search by category
          --limit=N        Limit results (default: 10)
          
        Examples:
          app-search game
          app-search editor --tag=text
          app-search --category=utilities
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        
        # Parse options
        verbose = '--verbose' in args
        exact = '--exact' in args
        limit = 10
        tag = None
        category = None
        
        # Extract query and other options
        query = None
        filtered_args = []
        
        for arg in args:
            if arg.startswith('--limit='):
                try:
                    limit = int(arg[8:])
                except ValueError:
                    return f"Invalid limit value: {arg[8:]}"
            elif arg.startswith('--tag='):
                tag = arg[6:]
            elif arg.startswith('--category='):
                category = arg[11:]
            elif not arg.startswith('--'):
                query = arg
            else:
                filtered_args.append(arg)
        
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Perform search
        if exact and query:
            # Exact match by name
            app_info = app_manager.get_app_info(query)
            if app_info:
                results = {query: app_info}
            else:
                results = {}
        else:
            # Search by various criteria
            results = app_manager.search_apps(
                query=query,
                tag=tag,
                category=category,
                limit=limit
            )
        
        if not results:
            return "No applications found matching the criteria."
        
        # Format output
        if verbose:
            result = [f"Found {len(results)} application(s):"]
            
            for name, info in results.items():
                result.append(f"\n{name}:")
                result.append(f"  Version: {info.version}")
                
                if info.description:
                    result.append(f"  Description: {info.description}")
                
                if hasattr(info, 'tags') and info.tags:
                    result.append(f"  Tags: {', '.join(info.tags)}")
                    
                if hasattr(info, 'category') and info.category:
                    result.append(f"  Category: {info.category}")
                    
                if hasattr(info, 'author') and info.author:
                    result.append(f"  Author: {info.author}")
                    
                if hasattr(info, 'repository') and info.repository:
                    result.append(f"  Repository: {info.repository}")
                    
                # Show if app is already installed
                if app_manager.is_app_installed(name):
                    installed_version = app_manager.get_installed_app_version(name)
                    result.append(f"  Status: Installed (version {installed_version})")
        else:
            result = ["NAME               VERSION    CATEGORY    DESCRIPTION"]
            result.append("------------------ ---------- ----------- -------------------------")
            
            for name, info in results.items():
                name_col = name[:18].ljust(18)
                version_col = info.version[:10].ljust(10)
                
                category = info.category if hasattr(info, 'category') and info.category else ""
                category_col = category[:11].ljust(11)
                
                desc = info.description[:25] if info.description else ""
                
                result.append(f"{name_col} {version_col} {category_col} {desc}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_app_update(fs, cwd, arg):
        """Update applications to newer versions
        
        Usage: app-update [name] [options]
        
        If no name is provided, checks for updates for all installed applications.
        
        Options:
          --check          Only check for updates, don't install
          --force          Force update even if already up to date
          --no-deps        Don't update dependencies
          
        Examples:
          app-update
          app-update --check
          app-update myapp
          app-update myapp --force
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        
        # Parse options
        check_only = '--check' in args
        force = '--force' in args
        no_deps = '--no-deps' in args
        
        # Extract app name if provided
        app_name = None
        for arg in args:
            if not arg.startswith('--'):
                app_name = arg
                break
        
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Check for updates
        if app_name:
            # Check specific app
            if not app_manager.is_app_installed(app_name):
                return f"Application '{app_name}' is not installed."
            
            current_version = app_manager.get_installed_app_version(app_name)
            update_available = app_manager.check_app_update(app_name)
            
            if not update_available and not force:
                return f"Application '{app_name}' is already up to date (version {current_version})."
            
            if check_only:
                if update_available:
                    new_version = app_manager.get_latest_app_version(app_name)
                    return f"Update available for '{app_name}': {current_version} -> {new_version}"
                else:
                    return f"No update available for '{app_name}' (version {current_version})."
            
            # Perform update
            try:
                with kpm_lock():
                    success, message = app_manager.update_app(
                        app_name,
                        force=force,
                        update_deps=not no_deps
                    )
                
                if success:
                    new_version = app_manager.get_installed_app_version(app_name)
                    return f"Successfully updated '{app_name}' from {current_version} to {new_version}"
                else:
                    return f"Failed to update '{app_name}': {message}"
            except Exception as e:
                logger.error(f"Error updating application: {e}")
                return f"Error updating application: {str(e)}"
        else:
            # Check all installed apps
            upgradable = app_manager.get_upgradable_apps()
            
            if not upgradable:
                return "All applications are up to date."
            
            if check_only:
                result = [f"Updates available for {len(upgradable)} application(s):"]
                
                for name, new_version in upgradable.items():
                    current_version = app_manager.get_installed_app_version(name)
                    result.append(f"  {name}: {current_version} -> {new_version}")
                
                return "\n".join(result)
            
            # Perform updates
            try:
                updated = []
                failed = []
                
                for name in upgradable.keys():
                    with kpm_lock():
                        success, message = app_manager.update_app(
                            name,
                            force=force,
                            update_deps=not no_deps
                        )
                    
                    if success:
                        new_version = app_manager.get_installed_app_version(name)
                        updated.append((name, new_version))
                    else:
                        failed.append((name, message))
                
                # Format output
                result = []
                
                if updated:
                    result.append(f"Successfully updated {len(updated)} application(s):")
                    for name, version in updated:
                        result.append(f"  {name} -> {version}")
                
                if failed:
                    if result:
                        result.append("")
                    result.append(f"Failed to update {len(failed)} application(s):")
                    for name, message in failed:
                        result.append(f"  {name}: {message}")
                
                return "\n".join(result)
            except Exception as e:
                logger.error(f"Error updating applications: {e}")
                return f"Error updating applications: {str(e)}"
    
    @staticmethod
    def do_app_info(fs, cwd, arg):
        """Show detailed information about an application
        
        Usage: app-info [name]
        
        Examples:
          app-info myapp
        """
        if not MODULES_AVAILABLE:
            return "Application management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return ApplicationManagementCommands.do_app_info.__doc__
        
        app_name = args[0]
        app_manager = ApplicationManagementCommands._ensure_app_manager()
        
        # Get app info
        app_info = app_manager.get_app_info(app_name)
        if not app_info:
            return f"Application '{app_name}' not found in app index."
        
        # Check if installed
        installed = app_manager.is_app_installed(app_name)
        installed_version = None
        if installed:
            installed_version = app_manager.get_installed_app_version(app_name)
            installed_info = app_manager.get_installed_app_info(app_name)
        
        # Format output
        result = [f"Application: {app_name}"]
        result.append(f"Version: {app_info.version}")
        
        if installed:
            result.append(f"Status: Installed (version {installed_version})")
            
            if installed_version != app_info.version:
                result.append(f"Update available: {app_info.version}")
                
            if hasattr(installed_info, 'install_date') and installed_info.install_date:
                result.append(f"Installed on: {installed_info.install_date}")
                
            if hasattr(installed_info, 'install_path') and installed_info.install_path:
                result.append(f"Install path: {installed_info.install_path}")
        else:
            result.append("Status: Not installed")
        
        if app_info.description:
            result.append(f"\nDescription: {app_info.description}")
            
        if hasattr(app_info, 'long_description') and app_info.long_description:
            result.append(f"\n{app_info.long_description}")
            
        if hasattr(app_info, 'author') and app_info.author:
            result.append(f"\nAuthor: {app_info.author}")
            
        if hasattr(app_info, 'homepage') and app_info.homepage:
            result.append(f"Homepage: {app_info.homepage}")
            
        if hasattr(app_info, 'repository') and app_info.repository:
            result.append(f"Repository: {app_info.repository}")
            
        if hasattr(app_info, 'license') and app_info.license:
            result.append(f"License: {app_info.license}")
            
        if hasattr(app_info, 'tags') and app_info.tags:
            result.append(f"Tags: {', '.join(app_info.tags)}")
            
        if hasattr(app_info, 'category') and app_info.category:
            result.append(f"Category: {app_info.category}")
            
        # Dependencies
        if hasattr(app_info, 'dependencies') and app_info.dependencies:
            result.append("\nDependencies:")
            for dep in app_info.dependencies:
                if isinstance(dep, str):
                    result.append(f"  {dep}")
                elif hasattr(dep, 'name') and hasattr(dep, 'version'):
                    result.append(f"  {dep.name} (>= {dep.version})")
        
        # Usage info
        if hasattr(app_info, 'usage_info') and app_info.usage_info:
            result.append("\nUsage:")
            result.append(app_info.usage_info)
        
        return "\n".join(result)

def register_commands(shell):
    """Register all application management commands with the KOS shell."""
    
    # Add the app-install command
    def do_app_install(self, arg):
        """Install an application from the app index"""
        try:
            result = ApplicationManagementCommands.do_app_install(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-install command: {e}")
            print(f"app-install: {str(e)}")
    
    # Add the app-remove command
    def do_app_remove(self, arg):
        """Remove an installed application"""
        try:
            result = ApplicationManagementCommands.do_app_remove(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-remove command: {e}")
            print(f"app-remove: {str(e)}")
    
    # Add the app-list command
    def do_app_list(self, arg):
        """List installed applications"""
        try:
            result = ApplicationManagementCommands.do_app_list(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-list command: {e}")
            print(f"app-list: {str(e)}")
    
    # Add the app-search command
    def do_app_search(self, arg):
        """Search for applications in the app index"""
        try:
            result = ApplicationManagementCommands.do_app_search(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-search command: {e}")
            print(f"app-search: {str(e)}")
    
    # Add the app-update command
    def do_app_update(self, arg):
        """Update applications to newer versions"""
        try:
            result = ApplicationManagementCommands.do_app_update(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-update command: {e}")
            print(f"app-update: {str(e)}")
    
    # Add the app-info command
    def do_app_info(self, arg):
        """Show detailed information about an application"""
        try:
            result = ApplicationManagementCommands.do_app_info(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in app-info command: {e}")
            print(f"app-info: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_app_install', do_app_install)
    setattr(shell.__class__, 'do_app_remove', do_app_remove)
    setattr(shell.__class__, 'do_app_list', do_app_list)
    setattr(shell.__class__, 'do_app_search', do_app_search)
    setattr(shell.__class__, 'do_app_update', do_app_update)
    setattr(shell.__class__, 'do_app_info', do_app_info)

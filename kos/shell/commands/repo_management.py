"""
Repository Management Commands for KOS shell.

This module implements repository management for the KOS Package Manager (KPM),
providing functionality to add, remove, update, and configure repositories.
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

logger = logging.getLogger('KOS.shell.repo_management')

# Import package management modules
try:
    from ...package.repo_index import RepoIndexManager, RepositoryInfo
    from ..commands.package_manager import kpm_lock, KPM_ROOT_DIR
    REPO_MODULES_AVAILABLE = True
except ImportError:
    logger.warning("Repository management modules not available")
    REPO_MODULES_AVAILABLE = False

# Repository configuration constants
REPO_CONFIG_DIR = os.path.join(KPM_ROOT_DIR, 'repos') if 'KPM_ROOT_DIR' in locals() else os.path.expanduser('~/.kos/kpm/repos')
REPO_CONFIG_FILE = os.path.join(REPO_CONFIG_DIR, 'repos.json')

class RepositoryManagementCommands:
    """Implementation of repository management commands for KOS shell."""
    
    _repo_manager = None
    
    @staticmethod
    def _ensure_repo_manager():
        """Ensure the repository manager is initialized"""
        if RepositoryManagementCommands._repo_manager is None and REPO_MODULES_AVAILABLE:
            RepositoryManagementCommands._repo_manager = RepoIndexManager()
        return RepositoryManagementCommands._repo_manager
    
    @staticmethod
    def do_repo_add(fs, cwd, arg):
        """Add a repository to KPM
        
        Usage: repo-add [name] [url] [options]
        
        Options:
          --active=yes/no     Set repository active status (default: yes)
          --priority=N        Set repository priority (lower is higher priority)
          --no-update         Don't update repository after adding
          
        Examples:
          repo-add custom https://example.com/repo
          repo-add testing https://test.example.com/repo --active=no
          repo-add stable https://stable.example.com/repo --priority=10
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        if len(args) < 2:
            return RepositoryManagementCommands.do_repo_add.__doc__
        
        name, url = args[0], args[1]
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        # Parse options
        active = True
        priority = 100  # Default priority
        update_after = True
        
        for arg in args[2:]:
            if arg.startswith('--active='):
                active_val = arg[9:].lower()
                active = active_val in ['yes', 'true', '1', 'on']
            elif arg.startswith('--priority='):
                try:
                    priority = int(arg[11:])
                except ValueError:
                    return f"Invalid priority value: {arg[11:]}"
            elif arg == '--no-update':
                update_after = False
        
        # Check if repository already exists
        existing_repo = repo_manager.get_repository(name)
        if existing_repo:
            return f"Repository '{name}' already exists."
        
        try:
            # Add repository with metadata
            success = repo_manager.add_repository(name, url, active=active)
            if not success:
                return f"Failed to add repository '{name}'"
            
            # Set repository priority if supported
            if hasattr(repo_manager, 'set_repository_priority'):
                repo_manager.set_repository_priority(name, priority)
            
            # Update repository if requested
            if update_after:
                result = repo_manager.update_repository(name)
                if result:
                    repo = repo_manager.get_repository(name)
                    pkg_count = len(repo.packages) if repo else 0
                    return f"Successfully added and updated repository '{name}' ({pkg_count} packages)"
                else:
                    return f"Added repository '{name}' but failed to update it. Use 'repo-update {name}' to try again."
            
            return f"Successfully added repository '{name}' (active: {active}, priority: {priority})"
        except Exception as e:
            logger.error(f"Error adding repository: {e}")
            return f"Error adding repository: {str(e)}"
    
    @staticmethod
    def do_repo_remove(fs, cwd, arg):
        """Remove a repository from KPM
        
        Usage: repo-remove [name] [options]
        
        Options:
          --force     Force removal even if packages are installed from this repository
          
        Examples:
          repo-remove custom
          repo-remove testing --force
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return RepositoryManagementCommands.do_repo_remove.__doc__
        
        name = args[0]
        force = '--force' in args
        
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        # Check if repository exists
        existing_repo = repo_manager.get_repository(name)
        if not existing_repo:
            return f"Repository '{name}' does not exist."
        
        # TODO: In a real implementation, check if packages are installed from this repository
        # and only allow removal if force flag is set
        
        # Remove repository
        success = repo_manager.remove_repository(name)
        if success:
            return f"Successfully removed repository '{name}'"
        else:
            return f"Failed to remove repository '{name}'"
    
    @staticmethod
    def do_repo_list(fs, cwd, arg):
        """List configured repositories
        
        Usage: repo-list [options]
        
        Options:
          --active         Show only active repositories
          --inactive       Show only inactive repositories
          --verbose        Show detailed information
          --json           Output in JSON format
          
        Examples:
          repo-list
          repo-list --active
          repo-list --verbose
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        
        # Parse options
        active_only = '--active' in args
        inactive_only = '--inactive' in args
        verbose = '--verbose' in args
        json_output = '--json' in args
        
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        repos = repo_manager.list_repositories()
        
        # Filter repositories
        if active_only:
            repos = [repo for repo in repos if repo.active]
        elif inactive_only:
            repos = [repo for repo in repos if not repo.active]
        
        if not repos:
            return "No repositories configured."
        
        if json_output:
            # Format as JSON
            import json
            repo_data = []
            for repo in repos:
                data = {
                    "name": repo.name,
                    "url": repo.url,
                    "active": repo.active,
                    "last_update": repo.last_update,
                    "package_count": len(repo.packages)
                }
                if hasattr(repo, 'priority'):
                    data["priority"] = repo.priority
                repo_data.append(data)
            return json.dumps(repo_data, indent=2)
        
        # Format output
        result = ["Configured repositories:"]
        
        if verbose:
            for repo in repos:
                result.append(f"\n{repo.name}:")
                result.append(f"  URL: {repo.url}")
                result.append(f"  Status: {'Active' if repo.active else 'Inactive'}")
                result.append(f"  Last update: {repo.last_update}")
                result.append(f"  Packages: {len(repo.packages)}")
                if hasattr(repo, 'priority'):
                    result.append(f"  Priority: {repo.priority}")
        else:
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
    def do_repo_update(fs, cwd, arg):
        """Update repository package index
        
        Usage: repo-update [name] [options]
        
        If no name is provided, all active repositories will be updated.
        
        Options:
          --force     Force update even for inactive repositories
          --quiet     Suppress detailed output
          
        Examples:
          repo-update
          repo-update custom
          repo-update custom --force
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        
        # Parse options
        force = '--force' in args
        quiet = '--quiet' in args
        
        # Remove options from args
        args = [a for a in args if not a.startswith('--')]
        
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        if not args:
            # Update all repositories
            results = repo_manager.update_all_repositories()
            
            # Format output
            success_count = sum(1 for success in results.values() if success)
            output = [f"Updated {success_count} of {len(results)} repositories:"]
            
            if not quiet:
                for repo_name, success in results.items():
                    status = "Success" if success else "Failed"
                    repo = repo_manager.get_repository(repo_name)
                    pkg_count = len(repo.packages) if repo and success else 0
                    output.append(f"  {repo_name}: {status} ({pkg_count} packages)")
            
            return "\n".join(output)
        else:
            # Update specific repository
            name = args[0]
            
            # Check if repository exists
            existing_repo = repo_manager.get_repository(name)
            if not existing_repo:
                return f"Repository '{name}' does not exist."
            
            # Check if repository is active
            if not existing_repo.active and not force:
                return f"Repository '{name}' is inactive. Use --force to update anyway."
            
            # Update repository
            success = repo_manager.update_repository(name)
            if success:
                pkg_count = len(existing_repo.packages)
                return f"Successfully updated repository '{name}' ({pkg_count} packages)"
            else:
                return f"Failed to update repository '{name}'"
    
    @staticmethod
    def do_repo_enable(fs, cwd, arg):
        """Enable a repository
        
        Usage: repo-enable [name]
        
        Examples:
          repo-enable custom
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return RepositoryManagementCommands.do_repo_enable.__doc__
        
        name = args[0]
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        # Check if repository exists
        existing_repo = repo_manager.get_repository(name)
        if not existing_repo:
            return f"Repository '{name}' does not exist."
        
        # Check if already enabled
        if existing_repo.active:
            return f"Repository '{name}' is already enabled."
        
        # Enable repository
        success = repo_manager.set_repository_active(name, True)
        if success:
            return f"Successfully enabled repository '{name}'"
        else:
            return f"Failed to enable repository '{name}'"
    
    @staticmethod
    def do_repo_disable(fs, cwd, arg):
        """Disable a repository
        
        Usage: repo-disable [name]
        
        Examples:
          repo-disable custom
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        if not args:
            return RepositoryManagementCommands.do_repo_disable.__doc__
        
        name = args[0]
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        # Check if repository exists
        existing_repo = repo_manager.get_repository(name)
        if not existing_repo:
            return f"Repository '{name}' does not exist."
        
        # Check if already disabled
        if not existing_repo.active:
            return f"Repository '{name}' is already disabled."
        
        # Disable repository
        success = repo_manager.set_repository_active(name, False)
        if success:
            return f"Successfully disabled repository '{name}'"
        else:
            return f"Failed to disable repository '{name}'"
    
    @staticmethod
    def do_repo_priority(fs, cwd, arg):
        """Set repository priority
        
        Usage: repo-priority [name] [priority]
        
        Lower numbers indicate higher priority. Default priority is 100.
        When multiple repositories contain the same package, the one with
        the highest priority (lowest number) will be used.
        
        Examples:
          repo-priority custom 10
          repo-priority testing 200
        """
        if not REPO_MODULES_AVAILABLE:
            return "Repository management modules not available"
        
        args = shlex.split(arg)
        if len(args) < 2:
            return RepositoryManagementCommands.do_repo_priority.__doc__
        
        name = args[0]
        try:
            priority = int(args[1])
        except ValueError:
            return f"Invalid priority value: {args[1]}"
        
        repo_manager = RepositoryManagementCommands._ensure_repo_manager()
        
        # Check if repository exists
        existing_repo = repo_manager.get_repository(name)
        if not existing_repo:
            return f"Repository '{name}' does not exist."
        
        # Check if set_repository_priority method exists
        if not hasattr(repo_manager, 'set_repository_priority'):
            return "Repository priority setting is not supported in this version."
        
        # Set priority
        try:
            success = repo_manager.set_repository_priority(name, priority)
            if success:
                return f"Successfully set priority for repository '{name}' to {priority}"
            else:
                return f"Failed to set priority for repository '{name}'"
        except Exception as e:
            logger.error(f"Error setting repository priority: {e}")
            return f"Error setting repository priority: {str(e)}"

def register_commands(shell):
    """Register all repository management commands with the KOS shell."""
    
    # Add the repo-add command
    def do_repo_add(self, arg):
        """Add a repository to KPM"""
        try:
            result = RepositoryManagementCommands.do_repo_add(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-add command: {e}")
            print(f"repo-add: {str(e)}")
    
    # Add the repo-remove command
    def do_repo_remove(self, arg):
        """Remove a repository from KPM"""
        try:
            result = RepositoryManagementCommands.do_repo_remove(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-remove command: {e}")
            print(f"repo-remove: {str(e)}")
    
    # Add the repo-list command
    def do_repo_list(self, arg):
        """List configured repositories"""
        try:
            result = RepositoryManagementCommands.do_repo_list(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-list command: {e}")
            print(f"repo-list: {str(e)}")
    
    # Add the repo-update command
    def do_repo_update(self, arg):
        """Update repository package index"""
        try:
            result = RepositoryManagementCommands.do_repo_update(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-update command: {e}")
            print(f"repo-update: {str(e)}")
    
    # Add the repo-enable command
    def do_repo_enable(self, arg):
        """Enable a repository"""
        try:
            result = RepositoryManagementCommands.do_repo_enable(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-enable command: {e}")
            print(f"repo-enable: {str(e)}")
    
    # Add the repo-disable command
    def do_repo_disable(self, arg):
        """Disable a repository"""
        try:
            result = RepositoryManagementCommands.do_repo_disable(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-disable command: {e}")
            print(f"repo-disable: {str(e)}")
    
    # Add the repo-priority command
    def do_repo_priority(self, arg):
        """Set repository priority"""
        try:
            result = RepositoryManagementCommands.do_repo_priority(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in repo-priority command: {e}")
            print(f"repo-priority: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_repo_add', do_repo_add)
    setattr(shell.__class__, 'do_repo_remove', do_repo_remove)
    setattr(shell.__class__, 'do_repo_list', do_repo_list)
    setattr(shell.__class__, 'do_repo_update', do_repo_update)
    setattr(shell.__class__, 'do_repo_enable', do_repo_enable)
    setattr(shell.__class__, 'do_repo_disable', do_repo_disable)
    setattr(shell.__class__, 'do_repo_priority', do_repo_priority)

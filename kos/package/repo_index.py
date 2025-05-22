"""
KOS Repository Index Manager
Handles the registry of repositories and their available packages
"""
import os
import json
import logging
import requests
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger('KOS.package.repo_index')

class RepositoryPackage:
    """Represents a package in a repository"""
    def __init__(self,
                 name: str,
                 version: str,
                 description: str = "",
                 author: str = "",
                 dependencies: List[str] = None,
                 entry_point: str = "",
                 tags: List[str] = None,
                 repository: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.dependencies = dependencies or []
        self.entry_point = entry_point
        self.tags = tags or []
        self.repository = repository
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": self.dependencies,
            "entry_point": self.entry_point,
            "tags": self.tags,
            "repository": self.repository
        }
        
    @staticmethod
    def from_dict(data: Dict[str, Any], repo_name: str = "") -> 'RepositoryPackage':
        """Create from dictionary"""
        return RepositoryPackage(
            name=data.get("name", ""),
            version=data.get("version", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            dependencies=data.get("dependencies", []),
            entry_point=data.get("entry_point", ""),
            tags=data.get("tags", []),
            repository=repo_name or data.get("repository", "")
        )

class RepositoryInfo:
    """Represents a repository in the index"""
    def __init__(self,
                 name: str,
                 url: str,
                 packages: Dict[str, RepositoryPackage] = None,
                 active: bool = True,
                 last_update: str = None):
        self.name = name
        self.url = url
        self.packages = packages or {}
        self.active = active
        self.last_update = last_update or datetime.now().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "url": self.url,
            "active": self.active,
            "last_update": self.last_update,
            "packages": {name: pkg.to_dict() for name, pkg in self.packages.items()}
        }
        
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'RepositoryInfo':
        """Create from dictionary"""
        repo_name = data.get("name", "")
        packages = {}
        for name, pkg_data in data.get("packages", {}).items():
            packages[name] = RepositoryPackage.from_dict(pkg_data, repo_name)
            
        return RepositoryInfo(
            name=repo_name,
            url=data.get("url", ""),
            packages=packages,
            active=data.get("active", True),
            last_update=data.get("last_update", datetime.now().isoformat())
        )

class RepoIndexManager:
    """Manages the KOS repository index"""
    
    def __init__(self):
        self.index_file = "KOS_REPO_INDEX.json"
        self.repos: Dict[str, RepositoryInfo] = {}
        self._load_index()
        
    def _load_index(self) -> None:
        """Load repository index from file"""
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    for name, repo_data in data.get("repositories", {}).items():
                        self.repos[name] = RepositoryInfo.from_dict(repo_data)
                logger.info(f"Loaded {len(self.repos)} repositories from index")
            else:
                logger.info("Repository index file not found, creating new index")
                self._save_index()  # Create an empty index file
        except Exception as e:
            logger.error(f"Error loading repository index: {e}")
            # Create an empty index in case of error
            self._save_index()
            
    def _save_index(self) -> None:
        """Save repository index to file"""
        try:
            data = {
                "repositories": {name: repo.to_dict() for name, repo in self.repos.items()}
            }
            with open(self.index_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.repos)} repositories to index")
        except Exception as e:
            logger.error(f"Error saving repository index: {e}")
            
    def add_repository(self, name: str, url: str, active: bool = True) -> bool:
        """Add a repository to the index"""
        try:
            self.repos[name] = RepositoryInfo(name=name, url=url, active=active)
            self._save_index()
            logger.info(f"Added repository '{name}' to index")
            return True
        except Exception as e:
            logger.error(f"Error adding repository to index: {e}")
            return False
            
    def remove_repository(self, name: str) -> bool:
        """Remove a repository from the index"""
        try:
            if name in self.repos:
                del self.repos[name]
                self._save_index()
                logger.info(f"Removed repository '{name}' from index")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing repository from index: {e}")
            return False
            
    def get_repository(self, name: str) -> Optional[RepositoryInfo]:
        """Get repository information from the index"""
        return self.repos.get(name)
        
    def list_repositories(self) -> List[RepositoryInfo]:
        """List all repositories in the index"""
        return list(self.repos.values())
        
    def get_active_repositories(self) -> List[RepositoryInfo]:
        """Get all active repositories"""
        return [repo for repo in self.repos.values() if repo.active]
        
    def set_repository_active(self, name: str, active: bool) -> bool:
        """Set repository active status"""
        repo = self.get_repository(name)
        if repo:
            repo.active = active
            self._save_index()
            logger.info(f"Set repository '{name}' active status to {active}")
            return True
        return False
        
    def update_repository(self, name: str) -> bool:
        """Update repository package list"""
        repo = self.get_repository(name)
        if not repo:
            logger.error(f"Repository '{name}' not found")
            return False
            
        try:
            # Fetch repository package list
            repo_url = repo.url.rstrip('/')
            index_url = f"{repo_url}/repo/index.json"
            
            response = requests.get(index_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch repository index: {response.status_code}")
                return False
                
            index_data = response.json()
            packages = {}
            
            for pkg_name, pkg_data in index_data.get("packages", {}).items():
                packages[pkg_name] = RepositoryPackage.from_dict(pkg_data, name)
                
            repo.packages = packages
            repo.last_update = datetime.now().isoformat()
            self._save_index()
            logger.info(f"Updated repository '{name}' with {len(packages)} packages")
            return True
        except Exception as e:
            logger.error(f"Error updating repository '{name}': {e}")
            return False
            
    def update_all_repositories(self) -> Dict[str, bool]:
        """Update all active repositories"""
        results = {}
        for repo_name, repo in self.repos.items():
            if repo.active:
                results[repo_name] = self.update_repository(repo_name)
        return results
        
    def find_package(self, package_name: str) -> List[RepositoryPackage]:
        """Find a package across all repositories"""
        results = []
        for repo in self.get_active_repositories():
            if package_name in repo.packages:
                results.append(repo.packages[package_name])
        return results
        
    def search_packages(self, query: str) -> List[RepositoryPackage]:
        """Search for packages matching a query"""
        results = []
        query = query.lower()
        for repo in self.get_active_repositories():
            for pkg in repo.packages.values():
                if (query in pkg.name.lower() or 
                    query in pkg.description.lower() or 
                    query in ' '.join(pkg.tags).lower()):
                    results.append(pkg)
        return results

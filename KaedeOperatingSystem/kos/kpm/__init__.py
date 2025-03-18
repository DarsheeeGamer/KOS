"""KOS Package Manager (KPM) - APT-like package management system"""
import json
import os
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class Repository:
    name: str
    url: str
    priority: int
    enabled: bool = True

@dataclass
class Package:
    name: str
    version: str
    description: str
    dependencies: List[str]
    repository: str
    size: int
    maintainer: str
    homepage: Optional[str] = None

class KPM:
    def __init__(self):
        self.config_dir = "/etc/kpm"
        self.repos_file = os.path.join(self.config_dir, "sources.json")
        self.cache_dir = "/var/cache/kpm"
        self.repos: Dict[str, Repository] = {}
        self.package_cache: Dict[str, Package] = {}
        
        self._init_dirs()
        self._load_repos()
        
    def _init_dirs(self):
        """Initialize KPM directory structure"""
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        if not os.path.exists(self.repos_file):
            # Create default repository configuration
            default_repos = {
                "main": Repository(
                    name="main",
                    url="https://kos.packages.main/",
                    priority=100
                ),
                "community": Repository(
                    name="community",
                    url="https://kos.packages.community/",
                    priority=50
                )
            }
            self._save_repos(default_repos)
            
    def _load_repos(self):
        """Load repository configuration"""
        try:
            with open(self.repos_file, 'r') as f:
                data = json.load(f)
                self.repos = {
                    name: Repository(**repo_data)
                    for name, repo_data in data.items()
                }
        except FileNotFoundError:
            self._init_dirs()
            
    def _save_repos(self, repos: Dict[str, Repository]):
        """Save repository configuration"""
        data = {
            name: {
                "name": repo.name,
                "url": repo.url,
                "priority": repo.priority,
                "enabled": repo.enabled
            }
            for name, repo in repos.items()
        }
        with open(self.repos_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def add_repo(self, name: str, url: str, priority: int = 50) -> bool:
        """Add a new package repository"""
        if name in self.repos:
            return False
            
        self.repos[name] = Repository(name=name, url=url, priority=priority)
        self._save_repos(self.repos)
        return True
        
    def remove_repo(self, name: str) -> bool:
        """Remove a package repository"""
        if name not in self.repos:
            return False
            
        del self.repos[name]
        self._save_repos(self.repos)
        return True
        
    def enable_repo(self, name: str) -> bool:
        """Enable a repository"""
        if name not in self.repos:
            return False
            
        self.repos[name].enabled = True
        self._save_repos(self.repos)
        return True
        
    def disable_repo(self, name: str) -> bool:
        """Disable a repository"""
        if name not in self.repos:
            return False
            
        self.repos[name].enabled = False
        self._save_repos(self.repos)
        return True
        
    def update(self):
        """Update package cache from all enabled repositories"""
        self.package_cache.clear()
        
        for repo in sorted(self.repos.values(), key=lambda r: r.priority, reverse=True):
            if not repo.enabled:
                continue
                
            try:
                # Fetch package list from repository
                response = requests.get(f"{repo.url}/packages.json")
                response.raise_for_status()
                
                packages = response.json()
                for pkg_data in packages:
                    pkg = Package(**pkg_data, repository=repo.name)
                    self.package_cache[pkg.name] = pkg
                    
            except Exception as e:
                print(f"Error updating repository {repo.name}: {e}")
                
    def search(self, query: str) -> List[Package]:
        """Search for packages matching query"""
        query = query.lower()
        return [
            pkg for pkg in self.package_cache.values()
            if query in pkg.name.lower() or query in pkg.description.lower()
        ]
        
    def install(self, package_name: str) -> bool:
        """Install a package"""
        if package_name not in self.package_cache:
            return False
            
        pkg = self.package_cache[package_name]
        
        # Check dependencies
        for dep in pkg.dependencies:
            if dep not in self.package_cache:
                print(f"Missing dependency: {dep}")
                return False
        
        try:
            # Download package
            response = requests.get(f"{self.repos[pkg.repository].url}/packages/{pkg.name}.kapp")
            response.raise_for_status()
            
            # Save package file
            package_path = os.path.join(self.cache_dir, f"{pkg.name}.kapp")
            with open(package_path, 'wb') as f:
                f.write(response.content)
                
            # Install package using existing KappManager
            from ..package_manager import KappManager
            km = KappManager()
            return km.install(package_path)
            
        except Exception as e:
            print(f"Error installing package {package_name}: {e}")
            return False
            
    def remove(self, package_name: str) -> bool:
        """Remove an installed package"""
        from ..package_manager import KappManager
        km = KappManager()
        return km.remove(package_name)

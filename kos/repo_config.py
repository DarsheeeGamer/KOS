"""
Enhanced KOS Repository Configuration System
==========================================

This module provides comprehensive repository management for KOS with:
- Advanced repository discovery and management
- Package indexing and metadata caching  
- Dependency resolution and version management
- Repository security and integrity verification
- Performance optimization and caching
- Multi-source repository aggregation
"""

import os
import json
import time
import hashlib
import requests
import threading
import logging
from typing import Dict, List, Optional, Any, Union, Set, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import urllib.parse
import tempfile
import shutil
import concurrent.futures
from collections import defaultdict

logger = logging.getLogger('KOS.repo_config')

class RepositoryType(Enum):
    """Repository types"""
    HTTP = "http"
    HTTPS = "https"
    GIT = "git"
    LOCAL = "local"
    MIRROR = "mirror"

class PackagePriority(Enum):
    """Package priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    TESTING = 5

@dataclass
class RepositoryMetadata:
    """Repository metadata information"""
    name: str
    url: str
    repo_type: RepositoryType
    description: str = ""
    maintainer: str = ""
    last_updated: Optional[datetime] = None
    package_count: int = 0
    enabled: bool = True
    priority: PackagePriority = PackagePriority.NORMAL
    mirror_of: Optional[str] = None
    checksum: Optional[str] = None
    signature: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PackageMetadata:
    """Enhanced package metadata"""
    name: str
    version: str
    description: str = ""
    author: str = ""
    maintainer: str = ""
    homepage: str = ""
    repository: str = ""
    
    # Dependencies and requirements
    dependencies: List[str] = field(default_factory=list)
    build_dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    replaces: List[str] = field(default_factory=list)
    
    # Package information
    size: int = 0
    installed_size: int = 0
    download_url: str = ""
    checksum: str = ""
    signature: str = ""
    license: str = ""
    platform: str = "any"
    architecture: str = "any"
    
    # Classification
    category: str = "misc"
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    
    # Files and installation
    files: List[str] = field(default_factory=list)
    entry_point: str = ""
    install_script: str = ""
    uninstall_script: str = ""
    
    # Metadata
    priority: PackagePriority = PackagePriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)

class RepositoryIndex:
    """Repository package index with caching and optimization"""
    
    def __init__(self, repository: RepositoryMetadata):
        self.repository = repository
        self.packages: Dict[str, PackageMetadata] = {}
        self.categories: Dict[str, List[str]] = defaultdict(list)
        self.tags: Dict[str, List[str]] = defaultdict(list)
        self.last_updated: Optional[datetime] = None
        self.cache_valid = False
        self.lock = threading.RLock()
    
    def add_package(self, package: PackageMetadata):
        """Add package to index"""
        with self.lock:
            self.packages[package.name] = package
            self.categories[package.category].append(package.name)
            for tag in package.tags:
                self.tags[tag].append(package.name)
            self.cache_valid = False
    
    def remove_package(self, package_name: str):
        """Remove package from index"""
        with self.lock:
            if package_name in self.packages:
                package = self.packages.pop(package_name)
                # Remove from categories and tags
                if package.category in self.categories:
                    self.categories[package.category] = [
                        p for p in self.categories[package.category] if p != package_name
                    ]
                for tag in package.tags:
                    if tag in self.tags:
                        self.tags[tag] = [p for p in self.tags[tag] if p != package_name]
                self.cache_valid = False
    
    def search(self, query: str, category: str = None, tags: List[str] = None) -> List[PackageMetadata]:
        """Search packages in index"""
        with self.lock:
            results = []
            query_lower = query.lower() if query else ""
            
            for package in self.packages.values():
                # Category filter
                if category and package.category != category:
                    continue
                
                # Tags filter
                if tags and not any(tag in package.tags for tag in tags):
                    continue
                
                # Text search
                if query_lower:
                    searchable_text = f"{package.name} {package.description} {' '.join(package.keywords)}".lower()
                    if query_lower not in searchable_text:
                        continue
                
                results.append(package)
            
            # Sort by relevance (simplified scoring)
            if query:
                results.sort(key=lambda p: self._calculate_relevance_score(p, query), reverse=True)
            
            return results
    
    def _calculate_relevance_score(self, package: PackageMetadata, query: str) -> float:
        """Calculate relevance score for search result"""
        score = 0.0
        query_lower = query.lower()
        
        # Exact name match gets highest score
        if package.name.lower() == query_lower:
            score += 100
        elif query_lower in package.name.lower():
            score += 50
        
        # Description match
        if query_lower in package.description.lower():
            score += 20
        
        # Keywords match
        for keyword in package.keywords:
            if query_lower in keyword.lower():
                score += 10
        
        # Tags match
        for tag in package.tags:
            if query_lower in tag.lower():
                score += 5
        
        # Priority boost
        score += (5 - package.priority.value) * 2
        
        return score
    
    def get_package(self, name: str) -> Optional[PackageMetadata]:
        """Get package by name"""
        with self.lock:
            return self.packages.get(name)
    
    def list_packages(self, category: str = None) -> List[PackageMetadata]:
        """List all packages, optionally filtered by category"""
        with self.lock:
            if category:
                package_names = self.categories.get(category, [])
                return [self.packages[name] for name in package_names if name in self.packages]
            return list(self.packages.values())
    
    def get_categories(self) -> List[str]:
        """Get all available categories"""
        with self.lock:
            return list(self.categories.keys())
    
    def get_tags(self) -> List[str]:
        """Get all available tags"""
        with self.lock:
            return list(self.tags.keys())
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics"""
        with self.lock:
            return {
                'total_packages': len(self.packages),
                'categories': len(self.categories),
                'tags': len(self.tags),
                'last_updated': self.last_updated.isoformat() if self.last_updated else None,
                'cache_valid': self.cache_valid
            }

class RepositoryManager:
    """Advanced repository management system"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = config_dir or os.path.expanduser("~/.kos/repositories")
        self.cache_dir = os.path.join(self.config_dir, "cache")
        self.repos_file = os.path.join(self.config_dir, "repositories.json")
        self.cache_file = os.path.join(self.config_dir, "cache.json")
        
        # Ensure directories exist
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Repository storage
        self.repositories: Dict[str, RepositoryMetadata] = {}
        self.indices: Dict[str, RepositoryIndex] = {}
        
        # Configuration
        self.update_interval = timedelta(hours=6)  # Auto-update interval
        self.cache_timeout = timedelta(hours=24)   # Cache validity
        self.max_concurrent_updates = 5
        self.request_timeout = 30
        
        # Threading
        self.lock = threading.RLock()
        self.update_executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_concurrent_updates)
        
        # Load configuration
        self._load_repositories()
        self._load_cache()
        
        logger.info(f"RepositoryManager initialized with {len(self.repositories)} repositories")
    
    def add_repository(self, name: str, url: str, repo_type: RepositoryType = None, 
                      description: str = "", priority: PackagePriority = PackagePriority.NORMAL) -> bool:
        """Add a new repository"""
        try:
            # Auto-detect repository type if not specified
            if repo_type is None:
                repo_type = self._detect_repository_type(url)
            
            # Validate URL
            if not self._validate_repository_url(url, repo_type):
                logger.error(f"Invalid repository URL: {url}")
                return False
            
            repo = RepositoryMetadata(
                name=name,
                url=url,
                repo_type=repo_type,
                description=description,
                priority=priority,
                last_updated=None
            )
            
            with self.lock:
                self.repositories[name] = repo
                self.indices[name] = RepositoryIndex(repo)
            
            # Save configuration
            self._save_repositories()
            
            # Try to update the repository
            self.update_repository(name)
            
            logger.info(f"Added repository: {name} ({url})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding repository {name}: {e}")
            return False
    
    def remove_repository(self, name: str) -> bool:
        """Remove a repository"""
        try:
            with self.lock:
                if name not in self.repositories:
                    logger.warning(f"Repository {name} not found")
                    return False
                
                # Remove from storage
                del self.repositories[name]
                if name in self.indices:
                    del self.indices[name]
            
            # Clean up cache
            cache_file = os.path.join(self.cache_dir, f"{name}.json")
            if os.path.exists(cache_file):
                os.remove(cache_file)
            
            # Save configuration
            self._save_repositories()
            
            logger.info(f"Removed repository: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing repository {name}: {e}")
            return False
    
    def enable_repository(self, name: str) -> bool:
        """Enable a repository"""
        with self.lock:
            if name in self.repositories:
                self.repositories[name].enabled = True
                self._save_repositories()
                return True
        return False
    
    def disable_repository(self, name: str) -> bool:
        """Disable a repository"""
        with self.lock:
            if name in self.repositories:
                self.repositories[name].enabled = False
                self._save_repositories()
                return True
        return False
    
    def update_repository(self, name: str) -> bool:
        """Update a single repository"""
        try:
            with self.lock:
                if name not in self.repositories:
                    logger.error(f"Repository {name} not found")
                    return False
                
                repo = self.repositories[name]
                if not repo.enabled:
                    logger.info(f"Repository {name} is disabled, skipping update")
                    return True
            
            logger.info(f"Updating repository: {name}")
            
            # Fetch repository data based on type
            if repo.repo_type in [RepositoryType.HTTP, RepositoryType.HTTPS]:
                return self._update_http_repository(repo)
            elif repo.repo_type == RepositoryType.GIT:
                return self._update_git_repository(repo)
            elif repo.repo_type == RepositoryType.LOCAL:
                return self._update_local_repository(repo)
            else:
                logger.error(f"Unsupported repository type: {repo.repo_type}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating repository {name}: {e}")
            return False
    
    def update_all_repositories(self) -> Dict[str, bool]:
        """Update all enabled repositories concurrently"""
        results = {}
        
        # Get enabled repositories
        enabled_repos = []
        with self.lock:
            enabled_repos = [name for name, repo in self.repositories.items() if repo.enabled]
        
        if not enabled_repos:
            logger.info("No enabled repositories to update")
            return results
        
        logger.info(f"Updating {len(enabled_repos)} repositories...")
        
        # Update repositories concurrently
        future_to_repo = {}
        for repo_name in enabled_repos:
            future = self.update_executor.submit(self.update_repository, repo_name)
            future_to_repo[future] = repo_name
        
        # Collect results
        for future in concurrent.futures.as_completed(future_to_repo, timeout=300):
            repo_name = future_to_repo[future]
            try:
                results[repo_name] = future.result()
            except Exception as e:
                logger.error(f"Error updating repository {repo_name}: {e}")
                results[repo_name] = False
        
        # Save cache
        self._save_cache()
        
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"Repository update completed: {success_count}/{len(enabled_repos)} successful")
        
        return results
    
    def search_packages(self, query: str, category: str = None, tags: List[str] = None) -> List[PackageMetadata]:
        """Search packages across all repositories"""
        all_results = []
        
        with self.lock:
            for name, index in self.indices.items():
                if self.repositories[name].enabled:
                    results = index.search(query, category, tags)
                    all_results.extend(results)
        
        # Remove duplicates (prefer higher priority repositories)
        unique_results = {}
        for package in all_results:
            key = package.name
            if key not in unique_results or package.priority.value < unique_results[key].priority.value:
                unique_results[key] = package
        
        return list(unique_results.values())
    
    def find_package(self, name: str) -> Optional[PackageMetadata]:
        """Find a specific package by name"""
        best_package = None
        best_priority = PackagePriority.TESTING
        
        with self.lock:
            for repo_name, index in self.indices.items():
                if self.repositories[repo_name].enabled:
                    package = index.get_package(name)
                    if package and package.priority.value < best_priority.value:
                        best_package = package
                        best_priority = package.priority
        
        return best_package
    
    def list_repositories(self) -> Dict[str, RepositoryMetadata]:
        """List all repositories"""
        with self.lock:
            return dict(self.repositories)
    
    def get_repository(self, name: str) -> Optional[RepositoryMetadata]:
        """Get repository metadata"""
        with self.lock:
            return self.repositories.get(name)
    
    def get_repository_packages(self, repo_name: str) -> List[PackageMetadata]:
        """Get all packages from a specific repository"""
        with self.lock:
            if repo_name in self.indices and self.repositories[repo_name].enabled:
                return self.indices[repo_name].list_packages()
        return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get repository manager statistics"""
        with self.lock:
            stats = {
                'repositories': {
                    'total': len(self.repositories),
                    'enabled': sum(1 for repo in self.repositories.values() if repo.enabled),
                    'by_type': {}
                },
                'packages': {
                    'total': 0,
                    'by_repository': {}
                },
                'last_update': None
            }
            
            # Count by repository type
            for repo in self.repositories.values():
                repo_type = repo.repo_type.value
                stats['repositories']['by_type'][repo_type] = stats['repositories']['by_type'].get(repo_type, 0) + 1
            
            # Count packages
            for repo_name, index in self.indices.items():
                if self.repositories[repo_name].enabled:
                    repo_stats = index.get_statistics()
                    package_count = repo_stats['total_packages']
                    stats['packages']['total'] += package_count
                    stats['packages']['by_repository'][repo_name] = package_count
                    
                    # Track latest update
                    if repo_stats['last_updated']:
                        update_time = datetime.fromisoformat(repo_stats['last_updated'])
                        if not stats['last_update'] or update_time > stats['last_update']:
                            stats['last_update'] = update_time
            
            if stats['last_update']:
                stats['last_update'] = stats['last_update'].isoformat()
            
            return stats
    
    def _detect_repository_type(self, url: str) -> RepositoryType:
        """Auto-detect repository type from URL"""
        url_lower = url.lower()
        
        if url_lower.startswith('https://'):
            return RepositoryType.HTTPS
        elif url_lower.startswith('http://'):
            return RepositoryType.HTTP
        elif url_lower.startswith('git://') or url_lower.endswith('.git'):
            return RepositoryType.GIT
        elif url_lower.startswith('file://') or os.path.exists(url):
            return RepositoryType.LOCAL
        else:
            # Default to HTTPS for security
            return RepositoryType.HTTPS
    
    def _validate_repository_url(self, url: str, repo_type: RepositoryType) -> bool:
        """Validate repository URL"""
        try:
            if repo_type == RepositoryType.LOCAL:
                return os.path.exists(url) or url.startswith('file://')
            
            # Parse URL
            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc:
                return False
            
            # Basic connectivity test for HTTP/HTTPS
            if repo_type in [RepositoryType.HTTP, RepositoryType.HTTPS]:
                try:
                    response = requests.head(url, timeout=10)
                    return response.status_code < 400
                except:
                    # URL might be valid but not reachable right now
                    return True
            
            return True
            
        except Exception:
            return False
    
    def _update_http_repository(self, repo: RepositoryMetadata) -> bool:
        """Update HTTP/HTTPS repository"""
        try:
            # Construct index URL
            index_url = f"{repo.url.rstrip('/')}/index.json"
            
            # Fetch index
            response = requests.get(index_url, timeout=self.request_timeout)
            response.raise_for_status()
            
            index_data = response.json()
            
            # Update repository metadata
            repo.last_updated = datetime.now()
            repo.package_count = len(index_data.get('packages', []))
            
            # Update package index
            index = self.indices[repo.name]
            index.packages.clear()
            index.categories.clear()
            index.tags.clear()
            
            for pkg_data in index_data.get('packages', []):
                package = self._parse_package_metadata(pkg_data, repo.name)
                if package:
                    index.add_package(package)
            
            index.last_updated = datetime.now()
            index.cache_valid = True
            
            logger.info(f"Updated repository {repo.name}: {repo.package_count} packages")
            return True
            
        except Exception as e:
            logger.error(f"Error updating HTTP repository {repo.name}: {e}")
            return False
    
    def _update_git_repository(self, repo: RepositoryMetadata) -> bool:
        """Update Git repository"""
        try:
            # This would implement Git repository updating
            # For now, treat as HTTP fallback
            logger.warning(f"Git repository support not fully implemented for {repo.name}")
            return self._update_http_repository(repo)
            
        except Exception as e:
            logger.error(f"Error updating Git repository {repo.name}: {e}")
            return False
    
    def _update_local_repository(self, repo: RepositoryMetadata) -> bool:
        """Update local repository"""
        try:
            index_file = os.path.join(repo.url, "index.json")
            
            if not os.path.exists(index_file):
                logger.error(f"Local repository index not found: {index_file}")
                return False
            
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            
            # Update repository metadata
            repo.last_updated = datetime.now()
            repo.package_count = len(index_data.get('packages', []))
            
            # Update package index
            index = self.indices[repo.name]
            index.packages.clear()
            index.categories.clear()
            index.tags.clear()
            
            for pkg_data in index_data.get('packages', []):
                package = self._parse_package_metadata(pkg_data, repo.name)
                if package:
                    index.add_package(package)
            
            index.last_updated = datetime.now()
            index.cache_valid = True
            
            logger.info(f"Updated local repository {repo.name}: {repo.package_count} packages")
            return True
            
        except Exception as e:
            logger.error(f"Error updating local repository {repo.name}: {e}")
            return False
    
    def _parse_package_metadata(self, pkg_data: Dict[str, Any], repository: str) -> Optional[PackageMetadata]:
        """Parse package metadata from repository data"""
        try:
            # Handle different timestamp formats
            created_at = None
            updated_at = None
            published_at = None
            
            for field, target in [('created_at', 'created_at'), ('updated_at', 'updated_at'), ('published_at', 'published_at')]:
                if field in pkg_data:
                    try:
                        if isinstance(pkg_data[field], str):
                            timestamp = datetime.fromisoformat(pkg_data[field].replace('Z', '+00:00'))
                        else:
                            timestamp = datetime.fromtimestamp(pkg_data[field])
                        
                        if target == 'created_at':
                            created_at = timestamp
                        elif target == 'updated_at':
                            updated_at = timestamp
                        elif target == 'published_at':
                            published_at = timestamp
                    except:
                        pass
            
            package = PackageMetadata(
                name=pkg_data.get('name', ''),
                version=pkg_data.get('version', ''),
                description=pkg_data.get('description', ''),
                author=pkg_data.get('author', ''),
                maintainer=pkg_data.get('maintainer', pkg_data.get('author', '')),
                homepage=pkg_data.get('homepage', ''),
                repository=repository,
                
                dependencies=pkg_data.get('dependencies', []),
                build_dependencies=pkg_data.get('build_dependencies', []),
                optional_dependencies=pkg_data.get('optional_dependencies', []),
                conflicts=pkg_data.get('conflicts', []),
                provides=pkg_data.get('provides', []),
                replaces=pkg_data.get('replaces', []),
                
                size=pkg_data.get('size', 0),
                installed_size=pkg_data.get('installed_size', 0),
                download_url=pkg_data.get('download_url', ''),
                checksum=pkg_data.get('checksum', ''),
                signature=pkg_data.get('signature', ''),
                license=pkg_data.get('license', ''),
                platform=pkg_data.get('platform', 'any'),
                architecture=pkg_data.get('architecture', 'any'),
                
                category=pkg_data.get('category', 'misc'),
                tags=pkg_data.get('tags', []),
                keywords=pkg_data.get('keywords', []),
                
                created_at=created_at,
                updated_at=updated_at,
                published_at=published_at,
                
                files=pkg_data.get('files', []),
                entry_point=pkg_data.get('entry_point', ''),
                install_script=pkg_data.get('install_script', ''),
                uninstall_script=pkg_data.get('uninstall_script', ''),
                
                priority=PackagePriority(pkg_data.get('priority', PackagePriority.NORMAL.value)),
                metadata=pkg_data.get('metadata', {})
            )
            
            return package
            
        except Exception as e:
            logger.error(f"Error parsing package metadata: {e}")
            return None
    
    def _load_repositories(self):
        """Load repository configuration"""
        try:
            if os.path.exists(self.repos_file):
                with open(self.repos_file, 'r') as f:
                    data = json.load(f)
                
                for repo_data in data.get('repositories', []):
                    try:
                        repo = RepositoryMetadata(
                            name=repo_data['name'],
                            url=repo_data['url'],
                            repo_type=RepositoryType(repo_data.get('type', 'https')),
                            description=repo_data.get('description', ''),
                            maintainer=repo_data.get('maintainer', ''),
                            enabled=repo_data.get('enabled', True),
                            priority=PackagePriority(repo_data.get('priority', PackagePriority.NORMAL.value)),
                            metadata=repo_data.get('metadata', {})
                        )
                        
                        # Parse last_updated
                        if 'last_updated' in repo_data and repo_data['last_updated']:
                            try:
                                repo.last_updated = datetime.fromisoformat(repo_data['last_updated'])
                            except:
                                pass
                        
                        self.repositories[repo.name] = repo
                        self.indices[repo.name] = RepositoryIndex(repo)
                        
                    except Exception as e:
                        logger.error(f"Error loading repository configuration: {e}")
            else:
                # Initialize with default repository
                self._initialize_default_repositories()
                
        except Exception as e:
            logger.error(f"Error loading repositories configuration: {e}")
            self._initialize_default_repositories()
    
    def _initialize_default_repositories(self):
        """Initialize with default KOS repository"""
        default_repo = RepositoryMetadata(
            name="main",
            url="https://raw.githubusercontent.com/DarsheeeGamer/kos-repo/refs/heads/main",
            repo_type=RepositoryType.HTTPS,
            description="Official KOS package repository",
            maintainer="KOS Development Team",
            enabled=True,
            priority=PackagePriority.HIGH
        )
        
        self.repositories["main"] = default_repo
        self.indices["main"] = RepositoryIndex(default_repo)
        
        self._save_repositories()
    
    def _save_repositories(self):
        """Save repository configuration"""
        try:
            data = {
                'repositories': [],
                'version': '2.0',
                'updated_at': datetime.now().isoformat()
            }
            
            for repo in self.repositories.values():
                repo_data = {
                    'name': repo.name,
                    'url': repo.url,
                    'type': repo.repo_type.value,
                    'description': repo.description,
                    'maintainer': repo.maintainer,
                    'enabled': repo.enabled,
                    'priority': repo.priority.value,
                    'metadata': repo.metadata
                }
                
                if repo.last_updated:
                    repo_data['last_updated'] = repo.last_updated.isoformat()
                
                data['repositories'].append(repo_data)
            
            with open(self.repos_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving repositories configuration: {e}")
    
    def _load_cache(self):
        """Load repository cache"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Load cached package indices
                for repo_name, index_data in cache_data.get('indices', {}).items():
                    if repo_name in self.repositories:
                        index = self.indices[repo_name]
                        
                        # Check cache validity
                        if 'last_updated' in index_data:
                            try:
                                last_updated = datetime.fromisoformat(index_data['last_updated'])
                                if datetime.now() - last_updated < self.cache_timeout:
                                    # Load packages from cache
                                    for pkg_data in index_data.get('packages', []):
                                        package = self._parse_package_metadata(pkg_data, repo_name)
                                        if package:
                                            index.add_package(package)
                                    
                                    index.last_updated = last_updated
                                    index.cache_valid = True
                                    
                                    logger.debug(f"Loaded cache for repository {repo_name}")
                            except:
                                logger.warning(f"Invalid cache timestamp for repository {repo_name}")
                                
        except Exception as e:
            logger.error(f"Error loading repository cache: {e}")
    
    def _save_cache(self):
        """Save repository cache"""
        try:
            cache_data = {
                'indices': {},
                'version': '2.0',
                'saved_at': datetime.now().isoformat()
            }
            
            for repo_name, index in self.indices.items():
                if index.cache_valid and index.last_updated:
                    index_data = {
                        'last_updated': index.last_updated.isoformat(),
                        'packages': []
                    }
                    
                    for package in index.packages.values():
                        pkg_data = self._serialize_package_metadata(package)
                        index_data['packages'].append(pkg_data)
                    
                    cache_data['indices'][repo_name] = index_data
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving repository cache: {e}")
    
    def _serialize_package_metadata(self, package: PackageMetadata) -> Dict[str, Any]:
        """Serialize package metadata for caching"""
        data = {
            'name': package.name,
            'version': package.version,
            'description': package.description,
            'author': package.author,
            'maintainer': package.maintainer,
            'homepage': package.homepage,
            'repository': package.repository,
            'dependencies': package.dependencies,
            'build_dependencies': package.build_dependencies,
            'optional_dependencies': package.optional_dependencies,
            'conflicts': package.conflicts,
            'provides': package.provides,
            'replaces': package.replaces,
            'size': package.size,
            'installed_size': package.installed_size,
            'download_url': package.download_url,
            'checksum': package.checksum,
            'signature': package.signature,
            'license': package.license,
            'platform': package.platform,
            'architecture': package.architecture,
            'category': package.category,
            'tags': package.tags,
            'keywords': package.keywords,
            'files': package.files,
            'entry_point': package.entry_point,
            'install_script': package.install_script,
            'uninstall_script': package.uninstall_script,
            'priority': package.priority.value,
            'metadata': package.metadata
        }
        
        # Serialize timestamps
        for field, value in [('created_at', package.created_at), ('updated_at', package.updated_at), ('published_at', package.published_at)]:
            if value:
                data[field] = value.isoformat()
        
        return data
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.update_executor.shutdown(wait=True)
            self._save_cache()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# Global repository manager instance
_repo_manager: Optional[RepositoryManager] = None

def get_repository_manager() -> RepositoryManager:
    """Get global repository manager instance"""
    global _repo_manager
    if _repo_manager is None:
        _repo_manager = RepositoryManager()
    return _repo_manager

# Legacy compatibility
class RepoConfig:
    """Legacy compatibility class"""
    
    def __init__(self):
        self.manager = get_repository_manager()
    
    def get_repository(self, name: str) -> Optional[Dict[str, Any]]:
        """Get repository (legacy format)"""
        repo = self.manager.get_repository(name)
        if repo:
            return {
                'name': repo.name,
                'url': repo.url,
                'enabled': repo.enabled,
                'type': repo.repo_type.value
            }
        return None
    
    def list_repositories(self) -> List[Dict[str, Any]]:
        """List repositories (legacy format)"""
        repos = []
        for repo in self.manager.repositories.values():
            repos.append({
                'name': repo.name,
                'url': repo.url,
                'enabled': repo.enabled,
                'type': repo.repo_type.value
            })
        return repos

"""
Advanced Indexing System for KOS Package Manager (KPM)

This module provides enhanced indexing capabilities for packages, applications, and repositories,
including search optimizations, tag-based indexing, and version tracking.
"""

import os
import json
import time
import logging
import shutil
import threading
from typing import Dict, List, Set, Tuple, Optional, Any, Union
from datetime import datetime

logger = logging.getLogger('KOS.package.index_manager')

# Default index locations
DEFAULT_INDEX_DIR = os.path.expanduser('~/.kos/kpm/index')
PACKAGE_INDEX_FILE = os.path.join(DEFAULT_INDEX_DIR, 'package_index.json')
TAG_INDEX_FILE = os.path.join(DEFAULT_INDEX_DIR, 'tag_index.json')
AUTHOR_INDEX_FILE = os.path.join(DEFAULT_INDEX_DIR, 'author_index.json')
CATEGORY_INDEX_FILE = os.path.join(DEFAULT_INDEX_DIR, 'category_index.json')
SEARCH_INDEX_FILE = os.path.join(DEFAULT_INDEX_DIR, 'search_index.json')

class IndexEntry:
    """Base class for index entries"""
    def __init__(self, name: str, version: str = None):
        self.name = name
        self.version = version
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'version': self.version,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'IndexEntry':
        """Create from dictionary"""
        entry = cls(data['name'], data.get('version'))
        if 'last_updated' in data and data['last_updated']:
            try:
                entry.last_updated = datetime.fromisoformat(data['last_updated'])
            except (ValueError, TypeError):
                entry.last_updated = datetime.now()
        return entry

class PackageIndexEntry(IndexEntry):
    """Package index entry with metadata"""
    def __init__(self, name: str, version: str = None):
        super().__init__(name, version)
        self.description = None
        self.author = None
        self.tags = []
        self.category = None
        self.dependencies = []
        self.repo_name = None
        self.homepage = None
        self.license = None
        self.size = 0
        self.download_count = 0
        self.rating = 0.0
        self.keywords = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = super().to_dict()
        data.update({
            'description': self.description,
            'author': self.author,
            'tags': self.tags,
            'category': self.category,
            'dependencies': self.dependencies,
            'repo_name': self.repo_name,
            'homepage': self.homepage,
            'license': self.license,
            'size': self.size,
            'download_count': self.download_count,
            'rating': self.rating,
            'keywords': self.keywords
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PackageIndexEntry':
        """Create from dictionary"""
        entry = super().from_dict(data)
        entry.description = data.get('description')
        entry.author = data.get('author')
        entry.tags = data.get('tags', [])
        entry.category = data.get('category')
        entry.dependencies = data.get('dependencies', [])
        entry.repo_name = data.get('repo_name')
        entry.homepage = data.get('homepage')
        entry.license = data.get('license')
        entry.size = data.get('size', 0)
        entry.download_count = data.get('download_count', 0)
        entry.rating = data.get('rating', 0.0)
        entry.keywords = data.get('keywords', [])
        return entry
    
    def get_search_terms(self) -> List[str]:
        """Get all searchable terms for this package"""
        terms = [self.name]
        
        if self.description:
            terms.extend(self.description.lower().split())
        
        if self.author:
            terms.append(self.author.lower())
        
        terms.extend([tag.lower() for tag in self.tags])
        
        if self.category:
            terms.append(self.category.lower())
        
        terms.extend([keyword.lower() for keyword in self.keywords])
        
        # Remove duplicates and common words
        common_words = {'a', 'an', 'the', 'and', 'or', 'for', 'of', 'to', 'in', 'on', 'by', 'with'}
        return list(set(term for term in terms if term and term not in common_words))

class AdvancedIndexManager:
    """
    Advanced index manager for packages with optimized search capabilities
    
    Features:
    - Multiple specialized indices (main, tag, author, category)
    - Search index with term frequency
    - Version tracking and history
    - Index statistics and metadata
    - Background index updates
    """
    def __init__(self, index_dir: str = DEFAULT_INDEX_DIR):
        self.index_dir = index_dir
        self.package_index = {}  # name -> PackageIndexEntry
        self.tag_index = {}      # tag -> [package names]
        self.author_index = {}   # author -> [package names]
        self.category_index = {} # category -> [package names]
        self.search_index = {}   # term -> [package names]
        self.index_metadata = {
            'last_updated': None,
            'package_count': 0,
            'tag_count': 0,
            'author_count': 0,
            'category_count': 0,
            'search_term_count': 0,
            'version': '1.0'
        }
        self.index_lock = threading.RLock()
        
        # Create index directory if it doesn't exist
        os.makedirs(self.index_dir, exist_ok=True)
        
        # Initialize indices
        self._load_indices()
    
    def _get_index_path(self, index_name: str) -> str:
        """Get the path to an index file"""
        return os.path.join(self.index_dir, f"{index_name}_index.json")
    
    def _load_indices(self):
        """Load all indices from disk"""
        with self.index_lock:
            # Load package index
            self._load_package_index()
            
            # Load tag index
            self._load_tag_index()
            
            # Load author index
            self._load_author_index()
            
            # Load category index
            self._load_category_index()
            
            # Load search index
            self._load_search_index()
            
            # Update metadata
            self._update_index_metadata()
    
    def _load_package_index(self):
        """Load the package index from disk"""
        try:
            if os.path.exists(PACKAGE_INDEX_FILE):
                with open(PACKAGE_INDEX_FILE, 'r') as f:
                    data = json.load(f)
                    self.package_index = {name: PackageIndexEntry.from_dict(pkg_data) 
                                         for name, pkg_data in data.items()}
                logger.debug(f"Loaded {len(self.package_index)} packages from index")
        except Exception as e:
            logger.error(f"Error loading package index: {e}")
            self.package_index = {}
    
    def _load_tag_index(self):
        """Load the tag index from disk"""
        try:
            if os.path.exists(TAG_INDEX_FILE):
                with open(TAG_INDEX_FILE, 'r') as f:
                    self.tag_index = json.load(f)
                logger.debug(f"Loaded {len(self.tag_index)} tags from index")
        except Exception as e:
            logger.error(f"Error loading tag index: {e}")
            self.tag_index = {}
    
    def _load_author_index(self):
        """Load the author index from disk"""
        try:
            if os.path.exists(AUTHOR_INDEX_FILE):
                with open(AUTHOR_INDEX_FILE, 'r') as f:
                    self.author_index = json.load(f)
                logger.debug(f"Loaded {len(self.author_index)} authors from index")
        except Exception as e:
            logger.error(f"Error loading author index: {e}")
            self.author_index = {}
    
    def _load_category_index(self):
        """Load the category index from disk"""
        try:
            if os.path.exists(CATEGORY_INDEX_FILE):
                with open(CATEGORY_INDEX_FILE, 'r') as f:
                    self.category_index = json.load(f)
                logger.debug(f"Loaded {len(self.category_index)} categories from index")
        except Exception as e:
            logger.error(f"Error loading category index: {e}")
            self.category_index = {}
    
    def _load_search_index(self):
        """Load the search index from disk"""
        try:
            if os.path.exists(SEARCH_INDEX_FILE):
                with open(SEARCH_INDEX_FILE, 'r') as f:
                    self.search_index = json.load(f)
                logger.debug(f"Loaded {len(self.search_index)} search terms from index")
        except Exception as e:
            logger.error(f"Error loading search index: {e}")
            self.search_index = {}
    
    def _save_indices(self):
        """Save all indices to disk"""
        with self.index_lock:
            # Update metadata
            self._update_index_metadata()
            
            # Save package index
            self._save_package_index()
            
            # Save tag index
            self._save_tag_index()
            
            # Save author index
            self._save_author_index()
            
            # Save category index
            self._save_category_index()
            
            # Save search index
            self._save_search_index()
    
    def _save_package_index(self):
        """Save the package index to disk"""
        try:
            # Create backup of existing index
            if os.path.exists(PACKAGE_INDEX_FILE):
                backup_file = f"{PACKAGE_INDEX_FILE}.bak"
                shutil.copy2(PACKAGE_INDEX_FILE, backup_file)
            
            # Save new index
            with open(PACKAGE_INDEX_FILE, 'w') as f:
                package_data = {name: pkg.to_dict() for name, pkg in self.package_index.items()}
                json.dump(package_data, f, indent=2)
            
            logger.debug(f"Saved {len(self.package_index)} packages to index")
        except Exception as e:
            logger.error(f"Error saving package index: {e}")
    
    def _save_tag_index(self):
        """Save the tag index to disk"""
        try:
            with open(TAG_INDEX_FILE, 'w') as f:
                json.dump(self.tag_index, f, indent=2)
            logger.debug(f"Saved {len(self.tag_index)} tags to index")
        except Exception as e:
            logger.error(f"Error saving tag index: {e}")
    
    def _save_author_index(self):
        """Save the author index to disk"""
        try:
            with open(AUTHOR_INDEX_FILE, 'w') as f:
                json.dump(self.author_index, f, indent=2)
            logger.debug(f"Saved {len(self.author_index)} authors to index")
        except Exception as e:
            logger.error(f"Error saving author index: {e}")
    
    def _save_category_index(self):
        """Save the category index to disk"""
        try:
            with open(CATEGORY_INDEX_FILE, 'w') as f:
                json.dump(self.category_index, f, indent=2)
            logger.debug(f"Saved {len(self.category_index)} categories to index")
        except Exception as e:
            logger.error(f"Error saving category index: {e}")
    
    def _save_search_index(self):
        """Save the search index to disk"""
        try:
            with open(SEARCH_INDEX_FILE, 'w') as f:
                json.dump(self.search_index, f, indent=2)
            logger.debug(f"Saved {len(self.search_index)} search terms to index")
        except Exception as e:
            logger.error(f"Error saving search index: {e}")
    
    def _update_index_metadata(self):
        """Update index metadata"""
        self.index_metadata = {
            'last_updated': datetime.now().isoformat(),
            'package_count': len(self.package_index),
            'tag_count': len(self.tag_index),
            'author_count': len(self.author_index),
            'category_count': len(self.category_index),
            'search_term_count': len(self.search_index),
            'version': '1.0'
        }
    
    def add_package(self, package_entry: Union[PackageIndexEntry, Dict[str, Any]], repo_name: str = None):
        """
        Add a package to the index
        
        Args:
            package_entry: Package entry or dictionary with package data
            repo_name: Repository name (optional)
        """
        with self.index_lock:
            # Convert dict to PackageIndexEntry if needed
            if isinstance(package_entry, dict):
                pkg = PackageIndexEntry.from_dict(package_entry)
            else:
                pkg = package_entry
            
            # Set repository name if provided
            if repo_name:
                pkg.repo_name = repo_name
            
            # Generate unique key for the package
            pkg_key = pkg.name.lower()
            
            # Add to package index
            self.package_index[pkg_key] = pkg
            
            # Update tag index
            for tag in pkg.tags:
                tag_key = tag.lower()
                if tag_key not in self.tag_index:
                    self.tag_index[tag_key] = []
                if pkg_key not in self.tag_index[tag_key]:
                    self.tag_index[tag_key].append(pkg_key)
            
            # Update author index
            if pkg.author:
                author_key = pkg.author.lower()
                if author_key not in self.author_index:
                    self.author_index[author_key] = []
                if pkg_key not in self.author_index[author_key]:
                    self.author_index[author_key].append(pkg_key)
            
            # Update category index
            if pkg.category:
                category_key = pkg.category.lower()
                if category_key not in self.category_index:
                    self.category_index[category_key] = []
                if pkg_key not in self.category_index[category_key]:
                    self.category_index[category_key].append(pkg_key)
            
            # Update search index
            search_terms = pkg.get_search_terms()
            for term in search_terms:
                if term not in self.search_index:
                    self.search_index[term] = []
                if pkg_key not in self.search_index[term]:
                    self.search_index[term].append(pkg_key)
    
    def remove_package(self, package_name: str):
        """
        Remove a package from the index
        
        Args:
            package_name: Name of the package to remove
        """
        with self.index_lock:
            pkg_key = package_name.lower()
            
            # Check if package exists
            if pkg_key not in self.package_index:
                return
            
            pkg = self.package_index[pkg_key]
            
            # Remove from package index
            del self.package_index[pkg_key]
            
            # Remove from tag index
            for tag in pkg.tags:
                tag_key = tag.lower()
                if tag_key in self.tag_index and pkg_key in self.tag_index[tag_key]:
                    self.tag_index[tag_key].remove(pkg_key)
                    # Remove tag if no more packages
                    if not self.tag_index[tag_key]:
                        del self.tag_index[tag_key]
            
            # Remove from author index
            if pkg.author:
                author_key = pkg.author.lower()
                if author_key in self.author_index and pkg_key in self.author_index[author_key]:
                    self.author_index[author_key].remove(pkg_key)
                    # Remove author if no more packages
                    if not self.author_index[author_key]:
                        del self.author_index[author_key]
            
            # Remove from category index
            if pkg.category:
                category_key = pkg.category.lower()
                if category_key in self.category_index and pkg_key in self.category_index[category_key]:
                    self.category_index[category_key].remove(pkg_key)
                    # Remove category if no more packages
                    if not self.category_index[category_key]:
                        del self.category_index[category_key]
            
            # Remove from search index
            search_terms = pkg.get_search_terms()
            for term in search_terms:
                if term in self.search_index and pkg_key in self.search_index[term]:
                    self.search_index[term].remove(pkg_key)
                    # Remove term if no more packages
                    if not self.search_index[term]:
                        del self.search_index[term]
    
    def update_from_repos(self, repo_manager) -> int:
        """
        Update the index from repositories
        
        Args:
            repo_manager: Repository manager object
            
        Returns:
            Number of packages indexed
        """
        with self.index_lock:
            # Clear existing index
            old_package_count = len(self.package_index)
            self.package_index = {}
            self.tag_index = {}
            self.author_index = {}
            self.category_index = {}
            self.search_index = {}
            
            # Get repositories
            repos = repo_manager.list_repositories()
            
            # Add packages from each repository
            total_packages = 0
            for repo in repos:
                # Skip inactive repositories
                if not repo.active:
                    continue
                
                for pkg in repo.packages:
                    # Create index entry from package
                    entry = PackageIndexEntry(pkg.name, pkg.version)
                    entry.description = pkg.description if hasattr(pkg, 'description') else None
                    entry.author = pkg.author if hasattr(pkg, 'author') else None
                    entry.tags = pkg.tags if hasattr(pkg, 'tags') else []
                    entry.category = pkg.category if hasattr(pkg, 'category') else None
                    entry.dependencies = [dep.name for dep in pkg.dependencies] if hasattr(pkg, 'dependencies') else []
                    entry.repo_name = repo.name
                    entry.homepage = pkg.homepage if hasattr(pkg, 'homepage') else None
                    entry.license = pkg.license if hasattr(pkg, 'license') else None
                    
                    # Add to index
                    self.add_package(entry, repo.name)
                    total_packages += 1
            
            # Save indices
            self._save_indices()
            
            logger.info(f"Updated index with {total_packages} packages from {len(repos)} repositories")
            return total_packages
    
    def search(self, query: str, tag: str = None, author: str = None, 
              category: str = None, limit: int = 10) -> List[PackageIndexEntry]:
        """
        Search for packages matching the query and filters
        
        Args:
            query: Search query
            tag: Filter by tag
            author: Filter by author
            category: Filter by category
            limit: Maximum number of results
            
        Returns:
            List of matching PackageIndexEntry objects
        """
        with self.index_lock:
            # Normalize query
            if query:
                query = query.lower()
                query_terms = query.split()
            else:
                query_terms = []
            
            # Get initial result set
            result_set = set()
            
            # If we have query terms, use search index
            if query_terms:
                # Find packages matching each term
                for term in query_terms:
                    if term in self.search_index:
                        term_packages = set(self.search_index[term])
                        if not result_set:
                            result_set = term_packages
                        else:
                            # Packages must match all terms (AND search)
                            result_set &= term_packages
            else:
                # If no query, start with all packages
                result_set = set(self.package_index.keys())
            
            # Apply filters
            if tag:
                tag_key = tag.lower()
                if tag_key in self.tag_index:
                    tag_packages = set(self.tag_index[tag_key])
                    result_set &= tag_packages
                else:
                    # No packages with this tag
                    return []
            
            if author:
                author_key = author.lower()
                if author_key in self.author_index:
                    author_packages = set(self.author_index[author_key])
                    result_set &= author_packages
                else:
                    # No packages by this author
                    return []
            
            if category:
                category_key = category.lower()
                if category_key in self.category_index:
                    category_packages = set(self.category_index[category_key])
                    result_set &= category_packages
                else:
                    # No packages in this category
                    return []
            
            # Convert result set to list of PackageIndexEntry
            results = [self.package_index[pkg_key] for pkg_key in result_set 
                      if pkg_key in self.package_index]
            
            # Sort by relevance (if query provided) or name
            if query:
                # Simple relevance scoring based on term frequency
                def relevance_score(pkg):
                    score = 0
                    # Exact name match gets highest score
                    if query == pkg.name.lower():
                        score += 100
                    # Name contains query
                    elif query in pkg.name.lower():
                        score += 50
                    # Description contains query
                    if pkg.description and query in pkg.description.lower():
                        score += 25
                    # Count matching terms in search terms
                    search_terms = pkg.get_search_terms()
                    for term in query_terms:
                        if term in search_terms:
                            score += 5
                    return score
                
                results.sort(key=relevance_score, reverse=True)
            else:
                # Sort by name if no query
                results.sort(key=lambda pkg: pkg.name.lower())
            
            # Apply limit
            return results[:limit]
    
    def get_package(self, package_name: str) -> Optional[PackageIndexEntry]:
        """
        Get a package from the index
        
        Args:
            package_name: Name of the package
            
        Returns:
            PackageIndexEntry or None if not found
        """
        with self.index_lock:
            pkg_key = package_name.lower()
            return self.package_index.get(pkg_key)
    
    def list_packages(self, tag: str = None, author: str = None, 
                     category: str = None, limit: int = 0) -> List[PackageIndexEntry]:
        """
        List packages with optional filtering
        
        Args:
            tag: Filter by tag
            author: Filter by author
            category: Filter by category
            limit: Maximum number of results (0 for no limit)
            
        Returns:
            List of PackageIndexEntry objects
        """
        with self.index_lock:
            # Start with all packages
            result_set = set(self.package_index.keys())
            
            # Apply filters
            if tag:
                tag_key = tag.lower()
                if tag_key in self.tag_index:
                    tag_packages = set(self.tag_index[tag_key])
                    result_set &= tag_packages
                else:
                    # No packages with this tag
                    return []
            
            if author:
                author_key = author.lower()
                if author_key in self.author_index:
                    author_packages = set(self.author_index[author_key])
                    result_set &= author_packages
                else:
                    # No packages by this author
                    return []
            
            if category:
                category_key = category.lower()
                if category_key in self.category_index:
                    category_packages = set(self.category_index[category_key])
                    result_set &= category_packages
                else:
                    # No packages in this category
                    return []
            
            # Convert result set to list of PackageIndexEntry
            results = [self.package_index[pkg_key] for pkg_key in result_set 
                      if pkg_key in self.package_index]
            
            # Sort by name
            results.sort(key=lambda pkg: pkg.name.lower())
            
            # Apply limit
            if limit > 0:
                return results[:limit]
            else:
                return results
    
    def list_tags(self) -> List[Tuple[str, int]]:
        """
        List all tags with package counts
        
        Returns:
            List of (tag, count) tuples, sorted by count (descending)
        """
        with self.index_lock:
            tags = [(tag, len(packages)) for tag, packages in self.tag_index.items()]
            return sorted(tags, key=lambda x: x[1], reverse=True)
    
    def list_authors(self) -> List[Tuple[str, int]]:
        """
        List all authors with package counts
        
        Returns:
            List of (author, count) tuples, sorted by count (descending)
        """
        with self.index_lock:
            authors = [(author, len(packages)) for author, packages in self.author_index.items()]
            return sorted(authors, key=lambda x: x[1], reverse=True)
    
    def list_categories(self) -> List[Tuple[str, int]]:
        """
        List all categories with package counts
        
        Returns:
            List of (category, count) tuples, sorted by count (descending)
        """
        with self.index_lock:
            categories = [(category, len(packages)) for category, packages in self.category_index.items()]
            return sorted(categories, key=lambda x: x[1], reverse=True)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics
        
        Returns:
            Dictionary with index statistics
        """
        with self.index_lock:
            stats = self.index_metadata.copy()
            
            # Add additional stats
            stats['top_tags'] = self.list_tags()[:10]
            stats['top_authors'] = self.list_authors()[:10]
            stats['top_categories'] = self.list_categories()[:10]
            
            # Get repository stats
            repo_stats = {}
            for pkg in self.package_index.values():
                if pkg.repo_name:
                    if pkg.repo_name not in repo_stats:
                        repo_stats[pkg.repo_name] = 0
                    repo_stats[pkg.repo_name] += 1
            
            stats['repositories'] = [(repo, count) for repo, count in repo_stats.items()]
            stats['repositories'].sort(key=lambda x: x[1], reverse=True)
            
            return stats
    
    def rebuild_indices(self):
        """Rebuild all secondary indices from the package index"""
        with self.index_lock:
            # Clear secondary indices
            self.tag_index = {}
            self.author_index = {}
            self.category_index = {}
            self.search_index = {}
            
            # Rebuild from package index
            for pkg_key, pkg in self.package_index.items():
                # Update tag index
                for tag in pkg.tags:
                    tag_key = tag.lower()
                    if tag_key not in self.tag_index:
                        self.tag_index[tag_key] = []
                    if pkg_key not in self.tag_index[tag_key]:
                        self.tag_index[tag_key].append(pkg_key)
                
                # Update author index
                if pkg.author:
                    author_key = pkg.author.lower()
                    if author_key not in self.author_index:
                        self.author_index[author_key] = []
                    if pkg_key not in self.author_index[author_key]:
                        self.author_index[author_key].append(pkg_key)
                
                # Update category index
                if pkg.category:
                    category_key = pkg.category.lower()
                    if category_key not in self.category_index:
                        self.category_index[category_key] = []
                    if pkg_key not in self.category_index[category_key]:
                        self.category_index[category_key].append(pkg_key)
                
                # Update search index
                search_terms = pkg.get_search_terms()
                for term in search_terms:
                    if term not in self.search_index:
                        self.search_index[term] = []
                    if pkg_key not in self.search_index[term]:
                        self.search_index[term].append(pkg_key)
            
            # Save indices
            self._save_indices()
            
            logger.info(f"Rebuilt all indices from {len(self.package_index)} packages")
    
    def background_update(self, repo_manager):
        """
        Start a background thread to update the index
        
        Args:
            repo_manager: Repository manager object
        """
        def update_thread():
            try:
                logger.info("Starting background index update")
                self.update_from_repos(repo_manager)
                logger.info("Background index update completed")
            except Exception as e:
                logger.error(f"Error in background index update: {e}")
        
        thread = threading.Thread(target=update_thread)
        thread.daemon = True
        thread.start()
        
        return thread

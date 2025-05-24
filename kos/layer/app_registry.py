"""
AppRegistry Component for KLayer

This module provides application registry capabilities for KOS,
managing application metadata, versions, and dependencies.
"""

import os
import sys
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Callable

logger = logging.getLogger('KOS.layer.app_registry')

class AppMetadata:
    """Application metadata information"""
    
    def __init__(self, app_id: str, name: str, version: str, description: str = None, author: str = None):
        """
        Initialize application metadata
        
        Args:
            app_id: Application ID
            name: Application name
            version: Application version
            description: Application description
            author: Application author
        """
        self.app_id = app_id
        self.name = name
        self.version = version
        self.description = description
        self.author = author
        self.executable = None
        self.icon_path = None
        self.website = None
        self.install_date = None
        self.last_updated = None
        self.dependencies = []
        self.tags = []
        self.category = None
        self.entry_points = {}
        self.permissions = []
        self.config = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "app_id": self.app_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "executable": self.executable,
            "icon_path": self.icon_path,
            "website": self.website,
            "install_date": self.install_date,
            "last_updated": self.last_updated,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "category": self.category,
            "entry_points": self.entry_points,
            "permissions": self.permissions,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppMetadata':
        """
        Create AppMetadata from dictionary
        
        Args:
            data: Dictionary with app metadata
            
        Returns:
            AppMetadata object
        """
        app_id = data.get("app_id")
        name = data.get("name")
        version = data.get("version")
        
        if not app_id or not name or not version:
            raise ValueError("Missing required fields (app_id, name, version)")
        
        metadata = cls(app_id, name, version, data.get("description"), data.get("author"))
        
        # Set additional fields
        metadata.executable = data.get("executable")
        metadata.icon_path = data.get("icon_path")
        metadata.website = data.get("website")
        metadata.install_date = data.get("install_date")
        metadata.last_updated = data.get("last_updated")
        metadata.dependencies = data.get("dependencies", [])
        metadata.tags = data.get("tags", [])
        metadata.category = data.get("category")
        metadata.entry_points = data.get("entry_points", {})
        metadata.permissions = data.get("permissions", [])
        metadata.config = data.get("config", {})
        
        return metadata

class AppRegistry:
    """
    Manages KOS applications registry
    
    This class provides methods to register, query, and manage
    applications within the KOS environment.
    """
    
    def __init__(self):
        """Initialize the AppRegistry component"""
        self.lock = threading.RLock()
        
        # App registry
        self.apps = {}  # app_id -> AppMetadata
        
        # App indices
        self.app_by_tag = {}  # tag -> [app_id]
        self.app_by_category = {}  # category -> [app_id]
        self.app_by_author = {}  # author -> [app_id]
        
        # Watchers for app changes
        self.watchers = []  # [(app_id_pattern, callback)]
        
        # Load app registry
        self._load_registry()
        
        logger.debug("AppRegistry component initialized")
    
    def _load_registry(self):
        """Load app registry from disk"""
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Load from registry file
            registry_file = os.path.join(kos_home, 'registry', 'apps.json')
            
            if os.path.exists(registry_file):
                with open(registry_file, 'r') as f:
                    registry_data = json.load(f)
                    
                    # Load apps
                    if "apps" in registry_data and isinstance(registry_data["apps"], dict):
                        for app_id, app_data in registry_data["apps"].items():
                            try:
                                metadata = AppMetadata.from_dict(app_data)
                                self.apps[app_id] = metadata
                                
                                # Update indices
                                self._update_indices(metadata)
                            except Exception as e:
                                logger.error(f"Error loading app metadata for {app_id}: {e}")
                    
                    logger.debug(f"Loaded registry with {len(self.apps)} applications")
        except Exception as e:
            logger.error(f"Error loading app registry: {e}")
    
    def _save_registry(self):
        """Save app registry to disk"""
        try:
            # Get KOS home directory
            kos_home = os.environ.get('KOS_HOME', os.path.expanduser('~/.kos'))
            
            # Create registry directory if it doesn't exist
            registry_dir = os.path.join(kos_home, 'registry')
            os.makedirs(registry_dir, exist_ok=True)
            
            # Save to registry file
            registry_file = os.path.join(registry_dir, 'apps.json')
            
            with self.lock:
                registry_data = {
                    "last_updated": datetime.now().isoformat(),
                    "apps": {app_id: metadata.to_dict() for app_id, metadata in self.apps.items()}
                }
                
                with open(registry_file, 'w') as f:
                    json.dump(registry_data, f, indent=2)
            
            logger.debug("Saved app registry to disk")
        except Exception as e:
            logger.error(f"Error saving app registry: {e}")
    
    def _update_indices(self, metadata: AppMetadata):
        """
        Update app indices
        
        Args:
            metadata: App metadata
        """
        app_id = metadata.app_id
        
        # Update tag index
        for tag in metadata.tags:
            if tag not in self.app_by_tag:
                self.app_by_tag[tag] = []
            
            if app_id not in self.app_by_tag[tag]:
                self.app_by_tag[tag].append(app_id)
        
        # Update category index
        if metadata.category:
            if metadata.category not in self.app_by_category:
                self.app_by_category[metadata.category] = []
            
            if app_id not in self.app_by_category[metadata.category]:
                self.app_by_category[metadata.category].append(app_id)
        
        # Update author index
        if metadata.author:
            if metadata.author not in self.app_by_author:
                self.app_by_author[metadata.author] = []
            
            if app_id not in self.app_by_author[metadata.author]:
                self.app_by_author[metadata.author].append(app_id)
    
    def _remove_from_indices(self, metadata: AppMetadata):
        """
        Remove app from indices
        
        Args:
            metadata: App metadata
        """
        app_id = metadata.app_id
        
        # Remove from tag index
        for tag in metadata.tags:
            if tag in self.app_by_tag and app_id in self.app_by_tag[tag]:
                self.app_by_tag[tag].remove(app_id)
                
                # Remove empty tag
                if not self.app_by_tag[tag]:
                    del self.app_by_tag[tag]
        
        # Remove from category index
        if metadata.category and metadata.category in self.app_by_category:
            if app_id in self.app_by_category[metadata.category]:
                self.app_by_category[metadata.category].remove(app_id)
                
                # Remove empty category
                if not self.app_by_category[metadata.category]:
                    del self.app_by_category[metadata.category]
        
        # Remove from author index
        if metadata.author and metadata.author in self.app_by_author:
            if app_id in self.app_by_author[metadata.author]:
                self.app_by_author[metadata.author].remove(app_id)
                
                # Remove empty author
                if not self.app_by_author[metadata.author]:
                    del self.app_by_author[metadata.author]
    
    def _notify_watchers(self, app_id: str, event_type: str, metadata: AppMetadata):
        """
        Notify watchers of app changes
        
        Args:
            app_id: App ID
            event_type: Event type (registered, updated, unregistered)
            metadata: App metadata
        """
        # Create event data
        event_data = {
            "event_type": event_type,
            "app_id": app_id,
            "metadata": metadata.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Call watchers
        for pattern, callback in self.watchers:
            if self._match_pattern(app_id, pattern):
                try:
                    callback(event_data)
                except Exception as e:
                    logger.error(f"Error in app watcher callback: {e}")
    
    def _match_pattern(self, app_id: str, pattern: str) -> bool:
        """
        Check if app ID matches pattern
        
        Args:
            app_id: App ID
            pattern: Pattern to match
            
        Returns:
            Whether the app ID matches the pattern
        """
        # Simple wildcard matching
        if pattern == "*":
            return True
        
        if pattern.endswith("*"):
            return app_id.startswith(pattern[:-1])
        
        if pattern.startswith("*"):
            return app_id.endswith(pattern[1:])
        
        return app_id == pattern
    
    def register_app(self, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register an application
        
        Args:
            app_data: Application data
            
        Returns:
            Dictionary with registration status
        """
        try:
            # Validate required fields
            if "app_id" not in app_data or "name" not in app_data or "version" not in app_data:
                return {
                    "success": False,
                    "error": "Missing required fields (app_id, name, version)"
                }
            
            app_id = app_data["app_id"]
            
            # Check for existing app
            with self.lock:
                if app_id in self.apps:
                    # Update existing app
                    return self.update_app(app_id, app_data)
            
            # Create metadata
            metadata = AppMetadata.from_dict(app_data)
            
            # Set install date
            metadata.install_date = datetime.now().isoformat()
            metadata.last_updated = metadata.install_date
            
            # Register app
            with self.lock:
                self.apps[app_id] = metadata
                
                # Update indices
                self._update_indices(metadata)
                
                # Save registry
                self._save_registry()
            
            # Notify watchers
            self._notify_watchers(app_id, "registered", metadata)
            
            logger.info(f"Registered application: {app_id}")
            
            return {
                "success": True,
                "app_id": app_id,
                "action": "registered"
            }
        except Exception as e:
            logger.error(f"Error registering application: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_app(self, app_id: str, app_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an application
        
        Args:
            app_id: Application ID
            app_data: Updated application data
            
        Returns:
            Dictionary with update status
        """
        try:
            with self.lock:
                if app_id not in self.apps:
                    return {
                        "success": False,
                        "error": f"Application not registered: {app_id}"
                    }
                
                # Get existing metadata
                metadata = self.apps[app_id]
                
                # Remove from indices
                self._remove_from_indices(metadata)
                
                # Update fields
                for key, value in app_data.items():
                    if key != "app_id" and hasattr(metadata, key):
                        setattr(metadata, key, value)
                
                # Update last_updated timestamp
                metadata.last_updated = datetime.now().isoformat()
                
                # Update indices
                self._update_indices(metadata)
                
                # Save registry
                self._save_registry()
            
            # Notify watchers
            self._notify_watchers(app_id, "updated", metadata)
            
            logger.info(f"Updated application: {app_id}")
            
            return {
                "success": True,
                "app_id": app_id,
                "action": "updated"
            }
        except Exception as e:
            logger.error(f"Error updating application: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def unregister_app(self, app_id: str) -> Dict[str, Any]:
        """
        Unregister an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with unregistration status
        """
        try:
            with self.lock:
                if app_id not in self.apps:
                    return {
                        "success": False,
                        "error": f"Application not registered: {app_id}"
                    }
                
                # Get metadata for notification
                metadata = self.apps[app_id]
                
                # Remove from indices
                self._remove_from_indices(metadata)
                
                # Remove app
                del self.apps[app_id]
                
                # Save registry
                self._save_registry()
            
            # Notify watchers
            self._notify_watchers(app_id, "unregistered", metadata)
            
            logger.info(f"Unregistered application: {app_id}")
            
            return {
                "success": True,
                "app_id": app_id,
                "action": "unregistered"
            }
        except Exception as e:
            logger.error(f"Error unregistering application: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_app_info(self, app_id: str) -> Dict[str, Any]:
        """
        Get information about an application
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with application information
        """
        with self.lock:
            if app_id not in self.apps:
                return {
                    "success": False,
                    "error": f"Application not found: {app_id}"
                }
            
            metadata = self.apps[app_id]
            
            return {
                "success": True,
                "app_id": app_id,
                "metadata": metadata.to_dict()
            }
    
    def list_apps(self, category: Optional[str] = None, tag: Optional[str] = None, 
                 author: Optional[str] = None) -> Dict[str, Any]:
        """
        List registered applications
        
        Args:
            category: Filter by category
            tag: Filter by tag
            author: Filter by author
            
        Returns:
            Dictionary with application list
        """
        with self.lock:
            app_ids = set(self.apps.keys())
            
            # Apply filters
            if category:
                category_apps = set(self.app_by_category.get(category, []))
                app_ids = app_ids.intersection(category_apps)
            
            if tag:
                tag_apps = set(self.app_by_tag.get(tag, []))
                app_ids = app_ids.intersection(tag_apps)
            
            if author:
                author_apps = set(self.app_by_author.get(author, []))
                app_ids = app_ids.intersection(author_apps)
            
            # Get app info
            apps = []
            for app_id in app_ids:
                metadata = self.apps[app_id]
                apps.append({
                    "app_id": app_id,
                    "name": metadata.name,
                    "version": metadata.version,
                    "description": metadata.description,
                    "author": metadata.author,
                    "category": metadata.category,
                    "tags": metadata.tags
                })
            
            return {
                "success": True,
                "apps": apps,
                "count": len(apps)
            }
    
    def search_apps(self, query: str) -> Dict[str, Any]:
        """
        Search for applications
        
        Args:
            query: Search query
            
        Returns:
            Dictionary with search results
        """
        query = query.lower()
        results = []
        
        with self.lock:
            for app_id, metadata in self.apps.items():
                # Check if query matches app_id, name, description, or tags
                if (query in app_id.lower() or
                    query in metadata.name.lower() or
                    (metadata.description and query in metadata.description.lower()) or
                    any(query in tag.lower() for tag in metadata.tags)):
                    
                    results.append({
                        "app_id": app_id,
                        "name": metadata.name,
                        "version": metadata.version,
                        "description": metadata.description,
                        "author": metadata.author,
                        "category": metadata.category,
                        "tags": metadata.tags
                    })
        
        return {
            "success": True,
            "results": results,
            "count": len(results),
            "query": query
        }
    
    def get_app_categories(self) -> Dict[str, Any]:
        """
        Get all application categories
        
        Returns:
            Dictionary with categories and app counts
        """
        with self.lock:
            categories = {}
            
            for category, app_ids in self.app_by_category.items():
                categories[category] = len(app_ids)
            
            return {
                "success": True,
                "categories": categories,
                "count": len(categories)
            }
    
    def get_app_tags(self) -> Dict[str, Any]:
        """
        Get all application tags
        
        Returns:
            Dictionary with tags and app counts
        """
        with self.lock:
            tags = {}
            
            for tag, app_ids in self.app_by_tag.items():
                tags[tag] = len(app_ids)
            
            return {
                "success": True,
                "tags": tags,
                "count": len(tags)
            }
    
    def get_app_authors(self) -> Dict[str, Any]:
        """
        Get all application authors
        
        Returns:
            Dictionary with authors and app counts
        """
        with self.lock:
            authors = {}
            
            for author, app_ids in self.app_by_author.items():
                authors[author] = len(app_ids)
            
            return {
                "success": True,
                "authors": authors,
                "count": len(authors)
            }
    
    def register_watcher(self, app_id_pattern: str, callback: Callable) -> Dict[str, Any]:
        """
        Register a watcher for app changes
        
        Args:
            app_id_pattern: App ID pattern (* for all, prefix* for prefix, *suffix for suffix)
            callback: Callback function
            
        Returns:
            Dictionary with registration status
        """
        with self.lock:
            self.watchers.append((app_id_pattern, callback))
            
            logger.debug(f"Registered app watcher for pattern: {app_id_pattern}")
            
            return {
                "success": True,
                "pattern": app_id_pattern
            }
    
    def unregister_watcher(self, app_id_pattern: str, callback: Callable) -> Dict[str, Any]:
        """
        Unregister a watcher
        
        Args:
            app_id_pattern: App ID pattern
            callback: Callback function
            
        Returns:
            Dictionary with unregistration status
        """
        with self.lock:
            for i, (pattern, cb) in enumerate(self.watchers):
                if pattern == app_id_pattern and cb == callback:
                    self.watchers.pop(i)
                    
                    logger.debug(f"Unregistered app watcher for pattern: {app_id_pattern}")
                    
                    return {
                        "success": True,
                        "pattern": app_id_pattern
                    }
            
            return {
                "success": False,
                "error": "Watcher not found"
            }
    
    def check_dependency(self, dependency: str) -> Dict[str, Any]:
        """
        Check if a dependency is satisfied
        
        Args:
            dependency: Dependency string (app_id or app_id>=version)
            
        Returns:
            Dictionary with dependency check status
        """
        try:
            # Parse dependency
            if ">=" in dependency:
                app_id, version = dependency.split(">=")
                app_id = app_id.strip()
                version = version.strip()
                check_version = True
            else:
                app_id = dependency.strip()
                version = None
                check_version = False
            
            # Check if app exists
            with self.lock:
                if app_id not in self.apps:
                    return {
                        "success": False,
                        "satisfied": False,
                        "error": f"Dependency not found: {app_id}",
                        "dependency": dependency
                    }
                
                metadata = self.apps[app_id]
                
                # Check version if needed
                if check_version:
                    # Simple version comparison (assumes semantic versioning)
                    if self._compare_versions(metadata.version, version) < 0:
                        return {
                            "success": True,
                            "satisfied": False,
                            "error": f"Version requirement not met: {app_id}>={version}, found {metadata.version}",
                            "dependency": dependency,
                            "installed_version": metadata.version
                        }
                
                return {
                    "success": True,
                    "satisfied": True,
                    "dependency": dependency,
                    "installed_version": metadata.version
                }
        except Exception as e:
            logger.error(f"Error checking dependency: {e}")
            return {
                "success": False,
                "error": str(e),
                "dependency": dependency
            }
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """
        Compare two version strings
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if version1 == version2, 1 if version1 > version2
        """
        # Split versions by dots
        parts1 = version1.split(".")
        parts2 = version2.split(".")
        
        # Compare each part
        for i in range(max(len(parts1), len(parts2))):
            # Get part or 0 if not available
            part1 = int(parts1[i]) if i < len(parts1) else 0
            part2 = int(parts2[i]) if i < len(parts2) else 0
            
            # Compare parts
            if part1 < part2:
                return -1
            elif part1 > part2:
                return 1
        
        # Versions are equal
        return 0
    
    def check_dependencies(self, dependencies: List[str]) -> Dict[str, Any]:
        """
        Check if multiple dependencies are satisfied
        
        Args:
            dependencies: List of dependency strings
            
        Returns:
            Dictionary with dependency check status
        """
        results = []
        all_satisfied = True
        
        for dependency in dependencies:
            result = self.check_dependency(dependency)
            results.append(result)
            
            if not result.get("satisfied", False):
                all_satisfied = False
        
        return {
            "success": True,
            "satisfied": all_satisfied,
            "results": results,
            "count": len(results)
        }
    
    def get_dependent_apps(self, app_id: str) -> Dict[str, Any]:
        """
        Get applications that depend on the specified app
        
        Args:
            app_id: Application ID
            
        Returns:
            Dictionary with dependent applications
        """
        dependents = []
        
        with self.lock:
            for dep_id, metadata in self.apps.items():
                # Check if app_id is in dependencies
                for dependency in metadata.dependencies:
                    dep_app_id = dependency.split(">=")[0].strip() if ">=" in dependency else dependency.strip()
                    
                    if dep_app_id == app_id:
                        dependents.append({
                            "app_id": dep_id,
                            "name": metadata.name,
                            "version": metadata.version,
                            "dependency": dependency
                        })
                        break
        
        return {
            "success": True,
            "app_id": app_id,
            "dependents": dependents,
            "count": len(dependents)
        }
    
    def verify_registry(self) -> Dict[str, Any]:
        """
        Verify registry integrity
        
        Returns:
            Dictionary with verification results
        """
        issues = []
        
        with self.lock:
            # Check for missing executables
            for app_id, metadata in self.apps.items():
                if metadata.executable and not os.path.exists(metadata.executable):
                    issues.append({
                        "app_id": app_id,
                        "issue": "missing_executable",
                        "details": f"Executable not found: {metadata.executable}"
                    })
            
            # Check for missing dependencies
            for app_id, metadata in self.apps.items():
                for dependency in metadata.dependencies:
                    result = self.check_dependency(dependency)
                    
                    if not result.get("satisfied", False):
                        issues.append({
                            "app_id": app_id,
                            "issue": "unsatisfied_dependency",
                            "details": result.get("error", f"Unsatisfied dependency: {dependency}")
                        })
            
            # Check index consistency
            for tag, app_ids in self.app_by_tag.items():
                for app_id in app_ids:
                    if app_id not in self.apps:
                        issues.append({
                            "issue": "index_inconsistency",
                            "details": f"App {app_id} in tag index but not in registry"
                        })
                    elif tag not in self.apps[app_id].tags:
                        issues.append({
                            "app_id": app_id,
                            "issue": "index_inconsistency",
                            "details": f"App in tag index for {tag} but tag not in app metadata"
                        })
            
            # Save registry if issues were found
            if issues:
                self._save_registry()
        
        return {
            "success": True,
            "verified": len(issues) == 0,
            "issues": issues,
            "count": len(issues)
        }
    
    def export_registry(self) -> Dict[str, Any]:
        """
        Export registry data
        
        Returns:
            Dictionary with registry data
        """
        with self.lock:
            registry_data = {
                "last_exported": datetime.now().isoformat(),
                "apps_count": len(self.apps),
                "categories_count": len(self.app_by_category),
                "tags_count": len(self.app_by_tag),
                "apps": {app_id: metadata.to_dict() for app_id, metadata in self.apps.items()}
            }
            
            return {
                "success": True,
                "registry": registry_data
            }
    
    def import_registry(self, registry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Import registry data
        
        Args:
            registry_data: Registry data
            
        Returns:
            Dictionary with import status
        """
        try:
            if "apps" not in registry_data or not isinstance(registry_data["apps"], dict):
                return {
                    "success": False,
                    "error": "Invalid registry data: missing or invalid apps"
                }
            
            imported = []
            failed = []
            
            for app_id, app_data in registry_data["apps"].items():
                try:
                    result = self.register_app(app_data)
                    
                    if result.get("success", False):
                        imported.append(app_id)
                    else:
                        failed.append({
                            "app_id": app_id,
                            "error": result.get("error", "Unknown error")
                        })
                except Exception as e:
                    failed.append({
                        "app_id": app_id,
                        "error": str(e)
                    })
            
            return {
                "success": True,
                "imported": imported,
                "failed": failed,
                "imported_count": len(imported),
                "failed_count": len(failed)
            }
        except Exception as e:
            logger.error(f"Error importing registry: {e}")
            return {
                "success": False,
                "error": str(e)
            }

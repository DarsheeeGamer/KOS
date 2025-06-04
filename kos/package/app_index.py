"""
KOS Application Index Manager
Handles the registry of installed applications and their CLI commands
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any, Union

logger = logging.getLogger('KOS.package.app_index')

class AppIndexEntry:
    """Represents an entry in the application index"""
    def __init__(self, 
                 name: str,
                 version: str,
                 entry_point: str,
                 app_path: str,
                 cli_aliases: List[str] = None,
                 cli_function: str = None,
                 description: str = "",
                 author: str = "",
                 repository: str = "",
                 tags: List[str] = None):
        self.name = name
        self.version = version
        self.entry_point = entry_point
        self.app_path = app_path
        self.cli_aliases = cli_aliases or []
        self.cli_function = cli_function or ""
        self.description = description
        self.author = author
        self.repository = repository
        self.tags = tags or []
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization"""
        return {
            "name": self.name,
            "version": self.version,
            "entry_point": self.entry_point,
            "app_path": self.app_path,
            "cli_aliases": self.cli_aliases,
            "cli_function": self.cli_function,
            "description": self.description,
            "author": self.author,
            "repository": self.repository,
            "tags": self.tags
        }
        
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AppIndexEntry':
        """Create entry from dictionary"""
        return AppIndexEntry(
            name=data.get("name", ""),
            version=data.get("version", ""),
            entry_point=data.get("entry_point", ""),
            app_path=data.get("app_path", ""),
            cli_aliases=data.get("cli_aliases", []),
            cli_function=data.get("cli_function", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            repository=data.get("repository", ""),
            tags=data.get("tags", [])
        )
        
class AppIndexManager:
    """Manages the KOS application index"""
    
    def __init__(self, apps_dir: str = "kos_apps"):
        self.index_file = "KOS_APP_INDEX.json"
        self.apps_dir = apps_dir
        self.apps: Dict[str, AppIndexEntry] = {}
        self._load_index()
        
    def _load_index(self) -> None:
        """Load application index from file"""
        try:
            if os.path.exists(self.index_file):
                with open(self.index_file, 'r') as f:
                    data = json.load(f)
                    for name, app_data in data.get("apps", {}).items():
                        self.apps[name] = AppIndexEntry.from_dict(app_data)
                logger.info(f"Loaded {len(self.apps)} applications from index")
            else:
                logger.info("App index file not found, creating new index")
                self._save_index()  # Create an empty index file
        except Exception as e:
            logger.error(f"Error loading app index: {e}")
            # Create an empty index in case of error
            self._save_index()
            
    def _save_index(self) -> bool:
        """Save the application index to disk"""
        try:
            # Convert objects to dictionaries for proper JSON serialization
            index_data = {'apps': {}}
            for name, app in self.apps.items():
                # Make sure we use the to_dict method for proper serialization
                if hasattr(app, 'to_dict') and callable(app.to_dict):
                    index_data['apps'][name] = app.to_dict()
                else:
                    # Fallback for direct dictionary conversion
                    app_dict = {}
                    for attr, value in app.__dict__.items():
                        # Convert any non-serializable objects to strings
                        if isinstance(value, (str, int, float, bool, type(None))):
                            app_dict[attr] = value
                        elif isinstance(value, (list, tuple)):
                            # Handle lists of basic types
                            app_dict[attr] = [str(item) if not isinstance(item, (str, int, float, bool, type(None))) else item for item in value]
                        else:
                            app_dict[attr] = str(value)
                    index_data['apps'][name] = app_dict
                
            # Ensure the directory exists
            index_dir = os.path.dirname(self.index_file)
            os.makedirs(index_dir, exist_ok=True)
            
            # Write to disk with robust error handling
            with open(self.index_file, 'w') as f:
                try:
                    json.dump(index_data, f, indent=2, default=str)
                    f.flush()
                    os.fsync(f.fileno())
                except TypeError as json_err:
                    logger.error(f"JSON serialization error: {json_err}")
                    # Try again with a simpler approach that forces string conversion
                    json.dump(index_data, f, indent=2, default=str)
                
            logger.debug(f"Saved application index to {self.index_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving application index: {e}")
            return False
            
    def add_app(self, app: AppIndexEntry) -> bool:
        """Add an application to the index"""
        try:
            self.apps[app.name] = app
            self._save_index()
            logger.info(f"Added application '{app.name}' to index")
            return True
        except Exception as e:
            logger.error(f"Error adding application to index: {e}")
            return False
            
    def remove_app(self, app_name: str) -> bool:
        """Remove an application from the index and filesystem"""
        try:
            if app_name in self.apps:
                # Get the app information before removing it
                app = self.apps[app_name]
                app_path = app.app_path
                
                # Properly resolve the app path relative to the KOS root
                full_app_path = app_path
                if not os.path.isabs(full_app_path):
                    # Try to locate the application relative to current directory
                    current_dir = os.getcwd()
                    # Check if path exists relative to current directory
                    if os.path.exists(os.path.join(current_dir, app_path)):
                        full_app_path = os.path.join(current_dir, app_path)
                    else:
                        # Use a default KOS apps directory
                        kos_apps_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'kos_apps')
                        full_app_path = os.path.join(kos_apps_dir, os.path.basename(app_path))
                    
                logger.info(f"Resolved app path for '{app_name}': {full_app_path}")
                
                # Remove from index
                del self.apps[app_name]
                self._save_index()
                
                # Delete application files from filesystem if they exist
                if os.path.exists(full_app_path) and os.path.isdir(full_app_path):
                    try:
                        import shutil
                        shutil.rmtree(full_app_path)
                        logger.info(f"Deleted application files for '{app_name}' from {full_app_path}")
                    except Exception as file_err:
                        logger.warning(f"Could not delete application files for '{app_name}': {file_err}")
                        # Continue anyway - we've removed from index which is the most important part
                else:
                    logger.warning(f"App directory not found at {full_app_path}, but removed from index")
                
                print(f"Successfully removed application '{app_name}'")
                logger.info(f"Removed application '{app_name}' from index")
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing application from index: {e}")
            return False
            
    def get_app(self, app_name: str) -> Optional[AppIndexEntry]:
        """Get application information from the index"""
        return self.apps.get(app_name)
        
    def get_app_by_alias(self, alias: str) -> Optional[AppIndexEntry]:
        """Get application by CLI alias"""
        for app in self.apps.values():
            if alias in app.cli_aliases:
                return app
        return None
        
    def list_apps(self) -> List[AppIndexEntry]:
        """List all applications in the index"""
        return list(self.apps.values())
        
    def is_app_installed(self, app_name: str) -> bool:
        """Check if an application is installed
        
        Args:
            app_name: Application name to check
            
        Returns:
            bool: True if the application is installed
        """
        # Check if app exists in index
        is_in_index = app_name in self.apps
        
        # Also verify the app directory exists (for more robustness)
        app_path = None
        if is_in_index:
            app = self.apps[app_name]
            app_path = app.app_path
        
        if app_path and os.path.exists(app_path) and os.path.isdir(app_path):
            return True
            
        # If we're here but the app is in index, it means the directory doesn't exist
        # This is an inconsistency, log a warning
        if is_in_index:
            logger.warning(f"Application '{app_name}' is in index but directory doesn't exist")
            
        return False
        
    def list_installed_apps(self) -> List[AppIndexEntry]:
        """List all actually installed applications
        
        Returns:
            List[AppIndexEntry]: List of installed applications
        """
        return [app for name, app in self.apps.items() if self.is_app_installed(name)]
        
    def get_app_entry_point(self, app_name: str) -> Optional[str]:
        """Get the full path to an app's entry point"""
        app = self.get_app(app_name)
        if app:
            return os.path.join(app.app_path, app.entry_point)
        return None
        
    def add_cli_alias(self, app_name: str, alias: str) -> bool:
        """Add a CLI alias for an application"""
        app = self.get_app(app_name)
        if app and alias not in app.cli_aliases:
            app.cli_aliases.append(alias)
            self._save_index()
            logger.info(f"Added CLI alias '{alias}' for application '{app_name}'")
            return True
        return False
        
    def remove_cli_alias(self, app_name: str, alias: str) -> bool:
        """Remove a CLI alias from an application"""
        app = self.get_app(app_name)
        if app and alias in app.cli_aliases:
            app.cli_aliases.remove(alias)
            self._save_index()
            logger.info(f"Removed CLI alias '{alias}' from application '{app_name}'")
            return True
        return False
        
    def update_cli_function(self, app_name: str, cli_function: str) -> bool:
        """Update the CLI function for an application"""
        app = self.get_app(app_name)
        if app:
            app.cli_function = cli_function
            self._save_index()
            logger.info(f"Updated CLI function for application '{app_name}'")
            return True
        return False

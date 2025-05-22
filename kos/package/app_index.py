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
            
    def _save_index(self) -> None:
        """Save application index to file"""
        try:
            data = {
                "apps": {name: app.to_dict() for name, app in self.apps.items()}
            }
            with open(self.index_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self.apps)} applications to index")
        except Exception as e:
            logger.error(f"Error saving app index: {e}")
            
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
        """Remove an application from the index"""
        try:
            if app_name in self.apps:
                del self.apps[app_name]
                self._save_index()
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

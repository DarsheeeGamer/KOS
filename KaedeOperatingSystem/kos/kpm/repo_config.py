"""KOS Package Manager Repository Configuration"""
import json
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

class RepositoryConfig:
    def __init__(self):
        self.config_file = "kos_repos.json"
        self.repos = self._load_config()

    def _load_config(self) -> Dict:
        """Load repository configuration"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        
        # Default configuration
        default_config = {
            "repositories": {
                "main": {
                    "url": "https://kos-repo.example.com/main",
                    "priority": 100,
                    "enabled": True,
                    "last_update": None
                }
            },
            "default_repo": "main"
        }
        self._save_config(default_config)
        return default_config

    def _save_config(self, config: Dict):
        """Save repository configuration"""
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

    def add_repository(self, name: str, url: str, priority: int = 50) -> bool:
        """Add a new repository"""
        if name in self.repos["repositories"]:
            return False
        
        self.repos["repositories"][name] = {
            "url": url,
            "priority": priority,
            "enabled": True,
            "last_update": None
        }
        self._save_config(self.repos)
        return True

    def remove_repository(self, name: str) -> bool:
        """Remove a repository"""
        if name not in self.repos["repositories"] or name == "main":
            return False
        
        del self.repos["repositories"][name]
        self._save_config(self.repos)
        return True

    def enable_repository(self, name: str) -> bool:
        """Enable a repository"""
        if name not in self.repos["repositories"]:
            return False
        
        self.repos["repositories"][name]["enabled"] = True
        self._save_config(self.repos)
        return True

    def disable_repository(self, name: str) -> bool:
        """Disable a repository"""
        if name not in self.repos["repositories"] or name == "main":
            return False
        
        self.repos["repositories"][name]["enabled"] = False
        self._save_config(self.repos)
        return True

    def list_repositories(self) -> List[Dict]:
        """List all repositories"""
        return [
            {"name": name, **repo}
            for name, repo in self.repos["repositories"].items()
        ]

    def get_repository(self, name: str) -> Optional[Dict]:
        """Get repository information"""
        return self.repos["repositories"].get(name)

    def update_repository(self, name: str) -> bool:
        """Update repository package list"""
        repo = self.get_repository(name)
        if not repo or not repo["enabled"]:
            return False

        try:
            # Simulate repository update
            # In real implementation, this would fetch package lists from the repository URL
            repo["last_update"] = datetime.now().isoformat()
            self._save_config(self.repos)
            return True
        except Exception:
            return False

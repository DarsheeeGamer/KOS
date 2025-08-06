"""
KOS Configuration Management
Simple, clean configuration handling
"""

import json
import os
from typing import Dict, Any

class Config:
    """System configuration manager"""
    
    DEFAULT_CONFIG = {
        'system': {
            'name': 'KOS',
            'version': '2.0',
            'prompt': 'kos> '
        },
        'vfs': {
            'disk_path': 'kaede.kdsk',
            'auto_save': True
        },
        'shell': {
            'history_size': 1000,
            'color_output': True
        },
        'packages': {
            'repository': 'https://kos-repo.example.com',
            'cache_dir': '/var/cache/kpm'
        }
    }
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file or 'kos.config.json'
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                    self._merge_config(user_config)
            except Exception:
                pass  # Use defaults on error
    
    def save(self):
        """Save configuration to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
    
    def _merge_config(self, user_config: Dict[str, Any]):
        """Merge user config with defaults"""
        for key, value in user_config.items():
            if key in self.config and isinstance(value, dict):
                self.config[key].update(value)
            else:
                self.config[key] = value
    
    def get(self, key: str, default=None):
        """Get config value by dot notation (e.g., 'system.version')"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """Set config value by dot notation"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
        self.save()
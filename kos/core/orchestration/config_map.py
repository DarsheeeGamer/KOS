"""
ConfigMap for KOS Orchestration System

This module implements ConfigMaps for the KOS orchestration system,
providing a way to inject configuration data into pods.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Union

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
CONFIG_MAP_PATH = os.path.join(ORCHESTRATION_ROOT, 'configmaps')

# Ensure directories exist
os.makedirs(CONFIG_MAP_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ConfigMap:
    """
    ConfigMap in the KOS orchestration system.
    
    A ConfigMap holds configuration data for pods.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 data: Dict[str, str] = None,
                 binary_data: Dict[str, bytes] = None):
        """
        Initialize a ConfigMap.
        
        Args:
            name: ConfigMap name
            namespace: Namespace
            data: String data
            binary_data: Binary data
        """
        self.name = name
        self.namespace = namespace
        self.data = data or {}
        self.binary_data = binary_data or {}
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": "",
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this ConfigMap."""
        return os.path.join(CONFIG_MAP_PATH, self.namespace, f"{self.name}.json")
    
    def _binary_dir(self) -> str:
        """Get the directory path for binary data."""
        return os.path.join(CONFIG_MAP_PATH, self.namespace, f"{self.name}_binary")
    
    def _load(self) -> bool:
        """
        Load the ConfigMap from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update data
            self.data = data.get("data", {})
            
            # Update binary data keys
            binary_keys = data.get("binaryData", {})
            
            # Load binary data
            binary_dir = self._binary_dir()
            if os.path.exists(binary_dir):
                self.binary_data = {}
                for key in binary_keys:
                    binary_path = os.path.join(binary_dir, key)
                    if os.path.exists(binary_path):
                        with open(binary_path, 'rb') as f:
                            self.binary_data[key] = f.read()
            
            return True
        except Exception as e:
            logger.error(f"Failed to load ConfigMap {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the ConfigMap to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                # Save metadata and data
                data = {
                    "kind": "ConfigMap",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "data": self.data,
                    "binaryData": {key: True for key in self.binary_data}
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Save binary data
                if self.binary_data:
                    binary_dir = self._binary_dir()
                    os.makedirs(binary_dir, exist_ok=True)
                    
                    for key, value in self.binary_data.items():
                        binary_path = os.path.join(binary_dir, key)
                        with open(binary_path, 'wb') as f:
                            f.write(value)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save ConfigMap {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the ConfigMap.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete binary directory
            binary_dir = self._binary_dir()
            if os.path.exists(binary_dir):
                import shutil
                shutil.rmtree(binary_dir)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete ConfigMap {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_config_maps(namespace: Optional[str] = None) -> List['ConfigMap']:
        """
        List all ConfigMaps.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of ConfigMaps
        """
        config_maps = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = CONFIG_MAP_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List ConfigMaps in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(CONFIG_MAP_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    config_map_name = filename[:-5]  # Remove .json extension
                    config_map = ConfigMap(config_map_name, ns)
                    config_maps.append(config_map)
        except Exception as e:
            logger.error(f"Failed to list ConfigMaps: {e}")
        
        return config_maps
    
    @staticmethod
    def get_config_map(name: str, namespace: str = "default") -> Optional['ConfigMap']:
        """
        Get a ConfigMap by name and namespace.
        
        Args:
            name: ConfigMap name
            namespace: Namespace
            
        Returns:
            ConfigMap object or None if not found
        """
        config_map = ConfigMap(name, namespace)
        
        if os.path.exists(config_map._file_path()):
            return config_map
        
        return None

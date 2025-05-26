"""
Secret Management for KOS Orchestration System

This module implements Secret management for the KOS orchestration system,
providing a way to store sensitive information such as passwords, tokens,
and keys.
"""

import os
import json
import base64
import logging
import threading
import time
import uuid
from typing import Dict, List, Any, Optional, Set, Tuple, Union

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
SECRET_PATH = os.path.join(ORCHESTRATION_ROOT, 'secrets')

# Ensure directories exist
os.makedirs(SECRET_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class Secret:
    """
    Secret in the KOS orchestration system.
    
    A Secret is used to store sensitive information, such as passwords,
    OAuth tokens, and ssh keys.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 data: Dict[str, bytes] = None,
                 string_data: Dict[str, str] = None,
                 type: str = "Opaque"):
        """
        Initialize a Secret.
        
        Args:
            name: Secret name
            namespace: Namespace
            data: Binary data
            string_data: String data
            type: Secret type
        """
        self.name = name
        self.namespace = namespace
        self.data = data or {}
        self.string_data = string_data or {}
        self.type = type
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        
        # Convert string data to binary data
        self._convert_string_data()
        
        # Load if exists
        self._load()
    
    def _convert_string_data(self) -> None:
        """Convert string data to binary data."""
        for key, value in self.string_data.items():
            self.data[key] = value.encode('utf-8')
    
    def _file_path(self) -> str:
        """Get the file path for this Secret."""
        return os.path.join(SECRET_PATH, self.namespace, f"{self.name}.json")
    
    def _data_dir(self) -> str:
        """Get the directory path for binary data."""
        return os.path.join(SECRET_PATH, self.namespace, f"{self.name}_data")
    
    def _load(self) -> bool:
        """
        Load the Secret from disk.
        
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
            
            # Update type
            self.type = data.get("type", "Opaque")
            
            # Update data keys
            data_keys = data.get("data", {})
            
            # Load data
            data_dir = self._data_dir()
            if os.path.exists(data_dir):
                self.data = {}
                for key in data_keys:
                    data_path = os.path.join(data_dir, key)
                    if os.path.exists(data_path):
                        with open(data_path, 'rb') as f:
                            self.data[key] = f.read()
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Secret {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Secret to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                # Save metadata and data keys
                data = {
                    "kind": "Secret",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "type": self.type,
                    "data": {key: True for key in self.data}
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Save data
                if self.data:
                    data_dir = self._data_dir()
                    os.makedirs(data_dir, exist_ok=True)
                    
                    for key, value in self.data.items():
                        data_path = os.path.join(data_dir, key)
                        with open(data_path, 'wb') as f:
                            f.write(value)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Secret {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Secret.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # Delete data directory
            data_dir = self._data_dir()
            if os.path.exists(data_dir):
                import shutil
                shutil.rmtree(data_dir)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Secret {self.namespace}/{self.name}: {e}")
            return False
    
    def get_data(self, key: str) -> Optional[bytes]:
        """
        Get binary data by key.
        
        Args:
            key: Data key
            
        Returns:
            Binary data or None if not found
        """
        return self.data.get(key)
    
    def get_string_data(self, key: str) -> Optional[str]:
        """
        Get string data by key.
        
        Args:
            key: Data key
            
        Returns:
            String data or None if not found
        """
        data = self.get_data(key)
        if data is not None:
            try:
                return data.decode('utf-8')
            except UnicodeDecodeError:
                return None
        
        return None
    
    def set_data(self, key: str, value: bytes) -> None:
        """
        Set binary data.
        
        Args:
            key: Data key
            value: Binary data
        """
        self.data[key] = value
    
    def set_string_data(self, key: str, value: str) -> None:
        """
        Set string data.
        
        Args:
            key: Data key
            value: String data
        """
        self.string_data[key] = value
        self.data[key] = value.encode('utf-8')
    
    def to_dict(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Convert the Secret to a dictionary.
        
        Args:
            include_data: Whether to include data
            
        Returns:
            Dict representation of the Secret
        """
        result = {
            "kind": "Secret",
            "apiVersion": "v1",
            "metadata": self.metadata,
            "type": self.type
        }
        
        if include_data:
            # Encode binary data as base64
            result["data"] = {
                key: base64.b64encode(value).decode('utf-8')
                for key, value in self.data.items()
            }
        
        return result
    
    @staticmethod
    def list_secrets(namespace: Optional[str] = None) -> List['Secret']:
        """
        List all Secrets.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of Secrets
        """
        secrets = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = SECRET_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List Secrets in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(SECRET_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    secret_name = filename[:-5]  # Remove .json extension
                    secret = Secret(secret_name, ns)
                    secrets.append(secret)
        except Exception as e:
            logger.error(f"Failed to list Secrets: {e}")
        
        return secrets
    
    @staticmethod
    def get_secret(name: str, namespace: str = "default") -> Optional['Secret']:
        """
        Get a Secret by name and namespace.
        
        Args:
            name: Secret name
            namespace: Namespace
            
        Returns:
            Secret object or None if not found
        """
        secret = Secret(name, namespace)
        
        if os.path.exists(secret._file_path()):
            return secret
        
        return None

"""
Registry Core for KOS Container Registry

This module implements the core registry functionality for the KOS container registry,
providing image storage, retrieval, and management.
"""

import os
import io
import json
import time
import shutil
import logging
import threading
import tarfile
import urllib.request
from typing import Dict, List, Set, Optional, Any, Union, Tuple, BinaryIO

from .image import Image, ImageConfig
from .index import RegistryIndex

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
REGISTRY_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/registry')
REGISTRY_CONFIG_PATH = os.path.join(REGISTRY_ROOT, 'config.json')

# Ensure directories exist
os.makedirs(os.path.dirname(REGISTRY_CONFIG_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class RegistryConfig:
    """Configuration for the KOS registry."""
    
    def __init__(self, storage_path: Optional[str] = None,
                 allow_insecure_registries: bool = False,
                 proxy_registries: Optional[List[str]] = None,
                 max_concurrent_uploads: int = 5,
                 max_concurrent_downloads: int = 5,
                 gc_interval: int = 86400,  # 24 hours
                 index_rebuild_interval: int = 3600,  # 1 hour
                 cache_size: int = 10240):  # 10 GB
        """
        Initialize registry configuration.
        
        Args:
            storage_path: Path to store registry data
            allow_insecure_registries: Whether to allow insecure connections to upstream registries
            proxy_registries: List of registries to proxy requests to
            max_concurrent_uploads: Maximum number of concurrent uploads
            max_concurrent_downloads: Maximum number of concurrent downloads
            gc_interval: Interval for garbage collection in seconds
            index_rebuild_interval: Interval for index rebuilding in seconds
            cache_size: Maximum size of the cache in MB
        """
        self.storage_path = storage_path or REGISTRY_ROOT
        self.allow_insecure_registries = allow_insecure_registries
        self.proxy_registries = proxy_registries or []
        self.max_concurrent_uploads = max_concurrent_uploads
        self.max_concurrent_downloads = max_concurrent_downloads
        self.gc_interval = gc_interval
        self.index_rebuild_interval = index_rebuild_interval
        self.cache_size = cache_size
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "storage_path": self.storage_path,
            "allow_insecure_registries": self.allow_insecure_registries,
            "proxy_registries": self.proxy_registries,
            "max_concurrent_uploads": self.max_concurrent_uploads,
            "max_concurrent_downloads": self.max_concurrent_downloads,
            "gc_interval": self.gc_interval,
            "index_rebuild_interval": self.index_rebuild_interval,
            "cache_size": self.cache_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegistryConfig':
        """
        Create a configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            RegistryConfig object
        """
        return cls(
            storage_path=data.get("storage_path"),
            allow_insecure_registries=data.get("allow_insecure_registries", False),
            proxy_registries=data.get("proxy_registries", []),
            max_concurrent_uploads=data.get("max_concurrent_uploads", 5),
            max_concurrent_downloads=data.get("max_concurrent_downloads", 5),
            gc_interval=data.get("gc_interval", 86400),
            index_rebuild_interval=data.get("index_rebuild_interval", 3600),
            cache_size=data.get("cache_size", 10240)
        )


class Registry:
    """
    KOS container registry.
    
    This class provides methods for working with the registry, including
    pushing, pulling, and managing images.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Registry, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the registry."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = self._load_config()
        self._upload_semaphore = threading.Semaphore(self.config.max_concurrent_uploads)
        self._download_semaphore = threading.Semaphore(self.config.max_concurrent_downloads)
        self._stop_event = threading.Event()
        self._maintenance_thread = None
        self._start_maintenance_thread()
    
    def _load_config(self) -> RegistryConfig:
        """
        Load registry configuration.
        
        Returns:
            RegistryConfig object
        """
        if os.path.exists(REGISTRY_CONFIG_PATH):
            try:
                with open(REGISTRY_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                
                return RegistryConfig.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load registry config: {e}")
        
        # Create default configuration
        config = RegistryConfig()
        self._save_config(config)
        
        return config
    
    def _save_config(self, config: RegistryConfig) -> bool:
        """
        Save registry configuration.
        
        Args:
            config: Configuration to save
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(REGISTRY_CONFIG_PATH, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save registry config: {e}")
            return False
    
    def update_config(self, config: RegistryConfig) -> bool:
        """
        Update registry configuration.
        
        Args:
            config: New configuration
            
        Returns:
            bool: Success or failure
        """
        if self._save_config(config):
            self.config = config
            
            # Update semaphores
            self._upload_semaphore = threading.Semaphore(self.config.max_concurrent_uploads)
            self._download_semaphore = threading.Semaphore(self.config.max_concurrent_downloads)
            
            return True
        
        return False
    
    def _start_maintenance_thread(self):
        """Start the maintenance thread."""
        if self._maintenance_thread and self._maintenance_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True
        )
        self._maintenance_thread.start()
    
    def _stop_maintenance_thread(self):
        """Stop the maintenance thread."""
        if not self._maintenance_thread or not self._maintenance_thread.is_alive():
            return
        
        self._stop_event.set()
        self._maintenance_thread.join(timeout=5)
    
    def _maintenance_loop(self):
        """Maintenance loop for garbage collection and index rebuilding."""
        gc_time = 0
        index_time = 0
        
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                
                # Check if garbage collection is needed
                if current_time - gc_time >= self.config.gc_interval:
                    logger.info("Running garbage collection")
                    Image.gc()
                    gc_time = current_time
                
                # Check if index rebuilding is needed
                if current_time - index_time >= self.config.index_rebuild_interval:
                    logger.info("Rebuilding registry index")
                    RegistryIndex().rebuild_index()
                    index_time = current_time
                
                # Sleep for a while
                self._stop_event.wait(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in maintenance loop: {e}")
                self._stop_event.wait(60)  # Wait before retrying
    
    def push_image(self, name: str, tag: str, layers: List[Union[bytes, BinaryIO]],
                   config: ImageConfig) -> bool:
        """
        Push an image to the registry.
        
        Args:
            name: Image name
            tag: Image tag
            layers: Image layers (compressed tars)
            config: Image configuration
            
        Returns:
            bool: Success or failure
        """
        with self._upload_semaphore:
            image = Image(name, tag)
            return image.push(layers, config)
    
    def pull_image(self, name: str, tag: str) -> Optional[Tuple[List[bytes], ImageConfig]]:
        """
        Pull an image from the registry.
        
        Args:
            name: Image name
            tag: Image tag
            
        Returns:
            Tuple of (layers, config) or None if not found
        """
        with self._download_semaphore:
            # Check local registry first
            image = Image(name, tag)
            result = image.pull()
            
            if result:
                return result
            
            # Try proxy registries if configured
            if self.config.proxy_registries:
                for registry_url in self.config.proxy_registries:
                    try:
                        logger.info(f"Trying to pull {name}:{tag} from {registry_url}")
                        result = self._pull_from_external(registry_url, name, tag)
                        if result:
                            # Save to local registry
                            layers, config = result
                            image.push(layers, config)
                            return result
                    except Exception as e:
                        logger.error(f"Failed to pull from {registry_url}: {e}")
            
            return None
    
    def _pull_from_external(self, registry_url: str, name: str, tag: str) -> Optional[Tuple[List[bytes], ImageConfig]]:
        """
        Pull an image from an external registry.
        
        Args:
            registry_url: External registry URL
            name: Image name
            tag: Image tag
            
        Returns:
            Tuple of (layers, config) or None if not found
        """
        # This is a simplified implementation
        # A real implementation would need to handle authentication, headers, etc.
        try:
            # Build URL for manifest
            url = f"{registry_url}/v2/{name}/manifests/{tag}"
            
            # Get manifest
            with urllib.request.urlopen(url) as response:
                manifest_data = response.read()
                manifest = json.loads(manifest_data)
            
            # Get config
            config_digest = manifest.get("config", {}).get("digest")
            if not config_digest:
                logger.error(f"Config digest not found in manifest")
                return None
            
            config_url = f"{registry_url}/v2/{name}/blobs/{config_digest}"
            with urllib.request.urlopen(config_url) as response:
                config_data = response.read()
                config = ImageConfig.from_dict(json.loads(config_data))
            
            # Get layers
            layers = []
            for layer in manifest.get("layers", []):
                layer_digest = layer.get("digest")
                if not layer_digest:
                    continue
                
                layer_url = f"{registry_url}/v2/{name}/blobs/{layer_digest}"
                with urllib.request.urlopen(layer_url) as response:
                    layer_data = response.read()
                    layers.append(layer_data)
            
            return (layers, config)
        except Exception as e:
            logger.error(f"Failed to pull from external registry: {e}")
            return None
    
    def delete_image(self, name: str, tag: str) -> bool:
        """
        Delete an image from the registry.
        
        Args:
            name: Image name
            tag: Image tag
            
        Returns:
            bool: Success or failure
        """
        image = Image(name, tag)
        return image.delete_tag()
    
    def list_images(self) -> List[Tuple[str, str]]:
        """
        List all images in the registry.
        
        Returns:
            List of (name, tag) tuples
        """
        return Image.list_images()
    
    def search_images(self, query: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Search for images in the registry.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        index = RegistryIndex()
        results = index.search(query, limit)
        
        return [result.to_dict() for result in results]
    
    def get_image_info(self, name: str, tag: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an image.
        
        Args:
            name: Image name
            tag: Image tag
            
        Returns:
            Dict with image information or None if not found
        """
        image = Image(name, tag)
        
        if not image.exists():
            return None
        
        try:
            # Get manifest and config
            manifest = image.get_manifest()
            if not manifest:
                return None
            
            config = image.get_config()
            if not config:
                return None
            
            # Calculate total size
            total_size = sum(image.get_blob_size(digest) for digest in manifest.layer_digests)
            
            # Get tag
            tag_info = image.load_tag()
            if not tag_info:
                return None
            
            return {
                "name": name,
                "tag": tag,
                "digest": tag_info.digest,
                "created": tag_info.created,
                "size": total_size,
                "layers": len(manifest.layer_digests),
                "architecture": config.architecture,
                "os": config.os,
                "entrypoint": config.entrypoint,
                "cmd": config.cmd,
                "labels": config.labels
            }
        except Exception as e:
            logger.error(f"Failed to get image info: {e}")
            return None
    
    def create_image_from_tar(self, name: str, tag: str, tar_path: str,
                             config: Optional[ImageConfig] = None) -> bool:
        """
        Create an image from a tar archive.
        
        Args:
            name: Image name
            tag: Image tag
            tar_path: Path to the tar archive
            config: Image configuration, or None to use default
            
        Returns:
            bool: Success or failure
        """
        image = Image(name, tag)
        return image.create_from_tar(tar_path, config)
    
    def extract_image_to_dir(self, name: str, tag: str, target_dir: str) -> bool:
        """
        Extract an image to a directory.
        
        Args:
            name: Image name
            tag: Image tag
            target_dir: Target directory
            
        Returns:
            bool: Success or failure
        """
        image = Image(name, tag)
        return image.extract_to_dir(target_dir)
    
    def run_gc(self) -> int:
        """
        Run garbage collection.
        
        Returns:
            Number of blobs removed
        """
        return Image.gc()
    
    def rebuild_index(self) -> bool:
        """
        Rebuild the registry index.
        
        Returns:
            bool: Success or failure
        """
        index = RegistryIndex()
        return index.rebuild_index()
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the registry.
        
        Returns:
            Dict with statistics
        """
        # Get index stats
        index = RegistryIndex()
        index_stats = index.get_stats()
        
        # Get disk usage
        storage_path = self.config.storage_path
        total_size = 0
        for root, dirs, files in os.walk(storage_path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
        
        # Count images and tags
        images = Image.list_images()
        unique_images = set(name for name, _ in images)
        
        return {
            "total_size": total_size,
            "image_count": len(unique_images),
            "tag_count": len(images),
            "blob_count": index_stats.get("digest_count", 0),
            "index_entry_count": index_stats.get("entry_count", 0),
            "config": self.config.to_dict()
        }

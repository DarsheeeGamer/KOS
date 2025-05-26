"""
Image Management for KOS Container Registry

This module implements image management for the KOS container registry,
handling image storage, layers, and metadata.
"""

import os
import io
import json
import time
import uuid
import hashlib
import tarfile
import logging
import threading
import shutil
from typing import Dict, List, Set, Optional, Any, Union, BinaryIO

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
REGISTRY_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/registry')
REGISTRY_IMAGES_PATH = os.path.join(REGISTRY_ROOT, 'images')
REGISTRY_BLOBS_PATH = os.path.join(REGISTRY_ROOT, 'blobs')
REGISTRY_TEMP_PATH = os.path.join(REGISTRY_ROOT, 'temp')

# Ensure directories exist
for directory in [REGISTRY_IMAGES_PATH, REGISTRY_BLOBS_PATH, REGISTRY_TEMP_PATH]:
    os.makedirs(directory, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ImageConfig:
    """Configuration for a container image."""
    
    def __init__(self, architecture: str = "amd64", os: str = "linux",
                 entrypoint: Optional[List[str]] = None,
                 cmd: Optional[List[str]] = None,
                 env: Optional[List[str]] = None,
                 labels: Optional[Dict[str, str]] = None,
                 working_dir: Optional[str] = None,
                 user: Optional[str] = None,
                 volumes: Optional[Dict[str, Dict]] = None,
                 exposed_ports: Optional[Dict[str, Dict]] = None):
        """
        Initialize an image configuration.
        
        Args:
            architecture: Image architecture
            os: Image operating system
            entrypoint: Default entrypoint
            cmd: Default command
            env: Environment variables
            labels: Image labels
            working_dir: Working directory
            user: User to run as
            volumes: Volume configurations
            exposed_ports: Exposed port configurations
        """
        self.architecture = architecture
        self.os = os
        self.entrypoint = entrypoint or []
        self.cmd = cmd or []
        self.env = env or []
        self.labels = labels or {}
        self.working_dir = working_dir or ""
        self.user = user or ""
        self.volumes = volumes or {}
        self.exposed_ports = exposed_ports or {}
        self.created = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the image configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "architecture": self.architecture,
            "os": self.os,
            "config": {
                "Entrypoint": self.entrypoint,
                "Cmd": self.cmd,
                "Env": self.env,
                "Labels": self.labels,
                "WorkingDir": self.working_dir,
                "User": self.user,
                "Volumes": self.volumes,
                "ExposedPorts": self.exposed_ports
            },
            "created": self.created
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageConfig':
        """
        Create an image configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ImageConfig object
        """
        config = data.get("config", {})
        
        return cls(
            architecture=data.get("architecture", "amd64"),
            os=data.get("os", "linux"),
            entrypoint=config.get("Entrypoint", []),
            cmd=config.get("Cmd", []),
            env=config.get("Env", []),
            labels=config.get("Labels", {}),
            working_dir=config.get("WorkingDir", ""),
            user=config.get("User", ""),
            volumes=config.get("Volumes", {}),
            exposed_ports=config.get("ExposedPorts", {})
        )


class ImageManifest:
    """Manifest for a container image."""
    
    def __init__(self, config_digest: str, layer_digests: Optional[List[str]] = None,
                 annotations: Optional[Dict[str, str]] = None):
        """
        Initialize an image manifest.
        
        Args:
            config_digest: Digest of the image configuration
            layer_digests: Digests of the image layers
            annotations: Manifest annotations
        """
        self.config_digest = config_digest
        self.layer_digests = layer_digests or []
        self.annotations = annotations or {}
        self.created = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the image manifest to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "digest": self.config_digest,
                "size": 0  # Will be set when saving
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
                    "digest": digest,
                    "size": 0  # Will be set when saving
                }
                for digest in self.layer_digests
            ],
            "annotations": self.annotations,
            "created": self.created
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageManifest':
        """
        Create an image manifest from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ImageManifest object
        """
        config = data.get("config", {})
        layers = data.get("layers", [])
        
        return cls(
            config_digest=config.get("digest", ""),
            layer_digests=[layer.get("digest", "") for layer in layers],
            annotations=data.get("annotations", {})
        )


class ImageTag:
    """Tag for a container image."""
    
    def __init__(self, name: str, tag: str, digest: str,
                 created: Optional[float] = None):
        """
        Initialize an image tag.
        
        Args:
            name: Image name
            tag: Tag name
            digest: Digest of the manifest
            created: Creation timestamp
        """
        self.name = name
        self.tag = tag
        self.digest = digest
        self.created = created or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the image tag to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "name": self.name,
            "tag": self.tag,
            "digest": self.digest,
            "created": self.created
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ImageTag':
        """
        Create an image tag from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ImageTag object
        """
        return cls(
            name=data.get("name", ""),
            tag=data.get("tag", ""),
            digest=data.get("digest", ""),
            created=data.get("created", time.time())
        )


class Image:
    """
    Container image in the KOS registry.
    
    This class provides methods for working with container images, including
    pushing, pulling, and managing image layers.
    """
    
    def __init__(self, name: str, tag: str = "latest"):
        """
        Initialize an image.
        
        Args:
            name: Image name
            tag: Image tag
        """
        self.name = name
        self.tag = tag
        self._lock = threading.Lock()
    
    @property
    def _image_dir(self) -> str:
        """Get the directory for this image."""
        return os.path.join(REGISTRY_IMAGES_PATH, self.name)
    
    @property
    def _tag_file(self) -> str:
        """Get the file for this image tag."""
        return os.path.join(self._image_dir, f"{self.tag}.json")
    
    def exists(self) -> bool:
        """
        Check if the image exists in the registry.
        
        Returns:
            bool: True if the image exists
        """
        return os.path.exists(self._tag_file)
    
    def save_tag(self, digest: str) -> bool:
        """
        Save an image tag.
        
        Args:
            digest: Digest of the manifest
            
        Returns:
            bool: Success or failure
        """
        try:
            # Create image directory if it doesn't exist
            os.makedirs(self._image_dir, exist_ok=True)
            
            # Create tag
            tag = ImageTag(
                name=self.name,
                tag=self.tag,
                digest=digest
            )
            
            # Save tag
            with open(self._tag_file, 'w') as f:
                json.dump(tag.to_dict(), f)
            
            # Update registry index
            from .index import RegistryIndex
            
            # Get image size and config
            manifest = self.get_manifest()
            if not manifest:
                logger.error(f"Failed to get manifest for {self.name}:{self.tag}")
                return False
            
            config = self.get_config()
            if not config:
                logger.error(f"Failed to get config for {self.name}:{self.tag}")
                return False
            
            # Calculate total size
            size = sum(self.get_blob_size(digest) for digest in manifest.layer_digests)
            
            # Add to index
            RegistryIndex().add_entry(
                name=self.name,
                tag=self.tag,
                digest=digest,
                created=time.time(),
                size=size,
                labels=config.labels
            )
            
            logger.info(f"Saved tag {self.name}:{self.tag} with digest {digest}")
            return True
        except Exception as e:
            logger.error(f"Failed to save tag {self.name}:{self.tag}: {e}")
            return False
    
    def load_tag(self) -> Optional[ImageTag]:
        """
        Load an image tag.
        
        Returns:
            ImageTag or None if not found
        """
        if not self.exists():
            logger.error(f"Tag not found: {self.name}:{self.tag}")
            return None
        
        try:
            with open(self._tag_file, 'r') as f:
                data = json.load(f)
            
            return ImageTag.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load tag {self.name}:{self.tag}: {e}")
            return None
    
    def delete_tag(self) -> bool:
        """
        Delete an image tag.
        
        Returns:
            bool: Success or failure
        """
        if not self.exists():
            logger.warning(f"Tag not found for deletion: {self.name}:{self.tag}")
            return False
        
        try:
            # Delete tag file
            os.remove(self._tag_file)
            
            # Delete image directory if empty
            if not os.listdir(self._image_dir):
                os.rmdir(self._image_dir)
            
            # Update registry index
            from .index import RegistryIndex
            RegistryIndex().remove_entry(self.name, self.tag)
            
            logger.info(f"Deleted tag {self.name}:{self.tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete tag {self.name}:{self.tag}: {e}")
            return False
    
    def get_digest(self) -> Optional[str]:
        """
        Get the digest for this image tag.
        
        Returns:
            Digest or None if not found
        """
        tag = self.load_tag()
        return tag.digest if tag else None
    
    def save_manifest(self, manifest: ImageManifest) -> str:
        """
        Save an image manifest.
        
        Args:
            manifest: Image manifest
            
        Returns:
            Manifest digest
        """
        # Add sizes to manifest
        manifest_dict = manifest.to_dict()
        
        # Add config size
        config_digest = manifest_dict["config"]["digest"]
        config_size = self.get_blob_size(config_digest)
        manifest_dict["config"]["size"] = config_size
        
        # Add layer sizes
        for i, layer in enumerate(manifest_dict["layers"]):
            layer_digest = layer["digest"]
            layer_size = self.get_blob_size(layer_digest)
            manifest_dict["layers"][i]["size"] = layer_size
        
        # Serialize manifest
        manifest_json = json.dumps(manifest_dict, sort_keys=True)
        
        # Calculate digest
        digest = f"sha256:{hashlib.sha256(manifest_json.encode()).hexdigest()}"
        
        # Save manifest
        blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
        with open(blob_path, 'w') as f:
            f.write(manifest_json)
        
        return digest
    
    def get_manifest(self) -> Optional[ImageManifest]:
        """
        Get the manifest for this image tag.
        
        Returns:
            ImageManifest or None if not found
        """
        digest = self.get_digest()
        if not digest:
            logger.error(f"Digest not found for {self.name}:{self.tag}")
            return None
        
        try:
            blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
            if not os.path.exists(blob_path):
                logger.error(f"Manifest blob not found: {digest}")
                return None
            
            with open(blob_path, 'r') as f:
                data = json.load(f)
            
            return ImageManifest.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to get manifest for {self.name}:{self.tag}: {e}")
            return None
    
    def save_config(self, config: ImageConfig) -> str:
        """
        Save an image configuration.
        
        Args:
            config: Image configuration
            
        Returns:
            Config digest
        """
        # Serialize config
        config_json = json.dumps(config.to_dict(), sort_keys=True)
        
        # Calculate digest
        digest = f"sha256:{hashlib.sha256(config_json.encode()).hexdigest()}"
        
        # Save config
        blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
        with open(blob_path, 'w') as f:
            f.write(config_json)
        
        return digest
    
    def get_config(self) -> Optional[ImageConfig]:
        """
        Get the configuration for this image tag.
        
        Returns:
            ImageConfig or None if not found
        """
        manifest = self.get_manifest()
        if not manifest:
            logger.error(f"Manifest not found for {self.name}:{self.tag}")
            return None
        
        try:
            blob_path = os.path.join(REGISTRY_BLOBS_PATH, manifest.config_digest)
            if not os.path.exists(blob_path):
                logger.error(f"Config blob not found: {manifest.config_digest}")
                return None
            
            with open(blob_path, 'r') as f:
                data = json.load(f)
            
            return ImageConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to get config for {self.name}:{self.tag}: {e}")
            return None
    
    def save_layer(self, data: Union[bytes, BinaryIO]) -> str:
        """
        Save an image layer.
        
        Args:
            data: Layer data (compressed tar)
            
        Returns:
            Layer digest
        """
        # Calculate digest
        if hasattr(data, 'read'):
            # It's a file-like object
            data.seek(0)
            digest = f"sha256:{hashlib.sha256(data.read()).hexdigest()}"
            data.seek(0)
        else:
            # It's bytes
            digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
        
        # Save layer
        blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
        if os.path.exists(blob_path):
            logger.info(f"Layer already exists: {digest}")
            return digest
        
        try:
            with open(blob_path, 'wb') as f:
                if hasattr(data, 'read'):
                    # It's a file-like object
                    shutil.copyfileobj(data, f)
                else:
                    # It's bytes
                    f.write(data)
            
            logger.info(f"Saved layer with digest {digest}")
            return digest
        except Exception as e:
            logger.error(f"Failed to save layer: {e}")
            if os.path.exists(blob_path):
                os.remove(blob_path)
            raise
    
    def get_layer(self, digest: str) -> Optional[bytes]:
        """
        Get an image layer.
        
        Args:
            digest: Layer digest
            
        Returns:
            Layer data or None if not found
        """
        blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
        if not os.path.exists(blob_path):
            logger.error(f"Layer blob not found: {digest}")
            return None
        
        try:
            with open(blob_path, 'rb') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to get layer {digest}: {e}")
            return None
    
    def get_blob_size(self, digest: str) -> int:
        """
        Get the size of a blob.
        
        Args:
            digest: Blob digest
            
        Returns:
            Blob size in bytes
        """
        blob_path = os.path.join(REGISTRY_BLOBS_PATH, digest)
        if not os.path.exists(blob_path):
            return 0
        
        return os.path.getsize(blob_path)
    
    def push(self, layers: List[Union[bytes, BinaryIO]], config: ImageConfig) -> bool:
        """
        Push an image to the registry.
        
        Args:
            layers: Image layers (compressed tars)
            config: Image configuration
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Save config
                config_digest = self.save_config(config)
                
                # Save layers
                layer_digests = []
                for layer in layers:
                    layer_digest = self.save_layer(layer)
                    layer_digests.append(layer_digest)
                
                # Create manifest
                manifest = ImageManifest(
                    config_digest=config_digest,
                    layer_digests=layer_digests
                )
                
                # Save manifest
                manifest_digest = self.save_manifest(manifest)
                
                # Save tag
                return self.save_tag(manifest_digest)
        except Exception as e:
            logger.error(f"Failed to push image {self.name}:{self.tag}: {e}")
            return False
    
    def pull(self) -> Optional[Tuple[List[bytes], ImageConfig]]:
        """
        Pull an image from the registry.
        
        Returns:
            Tuple of (layers, config) or None if not found
        """
        try:
            # Get manifest
            manifest = self.get_manifest()
            if not manifest:
                logger.error(f"Manifest not found for {self.name}:{self.tag}")
                return None
            
            # Get config
            config = self.get_config()
            if not config:
                logger.error(f"Config not found for {self.name}:{self.tag}")
                return None
            
            # Get layers
            layers = []
            for layer_digest in manifest.layer_digests:
                layer = self.get_layer(layer_digest)
                if not layer:
                    logger.error(f"Layer not found: {layer_digest}")
                    return None
                
                layers.append(layer)
            
            return (layers, config)
        except Exception as e:
            logger.error(f"Failed to pull image {self.name}:{self.tag}: {e}")
            return None
    
    def create_from_tar(self, tar_path: str, config: Optional[ImageConfig] = None) -> bool:
        """
        Create an image from a tar archive.
        
        Args:
            tar_path: Path to the tar archive
            config: Image configuration, or None to use default
            
        Returns:
            bool: Success or failure
        """
        try:
            # Create temp directory
            temp_dir = os.path.join(REGISTRY_TEMP_PATH, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                # Extract tar
                with tarfile.open(tar_path, 'r') as tar:
                    tar.extractall(temp_dir)
                
                # Create layer
                layer_file = os.path.join(temp_dir, "layer.tar.gz")
                with tarfile.open(layer_file, 'w:gz') as tar:
                    for item in os.listdir(temp_dir):
                        if item != "layer.tar.gz":
                            tar.add(os.path.join(temp_dir, item), arcname=item)
                
                # Read layer
                with open(layer_file, 'rb') as f:
                    layer_data = f.read()
                
                # Create config if not provided
                if not config:
                    config = ImageConfig()
                
                # Push image
                return self.push([layer_data], config)
            finally:
                # Clean up
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.error(f"Failed to create image from tar: {e}")
            return False
    
    def extract_to_dir(self, target_dir: str) -> bool:
        """
        Extract the image to a directory.
        
        Args:
            target_dir: Target directory
            
        Returns:
            bool: Success or failure
        """
        try:
            # Pull image
            result = self.pull()
            if not result:
                logger.error(f"Failed to pull image {self.name}:{self.tag}")
                return False
            
            layers, config = result
            
            # Create target directory
            os.makedirs(target_dir, exist_ok=True)
            
            # Extract layers
            for i, layer in enumerate(layers):
                # Create temp file for layer
                layer_file = os.path.join(REGISTRY_TEMP_PATH, f"layer_{i}.tar.gz")
                with open(layer_file, 'wb') as f:
                    f.write(layer)
                
                try:
                    # Extract layer
                    with tarfile.open(layer_file, 'r:gz') as tar:
                        tar.extractall(target_dir)
                finally:
                    # Clean up
                    if os.path.exists(layer_file):
                        os.remove(layer_file)
            
            return True
        except Exception as e:
            logger.error(f"Failed to extract image to directory: {e}")
            return False
    
    @staticmethod
    def list_images() -> List[Tuple[str, str]]:
        """
        List all images in the registry.
        
        Returns:
            List of (name, tag) tuples
        """
        images = []
        
        # Check if registry images directory exists
        if not os.path.exists(REGISTRY_IMAGES_PATH):
            return []
        
        # List image directories
        for name in os.listdir(REGISTRY_IMAGES_PATH):
            image_dir = os.path.join(REGISTRY_IMAGES_PATH, name)
            if not os.path.isdir(image_dir):
                continue
            
            # List tag files
            for filename in os.listdir(image_dir):
                if not filename.endswith('.json'):
                    continue
                
                tag = filename[:-5]  # Remove .json extension
                images.append((name, tag))
        
        return images
    
    @staticmethod
    def gc() -> int:
        """
        Garbage collect unused blobs.
        
        Returns:
            Number of blobs removed
        """
        try:
            # Collect all referenced digests
            referenced_digests = set()
            
            # List all images
            for name, tag in Image.list_images():
                image = Image(name, tag)
                
                # Get manifest
                manifest = image.get_manifest()
                if not manifest:
                    continue
                
                # Add manifest digest
                tag = image.load_tag()
                if tag:
                    referenced_digests.add(tag.digest)
                
                # Add config digest
                referenced_digests.add(manifest.config_digest)
                
                # Add layer digests
                referenced_digests.update(manifest.layer_digests)
            
            # List all blobs
            all_blobs = set()
            if os.path.exists(REGISTRY_BLOBS_PATH):
                all_blobs.update(os.listdir(REGISTRY_BLOBS_PATH))
            
            # Find unused blobs
            unused_blobs = all_blobs - referenced_digests
            
            # Remove unused blobs
            removed = 0
            for blob in unused_blobs:
                blob_path = os.path.join(REGISTRY_BLOBS_PATH, blob)
                if os.path.exists(blob_path):
                    os.remove(blob_path)
                    removed += 1
            
            logger.info(f"Garbage collected {removed} unused blobs")
            return removed
        except Exception as e:
            logger.error(f"Failed to garbage collect: {e}")
            return 0

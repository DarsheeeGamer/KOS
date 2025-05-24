
"""
KOS Container System

This module provides containerization capabilities for KOS, allowing isolated
execution environments similar to Docker or podman in Linux.
"""

import os
import sys
import time
import logging
import threading
import uuid
import json
import shutil
from typing import Dict, List, Any, Optional, Union, Tuple

# Set up logging
logger = logging.getLogger('KOS.container')

# Container registry
CONTAINERS = {}
CONTAINER_LOCK = threading.Lock()

class Container:
    """Container class representing an isolated execution environment"""
    
    def __init__(self, container_id: str, name: str, image: str, command: str = None):
        """Initialize a new container"""
        self.id = container_id
        self.name = name
        self.image = image
        self.command = command
        self.status = "created"  # created, running, stopped, paused, exited
        self.created_at = time.time()
        self.started_at = None
        self.environment = {}
        self.volumes = []
        self.ports = {}
        self.pid = None
        self.exit_code = None
        self.logs = []
    
    def start(self):
        """Start the container"""
        if self.status == "running":
            return False, "Container already running"
        
        # Simulate container startup
        self.status = "running"
        self.started_at = time.time()
        self.pid = 1000 + hash(self.id) % 1000
        self.logs.append(f"Container {self.id} started")
        
        return True, "Container started"
    
    def stop(self, timeout: int = 10):
        """Stop the container"""
        if self.status != "running":
            return False, "Container not running"
        
        # Simulate container stop
        self.status = "stopped"
        self.exit_code = 0
        self.logs.append(f"Container {self.id} stopped")
        
        return True, "Container stopped"
    
    def pause(self):
        """Pause the container"""
        if self.status != "running":
            return False, "Container not running"
        
        # Simulate container pause
        self.status = "paused"
        self.logs.append(f"Container {self.id} paused")
        
        return True, "Container paused"
    
    def unpause(self):
        """Unpause the container"""
        if self.status != "paused":
            return False, "Container not paused"
        
        # Simulate container unpause
        self.status = "running"
        self.logs.append(f"Container {self.id} unpaused")
        
        return True, "Container unpaused"
    
    def restart(self):
        """Restart the container"""
        if self.status not in ["running", "stopped", "exited"]:
            return False, "Cannot restart container in current state"
        
        # Simulate container restart
        success, message = self.stop()
        if not success:
            return False, f"Failed to stop container: {message}"
        
        success, message = self.start()
        if not success:
            return False, f"Failed to start container: {message}"
        
        return True, "Container restarted"
    
    def remove(self, force: bool = False):
        """Remove the container"""
        if self.status == "running" and not force:
            return False, "Cannot remove running container (use force=True to force removal)"
        
        # Simulate container removal
        with CONTAINER_LOCK:
            if self.id in CONTAINERS:
                del CONTAINERS[self.id]
        
        return True, "Container removed"
    
    def exec(self, command: str):
        """Execute a command in the container"""
        if self.status != "running":
            return False, "Container not running", None
        
        # Simulate command execution
        self.logs.append(f"Executed command: {command}")
        
        # Return simulated output
        return True, "Command executed", f"Output of '{command}'"
    
    def get_logs(self, tail: int = None):
        """Get container logs"""
        if tail:
            return self.logs[-tail:]
        return self.logs
    
    def to_dict(self):
        """Convert container to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "image": self.image,
            "command": self.command,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "environment": self.environment,
            "volumes": self.volumes,
            "ports": self.ports,
            "pid": self.pid,
            "exit_code": self.exit_code
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create container from dictionary"""
        container = cls(data["id"], data["name"], data["image"], data["command"])
        container.status = data["status"]
        container.created_at = data["created_at"]
        container.started_at = data["started_at"]
        container.environment = data["environment"]
        container.volumes = data["volumes"]
        container.ports = data["ports"]
        container.pid = data["pid"]
        container.exit_code = data["exit_code"]
        return container

class ContainerManager:
    """Manager for container operations"""
    
    @staticmethod
    def create_container(name: str, image: str, command: str = None, environment: Dict[str, str] = None, 
                         volumes: List[str] = None, ports: Dict[str, str] = None) -> Tuple[bool, str, Optional[Container]]:
        """Create a new container"""
        # Generate container ID
        container_id = str(uuid.uuid4())[:12]
        
        # Validate name uniqueness
        with CONTAINER_LOCK:
            for c in CONTAINERS.values():
                if c.name == name:
                    return False, f"Container name '{name}' already exists", None
        
        # Create container
        container = Container(container_id, name, image, command)
        
        # Set environment variables
        if environment:
            container.environment = environment
        
        # Set volumes
        if volumes:
            container.volumes = volumes
        
        # Set port mappings
        if ports:
            container.ports = ports
        
        # Add to registry
        with CONTAINER_LOCK:
            CONTAINERS[container_id] = container
        
        return True, f"Container {container_id} created", container
    
    @staticmethod
    def get_container(container_id: str) -> Optional[Container]:
        """Get container by ID"""
        with CONTAINER_LOCK:
            return CONTAINERS.get(container_id)
    
    @staticmethod
    def get_container_by_name(name: str) -> Optional[Container]:
        """Get container by name"""
        with CONTAINER_LOCK:
            for container in CONTAINERS.values():
                if container.name == name:
                    return container
        return None
    
    @staticmethod
    def list_containers(all: bool = False) -> List[Container]:
        """List containers"""
        with CONTAINER_LOCK:
            if all:
                return list(CONTAINERS.values())
            else:
                return [c for c in CONTAINERS.values() if c.status != "exited"]
    
    @staticmethod
    def save_containers(filepath: str) -> Tuple[bool, str]:
        """Save containers to file"""
        try:
            with CONTAINER_LOCK:
                data = {cid: container.to_dict() for cid, container in CONTAINERS.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Containers saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save containers: {str(e)}"
    
    @staticmethod
    def load_containers(filepath: str) -> Tuple[bool, str]:
        """Load containers from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with CONTAINER_LOCK:
                CONTAINERS.clear()
                for cid, container_data in data.items():
                    CONTAINERS[cid] = Container.from_dict(container_data)
            
            return True, f"Containers loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load containers: {str(e)}"

class Image:
    """Container image class"""
    
    def __init__(self, image_id: str, name: str, tag: str = "latest"):
        """Initialize a new image"""
        self.id = image_id
        self.name = name
        self.tag = tag
        self.created_at = time.time()
        self.size = 0
        self.layers = []
        self.config = {}
    
    def to_dict(self):
        """Convert image to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "tag": self.tag,
            "created_at": self.created_at,
            "size": self.size,
            "layers": self.layers,
            "config": self.config
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create image from dictionary"""
        image = cls(data["id"], data["name"], data["tag"])
        image.created_at = data["created_at"]
        image.size = data["size"]
        image.layers = data["layers"]
        image.config = data["config"]
        return image

class ImageManager:
    """Manager for image operations"""
    
    _images = {}  # Local image registry
    _images_lock = threading.Lock()
    
    @staticmethod
    def list_images():
        """List available images"""
        with ImageManager._images_lock:
            return list(ImageManager._images.values())
    
    @staticmethod
    def get_image(name, tag="latest"):
        """Get image by name and tag"""
        with ImageManager._images_lock:
            for image in ImageManager._images.values():
                if image.name == name and image.tag == tag:
                    return image
        return None
    
    @staticmethod
    def pull_image(name, tag="latest"):
        """Pull image from registry (simulated)"""
        # Generate image ID
        image_id = f"sha256:{uuid.uuid4().hex[:12]}"
        
        # Create image
        image = Image(image_id, name, tag)
        image.size = 50 * 1024 * 1024  # 50 MB simulated size
        image.layers = [f"layer{i}" for i in range(3)]  # Simulated layers
        
        # Add to registry
        with ImageManager._images_lock:
            ImageManager._images[image_id] = image
        
        return True, f"Image {name}:{tag} pulled", image
    
    @staticmethod
    def remove_image(name, tag="latest", force=False):
        """Remove image from registry"""
        with ImageManager._images_lock:
            for image_id, image in list(ImageManager._images.items()):
                if image.name == name and image.tag == tag:
                    # Check if any containers are using this image
                    in_use = False
                    with CONTAINER_LOCK:
                        for container in CONTAINERS.values():
                            if container.image == f"{name}:{tag}":
                                in_use = True
                                break
                    
                    if in_use and not force:
                        return False, f"Image {name}:{tag} is in use by containers", None
                    
                    # Remove image
                    del ImageManager._images[image_id]
                    return True, f"Image {name}:{tag} removed", None
        
        return False, f"Image {name}:{tag} not found", None
    
    @staticmethod
    def save_images(filepath):
        """Save images to file"""
        try:
            with ImageManager._images_lock:
                data = {img_id: img.to_dict() for img_id, img in ImageManager._images.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Images saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save images: {str(e)}"
    
    @staticmethod
    def load_images(filepath):
        """Load images from file"""
        try:
            if not os.path.exists(filepath):
                return False, f"File {filepath} does not exist"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with ImageManager._images_lock:
                ImageManager._images.clear()
                for img_id, img_data in data.items():
                    ImageManager._images[img_id] = Image.from_dict(img_data)
            
            return True, f"Images loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load images: {str(e)}"

# Initialize container system
def initialize():
    """Initialize the container system"""
    logger.info("Initializing KOS container system")
    
    # Create container directory
    container_dir = os.path.join(os.path.expanduser('~'), '.kos', 'containers')
    os.makedirs(container_dir, exist_ok=True)
    
    # Add some sample images
    image_db = os.path.join(container_dir, 'images.json')
    
    # Create sample images if DB doesn't exist
    if not os.path.exists(image_db):
        sample_images = {
            "sha256:1234567890ab": Image("sha256:1234567890ab", "kos/base", "latest"),
            "sha256:2345678901bc": Image("sha256:2345678901bc", "kos/python", "3.9"),
            "sha256:3456789012cd": Image("sha256:3456789012cd", "kos/nginx", "1.21")
        }
        
        # Add simulated sizes and layers
        sample_images["sha256:1234567890ab"].size = 20 * 1024 * 1024  # 20 MB
        sample_images["sha256:2345678901bc"].size = 50 * 1024 * 1024  # 50 MB
        sample_images["sha256:3456789012cd"].size = 30 * 1024 * 1024  # 30 MB
        
        # Add to registry
        with ImageManager._images_lock:
            ImageManager._images.update(sample_images)
        
        # Write to disk
        with open(image_db, 'w') as f:
            json.dump({img_id: img.to_dict() for img_id, img in sample_images.items()}, f, indent=2)
    else:
        # Load images from disk
        ImageManager.load_images(image_db)
    
    # Load containers if they exist
    container_db = os.path.join(container_dir, 'containers.json')
    if os.path.exists(container_db):
        ContainerManager.load_containers(container_db)
    
    logger.info("KOS container system initialized")

# Initialize on import
initialize()

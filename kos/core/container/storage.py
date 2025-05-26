"""
KOS Container Storage Management

Provides container storage capabilities:
- Volume management
- Container filesystem setup
- Storage driver interface
"""

import os
import time
import json
import uuid
import shutil
import logging
from typing import Dict, List, Any, Optional, Tuple

# Initialize logging
logger = logging.getLogger('KOS.container.storage')

class StorageManager:
    """
    Container storage manager
    """
    def __init__(self, volumes_dir: str):
        """
        Initialize the storage manager
        
        Args:
            volumes_dir: Directory for storing volumes
        """
        self.volumes_dir = volumes_dir
        os.makedirs(volumes_dir, exist_ok=True)
        
        # Volume metadata file
        self.metadata_file = os.path.join(volumes_dir, 'volumes.json')
        
        # Volume registry
        self.volumes = {}  # name -> volume info
        
        # Load volumes
        self._load_volumes()
    
    def _load_volumes(self):
        """Load volumes from metadata file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    self.volumes = json.load(f)
                
                logger.info(f"Loaded {len(self.volumes)} volumes")
            
            except Exception as e:
                logger.error(f"Error loading volumes: {e}")
                self.volumes = {}
    
    def _save_volumes(self):
        """Save volumes to metadata file"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.volumes, f, indent=2)
            
            logger.info(f"Saved {len(self.volumes)} volumes")
        
        except Exception as e:
            logger.error(f"Error saving volumes: {e}")
    
    def create_volume(self, name: str, path: Optional[str] = None) -> bool:
        """
        Create a new volume
        
        Args:
            name: Volume name
            path: Optional path for bind-mounted volumes
        """
        if name in self.volumes:
            logger.warning(f"Volume {name} already exists")
            return False
        
        try:
            # Generate a volume ID
            volume_id = str(uuid.uuid4())[:12]
            
            # Create volume directory
            volume_path = os.path.join(self.volumes_dir, volume_id)
            if not path:  # Regular volume
                os.makedirs(volume_path, exist_ok=True)
            
            # Create volume metadata
            volume = {
                'id': volume_id,
                'name': name,
                'path': path or volume_path,
                'bind': bool(path),
                'created': time.time(),
                'mountpoint': path or volume_path,
                'labels': {},
                'in_use': False
            }
            
            # Add to registry
            self.volumes[name] = volume
            self._save_volumes()
            
            logger.info(f"Created volume: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error creating volume {name}: {e}")
            return False
    
    def remove_volume(self, name: str, force: bool = False) -> bool:
        """
        Remove a volume
        
        Args:
            name: Volume name
            force: Force removal even if in use
        """
        if name not in self.volumes:
            logger.warning(f"Volume {name} does not exist")
            return False
        
        volume = self.volumes[name]
        
        if volume['in_use'] and not force:
            logger.warning(f"Volume {name} is in use")
            return False
        
        try:
            # Remove volume directory if not a bind mount
            if not volume['bind'] and os.path.exists(volume['path']):
                shutil.rmtree(volume['path'])
            
            # Remove from registry
            del self.volumes[name]
            self._save_volumes()
            
            logger.info(f"Removed volume: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error removing volume {name}: {e}")
            return False
    
    def list_volumes(self) -> List[Dict[str, Any]]:
        """List all volumes"""
        volumes = []
        for name, volume in self.volumes.items():
            volumes.append({
                'id': volume['id'],
                'name': name,
                'mountpoint': volume['mountpoint'],
                'bind': volume['bind'],
                'created': volume['created'],
                'in_use': volume['in_use']
            })
        
        return volumes
    
    def prepare_container_fs(self, container, image) -> bool:
        """
        Prepare filesystem for a container
        
        Args:
            container: Container object
            image: Image object
        """
        try:
            # Create container root directory
            container_dir = os.path.join(os.path.dirname(self.volumes_dir), 'containers', container.id)
            os.makedirs(container_dir, exist_ok=True)
            
            # Create rootfs directory
            rootfs = os.path.join(container_dir, 'rootfs')
            os.makedirs(rootfs, exist_ok=True)
            
            # Create container log directory
            log_dir = os.path.join(container_dir, 'logs')
            os.makedirs(log_dir, exist_ok=True)
            
            # Setup rootfs using the image
            # In a real implementation, this would use overlay fs or similar
            # For this implementation, we'll just copy the image rootfs
            if image.rootfs_path and os.path.exists(image.rootfs_path):
                # Copy image rootfs to container rootfs
                for item in os.listdir(image.rootfs_path):
                    src = os.path.join(image.rootfs_path, item)
                    dst = os.path.join(rootfs, item)
                    
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
            
            # Setup container config
            config_path = os.path.join(container_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump(container.to_dict(), f, indent=2)
            
            # Setup container log files
            stdout_log = os.path.join(log_dir, 'stdout.log')
            stderr_log = os.path.join(log_dir, 'stderr.log')
            
            with open(stdout_log, 'w') as f:
                f.write('')
            
            with open(stderr_log, 'w') as f:
                f.write('')
            
            # Update container paths
            container.rootfs = rootfs
            container.config_path = config_path
            container.log_path = log_dir
            
            # Mount volumes
            self._mount_volumes(container, rootfs)
            
            logger.info(f"Prepared filesystem for container {container.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error preparing filesystem for container {container.name}: {e}")
            return False
    
    def _mount_volumes(self, container, rootfs):
        """
        Mount volumes into container
        
        Args:
            container: Container object
            rootfs: Container rootfs path
        """
        for volume_config in container.volumes:
            # Parse volume config
            if ':' in volume_config:
                source, target = volume_config.split(':', 1)
            else:
                source = volume_config
                target = volume_config
            
            # Normalize target path
            target = target.lstrip('/')
            target_path = os.path.join(rootfs, target)
            
            # Check if source is a named volume
            if source in self.volumes:
                volume = self.volumes[source]
                source_path = volume['mountpoint']
                volume['in_use'] = True
            else:
                # Assume it's a host path
                source_path = os.path.abspath(source)
                
                # Create a bind volume for it
                volume_name = f"bind_{container.name}_{os.path.basename(source)}"
                self.create_volume(volume_name, source_path)
            
            # Create target directory
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            # In a real implementation, we would use mount system calls
            # For this implementation, we'll create a symlink or directory
            if os.path.exists(target_path):
                if os.path.isdir(target_path):
                    shutil.rmtree(target_path)
                else:
                    os.remove(target_path)
            
            # Create a symlink or copy the directory
            if os.path.isdir(source_path):
                os.symlink(source_path, target_path, target_is_directory=True)
            else:
                os.symlink(source_path, target_path)
            
            logger.info(f"Mounted {source_path} to {target_path} in container {container.name}")
    
    def cleanup_container_fs(self, container) -> bool:
        """
        Clean up filesystem for a container
        
        Args:
            container: Container object
        """
        try:
            # Get container directory
            container_dir = os.path.dirname(container.rootfs) if container.rootfs else None
            
            if container_dir and os.path.exists(container_dir):
                # Unmount volumes
                self._unmount_volumes(container)
                
                # Remove container directory
                shutil.rmtree(container_dir)
            
            logger.info(f"Cleaned up filesystem for container {container.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error cleaning up filesystem for container {container.name}: {e}")
            return False
    
    def _unmount_volumes(self, container):
        """
        Unmount volumes from container
        
        Args:
            container: Container object
        """
        # Mark volumes as no longer in use
        for volume_config in container.volumes:
            if ':' in volume_config:
                source, _ = volume_config.split(':', 1)
            else:
                source = volume_config
            
            if source in self.volumes:
                self.volumes[source]['in_use'] = False
            
            # Check for auto-created bind volumes
            volume_name = f"bind_{container.name}_{os.path.basename(source)}"
            if volume_name in self.volumes:
                self.remove_volume(volume_name)
        
        self._save_volumes()

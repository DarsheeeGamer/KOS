"""
KOS Container Image Management

Provides container image management capabilities:
- Image pulling and storage
- Image building from Dockerfiles
- Image metadata and layer management
- Registry integration
"""

import os
import time
import json
import uuid
import shutil
import hashlib
import tarfile
import logging
import tempfile
import requests
from typing import Dict, List, Any, Optional, Tuple

# Initialize logging
logger = logging.getLogger('KOS.container.image')

class Image:
    """Container image class"""
    def __init__(self, name: str, tag: str = 'latest', image_dict: Dict[str, Any] = None):
        """
        Initialize an image
        
        Args:
            name: Image name
            tag: Image tag
            image_dict: Image data dictionary (for loading)
        """
        self.name = name
        self.tag = tag
        self.id = str(uuid.uuid4())[:12]  # Short UUID for image ID
        
        if image_dict:
            # Load from dictionary
            self._load_from_dict(image_dict)
        else:
            # Initialize with defaults
            self.created = time.time()
            self.size = 0
            self.layers = []
            self.digests = {}
            self.architecture = 'amd64'
            self.os = 'linux'
            self.author = 'KOS'
            self.default_command = ['/bin/sh']
            self.default_entrypoint = []
            self.env = {}
            self.labels = {}
            self.config_path = None
            self.rootfs_path = None
            self.manifest_path = None
    
    def _load_from_dict(self, data: Dict[str, Any]):
        """Load image from dictionary"""
        self.id = data.get('id', str(uuid.uuid4())[:12])
        self.created = data.get('created', time.time())
        self.size = data.get('size', 0)
        self.layers = data.get('layers', [])
        self.digests = data.get('digests', {})
        self.architecture = data.get('architecture', 'amd64')
        self.os = data.get('os', 'linux')
        self.author = data.get('author', 'KOS')
        self.default_command = data.get('default_command', ['/bin/sh'])
        self.default_entrypoint = data.get('default_entrypoint', [])
        self.env = data.get('env', {})
        self.labels = data.get('labels', {})
        self.config_path = data.get('config_path')
        self.rootfs_path = data.get('rootfs_path')
        self.manifest_path = data.get('manifest_path')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert image to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'tag': self.tag,
            'created': self.created,
            'size': self.size,
            'layers': self.layers,
            'digests': self.digests,
            'architecture': self.architecture,
            'os': self.os,
            'author': self.author,
            'default_command': self.default_command,
            'default_entrypoint': self.default_entrypoint,
            'env': self.env,
            'labels': self.labels,
            'config_path': self.config_path,
            'rootfs_path': self.rootfs_path,
            'manifest_path': self.manifest_path
        }
    
    @property
    def full_name(self) -> str:
        """Get the full image name with tag"""
        return f"{self.name}:{self.tag}"

class ImageManager:
    """
    Container image manager
    """
    def __init__(self, images_dir: str):
        """
        Initialize the image manager
        
        Args:
            images_dir: Directory for storing images
        """
        self.images_dir = images_dir
        os.makedirs(images_dir, exist_ok=True)
        
        # Image metadata file
        self.metadata_file = os.path.join(images_dir, 'images.json')
        
        # Image registry
        self.images = {}  # name:tag -> Image
        
        # Default registry
        self.default_registry = 'registry.kos.io'
    
    def load_images(self):
        """Load images from metadata file"""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, 'r') as f:
                    image_dicts = json.load(f)
                
                for image_dict in image_dicts:
                    name = image_dict.get('name')
                    tag = image_dict.get('tag', 'latest')
                    
                    if name:
                        image = Image(name, tag, image_dict)
                        self.images[f"{name}:{tag}"] = image
                
                logger.info(f"Loaded {len(self.images)} images")
            
            except Exception as e:
                logger.error(f"Error loading images: {e}")
    
    def save_images(self):
        """Save images to metadata file"""
        try:
            image_dicts = [image.to_dict() for image in self.images.values()]
            
            with open(self.metadata_file, 'w') as f:
                json.dump(image_dicts, f, indent=2)
            
            logger.info(f"Saved {len(self.images)} images")
        
        except Exception as e:
            logger.error(f"Error saving images: {e}")
    
    def get_image(self, name_or_id: str) -> Optional[Image]:
        """
        Get an image by name, name:tag, or ID
        
        Args:
            name_or_id: Image name, name:tag, or ID
        """
        # Try direct lookup by name:tag
        if name_or_id in self.images:
            return self.images[name_or_id]
        
        # Try lookup by name with default tag
        if ':' not in name_or_id:
            if f"{name_or_id}:latest" in self.images:
                return self.images[f"{name_or_id}:latest"]
        
        # Try lookup by ID
        for image in self.images.values():
            if image.id == name_or_id:
                return image
        
        return None
    
    def pull_image(self, name: str, tag: str = 'latest') -> bool:
        """
        Pull an image from a registry
        
        Args:
            name: Image name
            tag: Image tag
        """
        logger.info(f"Pulling image: {name}:{tag}")
        
        # In a real implementation, this would contact a container registry
        # and download the image layers
        try:
            # Parse registry, name, and tag
            registry = self.default_registry
            if '/' in name:
                parts = name.split('/')
                if '.' in parts[0]:  # Likely a registry
                    registry = parts[0]
                    name = '/'.join(parts[1:])
            
            # Create a directory for the image
            image_id = hashlib.md5(f"{name}:{tag}".encode()).hexdigest()[:12]
            image_dir = os.path.join(self.images_dir, image_id)
            os.makedirs(image_dir, exist_ok=True)
            
            # Create image rootfs directory
            rootfs_path = os.path.join(image_dir, 'rootfs')
            os.makedirs(rootfs_path, exist_ok=True)
            
            # In a real implementation, we would download the image manifest,
            # image config, and image layers from the registry
            
            # For this implementation, we'll create a basic image structure
            
            # Create bin directory
            bin_dir = os.path.join(rootfs_path, 'bin')
            os.makedirs(bin_dir, exist_ok=True)
            
            # Create a simple shell script
            with open(os.path.join(bin_dir, 'sh'), 'w') as f:
                f.write('#!/bin/sh\necho "KOS Container Shell"\n')
            os.chmod(os.path.join(bin_dir, 'sh'), 0o755)
            
            # Create etc directory
            etc_dir = os.path.join(rootfs_path, 'etc')
            os.makedirs(etc_dir, exist_ok=True)
            
            # Create hostname file
            with open(os.path.join(etc_dir, 'hostname'), 'w') as f:
                f.write(f"{name}-container\n")
            
            # Create hosts file
            with open(os.path.join(etc_dir, 'hosts'), 'w') as f:
                f.write("127.0.0.1 localhost\n")
                f.write(f"127.0.1.1 {name}-container\n")
            
            # Create image config
            config = {
                'created': time.time(),
                'author': 'KOS',
                'architecture': 'amd64',
                'os': 'linux',
                'config': {
                    'Hostname': f"{name}-container",
                    'Domainname': '',
                    'User': '',
                    'AttachStdin': False,
                    'AttachStdout': True,
                    'AttachStderr': True,
                    'Tty': False,
                    'OpenStdin': False,
                    'StdinOnce': False,
                    'Env': [
                        'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
                    ],
                    'Cmd': ['/bin/sh'],
                    'Image': f"{registry}/{name}:{tag}",
                    'WorkingDir': '/',
                    'Entrypoint': None,
                    'Labels': {}
                },
                'rootfs': {
                    'type': 'layers',
                    'diff_ids': [
                        f"sha256:{hashlib.sha256(image_id.encode()).hexdigest()}"
                    ]
                },
                'history': [
                    {
                        'created': time.time(),
                        'created_by': f"KOS pull {name}:{tag}",
                        'empty_layer': False
                    }
                ]
            }
            
            # Write config file
            config_path = os.path.join(image_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Write manifest file
            manifest = {
                'schemaVersion': 2,
                'mediaType': 'application/vnd.docker.distribution.manifest.v2+json',
                'config': {
                    'mediaType': 'application/vnd.docker.container.image.v1+json',
                    'size': os.path.getsize(config_path),
                    'digest': f"sha256:{hashlib.sha256(open(config_path, 'rb').read()).hexdigest()}"
                },
                'layers': [
                    {
                        'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip',
                        'size': 0,
                        'digest': f"sha256:{hashlib.sha256(image_id.encode()).hexdigest()}"
                    }
                ]
            }
            
            manifest_path = os.path.join(image_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create the image object
            image = Image(name, tag)
            image.id = image_id
            image.size = self._get_directory_size(rootfs_path)
            image.layers = [layer['digest'] for layer in manifest['layers']]
            image.digests = {
                'config': manifest['config']['digest'],
                'manifest': f"sha256:{hashlib.sha256(open(manifest_path, 'rb').read()).hexdigest()}"
            }
            image.architecture = config['architecture']
            image.os = config['os']
            image.author = config['author']
            image.default_command = config['config']['Cmd']
            image.default_entrypoint = config['config'].get('Entrypoint') or []
            image.env = {e.split('=')[0]: e.split('=')[1] for e in config['config']['Env'] if '=' in e}
            image.labels = config['config'].get('Labels') or {}
            image.config_path = config_path
            image.rootfs_path = rootfs_path
            image.manifest_path = manifest_path
            
            # Add the image to the registry
            self.images[f"{name}:{tag}"] = image
            self.save_images()
            
            logger.info(f"Successfully pulled image: {name}:{tag}")
            return True
        
        except Exception as e:
            logger.error(f"Error pulling image {name}:{tag}: {e}")
            return False
    
    def build_image(self, name: str, path: str, tag: str = 'latest') -> bool:
        """
        Build an image from a Dockerfile
        
        Args:
            name: Image name
            path: Path to the build context (directory containing Dockerfile)
            tag: Image tag
        """
        logger.info(f"Building image: {name}:{tag} from {path}")
        
        # In a real implementation, this would parse the Dockerfile and
        # execute the build steps to create the image
        try:
            # Create a directory for the image
            image_id = hashlib.md5(f"{name}:{tag}:{time.time()}".encode()).hexdigest()[:12]
            image_dir = os.path.join(self.images_dir, image_id)
            os.makedirs(image_dir, exist_ok=True)
            
            # Create image rootfs directory
            rootfs_path = os.path.join(image_dir, 'rootfs')
            os.makedirs(rootfs_path, exist_ok=True)
            
            # Check if Dockerfile exists
            dockerfile_path = os.path.join(path, 'Dockerfile')
            if not os.path.exists(dockerfile_path):
                logger.error(f"Dockerfile not found in {path}")
                return False
            
            # Parse Dockerfile and execute build steps
            with open(dockerfile_path, 'r') as f:
                dockerfile_lines = f.readlines()
            
            # Extract base image, commands, etc.
            base_image = None
            cmd = ['/bin/sh']
            entrypoint = []
            env = {}
            labels = {}
            workdir = '/'
            
            for line in dockerfile_lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split(' ', 1)
                if len(parts) < 2:
                    continue
                
                instruction, args = parts
                instruction = instruction.upper()
                
                if instruction == 'FROM':
                    base_image = args.strip()
                elif instruction == 'RUN':
                    # In a real implementation, we would execute the command
                    logger.debug(f"Would run: {args}")
                elif instruction == 'CMD':
                    try:
                        cmd = json.loads(args)
                    except:
                        cmd = args.split()
                elif instruction == 'ENTRYPOINT':
                    try:
                        entrypoint = json.loads(args)
                    except:
                        entrypoint = args.split()
                elif instruction == 'ENV':
                    if '=' in args:
                        key, value = args.split('=', 1)
                        env[key.strip()] = value.strip()
                    else:
                        parts = args.split()
                        if len(parts) >= 2:
                            env[parts[0]] = parts[1]
                elif instruction == 'LABEL':
                    for part in args.split():
                        if '=' in part:
                            key, value = part.split('=', 1)
                            labels[key.strip()] = value.strip()
                elif instruction == 'WORKDIR':
                    workdir = args.strip()
                elif instruction == 'COPY' or instruction == 'ADD':
                    src_dest = args.split()
                    if len(src_dest) >= 2:
                        src, dest = src_dest[0], src_dest[-1]
                        src_path = os.path.join(path, src)
                        dest_path = os.path.join(rootfs_path, dest.lstrip('/'))
                        
                        if os.path.exists(src_path):
                            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                            if os.path.isdir(src_path):
                                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src_path, dest_path)
            
            # Create a basic directory structure if it doesn't exist
            for directory in ['bin', 'etc', 'lib', 'usr', 'var']:
                os.makedirs(os.path.join(rootfs_path, directory), exist_ok=True)
            
            # Create a simple shell script if bin/sh doesn't exist
            if not os.path.exists(os.path.join(rootfs_path, 'bin', 'sh')):
                with open(os.path.join(rootfs_path, 'bin', 'sh'), 'w') as f:
                    f.write('#!/bin/sh\necho "KOS Container Shell"\n')
                os.chmod(os.path.join(rootfs_path, 'bin', 'sh'), 0o755)
            
            # Create hostname file
            with open(os.path.join(rootfs_path, 'etc', 'hostname'), 'w') as f:
                f.write(f"{name}-container\n")
            
            # Create hosts file
            with open(os.path.join(rootfs_path, 'etc', 'hosts'), 'w') as f:
                f.write("127.0.0.1 localhost\n")
                f.write(f"127.0.1.1 {name}-container\n")
            
            # Create image config
            config = {
                'created': time.time(),
                'author': 'KOS',
                'architecture': 'amd64',
                'os': 'linux',
                'config': {
                    'Hostname': f"{name}-container",
                    'Domainname': '',
                    'User': '',
                    'AttachStdin': False,
                    'AttachStdout': True,
                    'AttachStderr': True,
                    'Tty': False,
                    'OpenStdin': False,
                    'StdinOnce': False,
                    'Env': [f"{k}={v}" for k, v in env.items()],
                    'Cmd': cmd,
                    'Image': f"{name}:{tag}",
                    'WorkingDir': workdir,
                    'Entrypoint': entrypoint,
                    'Labels': labels
                },
                'rootfs': {
                    'type': 'layers',
                    'diff_ids': [
                        f"sha256:{hashlib.sha256(image_id.encode()).hexdigest()}"
                    ]
                },
                'history': [
                    {
                        'created': time.time(),
                        'created_by': f"KOS build {name}:{tag}",
                        'empty_layer': False
                    }
                ]
            }
            
            # Write config file
            config_path = os.path.join(image_dir, 'config.json')
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Write manifest file
            manifest = {
                'schemaVersion': 2,
                'mediaType': 'application/vnd.docker.distribution.manifest.v2+json',
                'config': {
                    'mediaType': 'application/vnd.docker.container.image.v1+json',
                    'size': os.path.getsize(config_path),
                    'digest': f"sha256:{hashlib.sha256(open(config_path, 'rb').read()).hexdigest()}"
                },
                'layers': [
                    {
                        'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip',
                        'size': 0,
                        'digest': f"sha256:{hashlib.sha256(image_id.encode()).hexdigest()}"
                    }
                ]
            }
            
            manifest_path = os.path.join(image_dir, 'manifest.json')
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create the image object
            image = Image(name, tag)
            image.id = image_id
            image.size = self._get_directory_size(rootfs_path)
            image.layers = [layer['digest'] for layer in manifest['layers']]
            image.digests = {
                'config': manifest['config']['digest'],
                'manifest': f"sha256:{hashlib.sha256(open(manifest_path, 'rb').read()).hexdigest()}"
            }
            image.architecture = config['architecture']
            image.os = config['os']
            image.author = config['author']
            image.default_command = config['config']['Cmd']
            image.default_entrypoint = config['config'].get('Entrypoint') or []
            image.env = {e.split('=')[0]: e.split('=')[1] for e in config['config']['Env'] if '=' in e}
            image.labels = config['config'].get('Labels') or {}
            image.config_path = config_path
            image.rootfs_path = rootfs_path
            image.manifest_path = manifest_path
            
            # Add the image to the registry
            self.images[f"{name}:{tag}"] = image
            self.save_images()
            
            logger.info(f"Successfully built image: {name}:{tag}")
            return True
        
        except Exception as e:
            logger.error(f"Error building image {name}:{tag}: {e}")
            return False
    
    def list_images(self) -> List[Dict[str, Any]]:
        """List all images"""
        images = []
        for image in self.images.values():
            images.append({
                'id': image.id,
                'name': image.name,
                'tag': image.tag,
                'size': image.size,
                'created': image.created
            })
        
        return images
    
    def remove_image(self, name_or_id: str, force: bool = False) -> bool:
        """
        Remove an image
        
        Args:
            name_or_id: Image name, name:tag, or ID
            force: Force removal even if containers are using the image
        """
        image = self.get_image(name_or_id)
        if not image:
            logger.warning(f"Image not found: {name_or_id}")
            return False
        
        # Check if any containers are using the image
        # In a real implementation, we would check if any containers are using the image
        
        # Remove the image directory
        image_dir = os.path.dirname(image.config_path) if image.config_path else None
        if image_dir and os.path.exists(image_dir):
            shutil.rmtree(image_dir)
        
        # Remove from registry
        del self.images[f"{image.name}:{image.tag}"]
        self.save_images()
        
        logger.info(f"Removed image: {image.name}:{image.tag}")
        return True
    
    def _get_directory_size(self, path: str) -> int:
        """Get the total size of a directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                total_size += os.path.getsize(file_path)
        
        return total_size

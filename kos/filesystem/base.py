"""
Base filesystem implementation with core functionality
"""
import os
import logging
import pickle
from datetime import datetime
from typing import Dict, Optional, Any, Union, List
from ..exceptions import (
    FileSystemError, InvalidDiskFormat, FileNotFound,
    NotADirectory, IsADirectory
)

logger = logging.getLogger('KOS')

class FileNode:
    """Represents a file or directory in the filesystem with enhanced memory management"""
    def __init__(self, name: str, node_type: str = 'file', parent=None):
        self.name = name
        self.type = node_type
        self.content = {} if node_type == 'directory' else ''
        self.metadata = {
            'created': datetime.now(),
            'modified': datetime.now(),
            'permissions': 0o644 if node_type == 'file' else 0o755,
            'owner': 'root',
            'group': 'root'
        }
        self.parent = parent
        self.size = 0
        self._cached_content = None
        self._cache_timestamp = None
        
    def invalidate_cache(self):
        """Invalidate cached content"""
        self._cached_content = None
        self._cache_timestamp = None
        
    def get_content(self):
        """Get content with caching for large files"""
        if self.type == 'directory':
            return self.content
            
        # Return cached content if it exists and is valid
        if self._cached_content is not None and self._cache_timestamp == self.metadata['modified']:
            return self._cached_content
            
        # Cache and return content for files
        self._cached_content = self.content
        self._cache_timestamp = self.metadata['modified']
        return self.content
        
    def update_content(self, new_content):
        """Update content with automatic cache invalidation"""
        if self.type == 'directory':
            self.content = new_content
            return
            
        self.content = new_content
        self.metadata['modified'] = datetime.now()
        
        # Calculate size for files
        if isinstance(new_content, str):
            self.size = len(new_content.encode('utf-8'))
        elif isinstance(new_content, bytes):
            self.size = len(new_content)
        else:
            self.size = 0
            
        # Invalidate cache
        self.invalidate_cache()

class BaseFileSystem:
    """Base filesystem with core functionality"""
    def __init__(self, disk_size_mb: int = 100):
        self.root = FileNode('/', 'directory')
        self.current_path = '/'
        self.disk_size = disk_size_mb * 1024 * 1024  # Convert to bytes
        self.user_system = None
        self._init_filesystem()

    def _init_filesystem(self):
        """Initialize the filesystem structure"""
        try:
            essential_dirs = ['bin', 'etc', 'home', 'usr', 'var', 'tmp', 'opt']
            for dirname in essential_dirs:
                path = f"/{dirname}"
                if not self._get_node(path):
                    self.mkdir(path)
                    logger.debug(f"Created directory: {path}")
            logger.info("Basic directory structure created")
        except Exception as e:
            logger.error(f"Failed to initialize filesystem: {e}")
            raise FileSystemError(f"Failed to initialize filesystem: {str(e)}")

    def _get_node(self, path: str) -> Optional[FileNode]:
        """Get node at specified path"""
        try:
            if not path or path == '/':
                return self.root

            parts = [p for p in path.split('/') if p]
            node = self.root

            for part in parts:
                if not isinstance(node.content, dict):
                    return None
                if part not in node.content:
                    return None
                node = node.content[part]

            return node

        except Exception as e:
            logger.error(f"Error getting node at {path}: {e}")
            return None

    def _resolve_path(self, path: str) -> str:
        """Resolve relative path to absolute path"""
        try:
            if not path:
                return self.current_path
            if path == '.':
                return self.current_path
            if path == '..':
                return os.path.dirname(self.current_path) or '/'

            # Handle relative paths
            if not path.startswith('/'):
                path = os.path.join(self.current_path, path)

            # Normalize the path
            normalized = os.path.normpath(path)

            # Ensure the path stays within our virtual filesystem
            if not normalized.startswith('/'):
                normalized = '/' + normalized

            logger.debug(f"Resolved path '{path}' to '{normalized}'")
            return normalized
        except Exception as e:
            logger.error(f"Error resolving path {path}: {e}")
            raise FileSystemError(f"Failed to resolve path: {str(e)}")

    def list_directory(self, path: str = ".", long_format: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """List contents of a directory"""
        try:
            abs_path = self._resolve_path(path)
            logger.debug(f"Listing directory: {abs_path}")

            node = self._get_node(abs_path)
            if not node:
                raise FileNotFound(f"Directory not found: {path}")
            if node.type != 'directory':
                raise NotADirectory(f"{path} is not a directory")

            if not isinstance(node.content, dict):
                logger.error(f"Invalid content type for directory {abs_path}")
                return []

            items = []
            for name, child in sorted(node.content.items()):
                if long_format:
                    items.append({
                        'name': name,
                        'type': child.type,
                        'size': child.size,
                        'perms': oct(child.metadata['permissions'])[2:],
                        'owner': child.metadata['owner'],
                        'group': child.metadata['group'],
                        'modified': child.metadata['modified'].strftime('%Y-%m-%d %H:%M')
                    })
                else:
                    items.append(name)

            logger.debug(f"Found {len(items)} items in directory {abs_path}")
            return items
        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise FileSystemError(f"Failed to list directory: {str(e)}")

    def mkdir(self, path: str, create_parents: bool = False) -> None:
        """Create a directory
        
        Args:
            path: The path to create
            create_parents: If True, create parent directories as needed
        """
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            dir_name = os.path.basename(abs_path)

            logger.debug(f"Creating directory: {abs_path}")

            # Handle parent directory creation if requested
            parent = self._get_node(parent_path)
            if not parent:
                if create_parents:
                    logger.debug(f"Creating parent directories for: {abs_path}")
                    self.mkdir(parent_path, create_parents=True)
                    parent = self._get_node(parent_path)
                else:
                    raise FileNotFound(f"Parent directory not found: {parent_path}")
            
            if parent.type != 'directory':
                raise NotADirectory(f"Parent path is not a directory: {parent_path}")

            if dir_name in parent.content:
                logger.debug(f"Directory already exists: {path}")
                return

            new_dir = FileNode(dir_name, 'directory', parent)
            if isinstance(parent.content, dict):
                parent.content[dir_name] = new_dir
                parent.metadata['modified'] = datetime.now()
                logger.debug(f"Successfully created directory: {abs_path}")
            else:
                raise FileSystemError(f"Parent node content is not a dictionary: {parent_path}")

        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise FileSystemError(f"Failed to create directory: {str(e)}")

class FileSystem(BaseFileSystem):
    """Enhanced filesystem implementation with persistence"""
    def __init__(self, disk_size_mb: int = 100):
        self.disk_file = 'kaede.kdsk'
        
        # Try to load existing filesystem state first
        if os.path.exists(self.disk_file):
            try:
                self._load_filesystem()
                logger.info(f"Loaded filesystem state from {self.disk_file}")
            except Exception as e:
                logger.error(f"Failed to load filesystem state: {e}")
                super().__init__(disk_size_mb)
                logger.info("Initialized new filesystem")
        else:
            super().__init__(disk_size_mb)
            logger.info("Initialized new filesystem")
            
    def read_file(self, path: str) -> str:
        """Read content of a file from the filesystem using caching"""
        try:
            abs_path = self._resolve_path(path)
            logger.debug(f"Reading file: {abs_path}")

            node = self._get_node(abs_path)
            if not node:
                raise FileNotFound(f"File not found: {path}")
            if node.type != 'file':
                raise IsADirectory(f"{path} is a directory, not a file")
            
            # Use the node's get_content method to leverage caching
            content = node.get_content()
            logger.debug(f"Successfully read file: {abs_path}")
            return content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise FileSystemError(f"Failed to read file: {str(e)}")
            
    def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the filesystem with caching"""
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            file_name = os.path.basename(abs_path)
            
            logger.debug(f"Writing file: {abs_path}")
            
            # Get parent directory
            parent = self._get_node(parent_path)
            if not parent:
                raise FileNotFound(f"Parent directory not found: {parent_path}")
            if parent.type != 'directory':
                raise NotADirectory(f"Parent path is not a directory: {parent_path}")
            
            # Create or update file
            if file_name in parent.content:
                node = parent.content[file_name]
                if node.type != 'file':
                    raise IsADirectory(f"{path} is a directory, not a file")
                
                # Update existing file using update_content method
                node.update_content(content)
            else:
                # Create new file
                new_file = FileNode(file_name, 'file', parent)
                parent.content[file_name] = new_file
                # Use update_content to properly set size and caching
                new_file.update_content(content)
                
            # Update parent metadata
            parent.metadata['modified'] = datetime.now()
            
            # Automatic persistence
            self._save_filesystem()
            
            logger.debug(f"Successfully wrote file: {abs_path}")
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            raise FileSystemError(f"Failed to write file: {str(e)}")
    

    
    def _save_filesystem(self):
        """Save filesystem state to encrypted disk file"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            # Convert the filesystem structure to serializable format
            fs_data = {
                'disk_size': self.disk_size,
                'current_path': self.current_path,
                'root': self._node_to_dict(self.root),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Serialize data
            serialized_data = pickle.dumps(fs_data)
            
            # Generate encryption key from password using KDF
            password = b"kaede_os_secure_disk"  # In production, this would be a user-provided password
            salt = b"kos_filesystem_salt"       # Fixed salt for reproducibility
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            # Encrypt data
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(serialized_data)
            
            # Save encrypted data
            with open(self.disk_file, 'wb') as f:
                f.write(encrypted_data)
            
            logger.info(f"Filesystem state encrypted and saved to {self.disk_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save filesystem state: {e}")
            return False
    
    def _load_filesystem(self):
        """Load filesystem state from encrypted disk file"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import base64
            
            if not os.path.exists(self.disk_file):
                logger.warning(f"Disk file {self.disk_file} not found, initializing new filesystem")
                return False
            
            # Read encrypted data
            with open(self.disk_file, 'rb') as f:
                encrypted_data = f.read()
            
            # Generate decryption key from password using KDF
            password = b"kaede_os_secure_disk"  # Same password used for encryption
            salt = b"kos_filesystem_salt"       # Same salt used for encryption
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            # Decrypt data
            fernet = Fernet(key)
            try:
                decrypted_data = fernet.decrypt(encrypted_data)
                fs_data = pickle.loads(decrypted_data)
                
                # Log load timestamp
                load_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                saved_time = fs_data.get('timestamp', 'unknown')
                logger.info(f"Loading filesystem saved at {saved_time} (current time: {load_time})")
                
            except Exception as e:
                logger.error(f"Failed to decrypt filesystem data: {e}")
                return False
            
            # Initialize base properties
            self.disk_size = fs_data.get('disk_size', 100 * 1024 * 1024)
            self.current_path = fs_data.get('current_path', '/')
            self.user_system = None
            
            # Recreate filesystem nodes
            root_dict = fs_data.get('root')
            if root_dict:
                self.root = self._dict_to_node(root_dict)
                return True
            else:
                logger.warning("Root node not found in filesystem data")
                self.root = FileNode('/', 'directory')
                self._init_filesystem()
                return False
                
        except Exception as e:
            logger.error(f"Failed to load filesystem state: {e}")
            # Initialize a new filesystem in case of failure
            super().__init__(100)  # Default 100MB disk size
            logger.warning("Initialized new filesystem due to load failure")
            return False
    
    def _node_to_dict(self, node):
        """Convert FileNode to serializable dictionary"""
        if node is None:
            return None
        
        result = {
            'name': node.name,
            'type': node.type,
            'metadata': {
                'created': node.metadata['created'].strftime('%Y-%m-%d %H:%M:%S'),
                'modified': node.metadata['modified'].strftime('%Y-%m-%d %H:%M:%S'),
                'permissions': node.metadata['permissions'],
                'owner': node.metadata['owner'],
                'group': node.metadata['group']
            },
            'size': node.size
        }
        
        # Handle content based on node type
        if node.type == 'directory':
            result['content'] = {}
            for name, child in node.content.items():
                result['content'][name] = self._node_to_dict(child)
        else:
            # Use get_content() for files to ensure we use cached content if available
            result['content'] = node.get_content()
        
        return result
    
    def _dict_to_node(self, node_dict, parent=None):
        """Convert dictionary to FileNode"""
        if not node_dict:
            return None
        
        # Create node with basic properties
        node = FileNode(node_dict['name'], node_dict['type'], parent)
        
        # Parse metadata dates
        metadata = node_dict['metadata']
        node.metadata['created'] = datetime.strptime(metadata['created'], '%Y-%m-%d %H:%M:%S')
        node.metadata['modified'] = datetime.strptime(metadata['modified'], '%Y-%m-%d %H:%M:%S')
        node.metadata['permissions'] = metadata['permissions']
        node.metadata['owner'] = metadata['owner']
        node.metadata['group'] = metadata['group']
        
        node.size = node_dict.get('size', 0)
        
        # Handle content based on node type
        if node.type == 'directory':
            node.content = {}
            for name, child_dict in node_dict['content'].items():
                child_node = self._dict_to_node(child_dict, node)
                node.content[name] = child_node
        else:
            # Use update_content for files to properly set size and cache
            node.update_content(node_dict['content'])
        
        return node

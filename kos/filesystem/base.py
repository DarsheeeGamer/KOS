"""
Base filesystem implementation with core functionality
"""
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Any, Union, List
from ..exceptions import (
    FileSystemError, InvalidDiskFormat, FileNotFound,
    NotADirectory, IsADirectory
)

logger = logging.getLogger('KOS')

class FileNode:
    """Represents a file or directory in the filesystem"""
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

    def exists(self, path: str) -> bool:
        """Check if a file or directory exists at the specified path"""
        return self._get_node(path) is not None

    def _resolve_path(self, path: str) -> str:
        """Resolve relative path to absolute path"""
        try:
            if not path:
                return self.current_path
            if path == '.':
                return self.current_path
            if path == '..':
                return os.path.dirname(self.current_path.replace('\\', '/')) or '/'

            # Handle relative paths
            if not path.startswith('/'):
                # Use posix-style path joining to maintain forward slashes
                path = self.current_path.rstrip('/') + '/' + path

            # Normalize the path while preserving forward slashes
            normalized = os.path.normpath(path).replace('\\', '/')

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

    def mkdir(self, path: str) -> None:
        """Create a directory"""
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            dir_name = os.path.basename(abs_path)

            logger.debug(f"Creating directory: {abs_path}")

            parent = self._get_node(parent_path)
            if not parent:
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

    def change_directory(self, path: str) -> str:
        """Change current directory with validation"""
        try:
            abs_path = self._resolve_path(path)
            
            # Check if the directory exists
            node = self._get_node(abs_path)
            if not node:
                raise FileNotFound(f"Directory not found: {path}")
            
            if node.type != 'directory':
                raise NotADirectory(f"Not a directory: {path}")
            
            # Change current path
            self.current_path = abs_path
            logger.debug(f"Changed directory to: {abs_path}")
            return abs_path
            
        except Exception as e:
            logger.error(f"Error changing directory to {path}: {e}")
            raise

class FileSystem(BaseFileSystem):
    """Enhanced filesystem implementation"""
    def __init__(self, disk_size_mb: int = 100):
        super().__init__(disk_size_mb)
        self.disk_file = 'kaede.kdsk'
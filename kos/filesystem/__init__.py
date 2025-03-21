"""
Filesystem module initialization
"""
from ..exceptions import (
    FileSystemError, InvalidDiskFormat, FileNotFound,
    NotADirectory, IsADirectory
)
from .base import FileNode, BaseFileSystem
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FileSystem(BaseFileSystem):
    """Enhanced filesystem implementation"""
    def __init__(self, disk_size_mb: int = 100):
        super().__init__(disk_size_mb)
        self.disk_file = 'kaede.kdsk'
        # Note: We no longer automatically load the filesystem here
        # This is now done explicitly in main.py to ensure it always happens during boot
        
    def load_filesystem(self):
        """Load filesystem state from disk"""
        try:
            # Check if disk file exists
            if not os.path.exists(self.disk_file):
                logger.info(f"No filesystem state file found at {self.disk_file}")
                return False
                
            # Use base implementation if available
            if hasattr(super(), '_load_filesystem'):
                return super()._load_filesystem()
                
            # Otherwise use our own implementation
            import pickle
            from datetime import datetime
            
            # Load serialized data
            with open(self.disk_file, 'rb') as f:
                serialized_data = f.read()
                
            # Deserialize data
            fs_data = pickle.loads(serialized_data)
            
            # Extract filesystem structure
            if 'disk_size' in fs_data:
                self.disk_size = fs_data['disk_size']
            
            if 'current_path' in fs_data:
                self.current_path = fs_data['current_path']
                
            if 'root' in fs_data:
                self._load_node_from_dict(fs_data['root'])
                
            logger.info(f"Filesystem state loaded from {self.disk_file} (saved at {fs_data.get('timestamp', 'unknown')})")
            return True
        except Exception as e:
            logger.error(f"Failed to load filesystem state: {e}")
            return False
            
    def _load_node_from_dict(self, node_dict):
        """Load a node from its dictionary representation"""
        if not node_dict:
            return
            
        # Start with loading the root node
        self.root.name = node_dict.get('name', '/')
        
        # Process root's children
        if node_dict.get('type') == 'directory' and 'content' in node_dict:
            self._load_directory_content(self.root, node_dict['content'])
            
    def _load_directory_content(self, parent_node, content_dict):
        """Load directory content recursively"""
        if not content_dict:
            return
            
        from datetime import datetime
        
        # Clear existing content first to avoid duplicates
        parent_node.content = {}
        
        # Add each child node
        for name, child_dict in content_dict.items():
            # Create the appropriate node type
            node_type = child_dict.get('type', 'file')
            child_node = FileNode(name, node_type, parent_node)
            
            # Set metadata
            if 'metadata' in child_dict:
                metadata = child_dict['metadata']
                
                # Convert string dates to datetime objects
                created = metadata.get('created', None)
                modified = metadata.get('modified', None)
                
                if isinstance(created, str):
                    try:
                        child_node.metadata['created'] = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
                    except:
                        child_node.metadata['created'] = datetime.now()
                
                if isinstance(modified, str):
                    try:
                        child_node.metadata['modified'] = datetime.strptime(modified, '%Y-%m-%d %H:%M:%S')
                    except:
                        child_node.metadata['modified'] = datetime.now()
                
                # Set permissions, owner, and group
                if 'permissions' in metadata:
                    child_node.metadata['permissions'] = metadata['permissions']
                if 'owner' in metadata:
                    child_node.metadata['owner'] = metadata['owner']
                if 'group' in metadata:
                    child_node.metadata['group'] = metadata['group']
            
            # Set size
            if 'size' in child_dict:
                child_node.size = child_dict['size']
            
            # Add node to parent
            parent_node.content[name] = child_node
            
            # If directory, process its children recursively
            if node_type == 'directory' and 'content' in child_dict:
                self._load_directory_content(child_node, child_dict['content'])
            elif node_type == 'file' and 'content' in child_dict:
                # Set file content
                child_node.update_content(child_dict['content'])
        
    def node_to_dict(self, node):
        """Convert FileNode to serializable dictionary"""
        if node is None:
            return None
        
        # Create a basic serializable representation of the node
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
                result['content'][name] = self.node_to_dict(child)
        else:
            # Use get_content() for files to ensure we use cached content if available
            result['content'] = node.get_content()
        
        return result
        
    def save_filesystem(self):
        """Save filesystem state to disk"""
        try:
            # Use base implementation if available
            if hasattr(super(), '_save_filesystem'):
                return super()._save_filesystem()
                
            # Otherwise use our own implementation
            import pickle
            from datetime import datetime
            
            # Convert the filesystem structure to serializable format
            fs_data = {
                'disk_size': self.disk_size,
                'current_path': self.current_path,
                'root': self.node_to_dict(self.root),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Serialize data
            serialized_data = pickle.dumps(fs_data)
            
            # Save data (unencrypted version as fallback)
            with open(self.disk_file, 'wb') as f:
                f.write(serialized_data)
                
            logger.info(f"Filesystem state saved to {self.disk_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save filesystem state: {e}")
            return False

    def exists(self, path: str) -> bool:
        """Check if path exists"""
        node = self._get_node(self._resolve_path(path))
        return node is not None

    def list_directory(self, path: str = ".", long_format: bool = False):
        """List contents of a directory"""
        try:
            abs_path = self._resolve_path(path)
            logger.debug(f"FileSystem: listing directory {abs_path}")

            node = self._get_node(abs_path)
            if not node:
                raise FileNotFound(f"Directory not found: {path}")
            if node.type != 'directory':
                raise NotADirectory(f"{path} is not a directory")

            items = node.content.items()
            if not items:
                logger.debug(f"Directory {abs_path} is empty")
                return []

            result = []
            for name, child in sorted(items):
                if long_format:
                    result.append({
                        'name': name,
                        'type': child.type,
                        'size': child.size,
                        'perms': oct(child.metadata['permissions'])[2:],
                        'owner': child.metadata['owner'],
                        'group': child.metadata['group'],
                        'modified': child.metadata['modified'].strftime('%Y-%m-%d %H:%M')
                    })
                else:
                    result.append(name)

            logger.debug(f"Found {len(result)} items in {abs_path}")
            return result

        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise FileSystemError(f"Failed to list directory: {str(e)}")

    def cd(self, path: str) -> None:
        """Change current directory"""
        try:
            abs_path = self._resolve_path(path)
            node = self._get_node(abs_path)
            if not node:
                raise FileNotFound(f"Directory not found: {path}")
            if node.type != 'directory':
                raise NotADirectory(f"{path} is not a directory")
            self.current_path = abs_path
        except Exception as e:
            logger.error(f"Error changing directory to {path}: {e}")
            raise FileSystemError(f"Failed to change directory: {str(e)}")

    def pwd(self) -> str:
        """Print working directory"""
        return self.current_path or "/"

    def mkdir(self, path: str, create_parents: bool = False) -> None:
        """Create a directory
        
        Args:
            path: The path to create
            create_parents: If True, create parent directories as needed
        """
        logger.debug(f"FileSystem: creating directory {path} with create_parents={create_parents}")
        super().mkdir(path, create_parents)

    def touch(self, path: str) -> None:
        """Create an empty file or update modification time"""
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            file_name = os.path.basename(abs_path)

            logger.debug(f"FileSystem: touching file {abs_path}")

            parent = self._get_node(parent_path)
            if not parent or parent.type != 'directory':
                raise NotADirectory(f"Parent path is not a directory: {parent_path}")

            # If file exists, just update modification time
            if file_name in parent.content:
                node = parent.content[file_name]
                if node.type == 'file':
                    # Just update modification time
                    node.metadata['modified'] = datetime.now()
                    logger.debug(f"Updated timestamp for existing file: {abs_path}")
                else:
                    raise IsADirectory(f"{path} is a directory, not a file")
            else:
                # Create new empty file
                new_file = FileNode(file_name, 'file', parent)
                parent.content[file_name] = new_file
                # Use update_content to properly set size and caching
                new_file.update_content('')
                parent.metadata['modified'] = datetime.now()
                
                logger.debug(f"Successfully created file: {abs_path}")
        except Exception as e:
            logger.error(f"Error touching file {path}: {e}")
            raise FileSystemError(f"Failed to touch file: {str(e)}")

    def cat(self, path: str) -> str:
        """Display file contents using memory cache"""
        try:
            node = self._get_node(self._resolve_path(path))
            if not node:
                raise FileNotFound(f"File not found: {path}")
            if node.type != 'file':
                raise IsADirectory(f"{path} is a directory")
            # Use get_content to leverage caching
            return node.get_content()
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise FileSystemError(f"Failed to read file: {str(e)}")
            
    def read_file(self, path: str) -> str:
        """Read content of a file from the filesystem using caching"""
        return self.cat(path)
        
    def write_file(self, path: str, content: str) -> None:
        """Write content to a file in the filesystem with cache management"""
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            file_name = os.path.basename(abs_path)
            
            logger.debug(f"FileSystem: writing file {abs_path}")
            
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
            
            logger.debug(f"Successfully wrote file: {abs_path}")
        except Exception as e:
            logger.error(f"Error writing file {path}: {e}")
            raise FileSystemError(f"Failed to write file: {str(e)}")

__all__ = [
    'FileSystem',
    'FileNode',
    'FileSystemError',
    'InvalidDiskFormat',
    'FileNotFound',
    'NotADirectory',
    'IsADirectory'
]
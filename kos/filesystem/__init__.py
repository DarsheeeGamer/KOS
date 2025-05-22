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

    def mkdir(self, path: str, *args) -> None:
        """Create a directory"""
        logger.debug(f"FileSystem: creating directory {path}")
        # Ignore any additional arguments (for backward compatibility)
        super().mkdir(path)

    def touch(self, path: str) -> None:
        """Create an empty file"""
        try:
            abs_path = self._resolve_path(path)
            parent_path = os.path.dirname(abs_path)
            file_name = os.path.basename(abs_path)

            logger.debug(f"FileSystem: creating file {abs_path}")

            parent = self._get_node(parent_path)
            if not parent or parent.type != 'directory':
                raise NotADirectory(f"Parent path is not a directory: {parent_path}")

            if file_name in parent.content:
                raise FileSystemError(f"File already exists: {path}")

            new_file = FileNode(file_name, 'file', parent)
            new_file.content = ''
            parent.content[file_name] = new_file
            parent.metadata['modified'] = datetime.now()

            logger.debug(f"Successfully created file: {abs_path}")
        except Exception as e:
            logger.error(f"Error creating file {path}: {e}")
            raise FileSystemError(f"Failed to create file: {str(e)}")

    def cat(self, path: str) -> str:
        """Display file contents"""
        try:
            node = self._get_node(self._resolve_path(path))
            if not node:
                raise FileNotFound(f"File not found: {path}")
            if node.type != 'file':
                raise IsADirectory(f"{path} is a directory")
            return node.content
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}")
            raise FileSystemError(f"Failed to read file: {str(e)}")

__all__ = [
    'FileSystem',
    'FileNode',
    'FileSystemError',
    'InvalidDiskFormat',
    'FileNotFound',
    'NotADirectory',
    'IsADirectory'
]
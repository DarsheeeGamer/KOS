"""
Base filesystem implementation
"""
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Any, Union, List

logger = logging.getLogger('KOS')

class FileNode:
    def __init__(self, name: str, type: str, content: Dict, metadata: Dict, parent=None):
        self.name = name
        self.type = type
        self.content = content
        self.metadata = metadata
        self.parent = parent
        self.size = 0

    def invalidate_cache(self):
        """Invalidate cached data"""
        self.size = 0
        if self.parent:
            self.parent.invalidate_cache()

class BaseFileSystem:
    """Base filesystem with core functionality"""
    def __init__(self, disk_size_mb: int = 100):
        self._current_path = "/"
        self.node_cache: Dict[str, FileNode] = {}
        self.root = self._create_root_node()
        self.node_cache['/'] = self.root
        self.disk_manager = None
        self._user_system = None
        self._initialize_disk()
        logger.info(f"Initialized filesystem with {disk_size_mb}MB capacity")

    def _create_root_node(self) -> FileNode:
        return FileNode(
            name='/',
            type='dir',
            content={},
            metadata={
                'created': datetime.now(),
                'modified': datetime.now(),
                'permissions': 0o755,
                'owner': 'kaede',
                'group': 'kaede'
            }
        )

    def _initialize_disk(self):
        try:
            essential_dirs = ['home', 'bin', 'etc', 'var', 'tmp', 'usr', 'opt', 'mnt', 'proc', 'sys', 'dev']
            for dir_name in essential_dirs:
                self._create_directory(f'/{dir_name}')
                logger.debug(f"Created directory: /{dir_name}")
            logger.info("Basic directory structure created")
        except Exception as e:
            logger.error(f"Failed to initialize filesystem: {e}")
            raise FileSystemError(f"Failed to initialize filesystem: {str(e)}")


class FileSystemError(Exception):
    """File system related errors"""
    pass

class FileSystem(BaseFileSystem):
    """Enhanced filesystem with performance optimizations"""
    def __init__(self, disk_size_mb: int = 100):
        super().__init__(disk_size_mb)
        self._user_system: Optional["UserSystem"] = None

    @property
    def current_path(self) -> str:
        """Get current working directory path"""
        return self._current_path

    @current_path.setter
    def current_path(self, path: str):
        """Set current working directory path"""
        self._current_path = self._resolve_path(path)

    @property
    def user_system(self) -> Optional["UserSystem"]:
        return self._user_system

    @user_system.setter
    def user_system(self, value: Optional["UserSystem"]):
        self._user_system = value
        logger.info("User system reference updated")

    def _resolve_path(self, path: str) -> str:
        if not path:
            return self._current_path

        # Handle special paths first
        if path == '.':
            return self._current_path
        if path == '..':
            parent = os.path.dirname(self._current_path)
            return parent if parent else '/'
        if path == '~':
            if self.user_system and self.user_system.current_user == "kaede":
                return "/"
            return f"/home/{self.user_system.current_user if self.user_system else 'kaede'}"

        # Handle absolute paths
        if path.startswith('/'):
            normalized = os.path.normpath(path)
            return normalized if normalized != '.' else '/'

        # Handle relative paths
        full_path = os.path.join(self._current_path, path)
        normalized = os.path.normpath(full_path)
        return normalized if normalized != '.' else '/'

    def _get_node(self, path: str) -> FileNode:
        abs_path = self._resolve_path(path)

        if abs_path == '/':
            return self.root

        if abs_path in self.node_cache:
            return self.node_cache[abs_path]

        parts = [p for p in abs_path.split('/') if p]
        node = self.root
        current_path = ''

        for part in parts:
            current_path = os.path.join(current_path, part) if current_path else f"/{part}"
            if part not in node.content:
                raise FileSystemError(f"No such file or directory: {abs_path}")

            node = node.content[part]
            self.node_cache[current_path] = node

        return node

    def _create_directory(self, path: str, mode: int = 0o755) -> bool:
        """Create directory with proper node creation and caching"""
        try:
            abs_path = self._resolve_path(path)
            parent_path, name = os.path.split(abs_path)

            if not name:
                raise FileSystemError("Invalid directory name")

            parent = self._get_node(parent_path)
            if parent.type != 'dir':
                raise FileSystemError(f"Cannot create directory in non-directory: {parent_path}")

            if name in parent.content:
                raise FileSystemError(f"Cannot create directory '{path}': File exists")

            current_user = 'kaede'
            if hasattr(self, 'user_system') and self.user_system is not None:
                current_user = self.user_system.current_user

            new_dir = FileNode(
                name=name,
                type='dir',
                content={},
                metadata={
                    'created': datetime.now(),
                    'modified': datetime.now(),
                    'permissions': mode,
                    'owner': current_user,
                    'group': current_user
                },
                parent=parent
            )

            parent.content[name] = new_dir
            self.node_cache[abs_path] = new_dir
            parent.invalidate_cache()
            logger.debug(f"Created directory: {abs_path}")
            return True

        except Exception as e:
            logger.error(f"Error creating directory {path}: {e}")
            raise FileSystemError(f"Failed to create directory: {str(e)}")

    def list_directory(self, path: str = ".", long_format: bool = False) -> List[Union[str, Dict[str, Any]]]:
        """Enhanced directory listing with proper node traversal"""
        try:
            abs_path = self._resolve_path(path)
            node = self._get_node(abs_path)
            logger.debug(f"Listing directory: {abs_path}")

            if node.type != 'dir':
                raise FileSystemError(f"{path} is not a directory")

            entries = []
            for name, item in sorted(node.content.items()):
                if long_format:
                    entries.append({
                        'name': name,
                        'type': item.type,
                        'size': item.size,
                        'permissions': item.metadata['permissions'],
                        'owner': item.metadata['owner'],
                        'group': item.metadata['group'],
                        'modified': item.metadata['modified']
                    })
                else:
                    entries.append(name)

            return entries

        except Exception as e:
            logger.error(f"Error listing directory {path}: {e}")
            raise FileSystemError(f"Failed to list directory: {str(e)}")

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..user_system import UserSystem
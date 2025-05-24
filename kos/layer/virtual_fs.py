"""
Virtual FileSystem Component for KLayer

This module provides an advanced virtual filesystem implementation for KOS,
allowing for in-memory filesystems, overlay filesystems, and advanced
filesystem operations.
"""

import os
import sys
import io
import time
import logging
import threading
import json
import shutil
import stat
import hashlib
import tempfile
from typing import Dict, List, Any, Optional, Union, BinaryIO, TextIO, Callable, Tuple
from datetime import datetime

logger = logging.getLogger('KOS.layer.virtual_fs')

class VNode:
    """Virtual filesystem node representing a file or directory"""
    
    def __init__(self, name: str, is_dir: bool = False, parent=None):
        """Initialize a virtual filesystem node"""
        self.name = name
        self.is_dir = is_dir
        self.parent = parent
        self.children = {} if is_dir else None
        self.content = b"" if not is_dir else None
        self.metadata = {
            "created": time.time(),
            "modified": time.time(),
            "accessed": time.time(),
            "size": 0,
            "permissions": 0o644 if not is_dir else 0o755,
            "owner": "kos",
            "group": "kos"
        }
    
    def get_path(self) -> str:
        """Get the full path to this node"""
        if not self.parent:
            return self.name
        
        parent_path = self.parent.get_path()
        if parent_path == "/":
            return f"/{self.name}"
        else:
            return f"{parent_path}/{self.name}"
    
    def get_child(self, name: str) -> Optional['VNode']:
        """Get a child node by name"""
        if not self.is_dir or not self.children:
            return None
        
        return self.children.get(name)
    
    def add_child(self, node: 'VNode') -> bool:
        """Add a child node"""
        if not self.is_dir:
            return False
        
        if node.name in self.children:
            return False
        
        self.children[node.name] = node
        node.parent = self
        self.metadata["modified"] = time.time()
        return True
    
    def remove_child(self, name: str) -> bool:
        """Remove a child node by name"""
        if not self.is_dir or not self.children:
            return False
        
        if name not in self.children:
            return False
        
        del self.children[name]
        self.metadata["modified"] = time.time()
        return True
    
    def update_content(self, content: bytes) -> None:
        """Update file content"""
        if self.is_dir:
            return
        
        self.content = content
        self.metadata["modified"] = time.time()
        self.metadata["size"] = len(content)
    
    def append_content(self, content: bytes) -> None:
        """Append to file content"""
        if self.is_dir:
            return
        
        self.content += content
        self.metadata["modified"] = time.time()
        self.metadata["size"] = len(self.content)
    
    def read_content(self) -> bytes:
        """Read file content"""
        if self.is_dir:
            return b""
        
        self.metadata["accessed"] = time.time()
        return self.content
    
    def to_dict(self, include_content: bool = False) -> Dict[str, Any]:
        """Convert node to dictionary representation"""
        result = {
            "name": self.name,
            "path": self.get_path(),
            "is_dir": self.is_dir,
            "metadata": self.metadata.copy()
        }
        
        if not self.is_dir and include_content:
            result["content"] = self.content
        
        if self.is_dir and self.children:
            result["children"] = [child.to_dict(False) for child in self.children.values()]
        
        return result

class VirtualFileSystem:
    """Virtual filesystem implementation for KOS"""
    
    def __init__(self):
        """Initialize the virtual filesystem"""
        self.lock = threading.RLock()
        self.root = VNode("/", is_dir=True)
        self.mounts = {}  # Path -> Mount object
        self.watchers = {}  # Path -> List of callback functions
    
    def _resolve_path(self, path: str) -> List[str]:
        """Resolve a path to its components"""
        if not path or path == "/":
            return []
        
        # Normalize path
        norm_path = os.path.normpath(path).replace("\\", "/")
        
        # Remove leading slash
        if norm_path.startswith("/"):
            norm_path = norm_path[1:]
        
        # Split path components
        return norm_path.split("/")
    
    def _get_node(self, path: str) -> Optional[VNode]:
        """Get a node by path"""
        with self.lock:
            # Handle root path
            if path == "/" or not path:
                return self.root
            
            components = self._resolve_path(path)
            current = self.root
            
            for component in components:
                if not component:
                    continue
                
                if not current.is_dir:
                    return None
                
                current = current.get_child(component)
                if not current:
                    return None
            
            return current
    
    def _create_node(self, path: str, is_dir: bool = False) -> Tuple[bool, Optional[VNode]]:
        """Create a node at the specified path"""
        with self.lock:
            # Handle root path
            if path == "/" or not path:
                return (True, self.root)
            
            components = self._resolve_path(path)
            current = self.root
            
            # Navigate to parent directory
            for i in range(len(components) - 1):
                component = components[i]
                if not component:
                    continue
                
                if not current.is_dir:
                    return (False, None)
                
                child = current.get_child(component)
                if not child:
                    # Create intermediate directory
                    child = VNode(component, is_dir=True)
                    current.add_child(child)
                elif not child.is_dir:
                    return (False, None)
                
                current = child
            
            # Create the final node
            final_name = components[-1]
            if final_name in current.children:
                existing = current.get_child(final_name)
                if existing.is_dir != is_dir:
                    return (False, None)
                return (True, existing)
            
            # Create new node
            new_node = VNode(final_name, is_dir=is_dir)
            current.add_child(new_node)
            
            # Notify watchers
            self._notify_watchers(path, "create")
            
            return (True, new_node)
    
    def _notify_watchers(self, path: str, event_type: str, metadata: Dict[str, Any] = None) -> None:
        """Notify all watchers for a path"""
        # Find all watchers that apply to this path
        for watch_path, callbacks in self.watchers.items():
            if path.startswith(watch_path):
                for callback in callbacks:
                    try:
                        callback(path, event_type, metadata or {})
                    except Exception as e:
                        logger.error(f"Error notifying watcher for {path}: {e}")
    
    def exists(self, path: str) -> bool:
        """Check if a path exists in the filesystem"""
        return self._get_node(path) is not None
    
    def is_dir(self, path: str) -> bool:
        """Check if a path is a directory"""
        node = self._get_node(path)
        return node is not None and node.is_dir
    
    def is_file(self, path: str) -> bool:
        """Check if a path is a file"""
        node = self._get_node(path)
        return node is not None and not node.is_dir
    
    def list_dir(self, path: str) -> Dict[str, Any]:
        """List directory contents"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
        
        if not node.is_dir:
            return {
                "success": False,
                "error": f"Not a directory: {path}"
            }
        
        contents = []
        for child_name, child_node in sorted(node.children.items()):
            contents.append({
                "name": child_name,
                "path": child_node.get_path(),
                "is_dir": child_node.is_dir,
                "size": child_node.metadata["size"],
                "created": child_node.metadata["created"],
                "modified": child_node.metadata["modified"],
                "permissions": child_node.metadata["permissions"]
            })
        
        return {
            "success": True,
            "path": path,
            "contents": contents,
            "count": len(contents)
        }
    
    def create_dir(self, path: str) -> Dict[str, Any]:
        """Create a directory"""
        if self.exists(path):
            node = self._get_node(path)
            if node and node.is_dir:
                return {
                    "success": True,
                    "path": path,
                    "already_exists": True
                }
            else:
                return {
                    "success": False,
                    "error": f"Path exists but is not a directory: {path}"
                }
        
        success, node = self._create_node(path, is_dir=True)
        
        if not success:
            return {
                "success": False,
                "error": f"Failed to create directory: {path}"
            }
        
        return {
            "success": True,
            "path": path,
            "already_exists": False
        }
    
    def remove_dir(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Remove a directory"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"Directory not found: {path}"
            }
        
        if not node.is_dir:
            return {
                "success": False,
                "error": f"Not a directory: {path}"
            }
        
        if node.children and not recursive:
            return {
                "success": False,
                "error": f"Directory not empty. Use recursive=True to remove: {path}"
            }
        
        # Cannot remove root
        if not node.parent:
            return {
                "success": False,
                "error": "Cannot remove root directory"
            }
        
        parent = node.parent
        parent.remove_child(node.name)
        
        # Notify watchers
        self._notify_watchers(path, "delete")
        
        return {
            "success": True,
            "path": path,
            "recursive": recursive
        }
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read a file's content"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        if node.is_dir:
            return {
                "success": False,
                "error": f"Cannot read a directory: {path}"
            }
        
        content = node.read_content()
        
        return {
            "success": True,
            "path": path,
            "content": content,
            "size": len(content),
            "metadata": node.metadata
        }
    
    def write_file(self, path: str, content: bytes, append: bool = False) -> Dict[str, Any]:
        """Write content to a file"""
        node = self._get_node(path)
        
        if node and node.is_dir:
            return {
                "success": False,
                "error": f"Cannot write to a directory: {path}"
            }
        
        # Create new file if it doesn't exist
        if not node:
            success, node = self._create_node(path, is_dir=False)
            if not success:
                return {
                    "success": False,
                    "error": f"Failed to create file: {path}"
                }
        
        # Update content
        if append:
            node.append_content(content)
        else:
            node.update_content(content)
        
        # Notify watchers
        self._notify_watchers(path, "modify", {"size": node.metadata["size"]})
        
        return {
            "success": True,
            "path": path,
            "size": node.metadata["size"],
            "append": append
        }
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        if node.is_dir:
            return {
                "success": False,
                "error": f"Cannot delete a directory as file: {path}"
            }
        
        # Cannot remove root
        if not node.parent:
            return {
                "success": False,
                "error": "Cannot remove root node"
            }
        
        parent = node.parent
        parent.remove_child(node.name)
        
        # Notify watchers
        self._notify_watchers(path, "delete")
        
        return {
            "success": True,
            "path": path
        }
    
    def copy(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Copy a file or directory"""
        source_node = self._get_node(source_path)
        
        if not source_node:
            return {
                "success": False,
                "error": f"Source not found: {source_path}"
            }
        
        # Copy file
        if not source_node.is_dir:
            # Read source content
            content = source_node.read_content()
            
            # Write to target
            result = self.write_file(target_path, content)
            
            if not result["success"]:
                return result
            
            # Copy metadata
            target_node = self._get_node(target_path)
            if target_node:
                for key in ["permissions", "owner", "group"]:
                    target_node.metadata[key] = source_node.metadata[key]
            
            return {
                "success": True,
                "source_path": source_path,
                "target_path": target_path,
                "is_dir": False
            }
        
        # Copy directory
        self.create_dir(target_path)
        
        # Recursively copy children
        success = True
        errors = []
        
        for child_name, child_node in source_node.children.items():
            child_source = f"{source_path}/{child_name}" if source_path != "/" else f"/{child_name}"
            child_target = f"{target_path}/{child_name}" if target_path != "/" else f"/{child_name}"
            
            result = self.copy(child_source, child_target)
            if not result["success"]:
                success = False
                errors.append(result["error"])
        
        return {
            "success": success,
            "source_path": source_path,
            "target_path": target_path,
            "is_dir": True,
            "errors": errors if errors else None
        }
    
    def move(self, source_path: str, target_path: str) -> Dict[str, Any]:
        """Move a file or directory"""
        # Copy first
        copy_result = self.copy(source_path, target_path)
        if not copy_result["success"]:
            return copy_result
        
        # Then delete source
        if copy_result["is_dir"]:
            delete_result = self.remove_dir(source_path, recursive=True)
        else:
            delete_result = self.delete_file(source_path)
        
        if not delete_result["success"]:
            return {
                "success": False,
                "error": f"Copied to target but failed to delete source: {delete_result['error']}",
                "source_path": source_path,
                "target_path": target_path
            }
        
        return {
            "success": True,
            "source_path": source_path,
            "target_path": target_path,
            "is_dir": copy_result["is_dir"]
        }
    
    def get_metadata(self, path: str) -> Dict[str, Any]:
        """Get metadata for a file or directory"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
        
        return {
            "success": True,
            "path": path,
            "is_dir": node.is_dir,
            "metadata": node.metadata.copy()
        }
    
    def update_metadata(self, path: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Update metadata for a file or directory"""
        node = self._get_node(path)
        
        if not node:
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }
        
        # Update allowed metadata fields
        allowed_fields = ["permissions", "owner", "group"]
        for key in allowed_fields:
            if key in metadata:
                node.metadata[key] = metadata[key]
        
        node.metadata["modified"] = time.time()
        
        # Notify watchers
        self._notify_watchers(path, "metadata", node.metadata)
        
        return {
            "success": True,
            "path": path,
            "metadata": node.metadata.copy()
        }
    
    def watch(self, path: str, callback: Callable[[str, str, Dict[str, Any]], None]) -> str:
        """
        Add a watcher for changes to a path
        
        Args:
            path: Path to watch
            callback: Function to call when changes occur
                      callback(path, event_type, metadata)
        
        Returns:
            Watcher ID
        """
        with self.lock:
            # Create watcher ID
            watcher_id = hashlib.md5(f"{path}:{time.time()}:{id(callback)}".encode()).hexdigest()
            
            # Add to watchers
            if path not in self.watchers:
                self.watchers[path] = []
            
            self.watchers[path].append(callback)
            
            return watcher_id
    
    def unwatch(self, path: str, watcher_id: str) -> bool:
        """Remove a watcher"""
        with self.lock:
            if path not in self.watchers:
                return False
            
            # We don't actually store the watcher_id, just remove all watchers for this path
            # In a real implementation, we would use the watcher_id to remove only the specific watcher
            self.watchers.pop(path, None)
            
            return True
    
    def export_to_real_fs(self, vfs_path: str, real_path: str) -> Dict[str, Any]:
        """Export a virtual filesystem path to the real filesystem"""
        node = self._get_node(vfs_path)
        
        if not node:
            return {
                "success": False,
                "error": f"Virtual path not found: {vfs_path}"
            }
        
        try:
            # Create target directory if it doesn't exist
            real_parent = os.path.dirname(real_path)
            os.makedirs(real_parent, exist_ok=True)
            
            if node.is_dir:
                # Create directory
                os.makedirs(real_path, exist_ok=True)
                
                # Recursively export children
                success = True
                errors = []
                
                for child_name, child_node in node.children.items():
                    child_vfs_path = f"{vfs_path}/{child_name}" if vfs_path != "/" else f"/{child_name}"
                    child_real_path = os.path.join(real_path, child_name)
                    
                    result = self.export_to_real_fs(child_vfs_path, child_real_path)
                    if not result["success"]:
                        success = False
                        errors.append(result["error"])
                
                return {
                    "success": success,
                    "vfs_path": vfs_path,
                    "real_path": real_path,
                    "is_dir": True,
                    "errors": errors if errors else None
                }
            else:
                # Write file content
                with open(real_path, "wb") as f:
                    f.write(node.read_content())
                
                # Set permissions if possible
                try:
                    os.chmod(real_path, node.metadata["permissions"])
                except:
                    pass
                
                return {
                    "success": True,
                    "vfs_path": vfs_path,
                    "real_path": real_path,
                    "is_dir": False,
                    "size": node.metadata["size"]
                }
        except Exception as e:
            logger.error(f"Error exporting {vfs_path} to {real_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "vfs_path": vfs_path,
                "real_path": real_path
            }
    
    def import_from_real_fs(self, real_path: str, vfs_path: str) -> Dict[str, Any]:
        """Import from the real filesystem to the virtual filesystem"""
        if not os.path.exists(real_path):
            return {
                "success": False,
                "error": f"Real path not found: {real_path}"
            }
        
        try:
            if os.path.isdir(real_path):
                # Create directory
                self.create_dir(vfs_path)
                
                # Recursively import children
                success = True
                errors = []
                
                for child_name in os.listdir(real_path):
                    child_real_path = os.path.join(real_path, child_name)
                    child_vfs_path = f"{vfs_path}/{child_name}" if vfs_path != "/" else f"/{child_name}"
                    
                    result = self.import_from_real_fs(child_real_path, child_vfs_path)
                    if not result["success"]:
                        success = False
                        errors.append(result["error"])
                
                return {
                    "success": success,
                    "real_path": real_path,
                    "vfs_path": vfs_path,
                    "is_dir": True,
                    "errors": errors if errors else None
                }
            else:
                # Read file content
                with open(real_path, "rb") as f:
                    content = f.read()
                
                # Write to virtual fs
                result = self.write_file(vfs_path, content)
                if not result["success"]:
                    return result
                
                # Update metadata
                node = self._get_node(vfs_path)
                if node:
                    try:
                        stat_info = os.stat(real_path)
                        node.metadata["permissions"] = stat_info.st_mode & 0o777
                        node.metadata["created"] = stat_info.st_ctime
                        node.metadata["modified"] = stat_info.st_mtime
                        node.metadata["accessed"] = stat_info.st_atime
                    except:
                        pass
                
                return {
                    "success": True,
                    "real_path": real_path,
                    "vfs_path": vfs_path,
                    "is_dir": False,
                    "size": len(content)
                }
        except Exception as e:
            logger.error(f"Error importing {real_path} to {vfs_path}: {e}")
            return {
                "success": False,
                "error": str(e),
                "real_path": real_path,
                "vfs_path": vfs_path
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get filesystem statistics"""
        total_files = 0
        total_dirs = 0
        total_size = 0
        
        def count_nodes(node):
            nonlocal total_files, total_dirs, total_size
            
            if node.is_dir:
                total_dirs += 1
                for child in node.children.values():
                    count_nodes(child)
            else:
                total_files += 1
                total_size += node.metadata["size"]
        
        count_nodes(self.root)
        
        return {
            "success": True,
            "total_files": total_files,
            "total_directories": total_dirs,
            "total_size_bytes": total_size,
            "timestamp": time.time()
        }

# Create a singleton instance
virtual_fs = VirtualFileSystem()

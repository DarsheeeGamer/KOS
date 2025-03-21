"""
Enhanced disk management system with caching and performance optimizations
"""
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from functools import lru_cache
import logging
from ..exceptions import FileSystemError
from cachetools import TTLCache, cached

logger = logging.getLogger('KOS.disk')

class DiskManager:
    """Enhanced disk management system"""
    def __init__(self, filesystem):
        self.fs = filesystem
        self.usage_cache = TTLCache(maxsize=100, ttl=60)  # Cache disk usage for 60 seconds
        self.integrity_cache = TTLCache(maxsize=100, ttl=300)  # Cache integrity checks for 5 minutes
        logger.info("Disk manager initialized with caching")

    @cached(cache=TTLCache(maxsize=100, ttl=60))
    def get_usage(self) -> Dict[str, Any]:
        """Get disk usage statistics with caching"""
        try:
            total_size = self.fs.disk_size
            used_size = self._calculate_used_space(self.fs.root)
            free_size = total_size - used_size

            return {
                'total': total_size,
                'used': used_size,
                'free': free_size,
                'usage_percent': (used_size / total_size) * 100 if total_size > 0 else 0,
                'inodes_total': 1000000,  # Simulated inode count
                'inodes_used': len(self.fs.node_cache),
                'fs_type': 'kfs',  # KOS File System
                'mount_point': '/',
                'device': '/dev/kda1'
            }
        except Exception as e:
            logger.error(f"Failed to get disk usage: {e}")
            raise FileSystemError(f"Failed to get disk usage: {str(e)}")

    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def check_integrity(self) -> List[str]:
        """Check filesystem integrity with caching"""
        issues = []
        try:
            self._check_node_integrity(self.fs.root, '/', issues)
            
            # Additional checks
            self._check_directory_structure(issues)
            self._check_file_permissions(issues)
            self._check_symlinks(issues)
            
            return issues if issues else ["Filesystem integrity check passed"]
        except Exception as e:
            logger.error(f"Failed to check filesystem integrity: {e}")
            raise FileSystemError(f"Failed to check filesystem integrity: {str(e)}")

    def _calculate_used_space(self, node: Dict) -> int:
        """Calculate used space recursively with optimization"""
        if node['type'] == 'file':
            return len(node['content'])
        return sum(self._calculate_used_space(child) for child in node['content'].values())

    def _check_node_integrity(self, node: Dict, path: str, issues: List[str]):
        """Enhanced node integrity check"""
        try:
            required_fields = ['name', 'type', 'content', 'metadata']
            for field in required_fields:
                if field not in node:
                    issues.append(f"Missing required field '{field}' in {path}")

            if 'metadata' in node:
                metadata = node['metadata']
                required_metadata = ['created', 'modified', 'permissions', 'owner', 'group']
                for field in required_metadata:
                    if field not in metadata:
                        issues.append(f"Missing metadata field '{field}' in {path}")

            if node['type'] == 'dir':
                for name, child in node['content'].items():
                    child_path = os.path.join(path, name)
                    self._check_node_integrity(child, child_path, issues)

        except Exception as e:
            issues.append(f"Error checking node at {path}: {str(e)}")

    def _check_directory_structure(self, issues: List[str]):
        """Check essential directory structure"""
        essential_dirs = ['/bin', '/etc', '/home', '/usr', '/var', '/tmp']
        for dir_path in essential_dirs:
            try:
                node = self.fs._get_node(dir_path)
                if node['type'] != 'dir':
                    issues.append(f"Essential directory {dir_path} is not a directory")
            except FileSystemError:
                issues.append(f"Missing essential directory: {dir_path}")

    def _check_file_permissions(self, issues: List[str]):
        """Check file permissions"""
        secure_paths = ['/etc/passwd', '/etc/shadow']
        for path in secure_paths:
            try:
                node = self.fs._get_node(path)
                if node['metadata']['permissions'] & 0o077:
                    issues.append(f"Insecure permissions on {path}")
            except FileSystemError:
                pass  # Skip if file doesn't exist

    def _check_symlinks(self, issues: List[str]):
        """Check symbolic links"""
        def check_symlink(node: Dict, path: str):
            if node['type'] == 'link':
                target = node['content']
                try:
                    self.fs._get_node(target)
                except FileSystemError:
                    issues.append(f"Broken symlink at {path} -> {target}")

            if node['type'] == 'dir':
                for name, child in node['content'].items():
                    check_symlink(child, os.path.join(path, name))

        check_symlink(self.fs.root, '/')

    def repair_filesystem(self) -> bool:
        """Attempt to repair filesystem issues"""
        try:
            issues = self.check_integrity()
            if len(issues) == 1 and issues[0] == "Filesystem integrity check passed":
                return True

            # Repair broken directory structure
            for dir_path in ['/bin', '/etc', '/home', '/usr', '/var', '/tmp']:
                try:
                    self.fs._get_node(dir_path)
                except FileSystemError:
                    self.fs._create_directory(dir_path)

            # Fix permissions
            for path in ['/etc/passwd', '/etc/shadow']:
                try:
                    node = self.fs._get_node(path)
                    node['metadata']['permissions'] = 0o600
                except FileSystemError:
                    pass

            # Clear cache after repairs
            self.usage_cache.clear()
            self.integrity_cache.clear()

            logger.info("Filesystem repair completed")
            return True

        except Exception as e:
            logger.error(f"Failed to repair filesystem: {e}")
            return False

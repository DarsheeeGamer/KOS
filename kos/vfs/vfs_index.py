"""
KOS VFS Index System
====================
Provides filesystem indexing and metadata management for the VFS
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import IntEnum
import hashlib

logger = logging.getLogger('KOS.vfs.index')

class FileType(IntEnum):
    """VFS file types matching Unix file types"""
    REGULAR = 0o100000  # S_IFREG
    DIRECTORY = 0o040000  # S_IFDIR
    SYMLINK = 0o120000   # S_IFLNK
    BLOCK = 0o060000     # S_IFBLK
    CHAR = 0o020000      # S_IFCHR
    FIFO = 0o010000      # S_IFIFO
    SOCKET = 0o140000    # S_IFSOCK

@dataclass
class VFSEntry:
    """Represents a single entry in the VFS"""
    path: str
    name: str
    type: int
    size: int
    mode: int
    uid: int
    gid: int
    atime: float
    mtime: float
    ctime: float
    nlinks: int = 1
    blocks: int = 0
    checksum: Optional[str] = None
    symlink_target: Optional[str] = None
    children: Optional[List[str]] = None  # For directories
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'VFSEntry':
        """Create from dictionary"""
        return cls(**data)
    
    def is_directory(self) -> bool:
        """Check if this is a directory"""
        return (self.mode & 0o170000) == FileType.DIRECTORY
    
    def is_file(self) -> bool:
        """Check if this is a regular file"""
        return (self.mode & 0o170000) == FileType.REGULAR
    
    def is_symlink(self) -> bool:
        """Check if this is a symbolic link"""
        return (self.mode & 0o170000) == FileType.SYMLINK

class VFSIndex:
    """
    VFS Index System - maintains a complete index of all files and directories
    """
    
    def __init__(self, vfs):
        """Initialize VFS Index
        
        Args:
            vfs: VirtualFileSystem instance
        """
        self.vfs = vfs
        self.index: Dict[str, VFSEntry] = {}
        self.index_file = "/.vfs_index"
        self.index_version = "1.0"
        
        # Load or create index
        self._load_or_create_index()
        
        logger.info(f"VFS Index initialized with {len(self.index)} entries")
    
    def _load_or_create_index(self):
        """Load existing index or create a new one"""
        try:
            if self.vfs.exists(self.index_file):
                self._load_index()
            else:
                self._create_index()
                self._save_index()
        except Exception as e:
            logger.warning(f"Could not load index, creating new: {e}")
            self._create_index()
    
    def _load_index(self):
        """Load index from VFS"""
        try:
            # File operations use os flags
            import os
            VFS_O_RDONLY = os.O_RDONLY
            
            with self.vfs.open(self.index_file, VFS_O_RDONLY) as f:
                data = f.read()
                if data:
                    index_data = json.loads(data.decode('utf-8'))
                    
                    # Check version compatibility
                    if index_data.get('version') != self.index_version:
                        logger.warning("Index version mismatch, rebuilding")
                        self._create_index()
                        return
                    
                    # Load entries
                    for path, entry_data in index_data.get('entries', {}).items():
                        self.index[path] = VFSEntry.from_dict(entry_data)
                    
                    logger.info(f"Loaded {len(self.index)} entries from index")
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            self._create_index()
    
    def _save_index(self):
        """Save index to VFS"""
        try:
            import os
            VFS_O_WRONLY = os.O_WRONLY
            VFS_O_CREAT = os.O_CREAT
            VFS_O_TRUNC = os.O_TRUNC
            
            # Prepare index data
            index_data = {
                'version': self.index_version,
                'updated': time.time(),
                'entry_count': len(self.index),
                'entries': {path: entry.to_dict() for path, entry in self.index.items()}
            }
            
            data = json.dumps(index_data, indent=2)
            
            # Write to VFS
            flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
            with self.vfs.open(self.index_file, flags, 0o600) as f:
                f.write(data.encode('utf-8'))
            
            logger.debug(f"Saved index with {len(self.index)} entries")
            
        except Exception as e:
            logger.error(f"Error saving index: {e}")
    
    def _create_index(self):
        """Create a new index by scanning the VFS"""
        logger.info("Creating VFS index...")
        self.index = {}
        
        # Create root entry
        self._add_root_entry()
        
        # Scan filesystem
        self._scan_directory("/")
        
        logger.info(f"Created index with {len(self.index)} entries")
    
    def _add_root_entry(self):
        """Add the root directory entry"""
        now = time.time()
        self.index["/"] = VFSEntry(
            path="/",
            name="",
            type=FileType.DIRECTORY,
            size=4096,
            mode=0o40755,  # drwxr-xr-x
            uid=0,
            gid=0,
            atime=now,
            mtime=now,
            ctime=now,
            children=[]
        )
    
    def _scan_directory(self, path: str):
        """Recursively scan a directory and add entries to index"""
        try:
            # List directory contents
            entries = self.vfs.listdir(path)
            
            # Update parent's children list
            if path in self.index:
                self.index[path].children = []
            
            for entry_name in entries:
                if entry_name in ['.', '..']:
                    continue
                
                # Build full path
                if path == '/':
                    entry_path = f"/{entry_name}"
                else:
                    entry_path = f"{path}/{entry_name}"
                
                try:
                    # Get entry stats
                    stat = self.vfs.stat(entry_path)
                    
                    # Create VFS entry
                    entry = VFSEntry(
                        path=entry_path,
                        name=entry_name,
                        type=(stat.st_mode & 0o170000),
                        size=stat.st_size,
                        mode=stat.st_mode,
                        uid=stat.st_uid,
                        gid=stat.st_gid,
                        atime=stat.st_atime,
                        mtime=stat.st_mtime,
                        ctime=stat.st_ctime,
                        nlinks=stat.st_nlink,
                        blocks=getattr(stat, 'st_blocks', 0)
                    )
                    
                    # Add to index
                    self.index[entry_path] = entry
                    
                    # Add to parent's children
                    if path in self.index and self.index[path].children is not None:
                        self.index[path].children.append(entry_name)
                    
                    # Recursively scan subdirectories
                    if entry.is_directory():
                        entry.children = []
                        self._scan_directory(entry_path)
                    
                except Exception as e:
                    logger.debug(f"Could not stat {entry_path}: {e}")
                    
        except Exception as e:
            logger.debug(f"Could not scan directory {path}: {e}")
    
    def add_entry(self, path: str, entry: VFSEntry):
        """Add or update an entry in the index"""
        self.index[path] = entry
        
        # Update parent's children list
        parent_path = os.path.dirname(path)
        if parent_path in self.index:
            parent = self.index[parent_path]
            if parent.children is not None and entry.name not in parent.children:
                parent.children.append(entry.name)
        
        # Auto-save periodically
        if len(self.index) % 100 == 0:
            self._save_index()
    
    def remove_entry(self, path: str):
        """Remove an entry from the index"""
        if path in self.index:
            entry = self.index[path]
            
            # Remove from parent's children
            parent_path = os.path.dirname(path)
            if parent_path in self.index:
                parent = self.index[parent_path]
                if parent.children and entry.name in parent.children:
                    parent.children.remove(entry.name)
            
            # Remove entry
            del self.index[path]
    
    def get_entry(self, path: str) -> Optional[VFSEntry]:
        """Get an entry from the index"""
        return self.index.get(path)
    
    def list_directory(self, path: str) -> List[VFSEntry]:
        """List directory contents from index"""
        entry = self.index.get(path)
        if not entry or not entry.is_directory():
            return []
        
        children = []
        if entry.children:
            for child_name in entry.children:
                child_path = f"{path}/{child_name}" if path != '/' else f"/{child_name}"
                if child_path in self.index:
                    children.append(self.index[child_path])
        
        return children
    
    def search(self, pattern: str, path: str = "/") -> List[VFSEntry]:
        """Search for entries matching a pattern"""
        results = []
        pattern = pattern.lower()
        
        for entry_path, entry in self.index.items():
            if entry_path.startswith(path):
                if pattern in entry.name.lower() or pattern in entry_path.lower():
                    results.append(entry)
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get filesystem statistics from index"""
        stats = {
            'total_entries': len(self.index),
            'total_size': 0,
            'file_count': 0,
            'directory_count': 0,
            'symlink_count': 0,
            'largest_file': None,
            'oldest_file': None,
            'newest_file': None
        }
        
        largest_size = 0
        oldest_time = float('inf')
        newest_time = 0
        
        for entry in self.index.values():
            stats['total_size'] += entry.size
            
            if entry.is_file():
                stats['file_count'] += 1
                
                if entry.size > largest_size:
                    largest_size = entry.size
                    stats['largest_file'] = entry.path
                    
            elif entry.is_directory():
                stats['directory_count'] += 1
            elif entry.is_symlink():
                stats['symlink_count'] += 1
            
            if entry.mtime < oldest_time:
                oldest_time = entry.mtime
                stats['oldest_file'] = entry.path
            
            if entry.mtime > newest_time:
                newest_time = entry.mtime
                stats['newest_file'] = entry.path
        
        return stats
    
    def rebuild_index(self):
        """Rebuild the entire index"""
        logger.info("Rebuilding VFS index...")
        self._create_index()
        self._save_index()
        logger.info("Index rebuild complete")

# Global index instance
_vfs_index = None

def get_vfs_index(vfs) -> VFSIndex:
    """Get or create VFS index instance"""
    global _vfs_index
    if _vfs_index is None:
        _vfs_index = VFSIndex(vfs)
    return _vfs_index
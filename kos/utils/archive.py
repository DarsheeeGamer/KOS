"""
Archive and compression utilities for KOS
"""

import io
import json
import zlib
import time
from typing import List, Dict, Optional, BinaryIO
from dataclasses import dataclass

@dataclass
class ArchiveEntry:
    """Entry in an archive"""
    name: str
    size: int
    mode: int
    uid: int
    gid: int
    mtime: float
    is_dir: bool
    content: bytes = b''

class TarArchive:
    """Tar archive handler"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.entries: List[ArchiveEntry] = []
    
    def create(self, archive_path: str, files: List[str], compress: bool = False) -> bool:
        """Create tar archive"""
        if not self.vfs:
            return False
        
        self.entries = []
        
        # Collect files
        for filepath in files:
            if self.vfs.exists(filepath):
                self._add_path(filepath)
        
        # Serialize archive
        archive_data = self._serialize()
        
        # Compress if requested
        if compress:
            archive_data = zlib.compress(archive_data)
        
        # Write archive
        try:
            with self.vfs.open(archive_path, 'wb') as f:
                f.write(archive_data)
            return True
        except:
            return False
    
    def extract(self, archive_path: str, dest_dir: str = "/", compress: bool = False) -> bool:
        """Extract tar archive"""
        if not self.vfs:
            return False
        
        # Read archive
        try:
            with self.vfs.open(archive_path, 'rb') as f:
                archive_data = f.read()
        except:
            return False
        
        # Decompress if needed
        if compress:
            try:
                archive_data = zlib.decompress(archive_data)
            except:
                return False
        
        # Deserialize
        self._deserialize(archive_data)
        
        # Extract files
        for entry in self.entries:
            dest_path = f"{dest_dir}/{entry.name}".replace('//', '/')
            
            if entry.is_dir:
                if not self.vfs.exists(dest_path):
                    self.vfs.mkdir(dest_path)
            else:
                # Ensure parent directory exists
                parent = '/'.join(dest_path.split('/')[:-1])
                if parent and not self.vfs.exists(parent):
                    self.vfs.mkdir(parent)
                
                # Write file
                try:
                    with self.vfs.open(dest_path, 'wb') as f:
                        f.write(entry.content)
                except:
                    pass
        
        return True
    
    def list(self, archive_path: str, compress: bool = False) -> List[str]:
        """List contents of archive"""
        if not self.vfs:
            return []
        
        # Read archive
        try:
            with self.vfs.open(archive_path, 'rb') as f:
                archive_data = f.read()
        except:
            return []
        
        # Decompress if needed
        if compress:
            try:
                archive_data = zlib.decompress(archive_data)
            except:
                return []
        
        # Deserialize
        self._deserialize(archive_data)
        
        return [entry.name for entry in self.entries]
    
    def _add_path(self, path: str):
        """Add path to archive"""
        # Get node info
        node = self._get_node(path)
        if not node:
            return
        
        # Create entry
        entry = ArchiveEntry(
            name=path.lstrip('/'),
            size=0,
            mode=getattr(node, 'mode', 0o644),
            uid=getattr(node, 'uid', 0),
            gid=getattr(node, 'gid', 0),
            mtime=getattr(node, 'mtime', time.time()),
            is_dir=self.vfs.isdir(path)
        )
        
        if not entry.is_dir:
            # Read file content
            try:
                with self.vfs.open(path, 'rb') as f:
                    entry.content = f.read()
                    entry.size = len(entry.content)
            except:
                pass
        
        self.entries.append(entry)
        
        # Recursively add directory contents
        if entry.is_dir:
            try:
                for item in self.vfs.listdir(path):
                    self._add_path(f"{path}/{item}")
            except:
                pass
    
    def _get_node(self, path: str):
        """Get VFS node"""
        if not self.vfs or not hasattr(self.vfs, 'root'):
            return None
        
        parts = path.strip('/').split('/')
        node = self.vfs.root
        
        for part in parts:
            if not part:
                continue
            if hasattr(node, 'children') and part in node.children:
                node = node.children[part]
            else:
                return None
        
        return node
    
    def _serialize(self) -> bytes:
        """Serialize archive to bytes"""
        # Simple JSON serialization
        data = []
        for entry in self.entries:
            data.append({
                'name': entry.name,
                'size': entry.size,
                'mode': entry.mode,
                'uid': entry.uid,
                'gid': entry.gid,
                'mtime': entry.mtime,
                'is_dir': entry.is_dir,
                'content': entry.content.hex() if entry.content else ''
            })
        
        return json.dumps(data).encode()
    
    def _deserialize(self, data: bytes):
        """Deserialize archive from bytes"""
        self.entries = []
        
        try:
            entries_data = json.loads(data.decode())
            for entry_data in entries_data:
                entry = ArchiveEntry(
                    name=entry_data['name'],
                    size=entry_data['size'],
                    mode=entry_data['mode'],
                    uid=entry_data['uid'],
                    gid=entry_data['gid'],
                    mtime=entry_data['mtime'],
                    is_dir=entry_data['is_dir'],
                    content=bytes.fromhex(entry_data['content']) if entry_data['content'] else b''
                )
                self.entries.append(entry)
        except:
            pass

class ZipArchive:
    """ZIP archive handler"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.tar = TarArchive(vfs)  # Reuse tar implementation
    
    def create(self, archive_path: str, files: List[str]) -> bool:
        """Create ZIP archive"""
        # Use tar with compression
        return self.tar.create(archive_path, files, compress=True)
    
    def extract(self, archive_path: str, dest_dir: str = "/") -> bool:
        """Extract ZIP archive"""
        return self.tar.extract(archive_path, dest_dir, compress=True)
    
    def list(self, archive_path: str) -> List[str]:
        """List ZIP contents"""
        return self.tar.list(archive_path, compress=True)

class Compressor:
    """File compression utilities"""
    
    @staticmethod
    def gzip(data: bytes) -> bytes:
        """Gzip compress data"""
        return zlib.compress(data, level=9)
    
    @staticmethod
    def gunzip(data: bytes) -> bytes:
        """Gzip decompress data"""
        return zlib.decompress(data)
    
    @staticmethod
    def compress_file(vfs, input_path: str, output_path: str) -> bool:
        """Compress a file"""
        try:
            with vfs.open(input_path, 'rb') as f:
                data = f.read()
            
            compressed = Compressor.gzip(data)
            
            with vfs.open(output_path, 'wb') as f:
                f.write(compressed)
            
            return True
        except:
            return False
    
    @staticmethod
    def decompress_file(vfs, input_path: str, output_path: str) -> bool:
        """Decompress a file"""
        try:
            with vfs.open(input_path, 'rb') as f:
                compressed = f.read()
            
            data = Compressor.gunzip(compressed)
            
            with vfs.open(output_path, 'wb') as f:
                f.write(data)
            
            return True
        except:
            return False
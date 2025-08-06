"""
Backup and restore utilities for KOS
"""

import time
import json
import hashlib
from typing import List, Dict, Optional
from dataclasses import dataclass, field

@dataclass
class BackupManifest:
    """Backup manifest"""
    backup_id: str
    timestamp: float
    description: str
    files: List[str]
    total_size: int
    checksum: str
    incremental: bool = False
    parent_backup: Optional[str] = None

class BackupManager:
    """System backup manager"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.backup_dir = "/var/backups"
        self.manifest_file = f"{self.backup_dir}/manifest.json"
        self.manifests: Dict[str, BackupManifest] = {}
        
        self._init_backup_dir()
        self._load_manifests()
    
    def _init_backup_dir(self):
        """Initialize backup directory"""
        if not self.vfs:
            return
        
        if not self.vfs.exists(self.backup_dir):
            try:
                self.vfs.mkdir(self.backup_dir)
            except:
                pass
    
    def _load_manifests(self):
        """Load backup manifests"""
        if not self.vfs or not self.vfs.exists(self.manifest_file):
            return
        
        try:
            with self.vfs.open(self.manifest_file, 'r') as f:
                data = json.loads(f.read().decode())
            
            for manifest_data in data:
                manifest = BackupManifest(**manifest_data)
                self.manifests[manifest.backup_id] = manifest
        except:
            pass
    
    def _save_manifests(self):
        """Save backup manifests"""
        if not self.vfs:
            return
        
        try:
            data = []
            for manifest in self.manifests.values():
                data.append({
                    'backup_id': manifest.backup_id,
                    'timestamp': manifest.timestamp,
                    'description': manifest.description,
                    'files': manifest.files,
                    'total_size': manifest.total_size,
                    'checksum': manifest.checksum,
                    'incremental': manifest.incremental,
                    'parent_backup': manifest.parent_backup
                })
            
            with self.vfs.open(self.manifest_file, 'w') as f:
                f.write(json.dumps(data, indent=2).encode())
        except:
            pass
    
    def create_backup(self, paths: List[str], description: str = "",
                     incremental: bool = False) -> Optional[str]:
        """Create system backup"""
        if not self.vfs:
            return None
        
        # Generate backup ID
        backup_id = f"backup_{int(time.time())}"
        backup_file = f"{self.backup_dir}/{backup_id}.tar"
        
        # Collect files
        from kos.utils.archive import TarArchive
        archive = TarArchive(self.vfs)
        
        if archive.create(backup_file, paths, compress=True):
            # Calculate checksum
            try:
                with self.vfs.open(backup_file, 'rb') as f:
                    data = f.read()
                    checksum = hashlib.sha256(data).hexdigest()
                    total_size = len(data)
            except:
                checksum = ""
                total_size = 0
            
            # Create manifest
            manifest = BackupManifest(
                backup_id=backup_id,
                timestamp=time.time(),
                description=description or f"Backup created at {time.ctime()}",
                files=paths,
                total_size=total_size,
                checksum=checksum,
                incremental=incremental,
                parent_backup=self._get_last_backup_id() if incremental else None
            )
            
            self.manifests[backup_id] = manifest
            self._save_manifests()
            
            return backup_id
        
        return None
    
    def restore_backup(self, backup_id: str, target_dir: str = "/") -> bool:
        """Restore from backup"""
        if not self.vfs or backup_id not in self.manifests:
            return False
        
        manifest = self.manifests[backup_id]
        backup_file = f"{self.backup_dir}/{backup_id}.tar"
        
        # Verify checksum
        if manifest.checksum:
            try:
                with self.vfs.open(backup_file, 'rb') as f:
                    data = f.read()
                    if hashlib.sha256(data).hexdigest() != manifest.checksum:
                        return False  # Checksum mismatch
            except:
                return False
        
        # Restore files
        from kos.utils.archive import TarArchive
        archive = TarArchive(self.vfs)
        
        return archive.extract(backup_file, target_dir, compress=True)
    
    def list_backups(self) -> List[BackupManifest]:
        """List all backups"""
        return sorted(self.manifests.values(), 
                     key=lambda x: x.timestamp, reverse=True)
    
    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup"""
        if backup_id not in self.manifests:
            return False
        
        backup_file = f"{self.backup_dir}/{backup_id}.tar"
        
        # Delete backup file
        if self.vfs and self.vfs.exists(backup_file):
            try:
                self.vfs.remove(backup_file)
            except:
                pass
        
        # Remove manifest
        del self.manifests[backup_id]
        self._save_manifests()
        
        return True
    
    def verify_backup(self, backup_id: str) -> bool:
        """Verify backup integrity"""
        if backup_id not in self.manifests:
            return False
        
        manifest = self.manifests[backup_id]
        backup_file = f"{self.backup_dir}/{backup_id}.tar"
        
        # Check file exists
        if not self.vfs or not self.vfs.exists(backup_file):
            return False
        
        # Verify checksum
        try:
            with self.vfs.open(backup_file, 'rb') as f:
                data = f.read()
                return hashlib.sha256(data).hexdigest() == manifest.checksum
        except:
            return False
    
    def _get_last_backup_id(self) -> Optional[str]:
        """Get ID of last backup"""
        backups = self.list_backups()
        return backups[0].backup_id if backups else None
    
    def schedule_backup(self, paths: List[str], cron_schedule: str):
        """Schedule automatic backups"""
        # Would integrate with cron service
        # For now, just a placeholder
        pass

class SnapshotManager:
    """VFS snapshot manager"""
    
    def __init__(self, vfs=None):
        self.vfs = vfs
        self.snapshot_dir = "/var/snapshots"
        self.snapshots: Dict[str, str] = {}
    
    def create_snapshot(self, name: str) -> bool:
        """Create VFS snapshot"""
        if not self.vfs:
            return False
        
        # Save entire VFS state
        snapshot_file = f"{self.snapshot_dir}/{name}.snapshot"
        
        try:
            # In real implementation, would use copy-on-write
            # For now, just copy the VFS disk file
            import pickle
            
            if hasattr(self.vfs, 'root'):
                with self.vfs.open(snapshot_file, 'wb') as f:
                    pickle.dump(self.vfs.root, f)
                
                self.snapshots[name] = snapshot_file
                return True
        except:
            pass
        
        return False
    
    def restore_snapshot(self, name: str) -> bool:
        """Restore from snapshot"""
        if not self.vfs or name not in self.snapshots:
            return False
        
        snapshot_file = self.snapshots[name]
        
        try:
            import pickle
            
            with self.vfs.open(snapshot_file, 'rb') as f:
                self.vfs.root = pickle.load(f)
            
            self.vfs._save()
            return True
        except:
            pass
        
        return False
    
    def list_snapshots(self) -> List[str]:
        """List available snapshots"""
        return list(self.snapshots.keys())
    
    def delete_snapshot(self, name: str) -> bool:
        """Delete a snapshot"""
        if name not in self.snapshots:
            return False
        
        snapshot_file = self.snapshots[name]
        
        if self.vfs and self.vfs.exists(snapshot_file):
            try:
                self.vfs.remove(snapshot_file)
            except:
                pass
        
        del self.snapshots[name]
        return True
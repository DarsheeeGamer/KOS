"""
File permissions and ownership system for KOS
"""

import time
from typing import Optional, List, Dict
from dataclasses import dataclass
from enum import IntFlag

class Permission(IntFlag):
    """Unix-style file permissions"""
    # Owner permissions
    OWNER_READ = 0o400
    OWNER_WRITE = 0o200
    OWNER_EXEC = 0o100
    
    # Group permissions
    GROUP_READ = 0o040
    GROUP_WRITE = 0o020
    GROUP_EXEC = 0o010
    
    # Other permissions
    OTHER_READ = 0o004
    OTHER_WRITE = 0o002
    OTHER_EXEC = 0o001
    
    # Special permissions
    SETUID = 0o4000
    SETGID = 0o2000
    STICKY = 0o1000
    
    # Combinations
    OWNER_ALL = OWNER_READ | OWNER_WRITE | OWNER_EXEC
    GROUP_ALL = GROUP_READ | GROUP_WRITE | GROUP_EXEC
    OTHER_ALL = OTHER_READ | OTHER_WRITE | OTHER_EXEC

@dataclass
class FilePermissions:
    """File permissions and ownership"""
    mode: int = 0o644  # Default: rw-r--r--
    uid: int = 0  # Owner user ID
    gid: int = 0  # Owner group ID
    
    def check_read(self, uid: int, gid: int, groups: List[int] = None) -> bool:
        """Check read permission"""
        if uid == 0:  # Root has all permissions
            return True
        
        if uid == self.uid:
            return bool(self.mode & Permission.OWNER_READ)
        
        if gid == self.gid or (groups and self.gid in groups):
            return bool(self.mode & Permission.GROUP_READ)
        
        return bool(self.mode & Permission.OTHER_READ)
    
    def check_write(self, uid: int, gid: int, groups: List[int] = None) -> bool:
        """Check write permission"""
        if uid == 0:
            return True
        
        if uid == self.uid:
            return bool(self.mode & Permission.OWNER_WRITE)
        
        if gid == self.gid or (groups and self.gid in groups):
            return bool(self.mode & Permission.GROUP_WRITE)
        
        return bool(self.mode & Permission.OTHER_WRITE)
    
    def check_execute(self, uid: int, gid: int, groups: List[int] = None) -> bool:
        """Check execute permission"""
        if uid == 0:
            return True
        
        if uid == self.uid:
            return bool(self.mode & Permission.OWNER_EXEC)
        
        if gid == self.gid or (groups and self.gid in groups):
            return bool(self.mode & Permission.GROUP_EXEC)
        
        return bool(self.mode & Permission.OTHER_EXEC)
    
    def to_string(self) -> str:
        """Convert permissions to string format (e.g., 'rwxr-xr-x')"""
        result = []
        
        # Owner permissions
        result.append('r' if self.mode & Permission.OWNER_READ else '-')
        result.append('w' if self.mode & Permission.OWNER_WRITE else '-')
        if self.mode & Permission.SETUID and self.mode & Permission.OWNER_EXEC:
            result.append('s')
        elif self.mode & Permission.SETUID:
            result.append('S')
        elif self.mode & Permission.OWNER_EXEC:
            result.append('x')
        else:
            result.append('-')
        
        # Group permissions
        result.append('r' if self.mode & Permission.GROUP_READ else '-')
        result.append('w' if self.mode & Permission.GROUP_WRITE else '-')
        if self.mode & Permission.SETGID and self.mode & Permission.GROUP_EXEC:
            result.append('s')
        elif self.mode & Permission.SETGID:
            result.append('S')
        elif self.mode & Permission.GROUP_EXEC:
            result.append('x')
        else:
            result.append('-')
        
        # Other permissions
        result.append('r' if self.mode & Permission.OTHER_READ else '-')
        result.append('w' if self.mode & Permission.OTHER_WRITE else '-')
        if self.mode & Permission.STICKY and self.mode & Permission.OTHER_EXEC:
            result.append('t')
        elif self.mode & Permission.STICKY:
            result.append('T')
        elif self.mode & Permission.OTHER_EXEC:
            result.append('x')
        else:
            result.append('-')
        
        return ''.join(result)
    
    @classmethod
    def from_string(cls, perm_str: str) -> 'FilePermissions':
        """Create from string format (e.g., 'rwxr-xr-x')"""
        if len(perm_str) != 9:
            raise ValueError("Permission string must be 9 characters")
        
        mode = 0
        
        # Owner permissions
        if perm_str[0] == 'r':
            mode |= Permission.OWNER_READ
        if perm_str[1] == 'w':
            mode |= Permission.OWNER_WRITE
        if perm_str[2] in 'xs':
            mode |= Permission.OWNER_EXEC
        if perm_str[2] in 'sS':
            mode |= Permission.SETUID
        
        # Group permissions
        if perm_str[3] == 'r':
            mode |= Permission.GROUP_READ
        if perm_str[4] == 'w':
            mode |= Permission.GROUP_WRITE
        if perm_str[5] in 'xs':
            mode |= Permission.GROUP_EXEC
        if perm_str[5] in 'sS':
            mode |= Permission.SETGID
        
        # Other permissions
        if perm_str[6] == 'r':
            mode |= Permission.OTHER_READ
        if perm_str[7] == 'w':
            mode |= Permission.OTHER_WRITE
        if perm_str[8] in 'xt':
            mode |= Permission.OTHER_EXEC
        if perm_str[8] in 'tT':
            mode |= Permission.STICKY
        
        return cls(mode=mode)
    
    @classmethod
    def from_octal(cls, octal_str: str) -> 'FilePermissions':
        """Create from octal string (e.g., '755')"""
        mode = int(octal_str, 8)
        return cls(mode=mode)

class PermissionManager:
    """Manages file permissions system-wide"""
    
    def __init__(self, vfs=None, auth=None):
        self.vfs = vfs
        self.auth = auth
        self.umask = 0o022  # Default umask
        
        # ACL support (simplified)
        self.acls: Dict[str, List[Dict]] = {}
    
    def chmod(self, path: str, mode: int, uid: int = 0) -> bool:
        """Change file permissions"""
        if not self.vfs:
            return False
        
        # Get current permissions
        node = self._get_node(path)
        if not node:
            return False
        
        # Check if user can change permissions
        if uid != 0 and uid != getattr(node, 'uid', 0):
            return False
        
        # Update permissions
        node.mode = mode
        return True
    
    def chown(self, path: str, new_uid: int, new_gid: int = -1, uid: int = 0) -> bool:
        """Change file ownership"""
        if not self.vfs:
            return False
        
        # Only root can change ownership
        if uid != 0:
            return False
        
        node = self._get_node(path)
        if not node:
            return False
        
        node.uid = new_uid
        if new_gid != -1:
            node.gid = new_gid
        
        return True
    
    def check_access(self, path: str, uid: int, gid: int, 
                    mode: str = 'r', groups: List[int] = None) -> bool:
        """Check if user has access to file"""
        node = self._get_node(path)
        if not node:
            return False
        
        perms = FilePermissions(
            mode=getattr(node, 'mode', 0o644),
            uid=getattr(node, 'uid', 0),
            gid=getattr(node, 'gid', 0)
        )
        
        # Check ACLs first
        if self._check_acl(path, uid, mode):
            return True
        
        # Check standard permissions
        if mode == 'r':
            return perms.check_read(uid, gid, groups)
        elif mode == 'w':
            return perms.check_write(uid, gid, groups)
        elif mode == 'x':
            return perms.check_execute(uid, gid, groups)
        
        return False
    
    def _get_node(self, path: str):
        """Get VFS node for path"""
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
    
    def set_umask(self, new_umask: int) -> int:
        """Set umask and return old value"""
        old_umask = self.umask
        self.umask = new_umask
        return old_umask
    
    def get_umask(self) -> int:
        """Get current umask"""
        return self.umask
    
    def apply_umask(self, mode: int) -> int:
        """Apply umask to mode"""
        return mode & ~self.umask
    
    def add_acl(self, path: str, uid: int, permissions: str):
        """Add ACL entry for path"""
        if path not in self.acls:
            self.acls[path] = []
        
        self.acls[path].append({
            'uid': uid,
            'permissions': permissions
        })
    
    def remove_acl(self, path: str, uid: int = None):
        """Remove ACL entries"""
        if path not in self.acls:
            return
        
        if uid is None:
            # Remove all ACLs for path
            del self.acls[path]
        else:
            # Remove specific user's ACL
            self.acls[path] = [
                acl for acl in self.acls[path]
                if acl['uid'] != uid
            ]
    
    def _check_acl(self, path: str, uid: int, mode: str) -> bool:
        """Check ACL permissions"""
        if path not in self.acls:
            return False
        
        for acl in self.acls[path]:
            if acl['uid'] == uid and mode in acl['permissions']:
                return True
        
        return False
    
    def list_acl(self, path: str) -> List[Dict]:
        """List ACL entries for path"""
        return self.acls.get(path, [])

class Capabilities:
    """Linux-style capabilities system"""
    
    # Capability flags
    CAP_SYS_ADMIN = 0x0001
    CAP_NET_ADMIN = 0x0002
    CAP_SYS_TIME = 0x0004
    CAP_KILL = 0x0008
    CAP_SETUID = 0x0010
    CAP_SETGID = 0x0020
    CAP_CHOWN = 0x0040
    CAP_DAC_OVERRIDE = 0x0080
    CAP_FOWNER = 0x0100
    CAP_MKNOD = 0x0200
    CAP_NET_BIND = 0x0400
    CAP_SYS_BOOT = 0x0800
    
    def __init__(self):
        self.process_caps: Dict[int, int] = {}
    
    def grant(self, pid: int, capability: int):
        """Grant capability to process"""
        if pid not in self.process_caps:
            self.process_caps[pid] = 0
        
        self.process_caps[pid] |= capability
    
    def revoke(self, pid: int, capability: int):
        """Revoke capability from process"""
        if pid in self.process_caps:
            self.process_caps[pid] &= ~capability
    
    def check(self, pid: int, capability: int) -> bool:
        """Check if process has capability"""
        if pid not in self.process_caps:
            return False
        
        return bool(self.process_caps[pid] & capability)
    
    def drop_all(self, pid: int):
        """Drop all capabilities for process"""
        if pid in self.process_caps:
            del self.process_caps[pid]
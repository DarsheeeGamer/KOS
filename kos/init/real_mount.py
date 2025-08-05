"""
KOS Real Mount Operations
Direct mount/umount system calls
"""

import os
import ctypes
import logging
from typing import Optional, List, Dict, Any
from enum import IntEnum

logger = logging.getLogger('kos.init.mount')


class MountFlags(IntEnum):
    """Linux mount flags"""
    MS_RDONLY = 1           # Mount read-only
    MS_NOSUID = 2           # Ignore suid and sgid bits
    MS_NODEV = 4            # Disallow access to device special files
    MS_NOEXEC = 8           # Disallow program execution
    MS_SYNCHRONOUS = 16    # Writes are synced at once
    MS_REMOUNT = 32         # Alter flags of a mounted FS
    MS_MANDLOCK = 64        # Allow mandatory locks on an FS
    MS_DIRSYNC = 128        # Directory modifications are synchronous
    MS_NOATIME = 1024       # Do not update access times
    MS_NODIRATIME = 2048    # Do not update directory access times
    MS_BIND = 4096          # Bind mount
    MS_MOVE = 8192          # Move mount
    MS_REC = 16384          # Recursive mount
    MS_SILENT = 32768       # Suppress some messages
    MS_POSIXACL = (1 << 16) # VFS does not apply the umask
    MS_UNBINDABLE = (1 << 17) # Change to unbindable
    MS_PRIVATE = (1 << 18)  # Change to private
    MS_SLAVE = (1 << 19)    # Change to slave
    MS_SHARED = (1 << 20)   # Change to shared
    MS_RELATIME = (1 << 21) # Update atime relative to mtime/ctime
    MS_KERNMOUNT = (1 << 22) # Kernel internal mount
    MS_I_VERSION = (1 << 23) # Update inode I_version field
    MS_STRICTATIME = (1 << 24) # Always perform atime updates
    MS_LAZYTIME = (1 << 25) # Update the on-disk timestamps lazily


class UmountFlags(IntEnum):
    """Linux umount flags"""
    MNT_FORCE = 1       # Force unmount
    MNT_DETACH = 2      # Lazy unmount
    MNT_EXPIRE = 4      # Mark for expiry
    UMOUNT_NOFOLLOW = 8 # Don't follow symlinks


class RealMountManager:
    """Real mount operations using system calls"""
    
    def __init__(self):
        self.libc = ctypes.CDLL("libc.so.6", use_errno=True)
        self._setup_syscalls()
        self.mounts = []  # Track active mounts
        
    def _setup_syscalls(self):
        """Setup system call signatures"""
        # int mount(const char *source, const char *target,
        #          const char *filesystemtype, unsigned long mountflags,
        #          const void *data)
        self.libc.mount.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p,
            ctypes.c_ulong, ctypes.c_void_p
        ]
        self.libc.mount.restype = ctypes.c_int
        
        # int umount2(const char *target, int flags)
        self.libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
        self.libc.umount2.restype = ctypes.c_int
        
    def mount(self, source: str, target: str, fstype: str, 
             flags: int = 0, data: Optional[str] = None) -> bool:
        """Mount filesystem"""
        # Ensure target directory exists
        try:
            os.makedirs(target, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create mount point {target}: {e}")
            return False
            
        # Convert to bytes
        source_bytes = source.encode('utf-8') if source else None
        target_bytes = target.encode('utf-8')
        fstype_bytes = fstype.encode('utf-8') if fstype else None
        data_bytes = data.encode('utf-8') if data else None
        
        # Perform mount
        ret = self.libc.mount(source_bytes, target_bytes, fstype_bytes, flags, data_bytes)
        
        if ret == 0:
            # Track mount
            self.mounts.append({
                'source': source,
                'target': target,
                'fstype': fstype,
                'flags': flags,
                'data': data
            })
            logger.info(f"Mounted {source} on {target} type {fstype}")
            return True
        else:
            errno = ctypes.get_errno()
            logger.error(f"Mount failed: {os.strerror(errno)}")
            return False
            
    def umount(self, target: str, flags: int = 0) -> bool:
        """Unmount filesystem"""
        target_bytes = target.encode('utf-8')
        
        ret = self.libc.umount2(target_bytes, flags)
        
        if ret == 0:
            # Remove from tracked mounts
            self.mounts = [m for m in self.mounts if m['target'] != target]
            logger.info(f"Unmounted {target}")
            return True
        else:
            errno = ctypes.get_errno()
            logger.error(f"Unmount failed: {os.strerror(errno)}")
            return False
            
    def bind_mount(self, source: str, target: str, readonly: bool = False) -> bool:
        """Create bind mount"""
        flags = MountFlags.MS_BIND
        
        # First do the bind mount
        if not self.mount(source, target, None, flags):
            return False
            
        # Then remount if readonly requested
        if readonly:
            flags = MountFlags.MS_BIND | MountFlags.MS_RDONLY | MountFlags.MS_REMOUNT
            return self.mount(source, target, None, flags)
            
        return True
        
    def move_mount(self, source: str, target: str) -> bool:
        """Move mount to new location"""
        flags = MountFlags.MS_MOVE
        return self.mount(source, target, None, flags)
        
    def remount(self, target: str, flags: int, data: Optional[str] = None) -> bool:
        """Remount with new flags"""
        flags |= MountFlags.MS_REMOUNT
        
        # Find original mount info
        mount_info = None
        for m in self.mounts:
            if m['target'] == target:
                mount_info = m
                break
                
        if mount_info:
            return self.mount(mount_info['source'], target, 
                            mount_info['fstype'], flags, data)
        else:
            # Try remount anyway
            return self.mount(None, target, None, flags, data)
            
    def mount_essential_filesystems(self):
        """Mount essential system filesystems"""
        essential_mounts = [
            # source, target, fstype, flags, data
            ("proc", "/proc", "proc", 
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV, None),
             
            ("sysfs", "/sys", "sysfs",
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV, None),
             
            ("devtmpfs", "/dev", "devtmpfs",
             MountFlags.MS_NOSUID | MountFlags.MS_STRICTATIME, "mode=755"),
             
            ("securityfs", "/sys/kernel/security", "securityfs",
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV, None),
             
            ("tmpfs", "/dev/shm", "tmpfs",
             MountFlags.MS_NOSUID | MountFlags.MS_NODEV, None),
             
            ("devpts", "/dev/pts", "devpts",
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC, 
             "mode=620,gid=5"),
             
            ("tmpfs", "/run", "tmpfs",
             MountFlags.MS_NOSUID | MountFlags.MS_NODEV | MountFlags.MS_STRICTATIME,
             "mode=755"),
             
            ("tmpfs", "/sys/fs/cgroup", "tmpfs",
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV,
             "mode=755"),
             
            ("cgroup2", "/sys/fs/cgroup/unified", "cgroup2",
             MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV, None),
        ]
        
        # Mount cgroup v1 controllers
        cgroup_controllers = [
            "cpu", "cpuacct", "cpuset", "memory", "devices",
            "freezer", "net_cls", "blkio", "perf_event", "net_prio",
            "hugetlb", "pids", "rdma"
        ]
        
        for controller in cgroup_controllers:
            essential_mounts.append((
                "cgroup", f"/sys/fs/cgroup/{controller}", "cgroup",
                MountFlags.MS_NOSUID | MountFlags.MS_NOEXEC | MountFlags.MS_NODEV,
                controller
            ))
            
        # Perform mounts
        for source, target, fstype, flags, data in essential_mounts:
            self.mount(source, target, fstype, flags, data)
            
    def mount_fstab(self, fstab_path: str = "/etc/fstab"):
        """Mount filesystems from fstab"""
        if not os.path.exists(fstab_path):
            logger.warning(f"fstab not found: {fstab_path}")
            return
            
        with open(fstab_path, 'r') as f:
            for line in f:
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                    
                # Parse fstab entry
                parts = line.split()
                if len(parts) < 4:
                    continue
                    
                source = parts[0]
                target = parts[1]
                fstype = parts[2]
                options = parts[3] if len(parts) > 3 else "defaults"
                
                # Skip special entries
                if target in ['none', 'swap']:
                    continue
                    
                # Parse mount options
                flags, data = self._parse_mount_options(options)
                
                # Perform mount
                self.mount(source, target, fstype, flags, data)
                
    def _parse_mount_options(self, options: str) -> tuple[int, Optional[str]]:
        """Parse mount options string"""
        flags = 0
        data_opts = []
        
        option_map = {
            'ro': MountFlags.MS_RDONLY,
            'nosuid': MountFlags.MS_NOSUID,
            'nodev': MountFlags.MS_NODEV,
            'noexec': MountFlags.MS_NOEXEC,
            'sync': MountFlags.MS_SYNCHRONOUS,
            'dirsync': MountFlags.MS_DIRSYNC,
            'noatime': MountFlags.MS_NOATIME,
            'nodiratime': MountFlags.MS_NODIRATIME,
            'relatime': MountFlags.MS_RELATIME,
            'strictatime': MountFlags.MS_STRICTATIME,
            'lazytime': MountFlags.MS_LAZYTIME,
        }
        
        for opt in options.split(','):
            opt = opt.strip()
            
            if opt in option_map:
                flags |= option_map[opt]
            elif opt == 'rw':
                flags &= ~MountFlags.MS_RDONLY
            elif opt == 'defaults':
                # Default options
                pass
            elif '=' in opt:
                # Key=value option
                data_opts.append(opt)
            else:
                # Other filesystem-specific option
                data_opts.append(opt)
                
        data = ','.join(data_opts) if data_opts else None
        return flags, data
        
    def get_mounts(self) -> List[Dict[str, Any]]:
        """Get list of current mounts"""
        mounts = []
        
        # Read from /proc/mounts
        try:
            with open('/proc/mounts', 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 4:
                        mounts.append({
                            'source': parts[0],
                            'target': parts[1],
                            'fstype': parts[2],
                            'options': parts[3].split(','),
                            'dump': int(parts[4]) if len(parts) > 4 else 0,
                            'pass': int(parts[5]) if len(parts) > 5 else 0
                        })
        except:
            # Fallback to tracked mounts
            mounts = self.mounts.copy()
            
        return mounts
        
    def is_mounted(self, target: str) -> bool:
        """Check if path is a mount point"""
        mounts = self.get_mounts()
        return any(m['target'] == target for m in mounts)
        
    def unmount_all(self, force: bool = False):
        """Unmount all filesystems in reverse order"""
        mounts = self.get_mounts()
        
        # Sort by mount path length (deepest first)
        mounts.sort(key=lambda m: len(m['target']), reverse=True)
        
        # Skip essential mounts unless force
        essential = ['/', '/proc', '/sys', '/dev', '/run']
        
        for mount in mounts:
            target = mount['target']
            
            if not force and target in essential:
                continue
                
            flags = UmountFlags.MNT_DETACH if force else 0
            self.umount(target, flags)


# Global mount manager
_mount_manager = None

def get_mount_manager() -> RealMountManager:
    """Get global mount manager instance"""
    global _mount_manager
    if _mount_manager is None:
        _mount_manager = RealMountManager()
    return _mount_manager
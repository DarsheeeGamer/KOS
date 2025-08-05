"""
KOS Container Namespace Real Implementation
Using actual Linux namespace system calls
"""

import os
import ctypes
import logging
from typing import Dict, Optional, Tuple
from enum import IntEnum

logger = logging.getLogger('kos.container.namespace')


# Linux namespace constants
class CloneFlags(IntEnum):
    """Linux clone flags for namespace creation"""
    CLONE_VM = 0x00000100
    CLONE_FS = 0x00000200
    CLONE_FILES = 0x00000400
    CLONE_SIGHAND = 0x00000800
    CLONE_PIDFD = 0x00001000
    CLONE_PTRACE = 0x00002000
    CLONE_VFORK = 0x00004000
    CLONE_PARENT = 0x00008000
    CLONE_THREAD = 0x00010000
    CLONE_NEWNS = 0x00020000    # Mount namespace
    CLONE_SYSVSEM = 0x00040000
    CLONE_SETTLS = 0x00080000
    CLONE_PARENT_SETTID = 0x00100000
    CLONE_CHILD_CLEARTID = 0x00200000
    CLONE_DETACHED = 0x00400000
    CLONE_UNTRACED = 0x00800000
    CLONE_CHILD_SETTID = 0x01000000
    CLONE_NEWCGROUP = 0x02000000  # Cgroup namespace
    CLONE_NEWUTS = 0x04000000     # UTS namespace
    CLONE_NEWIPC = 0x08000000     # IPC namespace
    CLONE_NEWUSER = 0x10000000    # User namespace
    CLONE_NEWPID = 0x20000000     # PID namespace
    CLONE_NEWNET = 0x40000000     # Network namespace
    CLONE_IO = 0x80000000


# Load libc for system calls
libc = ctypes.CDLL("libc.so.6", use_errno=True)


class NamespaceManager:
    """Real namespace management using Linux system calls"""
    
    NAMESPACE_FILES = {
        'mnt': 'mnt',
        'uts': 'uts',
        'ipc': 'ipc',
        'pid': 'pid',
        'net': 'net',
        'user': 'user',
        'cgroup': 'cgroup',
    }
    
    def __init__(self):
        self.libc = libc
        self._setup_syscalls()
        
    def _setup_syscalls(self):
        """Setup system call signatures"""
        # int setns(int fd, int nstype)
        self.libc.setns.argtypes = [ctypes.c_int, ctypes.c_int]
        self.libc.setns.restype = ctypes.c_int
        
        # int unshare(int flags)
        self.libc.unshare.argtypes = [ctypes.c_int]
        self.libc.unshare.restype = ctypes.c_int
        
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
        
        # int pivot_root(const char *new_root, const char *put_old)
        self.libc.pivot_root.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        self.libc.pivot_root.restype = ctypes.c_int
        
        # int sethostname(const char *name, size_t len)
        self.libc.sethostname.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
        self.libc.sethostname.restype = ctypes.c_int
        
    def create_namespace(self, ns_type: str) -> str:
        """Create new namespace using unshare()"""
        flag_map = {
            'mnt': CloneFlags.CLONE_NEWNS,
            'uts': CloneFlags.CLONE_NEWUTS,
            'ipc': CloneFlags.CLONE_NEWIPC,
            'pid': CloneFlags.CLONE_NEWPID,
            'net': CloneFlags.CLONE_NEWNET,
            'user': CloneFlags.CLONE_NEWUSER,
            'cgroup': CloneFlags.CLONE_NEWCGROUP,
        }
        
        if ns_type not in flag_map:
            raise ValueError(f"Unknown namespace type: {ns_type}")
            
        flag = flag_map[ns_type]
        
        # Unshare the namespace
        ret = self.libc.unshare(flag)
        if ret < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"unshare failed for {ns_type}: {os.strerror(errno)}")
            
        # Return path to the namespace file
        return f"/proc/{os.getpid()}/ns/{ns_type}"
        
    def enter_namespace(self, ns_path: str, ns_type: Optional[str] = None):
        """Enter existing namespace using setns()"""
        # Open namespace file
        fd = os.open(ns_path, os.O_RDONLY)
        
        try:
            # Determine namespace type if not provided
            if ns_type is None:
                # Try to determine from path
                for ns, suffix in self.NAMESPACE_FILES.items():
                    if ns_path.endswith(f"/ns/{suffix}"):
                        ns_type = ns
                        break
                        
            # Get appropriate flag
            flag_map = {
                'mnt': 0,  # 0 means "any namespace"
                'uts': CloneFlags.CLONE_NEWUTS,
                'ipc': CloneFlags.CLONE_NEWIPC,
                'pid': CloneFlags.CLONE_NEWPID,
                'net': CloneFlags.CLONE_NEWNET,
                'user': CloneFlags.CLONE_NEWUSER,
                'cgroup': CloneFlags.CLONE_NEWCGROUP,
            }
            
            flag = flag_map.get(ns_type, 0)
            
            # Enter namespace
            ret = self.libc.setns(fd, flag)
            if ret < 0:
                errno = ctypes.get_errno()
                raise OSError(errno, f"setns failed: {os.strerror(errno)}")
                
        finally:
            os.close(fd)
            
    def setup_mount_namespace(self, rootfs: str):
        """Setup mount namespace with new root"""
        # Ensure we're in a mount namespace
        self.create_namespace('mnt')
        
        # Make everything private
        self._mount(None, "/", None, self.MS_REC | self.MS_PRIVATE, None)
        
        # Mount rootfs
        self._mount(rootfs, rootfs, None, self.MS_BIND | self.MS_REC, None)
        
        # Create put_old directory
        put_old = os.path.join(rootfs, "put_old")
        os.makedirs(put_old, exist_ok=True)
        
        # Pivot root
        ret = self.libc.pivot_root(rootfs.encode(), put_old.encode())
        if ret < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"pivot_root failed: {os.strerror(errno)}")
            
        # Change to new root
        os.chdir("/")
        
        # Unmount old root
        self._umount("/put_old", self.MNT_DETACH)
        os.rmdir("/put_old")
        
        # Mount essential filesystems
        self._setup_essential_mounts()
        
    def _setup_essential_mounts(self):
        """Mount essential filesystems in container"""
        mounts = [
            ("proc", "/proc", "proc", self.MS_NOSUID | self.MS_NOEXEC | self.MS_NODEV, None),
            ("sysfs", "/sys", "sysfs", self.MS_NOSUID | self.MS_NOEXEC | self.MS_NODEV | self.MS_RDONLY, None),
            ("tmpfs", "/dev", "tmpfs", self.MS_NOSUID | self.MS_STRICTATIME, "mode=755"),
            ("devpts", "/dev/pts", "devpts", self.MS_NOSUID | self.MS_NOEXEC, "mode=600,ptmxmode=666"),
            ("tmpfs", "/dev/shm", "tmpfs", self.MS_NOSUID | self.MS_NODEV | self.MS_NOEXEC, None),
            ("tmpfs", "/run", "tmpfs", self.MS_NOSUID | self.MS_NODEV | self.MS_STRICTATIME, "mode=755"),
        ]
        
        for source, target, fstype, flags, data in mounts:
            # Create mount point
            os.makedirs(target, exist_ok=True)
            
            # Mount filesystem
            try:
                self._mount(source, target, fstype, flags, data)
            except OSError as e:
                logger.warning(f"Failed to mount {fstype} on {target}: {e}")
                
    def setup_network_namespace(self) -> Tuple[str, str]:
        """Setup network namespace with veth pair"""
        import subprocess
        import random
        
        # Create network namespace
        ns_path = self.create_namespace('net')
        
        # Generate veth names
        rand_id = random.randint(1000, 9999)
        host_veth = f"veth{rand_id}h"
        container_veth = f"veth{rand_id}c"
        
        # Create veth pair using ip command
        try:
            # Create veth pair
            subprocess.run([
                "ip", "link", "add", host_veth,
                "type", "veth", "peer", "name", container_veth
            ], check=True, capture_output=True)
            
            # Move container end to namespace
            subprocess.run([
                "ip", "link", "set", container_veth,
                "netns", str(os.getpid())
            ], check=True, capture_output=True)
            
            # Bring up host end
            subprocess.run([
                "ip", "link", "set", host_veth, "up"
            ], check=True, capture_output=True)
            
            logger.info(f"Created veth pair: {host_veth} <-> {container_veth}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create veth pair: {e}")
            raise
            
        return host_veth, container_veth
        
    def configure_network_interface(self, ifname: str, ip_addr: str, gateway: str):
        """Configure network interface in current namespace"""
        import subprocess
        
        try:
            # Set IP address
            subprocess.run([
                "ip", "addr", "add", ip_addr, "dev", ifname
            ], check=True, capture_output=True)
            
            # Bring up interface
            subprocess.run([
                "ip", "link", "set", ifname, "up"
            ], check=True, capture_output=True)
            
            # Bring up loopback
            subprocess.run([
                "ip", "link", "set", "lo", "up"
            ], check=True, capture_output=True)
            
            # Add default route
            if gateway:
                subprocess.run([
                    "ip", "route", "add", "default", "via", gateway
                ], check=True, capture_output=True)
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure network: {e}")
            raise
            
    def setup_uts_namespace(self, hostname: str):
        """Setup UTS namespace with hostname"""
        # Create UTS namespace
        ns_path = self.create_namespace('uts')
        
        # Set hostname
        ret = self.libc.sethostname(hostname.encode(), len(hostname))
        if ret < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"sethostname failed: {os.strerror(errno)}")
            
        return ns_path
        
    def setup_user_namespace(self, uid_map: str, gid_map: str):
        """Setup user namespace with UID/GID mapping"""
        # Create user namespace
        ns_path = self.create_namespace('user')
        
        # Write UID map
        with open("/proc/self/uid_map", "w") as f:
            f.write(uid_map)
            
        # Disable setgroups (required before setting gid_map)
        with open("/proc/self/setgroups", "w") as f:
            f.write("deny")
            
        # Write GID map
        with open("/proc/self/gid_map", "w") as f:
            f.write(gid_map)
            
        return ns_path
        
    # Mount flags
    MS_RDONLY = 1
    MS_NOSUID = 2
    MS_NODEV = 4
    MS_NOEXEC = 8
    MS_SYNCHRONOUS = 16
    MS_REMOUNT = 32
    MS_MANDLOCK = 64
    MS_DIRSYNC = 128
    MS_NOATIME = 1024
    MS_NODIRATIME = 2048
    MS_BIND = 4096
    MS_MOVE = 8192
    MS_REC = 16384
    MS_SILENT = 32768
    MS_POSIXACL = (1 << 16)
    MS_UNBINDABLE = (1 << 17)
    MS_PRIVATE = (1 << 18)
    MS_SLAVE = (1 << 19)
    MS_SHARED = (1 << 20)
    MS_RELATIME = (1 << 21)
    MS_KERNMOUNT = (1 << 22)
    MS_I_VERSION = (1 << 23)
    MS_STRICTATIME = (1 << 24)
    MS_LAZYTIME = (1 << 25)
    
    # Umount flags
    MNT_FORCE = 1
    MNT_DETACH = 2
    MNT_EXPIRE = 4
    UMOUNT_NOFOLLOW = 8
    
    def _mount(self, source: Optional[str], target: str, fstype: Optional[str],
              flags: int, data: Optional[str]):
        """Wrapper for mount system call"""
        source_bytes = source.encode() if source else None
        target_bytes = target.encode()
        fstype_bytes = fstype.encode() if fstype else None
        data_bytes = data.encode() if data else None
        
        ret = self.libc.mount(source_bytes, target_bytes, fstype_bytes, flags, data_bytes)
        if ret < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"mount failed: {os.strerror(errno)}")
            
    def _umount(self, target: str, flags: int = 0):
        """Wrapper for umount2 system call"""
        ret = self.libc.umount2(target.encode(), flags)
        if ret < 0:
            errno = ctypes.get_errno()
            raise OSError(errno, f"umount failed: {os.strerror(errno)}")


# Global namespace manager
_namespace_manager = None

def get_namespace_manager() -> NamespaceManager:
    """Get global namespace manager instance"""
    global _namespace_manager
    if _namespace_manager is None:
        _namespace_manager = NamespaceManager()
    return _namespace_manager
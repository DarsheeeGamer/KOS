"""
KOS InitRAMFS - Initial RAM Filesystem
Similar to Linux initrd/initramfs, provides early userspace
"""

import os
import tarfile
import io
from typing import Dict, List, Optional

class KOSInitRAMFS:
    """
    Initial RAM Filesystem for early boot
    Contains essential binaries and configuration for system startup
    """
    
    def __init__(self):
        self.image_path = None
        self.contents = {}  # Path -> (content, mode, uid, gid)
        self._create_minimal_system()
        
    def _create_minimal_system(self):
        """Create a minimal system structure"""
        # Essential directories
        self._add_directory('/bin', 0o755)
        self._add_directory('/sbin', 0o755)
        self._add_directory('/etc', 0o755)
        self._add_directory('/dev', 0o755)
        self._add_directory('/proc', 0o555)
        self._add_directory('/sys', 0o555)
        self._add_directory('/tmp', 0o1777)
        self._add_directory('/var', 0o755)
        self._add_directory('/var/run', 0o755)
        self._add_directory('/var/log', 0o755)
        
        # Essential device nodes (will be created by devfs)
        self._add_device('/dev/null', 'c', 1, 3, 0o666)
        self._add_device('/dev/zero', 'c', 1, 5, 0o666)
        self._add_device('/dev/random', 'c', 1, 8, 0o666)
        self._add_device('/dev/urandom', 'c', 1, 9, 0o666)
        self._add_device('/dev/console', 'c', 5, 1, 0o600)
        self._add_device('/dev/tty', 'c', 5, 0, 0o666)
        
        # Essential configuration files
        self._add_file('/etc/passwd', self._create_passwd(), 0o644)
        self._add_file('/etc/group', self._create_group(), 0o644)
        self._add_file('/etc/shadow', self._create_shadow(), 0o600)
        self._add_file('/etc/hostname', b'kos-system\n', 0o644)
        self._add_file('/etc/hosts', self._create_hosts(), 0o644)
        self._add_file('/etc/fstab', self._create_fstab(), 0o644)
        self._add_file('/etc/inittab', self._create_inittab(), 0o644)
        
        # Init script
        self._add_file('/sbin/init', self._create_init_script(), 0o755)
        
        # Essential binaries (shells, basic commands)
        self._add_shell_commands()
        
    def _create_passwd(self) -> bytes:
        """Create /etc/passwd file"""
        return b"""root:x:0:0:root:/root:/bin/sh
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
nobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin
"""

    def _create_group(self) -> bytes:
        """Create /etc/group file"""
        return b"""root:x:0:
daemon:x:1:
bin:x:2:
sys:x:3:
adm:x:4:
tty:x:5:
disk:x:6:
wheel:x:10:
users:x:100:
nogroup:x:65534:
"""

    def _create_shadow(self) -> bytes:
        """Create /etc/shadow file"""
        # Password is 'kos' (hashed)
        return b"""root:$1$kos$7QJxk8fXwG5gV4Yt3LFQK/:19000:0:99999:7:::
daemon:*:19000:0:99999:7:::
bin:*:19000:0:99999:7:::
sys:*:19000:0:99999:7:::
nobody:*:19000:0:99999:7:::
"""

    def _create_hosts(self) -> bytes:
        """Create /etc/hosts file"""
        return b"""127.0.0.1       localhost
::1             localhost ip6-localhost ip6-loopback
"""

    def _create_fstab(self) -> bytes:
        """Create /etc/fstab file"""
        return b"""# <file system> <mount point>   <type>  <options>       <dump>  <pass>
proc            /proc           proc    defaults        0       0
sysfs           /sys            sysfs   defaults        0       0
devfs           /dev            devfs   defaults        0       0
tmpfs           /tmp            tmpfs   defaults        0       0
"""

    def _create_inittab(self) -> bytes:
        """Create /etc/inittab file"""
        return b"""# /etc/inittab: init(8) configuration.

# Default runlevel
id:5:initdefault:

# System initialization
si::sysinit:/etc/init.d/rcS

# Runlevels
l0:0:wait:/etc/init.d/rc 0
l1:1:wait:/etc/init.d/rc 1
l2:2:wait:/etc/init.d/rc 2
l3:3:wait:/etc/init.d/rc 3
l4:4:wait:/etc/init.d/rc 4
l5:5:wait:/etc/init.d/rc 5
l6:6:wait:/etc/init.d/rc 6

# Console
1:2345:respawn:/sbin/getty 38400 tty1
"""

    def _create_init_script(self) -> bytes:
        """Create a simple init script"""
        return b"""#!/bin/sh
# KOS Init Script

echo "Starting KOS init..."

# Mount essential filesystems
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devfs none /dev

# Set hostname
hostname -F /etc/hostname

# Start system logger
#syslogd

# Start services
echo "Starting services..."

# Start shell on console
echo "Starting console shell..."
exec /bin/sh
"""

    def _add_shell_commands(self):
        """Add basic shell commands"""
        # These would be actual binaries in a real system
        # For VOS, we'll add markers that the shell can recognize
        
        commands = ['sh', 'ls', 'cat', 'echo', 'mkdir', 'rm', 'cp', 'mv', 
                   'mount', 'umount', 'ps', 'kill', 'chmod', 'chown']
        
        for cmd in commands:
            # Simple shell script that calls into KOS
            content = f"""#!/bin/sh
# KOS {cmd} command
exec /usr/lib/kos/commands/{cmd} "$@"
""".encode()
            self._add_file(f'/bin/{cmd}', content, 0o755)
            
    def _add_file(self, path: str, content: bytes, mode: int, uid: int = 0, gid: int = 0):
        """Add a file to the initramfs"""
        self.contents[path] = {
            'type': 'file',
            'content': content,
            'mode': mode,
            'uid': uid,
            'gid': gid
        }
        
    def _add_directory(self, path: str, mode: int, uid: int = 0, gid: int = 0):
        """Add a directory to the initramfs"""
        self.contents[path] = {
            'type': 'dir',
            'mode': mode,
            'uid': uid,
            'gid': gid
        }
        
    def _add_device(self, path: str, dev_type: str, major: int, minor: int, 
                   mode: int, uid: int = 0, gid: int = 0):
        """Add a device node to the initramfs"""
        self.contents[path] = {
            'type': 'device',
            'dev_type': dev_type,  # 'c' for char, 'b' for block
            'major': major,
            'minor': minor,
            'mode': mode,
            'uid': uid,
            'gid': gid
        }
        
    def _add_symlink(self, path: str, target: str, uid: int = 0, gid: int = 0):
        """Add a symbolic link to the initramfs"""
        self.contents[path] = {
            'type': 'symlink',
            'target': target,
            'uid': uid,
            'gid': gid
        }
        
    def extract_to(self, vfs: 'KOSVirtualFilesystem', target_dir: str = '/'):
        """Extract initramfs contents to VFS"""
        # Sort paths to ensure parent directories are created first
        paths = sorted(self.contents.keys())
        
        for path in paths:
            entry = self.contents[path]
            full_path = os.path.join(target_dir, path.lstrip('/'))
            
            if entry['type'] == 'dir':
                vfs.mkdir(full_path, entry['mode'])
                vfs.chown(full_path, entry['uid'], entry['gid'])
                
            elif entry['type'] == 'file':
                # Create parent directory if needed
                parent = os.path.dirname(full_path)
                if not vfs.exists(parent):
                    vfs.makedirs(parent)
                    
                # Write file
                vfs.create_file(full_path, entry['content'])
                vfs.chmod(full_path, entry['mode'])
                vfs.chown(full_path, entry['uid'], entry['gid'])
                
            elif entry['type'] == 'symlink':
                vfs.symlink(entry['target'], full_path)
                vfs.lchown(full_path, entry['uid'], entry['gid'])
                
            elif entry['type'] == 'device':
                # Device nodes are typically created by devfs
                # Just store the information for now
                pass
                
    def create_archive(self, output_path: str):
        """Create a tar.gz archive of the initramfs"""
        with tarfile.open(output_path, 'w:gz') as tar:
            for path, entry in sorted(self.contents.items()):
                info = tarfile.TarInfo(name=path)
                
                if entry['type'] == 'dir':
                    info.type = tarfile.DIRTYPE
                    info.mode = entry['mode']
                    tar.addfile(info)
                    
                elif entry['type'] == 'file':
                    info.type = tarfile.REGTYPE
                    info.mode = entry['mode']
                    info.size = len(entry['content'])
                    tar.addfile(info, io.BytesIO(entry['content']))
                    
                elif entry['type'] == 'symlink':
                    info.type = tarfile.SYMTYPE
                    info.linkname = entry['target']
                    tar.addfile(info)
                    
                info.uid = entry.get('uid', 0)
                info.gid = entry.get('gid', 0)
                
    def load_from_archive(self, archive_path: str):
        """Load initramfs from a tar.gz archive"""
        self.contents.clear()
        
        with tarfile.open(archive_path, 'r:gz') as tar:
            for member in tar.getmembers():
                if member.isdir():
                    self._add_directory(member.name, member.mode, 
                                      member.uid, member.gid)
                elif member.isfile():
                    content = tar.extractfile(member).read()
                    self._add_file(member.name, content, member.mode,
                                 member.uid, member.gid)
                elif member.issym():
                    self._add_symlink(member.name, member.linkname,
                                    member.uid, member.gid)
                                    
    def list_contents(self) -> List[str]:
        """List all files in the initramfs"""
        return sorted(self.contents.keys())
        
    def get_size(self) -> int:
        """Get total size of initramfs contents"""
        total = 0
        for entry in self.contents.values():
            if entry['type'] == 'file':
                total += len(entry['content'])
        return total
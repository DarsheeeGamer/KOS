"""
KOS VFS Initialization
======================
Initializes the VFS with essential system files, directories, and applications
"""

import os
import json
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger('KOS.vfs.init')

class VFSInitializer:
    """Initialize VFS with complete filesystem structure"""
    
    def __init__(self, vfs):
        """Initialize VFS initializer
        
        Args:
            vfs: VirtualFileSystem instance
        """
        self.vfs = vfs
        self.initialized_flag = "/.vfs_initialized"
        
    def is_initialized(self) -> bool:
        """Check if VFS has been initialized"""
        return self.vfs.exists(self.initialized_flag)
    
    def initialize(self, force: bool = False):
        """Initialize the VFS with complete filesystem structure
        
        Args:
            force: Force reinitialization even if already done
        """
        if self.is_initialized() and not force:
            logger.info("VFS already initialized")
            return
        
        logger.info("Initializing VFS filesystem structure...")
        
        # Create essential directories
        self._create_directories()
        
        # Create system files
        self._create_system_files()
        
        # Create binary directories and programs
        self._create_programs()
        
        # Create user home directories
        self._create_user_homes()
        
        # Create application data
        self._create_applications()
        
        # Create sample data files
        self._create_sample_data()
        
        # Mark as initialized
        self._set_initialized()
        
        logger.info("VFS initialization complete")
    
    def _create_directories(self):
        """Create essential directory structure"""
        # Use root context for initialization
        import os
        original_uid = os.getuid()
        original_gid = os.getgid()
        
        directories = [
            # Root level
            "/bin",          # Essential command binaries
            "/boot",         # Boot loader files
            "/dev",          # Device files
            "/etc",          # System configuration
            "/home",         # User home directories
            "/lib",          # Essential shared libraries
            "/media",        # Mount points for removable media
            "/mnt",          # Temporary mount points
            "/opt",          # Optional software
            "/proc",         # Process information
            "/root",         # Root user home
            "/run",          # Runtime data
            "/sbin",         # System binaries
            "/srv",          # Service data
            "/sys",          # System information
            "/tmp",          # Temporary files
            "/usr",          # User programs
            "/var",          # Variable data
            
            # /etc subdirectories
            "/etc/init.d",
            "/etc/kos",
            "/etc/network",
            "/etc/security",
            "/etc/systemd",
            "/etc/X11",
            
            # /usr subdirectories
            "/usr/bin",
            "/usr/sbin",
            "/usr/lib",
            "/usr/local",
            "/usr/local/bin",
            "/usr/local/lib",
            "/usr/share",
            "/usr/share/doc",
            "/usr/share/man",
            "/usr/share/applications",
            "/usr/include",
            "/usr/src",
            
            # /var subdirectories
            "/var/cache",
            "/var/cache/kos",
            "/var/cache/pip",
            "/var/lib",
            "/var/lib/kos",
            "/var/lib/kos/packages",
            "/var/lib/kos/apps",
            "/var/lock",
            "/var/log",
            "/var/mail",
            "/var/opt",
            "/var/run",
            "/var/spool",
            "/var/tmp",
            "/var/www",
            
            # /home subdirectories
            "/home/user",
            "/home/user/Desktop",
            "/home/user/Documents",
            "/home/user/Downloads",
            "/home/user/Music",
            "/home/user/Pictures",
            "/home/user/Videos",
            "/home/user/.config",
            "/home/user/.local",
            "/home/user/.cache",
            
            # /opt subdirectories
            "/opt/kos",
            "/opt/kos/apps",
            "/opt/kos/games",
            "/opt/kos/tools",
        ]
        
        for directory in directories:
            try:
                if not self.vfs.exists(directory):
                    # Try with root permissions (uid=0, gid=0)
                    try:
                        self.vfs.mkdir(directory, 0o755, uid=0, gid=0)
                        logger.debug(f"Created directory: {directory}")
                    except:
                        # Fallback to regular mkdir
                        self.vfs.mkdir(directory, 0o755)
                        logger.debug(f"Created directory: {directory}")
            except Exception as e:
                logger.warning(f"Could not create {directory}: {e}")
    
    def _create_system_files(self):
        """Create essential system configuration files"""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        system_files = {
            # System information
            "/etc/hostname": b"kos\n",
            "/etc/hosts": b"""127.0.0.1    localhost
127.0.1.1    kos
::1          localhost ip6-localhost ip6-loopback
""",
            
            # OS release information
            "/etc/os-release": b"""NAME="KOS"
VERSION="1.0"
ID=kos
ID_LIKE=unix
PRETTY_NAME="Kaede OS 1.0"
VERSION_ID="1.0"
HOME_URL="https://github.com/DarsheeeGamer/KOS"
""",
            
            # User and group files
            "/etc/passwd": b"""root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
sys:x:3:3:sys:/dev:/usr/sbin/nologin
user:x:1000:1000:User:/home/user:/bin/bash
""",
            
            "/etc/group": b"""root:x:0:
daemon:x:1:
bin:x:2:
sys:x:3:
adm:x:4:
tty:x:5:
disk:x:6:
wheel:x:10:root,user
users:x:100:
user:x:1000:
""",
            
            "/etc/shadow": b"""root:*:19000:0:99999:7:::
daemon:*:19000:0:99999:7:::
bin:*:19000:0:99999:7:::
sys:*:19000:0:99999:7:::
user:*:19000:0:99999:7:::
""",
            
            # Shell configuration
            "/etc/profile": b"""# /etc/profile: system-wide profile for KOS

export PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
export PS1='\\u@\\h:\\w\\$ '
export EDITOR=nano
export TERM=xterm-256color

# KOS specific
export KOS_HOME=/opt/kos
export KOS_VERSION=1.0
""",
            
            "/etc/bash.bashrc": b"""# System-wide bashrc for KOS

# Enable color support
alias ls='ls --color=auto'
alias grep='grep --color=auto'
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Safety aliases
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'
""",
            
            # System configuration
            "/etc/fstab": b"""# /etc/fstab: static file system information
# <file system> <mount point>   <type>  <options>       <dump>  <pass>
/dev/vfs        /               kosfs   defaults        0       1
proc            /proc           proc    defaults        0       0
sysfs           /sys            sysfs   defaults        0       0
devpts          /dev/pts        devpts  defaults        0       0
tmpfs           /tmp            tmpfs   defaults        0       0
""",
            
            # Network configuration
            "/etc/resolv.conf": b"""nameserver 8.8.8.8
nameserver 8.8.4.4
""",
            
            # KOS specific configuration
            "/etc/kos/config.json": json.dumps({
                "version": "1.0",
                "system": {
                    "name": "KOS",
                    "kernel": "kos-kernel-1.0",
                    "architecture": "x86_64"
                },
                "features": {
                    "vfs": True,
                    "networking": True,
                    "containers": True,
                    "security": True
                },
                "paths": {
                    "apps": "/opt/kos/apps",
                    "data": "/var/lib/kos",
                    "logs": "/var/log/kos",
                    "cache": "/var/cache/kos"
                }
            }, indent=2).encode(),
            
            # Message of the day
            "/etc/motd": b"""
Welcome to Kaede OS (KOS) v1.0
===============================

 * Documentation:  https://github.com/DarsheeeGamer/KOS
 * Support:        https://github.com/DarsheeeGamer/KOS/issues
 
Type 'help' for available commands.
""",
        }
        
        flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
        
        for filepath, content in system_files.items():
            try:
                # Ensure parent directory exists
                parent = os.path.dirname(filepath)
                if not self.vfs.exists(parent):
                    self.vfs.mkdir(parent, 0o755)
                
                # Write file with root permissions
                try:
                    with self.vfs.open(filepath, flags, 0o644, uid=0, gid=0) as f:
                        f.write(content)
                    logger.debug(f"Created system file: {filepath}")
                except:
                    # Fallback
                    with self.vfs.open(filepath, flags, 0o644) as f:
                        f.write(content)
                    logger.debug(f"Created system file: {filepath}")
            except Exception as e:
                logger.warning(f"Could not create {filepath}: {e}")
    
    def _create_programs(self):
        """Create program files in /bin, /usr/bin, etc."""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        # Essential commands in /bin
        bin_programs = {
            "/bin/ls": b"""#!/usr/bin/env python3
# KOS ls command
import os, sys
print("ls: listing directory contents")
""",
            "/bin/cat": b"""#!/usr/bin/env python3
# KOS cat command
import sys
print("cat: concatenate files")
""",
            "/bin/echo": b"""#!/usr/bin/env python3
# KOS echo command
import sys
print(' '.join(sys.argv[1:]))
""",
            "/bin/pwd": b"""#!/usr/bin/env python3
# KOS pwd command
import os
print(os.getcwd())
""",
            "/bin/mkdir": b"""#!/usr/bin/env python3
# KOS mkdir command
import os, sys
if len(sys.argv) > 1:
    os.makedirs(sys.argv[1], exist_ok=True)
""",
            "/bin/rm": b"""#!/usr/bin/env python3
# KOS rm command
import os, sys
print("rm: remove files")
""",
            "/bin/cp": b"""#!/usr/bin/env python3
# KOS cp command
print("cp: copy files")
""",
            "/bin/mv": b"""#!/usr/bin/env python3
# KOS mv command
print("mv: move files")
""",
            "/bin/bash": b"""#!/usr/bin/env python3
# KOS bash shell
print("KOS Shell v1.0")
""",
            "/bin/sh": b"""#!/usr/bin/env python3
# KOS sh shell
print("KOS Shell v1.0")
""",
        }
        
        # User programs in /usr/bin
        usr_programs = {
            "/usr/bin/python3": b"""#!/usr/bin/env python3
# KOS Python interpreter
print("Python 3.x for KOS")
""",
            "/usr/bin/git": b"""#!/usr/bin/env python3
# KOS git
print("git version 2.x for KOS")
""",
            "/usr/bin/nano": b"""#!/usr/bin/env python3
# KOS nano editor
print("nano editor for KOS")
""",
            "/usr/bin/vim": b"""#!/usr/bin/env python3
# KOS vim editor
print("vim editor for KOS")
""",
            "/usr/bin/wget": b"""#!/usr/bin/env python3
# KOS wget
print("wget: download files")
""",
            "/usr/bin/curl": b"""#!/usr/bin/env python3
# KOS curl
print("curl: transfer data")
""",
            "/usr/bin/top": b"""#!/usr/bin/env python3
# KOS top
print("top: process viewer")
""",
            "/usr/bin/htop": b"""#!/usr/bin/env python3
# KOS htop
print("htop: interactive process viewer")
""",
            "/usr/bin/tree": b"""#!/usr/bin/env python3
# KOS tree
print("tree: directory tree viewer")
""",
        }
        
        # System binaries in /sbin
        sbin_programs = {
            "/sbin/init": b"""#!/usr/bin/env python3
# KOS init system
print("KOS init v1.0")
""",
            "/sbin/reboot": b"""#!/usr/bin/env python3
# KOS reboot
print("Rebooting KOS...")
""",
            "/sbin/shutdown": b"""#!/usr/bin/env python3
# KOS shutdown
print("Shutting down KOS...")
""",
            "/sbin/mount": b"""#!/usr/bin/env python3
# KOS mount
print("mount: mount filesystems")
""",
            "/sbin/umount": b"""#!/usr/bin/env python3
# KOS umount
print("umount: unmount filesystems")
""",
        }
        
        flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
        
        # Write all programs
        all_programs = {**bin_programs, **usr_programs, **sbin_programs}
        
        for filepath, content in all_programs.items():
            try:
                # Ensure parent directory exists
                parent = os.path.dirname(filepath)
                if not self.vfs.exists(parent):
                    self._create_directory_recursive(parent)
                
                # Write with execute permissions
                try:
                    with self.vfs.open(filepath, flags, 0o755, uid=0, gid=0) as f:
                        f.write(content)
                    logger.debug(f"Created program: {filepath}")
                except:
                    with self.vfs.open(filepath, flags, 0o755) as f:
                        f.write(content)
                    logger.debug(f"Created program: {filepath}")
            except Exception as e:
                logger.warning(f"Could not create {filepath}: {e}")
    
    def _create_user_homes(self):
        """Create user home directories with config files"""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        user_files = {
            # User bashrc
            "/home/user/.bashrc": b"""# User bashrc for KOS

# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# User specific aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias kos='python3 /opt/kos/main.py'

# Set prompt
export PS1='\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '
""",
            
            # User profile
            "/home/user/.profile": b"""# User profile for KOS

# Add user bin to PATH
export PATH="$HOME/.local/bin:$PATH"

# KOS user settings
export EDITOR=nano
export BROWSER=firefox
""",
            
            # Desktop entries
            "/home/user/Desktop/README.txt": b"""Welcome to KOS Desktop!

This is your desktop directory. You can place shortcuts and files here.
""",
            
            # Documents
            "/home/user/Documents/welcome.txt": b"""Welcome to Kaede OS!

This is your Documents folder. Store your personal documents here.

Getting Started:
- Type 'help' for available commands
- Use 'kpm install <package>' to install packages
- Explore the system with 'ls' and 'cd' commands

Enjoy using KOS!
""",
            
            "/home/user/Documents/notes.txt": b"""My Notes
========

- KOS is a virtual operating system
- Everything is stored in the VFS (Virtual File System)
- The VFS is contained in the kaede.kdsk file
""",
            
            # Sample code
            "/home/user/Documents/hello.py": b"""#!/usr/bin/env python3
# Sample Python script for KOS

def main():
    print("Hello from KOS!")
    print("This script is running inside the Virtual File System")
    
    # Get system info
    import os
    print(f"Current directory: {os.getcwd()}")
    print(f"User: {os.environ.get('USER', 'unknown')}")

if __name__ == "__main__":
    main()
""",
            
            # Config files
            "/home/user/.config/kos/settings.json": json.dumps({
                "theme": "dark",
                "terminal": {
                    "colors": "256",
                    "font": "monospace",
                    "size": 12
                },
                "editor": {
                    "default": "nano",
                    "tabs": 4,
                    "wrap": True
                }
            }, indent=2).encode(),
        }
        
        flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
        
        for filepath, content in user_files.items():
            try:
                # Ensure parent directory exists
                parent = os.path.dirname(filepath)
                if not self.vfs.exists(parent):
                    self.vfs.mkdir(parent, 0o755)
                
                with self.vfs.open(filepath, flags, 0o644) as f:
                    f.write(content)
                logger.debug(f"Created user file: {filepath}")
            except Exception as e:
                logger.warning(f"Could not create {filepath}: {e}")
    
    def _create_applications(self):
        """Create installed applications in /opt/kos/apps"""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        apps = {
            # Text Editor App
            "/opt/kos/apps/editor/editor.py": b"""#!/usr/bin/env python3
# KOS Text Editor Application

class TextEditor:
    def __init__(self):
        self.name = "KOS Text Editor"
        self.version = "1.0"
    
    def run(self):
        print(f"{self.name} v{self.version}")
        print("Simple text editor for KOS")

if __name__ == "__main__":
    editor = TextEditor()
    editor.run()
""",
            
            "/opt/kos/apps/editor/README.md": b"""# KOS Text Editor

A simple text editor for KOS.

## Features
- Create and edit text files
- Syntax highlighting
- Search and replace

## Usage
Run `editor <filename>` to start editing.
""",
            
            # File Manager App
            "/opt/kos/apps/filemanager/fm.py": b"""#!/usr/bin/env python3
# KOS File Manager

class FileManager:
    def __init__(self):
        self.name = "KOS File Manager"
        self.version = "1.0"
    
    def run(self):
        print(f"{self.name} v{self.version}")
        print("Browse and manage files in KOS")

if __name__ == "__main__":
    fm = FileManager()
    fm.run()
""",
            
            # Calculator App
            "/opt/kos/apps/calculator/calc.py": b"""#!/usr/bin/env python3
# KOS Calculator

def calculator():
    print("KOS Calculator v1.0")
    print("Enter expressions to calculate (or 'quit' to exit)")
    
    while True:
        expr = input("> ")
        if expr.lower() == 'quit':
            break
        try:
            result = eval(expr)
            print(f"= {result}")
        except:
            print("Invalid expression")

if __name__ == "__main__":
    calculator()
""",
            
            # System Monitor App
            "/opt/kos/apps/sysmon/monitor.py": b"""#!/usr/bin/env python3
# KOS System Monitor

import os
import json

class SystemMonitor:
    def __init__(self):
        self.name = "KOS System Monitor"
        self.version = "1.0"
    
    def get_stats(self):
        return {
            "cpu": "0%",
            "memory": "128MB / 512MB",
            "disk": "100MB / 1GB",
            "processes": 42
        }
    
    def run(self):
        print(f"{self.name} v{self.version}")
        stats = self.get_stats()
        for key, value in stats.items():
            print(f"{key.upper()}: {value}")

if __name__ == "__main__":
    monitor = SystemMonitor()
    monitor.run()
""",
            
            # Terminal App
            "/opt/kos/apps/terminal/term.py": b"""#!/usr/bin/env python3
# KOS Terminal Emulator

class Terminal:
    def __init__(self):
        self.name = "KOS Terminal"
        self.version = "1.0"
    
    def run(self):
        print(f"{self.name} v{self.version}")
        print("Type 'exit' to quit")
        
        while True:
            cmd = input("$ ")
            if cmd == 'exit':
                break
            print(f"Executing: {cmd}")

if __name__ == "__main__":
    term = Terminal()
    term.run()
""",
        }
        
        flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
        
        for filepath, content in apps.items():
            try:
                # Ensure parent directory exists
                parent = os.path.dirname(filepath)
                if not self.vfs.exists(parent):
                    self._create_directory_recursive(parent)
                
                with self.vfs.open(filepath, flags, 0o755 if filepath.endswith('.py') else 0o644) as f:
                    f.write(content)
                logger.debug(f"Created application: {filepath}")
            except Exception as e:
                logger.warning(f"Could not create {filepath}: {e}")
    
    def _create_sample_data(self):
        """Create sample data files"""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        data_files = {
            # Log files
            "/var/log/system.log": b"""[2024-01-01 00:00:00] System boot
[2024-01-01 00:00:01] VFS initialized
[2024-01-01 00:00:02] Network services started
[2024-01-01 00:00:03] KOS ready
""",
            
            "/var/log/kos.log": b"""KOS System Log
==============
System initialized successfully
All services running normally
""",
            
            # Cache files
            "/var/cache/kos/packages.json": json.dumps({
                "packages": [
                    {"name": "editor", "version": "1.0", "installed": True},
                    {"name": "calculator", "version": "1.0", "installed": True},
                    {"name": "sysmon", "version": "1.0", "installed": True}
                ]
            }, indent=2).encode(),
            
            # Temp files
            "/tmp/session.lock": b"PID: 1234\n",
            
            # Web content
            "/var/www/index.html": b"""<!DOCTYPE html>
<html>
<head>
    <title>KOS Web Server</title>
</head>
<body>
    <h1>Welcome to KOS</h1>
    <p>This is the default web page for the KOS web server.</p>
</body>
</html>
""",
        }
        
        flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
        
        for filepath, content in data_files.items():
            try:
                # Ensure parent directory exists
                parent = os.path.dirname(filepath)
                if not self.vfs.exists(parent):
                    self._create_directory_recursive(parent)
                
                with self.vfs.open(filepath, flags, 0o644) as f:
                    f.write(content)
                logger.debug(f"Created data file: {filepath}")
            except Exception as e:
                logger.warning(f"Could not create {filepath}: {e}")
    
    def _create_directory_recursive(self, path: str):
        """Recursively create directories"""
        if not path or path == '/':
            return
        
        parts = path.strip('/').split('/')
        current = ''
        
        for part in parts:
            current = f"/{part}" if not current else f"{current}/{part}"
            
            if not self.vfs.exists(current):
                try:
                    # Try with root permissions first
                    self.vfs.mkdir(current, 0o755, uid=0, gid=0)
                except:
                    try:
                        # Fallback to regular mkdir
                        self.vfs.mkdir(current, 0o755)
                    except:
                        pass
    
    def _set_initialized(self):
        """Mark VFS as initialized"""
        import os
        VFS_O_WRONLY = os.O_WRONLY
        VFS_O_CREAT = os.O_CREAT
        VFS_O_TRUNC = os.O_TRUNC
        
        try:
            flags = VFS_O_WRONLY | VFS_O_CREAT | VFS_O_TRUNC
            with self.vfs.open(self.initialized_flag, flags, 0o644) as f:
                data = json.dumps({
                    "initialized": True,
                    "timestamp": time.time(),
                    "version": "1.0"
                })
                f.write(data.encode())
            logger.info("VFS marked as initialized")
        except Exception as e:
            logger.error(f"Could not set initialized flag: {e}")

def initialize_vfs(vfs, force: bool = False):
    """Initialize VFS with complete filesystem
    
    Args:
        vfs: VirtualFileSystem instance
        force: Force reinitialization
    """
    # Check if we should use root VFS for initialization
    if not hasattr(vfs, '_initialized_with_root'):
        try:
            # Try to use RootVFS for initialization
            from kos.vfs.root_vfs import get_root_vfs
            root_vfs = get_root_vfs()
            initializer = VFSInitializer(root_vfs)
            initializer.initialize(force)
            vfs._initialized_with_root = True
            return
        except:
            pass
    
    # Fallback to regular VFS
    initializer = VFSInitializer(vfs)
    initializer.initialize(force)
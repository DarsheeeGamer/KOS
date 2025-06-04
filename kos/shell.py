"""
Enhanced shell implementation with advanced features and improved performance
"""
import cmd
import shlex
import os
import signal
import re
import logging
import sys
import time
import psutil # Added import for system information
import subprocess
import socket
import threading
import json
import hashlib
import mimetypes
import gzip
import tarfile
import zipfile
import bz2
import platform
import urllib.request
import urllib.parse
import stat
import fnmatch
import collections
from pathlib import Path
from kos.internal import system_manager, register_exit_handler, exit as kos_exit
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
    from rich.panel import Panel
    from rich.syntax import Syntax
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = Table = Progress = SpinnerColumn = TimeElapsedColumn = Panel = Syntax = None
    logging.warning("Rich library not available, falling back to basic output")

from kos.filesystem.base import FileSystem
from kos.process.manager import ProcessManager
from kos.package_manager import KpmManager
from kos.exceptions import KOSError, FileSystemError
from kos.user_system import UserSystem

logger = logging.getLogger('KOS.shell')

class KaedeShell(cmd.Cmd):
    """Enhanced KOS shell with comprehensive Linux/POSIX commands"""
    HISTORY_FILE = ".kos_history"
    MAX_HISTORY = 1000
    COMMAND_HELP_FILE = "command_help.json"

    def __init__(self, filesystem: FileSystem, package_manager: KpmManager, 
                 process_manager: ProcessManager, user_system: UserSystem):
        super().__init__()
        self.fs = filesystem
        self.pm = package_manager
        self.process_mgr = process_manager
        self.us = user_system
        self.history: List[str] = []
        self.console = Console() if RICH_AVAILABLE and Console else None
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._resource_cache = TTLCache(maxsize=100, ttl=1)  # Cache resource usage for 1 second
        
        # Environment variables
        self.env_vars = {
            "PATH": "/bin:/usr/bin:/usr/local/bin",
            "HOME": f"/home/{self.us.current_user}",
            "USER": self.us.current_user,
            "SHELL": "/bin/ksh",
            "TERM": "xterm-256color",
            "LANG": "en_US.UTF-8",
            "PWD": self.fs.current_path,
            "OLDPWD": self.fs.current_path,
        }
        
        # Job control
        self.jobs = {}
        self.job_counter = 0
        
        # Aliases
        self.aliases = {
            'll': 'ls -l',
            'la': 'ls -a',
            'l': 'ls -CF',
            'dir': 'ls',
            'copy': 'cp',
            'move': 'mv',
            'del': 'rm',
            'type': 'cat',
            'md': 'mkdir',
            'rd': 'rmdir'
        }
        
        self._load_history()
        self._setup_signal_handlers()

        # Enhanced command categories with descriptions
        self.command_categories = {
            "File Operations": {
                "ls": "List directory contents with enhanced formatting",
                "cd": "Change directory with path completion",
                "pwd": "Print working directory",
                "mkdir": "Create directory with permissions",
                "rmdir": "Remove empty directories",
                "touch": "Create or update file timestamps",
                "cat": "Display file contents with syntax highlighting",
                "rm": "Remove files or directories",
                "cp": "Copy files or directories",
                "mv": "Move/rename files or directories",
                "chmod": "Change file permissions",
                "chown": "Change file ownership",
                "ln": "Create links",
                "readlink": "Print symbolic link targets",
                "grep": "Search file patterns with highlighting",
                "find": "Search files with advanced criteria",
                "locate": "Find files by name",
                "tree": "Display directory structure",
                "du": "Display directory space usage",
                "file": "Determine file type",
                "stat": "Display file/filesystem status",
                "which": "Locate a command",
                "whereis": "Locate binary, source, manual",
                "basename": "Strip directory and suffix from filename",
                "dirname": "Strip filename from path"
            },
            "Process Management": {
                "ps": "Display process information",
                "top": "Interactive process viewer",
                "htop": "Enhanced process viewer",
                "kill": "Send signals to processes",
                "killall": "Kill processes by name",
                "pkill": "Kill processes by criteria",
                "pgrep": "Find processes by criteria", 
                "nice": "Change process priority",
                "renice": "Adjust process priority",
                "nohup": "Run command immune to hangups",
                "pstree": "Show process hierarchy",
                "jobs": "List background jobs",
                "fg": "Bring job to foreground",
                "bg": "Put job in background",
                "disown": "Remove job from job table"
            },
            "System Operations": {
                "whoami": "Display current user",
                "who": "Show logged in users",
                "w": "Show user activity",
                "id": "Print user and group IDs",
                "hostname": "Show/set system hostname",
                "su": "Switch user",
                "sudo": "Execute as another user",
                "useradd": "Add new user",
                "userdel": "Delete user",
                "usermod": "Modify user account",
                "passwd": "Change password",
                "groups": "Show user groups",
                "kudo": "Execute with elevated privileges",
                "clear": "Clear terminal screen",
                "reset": "Reset terminal",
                "tty": "Print terminal name",
                "stty": "Change terminal settings",
                "env": "Display/set environment variables",
                "export": "Set environment variables",
                "unset": "Unset environment variables",
                "alias": "Create command aliases",
                "unalias": "Remove command aliases",
                "history": "Command history",
                "logout": "Exit shell",
                "exit": "Exit shell"
            },
            "Text Processing": {
                "sed": "Stream editor",
                "awk": "Pattern scanning/processing",
                "head": "Output first part of files",
                "tail": "Output last part of files",
                "wc": "Print word/line/byte counts",
                "sort": "Sort lines of text files",
                "uniq": "Report/omit repeated lines",
                "cut": "Remove sections from lines",
                "tr": "Translate/delete characters",
                "diff": "Compare files line by line",
                "patch": "Apply diff files",
                "comm": "Compare sorted files line by line",
                "join": "Join lines based on common field",
                "split": "Split file into pieces",
                "csplit": "Context split",
                "fmt": "Format text",
                "fold": "Wrap text to specified width",
                "expand": "Convert tabs to spaces",
                "unexpand": "Convert spaces to tabs",
                "nl": "Number lines of files",
                "od": "Dump files in octal/hex",
                "hexdump": "Display file in hexadecimal",
                "strings": "Print printable character sequences",
                "tee": "Read from input and write to output and files"
            },
            "Archive and Compression": {
                "tar": "Archive files",
                "gzip": "Compress/decompress files", 
                "gunzip": "Decompress gzip files",
                "zip": "Package/compress files",
                "unzip": "Extract compressed files",
                "bzip2": "Block-sorting compression",
                "bunzip2": "Decompress bzip2 files",
                "xz": "LZMA compression",
                "unxz": "Decompress xz files",
                "compress": "Compress files",
                "uncompress": "Decompress files",
                "zcat": "Display compressed files",
                "ar": "Create/modify archives",
                "cpio": "Copy files to/from archives"
            },
            "System Information": {
                "uname": "Print system information",
                "uptime": "Show system uptime",
                "df": "Report disk space usage",
                "free": "Display memory usage",
                "lscpu": "Display CPU information",
                "lsblk": "List block devices",
                "lsusb": "List USB devices",
                "lspci": "List PCI devices",
                "date": "Display/set system date",
                "cal": "Display calendar",
                "sysinfo": "Show system statistics",
                "vmstat": "Virtual memory statistics",
                "iostat": "Input/output statistics",
                "sar": "System activity reporter",
                "dmesg": "Display kernel messages",
                "lsmod": "List loaded modules",
                "mount": "Mount filesystems",
                "umount": "Unmount filesystems"
            },
            "Network Tools": {
                "ping": "Test network connectivity",
                "ping6": "Test IPv6 connectivity",
                "traceroute": "Trace network route",
                "tracepath": "Trace network path",
                "netstat": "Network statistics",
                "ss": "Socket statistics",
                "lsof": "List open files",
                "wget": "Retrieve files via HTTP",
                "curl": "Transfer data via protocols",
                "ftp": "File transfer protocol",
                "sftp": "Secure file transfer",
                "scp": "Secure copy",
                "rsync": "Remote/local file sync",
                "ifconfig": "Configure network interface",
                "ip": "Show/manipulate routing",
                "route": "Show/manipulate routing table",
                "arp": "Manipulate ARP table",
                "nslookup": "Query DNS",
                "dig": "DNS lookup utility",
                "host": "DNS lookup utility"
            },
            "Text Editors": {
                "nano": "Simple text editor",
                "vim": "Vi improved editor",
                "emacs": "Emacs editor",
                "ed": "Line editor"
            },
            "Package Management": {
                "kapp": "KOS package manager",
                "apt": "Advanced package tool",
                "yum": "Yellowdog updater modified",
                "dnf": "Dandified YUM",
                "pacman": "Package manager",
                "rpm": "RPM package manager",
                "dpkg": "Debian package manager"
            },
            "Security": {
                "chmod": "Change file permissions",
                "chown": "Change file ownership",
                "chgrp": "Change group ownership",
                "umask": "Set file creation mask",
                "su": "Switch user",
                "sudo": "Execute as another user",
                "passwd": "Change password",
                "ssh": "Secure shell",
                "ssh-keygen": "Generate SSH keys",
                "gpg": "GNU privacy guard"
            },
            "Programming": {
                "kaede": "Kaede programming language",
                "python": "Python interpreter",
                "python3": "Python 3 interpreter",
                "gcc": "GNU C compiler",
                "g++": "GNU C++ compiler",
                "make": "Build automation",
                "cmake": "Cross-platform make",
                "gdb": "GNU debugger",
                "valgrind": "Memory error detector",
                "strace": "System call tracer",
                "ltrace": "Library call tracer"
            }
        }

        self.intro = self._get_intro()
        self.prompt = self._get_prompt()
        logger.info("Enhanced shell initialized with comprehensive Linux/POSIX commands")

    def get_resource_value(self, resource_dict: Dict, *keys: str) -> float:
        """Safely get nested resource values with type checking"""
        try:
            value = resource_dict
            for key in keys:
                value = value[key]
            return float(value) if isinstance(value, (int, float)) else 0.0
        except (KeyError, TypeError, ValueError):
            return 0.0

    def _get_intro(self) -> str:
        """Generate enhanced intro message with system info"""
        try:
            resources = self.process_mgr.get_system_resources()
            cpu_percent = self.get_resource_value(resources, 'cpu', 'percent')
            mem_percent = self.get_resource_value(resources, 'memory', 'virtual', 'percent')
            disk_percent = self.get_resource_value(resources, 'disk', 'usage', 'percent')

            return f"""
╔══════════════════════════════════════════════════════════╗
║                 Welcome to Kaede OS (KOS)                ║
║                                                         ║
║  System Information:                                    ║
║  - CPU Usage: {cpu_percent:.1f}%                                  ║
║  - Memory: {mem_percent:.1f}% used                              ║
║  - Disk: {disk_percent:.1f}% used                                ║
║                                                         ║
║  Type 'help' for commands, 'intro' for system info     ║
╚══════════════════════════════════════════════════════════╝
"""
        except Exception as e:
            logger.error(f"Error generating intro: {e}")
            return "Welcome to KOS. Type 'help' for commands.\n"

    def _get_prompt(self) -> str:
        """Generate enhanced shell prompt with git-like info"""
        cwd = self.fs.current_path.replace('/home/runner/workspace', '')
        if not cwd:
            cwd = "/"

        time_str = datetime.now().strftime("%H:%M")
        branch = "main"  # TODO: Implement git integration

        if self.us.current_user == "kaede":
            return f"\033[1;31m[{time_str} root@kos {cwd} ({branch})]#\033[0m "
        return f"\033[1;34m[{time_str} {self.us.current_user}@kos {cwd} ({branch})]$\033[0m "

    def _setup_signal_handlers(self):
        """Setup enhanced signal handling"""
        signal.signal(signal.SIGINT, self._handle_sigint)
        signal.signal(signal.SIGTERM, self._handle_sigterm)

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl+C)"""
        print("\n^C")
        return False

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM"""
        print("\nTerminating shell...")
        self._cleanup()
        sys.exit(0)

    def _cleanup(self):
        """Cleanup before exiting"""
        self._save_history()
        self.executor.shutdown(wait=True)

    def _load_history(self):
        """Load command history"""
        try:
            if os.path.exists(self.HISTORY_FILE):
                with open(self.HISTORY_FILE, 'r') as f:
                    self.history = f.read().splitlines()[-self.MAX_HISTORY:]
        except Exception as e:
            logger.error(f"Error loading history: {e}")

    def _save_history(self):
        """Save command history"""
        try:
            with open(self.HISTORY_FILE, 'w') as f:
                f.write('\n'.join(self.history[-self.MAX_HISTORY:]))
        except Exception as e:
            logger.error(f"Error saving history: {e}")

    def precmd(self, line):
        """Pre-process command"""
        if line.strip():
            self.history.append(line.strip())
            # Handle aliases
            parts = shlex.split(line) if line else []
            if parts and parts[0] in self.aliases:
                parts[0] = self.aliases[parts[0]]
                line = ' '.join(parts)
        return line

    def postcmd(self, stop, line):
        """Post-process command"""
        if line.strip():
            self.env_vars["OLDPWD"] = self.env_vars["PWD"]
            self.env_vars["PWD"] = self.fs.current_path
            self.prompt = self._get_prompt()
        return stop

    # FILE OPERATIONS
    def do_ls(self, arg):
        """List directory contents - ls [options] [path]"""
        args = shlex.split(arg) if arg else []
        options = {'long': False, 'all': False, 'human': False, 'time': False, 'classify': False, 'reverse': False}
        paths = []
        
        for a in args:
            if a.startswith('-'):
                if 'l' in a: options['long'] = True
                if 'a' in a: options['all'] = True
                if 'h' in a: options['human'] = True
                if 't' in a: options['time'] = True
                if 'F' in a: options['classify'] = True
                if 'r' in a: options['reverse'] = True
            else:
                paths.append(a)
        
        if not paths:
            paths = ['.']
        
        for path in paths:
            try:
                items = self.fs.list_directory(path, show_hidden=options['all'])
                if options['time']:
                    items.sort(key=lambda x: x.get('modified', 0), reverse=not options['reverse'])
                elif options['reverse']:
                    items.reverse()
                
                if options['long']:
                    self._display_long_listing(items, options['human'])
                else:
                    names = [item['name'] + ('/' if item['type'] == 'directory' else '') 
                            for item in items]
                    if options['classify']:
                        names = [self._classify_name(name, item) for name, item in zip(names, items)]
                    print('  '.join(names))
            except Exception as e:
                print(f"ls: {path}: {e}")

    def _display_long_listing(self, items, human_readable=False):
        """Display files in long format"""
        for item in items:
            mode = item.get('permissions', '----------')
            links = item.get('links', 1)
            owner = item.get('owner', 'root')
            group = item.get('group', 'root')
            size = item.get('size', 0)
            
            if human_readable:
                size_str = self._human_readable_size(size)
            else:
                size_str = str(size)
            
            mtime = datetime.fromtimestamp(item.get('modified', time.time()))
            time_str = mtime.strftime('%b %d %H:%M')
            
            name = item['name']
            if item['type'] == 'directory':
                name = f"\033[94m{name}\033[0m"
            elif item.get('executable', False):
                name = f"\033[92m{name}\033[0m"
            
            print(f"{mode} {links:3} {owner:8} {group:8} {size_str:8} {time_str} {name}")

    def _human_readable_size(self, size):
        """Convert size to human readable format"""
        for unit in ['B', 'K', 'M', 'G', 'T']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}P"

    def _classify_name(self, name, item):
        """Add classification character to filename"""
        if item['type'] == 'directory':
            return name + '/'
        elif item.get('executable', False):
            return name + '*'
        elif item.get('link', False):
            return name + '@'
        return name

    def do_cd(self, arg):
        """Change directory - cd [path]"""
        if not arg:
            arg = self.env_vars.get('HOME', '/')
        elif arg == '-':
            arg = self.env_vars.get('OLDPWD', '/')
        
        try:
            self.fs.change_directory(arg)
            self.env_vars["OLDPWD"] = self.env_vars["PWD"]
            self.env_vars["PWD"] = self.fs.current_path
        except Exception as e:
            print(f"cd: {e}")

    def do_pwd(self, arg):
        """Print working directory"""
        print(self.fs.current_path)

    def do_mkdir(self, arg):
        """Create directories - mkdir [options] directory..."""
        if not arg:
            print("mkdir: missing operand")
            return
        
        args = shlex.split(arg)
        parents = False
        mode = 0o755
        dirs = []
        
        for a in args:
            if a == '-p':
                parents = True
            elif a.startswith('-m'):
                if '=' in a:
                    mode = int(a.split('=')[1], 8)
            elif not a.startswith('-'):
                dirs.append(a)
        
        for directory in dirs:
            try:
                if parents:
                    self.fs.create_directory_recursive(directory, mode)
                else:
                    self.fs.create_directory(directory, mode)
            except Exception as e:
                print(f"mkdir: {directory}: {e}")

    def do_rmdir(self, arg):
        """Remove empty directories - rmdir directory..."""
        if not arg:
            print("rmdir: missing operand")
            return
        
        dirs = shlex.split(arg)
        for directory in dirs:
            try:
                items = self.fs.list_directory(directory)
                if items:
                    print(f"rmdir: {directory}: Directory not empty")
                else:
                    self.fs.delete_directory(directory)
            except Exception as e:
                print(f"rmdir: {directory}: {e}")

    def do_touch(self, arg):
        """Create files or update timestamps - touch file..."""
        if not arg:
            print("touch: missing file operand")
            return
        
        files = shlex.split(arg)
        current_time = time.time()
        
        for filename in files:
            try:
                if self.fs.file_exists(filename):
                    # Update timestamps
                    self.fs.set_file_times(filename, current_time, current_time)
                else:
                    # Create empty file
                    self.fs.create_file(filename, "")
            except Exception as e:
                print(f"touch: {filename}: {e}")

    def do_cat(self, arg):
        """Display file contents - cat [options] file..."""
        if not arg:
            print("cat: missing file operand")
            return
        
        args = shlex.split(arg)
        number_lines = False
        show_ends = False
        files = []
        
        for a in args:
            if a == '-n':
                number_lines = True
            elif a == '-E':
                show_ends = True
            elif not a.startswith('-'):
                files.append(a)
        
        for filename in files:
            try:
                content = self.fs.read_file(filename)
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if number_lines:
                        print(f"{i:6}\t{line}", end='')
                    else:
                        print(line, end='')
                    
                    if show_ends:
                        print('$')
                    else:
                        print()
                        
            except Exception as e:
                print(f"cat: {filename}: {e}")

    def do_rm(self, arg):
        """Remove files/directories - rm [options] file..."""
        if not arg:
            print("rm: missing operand")
            return
        
        args = shlex.split(arg)
        recursive = False
        force = False
        interactive = False
        files = []
        
        for a in args:
            if a == '-r' or a == '-R':
                recursive = True
            elif a == '-f':
                force = True
            elif a == '-i':
                interactive = True
            elif not a.startswith('-'):
                files.append(a)
        
        for filename in files:
            try:
                if interactive and not force:
                    response = input(f"rm: remove '{filename}'? (y/n) ")
                    if response.lower() not in ['y', 'yes']:
                        continue
                
                if self.fs.is_directory(filename):
                    if recursive:
                        self.fs.remove_directory_recursive(filename)
                    else:
                        print(f"rm: {filename}: is a directory")
                else:
                    self.fs.delete_file(filename)
            except Exception as e:
                if not force:
                    print(f"rm: {filename}: {e}")

    def do_cp(self, arg):
        """Copy files/directories - cp [options] source dest"""
        if not arg:
            print("cp: missing file operand")
            return
        
        args = shlex.split(arg)
        recursive = False
        preserve = False
        files = []
        
        for a in args:
            if a == '-r' or a == '-R':
                recursive = True
            elif a == '-p':
                preserve = True
            elif not a.startswith('-'):
                files.append(a)
        
        if len(files) < 2:
            print("cp: missing destination file operand")
            return
        
        source = files[0]
        dest = files[1]
        
        try:
            if self.fs.is_directory(source):
                if recursive:
                    self.fs.copy_directory_recursive(source, dest, preserve)
                else:
                    print(f"cp: {source}: is a directory (not copied)")
            else:
                self.fs.copy_file(source, dest, preserve)
        except Exception as e:
            print(f"cp: {e}")

    def do_mv(self, arg):
        """Move/rename files - mv source dest"""
        if not arg:
            print("mv: missing file operand")
            return
        
        args = shlex.split(arg)
        if len(args) < 2:
            print("mv: missing destination file operand")
            return
        
        source = args[0]
        dest = args[1]
        
        try:
            self.fs.move_file(source, dest)
        except Exception as e:
            print(f"mv: {e}")

    def do_chmod(self, arg):
        """Change file permissions - chmod mode file..."""
        if not arg:
            print("chmod: missing operand")
            return
        
        args = shlex.split(arg)
        if len(args) < 2:
            print("chmod: missing operand")
            return
        
        mode = args[0]
        files = args[1:]
        
        try:
            if mode.isdigit():
                mode_int = int(mode, 8)
            else:
                # Handle symbolic mode (simplified)
                mode_int = 0o644  # Default
            
            for filename in files:
                self.fs.set_permissions(filename, mode_int)
        except Exception as e:
            print(f"chmod: {e}")

    def do_chown(self, arg):
        """Change file ownership - chown [user][:group] file..."""
        if not arg:
            print("chown: missing operand")
            return
        
        args = shlex.split(arg)
        if len(args) < 2:
            print("chown: missing operand")
            return
        
        owner_spec = args[0]
        files = args[1:]
        
        if ':' in owner_spec:
            user, group = owner_spec.split(':', 1)
        else:
            user = owner_spec
            group = None
        
        try:
            for filename in files:
                self.fs.set_owner(filename, user, group)
        except Exception as e:
            print(f"chown: {e}")

    def do_ln(self, arg):
        """Create links - ln [options] target linkname"""
        if not arg:
            print("ln: missing file operand")
            return
        
        args = shlex.split(arg)
        symbolic = False
        files = []
        
        for a in args:
            if a == '-s':
                symbolic = True
            elif not a.startswith('-'):
                files.append(a)
        
        if len(files) < 2:
            print("ln: missing destination file operand")
            return
        
        target = files[0]
        linkname = files[1]
        
        try:
            if symbolic:
                self.fs.create_symlink(target, linkname)
            else:
                self.fs.create_hardlink(target, linkname)
        except Exception as e:
            print(f"ln: {e}")

    def do_find(self, arg):
        """Find files - find [path] [expression]"""
        args = shlex.split(arg) if arg else ['.']
        path = args[0] if args else '.'
        
        name_pattern = None
        file_type = None
        min_size = None
        max_size = None
        
        i = 1
        while i < len(args):
            if args[i] == '-name' and i + 1 < len(args):
                name_pattern = args[i + 1]
                i += 2
            elif args[i] == '-type' and i + 1 < len(args):
                file_type = args[i + 1]
                i += 2
            elif args[i] == '-size' and i + 1 < len(args):
                size_spec = args[i + 1]
                if size_spec.startswith('+'):
                    min_size = int(size_spec[1:])
                elif size_spec.startswith('-'):
                    max_size = int(size_spec[1:])
                i += 2
            else:
                i += 1
        
        try:
            results = self.fs.find_files(path, name_pattern, file_type, min_size, max_size)
            for result in results:
                print(result)
        except Exception as e:
            print(f"find: {e}")

    def do_grep(self, arg):
        """Search text patterns - grep [options] pattern [file...]"""
        if not arg:
            print("grep: missing pattern")
            return
        
        args = shlex.split(arg)
        ignore_case = False
        line_numbers = False
        recursive = False
        pattern = None
        files = []
        
        for a in args:
            if a == '-i':
                ignore_case = True
            elif a == '-n':
                line_numbers = True
            elif a == '-r' or a == '-R':
                recursive = True
            elif pattern is None:
                pattern = a
            else:
                files.append(a)
        
        if not pattern:
            print("grep: missing pattern")
            return
        
        if not files:
            files = ['-']  # stdin
        
        try:
            import re
            flags = re.IGNORECASE if ignore_case else 0
            regex = re.compile(pattern, flags)
            
            for filename in files:
                if filename == '-':
                    # Read from stdin - simplified
                    continue
                
                try:
                    if recursive and self.fs.is_directory(filename):
                        for root, dirs, filelist in self.fs.walk(filename):
                            for f in filelist:
                                full_path = self.fs.join_path(root, f)
                                self._grep_file(regex, full_path, line_numbers, len(files) > 1)
                    else:
                        self._grep_file(regex, filename, line_numbers, len(files) > 1)
                except Exception as e:
                    print(f"grep: {filename}: {e}")
        except Exception as e:
            print(f"grep: {e}")

    def _grep_file(self, regex, filename, line_numbers, show_filename):
        """Helper function to grep a single file"""
        try:
            content = self.fs.read_file(filename)
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    output = ""
                    if show_filename:
                        output += f"{filename}:"
                    if line_numbers:
                        output += f"{i}:"
                    output += line
                    print(output)
        except Exception:
            pass

    def do_head(self, arg):
        """Output first part of files - head [options] [file...]"""
        args = shlex.split(arg) if arg else []
        lines = 10
        files = []
        
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                lines = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                lines = int(args[i][1:])
                i += 1
            else:
                files.append(args[i])
                i += 1
        
        if not files:
            files = ['-']  # stdin
        
        for filename in files:
            try:
                if filename == '-':
                    continue  # stdin handling simplified
                
                content = self.fs.read_file(filename)
                file_lines = content.split('\n')
                
                if len(files) > 1:
                    print(f"==> {filename} <==")
                
                for line in file_lines[:lines]:
                    print(line)
                
                if len(files) > 1:
                    print()
            except Exception as e:
                print(f"head: {filename}: {e}")

    def do_tail(self, arg):
        """Output last part of files - tail [options] [file...]"""
        args = shlex.split(arg) if arg else []
        lines = 10
        follow = False
        files = []
        
        i = 0
        while i < len(args):
            if args[i] == '-n' and i + 1 < len(args):
                lines = int(args[i + 1])
                i += 2
            elif args[i].startswith('-') and args[i][1:].isdigit():
                lines = int(args[i][1:])
                i += 1
            elif args[i] == '-f':
                follow = True
                i += 1
            else:
                files.append(args[i])
                i += 1
        
        if not files:
            files = ['-']
        
        for filename in files:
            try:
                if filename == '-':
                    continue
                
                content = self.fs.read_file(filename)
                file_lines = content.split('\n')
                
                if len(files) > 1:
                    print(f"==> {filename} <==")
                
                start_index = max(0, len(file_lines) - lines)
                for line in file_lines[start_index:]:
                    print(line)
                
                if follow:
                    # Simplified follow mode
                    print(f"tail: following {filename} (Ctrl+C to stop)")
                    try:
                        while True:
                            time.sleep(1)
                            new_content = self.fs.read_file(filename)
                            new_lines = new_content.split('\n')
                            if len(new_lines) > len(file_lines):
                                for line in new_lines[len(file_lines):]:
                                    print(line)
                                file_lines = new_lines
                    except KeyboardInterrupt:
                        print()
                        break
                
                if len(files) > 1:
                    print()
            except Exception as e:
                print(f"tail: {filename}: {e}")

    def do_wc(self, arg):
        """Print word, line, character, and byte counts - wc [options] [file...]"""
        args = shlex.split(arg) if arg else []
        count_lines = True
        count_words = True
        count_chars = True
        count_bytes = True
        files = []
        
        # Parse options
        for a in args:
            if a == '-l':
                count_lines, count_words, count_chars, count_bytes = True, False, False, False
            elif a == '-w':
                count_lines, count_words, count_chars, count_bytes = False, True, False, False
            elif a == '-c':
                count_lines, count_words, count_chars, count_bytes = False, False, False, True
            elif a == '-m':
                count_lines, count_words, count_chars, count_bytes = False, False, True, False
            elif not a.startswith('-'):
                files.append(a)
        
        if not files:
            files = ['-']
        
        total_lines = total_words = total_chars = total_bytes = 0
        
        for filename in files:
            try:
                if filename == '-':
                    continue
                
                content = self.fs.read_file(filename)
                lines = len(content.split('\n')) if content else 0
                words = len(content.split()) if content else 0
                chars = len(content)
                bytes_count = len(content.encode('utf-8'))
                
                total_lines += lines
                total_words += words
                total_chars += chars
                total_bytes += bytes_count
                
                output = []
                if count_lines:
                    output.append(f"{lines:8}")
                if count_words:
                    output.append(f"{words:8}")
                if count_chars:
                    output.append(f"{chars:8}")
                if count_bytes and not count_chars:
                    output.append(f"{bytes_count:8}")
                output.append(f" {filename}")
                
                print("".join(output))
            except Exception as e:
                print(f"wc: {filename}: {e}")
        
        if len(files) > 1:
            output = []
            if count_lines:
                output.append(f"{total_lines:8}")
            if count_words:
                output.append(f"{total_words:8}")
            if count_chars:
                output.append(f"{total_chars:8}")
            if count_bytes and not count_chars:
                output.append(f"{total_bytes:8}")
            output.append(" total")
            print("".join(output))

    def do_sort(self, arg):
        """Sort lines of text files - sort [options] [file...]"""
        args = shlex.split(arg) if arg else []
        reverse = False
        numeric = False
        unique = False
        files = []
        
        for a in args:
            if a == '-r':
                reverse = True
            elif a == '-n':
                numeric = True
            elif a == '-u':
                unique = True
            elif not a.startswith('-'):
                files.append(a)
        
        if not files:
            files = ['-']
        
        all_lines = []
        for filename in files:
            try:
                if filename == '-':
                    continue
                
                content = self.fs.read_file(filename)
                all_lines.extend(content.split('\n'))
            except Exception as e:
                print(f"sort: {filename}: {e}")
                continue
        
        if numeric:
            try:
                all_lines.sort(key=lambda x: float(x) if x.strip() else 0, reverse=reverse)
            except ValueError:
                all_lines.sort(reverse=reverse)
        else:
            all_lines.sort(reverse=reverse)
        
        if unique:
            seen = set()
            unique_lines = []
            for line in all_lines:
                if line not in seen:
                    seen.add(line)
                    unique_lines.append(line)
            all_lines = unique_lines
        
        for line in all_lines:
            print(line)

    def do_uniq(self, arg):
        """Report or omit repeated lines - uniq [options] [file]"""
        args = shlex.split(arg) if arg else []
        count = False
        duplicates_only = False
        unique_only = False
        filename = None
        
        for a in args:
            if a == '-c':
                count = True
            elif a == '-d':
                duplicates_only = True
            elif a == '-u':
                unique_only = True
            elif not a.startswith('-'):
                filename = a
        
        try:
            if filename:
                content = self.fs.read_file(filename)
            else:
                return  # stdin handling simplified
            
            lines = content.split('\n')
            result = []
            line_counts = {}
            
            # Count occurrences
            for line in lines:
                line_counts[line] = line_counts.get(line, 0) + 1
            
            # Process based on options
            prev_line = None
            for line in lines:
                if line != prev_line:  # First occurrence of this line in sequence
                    line_count = line_counts[line]
                    
                    if duplicates_only and line_count == 1:
                        continue
                    if unique_only and line_count > 1:
                        continue
                    
                    if count:
                        print(f"{line_count:7} {line}")
                    else:
                        print(line)
                    
                    prev_line = line
        except Exception as e:
            print(f"uniq: {e}")

    def do_cut(self, arg):
        """Remove sections from each line - cut [options] [file...]"""
        if not arg:
            print("cut: missing operand")
            return
        
        args = shlex.split(arg)
        fields = None
        characters = None
        delimiter = '\t'
        files = []
        
        i = 0
        while i < len(args):
            if args[i] == '-f' and i + 1 < len(args):
                fields = args[i + 1]
                i += 2
            elif args[i] == '-c' and i + 1 < len(args):
                characters = args[i + 1]
                i += 2
            elif args[i] == '-d' and i + 1 < len(args):
                delimiter = args[i + 1]
                i += 2
            else:
                files.append(args[i])
                i += 1
        
        if not files:
            files = ['-']
        
        for filename in files:
            try:
                if filename == '-':
                    continue
                
                content = self.fs.read_file(filename)
                lines = content.split('\n')
                
                for line in lines:
                    if characters:
                        # Character-based cutting
                        result = self._cut_characters(line, characters)
                        print(result)
                    elif fields:
                        # Field-based cutting
                        result = self._cut_fields(line, fields, delimiter)
                        print(result)
            except Exception as e:
                print(f"cut: {filename}: {e}")

    def _cut_characters(self, line, char_spec):
        """Cut characters from line based on specification"""
        if '-' in char_spec:
            parts = char_spec.split('-', 1)
            start = int(parts[0]) - 1 if parts[0] else 0
            end = int(parts[1]) if parts[1] else len(line)
            return line[start:end]
        else:
            pos = int(char_spec) - 1
            return line[pos] if pos < len(line) else ''

    def _cut_fields(self, line, field_spec, delimiter):
        """Cut fields from line based on specification"""
        fields = line.split(delimiter)
        if '-' in field_spec:
            parts = field_spec.split('-', 1)
            start = int(parts[0]) - 1 if parts[0] else 0
            end = int(parts[1]) if parts[1] else len(fields)
            return delimiter.join(fields[start:end])
        else:
            field_num = int(field_spec) - 1
            return fields[field_num] if field_num < len(fields) else ''

    def do_tr(self, arg):
        """Translate or delete characters - tr [options] set1 [set2]"""
        if not arg:
            print("tr: missing operand")
            return
        
        args = shlex.split(arg)
        delete_mode = False
        squeeze_mode = False
        set1 = None
        set2 = None
        
        for a in args:
            if a == '-d':
                delete_mode = True
            elif a == '-s':
                squeeze_mode = True
            elif set1 is None:
                set1 = a
            elif set2 is None:
                set2 = a
        
        if not set1:
            print("tr: missing set1")
            return
        
        # Read from stdin (simplified - would normally read from stdin)
        content = "Sample text for translation"  # Placeholder
        
        if delete_mode:
            # Delete characters in set1
            result = ''.join(c for c in content if c not in set1)
        elif set2:
            # Translate set1 to set2
            trans_table = str.maketrans(set1, set2)
            result = content.translate(trans_table)
        else:
            result = content
        
        if squeeze_mode and set2:
            # Squeeze repeated characters in set2
            import re
            for c in set2:
                result = re.sub(c + '+', c, result)
        
        print(result)

    def do_diff(self, arg):
        """Compare files line by line - diff [options] file1 file2"""
        if not arg:
            print("diff: missing operand")
            return
        
        args = shlex.split(arg)
        unified = False
        files = []
        
        for a in args:
            if a == '-u':
                unified = True
            elif not a.startswith('-'):
                files.append(a)
        
        if len(files) < 2:
            print("diff: missing operand")
            return
        
        file1, file2 = files[0], files[1]
        
        try:
            content1 = self.fs.read_file(file1).split('\n')
            content2 = self.fs.read_file(file2).split('\n')
            
            if unified:
                self._diff_unified(content1, content2, file1, file2)
            else:
                self._diff_normal(content1, content2)
        except Exception as e:
            print(f"diff: {e}")

    def _diff_normal(self, lines1, lines2):
        """Normal diff output"""
        import difflib
        differ = difflib.Differ()
        diff = list(differ.compare(lines1, lines2))
        
        for line in diff:
            if line.startswith('- '):
                print(f"< {line[2:]}")
            elif line.startswith('+ '):
                print(f"> {line[2:]}")

    def _diff_unified(self, lines1, lines2, file1, file2):
        """Unified diff output"""
        import difflib
        diff = difflib.unified_diff(lines1, lines2, fromfile=file1, tofile=file2, lineterm='')
        for line in diff:
            print(line)

    # PROCESS MANAGEMENT
    def do_ps(self, arg):
        """Display process information - ps [options]"""
        args = shlex.split(arg) if arg else []
        all_processes = False
        full_format = False
        user_format = False
        
        for a in args:
            if a == '-e' or a == '-A':
                all_processes = True
            elif a == '-f':
                full_format = True
            elif a == '-u':
                user_format = True
        
        try:
            processes = self.process_mgr.list_processes()
            
            if full_format:
                print(f"{'UID':>8} {'PID':>8} {'PPID':>8} {'C':>3} {'STIME':>8} {'TTY':>8} {'TIME':>8} CMD")
                for proc in processes:
                    print(f"{proc.username:>8} {proc.pid:>8} {proc.ppid:>8} {int(proc.cpu_percent):>3} "
                          f"{'?':>8} {'?':>8} {self._format_time(proc.create_time):>8} {proc.name}")
            else:
                print(f"{'PID':>8} {'TTY':>8} {'TIME':>8} CMD")
                for proc in processes:
                    print(f"{proc.pid:>8} {'?':>8} {self._format_time(proc.create_time):>8} {proc.name}")
        except Exception as e:
            print(f"ps: {e}")

    def _format_time(self, timestamp):
        """Format process time"""
        try:
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime("%H:%M")
        except:
            return "00:00"

    def do_kill(self, arg):
        """Send signal to processes - kill [signal] pid..."""
        if not arg:
            print("kill: missing operand")
            return
        
        args = shlex.split(arg)
        signal_num = 15  # SIGTERM
        pids = []
        
        for a in args:
            if a.startswith('-'):
                signal_num = int(a[1:]) if a[1:].isdigit() else 15
            else:
                pids.append(int(a))
        
        for pid in pids:
            try:
                self.process_mgr.kill_process(pid, signal_num)
                print(f"Sent signal {signal_num} to process {pid}")
            except Exception as e:
                print(f"kill: {pid}: {e}")

    def do_killall(self, arg):
        """Kill processes by name - killall [signal] name..."""
        if not arg:
            print("killall: missing operand")
            return
        
        args = shlex.split(arg)
        signal_num = 15
        names = []
        
        for a in args:
            if a.startswith('-'):
                signal_num = int(a[1:]) if a[1:].isdigit() else 15
            else:
                names.append(a)
        
        for name in names:
            try:
                processes = self.process_mgr.find_processes_by_name(name)
                for proc in processes:
                    self.process_mgr.kill_process(proc.pid, signal_num)
                    print(f"Killed {name} (PID {proc.pid})")
            except Exception as e:
                print(f"killall: {name}: {e}")

    def do_jobs(self, arg):
        """List active jobs"""
        if not self.jobs:
            print("No active jobs")
            return
        
        for job_id, job_info in self.jobs.items():
            status = "Running" if job_info['running'] else "Stopped"
            print(f"[{job_id}]  {status}    {job_info['command']}")

    def do_nohup(self, arg):
        """Run command immune to hangups - nohup command [args...]"""
        if not arg:
            print("nohup: missing operand")
            return
        
        print(f"nohup: {arg} &")
        print("Output will be written to 'nohup.out'")
        
        # Simplified implementation - would normally run in background
        try:
            self.onecmd(arg)
        except Exception as e:
            print(f"nohup: {e}")

    # SYSTEM INFORMATION
    def do_uname(self, arg):
        """Print system information - uname [options]"""
        args = shlex.split(arg) if arg else []
        show_all = '-a' in args
        show_kernel = '-s' in args or show_all
        show_nodename = '-n' in args or show_all
        show_release = '-r' in args or show_all
        show_version = '-v' in args or show_all
        show_machine = '-m' in args or show_all
        show_os = '-o' in args or show_all
        
        if not args or args == []:
            show_kernel = True
        
        info = []
        if show_kernel:
            info.append("KOS")
        if show_nodename:
            info.append("kos-system")
        if show_release:
            info.append("1.0.0")
        if show_version:
            info.append("#1 SMP " + datetime.now().strftime("%a %b %d %H:%M:%S UTC %Y"))
        if show_machine:
            info.append(platform.machine())
        if show_os:
            info.append("GNU/Linux")
        
        print(" ".join(info))

    def do_hostname(self, arg):
        """Display or set system hostname - hostname [name]"""
        if not arg:
            print("kos-system")
        else:
            print(f"hostname set to: {arg}")

    def do_whoami(self, arg):
        """Display current username"""
        print(self.us.current_user)

    def do_id(self, arg):
        """Print user and group IDs - id [user]"""
        username = arg.strip() if arg else self.us.current_user
        try:
            user_info = self.us.get_user_info(username)
            uid = user_info.get('uid', 1000)
            gid = user_info.get('gid', 1000)
            groups = user_info.get('groups', ['users'])
            
            group_list = ','.join(f"{g}({i})" for i, g in enumerate(groups, gid))
            print(f"uid={uid}({username}) gid={gid}({groups[0]}) groups={group_list}")
        except Exception as e:
            print(f"id: {e}")

    def do_env(self, arg):
        """Display environment variables - env [variable=value...] [command]"""
        if not arg:
            for key, value in sorted(self.env_vars.items()):
                print(f"{key}={value}")
        else:
            # Simplified - would normally set env vars and run command
            print(f"env: {arg}")

    def do_export(self, arg):
        """Set environment variables - export [variable=value...]"""
        if not arg:
            for key, value in sorted(self.env_vars.items()):
                print(f"export {key}={value}")
        else:
            parts = arg.split('=', 1)
            if len(parts) == 2:
                self.env_vars[parts[0]] = parts[1]
            else:
                print(f"export: {arg}: not a valid identifier")

    def do_alias(self, arg):
        """Create command alias - alias [name='command']"""
        if not arg:
            for alias, command in sorted(self.aliases.items()):
                print(f"alias {alias}='{command}'")
        else:
            if '=' in arg:
                name, command = arg.split('=', 1)
                self.aliases[name] = command.strip("'\"")
            else:
                if arg in self.aliases:
                    print(f"alias {arg}='{self.aliases[arg]}'")
                else:
                    print(f"alias: {arg}: not found")

    def do_history(self, arg):
        """Display command history"""
        args = shlex.split(arg) if arg else []
        count = 10
        
        if args and args[0].isdigit():
            count = int(args[0])
        
        recent_history = self.history[-count:] if count > 0 else self.history
        for i, cmd in enumerate(recent_history, len(self.history) - len(recent_history) + 1):
            print(f"{i:5} {cmd}")

    def do_which(self, arg):
        """Locate command - which command..."""
        if not arg:
            print("which: missing operand")
            return
        
        commands = shlex.split(arg)
        for cmd in commands:
            if hasattr(self, f'do_{cmd}'):
                print(f"/bin/{cmd}")
            elif cmd in self.aliases:
                print(f"alias {cmd}='{self.aliases[cmd]}'")
            else:
                print(f"which: no {cmd} in PATH")

    def do_du(self, arg):
        """Display directory space usage - du [options] [path...]"""
        args = shlex.split(arg) if arg else ['.']
        human_readable = '-h' in args
        summarize = '-s' in args
        paths = [a for a in args if not a.startswith('-')]
        
        if not paths:
            paths = ['.']
        
        for path in paths:
            try:
                size = self.fs.get_directory_size(path)
                if human_readable:
                    size_str = self._human_readable_size(size)
                else:
                    size_str = str(size // 1024)  # In KB
                
                print(f"{size_str}\t{path}")
            except Exception as e:
                print(f"du: {path}: {e}")

    def do_df(self, arg):
        """Display filesystem disk space usage - df [options]"""
        args = shlex.split(arg) if arg else []
        human_readable = '-h' in args
        
        try:
            disk_info = self.process_mgr.get_disk_usage()
            
            print(f"{'Filesystem':<20} {'1K-blocks':>10} {'Used':>10} {'Available':>10} {'Use%':>5} {'Mounted on'}")
            
            total = disk_info.get('total', 0)
            used = disk_info.get('used', 0)
            free = disk_info.get('free', 0)
            percent = disk_info.get('percent', 0)
            
            if human_readable:
                total_str = self._human_readable_size(total)
                used_str = self._human_readable_size(used)
                free_str = self._human_readable_size(free)
            else:
                total_str = str(total // 1024)
                used_str = str(used // 1024)
                free_str = str(free // 1024)
            
            print(f"{'kos-filesystem':<20} {total_str:>10} {used_str:>10} {free_str:>10} {percent:>4}% /")
            
        except Exception as e:
            print(f"df: {e}")

    def do_free(self, arg):
        """Display memory usage - free [options]"""
        args = shlex.split(arg) if arg else []
        human_readable = '-h' in args
        
        try:
            memory_info = self.process_mgr.get_memory_info()
            
            total = memory_info.get('total', 0)
            used = memory_info.get('used', 0)
            free = memory_info.get('free', 0)
            available = memory_info.get('available', 0)
            
            if human_readable:
                total_str = self._human_readable_size(total)
                used_str = self._human_readable_size(used)
                free_str = self._human_readable_size(free)
                avail_str = self._human_readable_size(available)
            else:
                total_str = str(total // 1024)
                used_str = str(used // 1024)
                free_str = str(free // 1024)
                avail_str = str(available // 1024)
            
            print(f"{'':>14} {'total':>10} {'used':>10} {'free':>10} {'available':>10}")
            print(f"{'Mem:':<14} {total_str:>10} {used_str:>10} {free_str:>10} {avail_str:>10}")
            
        except Exception as e:
            print(f"free: {e}")

    def do_uptime(self, arg):
        """Show system uptime and load"""
        try:
            boot_time = psutil.boot_time()
            uptime_seconds = time.time() - boot_time
            
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            current_time = datetime.now().strftime("%H:%M:%S")
            users = 1  # Simplified
            load_avg = "0.00, 0.00, 0.00"  # Simplified
            
            uptime_str = f"up {days} days, {hours}:{minutes:02d}"
            print(f" {current_time} up {uptime_str}, {users} user, load average: {load_avg}")
            
        except Exception as e:
            print(f"uptime: {e}")

    def do_date(self, arg):
        """Display or set date - date [options] [+format]"""
        if not arg:
            print(datetime.now().strftime("%a %b %d %H:%M:%S %Z %Y"))
        elif arg.startswith('+'):
            # Custom format
            format_str = arg[1:].replace('%Y', '%Y').replace('%m', '%m').replace('%d', '%d')
            print(datetime.now().strftime(format_str))
        else:
            print("date: setting date not implemented")

    # NETWORK TOOLS
    def do_ping(self, arg):
        """Test network connectivity - ping host"""
        if not arg:
            print("ping: missing host operand")
            return
        
        host = arg.strip()
        print(f"PING {host} (127.0.0.1) 56(84) bytes of data.")
        
        try:
            for i in range(4):
                print(f"64 bytes from {host} (127.0.0.1): icmp_seq={i+1} time=0.1 ms")
                time.sleep(1)
            print(f"\n--- {host} ping statistics ---")
            print("4 packets transmitted, 4 received, 0% packet loss, time 3003ms")
            print("rtt min/avg/max/mdev = 0.1/0.1/0.1/0.0 ms")
        except KeyboardInterrupt:
            print(f"\n--- {host} ping statistics ---")
            print("ping interrupted")

    def do_wget(self, arg):
        """Retrieve files from web - wget [options] URL"""
        if not arg:
            print("wget: missing URL")
            return
        
        url = arg.strip()
        try:
            filename = url.split('/')[-1] or 'index.html'
            print(f"--{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}--  {url}")
            print(f"Saving to: '{filename}'")
            
            # Simplified download simulation
            content = f"Content downloaded from {url}"
            self.fs.create_file(filename, content)
            print(f"'{filename}' saved")
            
        except Exception as e:
            print(f"wget: {e}")

    def do_curl(self, arg):
        """Transfer data from servers - curl [options] URL"""
        if not arg:
            print("curl: missing URL")
            return
        
        args = shlex.split(arg)
        output_file = None
        url = None
        
        i = 0
        while i < len(args):
            if args[i] == '-o' and i + 1 < len(args):
                output_file = args[i + 1]
                i += 2
            else:
                url = args[i]
                i += 1
        
        if not url:
            print("curl: no URL specified")
            return
        
        try:
            # Simplified curl simulation
            content = f"Content from {url}\n"
            
            if output_file:
                self.fs.create_file(output_file, content)
                print(f"Content saved to {output_file}")
            else:
                print(content)
                
        except Exception as e:
            print(f"curl: {e}")

    # ARCHIVE AND COMPRESSION
    def do_tar(self, arg):
        """Archive files - tar [options] [archive] [files...]"""
        if not arg:
            print("tar: missing operand")
            return
        
        args = shlex.split(arg)
        create = False
        extract = False
        verbose = False
        file_arg = None
        files = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                options = args[i][1:]
                if 'c' in options:
                    create = True
                if 'x' in options:
                    extract = True
                if 'v' in options:
                    verbose = True
                if 'f' in options and i + 1 < len(args):
                    file_arg = args[i + 1]
                    i += 1
            else:
                if file_arg is None:
                    file_arg = args[i]
                else:
                    files.append(args[i])
            i += 1
        
        if not file_arg:
            print("tar: missing archive file")
            return
        
        try:
            if create:
                print(f"Creating archive {file_arg}")
                # Simplified tar creation
                archive_content = "# TAR Archive\n"
                for filename in files:
                    if verbose:
                        print(filename)
                    archive_content += f"File: {filename}\n"
                self.fs.create_file(file_arg, archive_content)
            elif extract:
                print(f"Extracting archive {file_arg}")
                if verbose:
                    print("Verbose extraction not implemented")
                # Simplified extraction would go here
        except Exception as e:
            print(f"tar: {e}")

    def do_gzip(self, arg):
        """Compress files - gzip [files...]"""
        if not arg:
            print("gzip: missing operand")
            return
        
        files = shlex.split(arg)
        for filename in files:
            try:
                content = self.fs.read_file(filename)
                compressed = gzip.compress(content.encode())
                
                compressed_filename = filename + '.gz'
                # Note: In real implementation, would write binary data
                self.fs.create_file(compressed_filename, f"[GZIP compressed data for {filename}]")
                self.fs.delete_file(filename)
                
                print(f"Compressed {filename} -> {compressed_filename}")
            except Exception as e:
                print(f"gzip: {filename}: {e}")

    def do_gunzip(self, arg):
        """Decompress gzip files - gunzip [files...]"""
        if not arg:
            print("gunzip: missing operand")
            return
        
        files = shlex.split(arg)
        for filename in files:
            try:
                if not filename.endswith('.gz'):
                    print(f"gunzip: {filename}: not in gzip format")
                    continue
                
                # Simplified decompression
                original_filename = filename[:-3]
                content = f"[Decompressed content of {filename}]"
                self.fs.create_file(original_filename, content)
                self.fs.delete_file(filename)
                
                print(f"Decompressed {filename} -> {original_filename}")
            except Exception as e:
                print(f"gunzip: {filename}: {e}")

    # TEXT EDITORS
    def do_nano(self, arg):
        """Simple text editor - nano [file]"""
        if not arg:
            print("nano: missing file operand")
            return
        
        filename = arg.strip()
        print(f"Opening {filename} in nano editor (simplified)")
        
        try:
            if self.fs.file_exists(filename):
                content = self.fs.read_file(filename)
                print(f"Current content:\n{content}")
            
            print("\nSimulated nano editor - enter text (empty line to save and exit):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            
            new_content = '\n'.join(lines)
            self.fs.create_file(filename, new_content)
            print(f"File {filename} saved")
            
        except Exception as e:
            print(f"nano: {e}")

    def do_clear(self, arg):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def do_exit(self, arg):
        """Exit the shell"""
        print("Goodbye!")
        return True

    def do_logout(self, arg):
        """Exit the shell"""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        """Handle Ctrl+D"""
        print()
        return self.do_exit(arg)
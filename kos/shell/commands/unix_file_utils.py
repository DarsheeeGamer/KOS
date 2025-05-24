"""
Unix-like File Utilities for KOS Shell

This module provides Linux/Unix-like file manipulation commands for KOS.
"""

import os
import sys
import time
import stat
import shutil
import logging
import glob
import fnmatch
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.layer import klayer

# Set up logging
logger = logging.getLogger('KOS.shell.commands.unix_file_utils')

class UnixFileUtilities:
    """Unix-like file utility commands for KOS shell"""
    
    @staticmethod
    def do_ls(fs, cwd, arg):
        """
        List directory contents
        
        Usage: ls [options] [directory...]
        
        Options:
          -a, --all             Include hidden entries (starting with .)
          -l                    Use long listing format
          -h, --human-readable  Print sizes in human readable format
          -r, --reverse         Reverse order while sorting
          -S                    Sort by file size, largest first
          -t                    Sort by modification time, newest first
          -R, --recursive       List subdirectories recursively
          --color               Colorize the output
        """
        args = arg.split()
        
        # Parse options
        show_all = False
        long_format = False
        human_readable = False
        reverse = False
        sort_by_size = False
        sort_by_time = False
        recursive = False
        colorize = False
        
        # Process arguments
        paths = []
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] == '-a' or args[i] == '--all':
                    show_all = True
                elif args[i] == '-l':
                    long_format = True
                elif args[i] == '-h' or args[i] == '--human-readable':
                    human_readable = True
                elif args[i] == '-r' or args[i] == '--reverse':
                    reverse = True
                elif args[i] == '-S':
                    sort_by_size = True
                elif args[i] == '-t':
                    sort_by_time = True
                elif args[i] == '-R' or args[i] == '--recursive':
                    recursive = True
                elif args[i] == '--color':
                    colorize = True
                elif args[i] == '-la' or args[i] == '-al':
                    long_format = True
                    show_all = True
                else:
                    # Process combined options like -lah
                    for c in args[i][1:]:
                        if c == 'a':
                            show_all = True
                        elif c == 'l':
                            long_format = True
                        elif c == 'h':
                            human_readable = True
                        elif c == 'r':
                            reverse = True
                        elif c == 'S':
                            sort_by_size = True
                        elif c == 't':
                            sort_by_time = True
                        elif c == 'R':
                            recursive = True
            else:
                paths.append(args[i])
            i += 1
        
        # If no paths specified, use current directory
        if not paths:
            paths = [cwd]
        
        results = []
        
        # Process each path
        for path in paths:
            # Resolve path
            if not os.path.isabs(path):
                path = os.path.join(cwd, path)
            
            # Check if path exists
            if not os.path.exists(path):
                results.append(f"ls: cannot access '{path}': No such file or directory")
                continue
            
            # Get directory contents
            if os.path.isdir(path):
                entries = []
                try:
                    with os.scandir(path) as it:
                        for entry in it:
                            # Skip hidden entries unless show_all is True
                            if not show_all and entry.name.startswith('.'):
                                continue
                            
                            entry_stat = entry.stat()
                            entries.append({
                                'name': entry.name,
                                'path': entry.path,
                                'is_dir': entry.is_dir(),
                                'size': entry_stat.st_size,
                                'mtime': entry_stat.st_mtime,
                                'atime': entry_stat.st_atime,
                                'ctime': entry_stat.st_ctime,
                                'mode': entry_stat.st_mode,
                                'uid': entry_stat.st_uid,
                                'gid': entry_stat.st_gid,
                                'nlink': entry_stat.st_nlink
                            })
                except PermissionError:
                    results.append(f"ls: cannot open directory '{path}': Permission denied")
                    continue
                
                # Sort entries
                if sort_by_size:
                    entries.sort(key=lambda e: e['size'], reverse=not reverse)
                elif sort_by_time:
                    entries.sort(key=lambda e: e['mtime'], reverse=not reverse)
                else:
                    entries.sort(key=lambda e: e['name'].lower(), reverse=reverse)
                
                # Format output
                if len(paths) > 1 or recursive:
                    results.append(f"\n{path}:")
                
                if long_format:
                    # Calculate column widths
                    nlink_width = max([len(str(e['nlink'])) for e in entries]) if entries else 1
                    uid_width = max([len(str(e['uid'])) for e in entries]) if entries else 1
                    gid_width = max([len(str(e['gid'])) for e in entries]) if entries else 1
                    size_width = max([len(str(e['size'])) for e in entries]) if entries else 1
                    
                    for entry in entries:
                        # Format mode (permissions)
                        mode_str = UnixFileUtilities._format_mode(entry['mode'])
                        
                        # Format size
                        if human_readable:
                            size_str = UnixFileUtilities._format_size(entry['size'])
                        else:
                            size_str = str(entry['size'])
                        
                        # Format time
                        mtime_str = datetime.fromtimestamp(entry['mtime']).strftime('%b %d %H:%M')
                        
                        # Format name with color if requested
                        name = entry['name']
                        if colorize:
                            if entry['is_dir']:
                                name = f"\033[1;34m{name}\033[0m"  # Blue for directories
                            elif entry['mode'] & stat.S_IXUSR:
                                name = f"\033[1;32m{name}\033[0m"  # Green for executables
                            elif entry['mode'] & stat.S_IFLNK:
                                name = f"\033[1;36m{name}\033[0m"  # Cyan for symlinks
                        
                        line = (
                            f"{mode_str} "
                            f"{entry['nlink']:{nlink_width}} "
                            f"{entry['uid']:{uid_width}} "
                            f"{entry['gid']:{gid_width}} "
                            f"{size_str:{size_width if not human_readable else ''}} "
                            f"{mtime_str} "
                            f"{name}"
                        )
                        results.append(line)
                else:
                    # Simple format
                    names = []
                    for entry in entries:
                        name = entry['name']
                        if colorize:
                            if entry['is_dir']:
                                name = f"\033[1;34m{name}\033[0m"  # Blue for directories
                            elif entry['mode'] & stat.S_IXUSR:
                                name = f"\033[1;32m{name}\033[0m"  # Green for executables
                            elif entry['mode'] & stat.S_IFLNK:
                                name = f"\033[1;36m{name}\033[0m"  # Cyan for symlinks
                        names.append(name)
                    
                    # Arrange in columns (simplified)
                    results.append("  ".join(names))
                
                # Process subdirectories if recursive
                if recursive:
                    for entry in entries:
                        if entry['is_dir'] and entry['name'] not in ['.', '..']:
                            subdir_path = os.path.join(path, entry['name'])
                            subdir_result = UnixFileUtilities.do_ls(fs, cwd, f"-{'a' if show_all else ''}{'l' if long_format else ''}{'h' if human_readable else ''}{'r' if reverse else ''}{'S' if sort_by_size else ''}{'t' if sort_by_time else ''}{'R' if recursive else ''} {subdir_path}")
                            results.append(subdir_result)
            else:
                # It's a file, just show its info
                try:
                    entry_stat = os.stat(path)
                    entry = {
                        'name': os.path.basename(path),
                        'path': path,
                        'is_dir': False,
                        'size': entry_stat.st_size,
                        'mtime': entry_stat.st_mtime,
                        'atime': entry_stat.st_atime,
                        'ctime': entry_stat.st_ctime,
                        'mode': entry_stat.st_mode,
                        'uid': entry_stat.st_uid,
                        'gid': entry_stat.st_gid,
                        'nlink': entry_stat.st_nlink
                    }
                    
                    if long_format:
                        # Format mode (permissions)
                        mode_str = UnixFileUtilities._format_mode(entry['mode'])
                        
                        # Format size
                        if human_readable:
                            size_str = UnixFileUtilities._format_size(entry['size'])
                        else:
                            size_str = str(entry['size'])
                        
                        # Format time
                        mtime_str = datetime.fromtimestamp(entry['mtime']).strftime('%b %d %H:%M')
                        
                        # Format name with color if requested
                        name = entry['name']
                        if colorize:
                            if entry['is_dir']:
                                name = f"\033[1;34m{name}\033[0m"  # Blue for directories
                            elif entry['mode'] & stat.S_IXUSR:
                                name = f"\033[1;32m{name}\033[0m"  # Green for executables
                            elif entry['mode'] & stat.S_IFLNK:
                                name = f"\033[1;36m{name}\033[0m"  # Cyan for symlinks
                        
                        line = (
                            f"{mode_str} "
                            f"{entry['nlink']} "
                            f"{entry['uid']} "
                            f"{entry['gid']} "
                            f"{size_str} "
                            f"{mtime_str} "
                            f"{name}"
                        )
                        results.append(line)
                    else:
                        name = entry['name']
                        if colorize:
                            if entry['is_dir']:
                                name = f"\033[1;34m{name}\033[0m"  # Blue for directories
                            elif entry['mode'] & stat.S_IXUSR:
                                name = f"\033[1;32m{name}\033[0m"  # Green for executables
                            elif entry['mode'] & stat.S_IFLNK:
                                name = f"\033[1;36m{name}\033[0m"  # Cyan for symlinks
                        results.append(name)
                        
                except PermissionError:
                    results.append(f"ls: cannot access '{path}': Permission denied")
                except FileNotFoundError:
                    results.append(f"ls: cannot access '{path}': No such file or directory")
        
        return "\n".join(results)
    
    @staticmethod
    def _format_mode(mode):
        """Format file mode (permissions) in Unix-like format"""
        perms = ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-']
        
        # File type
        if stat.S_ISDIR(mode):
            perms[0] = 'd'
        elif stat.S_ISLNK(mode):
            perms[0] = 'l'
        elif stat.S_ISCHR(mode):
            perms[0] = 'c'
        elif stat.S_ISBLK(mode):
            perms[0] = 'b'
        elif stat.S_ISFIFO(mode):
            perms[0] = 'p'
        elif stat.S_ISSOCK(mode):
            perms[0] = 's'
        
        # User permissions
        if mode & stat.S_IRUSR:
            perms[1] = 'r'
        if mode & stat.S_IWUSR:
            perms[2] = 'w'
        if mode & stat.S_IXUSR:
            perms[3] = 'x'
        
        # Group permissions
        if mode & stat.S_IRGRP:
            perms[4] = 'r'
        if mode & stat.S_IWGRP:
            perms[5] = 'w'
        if mode & stat.S_IXGRP:
            perms[6] = 'x'
        
        # Other permissions
        if mode & stat.S_IROTH:
            perms[7] = 'r'
        if mode & stat.S_IWOTH:
            perms[8] = 'w'
        if mode & stat.S_IXOTH:
            perms[9] = 'x'
        
        # Special bits
        if mode & stat.S_ISUID:
            perms[3] = 's' if perms[3] == 'x' else 'S'
        if mode & stat.S_ISGID:
            perms[6] = 's' if perms[6] == 'x' else 'S'
        if mode & stat.S_ISVTX:
            perms[9] = 't' if perms[9] == 'x' else 'T'
        
        return ''.join(perms)
    
    @staticmethod
    def _format_size(size):
        """Format size in human-readable format"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}K"
        elif size < 1024 * 1024 * 1024:
            return f"{size/(1024*1024):.1f}M"
        else:
            return f"{size/(1024*1024*1024):.1f}G"
    
    @staticmethod
    def do_cp(fs, cwd, arg):
        """
        Copy files and directories
        
        Usage: cp [options] source... destination
        
        Options:
          -r, -R, --recursive   Copy directories recursively
          -f, --force           Force copy by removing destination if needed
          -i, --interactive     Prompt before overwrite
          -p, --preserve        Preserve file attributes if possible
          -v, --verbose         Explain what is being done
        """
        args = arg.split()
        
        # Parse options
        recursive = False
        force = False
        interactive = False
        preserve = False
        verbose = False
        
        # Process arguments
        sources = []
        destination = None
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-r', '-R', '--recursive']:
                    recursive = True
                elif args[i] in ['-f', '--force']:
                    force = True
                    interactive = False  # force overrides interactive
                elif args[i] in ['-i', '--interactive']:
                    interactive = True
                    force = False  # interactive overrides force
                elif args[i] in ['-p', '--preserve']:
                    preserve = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                else:
                    # Process combined options like -rf
                    for c in args[i][1:]:
                        if c == 'r' or c == 'R':
                            recursive = True
                        elif c == 'f':
                            force = True
                            interactive = False
                        elif c == 'i':
                            interactive = True
                            force = False
                        elif c == 'p':
                            preserve = True
                        elif c == 'v':
                            verbose = True
            else:
                sources.append(args[i])
            i += 1
        
        # Last source is actually the destination
        if sources:
            destination = sources.pop()
        
        if not sources or not destination:
            return "cp: missing file operand\nTry 'cp --help' for more information."
        
        # Resolve paths
        resolved_sources = []
        for source in sources:
            if not os.path.isabs(source):
                resolved_sources.append(os.path.join(cwd, source))
            else:
                resolved_sources.append(source)
        
        if not os.path.isabs(destination):
            resolved_destination = os.path.join(cwd, destination)
        else:
            resolved_destination = destination
        
        # Check if destination is a directory
        dest_is_dir = os.path.isdir(resolved_destination)
        
        # If multiple sources, destination must be a directory
        if len(resolved_sources) > 1 and not dest_is_dir:
            return f"cp: target '{destination}' is not a directory"
        
        results = []
        
        # Process each source
        for source in resolved_sources:
            # Check if source exists
            if not os.path.exists(source):
                results.append(f"cp: cannot stat '{source}': No such file or directory")
                continue
            
            # Determine target path
            if dest_is_dir:
                target = os.path.join(resolved_destination, os.path.basename(source))
            else:
                target = resolved_destination
            
            # Check if source is a directory
            if os.path.isdir(source):
                if not recursive:
                    results.append(f"cp: -r not specified; omitting directory '{source}'")
                    continue
                
                # Copy directory recursively
                try:
                    if os.path.exists(target):
                        if os.path.samefile(source, target):
                            results.append(f"cp: '{source}' and '{target}' are the same file")
                            continue
                        
                        if interactive:
                            # In real implementation, would prompt user here
                            results.append(f"cp: overwrite '{target}'? (y/n)")
                            continue
                        
                        if not force:
                            if not os.access(target, os.W_OK):
                                results.append(f"cp: cannot remove '{target}': Permission denied")
                                continue
                        
                        # Remove existing directory if force
                        if force:
                            shutil.rmtree(target)
                    
                    # Copy directory
                    shutil.copytree(source, target, symlinks=True)
                    
                    if verbose:
                        results.append(f"'{source}' -> '{target}'")
                except PermissionError:
                    results.append(f"cp: cannot create directory '{target}': Permission denied")
                except shutil.Error as e:
                    results.append(f"cp: error copying '{source}': {str(e)}")
            else:
                # Copy file
                try:
                    if os.path.exists(target):
                        if os.path.samefile(source, target):
                            results.append(f"cp: '{source}' and '{target}' are the same file")
                            continue
                        
                        if interactive:
                            # In real implementation, would prompt user here
                            results.append(f"cp: overwrite '{target}'? (y/n)")
                            continue
                        
                        if not force:
                            if not os.access(target, os.W_OK):
                                results.append(f"cp: cannot remove '{target}': Permission denied")
                                continue
                    
                    # Copy file
                    if preserve:
                        shutil.copy2(source, target)  # Preserves metadata
                    else:
                        shutil.copy(source, target)
                    
                    if verbose:
                        results.append(f"'{source}' -> '{target}'")
                except PermissionError:
                    results.append(f"cp: cannot create regular file '{target}': Permission denied")
                except shutil.Error as e:
                    results.append(f"cp: error copying '{source}': {str(e)}")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output if not verbose
    
    @staticmethod
    def do_mkdir(fs, cwd, arg):
        """
        Create directories
        
        Usage: mkdir [options] directory...
        
        Options:
          -p, --parents         Create parent directories as needed
          -v, --verbose         Print a message for each created directory
          -m, --mode=MODE       Set file mode (as in chmod)
        """
        args = arg.split()
        
        # Parse options
        parents = False
        verbose = False
        mode = 0o777  # Default mode
        
        # Process arguments
        directories = []
        
        i = 0
        while i < len(args):
            if args[i].startswith('-'):
                if args[i] in ['-p', '--parents']:
                    parents = True
                elif args[i] in ['-v', '--verbose']:
                    verbose = True
                elif args[i].startswith('-m=') or args[i].startswith('--mode='):
                    mode_str = args[i].split('=')[1]
                    try:
                        # Convert mode string to octal
                        mode = int(mode_str, 8)
                    except ValueError:
                        return f"mkdir: invalid mode: '{mode_str}'"
                elif args[i].startswith('-m'):
                    mode_str = args[i][2:]
                    try:
                        # Convert mode string to octal
                        mode = int(mode_str, 8)
                    except ValueError:
                        return f"mkdir: invalid mode: '{mode_str}'"
                else:
                    # Process combined options like -pv
                    for c in args[i][1:]:
                        if c == 'p':
                            parents = True
                        elif c == 'v':
                            verbose = True
            else:
                directories.append(args[i])
            i += 1
        
        if not directories:
            return "mkdir: missing operand\nTry 'mkdir --help' for more information."
        
        results = []
        
        # Process each directory
        for directory in directories:
            # Resolve path
            if not os.path.isabs(directory):
                path = os.path.join(cwd, directory)
            else:
                path = directory
            
            try:
                # Create directory
                if parents:
                    os.makedirs(path, mode=mode, exist_ok=True)
                else:
                    os.mkdir(path, mode=mode)
                
                if verbose:
                    results.append(f"mkdir: created directory '{directory}'")
            except FileExistsError:
                results.append(f"mkdir: cannot create directory '{directory}': File exists")
            except PermissionError:
                results.append(f"mkdir: cannot create directory '{directory}': Permission denied")
            except FileNotFoundError:
                results.append(f"mkdir: cannot create directory '{directory}': No such file or directory")
        
        if results:
            return "\n".join(results)
        return ""  # Success with no output if not verbose

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("ls", UnixFileUtilities.do_ls)
    shell.register_command("cp", UnixFileUtilities.do_cp)
    shell.register_command("mkdir", UnixFileUtilities.do_mkdir)

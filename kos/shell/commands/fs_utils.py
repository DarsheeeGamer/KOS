"""
File System Utilities for KOS Shell

This module implements Linux-style file system commands for the KOS shell,
providing familiar utilities for file manipulation, searching, and information.
"""

import os
import re
import shlex
import logging
import fnmatch
import stat
import time
import datetime
import shutil
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger('KOS.shell.fs_utils')

class FileSystemUtils:
    """Implementation of Linux-style file system utilities for KOS shell."""
    
    @staticmethod
    def do_find(fs, cwd, arg):
        """Search for files in a directory hierarchy
        
        Usage: find [path] [options]
        
        Options:
          -name PATTERN       File name matches PATTERN (using shell-style wildcards)
          -type TYPE          File is of type TYPE (f=file, d=directory)
          -size SIZE          File uses SIZE space (e.g., +10k, -5M)
          -mtime DAYS         File's data was last modified DAYS days ago
          -newer FILE         File was modified more recently than FILE
          -exec CMD           Execute command CMD on each matched file
          
        Examples:
          find /home -name "*.txt"
          find . -type f -size +1M
          find /var/log -mtime -7
        """
        args = shlex.split(arg)
        if not args:
            return FileSystemUtils.do_find.__doc__
        
        # Parse path and options
        path = args[0] if not args[0].startswith('-') else cwd
        
        # Default values
        name_pattern = None
        file_type = None
        size_spec = None
        mtime_spec = None
        newer_file = None
        exec_cmd = None
        
        # Parse options
        i = 1 if not args[0].startswith('-') else 0
        while i < len(args):
            if args[i] == '-name' and i + 1 < len(args):
                name_pattern = args[i + 1]
                i += 2
            elif args[i] == '-type' and i + 1 < len(args):
                file_type = args[i + 1]
                i += 2
            elif args[i] == '-size' and i + 1 < len(args):
                size_spec = args[i + 1]
                i += 2
            elif args[i] == '-mtime' and i + 1 < len(args):
                mtime_spec = args[i + 1]
                i += 2
            elif args[i] == '-newer' and i + 1 < len(args):
                newer_file = args[i + 1]
                i += 2
            elif args[i] == '-exec' and i + 1 < len(args):
                # Collect everything until the end or until ';'
                exec_start = i + 1
                while i + 1 < len(args) and args[i + 1] != ';':
                    i += 1
                if i + 1 < len(args) and args[i + 1] == ';':
                    exec_cmd = ' '.join(args[exec_start:i + 1])
                    i += 2
                else:
                    return "Error: -exec requires a command terminated by ';'"
            else:
                i += 1
        
        # Process newer file reference time if specified
        newer_time = None
        if newer_file:
            try:
                newer_time = os.path.getmtime(os.path.join(cwd, newer_file))
            except (OSError, IOError):
                return f"Error: Could not access reference file '{newer_file}'"
        
        # Perform the search
        results = []
        try:
            # Resolve path relative to cwd if not absolute
            search_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
            
            for root, dirs, files in os.walk(search_path):
                for item in dirs + files:
                    full_path = os.path.join(root, item)
                    rel_path = os.path.relpath(full_path, cwd)
                    
                    # Check file type
                    is_dir = os.path.isdir(full_path)
                    if file_type == 'f' and is_dir:
                        continue
                    if file_type == 'd' and not is_dir:
                        continue
                    
                    # Check name pattern
                    if name_pattern and not fnmatch.fnmatch(item, name_pattern):
                        continue
                    
                    # Check size
                    if size_spec:
                        size = os.path.getsize(full_path)
                        if size_spec.startswith('+'):
                            size_val = FileSystemUtils._parse_size(size_spec[1:])
                            if size <= size_val:
                                continue
                        elif size_spec.startswith('-'):
                            size_val = FileSystemUtils._parse_size(size_spec[1:])
                            if size >= size_val:
                                continue
                        else:
                            size_val = FileSystemUtils._parse_size(size_spec)
                            if size != size_val:
                                continue
                    
                    # Check mtime
                    if mtime_spec:
                        mtime = os.path.getmtime(full_path)
                        days_diff = (time.time() - mtime) / (60 * 60 * 24)
                        if mtime_spec.startswith('+'):
                            days = int(mtime_spec[1:])
                            if days_diff <= days:
                                continue
                        elif mtime_spec.startswith('-'):
                            days = int(mtime_spec[1:])
                            if days_diff >= days:
                                continue
                        else:
                            days = int(mtime_spec)
                            if not (days <= days_diff < days + 1):
                                continue
                    
                    # Check newer
                    if newer_time and os.path.getmtime(full_path) <= newer_time:
                        continue
                    
                    # Execute command if specified
                    if exec_cmd:
                        # Replace {} with the file path
                        cmd = exec_cmd.replace('{}', full_path)
                        # Execute command (simplified implementation)
                        os.system(cmd)
                    
                    results.append(rel_path)
        
        except Exception as e:
            logger.error(f"Error in find command: {e}")
            return f"Error: {str(e)}"
        
        if not results:
            return "No matching files found."
        
        return "\n".join(results)
    
    @staticmethod
    def _parse_size(size_str):
        """Parse size string with suffix (k, M, G) to bytes"""
        size_str = size_str.strip()
        if size_str.endswith('k'):
            return int(size_str[:-1]) * 1024
        elif size_str.endswith('M'):
            return int(size_str[:-1]) * 1024 * 1024
        elif size_str.endswith('G'):
            return int(size_str[:-1]) * 1024 * 1024 * 1024
        else:
            return int(size_str)
    
    @staticmethod
    def do_grep(fs, cwd, arg):
        """Search for PATTERN in files
        
        Usage: grep [options] PATTERN [FILE...]
        
        Options:
          -r, --recursive    Recursively search directories
          -i, --ignore-case  Ignore case distinctions
          -v, --invert-match Select non-matching lines
          -n, --line-number  Print line number with output lines
          -l, --files-with-matches
                            Print only names of FILEs with matches
          -c, --count        Print only a count of matching lines per FILE
          
        Examples:
          grep "import" *.py
          grep -r -i "error" /var/log
          grep -v "DEBUG" app.log
        """
        args = shlex.split(arg)
        if len(args) < 1:
            return FileSystemUtils.do_grep.__doc__
        
        # Parse options
        recursive = False
        ignore_case = False
        invert_match = False
        line_number = False
        files_with_matches = False
        count_only = False
        
        # Extract options
        while args and args[0].startswith('-'):
            if args[0] in ['-r', '--recursive']:
                recursive = True
            elif args[0] in ['-i', '--ignore-case']:
                ignore_case = True
            elif args[0] in ['-v', '--invert-match']:
                invert_match = True
            elif args[0] in ['-n', '--line-number']:
                line_number = True
            elif args[0] in ['-l', '--files-with-matches']:
                files_with_matches = True
            elif args[0] in ['-c', '--count']:
                count_only = True
            else:
                return f"Unknown option: {args[0]}"
            args = args[1:]
        
        if not args:
            return "Missing pattern"
        
        pattern = args[0]
        args = args[1:]
        
        # If no files specified and not recursive, return error
        if not args and not recursive:
            return "No files specified"
        
        # If recursive and no files, use current directory
        if recursive and not args:
            args = ['.']
        
        # Compile regex
        try:
            if ignore_case:
                regex = re.compile(pattern, re.IGNORECASE)
            else:
                regex = re.compile(pattern)
        except re.error as e:
            return f"Invalid regular expression: {e}"
        
        results = []
        file_count = 0
        match_count = 0
        
        # Process each file/directory
        for path in args:
            # Resolve path relative to cwd if not absolute
            full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
            
            # Get all files to process
            files_to_process = []
            if os.path.isdir(full_path):
                if recursive:
                    # Walk directory recursively
                    for root, dirs, files in os.walk(full_path):
                        for file in files:
                            files_to_process.append(os.path.join(root, file))
                else:
                    results.append(f"{path} is a directory")
                    continue
            else:
                files_to_process.append(full_path)
            
            # Process each file
            for file_path in files_to_process:
                try:
                    with open(file_path, 'r', errors='replace') as f:
                        file_matches = 0
                        file_displayed = False
                        
                        for i, line in enumerate(f, 1):
                            match = bool(regex.search(line))
                            if invert_match:
                                match = not match
                            
                            if match:
                                file_matches += 1
                                match_count += 1
                                
                                if not count_only and not files_with_matches:
                                    rel_path = os.path.relpath(file_path, cwd)
                                    if line_number:
                                        results.append(f"{rel_path}:{i}:{line.rstrip()}")
                                    else:
                                        results.append(f"{rel_path}:{line.rstrip()}")
                        
                        if file_matches > 0:
                            file_count += 1
                            
                            if files_with_matches:
                                rel_path = os.path.relpath(file_path, cwd)
                                results.append(rel_path)
                            elif count_only:
                                rel_path = os.path.relpath(file_path, cwd)
                                results.append(f"{rel_path}:{file_matches}")
                
                except (IOError, UnicodeDecodeError) as e:
                    results.append(f"Error reading {file_path}: {e}")
        
        if not results:
            return "No matches found"
        
        return "\n".join(results)
    
    @staticmethod
    def do_df(fs, cwd, arg):
        """Report file system disk space usage
        
        Usage: df [options] [FILE...]
        
        Options:
          -h, --human-readable  Print sizes in human readable format
          -a, --all             Include empty file systems
          
        Examples:
          df
          df -h
          df /home
        """
        args = shlex.split(arg)
        
        # Parse options
        human_readable = False
        show_all = False
        
        # Extract options
        while args and args[0].startswith('-'):
            if args[0] in ['-h', '--human-readable']:
                human_readable = True
            elif args[0] in ['-a', '--all']:
                show_all = True
            else:
                return f"Unknown option: {args[0]}"
            args = args[1:]
        
        # Get paths to check
        paths = args if args else ['/']
        
        # Format output
        result = ["Filesystem            Size  Used  Avail  Use%  Mounted on"]
        
        for path in paths:
            try:
                # Resolve path relative to cwd if not absolute
                full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
                
                if not os.path.exists(full_path):
                    result.append(f"{path}: No such file or directory")
                    continue
                
                # Get disk usage stats
                disk = shutil.disk_usage(full_path)
                
                # Skip empty filesystems if not showing all
                if not show_all and disk.total == 0:
                    continue
                
                # Format sizes
                if human_readable:
                    total = FileSystemUtils._format_size(disk.total)
                    used = FileSystemUtils._format_size(disk.used)
                    free = FileSystemUtils._format_size(disk.free)
                else:
                    total = str(disk.total)
                    used = str(disk.used)
                    free = str(disk.free)
                
                # Calculate usage percentage
                if disk.total > 0:
                    use_percent = int(disk.used / disk.total * 100)
                else:
                    use_percent = 0
                
                # Get filesystem info (simplified for cross-platform)
                filesystem = "local"
                mounted_on = os.path.abspath(os.path.dirname(full_path))
                
                # Format line
                result.append(f"{filesystem:<20} {total:>6}  {used:>5}  {free:>5}  {use_percent:>3}%  {mounted_on}")
            
            except Exception as e:
                result.append(f"Error getting disk usage for {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def _format_size(size):
        """Format size in bytes to human-readable format"""
        for unit in ['B', 'K', 'M', 'G', 'T', 'P']:
            if size < 1024 or unit == 'P':
                if unit == 'B':
                    return f"{size}{unit}"
                return f"{size:.1f}{unit}"
            size /= 1024
    
    @staticmethod
    def do_du(fs, cwd, arg):
        """Estimate file space usage
        
        Usage: du [options] [FILE...]
        
        Options:
          -h, --human-readable  Print sizes in human readable format
          -s, --summarize       Display only a total for each argument
          -d, --max-depth=N     Print the total for directories only N levels deep
          
        Examples:
          du
          du -h /var/log
          du -s *
        """
        args = shlex.split(arg)
        
        # Parse options
        human_readable = False
        summarize = False
        max_depth = None
        
        # Extract options
        while args and args[0].startswith('-'):
            if args[0] in ['-h', '--human-readable']:
                human_readable = True
            elif args[0] in ['-s', '--summarize']:
                summarize = True
            elif args[0].startswith('-d') or args[0].startswith('--max-depth='):
                if args[0].startswith('-d'):
                    if len(args[0]) > 2:
                        max_depth = int(args[0][2:])
                    elif len(args) > 1:
                        max_depth = int(args[1])
                        args = args[1:]
                else:
                    max_depth = int(args[0].split('=')[1])
            else:
                return f"Unknown option: {args[0]}"
            args = args[1:]
        
        # Get paths to check
        paths = args if args else ['.']
        
        result = []
        
        for path in paths:
            try:
                # Resolve path relative to cwd if not absolute
                full_path = os.path.join(cwd, path) if not os.path.isabs(path) else path
                
                if not os.path.exists(full_path):
                    result.append(f"{path}: No such file or directory")
                    continue
                
                if summarize:
                    # Only show total for the path
                    total_size = FileSystemUtils._get_dir_size(full_path)
                    size_str = FileSystemUtils._format_size(total_size) if human_readable else str(total_size)
                    result.append(f"{size_str}\t{path}")
                else:
                    # Show sizes for subdirectories
                    for root, dirs, files in os.walk(full_path):
                        # Check depth
                        if max_depth is not None:
                            rel_path = os.path.relpath(root, full_path)
                            if rel_path == '.':
                                current_depth = 0
                            else:
                                current_depth = rel_path.count(os.sep) + 1
                            
                            if current_depth > max_depth:
                                continue
                        
                        # Get size of this directory
                        dir_size = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))
                        
                        # Format size
                        size_str = FileSystemUtils._format_size(dir_size) if human_readable else str(dir_size)
                        
                        # Display relative path
                        rel_path = os.path.relpath(root, cwd)
                        result.append(f"{size_str}\t{rel_path}")
            
            except Exception as e:
                result.append(f"Error getting usage for {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def _get_dir_size(path):
        """Get total size of a directory"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
        return total_size
    
    @staticmethod
    def do_chmod(fs, cwd, arg):
        """Change file mode bits
        
        Usage: chmod [options] MODE FILE...
        
        Options:
          -R, --recursive   Change files and directories recursively
          
        Examples:
          chmod 755 script.py
          chmod -R 644 /var/www
        """
        args = shlex.split(arg)
        if len(args) < 2:
            return FileSystemUtils.do_chmod.__doc__
        
        # Parse options
        recursive = False
        
        # Extract options
        while args and args[0].startswith('-'):
            if args[0] in ['-R', '--recursive']:
                recursive = True
            else:
                return f"Unknown option: {args[0]}"
            args = args[1:]
        
        if len(args) < 2:
            return "Missing mode or file"
        
        mode_str = args[0]
        files = args[1:]
        
        # Parse mode
        try:
            mode = int(mode_str, 8)
        except ValueError:
            return f"Invalid mode: {mode_str}"
        
        result = []
        
        for file in files:
            try:
                # Resolve path relative to cwd if not absolute
                full_path = os.path.join(cwd, file) if not os.path.isabs(file) else file
                
                if not os.path.exists(full_path):
                    result.append(f"{file}: No such file or directory")
                    continue
                
                if recursive and os.path.isdir(full_path):
                    # Change permissions recursively
                    for root, dirs, files in os.walk(full_path):
                        for d in dirs:
                            os.chmod(os.path.join(root, d), mode)
                        for f in files:
                            os.chmod(os.path.join(root, f), mode)
                
                # Change permissions for the file/directory itself
                os.chmod(full_path, mode)
                result.append(f"Changed mode of '{file}' to {mode_str}")
            
            except Exception as e:
                result.append(f"Error changing mode of {file}: {e}")
        
        return "\n".join(result)

def register_commands(shell):
    """Register all file system utility commands with the KOS shell."""
    
    # Register the find command
    def do_find(self, arg):
        """Search for files in a directory hierarchy"""
        try:
            result = FileSystemUtils.do_find(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in find command: {e}")
            print(f"find: {str(e)}")
    
    # Register the grep command
    def do_grep(self, arg):
        """Search for PATTERN in files"""
        try:
            result = FileSystemUtils.do_grep(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in grep command: {e}")
            print(f"grep: {str(e)}")
    
    # Register the df command
    def do_df(self, arg):
        """Report file system disk space usage"""
        try:
            result = FileSystemUtils.do_df(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in df command: {e}")
            print(f"df: {str(e)}")
    
    # Register the du command
    def do_du(self, arg):
        """Estimate file space usage"""
        try:
            result = FileSystemUtils.do_du(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in du command: {e}")
            print(f"du: {str(e)}")
    
    # Register the chmod command
    def do_chmod(self, arg):
        """Change file mode bits"""
        try:
            result = FileSystemUtils.do_chmod(self.fs, self.fs.cwd, arg)
            if result:
                print(result)
        except Exception as e:
            logger.error(f"Error in chmod command: {e}")
            print(f"chmod: {str(e)}")
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_find', do_find)
    setattr(shell.__class__, 'do_grep', do_grep)
    setattr(shell.__class__, 'do_df', do_df)
    setattr(shell.__class__, 'do_du', do_du)
    setattr(shell.__class__, 'do_chmod', do_chmod)

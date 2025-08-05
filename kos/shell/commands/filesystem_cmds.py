"""
Filesystem Command Interface for KOS

This module provides shell commands that interface with the KOS core filesystem implementation,
allowing users to manage filesystems, mount points, and perform various file operations.
"""

import os
import shlex
import logging
import argparse
import time
from typing import List, Dict, Any, Optional, Tuple, Union

# Import KOS components
from kos.core import filesystem
from kos.core.filesystem import FileSystemType, FileInfo, FileType

# Set up logging
logger = logging.getLogger('KOS.shell.commands.filesystem_cmds')


class FilesystemCommands:
    """Filesystem-related commands for KOS shell"""
    
    @staticmethod
    def do_fsinfo(fs, cwd, arg):
        """
        Display filesystem information
        
        Usage: fsinfo [options] [path]
        
        Options:
          -m, --mount-points  Show mount points
          -f, --filesystems   Show filesystem types
          -d, --details       Show detailed information
          
        Examples:
          fsinfo              Show basic filesystem information
          fsinfo -m           Show mount points
          fsinfo -f           Show filesystem types
          fsinfo -d /home     Show detailed information for /home
        """
        parser = argparse.ArgumentParser(prog='fsinfo', add_help=False)
        parser.add_argument('-m', '--mount-points', action='store_true', help='Show mount points')
        parser.add_argument('-f', '--filesystems', action='store_true', help='Show filesystem types')
        parser.add_argument('-d', '--details', action='store_true', help='Show detailed information')
        parser.add_argument('path', nargs='?', default=None, help='Path to show information for')
        
        try:
            args = parser.parse_args(shlex.split(arg))
        except Exception:
            return FilesystemCommands.do_fsinfo.__doc__
        
        # Initialize filesystem if not already initialized
        if not hasattr(filesystem, '_fs_state') or not filesystem._fs_state.get('initialized', False):
            filesystem.initialize()
        
        result = []
        
        # Basic filesystem information
        if not (args.mount_points or args.filesystems or args.details):
            result.append("Filesystem Information:")
            result.append("-" * 20)
            
            # Show registered filesystem types
            fs_types = list(filesystem.fs_manager._fs_state['registered_filesystems'].keys())
            result.append(f"Registered filesystem types: {', '.join(t.value for t in fs_types)}")
            
            # Show mount points
            mount_points = filesystem.get_mount_points()
            result.append(f"Number of mount points: {len(mount_points)}")
            
            # Show default filesystem type
            default_fs = filesystem.fs_manager._fs_state.get('default_fs', None)
            if default_fs:
                result.append(f"Default filesystem type: {default_fs.value}")
            
            # Show if root filesystem is mounted
            root_fs = filesystem.fs_manager._fs_state.get('root_fs', None)
            result.append(f"Root filesystem mounted: {'Yes' if root_fs else 'No'}")
        
        # Show mount points
        if args.mount_points:
            result.append("\nMount Points:")
            result.append("-" * 20)
            
            mounted_filesystems = filesystem.get_mounted_filesystems()
            
            if not mounted_filesystems:
                result.append("No filesystems mounted")
            else:
                result.append(f"{'Mount Point':<20} {'Type':<15} {'Name':<20}")
                result.append("-" * 55)
                
                for mount_point, fs_info in mounted_filesystems.items():
                    result.append(f"{mount_point:<20} {fs_info['type']:<15} {fs_info['name']:<20}")
        
        # Show filesystem types
        if args.filesystems:
            result.append("\nFilesystem Types:")
            result.append("-" * 20)
            
            registered = filesystem.fs_manager._fs_state['registered_filesystems']
            
            if not registered:
                result.append("No filesystem types registered")
            else:
                result.append(f"{'Type':<15} {'Implementation':<30}")
                result.append("-" * 45)
                
                for fs_type, fs_class in registered.items():
                    result.append(f"{fs_type.value:<15} {fs_class.__name__:<30}")
        
        # Show detailed information for a path
        if args.details:
            path = args.path or cwd
            
            result.append(f"\nDetailed Information for {path}:")
            result.append("-" * 30)
            
            try:
                # Find the filesystem and mount point for this path
                mount_point = None
                for mp in filesystem.get_mount_points():
                    if path == mp or path.startswith(mp + '/'):
                        mount_point = mp
                        break
                
                if not mount_point:
                    return f"No filesystem mounted for path: {path}"
                
                fs_info = filesystem.get_mounted_filesystems().get(mount_point)
                
                result.append(f"Mount point: {mount_point}")
                result.append(f"Filesystem type: {fs_info['type']}")
                result.append(f"Filesystem name: {fs_info['name']}")
                
                # Get file info if path exists
                if filesystem.file_exists(path):
                    file_info = filesystem.get_file_info(path)
                    
                    result.append(f"\nFile information:")
                    result.append(f"  Name: {file_info.name}")
                    result.append(f"  Type: {file_info.type.value}")
                    result.append(f"  Size: {FilesystemCommands._format_size(file_info.size)}")
                    result.append(f"  Created: {FilesystemCommands._format_time(file_info.created)}")
                    result.append(f"  Modified: {FilesystemCommands._format_time(file_info.modified)}")
                    result.append(f"  Accessed: {FilesystemCommands._format_time(file_info.accessed)}")
                    result.append(f"  Owner: {file_info.owner}")
                    result.append(f"  Group: {file_info.group}")
                    result.append(f"  Permissions: {FilesystemCommands._format_permissions(file_info.permissions)}")
                    
                    if file_info.type == FileType.DIRECTORY:
                        # List directory contents
                        contents = filesystem.list_directory(path)
                        result.append(f"\nDirectory contents ({len(contents)} items):")
                        
                        if contents:
                            result.append(f"{'Name':<30} {'Type':<10} {'Size':<10} {'Modified':<20}")
                            result.append("-" * 70)
                            
                            for item in contents:
                                result.append(f"{item.name:<30} {item.type.value:<10} "
                                            f"{FilesystemCommands._format_size(item.size):<10} "
                                            f"{FilesystemCommands._format_time(item.modified):<20}")
                else:
                    result.append(f"\nPath does not exist: {path}")
            
            except Exception as e:
                result.append(f"Error getting details for {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_mount(fs, cwd, arg):
        """
        Mount a filesystem
        
        Usage: mount [options] [device] [mount_point]
        
        Options:
          -t, --type=TYPE     Filesystem type (memory, disk, network, virtual, user)
          -n, --name=NAME     Filesystem name
          
        Examples:
          mount                   Show mounted filesystems
          mount -t memory /mnt    Mount a memory filesystem at /mnt
          mount -t disk /dev/sda1 /mnt  Mount a disk filesystem at /mnt
        """
        # Parse arguments
        args = shlex.split(arg)
        
        # Default values
        fs_type = None
        fs_name = None
        device = None
        mount_point = None
        
        # If no arguments, show mounted filesystems
        if not args:
            mounted = filesystem.get_mounted_filesystems()
            
            if not mounted:
                return "No filesystems mounted"
            
            result = ["Mounted filesystems:"]
            result.append(f"{'Mount Point':<20} {'Type':<15} {'Name':<20}")
            result.append("-" * 55)
            
            for mp, info in mounted.items():
                result.append(f"{mp:<20} {info['type']:<15} {info['name']:<20}")
            
            return "\n".join(result)
        
        # Parse options
        i = 0
        while i < len(args):
            if args[i] in ['-t', '--type'] and i + 1 < len(args):
                fs_type = args[i + 1]
                i += 2
            elif args[i].startswith('--type='):
                fs_type = args[i][7:]
                i += 1
            elif args[i] in ['-n', '--name'] and i + 1 < len(args):
                fs_name = args[i + 1]
                i += 2
            elif args[i].startswith('--name='):
                fs_name = args[i][7:]
                i += 1
            else:
                # Positional arguments
                if not device:
                    device = args[i]
                elif not mount_point:
                    mount_point = args[i]
                i += 1
        
        # Validate arguments
        if not mount_point:
            if device:
                # If only one positional argument, assume it's the mount point
                mount_point = device
                device = None
            else:
                return "Missing mount point"
        
        # Normalize mount point
        mount_point = filesystem.normalize_path(mount_point)
        
        # Default to memory filesystem if not specified
        if not fs_type:
            fs_type = 'memory'
        
        # Convert string to FileSystemType
        try:
            fs_type_enum = FileSystemType(fs_type.lower())
        except ValueError:
            return f"Invalid filesystem type: {fs_type}. Valid types: {', '.join(t.value for t in FileSystemType)}"
        
        # Use mount point as name if not specified
        if not fs_name:
            fs_name = f"fs_{mount_point.replace('/', '_')}"
        
        # Mount the filesystem
        config = {'device': device} if device else None
        
        try:
            success = filesystem.mount(fs_type_enum, mount_point, fs_name, config)
            
            if success:
                return f"Mounted {fs_type} filesystem at {mount_point}"
            else:
                return f"Failed to mount filesystem at {mount_point}"
        
        except Exception as e:
            return f"Error mounting filesystem: {e}"
    
    @staticmethod
    def do_umount(fs, cwd, arg):
        """
        Unmount a filesystem
        
        Usage: umount [mount_point]
        
        Examples:
          umount /mnt    Unmount the filesystem at /mnt
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing mount point"
        
        mount_point = args[0]
        
        # Normalize mount point
        mount_point = filesystem.normalize_path(mount_point)
        
        try:
            success = filesystem.unmount(mount_point)
            
            if success:
                return f"Unmounted filesystem at {mount_point}"
            else:
                return f"Failed to unmount filesystem at {mount_point}"
        
        except Exception as e:
            return f"Error unmounting filesystem: {e}"
    
    @staticmethod
    def do_mkdir(fs, cwd, arg):
        """
        Create a directory
        
        Usage: mkdir [options] DIRECTORY...
        
        Options:
          -p, --parents    Create parent directories as needed
          
        Examples:
          mkdir test       Create directory 'test'
          mkdir -p a/b/c   Create directory 'a/b/c' and parents
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing directory name"
        
        # Parse options
        create_parents = False
        dirs = []
        
        for arg in args:
            if arg in ['-p', '--parents']:
                create_parents = True
            elif arg.startswith('-'):
                return f"Unknown option: {arg}"
            else:
                dirs.append(arg)
        
        if not dirs:
            return "Missing directory name"
        
        result = []
        
        for dir_name in dirs:
            # Resolve path
            if not filesystem.is_absolute_path(dir_name):
                path = filesystem.resolve_path(cwd, dir_name)
            else:
                path = dir_name
            
            try:
                if create_parents:
                    # Create parent directories as needed
                    components = filesystem.get_path_components(path)
                    
                    # Skip the first component if it's the root
                    start_idx = 1 if components and components[0] == '/' else 0
                    
                    # Create each directory in the path
                    current_path = '/' if components and components[0] == '/' else ''
                    
                    for i in range(start_idx, len(components)):
                        current_path = filesystem.join_path(current_path, components[i])
                        
                        if not filesystem.file_exists(current_path):
                            filesystem.create_directory(current_path)
                    
                    result.append(f"Created directory: {path}")
                else:
                    # Create just the specified directory
                    if filesystem.create_directory(path):
                        result.append(f"Created directory: {path}")
                    else:
                        result.append(f"Failed to create directory: {path}")
            
            except Exception as e:
                result.append(f"Error creating directory {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_rmdir(fs, cwd, arg):
        """
        Remove empty directories
        
        Usage: rmdir [options] DIRECTORY...
        
        Options:
          -p, --parents    Remove DIRECTORY and its ancestors
          
        Examples:
          rmdir test       Remove directory 'test'
          rmdir -p a/b/c   Remove 'a/b/c', then 'a/b', then 'a'
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing directory name"
        
        # Parse options
        remove_parents = False
        dirs = []
        
        for arg in args:
            if arg in ['-p', '--parents']:
                remove_parents = True
            elif arg.startswith('-'):
                return f"Unknown option: {arg}"
            else:
                dirs.append(arg)
        
        if not dirs:
            return "Missing directory name"
        
        result = []
        
        for dir_name in dirs:
            # Resolve path
            if not filesystem.is_absolute_path(dir_name):
                path = filesystem.resolve_path(cwd, dir_name)
            else:
                path = dir_name
            
            try:
                if not filesystem.file_exists(path):
                    result.append(f"Directory does not exist: {path}")
                    continue
                
                if not filesystem.is_directory(path):
                    result.append(f"Not a directory: {path}")
                    continue
                
                if filesystem.delete_directory(path):
                    result.append(f"Removed directory: {path}")
                    
                    # Remove parent directories if requested
                    if remove_parents:
                        parent = filesystem.get_parent_directory(path)
                        
                        while parent and parent != '/' and parent != '.':
                            # Only remove if empty
                            if filesystem.delete_directory(parent):
                                result.append(f"Removed parent directory: {parent}")
                                parent = filesystem.get_parent_directory(parent)
                            else:
                                break
                else:
                    result.append(f"Failed to remove directory: {path}")
            
            except Exception as e:
                result.append(f"Error removing directory {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_touch(fs, cwd, arg):
        """
        Update the access and modification times of a file
        
        Usage: touch [options] FILE...
        
        Options:
          -c, --no-create    Do not create files that don't exist
          
        Examples:
          touch file.txt     Create or update 'file.txt'
          touch -c file.txt  Update 'file.txt' only if it exists
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing file name"
        
        # Parse options
        no_create = False
        files = []
        
        for arg in args:
            if arg in ['-c', '--no-create']:
                no_create = True
            elif arg.startswith('-'):
                return f"Unknown option: {arg}"
            else:
                files.append(arg)
        
        if not files:
            return "Missing file name"
        
        result = []
        
        for file_name in files:
            # Resolve path
            if not filesystem.is_absolute_path(file_name):
                path = filesystem.resolve_path(cwd, file_name)
            else:
                path = file_name
            
            try:
                if filesystem.file_exists(path):
                    # Update access and modification times
                    now = time.time()
                    filesystem.set_file_info(path, {
                        'accessed': now,
                        'modified': now
                    })
                    result.append(f"Updated: {path}")
                elif not no_create:
                    # Create the file
                    if filesystem.create_file(path):
                        result.append(f"Created: {path}")
                    else:
                        result.append(f"Failed to create: {path}")
                else:
                    result.append(f"File does not exist (not created): {path}")
            
            except Exception as e:
                result.append(f"Error touching file {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_cat(fs, cwd, arg):
        """
        Concatenate and display file contents
        
        Usage: cat [options] FILE...
        
        Options:
          -n, --number    Number all output lines
          
        Examples:
          cat file.txt         Display contents of 'file.txt'
          cat -n file1 file2   Display contents with line numbers
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing file name"
        
        # Parse options
        number_lines = False
        files = []
        
        for arg in args:
            if arg in ['-n', '--number']:
                number_lines = True
            elif arg.startswith('-'):
                return f"Unknown option: {arg}"
            else:
                files.append(arg)
        
        if not files:
            return "Missing file name"
        
        result = []
        
        for file_name in files:
            # Resolve path
            if not filesystem.is_absolute_path(file_name):
                path = filesystem.resolve_path(cwd, file_name)
            else:
                path = file_name
            
            try:
                if not filesystem.file_exists(path):
                    result.append(f"File does not exist: {path}")
                    continue
                
                if filesystem.is_directory(path):
                    result.append(f"Is a directory: {path}")
                    continue
                
                # Read file contents
                content = filesystem.read_entire_file(path)
                
                # If we have multiple files, add a header
                if len(files) > 1:
                    result.append(f"\n==> {path} <==\n")
                
                # Process content
                if number_lines:
                    # Add line numbers
                    lines = content.decode('utf-8', errors='replace').splitlines()
                    for i, line in enumerate(lines, 1):
                        result.append(f"{i:6}  {line}")
                else:
                    # Add content as is
                    result.append(content.decode('utf-8', errors='replace'))
            
            except Exception as e:
                result.append(f"Error reading file {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def do_rm(fs, cwd, arg):
        """
        Remove files or directories
        
        Usage: rm [options] FILE...
        
        Options:
          -r, --recursive    Remove directories and their contents recursively
          -f, --force        Ignore nonexistent files and never prompt
          
        Examples:
          rm file.txt        Remove file 'file.txt'
          rm -r directory    Remove directory 'directory' and its contents
        """
        args = shlex.split(arg)
        
        if not args:
            return "Missing file name"
        
        # Parse options
        recursive = False
        force = False
        files = []
        
        for arg in args:
            if arg in ['-r', '--recursive']:
                recursive = True
            elif arg in ['-f', '--force']:
                force = True
            elif arg.startswith('-'):
                if arg == '-rf' or arg == '-fr':
                    recursive = True
                    force = True
                else:
                    return f"Unknown option: {arg}"
            else:
                files.append(arg)
        
        if not files:
            return "Missing file name"
        
        result = []
        
        for file_name in files:
            # Resolve path
            if not filesystem.is_absolute_path(file_name):
                path = filesystem.resolve_path(cwd, file_name)
            else:
                path = file_name
            
            try:
                if not filesystem.file_exists(path):
                    if not force:
                        result.append(f"File does not exist: {path}")
                    continue
                
                if filesystem.is_directory(path):
                    if recursive:
                        # Recursive delete of directory
                        # First get directory contents
                        items = filesystem.list_directory(path)
                        
                        # Recursively delete each item
                        for item in items:
                            item_path = filesystem.join_path(path, item.name)
                            
                            if item.type == FileType.DIRECTORY:
                                # Recursive delete of subdirectory
                                FilesystemCommands.do_rm(fs, cwd, f"-rf {item_path}")
                            else:
                                # Delete file
                                filesystem.delete_file(item_path)
                        
                        # Delete the directory itself
                        if filesystem.delete_directory(path):
                            result.append(f"Removed directory: {path}")
                        else:
                            result.append(f"Failed to remove directory: {path}")
                    else:
                        result.append(f"Is a directory (use -r to remove): {path}")
                else:
                    # Delete file
                    if filesystem.delete_file(path):
                        result.append(f"Removed file: {path}")
                    else:
                        result.append(f"Failed to remove file: {path}")
            
            except Exception as e:
                if not force:
                    result.append(f"Error removing {path}: {e}")
        
        return "\n".join(result)
    
    @staticmethod
    def _format_size(size):
        """Format file size in human-readable format"""
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f} GB"
    
    @staticmethod
    def _format_time(timestamp):
        """Format timestamp in human-readable format"""
        try:
            # Convert timestamp to string representation
            return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        except Exception:
            return "Unknown"
    
    @staticmethod
    def _format_permissions(mode):
        """Format file permissions in octal and symbolic format"""
        octal = f"{mode:o}"
        
        # Convert to symbolic format (e.g., 'rwxr-xr--')
        symbolic = ""
        
        # Owner permissions
        symbolic += "r" if mode & 0o400 else "-"
        symbolic += "w" if mode & 0o200 else "-"
        symbolic += "x" if mode & 0o100 else "-"
        
        # Group permissions
        symbolic += "r" if mode & 0o40 else "-"
        symbolic += "w" if mode & 0o20 else "-"
        symbolic += "x" if mode & 0o10 else "-"
        
        # Other permissions
        symbolic += "r" if mode & 0o4 else "-"
        symbolic += "w" if mode & 0o2 else "-"
        symbolic += "x" if mode & 0o1 else "-"
        
        return f"{octal} ({symbolic})"


def register_commands(shell):
    """Register filesystem commands with the shell"""
    
    # Register the fsinfo command
    def do_fsinfo(self, arg):
        """Display filesystem information"""
        result = FilesystemCommands.do_fsinfo(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the mount command
    def do_mount(self, arg):
        """Mount a filesystem"""
        result = FilesystemCommands.do_mount(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the umount command
    def do_umount(self, arg):
        """Unmount a filesystem"""
        result = FilesystemCommands.do_umount(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the mkdir command
    def do_mkdir(self, arg):
        """Create a directory"""
        result = FilesystemCommands.do_mkdir(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the rmdir command
    def do_rmdir(self, arg):
        """Remove empty directories"""
        result = FilesystemCommands.do_rmdir(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the touch command
    def do_touch(self, arg):
        """Update file access and modification times"""
        result = FilesystemCommands.do_touch(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the cat command
    def do_cat(self, arg):
        """Concatenate and display file contents"""
        result = FilesystemCommands.do_cat(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Register the rm command
    def do_rm(self, arg):
        """Remove files or directories"""
        result = FilesystemCommands.do_rm(self.fs, self.fs.current_path, arg)
        if result:
            print(result)
    
    # Attach the command methods to the shell
    setattr(shell.__class__, 'do_fsinfo', do_fsinfo)
    setattr(shell.__class__, 'do_mount', do_mount)
    setattr(shell.__class__, 'do_umount', do_umount)
    setattr(shell.__class__, 'do_mkdir', do_mkdir)
    setattr(shell.__class__, 'do_rmdir', do_rmdir)
    setattr(shell.__class__, 'do_touch', do_touch)
    setattr(shell.__class__, 'do_cat', do_cat)
    setattr(shell.__class__, 'do_rm', do_rm)

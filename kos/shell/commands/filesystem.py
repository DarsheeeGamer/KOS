"""
Filesystem commands for KOS Shell
"""

import os
import shlex
import types
from typing import List

def register_commands(shell):
    """Register filesystem commands with shell"""
    
    def do_pwd(self, arg):
        """Print working directory"""
        print(self.cwd)
    
    def do_cd(self, arg):
        """Change directory
        Usage: cd [directory]"""
        if not arg:
            # Go to home
            self.cwd = f'/home/{self.klayer.get_current_user()}' if self.klayer else '/home/user'
        else:
            # Resolve path
            if arg.startswith('/'):
                new_path = os.path.normpath(arg)
            else:
                new_path = os.path.normpath(os.path.join(self.cwd, arg))
            
            # Check if directory exists
            if self.vfs and self.vfs.exists(new_path) and self.vfs.isdir(new_path):
                self.cwd = new_path
            else:
                print(f"cd: {arg}: No such directory")
    
    def do_ls(self, arg):
        """List directory contents
        Usage: ls [directory] [-l] [-a]"""
        args = shlex.split(arg)
        
        # Parse options
        show_hidden = '-a' in args
        long_format = '-l' in args
        
        # Get directory to list
        dirs = [a for a in args if not a.startswith('-')]
        target = dirs[0] if dirs else self.cwd
        
        # Resolve path
        if not target.startswith('/'):
            target = os.path.normpath(os.path.join(self.cwd, target))
        
        if not self.vfs:
            print("VFS not available")
            return
        
        try:
            entries = self.vfs.listdir(target)
            
            if not show_hidden:
                entries = [e for e in entries if not e.startswith('.')]
            
            if long_format:
                # Detailed listing
                for entry in sorted(entries):
                    path = os.path.join(target, entry)
                    stat = self.vfs.stat(path)
                    
                    # Format mode
                    if self.vfs.isdir(path):
                        type_char = 'd'
                    else:
                        type_char = '-'
                    
                    # Format size
                    size = stat.st_size
                    
                    print(f"{type_char}rwxr-xr-x  1 user user  {size:8} {entry}")
            else:
                # Simple listing
                for entry in sorted(entries):
                    path = os.path.join(target, entry)
                    if self.vfs.isdir(path):
                        print(f"{entry}/")
                    else:
                        print(entry)
        
        except Exception as e:
            print(f"ls: {target}: {e}")
    
    def do_cat(self, arg):
        """Display file contents
        Usage: cat <file>"""
        if not arg:
            print("Usage: cat <file>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        # Resolve path
        if not arg.startswith('/'):
            path = os.path.normpath(os.path.join(self.cwd, arg))
        else:
            path = arg
        
        try:
            with self.vfs.open(path, 'r') as f:
                content = f.read()
                print(content.decode('utf-8', errors='replace'), end='')
        except Exception as e:
            print(f"cat: {arg}: {e}")
    
    def do_mkdir(self, arg):
        """Create directory
        Usage: mkdir <directory>"""
        if not arg:
            print("Usage: mkdir <directory>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        # Resolve path
        if not arg.startswith('/'):
            path = os.path.normpath(os.path.join(self.cwd, arg))
        else:
            path = arg
        
        try:
            self.vfs.mkdir(path)
            print(f"Created directory: {path}")
        except Exception as e:
            print(f"mkdir: {arg}: {e}")
    
    def do_rm(self, arg):
        """Remove file or directory
        Usage: rm [-r] <path>"""
        args = shlex.split(arg)
        
        if not args:
            print("Usage: rm [-r] <path>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        recursive = '-r' in args
        paths = [a for a in args if not a.startswith('-')]
        
        for path_arg in paths:
            # Resolve path
            if not path_arg.startswith('/'):
                path = os.path.normpath(os.path.join(self.cwd, path_arg))
            else:
                path = path_arg
            
            try:
                if self.vfs.isdir(path):
                    if recursive:
                        # TODO: Implement recursive removal
                        self.vfs.rmdir(path)
                    else:
                        print(f"rm: {path_arg}: Is a directory (use -r)")
                else:
                    self.vfs.unlink(path)
                    print(f"Removed: {path}")
            except Exception as e:
                print(f"rm: {path_arg}: {e}")
    
    def do_touch(self, arg):
        """Create empty file
        Usage: touch <file>"""
        if not arg:
            print("Usage: touch <file>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        # Resolve path
        if not arg.startswith('/'):
            path = os.path.normpath(os.path.join(self.cwd, arg))
        else:
            path = arg
        
        try:
            with self.vfs.open(path, 'w') as f:
                pass  # Create empty file
            print(f"Created: {path}")
        except Exception as e:
            print(f"touch: {arg}: {e}")
    
    def do_cp(self, arg):
        """Copy file
        Usage: cp <source> <dest>"""
        args = shlex.split(arg)
        
        if len(args) != 2:
            print("Usage: cp <source> <dest>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        src, dst = args
        
        # Resolve paths
        if not src.startswith('/'):
            src = os.path.normpath(os.path.join(self.cwd, src))
        if not dst.startswith('/'):
            dst = os.path.normpath(os.path.join(self.cwd, dst))
        
        try:
            # Read source
            with self.vfs.open(src, 'r') as f:
                content = f.read()
            
            # Write to destination
            with self.vfs.open(dst, 'w') as f:
                f.write(content)
            
            print(f"Copied {src} to {dst}")
        except Exception as e:
            print(f"cp: {e}")
    
    def do_mv(self, arg):
        """Move/rename file
        Usage: mv <source> <dest>"""
        args = shlex.split(arg)
        
        if len(args) != 2:
            print("Usage: mv <source> <dest>")
            return
        
        if not self.vfs:
            print("VFS not available")
            return
        
        src, dst = args
        
        # Resolve paths
        if not src.startswith('/'):
            src = os.path.normpath(os.path.join(self.cwd, src))
        if not dst.startswith('/'):
            dst = os.path.normpath(os.path.join(self.cwd, dst))
        
        try:
            # Read source
            with self.vfs.open(src, 'r') as f:
                content = f.read()
            
            # Write to destination
            with self.vfs.open(dst, 'w') as f:
                f.write(content)
            
            # Remove source
            self.vfs.unlink(src)
            
            print(f"Moved {src} to {dst}")
        except Exception as e:
            print(f"mv: {e}")
    
    def do_find(self, arg):
        """Find files
        Usage: find [directory] -name <pattern>"""
        # Simple find implementation
        if not self.vfs:
            print("VFS not available")
            return
        
        # TODO: Implement proper find
        print("Find command not fully implemented yet")
    
    # Register all commands using MethodType
    shell.do_pwd = types.MethodType(do_pwd, shell)
    shell.do_cd = types.MethodType(do_cd, shell)
    shell.do_ls = types.MethodType(do_ls, shell)
    shell.do_cat = types.MethodType(do_cat, shell)
    shell.do_mkdir = types.MethodType(do_mkdir, shell)
    shell.do_rm = types.MethodType(do_rm, shell)
    shell.do_touch = types.MethodType(do_touch, shell)
    shell.do_cp = types.MethodType(do_cp, shell)
    shell.do_mv = types.MethodType(do_mv, shell)
    shell.do_find = types.MethodType(do_find, shell)
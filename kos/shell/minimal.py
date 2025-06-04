"""
Minimal Shell Fallback for KOS
==============================

A basic shell implementation that provides essential functionality
when the main KOS shell cannot be initialized.
"""

import cmd
import os
import sys
import logging
from typing import List, Optional

logger = logging.getLogger('KOS.shell.minimal')

class MinimalShell(cmd.Cmd):
    """Minimal shell implementation for KOS fallback"""
    
    intro = """
KOS Minimal Shell
=================
Warning: Running in minimal mode due to initialization issues.
Basic commands available. Type 'help' for available commands.
"""
    
    prompt = 'kos-minimal> '
    
    def __init__(self):
        super().__init__()
        self.current_dir = os.getcwd()
        logger.info("Minimal shell initialized")
    
    def do_help(self, arg):
        """Show available commands"""
        if arg:
            super().do_help(arg)
        else:
            print("Available commands:")
            print("  help [command]  - Show help for command")
            print("  exit, quit      - Exit the shell")
            print("  pwd             - Show current directory")
            print("  ls [dir]        - List directory contents")
            print("  cd <dir>        - Change directory")
            print("  echo <text>     - Echo text")
            print("  status          - Show system status")
            print("  version         - Show version information")
            print("  clear           - Clear screen")
    
    def do_exit(self, arg):
        """Exit the shell"""
        print("Goodbye!")
        return True
    
    def do_quit(self, arg):
        """Exit the shell"""
        return self.do_exit(arg)
    
    def do_pwd(self, arg):
        """Show current working directory"""
        print(self.current_dir)
    
    def do_ls(self, arg):
        """List directory contents"""
        try:
            directory = arg.strip() if arg.strip() else self.current_dir
            
            if not os.path.exists(directory):
                print(f"ls: cannot access '{directory}': No such file or directory")
                return
            
            if not os.path.isdir(directory):
                print(f"ls: {directory}: Not a directory")
                return
            
            items = os.listdir(directory)
            if not items:
                return
            
            # Simple listing
            for item in sorted(items):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    print(f"{item}/")
                else:
                    print(item)
                    
        except PermissionError:
            print(f"ls: cannot open directory '{directory}': Permission denied")
        except Exception as e:
            print(f"ls: error listing directory: {e}")
    
    def do_cd(self, arg):
        """Change directory"""
        try:
            if not arg.strip():
                # Go to home directory
                new_dir = os.path.expanduser("~")
            else:
                new_dir = arg.strip()
            
            # Handle relative paths
            if not os.path.isabs(new_dir):
                new_dir = os.path.join(self.current_dir, new_dir)
            
            # Normalize the path
            new_dir = os.path.normpath(new_dir)
            
            if not os.path.exists(new_dir):
                print(f"cd: no such file or directory: {new_dir}")
                return
            
            if not os.path.isdir(new_dir):
                print(f"cd: not a directory: {new_dir}")
                return
            
            self.current_dir = new_dir
            # Also change the actual working directory
            os.chdir(new_dir)
            
        except PermissionError:
            print(f"cd: permission denied: {arg}")
        except Exception as e:
            print(f"cd: error changing directory: {e}")
    
    def do_echo(self, arg):
        """Echo text to output"""
        print(arg)
    
    def do_status(self, arg):
        """Show minimal system status"""
        print("KOS Minimal Shell Status:")
        print(f"  Current Directory: {self.current_dir}")
        print(f"  Python Version: {sys.version}")
        print(f"  Platform: {sys.platform}")
        print("  Status: Running in minimal mode")
        print("  Note: Full KOS functionality not available")
    
    def do_version(self, arg):
        """Show version information"""
        print("KOS Minimal Shell v1.0.0")
        print("Fallback shell for KOS when main shell is unavailable")
    
    def do_clear(self, arg):
        """Clear the screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def do_env(self, arg):
        """Show environment variables"""
        if arg.strip():
            # Show specific environment variable
            var_name = arg.strip()
            value = os.environ.get(var_name)
            if value is not None:
                print(f"{var_name}={value}")
            else:
                print(f"env: {var_name}: not found")
        else:
            # Show all environment variables
            for key, value in sorted(os.environ.items()):
                print(f"{key}={value}")
    
    def do_cat(self, arg):
        """Display file contents"""
        if not arg.strip():
            print("cat: missing file argument")
            return
        
        file_path = arg.strip()
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.current_dir, file_path)
        
        try:
            if not os.path.exists(file_path):
                print(f"cat: {arg}: No such file or directory")
                return
            
            if not os.path.isfile(file_path):
                print(f"cat: {arg}: Is a directory")
                return
            
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
                print(content, end='')
                
        except PermissionError:
            print(f"cat: {arg}: Permission denied")
        except Exception as e:
            print(f"cat: error reading file: {e}")
    
    def do_mkdir(self, arg):
        """Create directory"""
        if not arg.strip():
            print("mkdir: missing directory argument")
            return
        
        dir_path = arg.strip()
        if not os.path.isabs(dir_path):
            dir_path = os.path.join(self.current_dir, dir_path)
        
        try:
            os.makedirs(dir_path, exist_ok=False)
            print(f"Directory created: {dir_path}")
        except FileExistsError:
            print(f"mkdir: cannot create directory '{arg}': File exists")
        except PermissionError:
            print(f"mkdir: cannot create directory '{arg}': Permission denied")
        except Exception as e:
            print(f"mkdir: error creating directory: {e}")
    
    def do_rmdir(self, arg):
        """Remove empty directory"""
        if not arg.strip():
            print("rmdir: missing directory argument")
            return
        
        dir_path = arg.strip()
        if not os.path.isabs(dir_path):
            dir_path = os.path.join(self.current_dir, dir_path)
        
        try:
            os.rmdir(dir_path)
            print(f"Directory removed: {dir_path}")
        except FileNotFoundError:
            print(f"rmdir: failed to remove '{arg}': No such file or directory")
        except OSError as e:
            if e.errno == 39:  # Directory not empty
                print(f"rmdir: failed to remove '{arg}': Directory not empty")
            else:
                print(f"rmdir: failed to remove '{arg}': {e}")
        except Exception as e:
            print(f"rmdir: error removing directory: {e}")
    
    def do_touch(self, arg):
        """Create empty file or update timestamp"""
        if not arg.strip():
            print("touch: missing file argument")
            return
        
        file_path = arg.strip()
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.current_dir, file_path)
        
        try:
            # Create file if it doesn't exist, or update timestamp if it does
            with open(file_path, 'a'):
                pass
            print(f"File created/updated: {file_path}")
        except PermissionError:
            print(f"touch: cannot touch '{arg}': Permission denied")
        except Exception as e:
            print(f"touch: error creating/updating file: {e}")
    
    def default(self, line):
        """Handle unknown commands"""
        cmd_name = line.split()[0] if line else ""
        print(f"kos-minimal: {cmd_name}: command not found")
        print("Type 'help' for available commands")
    
    def emptyline(self):
        """Handle empty input"""
        pass
    
    def cmdloop(self, intro=None):
        """Custom command loop with better error handling"""
        try:
            super().cmdloop(intro)
        except KeyboardInterrupt:
            print("\nUse 'exit' or 'quit' to leave the shell")
            self.cmdloop()
        except EOFError:
            print("\nGoodbye!")
            return True
        except Exception as e:
            logger.error(f"Error in minimal shell: {e}")
            print(f"Shell error: {e}")
            print("Type 'exit' to quit")
            self.cmdloop()

# Export the class
__all__ = ['MinimalShell'] 
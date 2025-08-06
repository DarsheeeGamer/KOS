"""
KOS Shell
Clean, single shell implementation with modular commands
"""

import cmd
import os
import sys
import shlex
import readline
from typing import Optional, List
from pathlib import Path

class KOSShell(cmd.Cmd):
    """
    The ONE AND ONLY KOS Shell
    Clean, simple, working
    """
    
    intro = """
╔══════════════════════════════════════════════╗
║         KOS - Kaede Operating System         ║
║              Version 2.0 Clean               ║
╚══════════════════════════════════════════════╝
Type 'help' for available commands
Type 'exit' to quit
"""
    
    prompt = 'kos> '
    
    def __init__(self, vfs=None, klayer=None, kadvlayer=None, kpm=None, python_env=None):
        super().__init__()
        self.vfs = vfs
        self.klayer = klayer
        self.kadvlayer = kadvlayer
        self.kpm = kpm
        self.python_env = python_env
        
        # Current directory tracking
        self.cwd = '/'
        
        # Command history
        self.history_file = os.path.expanduser('~/.kos_history')
        self._load_history()
        
        # Load command modules
        self._load_commands()
    
    def _load_history(self):
        """Load command history"""
        try:
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
        except:
            pass
    
    def _save_history(self):
        """Save command history"""
        try:
            readline.write_history_file(self.history_file)
        except:
            pass
    
    def _load_commands(self):
        """Load modular commands"""
        # Import command modules
        from .commands import filesystem, packages, system
        
        # Register commands
        filesystem.register_commands(self)
        packages.register_commands(self)
        system.register_commands(self)
    
    def postcmd(self, stop, line):
        """After each command"""
        # Update prompt with current directory
        if self.cwd != '/':
            self.prompt = f'kos:{self.cwd}> '
        else:
            self.prompt = 'kos> '
        
        # Save history
        self._save_history()
        
        return stop
    
    def emptyline(self):
        """Do nothing on empty line"""
        pass
    
    def default(self, line):
        """Handle unknown commands"""
        print(f"Command not found: {line.split()[0]}")
        print("Type 'help' for available commands")
    
    # Built-in Commands
    
    def do_help(self, arg):
        """Show help for commands"""
        if arg:
            # Show help for specific command
            try:
                func = getattr(self, f'do_{arg}')
                print(func.__doc__ or f"No help available for '{arg}'")
            except AttributeError:
                print(f"No such command: {arg}")
        else:
            # Show all commands
            print("\nAvailable Commands:")
            print("=" * 40)
            
            commands = []
            for name in dir(self):
                if name.startswith('do_'):
                    cmd_name = name[3:]
                    if cmd_name not in ['EOF', 'shell']:
                        commands.append(cmd_name)
            
            # Group commands
            file_cmds = ['ls', 'cd', 'pwd', 'cat', 'mkdir', 'rm', 'cp', 'mv', 'touch', 'find']
            pkg_cmds = ['kpm', 'pip']
            sys_cmds = ['status', 'ps', 'services', 'info', 'clear', 'exit']
            
            print("\nFile System:")
            for cmd in file_cmds:
                if cmd in commands:
                    print(f"  {cmd:<10} - {self._get_short_help(cmd)}")
            
            print("\nPackage Management:")
            for cmd in pkg_cmds:
                if cmd in commands:
                    print(f"  {cmd:<10} - {self._get_short_help(cmd)}")
            
            print("\nSystem:")
            for cmd in sys_cmds:
                if cmd in commands:
                    print(f"  {cmd:<10} - {self._get_short_help(cmd)}")
            
            print("\nType 'help <command>' for detailed help")
    
    def _get_short_help(self, cmd):
        """Get short help for command"""
        try:
            func = getattr(self, f'do_{cmd}')
            doc = func.__doc__ or ""
            # Return first line only
            return doc.split('\n')[0].strip()
        except:
            return ""
    
    def do_clear(self, arg):
        """Clear the terminal screen"""
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def do_exit(self, arg):
        """Exit KOS shell"""
        print("Goodbye!")
        return True
    
    def do_quit(self, arg):
        """Exit KOS shell"""
        return self.do_exit(arg)
    
    def do_EOF(self, arg):
        """Handle Ctrl+D"""
        print()  # New line
        return self.do_exit(arg)
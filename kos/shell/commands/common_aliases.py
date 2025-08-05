"""
Common Unix Aliases and Shortcuts for KOS
=========================================

Provides familiar Unix command aliases and shortcuts to make KOS
more user-friendly for Unix/Linux users.
"""

import logging

logger = logging.getLogger('KOS.shell.common_aliases')

def register_commands(shell):
    """Register common Unix aliases and shortcuts"""
    
    def ll_command(shell_instance, args):
        """Long listing format (ls -l alias)"""
        return shell_instance.onecmd(f"ls -l {args}" if args else "ls -l")
    
    def la_command(shell_instance, args):
        """List all files including hidden (ls -la alias)"""
        return shell_instance.onecmd(f"ls -la {args}" if args else "ls -la")
    
    def l_command(shell_instance, args):
        """Simple list (ls alias)"""
        return shell_instance.onecmd(f"ls {args}" if args else "ls")
    
    def dot_dot_command(shell_instance, args):
        """Go up one directory (cd .. shortcut)"""
        return shell_instance.onecmd("cd ..")
    
    def dot_dot_dot_command(shell_instance, args):
        """Go up two directories (cd ../.. shortcut)"""
        return shell_instance.onecmd("cd ../..")
    
    def home_command(shell_instance, args):
        """Go to home directory (cd ~ shortcut)"""
        return shell_instance.onecmd("cd ~")
    
    def cls_command(shell_instance, args):
        """Clear screen (Windows-style clear)"""
        return shell_instance.onecmd("clear")
    
    def dir_command(shell_instance, args):
        """Directory listing (Windows-style ls)"""
        return shell_instance.onecmd(f"ls {args}" if args else "ls")
    
    def type_command(shell_instance, args):
        """Show file contents (Windows-style cat)"""
        if args:
            return shell_instance.onecmd(f"cat {args}")
        else:
            print("Usage: type filename")
            return False
    
    def copy_command(shell_instance, args):
        """Copy files (Windows-style cp)"""
        if args:
            return shell_instance.onecmd(f"cp {args}")
        else:
            print("Usage: copy source destination")
            return False
    
    def move_command(shell_instance, args):
        """Move files (Windows-style mv)"""
        if args:
            return shell_instance.onecmd(f"mv {args}")
        else:
            print("Usage: move source destination")
            return False
    
    def del_command(shell_instance, args):
        """Delete files (Windows-style rm)"""
        if args:
            return shell_instance.onecmd(f"rm {args}")
        else:
            print("Usage: del filename")
            return False
    
    def md_command(shell_instance, args):
        """Make directory (Windows-style mkdir)"""
        if args:
            return shell_instance.onecmd(f"mkdir {args}")
        else:
            print("Usage: md directory")
            return False
    
    def rd_command(shell_instance, args):
        """Remove directory (Windows-style rmdir)"""
        if args:
            return shell_instance.onecmd(f"rmdir {args}")
        else:
            print("Usage: rd directory")
            return False
    
    def exit_command(shell_instance, args):
        """Exit the shell"""
        return shell_instance.onecmd("quit")
    
    def logout_command(shell_instance, args):
        """Logout (same as exit)"""
        return shell_instance.onecmd("quit")
    
    def q_command(shell_instance, args):
        """Quick exit (q shortcut)"""
        return shell_instance.onecmd("quit")
    
    # Unix-style shortcuts and aliases
    unix_aliases = {
        'll': (ll_command, "Long listing format (ls -l)"),
        'la': (la_command, "List all files including hidden (ls -la)"),
        'l': (l_command, "Simple list (ls)"),
        '..': (dot_dot_command, "Go up one directory (cd ..)"),
        '...': (dot_dot_dot_command, "Go up two directories (cd ../..)"),
        '~': (home_command, "Go to home directory (cd ~)"),
    }
    
    # Windows-style compatibility
    windows_aliases = {
        'cls': (cls_command, "Clear screen (Windows-style)"),
        'dir': (dir_command, "Directory listing (Windows-style)"),
        'type': (type_command, "Show file contents (Windows-style)"),
        'copy': (copy_command, "Copy files (Windows-style)"),
        'move': (move_command, "Move files (Windows-style)"),
        'del': (del_command, "Delete files (Windows-style)"),
        'md': (md_command, "Make directory (Windows-style)"),
        'rd': (rd_command, "Remove directory (Windows-style)"),
    }
    
    # Common exit commands
    exit_aliases = {
        'exit': (exit_command, "Exit the shell"),
        'logout': (logout_command, "Logout (same as exit)"),
        'q': (q_command, "Quick exit"),
    }
    
    # Combine all aliases
    all_aliases = {**unix_aliases, **windows_aliases, **exit_aliases}
    
    # Register all aliases
    for alias_name, (alias_func, alias_help) in all_aliases.items():
        shell.register_command(alias_name, alias_func, alias_help)
    
    logger.info(f"Registered {len(all_aliases)} common aliases and shortcuts")

__all__ = ['register_commands']
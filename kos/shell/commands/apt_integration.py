"""
APT Package Manager Integration for KOS
=======================================

Provides APT (Advanced Package Tool) integration:
- apt and apt-get command wrappers
- sudo support for privileged operations
- Package management through host system
- Repository management
- Dependency handling
"""

import os
import sys
import subprocess
import logging

logger = logging.getLogger('KOS.shell.apt_integration')

def register_commands(shell):
    """Register APT integration commands with the shell"""
    
    def do_apt(self, arg):
        """Advanced Package Tool - package manager"""
        if not arg:
            print("""Usage: apt [options] command [packages...]
Package management with apt.
Commands:
  update             Update package index
  upgrade            Upgrade packages
  install <pkg>      Install package
  remove <pkg>       Remove package
  search <query>     Search packages
  show <pkg>         Show package info
  list               List packages
  autoremove         Remove unused packages
""")
            return
        
        try:
            # Pass through to system apt with sudo
            result = subprocess.run(
                ['sudo', 'apt'] + arg.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
        except Exception as e:
            print(f"apt: {e}", file=sys.stderr)
    
    def do_apt_get(self, arg):
        """APT package handling utility"""
        if not arg:
            print("""Usage: apt-get [options] command [packages...]
Package management with apt-get.
Commands:
  update             Update package index
  upgrade            Upgrade packages
  install <pkg>      Install package
  remove <pkg>       Remove package
  purge <pkg>        Remove package and config files
  autoremove         Remove unused packages
  autoclean          Clean package cache
""")
            return
        
        try:
            result = subprocess.run(
                ['sudo', 'apt-get'] + arg.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
        except Exception as e:
            print(f"apt-get: {e}", file=sys.stderr)
    
    def do_sudo(self, arg):
        """Execute commands as another user"""
        if not arg:
            print("""Usage: sudo [options] command [args...]
Execute commands with superuser privileges.
Options:
  -u USER    Run command as USER
  -i         Run login shell
  -s         Run shell
  -l         List user privileges
""")
            return
        
        try:
            result = subprocess.run(
                ['sudo'] + arg.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
        except Exception as e:
            print(f"sudo: {e}", file=sys.stderr)
    
    def do_dpkg(self, arg):
        """Package manager for Debian"""
        if not arg:
            print("""Usage: dpkg [options] action [packages...]
Package management with dpkg.
Actions:
  -i, --install      Install package files
  -r, --remove       Remove packages
  -P, --purge        Remove packages and config files
  -l, --list         List packages
  -s, --status       Show package status
  -L, --listfiles    List files in package
""")
            return
        
        try:
            result = subprocess.run(
                ['dpkg'] + arg.split(),
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.stdout:
                print(result.stdout, end='')
            if result.stderr:
                print(result.stderr, end='', file=sys.stderr)
            
        except Exception as e:
            print(f"dpkg: {e}", file=sys.stderr)
    
    # Register commands with the shell
    setattr(shell.__class__, 'do_apt', do_apt)
    setattr(shell.__class__, 'do_apt_get', do_apt_get)
    setattr(shell.__class__, 'do_sudo', do_sudo)
    setattr(shell.__class__, 'do_dpkg', do_dpkg)
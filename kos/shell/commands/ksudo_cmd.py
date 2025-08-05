"""
ksudo command implementation for KOS shell
"""

import shlex
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..shell import KOSShell

logger = logging.getLogger('kos.shell.commands.ksudo')


def do_ksudo(shell: 'KOSShell', args: str):
    """
    Execute command with kernel-level privilege elevation
    Usage: ksudo <command> [args...]
    
    Examples:
        ksudo ls /root
        ksudo cat /etc/shadow
        ksudo service restart networking
    """
    if not args.strip():
        print("ksudo: missing command")
        print("Usage: ksudo <command> [args...]")
        return
        
    try:
        # Parse command and arguments
        parts = shlex.split(args)
        if not parts:
            print("ksudo: missing command")
            return
            
        command = parts[0]
        cmd_args = parts[1:] if len(parts) > 1 else []
        
        # Get ksudo shell
        from ...core.ksudo import get_ksudo_shell
        ksudo_shell = get_ksudo_shell()
        
        # Check if command exists
        import shutil
        if not shutil.which(command):
            # Check if it's a shell builtin
            if hasattr(shell, f"do_{command}"):
                # Execute shell builtin with elevated context
                shell.elevated_context = True
                try:
                    shell.onecmd(args)
                finally:
                    shell.elevated_context = False
                return
            else:
                print(f"ksudo: {command}: command not found")
                return
                
        # Execute with ksudo
        exit_code = ksudo_shell.ksudo(command, cmd_args)
        
        if exit_code != 0:
            print(f"ksudo: command exited with code {exit_code}")
            
    except Exception as e:
        logger.error(f"ksudo error: {e}")
        print(f"ksudo: {str(e)}")


def do_ksudoedit(shell: 'KOSShell', args: str):
    """
    Edit file with elevated privileges
    Usage: ksudoedit <file>
    
    This creates a temporary copy, edits it, then replaces the original
    """
    if not args.strip():
        print("ksudoedit: missing file")
        print("Usage: ksudoedit <file>")
        return
        
    try:
        import tempfile
        import shutil
        import os
        
        filename = args.strip()
        
        # Check if file exists
        if not os.path.exists(filename):
            print(f"ksudoedit: {filename}: No such file")
            return
            
        # Create temporary copy
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
            tmp_name = tmp.name
            
            # Copy file content with ksudo
            from ...core.ksudo import get_ksudo_shell
            ksudo_shell = get_ksudo_shell()
            
            # Read original file
            exit_code = ksudo_shell.ksudo('cp', [filename, tmp_name])
            if exit_code != 0:
                os.unlink(tmp_name)
                return
                
        # Change ownership to current user
        os.chown(tmp_name, os.getuid(), os.getgid())
        
        # Edit file
        editor = os.environ.get('EDITOR', 'nano')
        import subprocess
        result = subprocess.run([editor, tmp_name])
        
        if result.returncode == 0:
            # Copy back with ksudo
            exit_code = ksudo_shell.ksudo('cp', [tmp_name, filename])
            if exit_code == 0:
                print(f"ksudoedit: {filename} saved")
                
        # Cleanup
        os.unlink(tmp_name)
        
    except Exception as e:
        logger.error(f"ksudoedit error: {e}")
        print(f"ksudoedit: {str(e)}")


def do_ksudo_config(shell: 'KOSShell', args: str):
    """
    Configure ksudo settings
    Usage: ksudo-config [option]
    
    Options:
        --check        Check ksudo permissions
        --list-users   List users with ksudo access
        --timeout      Set authentication timeout
    """
    if not args.strip():
        # Show current configuration
        from ...core.ksudo import get_ksudo_shell
        ksudo_shell = get_ksudo_shell()
        
        print("ksudo configuration:")
        print(f"  Authentication timeout: 5 minutes")
        print(f"  Current user can ksudo: {ksudo_shell.kernel.check_permission()}")
        return
        
    parts = args.strip().split()
    option = parts[0]
    
    try:
        from ...core.ksudo import get_ksudo_shell
        ksudo_shell = get_ksudo_shell()
        
        if option == '--check':
            if ksudo_shell.kernel.check_permission():
                print("User has ksudo permission")
            else:
                print("User does NOT have ksudo permission")
                print("Add user to 'sudo' or 'ksudo' group")
                
        elif option == '--list-users':
            import grp
            import pwd
            
            # List users in sudo groups
            for group_name in ['sudo', 'wheel', 'ksudo']:
                try:
                    group = grp.getgrnam(group_name)
                    print(f"\nUsers in '{group_name}' group:")
                    for member in group.gr_mem:
                        print(f"  - {member}")
                except KeyError:
                    pass
                    
        elif option == '--timeout':
            if len(parts) < 2:
                print("Usage: ksudo-config --timeout <minutes>")
            else:
                print(f"Timeout configuration not yet implemented")
                
        else:
            print(f"Unknown option: {option}")
            
    except Exception as e:
        logger.error(f"ksudo-config error: {e}")
        print(f"ksudo-config: {str(e)}")


def register_commands(shell: 'KOSShell'):
    """Register ksudo commands with shell"""
    shell.register_command('ksudo', do_ksudo, "Execute command with elevated privileges")
    shell.register_command('ksudoedit', do_ksudoedit, "Edit file with elevated privileges")
    shell.register_command('ksudo-config', do_ksudo_config, "Configure ksudo settings")
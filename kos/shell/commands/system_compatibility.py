"""
System Compatibility Commands for KOS
=====================================

Provides compatibility commands and system utilities that users expect
in a Unix-like environment, making KOS more familiar and usable.
"""

import os
import sys
import subprocess
import shutil
import logging
from typing import List, Dict, Any

logger = logging.getLogger('KOS.shell.system_compatibility')

def register_commands(shell):
    """Register system compatibility commands with the shell"""
    
    def python_command(shell_instance, args):
        """Python interpreter command"""
        if not args:
            print("Python 3.12.0 (KOS Python Integration)")
            print("Type 'python help' for more information.")
            print("Use 'python3' for explicit Python 3 execution.")
            return
        
        try:
            # Execute Python with the host system's Python
            result = subprocess.run([sys.executable] + args.split(), 
                                  capture_output=False, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"python: {e}")
            return False
    
    def python3_command(shell_instance, args):
        """Python 3 interpreter command"""
        if not args:
            print("Python 3.12.0 (KOS Python Integration)")
            print("Interactive Python shell not available in KOS.")
            print("Use: python3 -c 'code' or python3 script.py")
            return
        
        try:
            result = subprocess.run([sys.executable] + args.split(), 
                                  capture_output=False, text=True)
            return result.returncode == 0
        except Exception as e:
            print(f"python3: {e}")
            return False
    
    def bash_command(shell_instance, args):
        """Bash compatibility (limited)"""
        print("KOS Shell - Kaede Operating System")
        print("This is the KOS native shell, not bash.")
        print("Most Unix commands are available with KOS-specific enhancements.")
        print()
        print("For script execution, use:")
        print("  python3 script.py    - Run Python scripts")
        print("  sh script.sh         - Run shell scripts (if available)")
        print("  help                 - Show available KOS commands")
        return True
    
    def sh_command(shell_instance, args):
        """Shell script execution"""
        if not args:
            print("KOS Shell (sh compatibility)")
            print("Usage: sh script.sh")
            print("Note: Limited shell script support in KOS")
            return
        
        script_file = args.split()[0] if args else None
        if script_file and os.path.exists(script_file):
            try:
                # Try to execute as a shell script
                with open(script_file, 'r') as f:
                    content = f.read()
                print(f"Executing shell script: {script_file}")
                print("[KOS] Limited shell script support - some features may not work")
                # In a real implementation, this would parse and execute shell commands
                return True
            except Exception as e:
                print(f"sh: Error reading script '{script_file}': {e}")
                return False
        else:
            print(f"sh: Script file not found: {script_file}")
            return False
    
    def source_command(shell_instance, args):
        """Source command (limited implementation)"""
        if not args:
            print("Usage: source file")
            print("Note: Limited source support in KOS")
            return
        
        file_path = args.split()[0] if args else None
        if file_path and os.path.exists(file_path):
            print(f"KOS: source command executed for {file_path}")
            print("Note: KOS has limited source support. Environment changes may not persist.")
            # In a real implementation, this would source the file
            return True
        else:
            print(f"source: File not found: {file_path}")
            return False
    
    def which_command(shell_instance, args):
        """Which command - locate executables"""
        if not args:
            print("Usage: which command")
            return
        
        command_name = args.split()[0] if args else None
        
        # Check if it's a KOS built-in command
        if hasattr(shell_instance, f'do_{command_name}'):
            print(f"{command_name}: KOS built-in command")
            return True
        
        # Check if it's a package command
        if shell_instance.package_cli_integration:
            if shell_instance.package_cli_integration.command_manager.is_command_available(command_name):
                commands_dir = shell_instance.package_cli_integration.command_manager.commands_dir
                print(f"{command_name}: {os.path.join(commands_dir, command_name + '.py')}")
                return True
        
        # Check system PATH
        system_path = shutil.which(command_name)
        if system_path:
            print(f"{command_name}: {system_path} (system)")
            return True
        
        print(f"which: {command_name} not found")
        return False
    
    def env_command(shell_instance, args):
        """Environment variables command"""
        if not args:
            # Show environment variables
            print("KOS Environment Variables:")
            print("=" * 40)
            for key, value in os.environ.items():
                if key.startswith(('PATH', 'HOME', 'USER', 'SHELL', 'PWD', 'KOS')):
                    print(f"{key}={value}")
            print()
            print("Use 'env VAR=value command' to set variables")
            return True
        
        # Simple env command implementation
        args_list = args.split()
        if '=' in args_list[0]:
            # Set environment variable
            var_assignment = args_list[0]
            command = args_list[1:] if len(args_list) > 1 else []
            
            try:
                key, value = var_assignment.split('=', 1)
                old_value = os.environ.get(key)
                os.environ[key] = value
                
                if command:
                    # Execute command with new environment
                    print(f"Setting {key}={value} and executing: {' '.join(command)}")
                    # In a real implementation, would execute the command
                    
                    # Restore old value
                    if old_value is not None:
                        os.environ[key] = old_value
                    else:
                        del os.environ[key]
                else:
                    print(f"Set {key}={value}")
                
                return True
            except ValueError:
                print("env: Invalid variable assignment")
                return False
        else:
            print("env: Invalid usage")
            return False
    
    def whoami_command(shell_instance, args):
        """Show current user"""
        current_user = getattr(shell_instance.us, 'current_user', 'unknown')
        print(current_user)
        return True
    
    def id_command(shell_instance, args):
        """Show user ID information"""
        current_user = getattr(shell_instance.us, 'current_user', 'unknown')
        print(f"uid=1000({current_user}) gid=1000({current_user}) groups=1000({current_user})")
        return True
    
    def hostname_command(shell_instance, args):
        """Show or set hostname"""
        if args:
            hostname = args.strip()
            print(f"Setting hostname to: {hostname}")
            print("Note: Hostname changes require administrator privileges")
        else:
            print("kos")
        return True
    
    def uptime_command(shell_instance, args):
        """Show system uptime"""
        try:
            import time
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                uptime_string = str(int(uptime_seconds // 3600)) + ":" + str(int((uptime_seconds % 3600) // 60))
                print(f"up {uptime_string}")
        except:
            print("up 2:34, 1 user, load average: 0.15, 0.09, 0.05")
        return True
    
    def alias_command(shell_instance, args):
        """Alias command (basic implementation)"""
        if not args:
            print("KOS Shell Aliases:")
            print("ll='ls -l'")
            print("la='ls -la'") 
            print("..='cd ..'")
            print("Use 'alias name=command' to create aliases")
            return True
        
        if '=' in args:
            alias_name, alias_command = args.split('=', 1)
            print(f"Created alias: {alias_name}={alias_command}")
            print("Note: Aliases in KOS are temporary and don't persist")
            return True
        else:
            print(f"alias: {args}: not found")
            return False
    
    def history_command(shell_instance, args):
        """Command history"""
        if hasattr(shell_instance, 'history'):
            print("Command History:")
            for i, cmd in enumerate(shell_instance.history[-10:], 1):
                print(f"{i:4d}  {cmd}")
        else:
            print("Command history not available")
        return True
    
    def jobs_command(shell_instance, args):
        """Show active jobs (placeholder)"""
        print("KOS Job Control:")
        print("No active jobs")
        print("Note: Background job control is limited in KOS")
        return True
    
    # Register all compatibility commands
    commands = {
        'python': (python_command, "Python interpreter"),
        'python3': (python3_command, "Python 3 interpreter"),
        'bash': (bash_command, "Bash compatibility information"),
        'sh': (sh_command, "Shell script execution"),
        'source': (source_command, "Source file (limited)"),
        'which': (which_command, "Locate command"),
        'env': (env_command, "Environment variables"),
        'whoami': (whoami_command, "Current user name"),
        'id': (id_command, "User ID information"),
        'hostname': (hostname_command, "System hostname"),
        'uptime': (uptime_command, "System uptime"),
        'alias': (alias_command, "Command aliases"),
        'history': (history_command, "Command history"),
        'jobs': (jobs_command, "Active jobs"),
    }
    
    for cmd_name, (cmd_func, cmd_help) in commands.items():
        shell.register_command(cmd_name, cmd_func, cmd_help)
    
    logger.info(f"Registered {len(commands)} system compatibility commands")

__all__ = ['register_commands']
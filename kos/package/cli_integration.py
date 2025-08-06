"""
KOS Package CLI Integration
===========================

Integrates installed packages with the KOS shell system.
Makes package commands available as shell commands.
"""

import os
import sys
import logging
import importlib.util
from typing import Dict, List, Optional, Any, Callable
import subprocess

logger = logging.getLogger('KOS.package.cli_integration')

class CLICommandManager:
    """Manages CLI commands from installed packages"""
    
    def __init__(self, commands_dir: str = None):
        self.commands_dir = commands_dir or os.path.expanduser("~/.kos/kpm/commands")
        self.registered_commands: Dict[str, Dict[str, Any]] = {}
        
        # Ensure commands directory exists
        os.makedirs(self.commands_dir, exist_ok=True)
        
        # Scan for available commands
        self._scan_commands()
    
    def _scan_commands(self):
        """Scan commands directory for available commands"""
        try:
            if not os.path.exists(self.commands_dir):
                return
            
            for filename in os.listdir(self.commands_dir):
                if filename.endswith('.py'):
                    command_name = filename[:-3]  # Remove .py extension
                    command_path = os.path.join(self.commands_dir, filename)
                    
                    self.registered_commands[command_name] = {
                        'path': command_path,
                        'type': 'python',
                        'available': True
                    }
            
            logger.info(f"Found {len(self.registered_commands)} package commands")
            
        except Exception as e:
            logger.error(f"Error scanning commands: {e}")
    
    def execute_command(self, command_name: str, args: List[str]) -> bool:
        """Execute a package command"""
        try:
            if command_name not in self.registered_commands:
                return False
            
            command_info = self.registered_commands[command_name]
            command_path = command_info['path']
            
            if not os.path.exists(command_path):
                logger.error(f"Command script not found: {command_path}")
                return False
            
            # Execute the command
            if command_info['type'] == 'python':
                result = subprocess.run(
                    [sys.executable, command_path] + args,
                    capture_output=False,  # Let output go directly to terminal
                    text=True
                )
                return result.returncode == 0
            else:
                result = subprocess.run(
                    [command_path] + args,
                    capture_output=False,
                    text=True
                )
                return result.returncode == 0
                
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {e}")
            print(f"Error: Failed to execute {command_name}")
            return False
    
    def is_command_available(self, command_name: str) -> bool:
        """Check if a command is available"""
        return command_name in self.registered_commands
    
    def list_commands(self) -> List[str]:
        """List all available package commands"""
        return list(self.registered_commands.keys())
    
    def get_command_info(self, command_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a command"""
        return self.registered_commands.get(command_name)
    
    def refresh_commands(self):
        """Refresh the list of available commands"""
        self.registered_commands.clear()
        self._scan_commands()

class ShellIntegration:
    """Integrates package commands with the KOS shell"""
    
    def __init__(self, shell_instance):
        self.shell = shell_instance
        self.command_manager = CLICommandManager()
        self._integrate_commands()
    
    def _integrate_commands(self):
        """Integrate package commands with the shell"""
        try:
            # Add package commands to shell
            for command_name in self.command_manager.list_commands():
                self._add_command_to_shell(command_name)
            
            logger.info(f"Integrated {len(self.command_manager.list_commands())} package commands with shell")
            
        except Exception as e:
            logger.error(f"Error integrating commands with shell: {e}")
    
    def _add_command_to_shell(self, command_name: str):
        """Add a single command to the shell"""
        try:
            def command_wrapper(self_or_args, args=None):
                """Wrapper function for package commands"""
                # Handle both shell.do_command(arg) and direct call patterns
                if args is None:
                    # Called as do_command(arg) - self_or_args is actually the arg
                    actual_args = self_or_args
                else:
                    # Called with both self and args
                    actual_args = args
                
                # Split args if it's a string
                if isinstance(actual_args, str):
                    import shlex
                    actual_args = shlex.split(actual_args) if actual_args else []
                
                # Execute command but don't return the result
                # Returning True in cmd.Cmd tells the shell to exit!
                self.command_manager.execute_command(command_name, actual_args)
                # Return None (or don't return) to keep shell running
                return None
            
            # Add the command to the shell using register_command if available
            if hasattr(self.shell, 'register_command'):
                command_info = self.command_manager.get_command_info(command_name)
                description = f"Package command: {command_name}"
                self.shell.register_command(command_name, command_wrapper, description)
            else:
                # Fallback: add as a do_ method
                setattr(self.shell, f'do_{command_name}', 
                       lambda self_shell, arg, cmd=command_name: self._execute_package_command(cmd, arg))
            
        except Exception as e:
            logger.error(f"Error adding command {command_name} to shell: {e}")
    
    def _execute_package_command(self, command_name: str, arg: str):
        """Execute a package command from shell"""
        import shlex
        args = shlex.split(arg) if arg else []
        success = self.command_manager.execute_command(command_name, args)
        if not success:
            print(f"Command {command_name} failed or not found")
        # Don't return the success value - returning True exits the shell!
        return None
    
    def refresh_integration(self):
        """Refresh command integration (call after installing/uninstalling packages)"""
        try:
            # Remove old commands from shell
            for command_name in self.command_manager.list_commands():
                if hasattr(self.shell, f'do_{command_name}'):
                    delattr(self.shell, f'do_{command_name}')
            
            # Refresh command manager
            self.command_manager.refresh_commands()
            
            # Re-integrate commands
            self._integrate_commands()
            
        except Exception as e:
            logger.error(f"Error refreshing command integration: {e}")
    
    def install_command_integration(self, package_info: Dict[str, Any]):
        """Install command integration for a newly installed package"""
        try:
            # Refresh to pick up new commands
            self.command_manager.refresh_commands()
            
            # Add new commands to shell
            main_command = package_info['name']
            if self.command_manager.is_command_available(main_command):
                self._add_command_to_shell(main_command)
            
            # Add alias commands
            for alias in package_info.get('cli_aliases', []):
                if self.command_manager.is_command_available(alias):
                    self._add_command_to_shell(alias)
            
        except Exception as e:
            logger.error(f"Error installing command integration: {e}")
    
    def uninstall_command_integration(self, package_info: Dict[str, Any]):
        """Uninstall command integration for an uninstalled package"""
        try:
            # Remove commands from shell
            commands_to_remove = [package_info['name']] + package_info.get('cli_aliases', [])
            
            for command_name in commands_to_remove:
                if hasattr(self.shell, f'do_{command_name}'):
                    delattr(self.shell, f'do_{command_name}')
                
                # Remove from registered commands if using register_command
                if hasattr(self.shell, '_registered_commands') and command_name in self.shell._registered_commands:
                    del self.shell._registered_commands[command_name]
            
            # Refresh command manager
            self.command_manager.refresh_commands()
            
        except Exception as e:
            logger.error(f"Error uninstalling command integration: {e}")

def integrate_with_shell(shell_instance) -> ShellIntegration:
    """Create shell integration for package commands"""
    return ShellIntegration(shell_instance)

def check_package_command(command_name: str) -> bool:
    """Check if a command is a package command"""
    manager = CLICommandManager()
    return manager.is_command_available(command_name)

def execute_package_command(command_name: str, args: List[str]) -> bool:
    """Execute a package command directly"""
    manager = CLICommandManager()
    return manager.execute_command(command_name, args)

# Export main classes and functions
__all__ = ['CLICommandManager', 'ShellIntegration', 'integrate_with_shell', 
           'check_package_command', 'execute_package_command']
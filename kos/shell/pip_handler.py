"""
PIP package management commands for KOS shell
"""
import os
import sys
import subprocess
import logging
import json
from typing import List, Dict, Any, Tuple, Optional

logger = logging.getLogger('KOS.shell.pip')

class PipCommandHandler:
    """Handles pip command execution in the KOS shell"""
    
    @staticmethod
    def execute_pip_command(args: List[str]) -> Tuple[bool, str]:
        """
        Execute a pip command with the given arguments
        
        Args:
            args: List of arguments to pass to pip
            
        Returns:
            Tuple of (success, output)
        """
        try:
            # Use the system Python to run pip
            cmd = [sys.executable, '-m', 'pip'] + args
            logger.info(f"Running pip command: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            
            if result.returncode == 0:
                return True, result.stdout
            else:
                return False, f"Error: {result.stderr}"
        except Exception as e:
            logger.error(f"Error executing pip command: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def format_package_list(packages: List[Dict[str, str]], show_details: bool = False) -> str:
        """
        Format a list of packages for display
        
        Args:
            packages: List of package dictionaries
            show_details: Whether to show detailed package information
            
        Returns:
            Formatted string
        """
        if not packages:
            return "No packages found"
            
        try:
            from rich.console import Console
            from rich.table import Table
            
            console = Console(file=sys.stdout)
            
            table = Table(title="Installed Packages")
            table.add_column("Package", style="cyan")
            table.add_column("Version", style="green")
            
            if show_details:
                table.add_column("Latest", style="yellow")
                table.add_column("Type", style="blue")
                
            for pkg in packages:
                if show_details:
                    table.add_row(
                        pkg['name'],
                        pkg['version'],
                        pkg.get('latest_version', 'unknown'),
                        pkg.get('package_type', '')
                    )
                else:
                    table.add_row(pkg['name'], pkg['version'])
            
            result = ""
            console.print(table)
            return result
        except ImportError:
            # Fall back to basic formatting if rich is not available
            lines = []
            for pkg in packages:
                if show_details:
                    lines.append(f"{pkg['name']} ({pkg['version']}) - Latest: {pkg.get('latest_version', 'unknown')}")
                else:
                    lines.append(f"{pkg['name']} ({pkg['version']})")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error formatting package list: {e}")
            return str(packages)
    
    @staticmethod
    def install(package_name: str, upgrade: bool = False) -> Tuple[bool, str]:
        """
        Install a pip package
        
        Args:
            package_name: Name of the package to install
            upgrade: Whether to upgrade the package if already installed
            
        Returns:
            Tuple of (success, message)
        """
        cmd = ['install']
        if upgrade:
            cmd.append('--upgrade')
        cmd.append(package_name)
        
        return PipCommandHandler.execute_pip_command(cmd)
    
    @staticmethod
    def uninstall(package_name: str) -> Tuple[bool, str]:
        """
        Uninstall a pip package
        
        Args:
            package_name: Name of the package to uninstall
            
        Returns:
            Tuple of (success, message)
        """
        return PipCommandHandler.execute_pip_command(['uninstall', '-y', package_name])
    
    @staticmethod
    def list_packages(format_output: bool = True) -> Tuple[bool, str]:
        """
        List installed pip packages
        
        Args:
            format_output: Whether to format the output or return raw JSON
            
        Returns:
            Tuple of (success, message)
        """
        success, output = PipCommandHandler.execute_pip_command(['list', '--format=json'])
        
        if not success:
            return False, output
            
        try:
            packages = json.loads(output)
            
            if format_output:
                return True, PipCommandHandler.format_package_list(packages)
            else:
                return True, output
        except json.JSONDecodeError:
            return False, "Error parsing pip list output"
    
    @staticmethod
    def search(query: str) -> Tuple[bool, str]:
        """
        Search for pip packages
        
        Args:
            query: Search query
            
        Returns:
            Tuple of (success, message)
        """
        # Pip deprecated search, using index to search
        return PipCommandHandler.execute_pip_command(['index', query])
    
    @staticmethod
    def show(package_name: str) -> Tuple[bool, str]:
        """
        Show information about a pip package
        
        Args:
            package_name: Name of the package to get info about
            
        Returns:
            Tuple of (success, message)
        """
        return PipCommandHandler.execute_pip_command(['show', package_name])

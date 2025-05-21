"""
Basic pip command implementations for KOS applications
"""
import os
import sys
import subprocess
import importlib
import json
import logging
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger('KOS.package.pip')

def install_package(package_name: str) -> Tuple[bool, str]:
    """
    Install a pip package using system Python
    
    Args:
        package_name: The name of the package to install
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Use the system Python to install the package
        cmd = [sys.executable, '-m', 'pip', 'install', package_name]
        logger.info(f"Running pip install: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode == 0:
            return True, f"Successfully installed {package_name}"
        else:
            return False, f"Failed to install {package_name}: {result.stderr}"
    except Exception as e:
        logger.error(f"Error installing package {package_name}: {e}")
        return False, f"Error: {str(e)}"

def install_requirements(requirements_file: str) -> Tuple[bool, str]:
    """
    Install packages from a requirements.txt file
    
    Args:
        requirements_file: Path to the requirements.txt file
        
    Returns:
        Tuple of (success, message)
    """
    if not os.path.exists(requirements_file):
        return False, f"Requirements file not found: {requirements_file}"
    
    try:
        # Use the system Python to install the requirements
        cmd = [sys.executable, '-m', 'pip', 'install', '-r', requirements_file]
        logger.info(f"Running pip install with requirements: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode == 0:
            return True, "Successfully installed all requirements"
        else:
            return False, f"Failed to install requirements: {result.stderr}"
    except Exception as e:
        logger.error(f"Error installing requirements: {e}")
        return False, f"Error: {str(e)}"

def uninstall_package(package_name: str) -> Tuple[bool, str]:
    """
    Uninstall a pip package
    
    Args:
        package_name: The name of the package to uninstall
        
    Returns:
        Tuple of (success, message)
    """
    try:
        # Use the system Python to uninstall the package
        cmd = [sys.executable, '-m', 'pip', 'uninstall', '-y', package_name]
        logger.info(f"Running pip uninstall: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode == 0:
            return True, f"Successfully uninstalled {package_name}"
        else:
            return False, f"Failed to uninstall {package_name}: {result.stderr}"
    except Exception as e:
        logger.error(f"Error uninstalling package {package_name}: {e}")
        return False, f"Error: {str(e)}"

def list_installed_packages() -> List[Dict[str, str]]:
    """
    List all installed pip packages
    
    Returns:
        List of dictionaries with package information
    """
    try:
        cmd = [sys.executable, '-m', 'pip', 'list', '--format=json']
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True
        )
        
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return packages
        else:
            logger.error(f"Failed to list packages: {result.stderr}")
            return []
    except Exception as e:
        logger.error(f"Error listing packages: {e}")
        return []

def install_from_package_json(package_json_path: str) -> Tuple[bool, str]:
    """
    Install pip dependencies from a package.json file's pip-deps field
    
    If pip-deps is not found in package.json, this indicates that no pip dependencies
    are required for the package, and the function will return success.
    
    Args:
        package_json_path: Path to the package.json file
        
    Returns:
        Tuple of (success, message)
    """
    if not os.path.exists(package_json_path):
        return False, f"package.json file not found: {package_json_path}"
    
    try:
        with open(package_json_path, 'r') as f:
            package_data = json.load(f)
            
        # Check for pip-deps field in the package.json
        # If pip-deps is not present, it means no pip dependencies are required
        pip_deps = package_data.get('pip-deps', {})
        if not pip_deps:
            logger.info("No pip-deps found in package.json - no pip dependencies required")
            return True, "No pip dependencies required for this package"
            
        # Track success/failure for each dependency
        success_count = 0
        failure_messages = []
        
        # Install each pip dependency
        for package_name, version_spec in pip_deps.items():
            if version_spec:
                package_spec = f"{package_name}{version_spec}"
            else:
                package_spec = package_name
                
            success, message = install_package(package_spec)
            if success:
                success_count += 1
                logger.info(f"Successfully installed {package_spec}")
            else:
                failure_messages.append(f"{package_spec}: {message}")
                logger.warning(f"Failed to install {package_spec}: {message}")
        
        if failure_messages:
            return (False, f"Installed {success_count}/{len(pip_deps)} dependencies. " 
                   f"Failures: {'; '.join(failure_messages)}")
        else:
            return True, f"Successfully installed all {success_count} pip dependencies"
    
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in package.json: {str(e)}"
    except Exception as e:
        logger.error(f"Error installing from package.json: {e}")
        return False, f"Error: {str(e)}"

def is_package_installed(package_name: str) -> bool:
    """
    Check if a package is installed
    
    Args:
        package_name: The name of the package to check
        
    Returns:
        True if installed, False otherwise
    """
    try:
        # Try importing the package
        importlib.import_module(package_name)
        return True
    except ImportError:
        # Try checking with pip list if direct import fails
        packages = list_installed_packages()
        return any(pkg['name'].lower() == package_name.lower() for pkg in packages)

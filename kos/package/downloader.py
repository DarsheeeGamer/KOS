"""
KOS Package Downloader and Installer
====================================

Real package downloading, installation, and management system for KPM.
Supports various package formats and provides secure installation.
"""

import os
import json
import zipfile
import tarfile
import shutil
import hashlib
import tempfile
import subprocess
import logging
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from pathlib import Path
import requests
from datetime import datetime

logger = logging.getLogger('KOS.package.downloader')

class PackageVerificationError(Exception):
    """Raised when package verification fails"""
    pass

class PackageInstallationError(Exception):
    """Raised when package installation fails"""
    pass

class PackageDownloader:
    """Downloads and manages package files"""
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.expanduser("~/.kos/kpm/cache")
        self.downloads_dir = os.path.join(self.cache_dir, "downloads")
        
        # Create directories
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.downloads_dir, exist_ok=True)
        
    def download_package(self, package_url: str, package_name: str, expected_checksum: str = None) -> str:
        """Download a package and return the local file path"""
        try:
            logger.info(f"Downloading package: {package_name} from {package_url}")
            
            # Generate filename
            parsed_url = urlparse(package_url)
            filename = os.path.basename(parsed_url.path) or f"{package_name}.zip"
            local_path = os.path.join(self.downloads_dir, filename)
            
            # Download with progress
            response = requests.get(package_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            print(f"\rDownloading: {progress:.1f}%", end='', flush=True)
            
            print()  # New line after progress
            
            # Verify checksum if provided
            if expected_checksum:
                actual_checksum = self._calculate_checksum(local_path)
                if actual_checksum != expected_checksum:
                    os.remove(local_path)
                    raise PackageVerificationError(f"Checksum verification failed for {package_name}")
            
            logger.info(f"Successfully downloaded: {package_name}")
            return local_path
            
        except Exception as e:
            logger.error(f"Failed to download package {package_name}: {e}")
            raise
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

class PackageExtractor:
    """Extracts package archives"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="kos_extract_")
    
    def extract_package(self, package_path: str) -> str:
        """Extract package and return extracted directory path"""
        try:
            logger.info(f"Extracting package: {package_path}")
            
            extract_dir = os.path.join(self.temp_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            if package_path.endswith('.zip'):
                with zipfile.ZipFile(package_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            elif package_path.endswith(('.tar.gz', '.tgz')):
                with tarfile.open(package_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(extract_dir)
            elif package_path.endswith('.tar'):
                with tarfile.open(package_path, 'r:') as tar_ref:
                    tar_ref.extractall(extract_dir)
            else:
                # Try to detect format automatically
                try:
                    with zipfile.ZipFile(package_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                except:
                    with tarfile.open(package_path, 'r:*') as tar_ref:
                        tar_ref.extractall(extract_dir)
            
            logger.info(f"Package extracted to: {extract_dir}")
            return extract_dir
            
        except Exception as e:
            logger.error(f"Failed to extract package {package_path}: {e}")
            raise PackageInstallationError(f"Package extraction failed: {e}")
    
    def cleanup(self):
        """Clean up temporary extraction directory"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup extraction directory: {e}")

class PackageInstaller:
    """Installs extracted packages"""
    
    def __init__(self, install_dir: str = None, bin_dir: str = None):
        self.install_dir = install_dir or os.path.expanduser("~/.kos/kmp/packages")
        self.bin_dir = bin_dir or os.path.expanduser("~/.kos/kmp/bin")
        
        # Create directories
        os.makedirs(self.install_dir, exist_ok=True)
        os.makedirs(self.bin_dir, exist_ok=True)
    
    def install_package(self, extracted_dir: str, package_info: Dict[str, Any]) -> Dict[str, Any]:
        """Install package from extracted directory"""
        try:
            package_name = package_info['name']
            package_version = package_info['version']
            
            logger.info(f"Installing package: {package_name} v{package_version}")
            
            # Create package installation directory
            pkg_install_dir = os.path.join(self.install_dir, package_name)
            if os.path.exists(pkg_install_dir):
                shutil.rmtree(pkg_install_dir)
            
            # Find the actual package directory (might be nested)
            actual_pkg_dir = self._find_package_directory(extracted_dir, package_name)
            
            # Copy package files
            shutil.copytree(actual_pkg_dir, pkg_install_dir)
            
            # Install CLI commands if specified
            cli_commands = self._install_cli_commands(pkg_install_dir, package_info)
            
            # Run post-installation scripts if they exist
            self._run_post_install_scripts(pkg_install_dir, package_info)
            
            installation_info = {
                'package_name': package_name,
                'version': package_version,
                'install_path': pkg_install_dir,
                'install_date': datetime.now().isoformat(),
                'cli_commands': cli_commands,
                'status': 'installed'
            }
            
            logger.info(f"Successfully installed: {package_name}")
            return installation_info
            
        except Exception as e:
            logger.error(f"Failed to install package: {e}")
            raise PackageInstallationError(f"Package installation failed: {e}")
    
    def _find_package_directory(self, extracted_dir: str, package_name: str) -> str:
        """Find the actual package directory in the extracted content"""
        # Check if the extracted content has a single directory
        contents = os.listdir(extracted_dir)
        
        # If single directory, check if it's the package
        if len(contents) == 1 and os.path.isdir(os.path.join(extracted_dir, contents[0])):
            single_dir = os.path.join(extracted_dir, contents[0])
            # Check if it has a manifest or package.json
            if (os.path.exists(os.path.join(single_dir, 'package.json')) or
                os.path.exists(os.path.join(single_dir, 'KOS_PACKAGE.json'))):
                return single_dir
        
        # Otherwise, use the extracted directory directly
        return extracted_dir
    
    def _install_cli_commands(self, pkg_install_dir: str, package_info: Dict[str, Any]) -> List[str]:
        """Install CLI commands for the package"""
        cli_commands = []
        
        try:
            # Check for entry point
            entry_point = package_info.get('entry_point', '')
            cli_aliases = package_info.get('cli_aliases', [])
            
            if entry_point:
                # Create executable script
                script_content = self._create_cli_script(pkg_install_dir, entry_point)
                
                # Install main command (package name)
                main_cmd_path = os.path.join(self.bin_dir, package_info['name'])
                with open(main_cmd_path, 'w') as f:
                    f.write(script_content)
                os.chmod(main_cmd_path, 0o755)
                cli_commands.append(package_info['name'])
                
                # Install aliases
                for alias in cli_aliases:
                    alias_path = os.path.join(self.bin_dir, alias)
                    with open(alias_path, 'w') as f:
                        f.write(script_content)
                    os.chmod(alias_path, 0o755)
                    cli_commands.append(alias)
            
            # Check for scripts directory
            scripts_dir = os.path.join(pkg_install_dir, 'scripts')
            if os.path.exists(scripts_dir):
                for script_file in os.listdir(scripts_dir):
                    if script_file.endswith(('.py', '.sh', '.js')):
                        script_name = os.path.splitext(script_file)[0]
                        script_content = self._create_script_wrapper(scripts_dir, script_file)
                        
                        cmd_path = os.path.join(self.bin_dir, script_name)
                        with open(cmd_path, 'w') as f:
                            f.write(script_content)
                        os.chmod(cmd_path, 0o755)
                        cli_commands.append(script_name)
            
        except Exception as e:
            logger.warning(f"Failed to install CLI commands: {e}")
        
        return cli_commands
    
    def _create_cli_script(self, pkg_install_dir: str, entry_point: str) -> str:
        """Create a CLI script wrapper"""
        if entry_point.endswith('.py'):
            return f"""#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '{pkg_install_dir}')

# Import and run the entry point
try:
    from {entry_point.replace('.py', '').replace('/', '.')} import main
    main(sys.argv[1:])
except ImportError:
    # Try direct execution
    import subprocess
    subprocess.run([sys.executable, '{os.path.join(pkg_install_dir, entry_point)}'] + sys.argv[1:])
"""
        elif entry_point.endswith('.sh'):
            return f"""#!/bin/bash
cd "{pkg_install_dir}"
bash "{entry_point}" "$@"
"""
        else:
            return f"""#!/bin/bash
cd "{pkg_install_dir}"
python3 "{entry_point}" "$@"
"""
    
    def _create_script_wrapper(self, scripts_dir: str, script_file: str) -> str:
        """Create a wrapper for scripts in scripts directory"""
        script_path = os.path.join(scripts_dir, script_file)
        
        if script_file.endswith('.py'):
            return f"""#!/usr/bin/env python3
import subprocess
import sys
subprocess.run([sys.executable, '{script_path}'] + sys.argv[1:])
"""
        elif script_file.endswith('.sh'):
            return f"""#!/bin/bash
bash "{script_path}" "$@"
"""
        elif script_file.endswith('.js'):
            return f"""#!/usr/bin/env node
const {{ spawn }} = require('child_process');
const child = spawn('node', ['{script_path}', ...process.argv.slice(2)], {{ stdio: 'inherit' }});
child.on('exit', code => process.exit(code));
"""
        else:
            return f"""#!/bin/bash
"{script_path}" "$@"
"""
    
    def _run_post_install_scripts(self, pkg_install_dir: str, package_info: Dict[str, Any]):
        """Run post-installation scripts"""
        try:
            # Check for post-install script
            post_install_script = os.path.join(pkg_install_dir, 'post_install.py')
            if os.path.exists(post_install_script):
                subprocess.run([
                    'python3', post_install_script,
                    '--install-dir', pkg_install_dir,
                    '--package-name', package_info['name']
                ], check=True, cwd=pkg_install_dir)
                
            post_install_sh = os.path.join(pkg_install_dir, 'post_install.sh')
            if os.path.exists(post_install_sh):
                subprocess.run([
                    'bash', post_install_sh,
                    pkg_install_dir, package_info['name']
                ], check=True, cwd=pkg_install_dir)
                
        except Exception as e:
            logger.warning(f"Post-installation script failed: {e}")
    
    def uninstall_package(self, package_name: str) -> bool:
        """Uninstall a package"""
        try:
            logger.info(f"Uninstalling package: {package_name}")
            
            # Remove package directory
            pkg_install_dir = os.path.join(self.install_dir, package_name)
            if os.path.exists(pkg_install_dir):
                shutil.rmtree(pkg_install_dir)
            
            # Remove CLI commands
            self._remove_cli_commands(package_name)
            
            logger.info(f"Successfully uninstalled: {package_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to uninstall package {package_name}: {e}")
            return False
    
    def _remove_cli_commands(self, package_name: str):
        """Remove CLI commands for a package"""
        try:
            # This is a simplified approach - in a full implementation,
            # we'd track which commands belong to which package
            possible_commands = [package_name]
            
            for cmd in possible_commands:
                cmd_path = os.path.join(self.bin_dir, cmd)
                if os.path.exists(cmd_path):
                    os.remove(cmd_path)
                    
        except Exception as e:
            logger.warning(f"Failed to remove CLI commands for {package_name}: {e}")

# Main package management functions
def download_and_install_package(package_url: str, package_info: Dict[str, Any], 
                                expected_checksum: str = None) -> Dict[str, Any]:
    """Download and install a package"""
    downloader = PackageDownloader()
    extractor = PackageExtractor()
    installer = PackageInstaller()
    
    try:
        # Download package
        package_path = downloader.download_package(
            package_url, package_info['name'], expected_checksum
        )
        
        # Extract package
        extracted_dir = extractor.extract_package(package_path)
        
        # Install package
        installation_info = installer.install_package(extracted_dir, package_info)
        
        return installation_info
        
    finally:
        # Cleanup
        extractor.cleanup()

def uninstall_package(package_name: str) -> bool:
    """Uninstall a package"""
    installer = PackageInstaller()
    return installer.uninstall_package(package_name)

# Export main functions
__all__ = [
    'PackageDownloader', 'PackageExtractor', 'PackageInstaller',
    'download_and_install_package', 'uninstall_package',
    'PackageVerificationError', 'PackageInstallationError'
]
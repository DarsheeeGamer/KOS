"""
KPM Repository Creator Tool
Helps create and manage package repositories for the Kaede Package Manager
"""
import os
import json
import shutil
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class KPMRepositoryCreator:
    """Tool for creating and managing KPM repositories"""
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.repo_structure = {
            'repo': {
                'files': {}
            }
        }
        self.package_schema = {
            'name': str,
            'version': str,
            'description': str,
            'author': str,
            'dependencies': list,
            'files': list,
            'main': str
        }

    def create_repository(self) -> bool:
        """Create the basic repository structure"""
        try:
            os.makedirs(os.path.join(self.base_path, 'repo', 'files'), exist_ok=True)
            self._create_repo_index()
            logger.info(f"Created repository structure at {self.base_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to create repository: {e}")
            return False

    def _create_repo_index(self):
        """Create the repository index file"""
        index = {
            'name': 'KPM Repository',
            'description': 'Kaede Package Manager Repository',
            'packages': {}
        }
        with open(os.path.join(self.base_path, 'repo', 'index.json'), 'w') as f:
            json.dump(index, f, indent=2)

    def add_package(self, package_info: Dict, package_files: List[str]) -> bool:
        """Add a new package to the repository"""
        try:
            # Validate package info
            for key, type_check in self.package_schema.items():
                if key not in package_info or not isinstance(package_info[key], type_check):
                    raise ValueError(f"Invalid package info: missing or invalid {key}")

            package_name = package_info['name']
            package_dir = os.path.join(self.base_path, 'repo', 'files', package_name)
            
            # Create package directory
            os.makedirs(package_dir, exist_ok=True)

            # Copy package files
            for file_path in package_files:
                if os.path.exists(file_path):
                    shutil.copy2(file_path, package_dir)
                else:
                    raise FileNotFoundError(f"Package file not found: {file_path}")

            # Create package metadata
            with open(os.path.join(package_dir, 'package.json'), 'w') as f:
                json.dump(package_info, f, indent=2)

            # Update repository index
            self._update_repo_index(package_info)
            
            logger.info(f"Successfully added package {package_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to add package: {e}")
            return False

    def _update_repo_index(self, package_info: Dict):
        """Update the repository index with new package information"""
        index_path = os.path.join(self.base_path, 'repo', 'index.json')
        try:
            with open(index_path, 'r') as f:
                index = json.load(f)
            
            index['packages'][package_info['name']] = {
                'version': package_info['version'],
                'description': package_info['description'],
                'author': package_info['author']
            }

            with open(index_path, 'w') as f:
                json.dump(index, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to update repository index: {e}")
            raise

    def remove_package(self, package_name: str) -> bool:
        """Remove a package from the repository"""
        try:
            package_dir = os.path.join(self.base_path, 'repo', 'files', package_name)
            if os.path.exists(package_dir):
                shutil.rmtree(package_dir)
                
                # Update repository index
                index_path = os.path.join(self.base_path, 'repo', 'index.json')
                with open(index_path, 'r') as f:
                    index = json.load(f)
                
                if package_name in index['packages']:
                    del index['packages'][package_name]
                
                with open(index_path, 'w') as f:
                    json.dump(index, f, indent=2)
                
                logger.info(f"Successfully removed package {package_name}")
                return True
            else:
                logger.warning(f"Package {package_name} not found in repository")
                return False

        except Exception as e:
            logger.error(f"Failed to remove package: {e}")
            return False

    def list_packages(self) -> List[Dict]:
        """List all packages in the repository"""
        try:
            index_path = os.path.join(self.base_path, 'repo', 'index.json')
            with open(index_path, 'r') as f:
                index = json.load(f)
            return [
                {'name': name, **info}
                for name, info in index['packages'].items()
            ]
        except Exception as e:
            logger.error(f"Failed to list packages: {e}")
            return []

    def get_package_info(self, package_name: str) -> Optional[Dict]:
        """Get detailed information about a specific package"""
        try:
            package_dir = os.path.join(self.base_path, 'repo', 'files', package_name)
            if os.path.exists(package_dir):
                with open(os.path.join(package_dir, 'package.json'), 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to get package info: {e}")
            return None

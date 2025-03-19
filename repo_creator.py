
#!/usr/bin/env python3
"""
KPM Repository Creator CLI - Standalone Version
Creates and manages KPM package repositories directly from a files directory
"""
import os
import sys
import json
import shutil
import hashlib
from datetime import datetime
from typing import Dict, List

def calculate_checksum(file_path: str) -> str:
    """Calculate SHA-256 checksum of a file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for block in iter(lambda: f.read(4096), b''):
            sha256.update(block)
    return sha256.hexdigest()

def create_repository_structure():
    """Create the basic repository structure"""
    os.makedirs('files', exist_ok=True)
    os.makedirs('repo/files', exist_ok=True)
    
    # Create initial repo index
    index = {
        'name': 'KPM Repository',
        'description': 'Kaede Package Manager Repository',
        'packages': {}
    }
    
    with open('repo/index.json', 'w') as f:
        json.dump(index, f, indent=2)

def update_package_index(package_info: Dict):
    """Update the repository index with package information"""
    try:
        with open('repo/index.json', 'r') as f:
            index = json.load(f)
        
        index['packages'][package_info['name']] = {
            'version': package_info['version'],
            'description': package_info['description'],
            'author': package_info['author']
        }
        
        with open('repo/index.json', 'w') as f:
            json.dump(index, f, indent=2)
    except Exception as e:
        print(f"Error updating index: {e}")
        sys.exit(1)

def process_package_directory(dir_path: str) -> Dict:
    """Process a package directory and create package info"""
    try:
        with open(os.path.join(dir_path, 'package.json'), 'r') as f:
            package_info = json.load(f)
        
        # Validate required fields
        required_fields = ['name', 'version', 'description', 'author', 'main']
        for field in required_fields:
            if field not in package_info:
                raise ValueError(f"Missing required field: {field}")
        
        # Calculate checksums and size
        total_size = 0
        checksums = []
        files = []
        
        for item in os.listdir(dir_path):
            if item == 'package.json':
                continue
            
            file_path = os.path.join(dir_path, item)
            if os.path.isfile(file_path):
                files.append(item)
                checksums.append(calculate_checksum(file_path))
                total_size += os.path.getsize(file_path)
        
        package_info['files'] = files
        package_info['checksum'] = hashlib.sha256(','.join(checksums).encode()).hexdigest()
        package_info['size'] = total_size
        
        return package_info
    
    except Exception as e:
        print(f"Error processing package directory {dir_path}: {e}")
        return None

def main():
    # Create repository structure
    create_repository_structure()
    print("Repository structure created")
    
    # Process all directories in /files
    files_dir = 'files'
    if not os.path.exists(files_dir):
        print("Error: /files directory not found")
        sys.exit(1)
    
    for item in os.listdir(files_dir):
        package_dir = os.path.join(files_dir, item)
        if os.path.isdir(package_dir):
            print(f"Processing package: {item}")
            
            package_info = process_package_directory(package_dir)
            if package_info:
                # Copy package to repo
                repo_package_dir = os.path.join('repo/files', item)
                if os.path.exists(repo_package_dir):
                    shutil.rmtree(repo_package_dir)
                shutil.copytree(package_dir, repo_package_dir)
                
                # Update repository index
                update_package_index(package_info)
                print(f"Successfully added package: {item}")
            else:
                print(f"Skipping invalid package: {item}")

if __name__ == '__main__':
    main()

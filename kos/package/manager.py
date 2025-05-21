"""
Enhanced package management system with dependency resolution and caching
"""
import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import logging
from functools import lru_cache
import hashlib
import subprocess
import requests

logger = logging.getLogger('KOS.package')


@dataclass
class PackageDependency:
    name: str
    version: str
    optional: bool = False

    def __str__(self):
        return f"{self.name} {self.version}"


@dataclass
class Package:
    """Package information with enhanced metadata"""
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if not isinstance(other, Package):
            return NotImplemented
        return self.name == other.name
    name: str
    version: str
    description: str
    author: str
    dependencies: List[PackageDependency]
    install_date: Optional[datetime] = None
    size: int = 0
    checksum: str = ""
    homepage: str = ""
    license: str = ""
    tags: List[str] = None
    installed: bool = False
    repository: str = "main"
    entry_point: str = ""
    cli_aliases: List[str] = None  # ADDED cli_aliases
    cli_function: str = ""  # ADDED cli_function

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.cli_aliases is None:  # Initialize cli_aliases if None
            self.cli_aliases = []
        if isinstance(self.dependencies, list) and all(
                isinstance(d, str) for d in self.dependencies):
            self.dependencies = [
                PackageDependency(d, "*") for d in self.dependencies
            ]

    def to_dict(self) -> Dict:
        return {
            'name':
            self.name,
            'version':
            self.version,
            'description':
            self.description,
            'author':
            self.author,
            'dependencies': [str(d) for d in self.dependencies],
            'install_date':
            self.install_date.isoformat() if self.install_date else None,
            'size':
            self.size,
            'checksum':
            self.checksum,
            'homepage':
            self.homepage,
            'license':
            self.license,
            'tags':
            self.tags,
            'repository':
            self.repository,
            'entry_point':
            self.entry_point,
            'cli_aliases':
            self.cli_aliases,  # ADDED cli_aliases to dict
            'cli_function':
            self.cli_function  # ADDED cli_function to dict
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Package':
        deps = data.get('dependencies', [])
        if isinstance(deps, list) and all(isinstance(d, str) for d in deps):
            deps = [PackageDependency(d, "*") for d in deps]
        install_date = None
        if data.get('install_date'):
            try:
                install_date = datetime.fromisoformat(data['install_date'])
            except ValueError:
                pass
        return Package(
            name=data['name'],
            version=data['version'],
            description=data['description'],
            author=data['author'],
            dependencies=deps,
            install_date=install_date,
            size=data.get('size', 0),
            checksum=data.get('checksum', ''),
            homepage=data.get('homepage', ''),
            license=data.get('license', ''),
            tags=data.get('tags', []),
            repository=data.get('repository', 'main'),
            entry_point=data.get('entry_point', ''),
            cli_aliases=data.get('cli_aliases',
                                 []),  # LOAD cli_aliases from dict
            cli_function=data.get('cli_function',
                                  '')  # LOAD cli_function from dict
        )

    def get_install_info(self) -> str:
        """Get formatted installation information"""
        if not self.installed:
            return "Not installed"
        return f"Installed: {self.install_date.strftime('%Y-%m-%d %H:%M:%S') if self.install_date else 'Unknown'}"


class PackageDatabase:
    """Package database with dependency resolution"""

    def __init__(self):
        self.packages: Dict[str, Package] = {}

    def add_package(self, package: Package) -> None:
        """Add or update a package in the database"""
        self.packages[package.name] = package

    def get_package(self, name: str) -> Optional[Package]:
        """Get a package by name"""
        return self.packages.get(name)

    def list_installed(self) -> List[Package]:
        """List all installed packages"""
        return [pkg for pkg in self.packages.values() if pkg.installed]

    def remove_package(self, name: str) -> bool:
        """Remove a package from the database"""
        if name in self.packages:
            del self.packages[name]
            return True
        return False

    @lru_cache(maxsize=100)
    def resolve_dependencies(self, package_name: str) -> Set[Package]:
        """Resolve package dependencies with caching"""
        resolved = set()
        if package_name not in self.packages:
            return resolved

        def resolve_recursive(pkg_name: str):
            if pkg_name in resolved:
                return
            package = self.packages[pkg_name]
            resolved.add(package)
            for dep in package.dependencies:
                if dep.name in self.packages:
                    resolve_recursive(dep.name)

        resolve_recursive(package_name)
        return resolved

    def clear_cache(self):
        """Clear the dependency resolution cache"""
        self.resolve_dependencies.cache_clear()

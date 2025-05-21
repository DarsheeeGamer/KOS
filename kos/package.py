"""KOS Package Manager CLI Package Definitions"""
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class PackageDependency:
    name: str
    version_min: Optional[str] = None
    version_max: Optional[str] = None

    def __str__(self):
        if self.version_min and self.version_max:
            return f"{self.name} (>={self.version_min}, <={self.version_max})"
        elif self.version_min:
            return f"{self.name} (>={self.version_min})"
        elif self.version_max:
            return f"{self.name} (<={self.version_max})"
        return self.name

@dataclass
class Package:
    name: str
    version: str
    description: str
    author: str
    dependencies: List[PackageDependency]
    installed: bool = False
    install_date: Optional[str] = None
    repository: str = "local"
    size: int = 0
    checksum: str = ""
    entry_point: str = "main.py"  # Default CLI entry point
    cli_function: str = ""  # Function to run for CLI
    cli_aliases: List[str] = []  # Command aliases

    @staticmethod
    def from_dict(data: Dict) -> 'Package':
        # Handle dependencies - can be either strings or dicts
        deps = []
        for dep in data.get("dependencies", []):
            if isinstance(dep, str):
                deps.append(PackageDependency(name=dep))
            else:
                deps.append(PackageDependency(
                    name=dep["name"],
                    version_min=dep.get("version_min"),
                    version_max=dep.get("version_max")
                ))

        return Package(
            name=data["name"],
            version=data["version"],
            description=data["description"],
            author=data["author"],
            dependencies=deps,
            installed=data.get("installed", False),
            install_date=data.get("install_date"),
            repository=data.get("repository", "local"),
            size=data.get("size", 0),
            checksum=data.get("checksum", ""),
            entry_point=data.get("entry_point", "main.py")
        )

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "dependencies": [
                {
                    "name": dep.name,
                    "version_min": dep.version_min,
                    "version_max": dep.version_max
                } if (dep.version_min or dep.version_max) else dep.name
                for dep in self.dependencies
            ],
            "installed": self.installed,
            "install_date": self.install_date,
            "repository": self.repository,
            "size": self.size,
            "checksum": self.checksum,
            "entry_point": self.entry_point
        }

    def get_full_name(self) -> str:
        """Get package full name with version"""
        return f"{self.name}-{self.version}"

    def get_install_info(self) -> str:
        """Get package installation information"""
        if not self.installed:
            return "Not installed"
        return f"Installed on {self.install_date}"

    def matches_version(self, version: str) -> bool:
        """Check if package matches version requirement"""
        from packaging import version as pkg_version
        try:
            return pkg_version.parse(self.version) == pkg_version.parse(version)
        except:
            return self.version == version

class PackageDatabase:
    def __init__(self):
        self.packages: Dict[str, Package] = {}

    def add_package(self, package: Package):
        """Add or update a package in the database"""
        self.packages[package.name] = package

    def get_package(self, name: str) -> Optional[Package]:
        """Get a package by name"""
        return self.packages.get(name)

    def remove_package(self, name: str):
        """Remove a package from the database"""
        if name in self.packages:
            del self.packages[name]

    def list_installed(self) -> List[Package]:
        """List all installed packages"""
        return [pkg for pkg in self.packages.values() if pkg.installed]

    def list_available(self) -> List[Package]:
        """List all available packages"""
        return list(self.packages.values())

    def resolve_dependencies(self, package_name: str) -> List[Package]:
        """Resolve all dependencies for a package"""
        resolved = []
        seen = set()

        def resolve(name: str):
            if name in seen:
                return
            seen.add(name)

            pkg = self.get_package(name)
            if not pkg:
                raise ValueError(f"Package not found: {name}")

            for dep in pkg.dependencies:
                resolve(dep.name)
            resolved.append(pkg)

        resolve(package_name)
        return resolved

    def find_matching_version(self, name: str, version: Optional[str] = None) -> Optional[Package]:
        """Find a package matching the name and version"""
        pkg = self.get_package(name)
        if not pkg:
            return None
        if version and not pkg.matches_version(version):
            return None
        return pkg
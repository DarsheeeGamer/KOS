"""
KOS System Management
====================

Core system management components providing Ubuntu-like functionality:
- Service management (systemd-like)
- Package management (KPM - Kaede Package Manager)
- Ubuntu-style command-line utilities
- Process management and monitoring
- System configuration and state management
"""

from .systemd_like import (
    ServiceManager, get_service_manager,
    ServiceUnit, SocketUnit, TimerUnit,
    ServiceState, ServiceType, RestartPolicy, UnitType,
    DependencyResolver as ServiceDependencyResolver
)

from .kpm import (
    KPMManager, get_kpm_manager,
    Package, Repository, PackageDependency, PackageVersion,
    PackageState, PackagePriority, RepositoryType,
    DependencyResolver as PackageDependencyResolver, PackageCache
)

__all__ = [
    # Service Management
    'ServiceManager', 'get_service_manager',
    'ServiceUnit', 'SocketUnit', 'TimerUnit',
    'ServiceState', 'ServiceType', 'RestartPolicy', 'UnitType',
    'ServiceDependencyResolver',
    
    # Package Management
    'KPMManager', 'get_kpm_manager',
    'Package', 'Repository', 'PackageDependency', 'PackageVersion',
    'PackageState', 'PackagePriority', 'RepositoryType',
    'PackageDependencyResolver', 'PackageCache'
] 
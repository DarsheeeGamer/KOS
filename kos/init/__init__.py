"""
KOS Init System - systemd-like init for KOS
"""

from .init_system import KOSInitSystem, InitService, ServiceState
from .service_manager import ServiceManager
from .unit_files import UnitFile, UnitType
from .systemd import (
    SystemdManager, Unit, ServiceUnit, TargetUnit,
    UnitType as SystemdUnitType, UnitState, ServiceType,
    RestartPolicy, UnitDependency, ServiceConfig, TargetConfig,
    get_systemd_manager
)

__all__ = [
    'KOSInitSystem', 'InitService', 'ServiceState', 'ServiceManager', 
    'UnitFile', 'UnitType',
    'SystemdManager', 'Unit', 'ServiceUnit', 'TargetUnit',
    'SystemdUnitType', 'UnitState', 'ServiceType',
    'RestartPolicy', 'UnitDependency', 'ServiceConfig', 'TargetConfig',
    'get_systemd_manager'
]
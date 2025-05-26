"""
Container Orchestration System for KOS

This module provides Kubernetes-like container orchestration features for KOS, including:
- Pod management (groups of containers)
- Scheduling and placement
- Service discovery
- Load balancing
- State management

The orchestration system integrates with the container, network, storage, and security
subsystems to provide a comprehensive container management platform.
"""

from .pod import Pod, PodSpec, PodStatus, PodPhase
from .scheduler import Scheduler, SchedulerPolicy
from .service import Service, ServiceSpec, ServiceType
from .controller import Controller, ControllerType, ControllerStatus
from .replica_set import ReplicaSet
from .deployment import Deployment, DeploymentStrategy, DeploymentStrategyType
from .stateful_set import StatefulSet, StatefulSetUpdateStrategy, PersistentVolumeClaimSpec
from .discovery import ServiceDiscovery, DNSProvider, DNSRecord, DNSRecordType
# Volume imports will be added when volume subsystem is implemented
# from .volume import PersistentVolume, PersistentVolumeClaim, StorageClass

__all__ = [
    'Pod', 'PodSpec', 'PodStatus', 'PodPhase',
    'Scheduler', 'SchedulerPolicy',
    'Service', 'ServiceSpec', 'ServiceType',
    'Controller', 'ControllerType', 'ControllerStatus',
    'ReplicaSet',
    'Deployment', 'DeploymentStrategy', 'DeploymentStrategyType',
    'StatefulSet', 'StatefulSetUpdateStrategy', 'PersistentVolumeClaimSpec',
    'ServiceDiscovery', 'DNSProvider', 'DNSRecord', 'DNSRecordType'
    # Volume classes will be added when volume subsystem is implemented
    # 'PersistentVolume', 'PersistentVolumeClaim', 'StorageClass'
]

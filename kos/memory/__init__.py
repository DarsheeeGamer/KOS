"""
KOS Memory Management Module
Unified memory space and byte-level data distribution
"""

from .data_distributor import (
    ByteLevelDistributor, DistributedDataObject, DataSegment,
    DistributionStrategy, DataType
)

from .coherency_protocol import (
    MOESICoherencyProtocol, CoherencyState, MessageType,
    CacheLine, CoherencyMessage
)

from .unified_memory import (
    UnifiedMemorySpace, UnifiedMemoryRegion, MemoryAllocation
)

__all__ = [
    'ByteLevelDistributor',
    'DistributedDataObject', 
    'DataSegment',
    'DistributionStrategy',
    'DataType',
    'MOESICoherencyProtocol',
    'CoherencyState',
    'MessageType',
    'CacheLine',
    'CoherencyMessage',
    'UnifiedMemorySpace',
    'UnifiedMemoryRegion',
    'MemoryAllocation'
]
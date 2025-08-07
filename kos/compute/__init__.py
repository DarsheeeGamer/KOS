"""
KOS Compute Module
Universal compute API and kernel management
"""

from .universal_api import (
    UniversalComputeAPI, UniversalKernel, KernelDefinition,
    ComputeBuffer, ExecutionContext, KernelType, ExecutionMode,
    MemoryLocation
)

__all__ = [
    'UniversalComputeAPI',
    'UniversalKernel',
    'KernelDefinition',
    'ComputeBuffer', 
    'ExecutionContext',
    'KernelType',
    'ExecutionMode',
    'MemoryLocation'
]
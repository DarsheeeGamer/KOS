"""
KOS Control Groups (cgroups) Manager
Comprehensive resource control and limitation system
"""

import os
import json
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
import subprocess

logger = logging.getLogger('kos.cgroups')


class CgroupSubsystem(Enum):
    """Cgroup subsystems/controllers"""
    CPU = "cpu"
    CPUACCT = "cpuacct"
    CPUSET = "cpuset"
    MEMORY = "memory"
    DEVICES = "devices"
    FREEZER = "freezer"
    NET_CLS = "net_cls"
    BLKIO = "blkio"
    PERF_EVENT = "perf_event"
    NET_PRIO = "net_prio"
    HUGETLB = "hugetlb"
    PIDS = "pids"
    RDMA = "rdma"


@dataclass
class CgroupLimit:
    """Resource limit configuration"""
    soft: Optional[int] = None
    hard: Optional[int] = None
    
    def to_bytes(self) -> Tuple[Optional[int], Optional[int]]:
        """Convert to bytes if needed"""
        return (self.soft, self.hard)


@dataclass
class CpuLimit:
    """CPU resource limits"""
    shares: int = 1024  # CPU shares (relative weight)
    period_us: int = 100000  # CFS period in microseconds
    quota_us: int = -1  # CFS quota in microseconds (-1 = unlimited)
    rt_period_us: int = 1000000  # RT period in microseconds
    rt_runtime_us: int = 0  # RT runtime in microseconds
    cpus: Optional[str] = None  # CPUs allowed (e.g., "0-3,5")
    mems: Optional[str] = None  # Memory nodes allowed


@dataclass
class MemoryLimit:
    """Memory resource limits"""
    limit: int = -1  # Memory limit in bytes (-1 = unlimited)
    soft_limit: int = -1  # Soft limit in bytes
    swap_limit: int = -1  # Swap + memory limit
    kernel_limit: int = -1  # Kernel memory limit
    tcp_limit: int = -1  # TCP buffer memory limit
    oom_kill_disable: bool = False  # Disable OOM killer
    swappiness: int = 60  # Swappiness value (0-100)


@dataclass
class IoLimit:
    """I/O resource limits"""
    weight: int = 100  # IO weight (10-1000)
    device_limits: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # device_limits format: {"8:0": {"read_bps": 1048576, "write_bps": 1048576}}


@dataclass
class PidsLimit:
    """PIDs resource limits"""
    max: int = -1  # Maximum number of PIDs (-1 = unlimited)


class CgroupController:
    """Base cgroup controller"""
    
    def __init__(self, subsystem: CgroupSubsystem, cgroup_path: str):
        self.subsystem = subsystem
        self.cgroup_path = cgroup_path
        self._lock = threading.Lock()
        
    def _read_value(self, filename: str) -> str:
        """Read value from cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'r') as f:
                return f.read().strip()
        except (IOError, OSError) as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return ""
            
    def _write_value(self, filename: str, value: str):
        """Write value to cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(str(value))
        except (IOError, OSError) as e:
            logger.error(f"Failed to write to {filepath}: {e}")
            
    def add_process(self, pid: int):
        """Add process to cgroup"""
        self._write_value("cgroup.procs", str(pid))
        
    def add_thread(self, tid: int):
        """Add thread to cgroup"""
        self._write_value("tasks", str(tid))
        
    def get_processes(self) -> List[int]:
        """Get list of processes in cgroup"""
        procs = self._read_value("cgroup.procs")
        return [int(pid) for pid in procs.split() if pid]
        
    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics"""
        return {}


class CpuController(CgroupController):
    """CPU cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.CPU, cgroup_path)
        
    def set_limits(self, limits: CpuLimit):
        """Set CPU limits"""
        with self._lock:
            # CPU shares
            self._write_value("cpu.shares", str(limits.shares))
            
            # CFS bandwidth control
            self._write_value("cpu.cfs_period_us", str(limits.period_us))
            self._write_value("cpu.cfs_quota_us", str(limits.quota_us))
            
            # RT bandwidth control
            self._write_value("cpu.rt_period_us", str(limits.rt_period_us))
            self._write_value("cpu.rt_runtime_us", str(limits.rt_runtime_us))
            
    def get_stats(self) -> Dict[str, Any]:
        """Get CPU statistics"""
        stats = {}
        
        # Read cpu.stat
        stat_data = self._read_value("cpu.stat")
        for line in stat_data.split('\n'):
            if line:
                key, value = line.split()
                stats[key] = int(value)
                
        # Read cpuacct.usage
        stats['usage_nsec'] = int(self._read_value("cpuacct.usage") or 0)
        
        # Read cpuacct.usage_percpu
        percpu = self._read_value("cpuacct.usage_percpu")
        if percpu:
            stats['usage_percpu'] = [int(x) for x in percpu.split()]
            
        return stats


class MemoryController(CgroupController):
    """Memory cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.MEMORY, cgroup_path)
        
    def set_limits(self, limits: MemoryLimit):
        """Set memory limits"""
        with self._lock:
            # Memory limit
            if limits.limit > 0:
                self._write_value("memory.limit_in_bytes", str(limits.limit))
                
            # Soft limit
            if limits.soft_limit > 0:
                self._write_value("memory.soft_limit_in_bytes", str(limits.soft_limit))
                
            # Swap limit
            if limits.swap_limit > 0:
                self._write_value("memory.memsw.limit_in_bytes", str(limits.swap_limit))
                
            # Kernel memory limit
            if limits.kernel_limit > 0:
                self._write_value("memory.kmem.limit_in_bytes", str(limits.kernel_limit))
                
            # TCP buffer limit
            if limits.tcp_limit > 0:
                self._write_value("memory.kmem.tcp.limit_in_bytes", str(limits.tcp_limit))
                
            # OOM control
            self._write_value("memory.oom_control", "1" if limits.oom_kill_disable else "0")
            
            # Swappiness
            self._write_value("memory.swappiness", str(limits.swappiness))
            
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        stats = {}
        
        # Current usage
        stats['usage'] = int(self._read_value("memory.usage_in_bytes") or 0)
        stats['max_usage'] = int(self._read_value("memory.max_usage_in_bytes") or 0)
        stats['limit'] = int(self._read_value("memory.limit_in_bytes") or 0)
        
        # Detailed stats
        stat_data = self._read_value("memory.stat")
        for line in stat_data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    key, value = parts
                    stats[f"stat_{key}"] = int(value)
                    
        # Pressure stats (if available)
        pressure = self._read_value("memory.pressure_level")
        if pressure:
            stats['pressure'] = pressure
            
        return stats
        
    def set_oom_score_adj(self, score: int):
        """Set OOM score adjustment (-1000 to 1000)"""
        self._write_value("memory.oom_score_adj", str(max(-1000, min(1000, score))))


class IoController(CgroupController):
    """Block I/O cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.BLKIO, cgroup_path)
        
    def set_limits(self, limits: IoLimit):
        """Set I/O limits"""
        with self._lock:
            # Weight
            self._write_value("blkio.weight", str(limits.weight))
            
            # Device limits
            for device, dev_limits in limits.device_limits.items():
                # Read bandwidth
                if 'read_bps' in dev_limits:
                    self._write_value("blkio.throttle.read_bps_device", 
                                    f"{device} {dev_limits['read_bps']}")
                    
                # Write bandwidth
                if 'write_bps' in dev_limits:
                    self._write_value("blkio.throttle.write_bps_device",
                                    f"{device} {dev_limits['write_bps']}")
                    
                # Read IOPS
                if 'read_iops' in dev_limits:
                    self._write_value("blkio.throttle.read_iops_device",
                                    f"{device} {dev_limits['read_iops']}")
                    
                # Write IOPS
                if 'write_iops' in dev_limits:
                    self._write_value("blkio.throttle.write_iops_device",
                                    f"{device} {dev_limits['write_iops']}")
                    
    def get_stats(self) -> Dict[str, Any]:
        """Get I/O statistics"""
        stats = {}
        
        # Read service bytes
        service_bytes = self._read_value("blkio.throttle.io_service_bytes")
        stats['service_bytes'] = self._parse_io_stat(service_bytes)
        
        # Read serviced ops
        serviced = self._read_value("blkio.throttle.io_serviced")
        stats['serviced'] = self._parse_io_stat(serviced)
        
        # Read queued
        queued = self._read_value("blkio.throttle.io_queued")
        stats['queued'] = self._parse_io_stat(queued)
        
        return stats
        
    def _parse_io_stat(self, data: str) -> Dict[str, Dict[str, int]]:
        """Parse I/O statistics data"""
        result = {}
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 3:
                    device, op_type, value = parts
                    if device not in result:
                        result[device] = {}
                    result[device][op_type] = int(value)
        return result


class PidsController(CgroupController):
    """PIDs cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.PIDS, cgroup_path)
        
    def set_limits(self, limits: PidsLimit):
        """Set PIDs limits"""
        with self._lock:
            if limits.max > 0:
                self._write_value("pids.max", str(limits.max))
            else:
                self._write_value("pids.max", "max")
                
    def get_stats(self) -> Dict[str, Any]:
        """Get PIDs statistics"""
        return {
            'current': int(self._read_value("pids.current") or 0),
            'max': self._read_value("pids.max")
        }


class CpusetController(CgroupController):
    """CPU set cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.CPUSET, cgroup_path)
        
    def set_cpus(self, cpus: str):
        """Set allowed CPUs (e.g., "0-3,5")"""
        self._write_value("cpuset.cpus", cpus)
        
    def set_mems(self, mems: str):
        """Set allowed memory nodes"""
        self._write_value("cpuset.mems", mems)
        
    def set_exclusive(self, cpu_exclusive: bool = False, mem_exclusive: bool = False):
        """Set exclusive access"""
        self._write_value("cpuset.cpu_exclusive", "1" if cpu_exclusive else "0")
        self._write_value("cpuset.mem_exclusive", "1" if mem_exclusive else "0")
        
    def get_effective_cpus(self) -> str:
        """Get effective CPUs"""
        return self._read_value("cpuset.effective_cpus")
        
    def get_effective_mems(self) -> str:
        """Get effective memory nodes"""
        return self._read_value("cpuset.effective_mems")


class FreezerController(CgroupController):
    """Freezer cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.FREEZER, cgroup_path)
        
    def freeze(self):
        """Freeze all processes in cgroup"""
        self._write_value("freezer.state", "FROZEN")
        
    def thaw(self):
        """Thaw all processes in cgroup"""
        self._write_value("freezer.state", "THAWED")
        
    def get_state(self) -> str:
        """Get freezer state"""
        return self._read_value("freezer.state")


class DevicesController(CgroupController):
    """Devices cgroup controller"""
    
    def __init__(self, cgroup_path: str):
        super().__init__(CgroupSubsystem.DEVICES, cgroup_path)
        
    def allow_device(self, device_type: str, major: int, minor: int, access: str):
        """Allow device access
        
        Args:
            device_type: 'c' for char device, 'b' for block device
            major: Major device number (-1 for all)
            minor: Minor device number (-1 for all)
            access: Combination of 'r' (read), 'w' (write), 'm' (mknod)
        """
        major_str = "*" if major == -1 else str(major)
        minor_str = "*" if minor == -1 else str(minor)
        rule = f"{device_type} {major_str}:{minor_str} {access}"
        self._write_value("devices.allow", rule)
        
    def deny_device(self, device_type: str, major: int, minor: int, access: str):
        """Deny device access"""
        major_str = "*" if major == -1 else str(major)
        minor_str = "*" if minor == -1 else str(minor)
        rule = f"{device_type} {major_str}:{minor_str} {access}"
        self._write_value("devices.deny", rule)
        
    def allow_all_devices(self):
        """Allow access to all devices"""
        self._write_value("devices.allow", "a")
        
    def deny_all_devices(self):
        """Deny access to all devices"""
        self._write_value("devices.deny", "a")
        
    def get_list(self) -> List[str]:
        """Get device access list"""
        data = self._read_value("devices.list")
        return data.split('\n') if data else []


class CgroupManager:
    """Main cgroup manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.cgroup_root = "/sys/fs/cgroup"
        self.groups: Dict[str, Dict[str, CgroupController]] = {}
        self._lock = threading.RLock()
        
        # Check cgroup version
        self.version = self._detect_cgroup_version()
        
        # Available subsystems
        self.available_subsystems = self._detect_subsystems()
        
        logger.info(f"Initialized cgroup manager (version: {self.version})")
        
    def _detect_cgroup_version(self) -> int:
        """Detect cgroup version (1 or 2)"""
        # Check for cgroup v2
        if os.path.exists("/sys/fs/cgroup/cgroup.controllers"):
            return 2
        return 1
        
    def _detect_subsystems(self) -> Set[CgroupSubsystem]:
        """Detect available cgroup subsystems"""
        subsystems = set()
        
        if self.version == 1:
            # Check each subsystem directory
            for subsystem in CgroupSubsystem:
                if os.path.exists(os.path.join(self.cgroup_root, subsystem.value)):
                    subsystems.add(subsystem)
        else:
            # cgroup v2 - check controllers file
            controllers_file = "/sys/fs/cgroup/cgroup.controllers"
            if os.path.exists(controllers_file):
                with open(controllers_file, 'r') as f:
                    controllers = f.read().strip().split()
                    for controller in controllers:
                        try:
                            subsystems.add(CgroupSubsystem(controller))
                        except ValueError:
                            pass
                            
        return subsystems
        
    def create_group(self, name: str, subsystems: Optional[List[CgroupSubsystem]] = None) -> bool:
        """Create new cgroup"""
        with self._lock:
            if name in self.groups:
                return False
                
            if subsystems is None:
                subsystems = list(self.available_subsystems)
                
            controllers = {}
            
            for subsystem in subsystems:
                if subsystem not in self.available_subsystems:
                    logger.warning(f"Subsystem {subsystem.value} not available")
                    continue
                    
                # Create cgroup directory
                if self.version == 1:
                    cgroup_path = os.path.join(self.cgroup_root, subsystem.value, name)
                else:
                    cgroup_path = os.path.join(self.cgroup_root, name)
                    
                try:
                    os.makedirs(cgroup_path, exist_ok=True)
                    
                    # Create appropriate controller
                    if subsystem == CgroupSubsystem.CPU:
                        controllers[subsystem.value] = CpuController(cgroup_path)
                    elif subsystem == CgroupSubsystem.MEMORY:
                        controllers[subsystem.value] = MemoryController(cgroup_path)
                    elif subsystem == CgroupSubsystem.BLKIO:
                        controllers[subsystem.value] = IoController(cgroup_path)
                    elif subsystem == CgroupSubsystem.PIDS:
                        controllers[subsystem.value] = PidsController(cgroup_path)
                    elif subsystem == CgroupSubsystem.CPUSET:
                        controllers[subsystem.value] = CpusetController(cgroup_path)
                    elif subsystem == CgroupSubsystem.FREEZER:
                        controllers[subsystem.value] = FreezerController(cgroup_path)
                    elif subsystem == CgroupSubsystem.DEVICES:
                        controllers[subsystem.value] = DevicesController(cgroup_path)
                    else:
                        controllers[subsystem.value] = CgroupController(subsystem, cgroup_path)
                        
                except OSError as e:
                    logger.error(f"Failed to create cgroup {name}: {e}")
                    return False
                    
            self.groups[name] = controllers
            logger.info(f"Created cgroup: {name}")
            return True
            
    def delete_group(self, name: str) -> bool:
        """Delete cgroup"""
        with self._lock:
            if name not in self.groups:
                return False
                
            controllers = self.groups[name]
            
            # Remove all processes first
            for controller in controllers.values():
                procs = controller.get_processes()
                if procs:
                    logger.warning(f"Cgroup {name} still has {len(procs)} processes")
                    return False
                    
            # Remove cgroup directories
            for subsystem, controller in controllers.items():
                try:
                    os.rmdir(controller.cgroup_path)
                except OSError as e:
                    logger.error(f"Failed to remove cgroup directory: {e}")
                    
            del self.groups[name]
            logger.info(f"Deleted cgroup: {name}")
            return True
            
    def get_group(self, name: str) -> Optional[Dict[str, CgroupController]]:
        """Get cgroup controllers"""
        return self.groups.get(name)
        
    def add_process_to_group(self, name: str, pid: int) -> bool:
        """Add process to cgroup"""
        with self._lock:
            controllers = self.groups.get(name)
            if not controllers:
                return False
                
            # Add to all controllers
            for controller in controllers.values():
                try:
                    controller.add_process(pid)
                except Exception as e:
                    logger.error(f"Failed to add process {pid} to {controller.subsystem.value}: {e}")
                    
            logger.info(f"Added process {pid} to cgroup {name}")
            return True
            
    def set_cpu_limits(self, name: str, limits: CpuLimit) -> bool:
        """Set CPU limits for cgroup"""
        controllers = self.get_group(name)
        if not controllers:
            return False
            
        # Set CPU controller limits
        if 'cpu' in controllers:
            cpu_controller = controllers['cpu']
            if isinstance(cpu_controller, CpuController):
                cpu_controller.set_limits(limits)
                
        # Set cpuset controller limits
        if 'cpuset' in controllers and (limits.cpus or limits.mems):
            cpuset_controller = controllers['cpuset']
            if isinstance(cpuset_controller, CpusetController):
                if limits.cpus:
                    cpuset_controller.set_cpus(limits.cpus)
                if limits.mems:
                    cpuset_controller.set_mems(limits.mems)
                    
        return True
        
    def set_memory_limits(self, name: str, limits: MemoryLimit) -> bool:
        """Set memory limits for cgroup"""
        controllers = self.get_group(name)
        if not controllers or 'memory' not in controllers:
            return False
            
        mem_controller = controllers['memory']
        if isinstance(mem_controller, MemoryController):
            mem_controller.set_limits(limits)
            return True
            
        return False
        
    def set_io_limits(self, name: str, limits: IoLimit) -> bool:
        """Set I/O limits for cgroup"""
        controllers = self.get_group(name)
        if not controllers or 'blkio' not in controllers:
            return False
            
        io_controller = controllers['blkio']
        if isinstance(io_controller, IoController):
            io_controller.set_limits(limits)
            return True
            
        return False
        
    def set_pids_limit(self, name: str, max_pids: int) -> bool:
        """Set PIDs limit for cgroup"""
        controllers = self.get_group(name)
        if not controllers or 'pids' not in controllers:
            return False
            
        pids_controller = controllers['pids']
        if isinstance(pids_controller, PidsController):
            pids_controller.set_limits(PidsLimit(max=max_pids))
            return True
            
        return False
        
    def freeze_group(self, name: str) -> bool:
        """Freeze all processes in cgroup"""
        controllers = self.get_group(name)
        if not controllers or 'freezer' not in controllers:
            return False
            
        freezer = controllers['freezer']
        if isinstance(freezer, FreezerController):
            freezer.freeze()
            return True
            
        return False
        
    def thaw_group(self, name: str) -> bool:
        """Thaw all processes in cgroup"""
        controllers = self.get_group(name)
        if not controllers or 'freezer' not in controllers:
            return False
            
        freezer = controllers['freezer']
        if isinstance(freezer, FreezerController):
            freezer.thaw()
            return True
            
        return False
        
    def get_group_stats(self, name: str) -> Dict[str, Any]:
        """Get statistics for cgroup"""
        controllers = self.get_group(name)
        if not controllers:
            return {}
            
        stats = {}
        for subsystem, controller in controllers.items():
            try:
                stats[subsystem] = controller.get_stats()
            except Exception as e:
                logger.error(f"Failed to get stats for {subsystem}: {e}")
                
        return stats
        
    def list_groups(self) -> List[str]:
        """List all cgroups"""
        with self._lock:
            return list(self.groups.keys())
            
    def create_system_groups(self):
        """Create default system cgroups"""
        # System services
        self.create_group("system", [
            CgroupSubsystem.CPU,
            CgroupSubsystem.MEMORY,
            CgroupSubsystem.BLKIO,
            CgroupSubsystem.PIDS
        ])
        
        # User sessions
        self.create_group("user", [
            CgroupSubsystem.CPU,
            CgroupSubsystem.MEMORY,
            CgroupSubsystem.PIDS
        ])
        
        # Containers
        self.create_group("containers", [
            CgroupSubsystem.CPU,
            CgroupSubsystem.MEMORY,
            CgroupSubsystem.BLKIO,
            CgroupSubsystem.PIDS,
            CgroupSubsystem.DEVICES
        ])
        
        # Virtual machines
        self.create_group("vms", [
            CgroupSubsystem.CPU,
            CgroupSubsystem.MEMORY,
            CgroupSubsystem.BLKIO
        ])


# Global cgroup manager instance
_cgroup_manager = None

def get_cgroup_manager(kernel) -> CgroupManager:
    """Get global cgroup manager"""
    global _cgroup_manager
    if _cgroup_manager is None:
        _cgroup_manager = CgroupManager(kernel)
        _cgroup_manager.create_system_groups()
    return _cgroup_manager
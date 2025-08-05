"""
KOS Control Groups v2 (Unified Hierarchy) Implementation
Modern cgroup implementation with unified controller management
"""

import os
import time
import threading
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger('kos.cgroups.v2')


class CgroupV2Controller(Enum):
    """Cgroup v2 controllers"""
    CPU = "cpu"
    MEMORY = "memory"
    IO = "io"
    PIDS = "pids"
    CPUSET = "cpuset"
    RDMA = "rdma"
    HUGETLB = "hugetlb"


@dataclass
class CgroupV2Config:
    """Cgroup v2 configuration"""
    # CPU configuration
    cpu_weight: Optional[int] = None  # 1-10000 (default 100)
    cpu_max: Optional[Tuple[int, int]] = None  # (quota, period) in microseconds
    cpu_pressure: bool = True  # Enable CPU pressure info
    
    # Memory configuration
    memory_min: Optional[int] = None  # Minimum memory guarantee
    memory_low: Optional[int] = None  # Best-effort memory protection
    memory_high: Optional[int] = None  # Memory usage throttle limit
    memory_max: Optional[int] = None  # Memory usage hard limit
    memory_swap_max: Optional[int] = None  # Swap usage limit
    memory_pressure: bool = True  # Enable memory pressure info
    
    # I/O configuration
    io_weight: Optional[int] = None  # 1-10000 (default 100)
    io_max: Optional[Dict[str, Dict[str, int]]] = None  # Device limits
    io_pressure: bool = True  # Enable I/O pressure info
    
    # PIDs configuration
    pids_max: Optional[int] = None  # Maximum number of PIDs
    
    # CPU set configuration
    cpuset_cpus: Optional[str] = None  # CPUs in which tasks can run
    cpuset_mems: Optional[str] = None  # Memory nodes in which tasks can allocate


@dataclass
class CgroupPressure:
    """Pressure Stall Information (PSI) data"""
    some_avg10: float = 0.0  # 10 second average
    some_avg60: float = 0.0  # 60 second average
    some_avg300: float = 0.0  # 300 second average
    some_total: int = 0  # Total stall time in microseconds
    full_avg10: float = 0.0
    full_avg60: float = 0.0
    full_avg300: float = 0.0
    full_total: int = 0


@dataclass
class CgroupDelegation:
    """Cgroup delegation configuration"""
    delegate_to_user: Optional[str] = None  # User to delegate to
    delegate_to_group: Optional[str] = None  # Group to delegate to
    delegated_controllers: Set[str] = field(default_factory=set)
    allow_migration: bool = True


class UnifiedController:
    """Unified cgroup v2 controller"""
    
    def __init__(self, cgroup_path: str):
        self.cgroup_path = cgroup_path
        self._lock = threading.Lock()
        
        # Ensure cgroup exists
        os.makedirs(cgroup_path, exist_ok=True)
        
        # Get enabled controllers
        self.enabled_controllers = self._get_enabled_controllers()
        
    def _read_file(self, filename: str) -> str:
        """Read from cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'r') as f:
                return f.read().strip()
        except (IOError, OSError):
            return ""
            
    def _write_file(self, filename: str, value: str):
        """Write to cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(str(value))
        except (IOError, OSError) as e:
            logger.error(f"Failed to write to {filepath}: {e}")
            
    def _get_enabled_controllers(self) -> Set[str]:
        """Get list of enabled controllers"""
        controllers = self._read_file("cgroup.controllers")
        return set(controllers.split()) if controllers else set()
        
    def enable_controllers(self, controllers: List[str]):
        """Enable controllers for child cgroups"""
        with self._lock:
            for controller in controllers:
                self._write_file("cgroup.subtree_control", f"+{controller}")
                
    def disable_controllers(self, controllers: List[str]):
        """Disable controllers for child cgroups"""
        with self._lock:
            for controller in controllers:
                self._write_file("cgroup.subtree_control", f"-{controller}")
                
    def add_process(self, pid: int):
        """Add process to cgroup"""
        self._write_file("cgroup.procs", str(pid))
        
    def add_thread(self, tid: int):
        """Add thread to cgroup"""
        self._write_file("cgroup.threads", str(tid))
        
    def get_processes(self) -> List[int]:
        """Get all processes in cgroup"""
        procs = self._read_file("cgroup.procs")
        return [int(pid) for pid in procs.split() if pid]
        
    def get_threads(self) -> List[int]:
        """Get all threads in cgroup"""
        threads = self._read_file("cgroup.threads")
        return [int(tid) for tid in threads.split() if tid]
        
    def apply_config(self, config: CgroupV2Config):
        """Apply cgroup v2 configuration"""
        with self._lock:
            # CPU configuration
            if "cpu" in self.enabled_controllers:
                if config.cpu_weight is not None:
                    self._write_file("cpu.weight", str(config.cpu_weight))
                    
                if config.cpu_max is not None:
                    quota, period = config.cpu_max
                    self._write_file("cpu.max", f"{quota} {period}")
                    
            # Memory configuration
            if "memory" in self.enabled_controllers:
                if config.memory_min is not None:
                    self._write_file("memory.min", str(config.memory_min))
                    
                if config.memory_low is not None:
                    self._write_file("memory.low", str(config.memory_low))
                    
                if config.memory_high is not None:
                    self._write_file("memory.high", str(config.memory_high))
                    
                if config.memory_max is not None:
                    self._write_file("memory.max", str(config.memory_max))
                    
                if config.memory_swap_max is not None:
                    self._write_file("memory.swap.max", str(config.memory_swap_max))
                    
            # I/O configuration
            if "io" in self.enabled_controllers:
                if config.io_weight is not None:
                    self._write_file("io.weight", str(config.io_weight))
                    
                if config.io_max is not None:
                    for device, limits in config.io_max.items():
                        for limit_type, value in limits.items():
                            self._write_file("io.max", f"{device} {limit_type}={value}")
                            
            # PIDs configuration
            if "pids" in self.enabled_controllers:
                if config.pids_max is not None:
                    self._write_file("pids.max", str(config.pids_max))
                    
            # CPU set configuration
            if "cpuset" in self.enabled_controllers:
                if config.cpuset_cpus is not None:
                    self._write_file("cpuset.cpus", config.cpuset_cpus)
                    
                if config.cpuset_mems is not None:
                    self._write_file("cpuset.mems", config.cpuset_mems)
                    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cgroup statistics"""
        stats = {
            'type': self._read_file("cgroup.type"),
            'controllers': list(self.enabled_controllers),
            'processes': len(self.get_processes()),
            'threads': len(self.get_threads())
        }
        
        # CPU stats
        if "cpu" in self.enabled_controllers:
            cpu_stat = self._parse_flat_keyed_file("cpu.stat")
            stats['cpu'] = {
                'weight': self._read_file("cpu.weight"),
                'max': self._read_file("cpu.max"),
                'stat': cpu_stat
            }
            
            # CPU pressure
            if os.path.exists(os.path.join(self.cgroup_path, "cpu.pressure")):
                stats['cpu']['pressure'] = self._parse_pressure("cpu.pressure")
                
        # Memory stats
        if "memory" in self.enabled_controllers:
            mem_stat = self._parse_flat_keyed_file("memory.stat")
            stats['memory'] = {
                'current': self._read_file("memory.current"),
                'min': self._read_file("memory.min"),
                'low': self._read_file("memory.low"),
                'high': self._read_file("memory.high"),
                'max': self._read_file("memory.max"),
                'stat': mem_stat,
                'events': self._parse_flat_keyed_file("memory.events")
            }
            
            # Memory pressure
            if os.path.exists(os.path.join(self.cgroup_path, "memory.pressure")):
                stats['memory']['pressure'] = self._parse_pressure("memory.pressure")
                
        # I/O stats
        if "io" in self.enabled_controllers:
            stats['io'] = {
                'weight': self._read_file("io.weight"),
                'stat': self._parse_io_stat("io.stat")
            }
            
            # I/O pressure
            if os.path.exists(os.path.join(self.cgroup_path, "io.pressure")):
                stats['io']['pressure'] = self._parse_pressure("io.pressure")
                
        # PIDs stats
        if "pids" in self.enabled_controllers:
            stats['pids'] = {
                'current': self._read_file("pids.current"),
                'max': self._read_file("pids.max"),
                'events': self._parse_flat_keyed_file("pids.events")
            }
            
        return stats
        
    def _parse_flat_keyed_file(self, filename: str) -> Dict[str, int]:
        """Parse flat keyed file format (key value pairs)"""
        data = self._read_file(filename)
        result = {}
        
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    key, value = parts
                    try:
                        result[key] = int(value)
                    except ValueError:
                        result[key] = value
                        
        return result
        
    def _parse_pressure(self, filename: str) -> Dict[str, CgroupPressure]:
        """Parse pressure stall information"""
        data = self._read_file(filename)
        result = {}
        
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if parts[0] in ['some', 'full']:
                    pressure = CgroupPressure()
                    
                    for metric in parts[1:]:
                        key, value = metric.split('=')
                        if key == 'avg10':
                            setattr(pressure, f'{parts[0]}_avg10', float(value))
                        elif key == 'avg60':
                            setattr(pressure, f'{parts[0]}_avg60', float(value))
                        elif key == 'avg300':
                            setattr(pressure, f'{parts[0]}_avg300', float(value))
                        elif key == 'total':
                            setattr(pressure, f'{parts[0]}_total', int(value))
                            
                    result[parts[0]] = pressure
                    
        return result
        
    def _parse_io_stat(self, filename: str) -> Dict[str, Dict[str, int]]:
        """Parse I/O statistics"""
        data = self._read_file(filename)
        result = {}
        
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if parts:
                    device = parts[0]
                    result[device] = {}
                    
                    for metric in parts[1:]:
                        key, value = metric.split('=')
                        result[device][key] = int(value)
                        
        return result
        
    def set_type(self, cgroup_type: str):
        """Set cgroup type (domain, threaded, etc.)"""
        valid_types = ['domain', 'threaded', 'domain threaded', 'domain invalid']
        if cgroup_type in valid_types:
            self._write_file("cgroup.type", cgroup_type)
            
    def freeze(self):
        """Freeze all processes in cgroup"""
        self._write_file("cgroup.freeze", "1")
        
    def thaw(self):
        """Thaw all processes in cgroup"""
        self._write_file("cgroup.freeze", "0")
        
    def is_frozen(self) -> bool:
        """Check if cgroup is frozen"""
        return self._read_file("cgroup.freeze") == "1"
        
    def kill_all(self):
        """Kill all processes in cgroup"""
        self._write_file("cgroup.kill", "1")


class CgroupV2Manager:
    """Cgroup v2 hierarchy manager"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.root_path = "/sys/fs/cgroup"
        self.groups: Dict[str, UnifiedController] = {}
        self._lock = threading.RLock()
        
        # Verify cgroup v2
        if not self._is_cgroup_v2():
            raise RuntimeError("Cgroup v2 not available")
            
        # Get available controllers
        self.available_controllers = self._get_available_controllers()
        
        logger.info(f"Initialized cgroup v2 manager (controllers: {self.available_controllers})")
        
    def _is_cgroup_v2(self) -> bool:
        """Check if cgroup v2 is available"""
        return os.path.exists(os.path.join(self.root_path, "cgroup.controllers"))
        
    def _get_available_controllers(self) -> Set[str]:
        """Get available controllers"""
        controllers_file = os.path.join(self.root_path, "cgroup.controllers")
        try:
            with open(controllers_file, 'r') as f:
                return set(f.read().strip().split())
        except (IOError, OSError):
            return set()
            
    def create_group(self, path: str, enable_controllers: Optional[List[str]] = None) -> UnifiedController:
        """Create new cgroup"""
        with self._lock:
            full_path = os.path.join(self.root_path, path.lstrip('/'))
            
            # Create unified controller
            controller = UnifiedController(full_path)
            
            # Enable controllers if specified
            if enable_controllers:
                # Enable in parent first
                parent_path = os.path.dirname(full_path)
                if parent_path != self.root_path:
                    parent = UnifiedController(parent_path)
                    parent.enable_controllers(enable_controllers)
                    
            self.groups[path] = controller
            logger.info(f"Created cgroup v2: {path}")
            return controller
            
    def get_group(self, path: str) -> Optional[UnifiedController]:
        """Get cgroup controller"""
        return self.groups.get(path)
        
    def delete_group(self, path: str) -> bool:
        """Delete cgroup"""
        with self._lock:
            if path not in self.groups:
                return False
                
            controller = self.groups[path]
            
            # Check if empty
            if controller.get_processes():
                logger.warning(f"Cannot delete non-empty cgroup: {path}")
                return False
                
            # Remove directory
            try:
                os.rmdir(controller.cgroup_path)
                del self.groups[path]
                logger.info(f"Deleted cgroup v2: {path}")
                return True
            except OSError as e:
                logger.error(f"Failed to delete cgroup: {e}")
                return False
                
    def setup_delegation(self, path: str, delegation: CgroupDelegation):
        """Setup cgroup delegation"""
        controller = self.get_group(path)
        if not controller:
            return
            
        # Set ownership
        if delegation.delegate_to_user or delegation.delegate_to_group:
            import pwd
            import grp
            
            uid = -1
            gid = -1
            
            if delegation.delegate_to_user:
                try:
                    uid = pwd.getpwnam(delegation.delegate_to_user).pw_uid
                except KeyError:
                    logger.error(f"User not found: {delegation.delegate_to_user}")
                    
            if delegation.delegate_to_group:
                try:
                    gid = grp.getgrnam(delegation.delegate_to_group).gr_gid
                except KeyError:
                    logger.error(f"Group not found: {delegation.delegate_to_group}")
                    
            if uid != -1 or gid != -1:
                os.chown(controller.cgroup_path, uid, gid)
                
                # Set permissions
                os.chmod(controller.cgroup_path, 0o755)
                
                # Make control files writable by owner
                for filename in os.listdir(controller.cgroup_path):
                    filepath = os.path.join(controller.cgroup_path, filename)
                    if os.path.isfile(filepath):
                        os.chmod(filepath, 0o644)
                        
        # Enable controllers for delegation
        if delegation.delegated_controllers:
            controller.enable_controllers(list(delegation.delegated_controllers))
            
    def migrate_process(self, pid: int, from_path: str, to_path: str) -> bool:
        """Migrate process between cgroups"""
        to_controller = self.get_group(to_path)
        if not to_controller:
            return False
            
        try:
            to_controller.add_process(pid)
            logger.info(f"Migrated process {pid} from {from_path} to {to_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to migrate process: {e}")
            return False
            
    def create_slice(self, name: str, config: CgroupV2Config) -> UnifiedController:
        """Create system slice (similar to systemd slice)"""
        slice_path = f"kos.slice/{name}.slice"
        
        # Create with all controllers
        controller = self.create_group(slice_path, list(self.available_controllers))
        
        # Apply configuration
        controller.apply_config(config)
        
        return controller
        
    def create_scope(self, name: str, pids: List[int], config: CgroupV2Config) -> UnifiedController:
        """Create transient scope for group of processes"""
        scope_path = f"kos.slice/{name}.scope"
        
        # Create scope
        controller = self.create_group(scope_path, list(self.available_controllers))
        
        # Apply configuration
        controller.apply_config(config)
        
        # Add processes
        for pid in pids:
            controller.add_process(pid)
            
        return controller
        
    def get_system_pressure(self) -> Dict[str, Any]:
        """Get system-wide pressure information"""
        pressure = {}
        
        # CPU pressure
        cpu_pressure_file = "/proc/pressure/cpu"
        if os.path.exists(cpu_pressure_file):
            with open(cpu_pressure_file, 'r') as f:
                pressure['cpu'] = f.read().strip()
                
        # Memory pressure
        mem_pressure_file = "/proc/pressure/memory"
        if os.path.exists(mem_pressure_file):
            with open(mem_pressure_file, 'r') as f:
                pressure['memory'] = f.read().strip()
                
        # I/O pressure
        io_pressure_file = "/proc/pressure/io"
        if os.path.exists(io_pressure_file):
            with open(io_pressure_file, 'r') as f:
                pressure['io'] = f.read().strip()
                
        return pressure
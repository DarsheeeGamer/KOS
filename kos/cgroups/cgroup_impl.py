"""
KOS Real Cgroup Implementation
Direct cgroup filesystem manipulation without simulation
"""

import os
import time
import logging
from typing import Dict, List, Set, Optional, Any
from pathlib import Path

logger = logging.getLogger('kos.cgroups.impl')


class RealCgroupController:
    """Real cgroup controller implementation"""
    
    def __init__(self, subsystem: str, cgroup_path: str):
        self.subsystem = subsystem
        self.cgroup_path = cgroup_path
        
        # Create cgroup directory if it doesn't exist
        os.makedirs(cgroup_path, exist_ok=True)
        
    def _read_file(self, filename: str) -> str:
        """Read from cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'r') as f:
                return f.read().strip()
        except (IOError, OSError) as e:
            logger.debug(f"Failed to read {filepath}: {e}")
            return ""
            
    def _write_file(self, filename: str, value: str) -> bool:
        """Write to cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(str(value))
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to write to {filepath}: {e}")
            return False
            
    def _write_file_append(self, filename: str, value: str) -> bool:
        """Append to cgroup file"""
        filepath = os.path.join(self.cgroup_path, filename)
        try:
            with open(filepath, 'a') as f:
                f.write(str(value) + '\n')
            return True
        except (IOError, OSError) as e:
            logger.error(f"Failed to append to {filepath}: {e}")
            return False
            
    def add_process(self, pid: int) -> bool:
        """Add process to cgroup"""
        return self._write_file("cgroup.procs", str(pid))
        
    def add_thread(self, tid: int) -> bool:
        """Add thread to cgroup"""
        return self._write_file("tasks", str(tid))
        
    def get_processes(self) -> List[int]:
        """Get all processes in cgroup"""
        procs = self._read_file("cgroup.procs")
        return [int(pid) for pid in procs.split() if pid.isdigit()]
        
    def get_threads(self) -> List[int]:
        """Get all threads in cgroup"""
        tasks = self._read_file("tasks")
        return [int(tid) for tid in tasks.split() if tid.isdigit()]
        
    def remove(self) -> bool:
        """Remove cgroup (must be empty)"""
        try:
            os.rmdir(self.cgroup_path)
            return True
        except OSError as e:
            logger.error(f"Failed to remove cgroup: {e}")
            return False


class RealCpuController(RealCgroupController):
    """Real CPU cgroup controller"""
    
    def set_shares(self, shares: int) -> bool:
        """Set CPU shares (relative weight)"""
        return self._write_file("cpu.shares", str(shares))
        
    def set_cfs_quota(self, quota_us: int) -> bool:
        """Set CFS quota in microseconds (-1 for unlimited)"""
        return self._write_file("cpu.cfs_quota_us", str(quota_us))
        
    def set_cfs_period(self, period_us: int) -> bool:
        """Set CFS period in microseconds"""
        return self._write_file("cpu.cfs_period_us", str(period_us))
        
    def set_rt_runtime(self, runtime_us: int) -> bool:
        """Set RT runtime in microseconds"""
        return self._write_file("cpu.rt_runtime_us", str(runtime_us))
        
    def set_rt_period(self, period_us: int) -> bool:
        """Set RT period in microseconds"""
        return self._write_file("cpu.rt_period_us", str(period_us))
        
    def get_stats(self) -> Dict[str, int]:
        """Get CPU statistics"""
        stats = {}
        
        # Read cpu.stat
        stat_data = self._read_file("cpu.stat")
        for line in stat_data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    key, value = parts
                    stats[key] = int(value)
                    
        # Read cpuacct.usage
        usage = self._read_file("cpuacct.usage")
        if usage:
            stats['usage_nsec'] = int(usage)
            
        # Read cpuacct.usage_percpu
        percpu = self._read_file("cpuacct.usage_percpu")
        if percpu:
            stats['usage_percpu'] = [int(x) for x in percpu.split()]
            
        # Read cpuacct.usage_sys
        usage_sys = self._read_file("cpuacct.usage_sys")
        if usage_sys:
            stats['usage_sys'] = int(usage_sys)
            
        # Read cpuacct.usage_user
        usage_user = self._read_file("cpuacct.usage_user")
        if usage_user:
            stats['usage_user'] = int(usage_user)
            
        return stats


class RealMemoryController(RealCgroupController):
    """Real memory cgroup controller"""
    
    def set_limit(self, limit_bytes: int) -> bool:
        """Set memory limit in bytes"""
        return self._write_file("memory.limit_in_bytes", str(limit_bytes))
        
    def set_soft_limit(self, limit_bytes: int) -> bool:
        """Set soft memory limit in bytes"""
        return self._write_file("memory.soft_limit_in_bytes", str(limit_bytes))
        
    def set_memsw_limit(self, limit_bytes: int) -> bool:
        """Set memory + swap limit in bytes"""
        return self._write_file("memory.memsw.limit_in_bytes", str(limit_bytes))
        
    def set_kmem_limit(self, limit_bytes: int) -> bool:
        """Set kernel memory limit in bytes"""
        return self._write_file("memory.kmem.limit_in_bytes", str(limit_bytes))
        
    def set_tcp_limit(self, limit_bytes: int) -> bool:
        """Set TCP buffer memory limit in bytes"""
        return self._write_file("memory.kmem.tcp.limit_in_bytes", str(limit_bytes))
        
    def set_swappiness(self, swappiness: int) -> bool:
        """Set swappiness (0-100)"""
        return self._write_file("memory.swappiness", str(swappiness))
        
    def set_oom_control(self, disable: bool) -> bool:
        """Enable/disable OOM killer"""
        return self._write_file("memory.oom_control", "1" if disable else "0")
        
    def force_empty(self) -> bool:
        """Force empty memory cgroup"""
        return self._write_file("memory.force_empty", "0")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        stats = {}
        
        # Current usage
        usage = self._read_file("memory.usage_in_bytes")
        if usage:
            stats['usage'] = int(usage)
            
        # Max usage
        max_usage = self._read_file("memory.max_usage_in_bytes")
        if max_usage:
            stats['max_usage'] = int(max_usage)
            
        # Limit
        limit = self._read_file("memory.limit_in_bytes")
        if limit:
            stats['limit'] = int(limit)
            
        # Detailed stats
        stat_data = self._read_file("memory.stat")
        for line in stat_data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    key, value = parts
                    stats[f'stat_{key}'] = int(value)
                    
        # Failcnt
        failcnt = self._read_file("memory.failcnt")
        if failcnt:
            stats['failcnt'] = int(failcnt)
            
        # OOM control
        oom_control = self._read_file("memory.oom_control")
        if oom_control:
            for line in oom_control.split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) == 2:
                        key, value = parts
                        stats[f'oom_{key}'] = int(value)
                        
        return stats
        
    def reset_max_usage(self) -> bool:
        """Reset max usage counter"""
        return self._write_file("memory.max_usage_in_bytes", "0")
        
    def reset_failcnt(self) -> bool:
        """Reset fail counter"""
        return self._write_file("memory.failcnt", "0")


class RealBlkioController(RealCgroupController):
    """Real block I/O cgroup controller"""
    
    def set_weight(self, weight: int) -> bool:
        """Set block I/O weight (100-1000)"""
        return self._write_file("blkio.weight", str(weight))
        
    def set_weight_device(self, major: int, minor: int, weight: int) -> bool:
        """Set per-device weight"""
        return self._write_file("blkio.weight_device", f"{major}:{minor} {weight}")
        
    def set_throttle_read_bps(self, major: int, minor: int, bps: int) -> bool:
        """Set read bandwidth limit"""
        return self._write_file("blkio.throttle.read_bps_device", f"{major}:{minor} {bps}")
        
    def set_throttle_write_bps(self, major: int, minor: int, bps: int) -> bool:
        """Set write bandwidth limit"""
        return self._write_file("blkio.throttle.write_bps_device", f"{major}:{minor} {bps}")
        
    def set_throttle_read_iops(self, major: int, minor: int, iops: int) -> bool:
        """Set read IOPS limit"""
        return self._write_file("blkio.throttle.read_iops_device", f"{major}:{minor} {iops}")
        
    def set_throttle_write_iops(self, major: int, minor: int, iops: int) -> bool:
        """Set write IOPS limit"""
        return self._write_file("blkio.throttle.write_iops_device", f"{major}:{minor} {iops}")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get block I/O statistics"""
        stats = {}
        
        # Parse various stat files
        stat_files = [
            "blkio.io_service_bytes",
            "blkio.io_serviced",
            "blkio.io_service_time",
            "blkio.io_wait_time",
            "blkio.io_merged",
            "blkio.io_queued",
            "blkio.throttle.io_service_bytes",
            "blkio.throttle.io_serviced"
        ]
        
        for stat_file in stat_files:
            data = self._read_file(stat_file)
            if data:
                stats[stat_file] = self._parse_blkio_stat(data)
                
        return stats
        
    def _parse_blkio_stat(self, data: str) -> Dict[str, Dict[str, int]]:
        """Parse block I/O statistics format"""
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
        
    def reset_stats(self) -> bool:
        """Reset block I/O statistics"""
        return self._write_file("blkio.reset_stats", "1")


class RealDevicesController(RealCgroupController):
    """Real devices cgroup controller"""
    
    def allow(self, device_type: str, major: int, minor: int, access: str) -> bool:
        """Allow device access"""
        major_str = "*" if major == -1 else str(major)
        minor_str = "*" if minor == -1 else str(minor)
        rule = f"{device_type} {major_str}:{minor_str} {access}"
        return self._write_file("devices.allow", rule)
        
    def deny(self, device_type: str, major: int, minor: int, access: str) -> bool:
        """Deny device access"""
        major_str = "*" if major == -1 else str(major)
        minor_str = "*" if minor == -1 else str(minor)
        rule = f"{device_type} {major_str}:{minor_str} {access}"
        return self._write_file("devices.deny", rule)
        
    def allow_all(self) -> bool:
        """Allow all devices"""
        return self._write_file("devices.allow", "a")
        
    def deny_all(self) -> bool:
        """Deny all devices"""
        return self._write_file("devices.deny", "a")
        
    def get_list(self) -> List[str]:
        """Get device access list"""
        data = self._read_file("devices.list")
        return data.split('\n') if data else []


class RealFreezerController(RealCgroupController):
    """Real freezer cgroup controller"""
    
    def freeze(self) -> bool:
        """Freeze all processes in cgroup"""
        return self._write_file("freezer.state", "FROZEN")
        
    def thaw(self) -> bool:
        """Thaw all processes in cgroup"""
        return self._write_file("freezer.state", "THAWED")
        
    def get_state(self) -> str:
        """Get freezer state"""
        return self._read_file("freezer.state")
        
    def wait_frozen(self, timeout: float = 5.0) -> bool:
        """Wait for cgroup to be frozen"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.get_state() == "FROZEN":
                return True
            time.sleep(0.1)
        return False
        
    def wait_thawed(self, timeout: float = 5.0) -> bool:
        """Wait for cgroup to be thawed"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.get_state() == "THAWED":
                return True
            time.sleep(0.1)
        return False


class RealPidsController(RealCgroupController):
    """Real PIDs cgroup controller"""
    
    def set_max(self, max_pids: int) -> bool:
        """Set maximum number of PIDs"""
        if max_pids < 0:
            return self._write_file("pids.max", "max")
        else:
            return self._write_file("pids.max", str(max_pids))
            
    def get_current(self) -> int:
        """Get current number of PIDs"""
        current = self._read_file("pids.current")
        return int(current) if current else 0
        
    def get_max(self) -> str:
        """Get maximum PIDs setting"""
        return self._read_file("pids.max")
        
    def get_events(self) -> Dict[str, int]:
        """Get PIDs events"""
        events = {}
        data = self._read_file("pids.events")
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    key, value = parts
                    events[key] = int(value)
        return events


class RealCpusetController(RealCgroupController):
    """Real cpuset cgroup controller"""
    
    def set_cpus(self, cpus: str) -> bool:
        """Set allowed CPUs"""
        return self._write_file("cpuset.cpus", cpus)
        
    def set_mems(self, mems: str) -> bool:
        """Set allowed memory nodes"""
        return self._write_file("cpuset.mems", mems)
        
    def set_cpu_exclusive(self, exclusive: bool) -> bool:
        """Set CPU exclusive"""
        return self._write_file("cpuset.cpu_exclusive", "1" if exclusive else "0")
        
    def set_mem_exclusive(self, exclusive: bool) -> bool:
        """Set memory exclusive"""
        return self._write_file("cpuset.mem_exclusive", "1" if exclusive else "0")
        
    def set_mem_hardwall(self, hardwall: bool) -> bool:
        """Set memory hardwall"""
        return self._write_file("cpuset.mem_hardwall", "1" if hardwall else "0")
        
    def set_memory_migrate(self, migrate: bool) -> bool:
        """Set memory migration on move"""
        return self._write_file("cpuset.memory_migrate", "1" if migrate else "0")
        
    def set_memory_spread_page(self, spread: bool) -> bool:
        """Set page cache spread"""
        return self._write_file("cpuset.memory_spread_page", "1" if spread else "0")
        
    def set_memory_spread_slab(self, spread: bool) -> bool:
        """Set slab cache spread"""
        return self._write_file("cpuset.memory_spread_slab", "1" if spread else "0")
        
    def set_sched_load_balance(self, balance: bool) -> bool:
        """Set scheduler load balancing"""
        return self._write_file("cpuset.sched_load_balance", "1" if balance else "0")
        
    def set_sched_relax_domain_level(self, level: int) -> bool:
        """Set scheduler relax domain level"""
        return self._write_file("cpuset.sched_relax_domain_level", str(level))
        
    def get_effective_cpus(self) -> str:
        """Get effective CPUs"""
        return self._read_file("cpuset.effective_cpus")
        
    def get_effective_mems(self) -> str:
        """Get effective memory nodes"""
        return self._read_file("cpuset.effective_mems")
        
    def get_memory_pressure(self) -> str:
        """Get memory pressure"""
        return self._read_file("cpuset.memory_pressure")
        
    def get_memory_pressure_enabled(self) -> bool:
        """Check if memory pressure is enabled"""
        enabled = self._read_file("cpuset.memory_pressure_enabled")
        return enabled == "1"


class RealNetClsController(RealCgroupController):
    """Real net_cls cgroup controller"""
    
    def set_classid(self, classid: int) -> bool:
        """Set network class ID"""
        return self._write_file("net_cls.classid", str(classid))
        
    def get_classid(self) -> int:
        """Get network class ID"""
        classid = self._read_file("net_cls.classid")
        return int(classid) if classid else 0


class RealNetPrioController(RealCgroupController):
    """Real net_prio cgroup controller"""
    
    def set_ifpriomap(self, interface: str, priority: int) -> bool:
        """Set interface priority map"""
        return self._write_file("net_prio.ifpriomap", f"{interface} {priority}")
        
    def get_prioidx(self) -> int:
        """Get priority index"""
        idx = self._read_file("net_prio.prioidx")
        return int(idx) if idx else 0
        
    def get_ifpriomap(self) -> Dict[str, int]:
        """Get interface priority map"""
        priomap = {}
        data = self._read_file("net_prio.ifpriomap")
        for line in data.split('\n'):
            if line:
                parts = line.split()
                if len(parts) == 2:
                    interface, priority = parts
                    priomap[interface] = int(priority)
        return priomap
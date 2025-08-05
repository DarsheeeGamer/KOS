"""
ProcFS - Process Filesystem Implementation
Provides process and system information through a virtual filesystem interface
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from kos.filesystem.base import FileSystem, FileNode, DirectoryNode


class ProcFileNode(FileNode):
    """Special file node that generates content dynamically"""
    
    def __init__(self, name: str, generator_func):
        super().__init__(name)
        self.generator_func = generator_func
        self._size = 0
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Generate and read content"""
        content = self.generator_func()
        if isinstance(content, str):
            content = content.encode('utf-8')
        
        if offset >= len(content):
            return b''
        
        if size == -1:
            return content[offset:]
        else:
            return content[offset:offset + size]
    
    @property
    def size(self) -> int:
        """Get dynamic size"""
        content = self.generator_func()
        if isinstance(content, str):
            return len(content.encode('utf-8'))
        return len(content)


class ProcessDirectoryNode(DirectoryNode):
    """Directory node for a specific process"""
    
    def __init__(self, pid: int, process_info: Dict[str, Any]):
        super().__init__(str(pid))
        self.pid = pid
        self.process_info = process_info
        self._create_process_files()
    
    def _create_process_files(self):
        """Create standard process info files"""
        # /proc/[pid]/status
        self.add_child(ProcFileNode('status', lambda: self._generate_status()))
        
        # /proc/[pid]/cmdline
        self.add_child(ProcFileNode('cmdline', lambda: self._generate_cmdline()))
        
        # /proc/[pid]/environ
        self.add_child(ProcFileNode('environ', lambda: self._generate_environ()))
        
        # /proc/[pid]/stat
        self.add_child(ProcFileNode('stat', lambda: self._generate_stat()))
        
        # /proc/[pid]/statm
        self.add_child(ProcFileNode('statm', lambda: self._generate_statm()))
        
        # /proc/[pid]/maps
        self.add_child(ProcFileNode('maps', lambda: self._generate_maps()))
        
        # /proc/[pid]/fd/ directory
        fd_dir = DirectoryNode('fd')
        self.add_child(fd_dir)
    
    def _generate_status(self) -> str:
        """Generate /proc/[pid]/status content"""
        info = self.process_info
        return f"""Name:\t{info.get('name', 'unknown')}
State:\t{info.get('state', 'R')} ({info.get('state_desc', 'running')})
Pid:\t{self.pid}
PPid:\t{info.get('ppid', 1)}
TracerPid:\t0
Uid:\t{info.get('uid', 1000)}\t{info.get('uid', 1000)}\t{info.get('uid', 1000)}\t{info.get('uid', 1000)}
Gid:\t{info.get('gid', 1000)}\t{info.get('gid', 1000)}\t{info.get('gid', 1000)}\t{info.get('gid', 1000)}
VmSize:\t{info.get('vm_size', 0)} kB
VmRSS:\t{info.get('vm_rss', 0)} kB
VmData:\t{info.get('vm_data', 0)} kB
VmStk:\t{info.get('vm_stk', 0)} kB
VmExe:\t{info.get('vm_exe', 0)} kB
Threads:\t{info.get('threads', 1)}
"""
    
    def _generate_cmdline(self) -> bytes:
        """Generate /proc/[pid]/cmdline content"""
        cmdline = self.process_info.get('cmdline', [])
        if cmdline:
            return '\0'.join(cmdline).encode('utf-8') + b'\0'
        return b''
    
    def _generate_environ(self) -> bytes:
        """Generate /proc/[pid]/environ content"""
        environ = self.process_info.get('environ', {})
        parts = []
        for key, value in environ.items():
            parts.append(f"{key}={value}")
        if parts:
            return '\0'.join(parts).encode('utf-8') + b'\0'
        return b''
    
    def _generate_stat(self) -> str:
        """Generate /proc/[pid]/stat content"""
        info = self.process_info
        return f"{self.pid} ({info.get('name', 'unknown')}) {info.get('state', 'R')} {info.get('ppid', 1)} {info.get('pgrp', self.pid)} {info.get('session', self.pid)} 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
    
    def _generate_statm(self) -> str:
        """Generate /proc/[pid]/statm content"""
        info = self.process_info
        # size resident shared text lib data dt
        pages = info.get('vm_size', 0) // 4  # Convert KB to pages
        return f"{pages} {info.get('vm_rss', 0) // 4} 0 0 0 0 0"
    
    def _generate_maps(self) -> str:
        """Generate /proc/[pid]/maps content"""
        # Simplified memory map
        return """00400000-00452000 r-xp 00000000 08:02 173521      /usr/bin/dbus-daemon
00651000-00652000 r--p 00051000 08:02 173521      /usr/bin/dbus-daemon
00652000-00655000 rw-p 00052000 08:02 173521      /usr/bin/dbus-daemon
00e03000-00e24000 rw-p 00000000 00:00 0           [heap]
7f104000-7f204000 rw-p 00000000 00:00 0           [stack]
"""


class ProcFS(FileSystem):
    """Process filesystem implementation"""
    
    def __init__(self):
        super().__init__()
        self.processes: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._init_static_files()
    
    def _init_static_files(self):
        """Initialize static proc files"""
        # /proc/version
        self.root.add_child(ProcFileNode('version', self._get_version))
        
        # /proc/uptime
        self.root.add_child(ProcFileNode('uptime', self._get_uptime))
        
        # /proc/loadavg
        self.root.add_child(ProcFileNode('loadavg', self._get_loadavg))
        
        # /proc/meminfo
        self.root.add_child(ProcFileNode('meminfo', self._get_meminfo))
        
        # /proc/cpuinfo
        self.root.add_child(ProcFileNode('cpuinfo', self._get_cpuinfo))
        
        # /proc/stat
        self.root.add_child(ProcFileNode('stat', self._get_stat))
        
        # /proc/filesystems
        self.root.add_child(ProcFileNode('filesystems', self._get_filesystems))
        
        # /proc/mounts
        self.root.add_child(ProcFileNode('mounts', self._get_mounts))
        
        # /proc/devices
        self.root.add_child(ProcFileNode('devices', self._get_devices))
        
        # /proc/modules
        self.root.add_child(ProcFileNode('modules', self._get_modules))
        
        # /proc/net directory
        net_dir = DirectoryNode('net')
        net_dir.add_child(ProcFileNode('dev', self._get_net_dev))
        net_dir.add_child(ProcFileNode('route', self._get_net_route))
        net_dir.add_child(ProcFileNode('tcp', self._get_net_tcp))
        self.root.add_child(net_dir)
        
        # /proc/sys directory structure
        sys_dir = DirectoryNode('sys')
        
        # /proc/sys/kernel
        kernel_dir = DirectoryNode('kernel')
        kernel_dir.add_child(ProcFileNode('hostname', self._get_hostname))
        kernel_dir.add_child(ProcFileNode('ostype', lambda: 'KOS\n'))
        kernel_dir.add_child(ProcFileNode('osrelease', lambda: '1.0.0\n'))
        kernel_dir.add_child(ProcFileNode('version', lambda: '#1 SMP PREEMPT_DYNAMIC\n'))
        sys_dir.add_child(kernel_dir)
        
        # /proc/sys/vm
        vm_dir = DirectoryNode('vm')
        vm_dir.add_child(ProcFileNode('swappiness', lambda: '60\n'))
        vm_dir.add_child(ProcFileNode('overcommit_memory', lambda: '0\n'))
        sys_dir.add_child(vm_dir)
        
        self.root.add_child(sys_dir)
    
    def register_process(self, pid: int, process_info: Dict[str, Any]):
        """Register a process in procfs"""
        with self._lock:
            self.processes[pid] = process_info
            proc_dir = ProcessDirectoryNode(pid, process_info)
            self.root.add_child(proc_dir)
    
    def unregister_process(self, pid: int):
        """Remove a process from procfs"""
        with self._lock:
            if pid in self.processes:
                del self.processes[pid]
                # Remove directory node
                for child in list(self.root.children.values()):
                    if isinstance(child, ProcessDirectoryNode) and child.pid == pid:
                        self.root.remove_child(child.name)
                        break
    
    def update_process(self, pid: int, process_info: Dict[str, Any]):
        """Update process information"""
        with self._lock:
            if pid in self.processes:
                self.processes[pid].update(process_info)
    
    def _get_version(self) -> str:
        """Generate /proc/version"""
        return "KOS version 1.0.0 (kos@kaede) (gcc version 11.4.0) #1 SMP PREEMPT_DYNAMIC\n"
    
    def _get_uptime(self) -> str:
        """Generate /proc/uptime"""
        uptime = time.time()  # Simplified - should track actual boot time
        idle = uptime * 0.9  # Simplified idle time
        return f"{uptime:.2f} {idle:.2f}\n"
    
    def _get_loadavg(self) -> str:
        """Generate /proc/loadavg"""
        # Simplified load average
        load1 = len(self.processes) * 0.7
        load5 = len(self.processes) * 0.5
        load15 = len(self.processes) * 0.3
        running = sum(1 for p in self.processes.values() if p.get('state') == 'R')
        total = len(self.processes)
        last_pid = max(self.processes.keys()) if self.processes else 1
        return f"{load1:.2f} {load5:.2f} {load15:.2f} {running}/{total} {last_pid}\n"
    
    def _get_meminfo(self) -> str:
        """Generate /proc/meminfo"""
        # Simplified memory info
        total_mem = 8 * 1024 * 1024  # 8GB in KB
        free_mem = 4 * 1024 * 1024   # 4GB free
        available = 5 * 1024 * 1024  # 5GB available
        
        return f"""MemTotal:       {total_mem} kB
MemFree:        {free_mem} kB
MemAvailable:   {available} kB
Buffers:        {100000} kB
Cached:         {500000} kB
SwapCached:     0 kB
Active:         {1000000} kB
Inactive:       {500000} kB
SwapTotal:      0 kB
SwapFree:       0 kB
Dirty:          0 kB
Writeback:      0 kB
Mapped:         {200000} kB
Shmem:          {50000} kB
Slab:           {100000} kB
"""
    
    def _get_cpuinfo(self) -> str:
        """Generate /proc/cpuinfo"""
        # Simplified CPU info
        return """processor       : 0
vendor_id       : KaedeVirtual
cpu family      : 23
model           : 1
model name      : KOS Virtual CPU @ 2.00GHz
stepping        : 1
cpu MHz         : 2000.000
cache size      : 512 KB
physical id     : 0
siblings        : 1
core id         : 0
cpu cores       : 1
flags           : fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge
"""
    
    def _get_stat(self) -> str:
        """Generate /proc/stat"""
        # Simplified system statistics
        return """cpu  1000 0 500 95000 100 0 50 0 0 0
cpu0 1000 0 500 95000 100 0 50 0 0 0
intr 10000 100 50 0 0 0 0 0 0 0 0 0 0 0 0 0 0
ctxt 50000
btime 1600000000
processes 1000
procs_running 2
procs_blocked 0
"""
    
    def _get_filesystems(self) -> str:
        """Generate /proc/filesystems"""
        return """nodev   sysfs
nodev   tmpfs
nodev   bdev
nodev   proc
nodev   devpts
        ext4
        vfat
nodev   ramfs
nodev   devfs
"""
    
    def _get_mounts(self) -> str:
        """Generate /proc/mounts"""
        return """rootfs / rootfs rw 0 0
sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
devfs /dev devfs rw,nosuid,relatime 0 0
tmpfs /tmp tmpfs rw,nosuid,nodev,relatime 0 0
"""
    
    def _get_devices(self) -> str:
        """Generate /proc/devices"""
        return """Character devices:
  1 mem
  5 /dev/tty
  5 /dev/console
  7 vcs
 10 misc
 13 input
 29 fb
128 ptm
136 pts
180 usb
189 usb_device
226 drm
250 kaim

Block devices:
  7 loop
  8 sd
  9 md
 11 sr
253 device-mapper
254 mdp
"""
    
    def _get_modules(self) -> str:
        """Generate /proc/modules"""
        return """kaim 16384 0 - Live 0xffffffffc0000000
kvm 1048576 0 - Live 0xffffffffc0100000
"""
    
    def _get_net_dev(self) -> str:
        """Generate /proc/net/dev"""
        return """Inter-|   Receive                                                |  Transmit
 face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed
    lo: 1000000     1000    0    0    0     0          0         0  1000000     1000    0    0    0     0       0          0
  eth0: 5000000     5000    0    0    0     0          0         0  3000000     3000    0    0    0     0       0          0
"""
    
    def _get_net_route(self) -> str:
        """Generate /proc/net/route"""
        return """Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT
eth0\t00000000\t0100007F\t0003\t0\t0\t0\t00000000\t0\t0\t0
eth0\t0000FEA9\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0
"""
    
    def _get_net_tcp(self) -> str:
        """Generate /proc/net/tcp"""
        return """  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:0CEA 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 12345 1 0000000000000000 100 0 0 10 0
"""
    
    def _get_hostname(self) -> str:
        """Get system hostname"""
        return "kos-system\n"
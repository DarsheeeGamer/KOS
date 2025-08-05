"""
SysFS - System Filesystem Implementation
Provides kernel and hardware information through a virtual filesystem
"""

import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from datetime import datetime

from kos.filesystem.base import FileSystem, FileNode, DirectoryNode


class SysFileNode(FileNode):
    """Special file node for sysfs that can be read and written"""
    
    def __init__(self, name: str, read_func=None, write_func=None, initial_value=""):
        super().__init__(name)
        self.read_func = read_func
        self.write_func = write_func
        self._value = initial_value
        self._lock = threading.Lock()
    
    def read(self, size: int = -1, offset: int = 0) -> bytes:
        """Read sysfs file content"""
        with self._lock:
            if self.read_func:
                content = self.read_func()
            else:
                content = self._value
            
            if isinstance(content, str):
                content = content.encode('utf-8')
            
            if offset >= len(content):
                return b''
            
            if size == -1:
                return content[offset:]
            else:
                return content[offset:offset + size]
    
    def write(self, data: bytes) -> int:
        """Write to sysfs file"""
        with self._lock:
            if self.write_func:
                # Pass decoded string to write function
                value = data.decode('utf-8').strip()
                self.write_func(value)
            else:
                # Store the value
                self._value = data.decode('utf-8')
            
            return len(data)
    
    @property
    def size(self) -> int:
        """Get file size"""
        with self._lock:
            if self.read_func:
                content = self.read_func()
            else:
                content = self._value
            
            if isinstance(content, str):
                return len(content.encode('utf-8'))
            return len(content)


class SysFS(FileSystem):
    """System filesystem implementation"""
    
    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._power_state = "on"
        self._cpu_freq = 2000000  # 2GHz in KHz
        self._init_sysfs_tree()
    
    def _init_sysfs_tree(self):
        """Initialize the sysfs directory structure"""
        # /sys/class
        self._create_class_hierarchy()
        
        # /sys/devices
        self._create_devices_hierarchy()
        
        # /sys/kernel
        self._create_kernel_hierarchy()
        
        # /sys/module
        self._create_module_hierarchy()
        
        # /sys/power
        self._create_power_hierarchy()
        
        # /sys/fs
        self._create_fs_hierarchy()
        
        # /sys/block
        self._create_block_hierarchy()
    
    def _create_class_hierarchy(self):
        """Create /sys/class hierarchy"""
        class_dir = DirectoryNode('class')
        self.root.add_child(class_dir)
        
        # /sys/class/net - Network interfaces
        net_dir = DirectoryNode('net')
        class_dir.add_child(net_dir)
        
        # Create loopback interface
        lo_dir = DirectoryNode('lo')
        net_dir.add_child(lo_dir)
        lo_dir.add_child(SysFileNode('address', lambda: '00:00:00:00:00:00\n'))
        lo_dir.add_child(SysFileNode('mtu', lambda: '65536\n', self._set_mtu))
        lo_dir.add_child(SysFileNode('operstate', lambda: 'UP\n'))
        lo_dir.add_child(SysFileNode('carrier', lambda: '1\n'))
        
        # Create eth0 interface
        eth0_dir = DirectoryNode('eth0')
        net_dir.add_child(eth0_dir)
        eth0_dir.add_child(SysFileNode('address', lambda: '52:54:00:12:34:56\n'))
        eth0_dir.add_child(SysFileNode('mtu', lambda: '1500\n', self._set_mtu))
        eth0_dir.add_child(SysFileNode('operstate', lambda: 'UP\n'))
        eth0_dir.add_child(SysFileNode('carrier', lambda: '1\n'))
        
        # /sys/class/tty - TTY devices
        tty_dir = DirectoryNode('tty')
        class_dir.add_child(tty_dir)
        
        # Add console
        console_dir = DirectoryNode('console')
        tty_dir.add_child(console_dir)
        console_dir.add_child(SysFileNode('dev', lambda: '5:1\n'))
        
        # /sys/class/block - Block devices
        block_class_dir = DirectoryNode('block')
        class_dir.add_child(block_class_dir)
        
        # Add loop devices
        for i in range(8):
            loop_dir = DirectoryNode(f'loop{i}')
            block_class_dir.add_child(loop_dir)
            loop_dir.add_child(SysFileNode('dev', lambda i=i: f'7:{i}\n'))
            loop_dir.add_child(SysFileNode('size', lambda: '0\n'))
    
    def _create_devices_hierarchy(self):
        """Create /sys/devices hierarchy"""
        devices_dir = DirectoryNode('devices')
        self.root.add_child(devices_dir)
        
        # /sys/devices/system
        system_dir = DirectoryNode('system')
        devices_dir.add_child(system_dir)
        
        # /sys/devices/system/cpu
        cpu_dir = DirectoryNode('cpu')
        system_dir.add_child(cpu_dir)
        
        # CPU0
        cpu0_dir = DirectoryNode('cpu0')
        cpu_dir.add_child(cpu0_dir)
        
        # CPU frequency scaling
        cpufreq_dir = DirectoryNode('cpufreq')
        cpu0_dir.add_child(cpufreq_dir)
        cpufreq_dir.add_child(SysFileNode('scaling_cur_freq', 
                                         lambda: f'{self._cpu_freq}\n'))
        cpufreq_dir.add_child(SysFileNode('scaling_min_freq', 
                                         lambda: '800000\n'))
        cpufreq_dir.add_child(SysFileNode('scaling_max_freq', 
                                         lambda: '3000000\n'))
        cpufreq_dir.add_child(SysFileNode('scaling_governor', 
                                         lambda: 'performance\n',
                                         self._set_cpu_governor))
        
        # /sys/devices/virtual
        virtual_dir = DirectoryNode('virtual')
        devices_dir.add_child(virtual_dir)
        
        # Virtual terminals
        tty_dir = DirectoryNode('tty')
        virtual_dir.add_child(tty_dir)
        
        # Platform devices
        platform_dir = DirectoryNode('platform')
        devices_dir.add_child(platform_dir)
    
    def _create_kernel_hierarchy(self):
        """Create /sys/kernel hierarchy"""
        kernel_dir = DirectoryNode('kernel')
        self.root.add_child(kernel_dir)
        
        # Kernel parameters
        kernel_dir.add_child(SysFileNode('hostname', 
                                       lambda: 'kos-system\n',
                                       self._set_hostname))
        kernel_dir.add_child(SysFileNode('ostype', lambda: 'KOS\n'))
        kernel_dir.add_child(SysFileNode('osrelease', lambda: '1.0.0\n'))
        kernel_dir.add_child(SysFileNode('version', lambda: '#1 SMP PREEMPT_DYNAMIC\n'))
        
        # /sys/kernel/mm
        mm_dir = DirectoryNode('mm')
        kernel_dir.add_child(mm_dir)
        
        # Transparent huge pages
        thp_dir = DirectoryNode('transparent_hugepage')
        mm_dir.add_child(thp_dir)
        thp_dir.add_child(SysFileNode('enabled', lambda: 'always [madvise] never\n'))
        
        # /sys/kernel/debug (restricted)
        debug_dir = DirectoryNode('debug')
        debug_dir.mode = 0o700  # Root only
        kernel_dir.add_child(debug_dir)
        
        # /sys/kernel/security
        security_dir = DirectoryNode('security')
        kernel_dir.add_child(security_dir)
        security_dir.add_child(SysFileNode('lsm', lambda: 'kaim,capability\n'))
    
    def _create_module_hierarchy(self):
        """Create /sys/module hierarchy"""
        module_dir = DirectoryNode('module')
        self.root.add_child(module_dir)
        
        # KAIM module
        kaim_dir = DirectoryNode('kaim')
        module_dir.add_child(kaim_dir)
        
        # Module parameters
        params_dir = DirectoryNode('parameters')
        kaim_dir.add_child(params_dir)
        params_dir.add_child(SysFileNode('debug', lambda: '0\n', self._set_debug))
        params_dir.add_child(SysFileNode('max_devices', lambda: '256\n'))
        
        # Module info
        kaim_dir.add_child(SysFileNode('refcnt', lambda: '1\n'))
        kaim_dir.add_child(SysFileNode('version', lambda: '1.0.0\n'))
        
        # Kernel module
        kernel_mod_dir = DirectoryNode('kernel')
        module_dir.add_child(kernel_mod_dir)
        
        params_dir = DirectoryNode('parameters')
        kernel_mod_dir.add_child(params_dir)
        params_dir.add_child(SysFileNode('panic', lambda: '0\n'))
    
    def _create_power_hierarchy(self):
        """Create /sys/power hierarchy"""
        power_dir = DirectoryNode('power')
        self.root.add_child(power_dir)
        
        # Power state
        power_dir.add_child(SysFileNode('state', 
                                      lambda: f'{self._power_state}\n',
                                      self._set_power_state))
        
        # Wake lock
        power_dir.add_child(SysFileNode('wake_lock', 
                                      lambda: '',
                                      self._acquire_wake_lock))
        power_dir.add_child(SysFileNode('wake_unlock',
                                      lambda: '',
                                      self._release_wake_lock))
        
        # PM stats
        power_dir.add_child(SysFileNode('pm_freeze_timeout', lambda: '5000\n'))
    
    def _create_fs_hierarchy(self):
        """Create /sys/fs hierarchy"""
        fs_dir = DirectoryNode('fs')
        self.root.add_child(fs_dir)
        
        # Cgroup
        cgroup_dir = DirectoryNode('cgroup')
        fs_dir.add_child(cgroup_dir)
        cgroup_dir.add_child(SysFileNode('available_controllers', 
                                       lambda: 'cpu memory pids\n'))
        
        # Ext4 info
        ext4_dir = DirectoryNode('ext4')
        fs_dir.add_child(ext4_dir)
        
        # FUSE
        fuse_dir = DirectoryNode('fuse')
        fs_dir.add_child(fuse_dir)
        fuse_dir.add_child(DirectoryNode('connections'))
    
    def _create_block_hierarchy(self):
        """Create /sys/block hierarchy"""
        block_dir = DirectoryNode('block')
        self.root.add_child(block_dir)
        
        # Loop devices
        for i in range(8):
            loop_dir = DirectoryNode(f'loop{i}')
            block_dir.add_child(loop_dir)
            
            # Device info
            loop_dir.add_child(SysFileNode('dev', lambda i=i: f'7:{i}\n'))
            loop_dir.add_child(SysFileNode('size', lambda: '0\n'))
            loop_dir.add_child(SysFileNode('removable', lambda: '0\n'))
            loop_dir.add_child(SysFileNode('ro', lambda: '0\n'))
            
            # Queue directory
            queue_dir = DirectoryNode('queue')
            loop_dir.add_child(queue_dir)
            queue_dir.add_child(SysFileNode('rotational', lambda: '0\n'))
            queue_dir.add_child(SysFileNode('scheduler', 
                                          lambda: '[none] mq-deadline kyber\n'))
    
    # Handler functions
    def _set_mtu(self, value: str):
        """Set network interface MTU"""
        try:
            mtu = int(value)
            if 68 <= mtu <= 65536:
                # Would actually set MTU
                pass
        except ValueError:
            pass
    
    def _set_cpu_governor(self, value: str):
        """Set CPU frequency governor"""
        governors = ['performance', 'powersave', 'ondemand', 'conservative']
        if value in governors:
            # Would actually set governor
            pass
    
    def _set_hostname(self, value: str):
        """Set system hostname"""
        # Would actually set hostname
        pass
    
    def _set_debug(self, value: str):
        """Set debug level"""
        try:
            debug_level = int(value)
            # Would set debug level
        except ValueError:
            pass
    
    def _set_power_state(self, value: str):
        """Set system power state"""
        valid_states = ['on', 'mem', 'disk', 'standby']
        if value in valid_states:
            self._power_state = value
    
    def _acquire_wake_lock(self, value: str):
        """Acquire a wake lock"""
        # Would actually acquire wake lock
        pass
    
    def _release_wake_lock(self, value: str):
        """Release a wake lock"""
        # Would actually release wake lock
        pass
    
    def create_device_node(self, path: str, device_class: str, 
                          major: int, minor: int):
        """Create a new device node in sysfs"""
        with self._lock:
            # Navigate to appropriate directory
            parts = path.strip('/').split('/')
            parent = self.root
            
            for part in parts[:-1]:
                child = parent.get_child(part)
                if not child:
                    child = DirectoryNode(part)
                    parent.add_child(child)
                parent = child
            
            # Create device directory
            device_name = parts[-1]
            device_dir = DirectoryNode(device_name)
            parent.add_child(device_dir)
            
            # Add standard device files
            device_dir.add_child(SysFileNode('dev', lambda: f'{major}:{minor}\n'))
            device_dir.add_child(SysFileNode('uevent', lambda: ''))
            
            # Create symlink in class directory
            if device_class:
                class_path = f'class/{device_class}'
                class_node = self._navigate_to_path(class_path)
                if class_node and isinstance(class_node, DirectoryNode):
                    # Would create symlink
                    pass
    
    def _navigate_to_path(self, path: str) -> Optional[Union[FileNode, DirectoryNode]]:
        """Navigate to a path in the filesystem"""
        parts = path.strip('/').split('/')
        current = self.root
        
        for part in parts:
            if isinstance(current, DirectoryNode):
                current = current.get_child(part)
                if not current:
                    return None
            else:
                return None
        
        return current
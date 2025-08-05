"""
KOS Bootloader - Simulates the boot process of a real OS
"""

import time
import logging
from enum import Enum
from typing import Dict, Any, Optional

class BootStage(Enum):
    """Boot stages similar to real Linux boot process"""
    BIOS = "BIOS/UEFI"
    BOOTLOADER = "Bootloader"
    KERNEL_LOAD = "Kernel Loading"
    KERNEL_INIT = "Kernel Initialization"
    INITRAMFS = "InitRAMFS"
    ROOT_MOUNT = "Root Filesystem Mount"
    INIT_SYSTEM = "Init System"
    COMPLETE = "Boot Complete"

class KOSBootloader:
    """
    Simulates a bootloader like GRUB
    Handles the initial boot process and kernel loading
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.boot_time = 0
        self.current_stage = BootStage.BIOS
        self.boot_log = []
        self.kernel = None
        self.initramfs = None
        
        # Boot parameters (like kernel command line)
        self.boot_params = {
            'root': '/dev/vda1',
            'quiet': False,
            'splash': False,
            'init': '/sbin/init',
            'runlevel': 5,
            'kos.debug': False
        }
        
        # Hardware info (simulated)
        self.hardware_info = {
            'cpu': {
                'model': 'KOS Virtual CPU',
                'cores': 4,
                'frequency': 2400  # MHz
            },
            'memory': {
                'total': 4 * 1024 * 1024 * 1024,  # 4GB
                'available': 4 * 1024 * 1024 * 1024
            },
            'storage': [
                {
                    'device': '/dev/vda',
                    'size': 20 * 1024 * 1024 * 1024,  # 20GB
                    'type': 'virtio'
                }
            ]
        }
        
    def _default_config(self) -> Dict[str, Any]:
        """Default bootloader configuration"""
        return {
            'timeout': 5,
            'default_entry': 0,
            'entries': [
                {
                    'title': 'KOS Linux',
                    'kernel': '/boot/vmlinuz-kos',
                    'initrd': '/boot/initrd.img-kos',
                    'params': 'root=/dev/vda1 ro quiet'
                },
                {
                    'title': 'KOS Linux (Recovery Mode)',
                    'kernel': '/boot/vmlinuz-kos',
                    'initrd': '/boot/initrd.img-kos',
                    'params': 'root=/dev/vda1 ro single'
                }
            ]
        }
        
    def boot(self, entry_index: Optional[int] = None) -> 'KOSKernel':
        """
        Main boot process
        Returns the loaded kernel instance
        """
        start_time = time.time()
        
        # Stage 1: BIOS/UEFI
        self._boot_stage(BootStage.BIOS)
        self._log("KOS Virtual BIOS v1.0")
        self._log("Copyright (c) 2024 KOS Project")
        self._log("")
        self._hardware_detection()
        time.sleep(0.1)  # Simulate BIOS time
        
        # Stage 2: Bootloader
        self._boot_stage(BootStage.BOOTLOADER)
        self._log("KOS Bootloader v1.0")
        self._log("")
        
        # Select boot entry
        if entry_index is None:
            entry_index = self.config['default_entry']
        
        if self.config['timeout'] > 0 and not self.boot_params.get('kos.fastboot'):
            self._show_boot_menu()
            # In real implementation, would wait for user input
            
        boot_entry = self.config['entries'][entry_index]
        self._log(f"Booting '{boot_entry['title']}'...")
        
        # Parse kernel parameters
        self._parse_kernel_params(boot_entry['params'])
        
        # Stage 3: Load kernel
        self._boot_stage(BootStage.KERNEL_LOAD)
        self._log(f"Loading kernel from {boot_entry['kernel']}...")
        self.kernel = self._load_kernel(boot_entry['kernel'])
        
        # Load initramfs
        self._log(f"Loading initial ramdisk from {boot_entry['initrd']}...")
        self.initramfs = self._load_initramfs(boot_entry['initrd'])
        
        # Stage 4: Transfer control to kernel
        self._boot_stage(BootStage.KERNEL_INIT)
        self._log("Starting kernel...")
        self._log("")
        
        # Calculate boot time
        self.boot_time = time.time() - start_time
        
        # Pass control to kernel
        self.kernel.boot(self.boot_params, self.hardware_info, self.initramfs)
        
        return self.kernel
        
    def _hardware_detection(self):
        """Simulate hardware detection"""
        self._log("Detecting hardware...")
        self._log(f"CPU: {self.hardware_info['cpu']['model']} "
                 f"({self.hardware_info['cpu']['cores']} cores @ "
                 f"{self.hardware_info['cpu']['frequency']}MHz)")
        self._log(f"Memory: {self.hardware_info['memory']['total'] // (1024*1024)}MB")
        
        for disk in self.hardware_info['storage']:
            self._log(f"Disk: {disk['device']} ({disk['size'] // (1024*1024*1024)}GB {disk['type']})")
            
    def _show_boot_menu(self):
        """Display boot menu"""
        self._log("=" * 60)
        self._log("KOS Boot Menu")
        self._log("=" * 60)
        
        for i, entry in enumerate(self.config['entries']):
            prefix = ">" if i == self.config['default_entry'] else " "
            self._log(f"{prefix} {i}: {entry['title']}")
            
        self._log("")
        self._log(f"Automatic boot in {self.config['timeout']} seconds...")
        self._log("Press any key to interrupt")
        
    def _parse_kernel_params(self, params: str):
        """Parse kernel command line parameters"""
        for param in params.split():
            if '=' in param:
                key, value = param.split('=', 1)
                # Convert boolean strings
                if value.lower() in ('true', '1', 'yes'):
                    value = True
                elif value.lower() in ('false', '0', 'no'):
                    value = False
                self.boot_params[key] = value
            else:
                # Boolean flag
                self.boot_params[param] = True
                
    def _load_kernel(self, kernel_path: str) -> 'KOSKernel':
        """Load the kernel (simulate)"""
        from .kernel import KOSKernel
        
        # In a real bootloader, this would:
        # 1. Read kernel from disk
        # 2. Decompress if needed
        # 3. Load into memory
        # 4. Set up initial page tables
        # 5. Switch to protected/long mode
        
        # For VOS, we just instantiate
        kernel = KOSKernel()
        kernel.image_path = kernel_path
        
        return kernel
        
    def _load_initramfs(self, initrd_path: str) -> 'KOSInitRAMFS':
        """Load initial RAM filesystem"""
        from .initramfs import KOSInitRAMFS
        
        # In real bootloader, this would load the compressed filesystem
        # For VOS, we create an instance
        initramfs = KOSInitRAMFS()
        initramfs.image_path = initrd_path
        
        return initramfs
        
    def _boot_stage(self, stage: BootStage):
        """Update current boot stage"""
        self.current_stage = stage
        if stage != BootStage.BIOS:  # BIOS stage is silent
            self._log(f"\n[{stage.value}]")
            
    def _log(self, message: str):
        """Log boot message"""
        timestamp = time.time()
        self.boot_log.append((timestamp, message))
        
        # In quiet mode, only show errors
        if not self.boot_params.get('quiet', False) or 'error' in message.lower():
            print(message)
            
    def get_boot_log(self) -> list:
        """Get complete boot log"""
        return self.boot_log
        
    def set_boot_param(self, key: str, value: Any):
        """Set a boot parameter"""
        self.boot_params[key] = value
        
    def add_boot_entry(self, entry: Dict[str, str]):
        """Add a new boot entry"""
        self.config['entries'].append(entry)
        
    def remove_boot_entry(self, index: int):
        """Remove a boot entry"""
        if 0 <= index < len(self.config['entries']):
            self.config['entries'].pop(index)
            
    def set_default_entry(self, index: int):
        """Set the default boot entry"""
        if 0 <= index < len(self.config['entries']):
            self.config['default_entry'] = index
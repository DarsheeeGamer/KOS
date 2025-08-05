"""
KOS Kernel - Core of the Virtual Operating System
"""

import time
import threading
import logging
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

class KernelState(Enum):
    """Kernel states during boot and operation"""
    UNINITIALIZED = "Uninitialized"
    BOOTING = "Booting"
    INITIALIZING = "Initializing"
    RUNNING = "Running"
    PANIC = "Panic"
    HALTED = "Halted"

@dataclass
class KernelConfig:
    """Kernel configuration parameters"""
    hz: int = 1000  # Timer frequency
    max_processes: int = 32768
    max_open_files: int = 1048576
    page_size: int = 4096
    kernel_stack_size: int = 8192
    preemptive: bool = True
    smp_enabled: bool = True
    max_cpus: int = 256

class KOSKernel:
    """
    The KOS Kernel - manages all core OS functionality
    """
    
    VERSION = "1.0.0"
    RELEASE = "Kaede"
    
    def __init__(self):
        self.state = KernelState.UNINITIALIZED
        self.config = KernelConfig()
        self.boot_params = {}
        self.hardware_info = {}
        self.start_time = None
        self.panic_message = None
        
        # Core subsystems (will be initialized during boot)
        self.memory_manager = None
        self.process_manager = None
        self.scheduler = None
        self.vfs = None
        self.device_manager = None
        self.network_stack = None
        self.security_manager = None
        
        # Kernel threads
        self.kernel_threads = {}
        self.timer_thread = None
        
        # System information
        self.system_info = {
            'kernel_version': f"{self.VERSION}-{self.RELEASE}",
            'architecture': 'x86_64',  # Simulated
            'hostname': 'localhost',
            'domainname': 'localdomain'
        }
        
        # Kernel log buffer
        self.log_buffer = []
        self.log_level = logging.INFO
        
    def boot(self, boot_params: Dict[str, Any], hardware_info: Dict[str, Any], 
             initramfs: Optional['KOSInitRAMFS'] = None):
        """
        Main kernel boot sequence
        """
        self.state = KernelState.BOOTING
        self.boot_params = boot_params
        self.hardware_info = hardware_info
        self.start_time = time.time()
        
        try:
            # Early initialization
            self._printk("Linux version %s (%s@%s) %s" % (
                self.system_info['kernel_version'],
                "kos",
                "buildhost",
                time.strftime("%a %b %d %H:%M:%S UTC %Y")
            ))
            
            self._printk("Command line: %s" % self._format_cmdline())
            
            # Initialize core subsystems in order
            self._init_memory_management()
            self._init_cpu_management()
            self._init_interrupt_handling()
            self._init_time_keeping()
            self._init_process_management()
            self._init_scheduler()
            self._init_vfs()
            self._init_device_drivers()
            self._init_network_stack()
            self._init_security()
            
            # Mount initial filesystems
            self._mount_initial_filesystems(initramfs)
            
            # Start kernel threads
            self._start_kernel_threads()
            
            # Kernel is ready
            self.state = KernelState.RUNNING
            self._printk("KOS kernel initialized successfully")
            
            # Calculate and display boot time
            boot_time = time.time() - self.start_time
            self._printk(f"Boot completed in {boot_time:.3f} seconds")
            
            # Start init process
            self._start_init_process()
            
        except Exception as e:
            self.panic(f"Kernel boot failed: {str(e)}")
            
    def _init_memory_management(self):
        """Initialize memory management subsystem"""
        self._printk("Initializing memory management...")
        
        from ..memory.manager import KOSMemoryManager
        
        total_memory = self.hardware_info['memory']['total']
        self.memory_manager = KOSMemoryManager(total_memory)
        
        # Reserve kernel memory
        kernel_size = 16 * 1024 * 1024  # 16MB for kernel
        self.memory_manager.reserve_kernel_memory(0, kernel_size)
        
        self._printk(f"Memory: {total_memory // (1024*1024)}MB total")
        self._printk(f"Memory: {self.memory_manager.get_free_memory() // (1024*1024)}MB available")
        
    def _init_cpu_management(self):
        """Initialize CPU management"""
        self._printk("Initializing CPU management...")
        
        num_cpus = self.hardware_info['cpu']['cores']
        if not self.config.smp_enabled:
            num_cpus = 1
            
        self._printk(f"Bringing up {num_cpus} CPUs...")
        
        # In real kernel, would initialize:
        # - Local APIC
        # - IOAPIC
        # - CPU hotplug
        # - Per-CPU data structures
        
        for cpu in range(num_cpus):
            self._printk(f"CPU{cpu}: {self.hardware_info['cpu']['model']} "
                        f"({self.hardware_info['cpu']['frequency']}MHz)")
            
    def _init_interrupt_handling(self):
        """Initialize interrupt handling"""
        self._printk("Setting up interrupt handlers...")
        
        # In real kernel would set up:
        # - IDT (Interrupt Descriptor Table)
        # - IRQ handlers
        # - Exception handlers
        # - System call interface
        
    def _init_time_keeping(self):
        """Initialize time keeping"""
        self._printk("Initializing timekeeping...")
        
        # Start timer thread for periodic tasks
        self.timer_thread = threading.Thread(
            target=self._timer_handler,
            name="kos-timer",
            daemon=True
        )
        self.timer_thread.start()
        
    def _init_process_management(self):
        """Initialize process management"""
        self._printk("Initializing process management...")
        
        from ..process.manager import KOSProcessManager
        
        self.process_manager = KOSProcessManager(self)
        
        # Create kernel process (PID 0)
        kernel_proc = self.process_manager.create_kernel_process()
        
        self._printk(f"Process management initialized (max processes: {self.config.max_processes})")
        
    def _init_scheduler(self):
        """Initialize the scheduler"""
        self._printk("Initializing scheduler...")
        
        from ..scheduler.cfs import KOSScheduler
        
        self.scheduler = KOSScheduler(self)
        self.scheduler.start()
        
        self._printk("CFS scheduler initialized")
        
    def _init_vfs(self):
        """Initialize Virtual Filesystem"""
        self._printk("Initializing VFS...")
        
        from ..filesystem.vfs import KOSVirtualFilesystem
        
        self.vfs = KOSVirtualFilesystem(self)
        
        # Register filesystem types
        self._printk("Registering filesystem types...")
        
        from ..filesystem.ramfs import RamFS
        from ..filesystem.procfs import ProcFS
        from ..filesystem.sysfs import SysFS
        from ..filesystem.devfs import DevFS
        
        self.vfs.register_filesystem_type('ramfs', RamFS)
        self.vfs.register_filesystem_type('procfs', ProcFS)
        self.vfs.register_filesystem_type('sysfs', SysFS)
        self.vfs.register_filesystem_type('devfs', DevFS)
        
        self._printk("VFS initialized")
        
    def _init_device_drivers(self):
        """Initialize device drivers"""
        self._printk("Initializing device drivers...")
        
        from ..devices.manager import KOSDeviceManager
        
        self.device_manager = KOSDeviceManager(self)
        
        # Register core device drivers
        self._printk("Registering core devices...")
        
        # Console device
        from ..devices.console import ConsoleDevice
        self.device_manager.register_device(ConsoleDevice())
        
        # Null device
        from ..devices.null import NullDevice
        self.device_manager.register_device(NullDevice())
        
        # Random devices
        from ..devices.random import RandomDevice, URandomDevice
        self.device_manager.register_device(RandomDevice())
        self.device_manager.register_device(URandomDevice())
        
        self._printk("Device drivers initialized")
        
    def _init_network_stack(self):
        """Initialize networking stack"""
        self._printk("Initializing networking...")
        
        from ..network.stack import KOSNetworkStack
        
        self.network_stack = KOSNetworkStack(self)
        
        # Start network stack
        self.network_stack.start()
        
        # Create loopback interface
        lo_interface = self.network_stack.create_interface('lo', '127.0.0.1')
        self.network_stack.interface_up('lo')
        
        self._printk("Network stack initialized")
        
    def _init_security(self):
        """Initialize security framework"""
        self._printk("Initializing security framework...")
        
        from ..security.manager import KOSSecurityManager
        
        self.security_manager = KOSSecurityManager(self)
        
        # Load security policies
        if self.boot_params.get('selinux', True):
            self._printk("SELinux: Initializing in enforcing mode")
            # Would load SELinux policies
            
        self._printk("Security framework initialized")
        
    def _mount_initial_filesystems(self, initramfs):
        """Mount initial filesystems"""
        self._printk("Mounting initial filesystems...")
        
        # Mount root filesystem (ramfs for now)
        self.vfs.mount('ramfs', '/', {})
        self._printk("Mounted root filesystem (ramfs)")
        
        # Mount proc
        self.vfs.mkdir('/proc', 0o555)
        self.vfs.mount('procfs', '/proc', {})
        self._printk("Mounted /proc (procfs)")
        
        # Mount sys
        self.vfs.mkdir('/sys', 0o555)
        self.vfs.mount('sysfs', '/sys', {})
        self._printk("Mounted /sys (sysfs)")
        
        # Mount dev
        self.vfs.mkdir('/dev', 0o755)
        self.vfs.mount('devfs', '/dev', {})
        self._printk("Mounted /dev (devfs)")
        
        # Create essential directories
        for path in ['/bin', '/sbin', '/lib', '/usr', '/etc', '/tmp', '/var', '/home', '/root']:
            self.vfs.mkdir(path, 0o755)
            
        # Extract initramfs if provided
        if initramfs:
            self._printk("Extracting initial ramdisk...")
            initramfs.extract_to(self.vfs, '/')
            
    def _start_kernel_threads(self):
        """Start essential kernel threads"""
        self._printk("Starting kernel threads...")
        
        # kworker threads
        for i in range(2):  # Start 2 kworker threads
            thread = threading.Thread(
                target=self._kworker_thread,
                args=(i,),
                name=f"kworker/{i}",
                daemon=True
            )
            thread.start()
            self.kernel_threads[f"kworker/{i}"] = thread
            
        # ksoftirqd thread
        thread = threading.Thread(
            target=self._ksoftirqd_thread,
            name="ksoftirqd/0",
            daemon=True
        )
        thread.start()
        self.kernel_threads["ksoftirqd/0"] = thread
        
    def _start_init_process(self):
        """Start the init process (PID 1)"""
        init_path = self.boot_params.get('init', '/sbin/init')
        self._printk(f"Starting init process: {init_path}")
        
        # Create init process
        init_proc = self.process_manager.create_process(
            name='init',
            executable=init_path,
            args=[init_path],
            env={'PATH': '/bin:/sbin:/usr/bin:/usr/sbin'},
            uid=0,
            gid=0
        )
        
        if init_proc:
            self._printk(f"Init process started (PID {init_proc.pid})")
        else:
            self.panic("Failed to start init process!")
            
    def _timer_handler(self):
        """Kernel timer handler thread"""
        while self.state == KernelState.RUNNING:
            # Handle periodic tasks
            time.sleep(1.0 / self.config.hz)
            
            # Update system time
            # Handle timer interrupts
            # Check for scheduled tasks
            
    def _kworker_thread(self, worker_id: int):
        """Kernel worker thread for async tasks"""
        while self.state == KernelState.RUNNING:
            # Process work queue items
            time.sleep(0.1)
            
    def _ksoftirqd_thread(self):
        """Kernel soft IRQ daemon"""
        while self.state == KernelState.RUNNING:
            # Handle soft interrupts
            time.sleep(0.01)
            
    def _format_cmdline(self) -> str:
        """Format kernel command line"""
        parts = []
        for key, value in self.boot_params.items():
            if value is True:
                parts.append(key)
            elif value is False:
                continue
            else:
                parts.append(f"{key}={value}")
        return ' '.join(parts)
        
    def _printk(self, message: str, level: int = logging.INFO):
        """Kernel print function"""
        timestamp = time.time() - (self.start_time or 0)
        log_entry = f"[{timestamp:8.3f}] {message}"
        
        self.log_buffer.append((timestamp, level, message))
        
        if level >= self.log_level:
            print(log_entry)
            
    def panic(self, message: str):
        """Kernel panic - unrecoverable error"""
        self.state = KernelState.PANIC
        self.panic_message = message
        
        print("\n" + "="*60)
        print("KERNEL PANIC - Not syncing: " + message)
        print("="*60)
        
        # Print stack trace
        import traceback
        traceback.print_exc()
        
        # In real kernel would:
        # - Disable interrupts
        # - Stop all CPUs
        # - Sync filesystems
        # - Reboot or halt
        
        # For VOS, we just halt
        self.halt()
        
    def halt(self):
        """Halt the kernel"""
        self.state = KernelState.HALTED
        self._printk("System halted.")
        
    def reboot(self):
        """Reboot the system"""
        self._printk("Rebooting system...")
        
        # Sync filesystems
        if self.vfs:
            self.vfs.sync()
            
        # Stop all processes
        if self.process_manager:
            self.process_manager.kill_all()
            
        # Reset to allow new boot
        self.state = KernelState.UNINITIALIZED
        
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0
        
    def get_load_average(self) -> tuple:
        """Get system load average (1, 5, 15 minutes)"""
        if self.scheduler:
            return self.scheduler.get_load_average()
        return (0.0, 0.0, 0.0)
        
    def get_memory_info(self) -> Dict[str, int]:
        """Get memory information"""
        if self.memory_manager:
            return {
                'total': self.memory_manager.total_memory,
                'free': self.memory_manager.get_free_memory(),
                'used': self.memory_manager.get_used_memory(),
                'cached': self.memory_manager.get_cached_memory(),
                'buffers': self.memory_manager.get_buffer_memory()
            }
        return {}
        
    def get_process_count(self) -> Dict[str, int]:
        """Get process counts"""
        if self.process_manager:
            return self.process_manager.get_process_stats()
        return {'total': 0, 'running': 0, 'sleeping': 0}
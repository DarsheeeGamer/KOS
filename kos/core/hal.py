"""
KOS Hardware Abstraction Layer (HAL)

This module provides a uniform interface for the kernel to interact with different types of hardware,
abstracting away the specific details of hardware interactions.
"""

import os
import sys
import time
import logging
import threading
import importlib
import platform
import psutil
from typing import Dict, List, Any, Optional, Tuple, Set, Callable

# Set up logging
logger = logging.getLogger('KOS.core.hal')

# HAL state
_hal_state = {
    'initialized': False,
    'devices': {},
    'drivers': {},
    'hardware_info': {},
    'device_callbacks': {}
}

# Locks
_hal_lock = threading.RLock()
_device_lock = threading.RLock()


class DeviceType:
    """Device types"""
    CPU = 'cpu'
    MEMORY = 'memory'
    STORAGE = 'storage'
    NETWORK = 'network'
    INPUT = 'input'
    OUTPUT = 'output'
    GPU = 'gpu'
    AUDIO = 'audio'
    TIMER = 'timer'
    GENERIC = 'generic'


class DeviceInfo:
    """Information about a device"""
    
    def __init__(self, device_id, device_type, name, description=None, properties=None):
        """
        Initialize device info
        
        Args:
            device_id: Device ID
            device_type: Device type
            name: Device name
            description: Device description
            properties: Device properties
        """
        self.device_id = device_id
        self.device_type = device_type
        self.name = name
        self.description = description or ''
        self.properties = properties or {}
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'device_id': self.device_id,
            'device_type': self.device_type,
            'name': self.name,
            'description': self.description,
            'properties': self.properties
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create from dictionary"""
        return cls(
            device_id=data['device_id'],
            device_type=data['device_type'],
            name=data['name'],
            description=data.get('description', ''),
            properties=data.get('properties', {})
        )
    
    def __repr__(self):
        return f"DeviceInfo(id={self.device_id}, type={self.device_type}, name={self.name})"


class DeviceDriver:
    """Base class for device drivers"""
    
    def __init__(self, device_info):
        """
        Initialize device driver
        
        Args:
            device_info: Device info
        """
        self.device_info = device_info
        self.initialized = False
    
    def initialize(self):
        """Initialize the device"""
        self.initialized = True
        return True
    
    def shutdown(self):
        """Shutdown the device"""
        self.initialized = False
        return True
    
    def read(self, offset=0, size=None):
        """
        Read from the device
        
        Args:
            offset: Offset to read from
            size: Number of bytes to read
        
        Returns:
            Data read
        """
        raise NotImplementedError("Read operation not supported by this device")
    
    def write(self, data, offset=0):
        """
        Write to the device
        
        Args:
            data: Data to write
            offset: Offset to write to
        
        Returns:
            Number of bytes written
        """
        raise NotImplementedError("Write operation not supported by this device")
    
    def ioctl(self, command, arg=0):
        """
        Perform an I/O control operation
        
        Args:
            command: Command to perform
            arg: Command argument
        
        Returns:
            Command result
        """
        raise NotImplementedError("IOCTL operation not supported by this device")
    
    def get_status(self):
        """
        Get device status
        
        Returns:
            Device status
        """
        return {
            'initialized': self.initialized,
            'device_id': self.device_info.device_id,
            'device_type': self.device_info.device_type,
            'name': self.device_info.name
        }


class CPUDriver(DeviceDriver):
    """CPU device driver"""
    
    def __init__(self, device_info):
        """
        Initialize CPU driver
        
        Args:
            device_info: Device info
        """
        super().__init__(device_info)
        self._last_cpu_times = None
    
    def get_status(self):
        """
        Get CPU status
        
        Returns:
            CPU status
        """
        status = super().get_status()
        
        # Add CPU-specific status
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_times = psutil.cpu_times()
            cpu_stats = psutil.cpu_stats()
            cpu_freq = psutil.cpu_freq()
            
            status.update({
                'percent': cpu_percent,
                'times': {
                    'user': cpu_times.user,
                    'system': cpu_times.system,
                    'idle': cpu_times.idle
                },
                'stats': {
                    'ctx_switches': cpu_stats.ctx_switches,
                    'interrupts': cpu_stats.interrupts,
                    'soft_interrupts': cpu_stats.soft_interrupts,
                    'syscalls': cpu_stats.syscalls
                },
                'freq': {
                    'current': cpu_freq.current if cpu_freq else 0,
                    'min': cpu_freq.min if cpu_freq and hasattr(cpu_freq, 'min') else 0,
                    'max': cpu_freq.max if cpu_freq and hasattr(cpu_freq, 'max') else 0
                }
            })
        except Exception as e:
            logger.warning(f"Error getting CPU status: {e}")
        
        return status


class MemoryDriver(DeviceDriver):
    """Memory device driver"""
    
    def __init__(self, device_info):
        """
        Initialize memory driver
        
        Args:
            device_info: Device info
        """
        super().__init__(device_info)
    
    def get_status(self):
        """
        Get memory status
        
        Returns:
            Memory status
        """
        status = super().get_status()
        
        # Add memory-specific status
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            status.update({
                'virtual': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'free': memory.free,
                    'percent': memory.percent
                },
                'swap': {
                    'total': swap.total,
                    'used': swap.used,
                    'free': swap.free,
                    'percent': swap.percent
                }
            })
        except Exception as e:
            logger.warning(f"Error getting memory status: {e}")
        
        return status


class StorageDriver(DeviceDriver):
    """Storage device driver"""
    
    def __init__(self, device_info):
        """
        Initialize storage driver
        
        Args:
            device_info: Device info
        """
        super().__init__(device_info)
        self._path = device_info.properties.get('path')
    
    def get_status(self):
        """
        Get storage status
        
        Returns:
            Storage status
        """
        status = super().get_status()
        
        # Add storage-specific status
        try:
            if self._path and os.path.exists(self._path):
                disk_usage = psutil.disk_usage(self._path)
                
                status.update({
                    'path': self._path,
                    'usage': {
                        'total': disk_usage.total,
                        'used': disk_usage.used,
                        'free': disk_usage.free,
                        'percent': disk_usage.percent
                    }
                })
                
                # Get disk I/O statistics if available
                try:
                    disk_io = psutil.disk_io_counters(perdisk=True)
                    disk_name = os.path.basename(self._path)
                    
                    if disk_name in disk_io:
                        io_stats = disk_io[disk_name]
                        status['io'] = {
                            'read_count': io_stats.read_count,
                            'write_count': io_stats.write_count,
                            'read_bytes': io_stats.read_bytes,
                            'write_bytes': io_stats.write_bytes,
                            'read_time': io_stats.read_time,
                            'write_time': io_stats.write_time
                        }
                except Exception as e:
                    logger.debug(f"Error getting disk I/O stats: {e}")
        except Exception as e:
            logger.warning(f"Error getting storage status: {e}")
        
        return status
    
    def read(self, offset=0, size=None):
        """
        Read from the storage device
        
        Args:
            offset: Offset to read from
            size: Number of bytes to read
        
        Returns:
            Data read
        """
        if not self._path:
            raise ValueError("Storage path not defined")
        
        if not os.path.exists(self._path):
            raise FileNotFoundError(f"Storage path not found: {self._path}")
        
        if os.path.isdir(self._path):
            raise IsADirectoryError(f"Cannot read from directory: {self._path}")
        
        with open(self._path, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    
    def write(self, data, offset=0):
        """
        Write to the storage device
        
        Args:
            data: Data to write
            offset: Offset to write to
        
        Returns:
            Number of bytes written
        """
        if not self._path:
            raise ValueError("Storage path not defined")
        
        if os.path.isdir(self._path):
            raise IsADirectoryError(f"Cannot write to directory: {self._path}")
        
        # Open in read+write mode to allow seeking without truncating
        with open(self._path, 'r+b') as f:
            f.seek(offset)
            return f.write(data)


class NetworkDriver(DeviceDriver):
    """Network device driver"""
    
    def __init__(self, device_info):
        """
        Initialize network driver
        
        Args:
            device_info: Device info
        """
        super().__init__(device_info)
        self._interface = device_info.properties.get('interface')
    
    def get_status(self):
        """
        Get network status
        
        Returns:
            Network status
        """
        status = super().get_status()
        
        # Add network-specific status
        try:
            if self._interface:
                net_io = psutil.net_io_counters(pernic=True)
                net_addrs = psutil.net_if_addrs()
                net_stats = psutil.net_if_stats()
                
                if self._interface in net_io:
                    io_stats = net_io[self._interface]
                    status['io'] = {
                        'bytes_sent': io_stats.bytes_sent,
                        'bytes_recv': io_stats.bytes_recv,
                        'packets_sent': io_stats.packets_sent,
                        'packets_recv': io_stats.packets_recv,
                        'errin': io_stats.errin,
                        'errout': io_stats.errout,
                        'dropin': io_stats.dropin,
                        'dropout': io_stats.dropout
                    }
                
                if self._interface in net_addrs:
                    addrs = net_addrs[self._interface]
                    status['addresses'] = []
                    
                    for addr in addrs:
                        status['addresses'].append({
                            'family': str(addr.family),
                            'address': addr.address,
                            'netmask': addr.netmask,
                            'broadcast': addr.broadcast
                        })
                
                if self._interface in net_stats:
                    stats = net_stats[self._interface]
                    status['stats'] = {
                        'isup': stats.isup,
                        'duplex': stats.duplex,
                        'speed': stats.speed,
                        'mtu': stats.mtu
                    }
        except Exception as e:
            logger.warning(f"Error getting network status: {e}")
        
        return status
    
    def read(self, offset=0, size=None):
        """
        Read from the network device (receive data)
        
        Args:
            offset: Ignored for network devices
            size: Maximum number of bytes to read
        
        Returns:
            Data received
        """
        # This is a placeholder - a real implementation would involve socket operations
        raise NotImplementedError("Network read not implemented")
    
    def write(self, data, offset=0):
        """
        Write to the network device (send data)
        
        Args:
            data: Data to send
            offset: Ignored for network devices
        
        Returns:
            Number of bytes sent
        """
        # This is a placeholder - a real implementation would involve socket operations
        raise NotImplementedError("Network write not implemented")


class TimerDriver(DeviceDriver):
    """Timer device driver"""
    
    def __init__(self, device_info):
        """
        Initialize timer driver
        
        Args:
            device_info: Device info
        """
        super().__init__(device_info)
        self._timers = {}
        self._timer_id_counter = 0
        self._timer_lock = threading.RLock()
    
    def ioctl(self, command, arg=0):
        """
        Perform an I/O control operation
        
        Args:
            command: Command to perform
            arg: Command argument
        
        Returns:
            Command result
        """
        if command == 'create_timer':
            # arg should be a dict with interval and callback
            return self.create_timer(arg.get('interval', 1.0), arg.get('callback'))
        elif command == 'cancel_timer':
            # arg should be a timer ID
            return self.cancel_timer(arg)
        elif command == 'get_timers':
            return self.get_timers()
        else:
            raise ValueError(f"Unknown timer command: {command}")
    
    def create_timer(self, interval, callback=None):
        """
        Create a timer
        
        Args:
            interval: Timer interval in seconds
            callback: Callback function
        
        Returns:
            Timer ID
        """
        with self._timer_lock:
            timer_id = self._timer_id_counter
            self._timer_id_counter += 1
            
            timer = threading.Timer(interval, self._timer_callback, args=[timer_id, callback])
            timer.daemon = True
            
            self._timers[timer_id] = {
                'timer': timer,
                'interval': interval,
                'callback': callback,
                'created': time.time(),
                'fires_at': time.time() + interval,
                'active': True
            }
            
            timer.start()
            
            return timer_id
    
    def cancel_timer(self, timer_id):
        """
        Cancel a timer
        
        Args:
            timer_id: Timer ID
        
        Returns:
            Success status
        """
        with self._timer_lock:
            if timer_id not in self._timers:
                return False
            
            timer_info = self._timers[timer_id]
            timer = timer_info['timer']
            
            if timer_info['active']:
                timer.cancel()
                timer_info['active'] = False
            
            return True
    
    def get_timers(self):
        """
        Get all timers
        
        Returns:
            Dictionary of timer information
        """
        with self._timer_lock:
            return {timer_id: {
                'interval': info['interval'],
                'created': info['created'],
                'fires_at': info['fires_at'],
                'active': info['active']
            } for timer_id, info in self._timers.items()}
    
    def _timer_callback(self, timer_id, callback):
        """
        Timer callback
        
        Args:
            timer_id: Timer ID
            callback: User callback
        """
        with self._timer_lock:
            if timer_id not in self._timers:
                return
            
            timer_info = self._timers[timer_id]
            timer_info['active'] = False
        
        # Call the user callback
        if callback:
            try:
                callback(timer_id)
            except Exception as e:
                logger.error(f"Error in timer callback: {e}")
        
        # Notify device callbacks
        if DeviceType.TIMER in _hal_state['device_callbacks']:
            for callback in _hal_state['device_callbacks'][DeviceType.TIMER]:
                try:
                    callback(self.device_info.device_id, {'timer_id': timer_id})
                except Exception as e:
                    logger.error(f"Error in timer device callback: {e}")


def register_device(device_info: DeviceInfo, driver_class=None) -> bool:
    """
    Register a device
    
    Args:
        device_info: Device info
        driver_class: Driver class for the device
    
    Returns:
        Success status
    """
    with _device_lock:
        if device_info.device_id in _hal_state['devices']:
            logger.warning(f"Device already registered: {device_info.device_id}")
            return False
        
        _hal_state['devices'][device_info.device_id] = device_info
        
        # Create driver instance if driver class is provided
        if driver_class:
            driver = driver_class(device_info)
            _hal_state['drivers'][device_info.device_id] = driver
            
            # Initialize the driver
            try:
                driver.initialize()
            except Exception as e:
                logger.error(f"Error initializing driver for device {device_info.device_id}: {e}")
                return False
        
        logger.debug(f"Registered device: {device_info.device_id}")
        
        return True


def get_device_info(device_id: str) -> Optional[DeviceInfo]:
    """
    Get device info
    
    Args:
        device_id: Device ID
    
    Returns:
        Device info
    """
    with _device_lock:
        return _hal_state['devices'].get(device_id)


def get_driver(device_id: str) -> Any:
    """
    Get device driver
    
    Args:
        device_id: Device ID
    
    Returns:
        Device driver
    """
    with _device_lock:
        return _hal_state['drivers'].get(device_id)


def list_devices(device_type: str = None) -> List[DeviceInfo]:
    """
    List devices
    
    Args:
        device_type: Filter by device type
    
    Returns:
        List of device info
    """
    with _device_lock:
        if device_type:
            return [info for info in _hal_state['devices'].values() 
                    if info.device_type == device_type]
        else:
            return list(_hal_state['devices'].values())


def register_device_callback(device_type: str, callback: Callable) -> bool:
    """
    Register a callback for device events
    
    Args:
        device_type: Device type
        callback: Callback function
    
    Returns:
        Success status
    """
    with _device_lock:
        if device_type not in _hal_state['device_callbacks']:
            _hal_state['device_callbacks'][device_type] = []
        
        _hal_state['device_callbacks'][device_type].append(callback)
        
        return True


def get_hardware_info() -> Dict[str, Any]:
    """
    Get hardware information
    
    Returns:
        Hardware information
    """
    with _hal_lock:
        return _hal_state['hardware_info']


def detect_hardware() -> Dict[str, Any]:
    """
    Detect hardware
    
    Returns:
        Hardware information
    """
    hardware_info = {}
    
    # Detect system information
    hardware_info['system'] = {
        'system': platform.system(),
        'node': platform.node(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor()
    }
    
    # Detect CPU
    try:
        cpu_info = {
            'count_physical': psutil.cpu_count(logical=False),
            'count_logical': psutil.cpu_count(logical=True),
            'architecture': platform.architecture()[0],
            'model': platform.processor()
        }
        
        hardware_info['cpu'] = cpu_info
    except Exception as e:
        logger.warning(f"Error detecting CPU: {e}")
    
    # Detect memory
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        memory_info = {
            'physical': {
                'total': memory.total,
                'available': memory.available
            },
            'swap': {
                'total': swap.total,
                'free': swap.free
            }
        }
        
        hardware_info['memory'] = memory_info
    except Exception as e:
        logger.warning(f"Error detecting memory: {e}")
    
    # Detect storage
    try:
        disks = []
        
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                
                disk_info = {
                    'device': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free
                }
                
                disks.append(disk_info)
            except Exception as e:
                logger.debug(f"Error getting disk usage for {partition.mountpoint}: {e}")
        
        hardware_info['storage'] = {
            'disks': disks
        }
    except Exception as e:
        logger.warning(f"Error detecting storage: {e}")
    
    # Detect network interfaces
    try:
        interfaces = []
        
        for iface, addrs in psutil.net_if_addrs().items():
            addresses = []
            
            for addr in addrs:
                addr_info = {
                    'family': str(addr.family),
                    'address': addr.address
                }
                
                if addr.netmask:
                    addr_info['netmask'] = addr.netmask
                
                if addr.broadcast:
                    addr_info['broadcast'] = addr.broadcast
                
                addresses.append(addr_info)
            
            iface_info = {
                'name': iface,
                'addresses': addresses
            }
            
            # Add interface statistics if available
            if iface in psutil.net_if_stats():
                stats = psutil.net_if_stats()[iface]
                iface_info['stats'] = {
                    'isup': stats.isup,
                    'duplex': stats.duplex,
                    'speed': stats.speed,
                    'mtu': stats.mtu
                }
            
            interfaces.append(iface_info)
        
        hardware_info['network'] = {
            'interfaces': interfaces
        }
    except Exception as e:
        logger.warning(f"Error detecting network interfaces: {e}")
    
    return hardware_info


def initialize() -> bool:
    """
    Initialize the HAL
    
    Returns:
        Success status
    """
    global _hal_state
    
    with _hal_lock:
        if _hal_state['initialized']:
            logger.warning("HAL already initialized")
            return True
        
        logger.info("Initializing HAL")
        
        # Detect hardware
        hardware_info = detect_hardware()
        _hal_state['hardware_info'] = hardware_info
        
        # Register core devices
        
        # CPU
        cpu_info = DeviceInfo(
            device_id='cpu0',
            device_type=DeviceType.CPU,
            name='CPU',
            description='Central Processing Unit',
            properties=hardware_info.get('cpu', {})
        )
        register_device(cpu_info, CPUDriver)
        
        # Memory
        memory_info = DeviceInfo(
            device_id='mem0',
            device_type=DeviceType.MEMORY,
            name='System Memory',
            description='System RAM',
            properties=hardware_info.get('memory', {}).get('physical', {})
        )
        register_device(memory_info, MemoryDriver)
        
        # Storage devices
        storage_devices = hardware_info.get('storage', {}).get('disks', [])
        for i, disk in enumerate(storage_devices):
            disk_info = DeviceInfo(
                device_id=f'storage{i}',
                device_type=DeviceType.STORAGE,
                name=f"Storage Device {disk.get('device', i)}",
                description=f"Storage device at {disk.get('mountpoint')}",
                properties={
                    'device': disk.get('device'),
                    'mountpoint': disk.get('mountpoint'),
                    'fstype': disk.get('fstype'),
                    'total': disk.get('total'),
                    'path': disk.get('mountpoint')
                }
            )
            register_device(disk_info, StorageDriver)
        
        # Network interfaces
        network_interfaces = hardware_info.get('network', {}).get('interfaces', [])
        for i, iface in enumerate(network_interfaces):
            iface_info = DeviceInfo(
                device_id=f'net{i}',
                device_type=DeviceType.NETWORK,
                name=f"Network Interface {iface.get('name')}",
                description=f"Network interface {iface.get('name')}",
                properties={
                    'interface': iface.get('name'),
                    'addresses': iface.get('addresses', []),
                    'stats': iface.get('stats', {})
                }
            )
            register_device(iface_info, NetworkDriver)
        
        # System timer
        timer_info = DeviceInfo(
            device_id='timer0',
            device_type=DeviceType.TIMER,
            name='System Timer',
            description='System timer device',
            properties={}
        )
        register_device(timer_info, TimerDriver)
        
        # Mark HAL as initialized
        _hal_state['initialized'] = True
        
        logger.info("HAL initialized")
        
        return True

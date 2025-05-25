"""
KOS Hardware Devices

This module provides functions for detecting and interacting with hardware devices,
used by the Hardware Abstraction Layer (HAL).
"""

import os
import sys
import time
import logging
import platform
import psutil
import socket
from typing import Dict, List, Any, Optional, Tuple

# Set up logging
logger = logging.getLogger('KOS.core.hal.devices')


def detect_cpu() -> Dict[str, Any]:
    """
    Detect CPU information
    
    Returns:
        CPU information
    """
    try:
        # Get CPU information
        cpu_info = {
            'model': platform.processor(),
            'architecture': platform.architecture()[0],
            'cores': psutil.cpu_count(logical=False) or 1,
            'threads': psutil.cpu_count(logical=True) or 1,
            'vendor_id': '',
            'frequency': {
                'current': 0,
                'min': 0,
                'max': 0
            },
            'cache': {
                'l1d': 0,
                'l1i': 0,
                'l2': 0,
                'l3': 0
            },
            'features': []
        }
        
        # Try to get CPU frequency
        try:
            freq = psutil.cpu_freq()
            if freq:
                cpu_info['frequency'] = {
                    'current': freq.current,
                    'min': freq.min if hasattr(freq, 'min') else 0,
                    'max': freq.max if hasattr(freq, 'max') else 0
                }
        except Exception as e:
            logger.debug(f"Error getting CPU frequency: {e}")
        
        # Try to get more detailed CPU information from /proc/cpuinfo on Linux
        if platform.system() == 'Linux':
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                
                # Parse CPU info
                for line in cpuinfo.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if key == 'vendor_id':
                            cpu_info['vendor_id'] = value
                        elif key == 'model name' and not cpu_info['model']:
                            cpu_info['model'] = value
                        elif key == 'flags':
                            cpu_info['features'] = value.split()
            except Exception as e:
                logger.debug(f"Error reading /proc/cpuinfo: {e}")
        
        # Additional information for Windows
        if platform.system() == 'Windows':
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\\DESCRIPTION\\System\\CentralProcessor\\0") as key:
                    cpu_info['vendor_id'] = winreg.QueryValueEx(key, "VendorIdentifier")[0]
                    if not cpu_info['model']:
                        cpu_info['model'] = winreg.QueryValueEx(key, "ProcessorNameString")[0]
                    cpu_info['frequency']['max'] = winreg.QueryValueEx(key, "~MHz")[0]
            except Exception as e:
                logger.debug(f"Error getting Windows CPU info: {e}")
        
        return cpu_info
    except Exception as e:
        logger.error(f"Error detecting CPU: {e}")
        return {
            'model': 'Unknown',
            'architecture': platform.architecture()[0],
            'cores': 1,
            'threads': 1
        }


def detect_memory() -> Dict[str, Any]:
    """
    Detect memory information
    
    Returns:
        Memory information
    """
    try:
        # Get memory information
        virtual_mem = psutil.virtual_memory()
        swap_mem = psutil.swap_memory()
        
        memory_info = {
            'total': virtual_mem.total,
            'available': virtual_mem.available,
            'used': virtual_mem.used,
            'free': virtual_mem.free,
            'percent': virtual_mem.percent,
            'swap': {
                'total': swap_mem.total,
                'used': swap_mem.used,
                'free': swap_mem.free,
                'percent': swap_mem.percent
            }
        }
        
        return memory_info
    except Exception as e:
        logger.error(f"Error detecting memory: {e}")
        return {
            'total': 0,
            'available': 0,
            'used': 0,
            'free': 0,
            'percent': 0,
            'swap': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0
            }
        }


def detect_storage_devices() -> List[Dict[str, Any]]:
    """
    Detect storage devices
    
    Returns:
        List of storage device information
    """
    devices = []
    
    try:
        # Get disk partitions
        partitions = psutil.disk_partitions(all=True)
        
        for partition in partitions:
            try:
                device_info = {
                    'name': partition.device,
                    'mountpoint': partition.mountpoint,
                    'fstype': partition.fstype,
                    'options': partition.opts,
                    'size': 0,
                    'used': 0,
                    'free': 0,
                    'percent': 0
                }
                
                # Get disk usage if possible
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device_info.update({
                        'size': usage.total,
                        'used': usage.used,
                        'free': usage.free,
                        'percent': usage.percent
                    })
                except Exception as e:
                    logger.debug(f"Error getting disk usage for {partition.mountpoint}: {e}")
                
                devices.append(device_info)
            except Exception as e:
                logger.debug(f"Error processing partition {partition.device}: {e}")
        
        # Get disk I/O statistics if available
        try:
            disk_io = psutil.disk_io_counters(perdisk=True)
            
            for name, io_stats in disk_io.items():
                # Try to match with an existing device
                matched = False
                for device in devices:
                    if name in device['name'] or device['name'] in name:
                        device['io'] = {
                            'read_count': io_stats.read_count,
                            'write_count': io_stats.write_count,
                            'read_bytes': io_stats.read_bytes,
                            'write_bytes': io_stats.write_bytes,
                            'read_time': io_stats.read_time,
                            'write_time': io_stats.write_time
                        }
                        matched = True
                        break
                
                # If no match found, add as a separate device
                if not matched:
                    devices.append({
                        'name': f"/dev/{name}" if platform.system() != 'Windows' else name,
                        'mountpoint': '',
                        'fstype': '',
                        'options': '',
                        'size': 0,
                        'used': 0,
                        'free': 0,
                        'percent': 0,
                        'io': {
                            'read_count': io_stats.read_count,
                            'write_count': io_stats.write_count,
                            'read_bytes': io_stats.read_bytes,
                            'write_bytes': io_stats.write_bytes,
                            'read_time': io_stats.read_time,
                            'write_time': io_stats.write_time
                        }
                    })
        except Exception as e:
            logger.debug(f"Error getting disk I/O statistics: {e}")
    except Exception as e:
        logger.error(f"Error detecting storage devices: {e}")
    
    return devices


def detect_network_interfaces() -> List[Dict[str, Any]]:
    """
    Detect network interfaces
    
    Returns:
        List of network interface information
    """
    interfaces = []
    
    try:
        # Get network addresses
        net_if_addrs = psutil.net_if_addrs()
        net_if_stats = psutil.net_if_stats()
        net_io_counters = psutil.net_io_counters(pernic=True)
        
        for interface_name, addrs in net_if_addrs.items():
            # Create interface info
            interface_info = {
                'name': interface_name,
                'addresses': [],
                'stats': {},
                'io': {}
            }
            
            # Add addresses
            for addr in addrs:
                addr_info = {
                    'family': str(addr.family),
                    'address': addr.address
                }
                
                if addr.netmask:
                    addr_info['netmask'] = addr.netmask
                
                if addr.broadcast:
                    addr_info['broadcast'] = addr.broadcast
                
                interface_info['addresses'].append(addr_info)
                
                # Add primary IPv4 address to top level
                if addr.family == socket.AF_INET:
                    interface_info['ip'] = addr.address
            
            # Add interface statistics
            if interface_name in net_if_stats:
                stats = net_if_stats[interface_name]
                interface_info['stats'] = {
                    'up': stats.isup,
                    'duplex': stats.duplex,
                    'speed': stats.speed,
                    'mtu': stats.mtu
                }
            
            # Add I/O counters
            if interface_name in net_io_counters:
                io = net_io_counters[interface_name]
                interface_info['io'] = {
                    'bytes_sent': io.bytes_sent,
                    'bytes_recv': io.bytes_recv,
                    'packets_sent': io.packets_sent,
                    'packets_recv': io.packets_recv,
                    'errin': io.errin,
                    'errout': io.errout,
                    'dropin': io.dropin,
                    'dropout': io.dropout
                }
            
            interfaces.append(interface_info)
    except Exception as e:
        logger.error(f"Error detecting network interfaces: {e}")
    
    return interfaces


def read_disk(device_path: str, offset: int = 0, size: int = 512) -> bytes:
    """
    Read directly from a disk device
    
    Args:
        device_path: Path to the device
        offset: Offset in bytes
        size: Number of bytes to read
    
    Returns:
        Data read from the disk
    """
    try:
        with open(device_path, 'rb') as f:
            f.seek(offset)
            return f.read(size)
    except Exception as e:
        logger.error(f"Error reading from disk device {device_path}: {e}")
        raise IOError(f"Cannot read from disk device: {e}")


def write_disk(device_path: str, data: bytes, offset: int = 0) -> int:
    """
    Write directly to a disk device
    
    Args:
        device_path: Path to the device
        data: Data to write
        offset: Offset in bytes
    
    Returns:
        Number of bytes written
    """
    try:
        with open(device_path, 'r+b') as f:
            f.seek(offset)
            return f.write(data)
    except Exception as e:
        logger.error(f"Error writing to disk device {device_path}: {e}")
        raise IOError(f"Cannot write to disk device: {e}")


def get_cpu_usage() -> Dict[str, Any]:
    """
    Get current CPU usage
    
    Returns:
        CPU usage information
    """
    try:
        # Get CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_times = psutil.cpu_times_percent(interval=0.1, percpu=True)
        
        # Calculate overall CPU usage
        overall_percent = sum(cpu_percent) / len(cpu_percent) if cpu_percent else 0
        
        usage = {
            'overall_percent': overall_percent,
            'per_cpu_percent': cpu_percent,
            'per_cpu_times': []
        }
        
        # Add per-CPU time breakdowns
        for i, times in enumerate(cpu_times):
            usage['per_cpu_times'].append({
                'cpu': i,
                'user': times.user,
                'system': times.system,
                'idle': times.idle,
                'nice': times.nice if hasattr(times, 'nice') else 0,
                'iowait': times.iowait if hasattr(times, 'iowait') else 0,
                'irq': times.irq if hasattr(times, 'irq') else 0,
                'softirq': times.softirq if hasattr(times, 'softirq') else 0,
                'steal': times.steal if hasattr(times, 'steal') else 0,
                'guest': times.guest if hasattr(times, 'guest') else 0
            })
        
        return usage
    except Exception as e:
        logger.error(f"Error getting CPU usage: {e}")
        return {
            'overall_percent': 0,
            'per_cpu_percent': [],
            'per_cpu_times': []
        }


def get_memory_usage() -> Dict[str, Any]:
    """
    Get current memory usage
    
    Returns:
        Memory usage information
    """
    try:
        # Get memory usage
        virtual_mem = psutil.virtual_memory()
        swap_mem = psutil.swap_memory()
        
        usage = {
            'virtual': {
                'total': virtual_mem.total,
                'available': virtual_mem.available,
                'used': virtual_mem.used,
                'free': virtual_mem.free,
                'percent': virtual_mem.percent,
                'active': virtual_mem.active if hasattr(virtual_mem, 'active') else 0,
                'inactive': virtual_mem.inactive if hasattr(virtual_mem, 'inactive') else 0,
                'buffers': virtual_mem.buffers if hasattr(virtual_mem, 'buffers') else 0,
                'cached': virtual_mem.cached if hasattr(virtual_mem, 'cached') else 0,
                'shared': virtual_mem.shared if hasattr(virtual_mem, 'shared') else 0,
                'slab': virtual_mem.slab if hasattr(virtual_mem, 'slab') else 0
            },
            'swap': {
                'total': swap_mem.total,
                'used': swap_mem.used,
                'free': swap_mem.free,
                'percent': swap_mem.percent,
                'sin': swap_mem.sin if hasattr(swap_mem, 'sin') else 0,
                'sout': swap_mem.sout if hasattr(swap_mem, 'sout') else 0
            }
        }
        
        return usage
    except Exception as e:
        logger.error(f"Error getting memory usage: {e}")
        return {
            'virtual': {
                'total': 0,
                'available': 0,
                'used': 0,
                'free': 0,
                'percent': 0
            },
            'swap': {
                'total': 0,
                'used': 0,
                'free': 0,
                'percent': 0
            }
        }


def get_disk_usage(path: str = None) -> Dict[str, Any]:
    """
    Get disk usage for a path or all mounted filesystems
    
    Args:
        path: Path to get disk usage for, or None for all
    
    Returns:
        Disk usage information
    """
    try:
        if path:
            # Get disk usage for a specific path
            usage = psutil.disk_usage(path)
            
            return {
                'path': path,
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': usage.percent
            }
        else:
            # Get disk usage for all partitions
            partitions = psutil.disk_partitions()
            usage = {}
            
            for partition in partitions:
                try:
                    part_usage = psutil.disk_usage(partition.mountpoint)
                    
                    usage[partition.mountpoint] = {
                        'device': partition.device,
                        'fstype': partition.fstype,
                        'total': part_usage.total,
                        'used': part_usage.used,
                        'free': part_usage.free,
                        'percent': part_usage.percent
                    }
                except Exception as e:
                    logger.debug(f"Error getting disk usage for {partition.mountpoint}: {e}")
            
            return usage
    except Exception as e:
        logger.error(f"Error getting disk usage: {e}")
        return {}


def get_network_usage() -> Dict[str, Any]:
    """
    Get current network usage
    
    Returns:
        Network usage information
    """
    try:
        # Get network I/O counters
        net_io = psutil.net_io_counters(pernic=True)
        
        usage = {}
        
        for interface, counters in net_io.items():
            usage[interface] = {
                'bytes_sent': counters.bytes_sent,
                'bytes_recv': counters.bytes_recv,
                'packets_sent': counters.packets_sent,
                'packets_recv': counters.packets_recv,
                'errin': counters.errin,
                'errout': counters.errout,
                'dropin': counters.dropin,
                'dropout': counters.dropout
            }
        
        return usage
    except Exception as e:
        logger.error(f"Error getting network usage: {e}")
        return {}


def get_network_connections() -> List[Dict[str, Any]]:
    """
    Get current network connections
    
    Returns:
        List of network connections
    """
    connections = []
    
    try:
        # Get network connections
        net_connections = psutil.net_connections()
        
        for conn in net_connections:
            connection_info = {
                'fd': conn.fd,
                'family': conn.family,
                'type': conn.type,
                'status': conn.status,
                'pid': conn.pid
            }
            
            # Add local address if available
            if conn.laddr:
                connection_info['local_address'] = {
                    'ip': conn.laddr.ip,
                    'port': conn.laddr.port
                }
            
            # Add remote address if available
            if conn.raddr:
                connection_info['remote_address'] = {
                    'ip': conn.raddr.ip,
                    'port': conn.raddr.port
                }
            
            connections.append(connection_info)
    except Exception as e:
        logger.error(f"Error getting network connections: {e}")
    
    return connections

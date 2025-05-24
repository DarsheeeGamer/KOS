"""
SystemInfo Component for KADVLayer

This module provides comprehensive system information gathering capabilities,
retrieving details about the host system's hardware, OS, and environment.
"""

import os
import sys
import platform
import socket
import logging
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.system_info')

class SystemInfo:
    """
    Gathers comprehensive system information about the host computer
    
    This class provides methods to retrieve detailed information about
    the host system's hardware, operating system, and environment.
    """
    
    def __init__(self):
        """Initialize the SystemInfo component"""
        self.cache_timeout = 60  # Cache timeout in seconds
        self._system_info_cache = None
        self._cache_timestamp = 0
        logger.debug("SystemInfo component initialized")
    
    def get_system_info(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive system information
        
        Args:
            use_cache: Whether to use cached data (if available)
            
        Returns:
            Dictionary with system information
        """
        current_time = datetime.now().timestamp()
        
        # Return cached data if available and not expired
        if use_cache and self._system_info_cache is not None:
            if current_time - self._cache_timestamp < self.cache_timeout:
                return self._system_info_cache
        
        try:
            # Collect system information
            info = {
                "timestamp": datetime.now().isoformat(),
                "platform": self._get_platform_info(),
                "cpu": self._get_cpu_info(),
                "memory": self._get_memory_info(),
                "disk": self._get_disk_info(),
                "network": self._get_network_info(),
                "python": self._get_python_info(),
                "user": self._get_user_info()
            }
            
            # Cache the result
            self._system_info_cache = info
            self._cache_timestamp = current_time
            
            return info
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {"error": str(e)}
    
    def _get_platform_info(self) -> Dict[str, Any]:
        """Get platform-specific information"""
        info = {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }
        
        # Add Windows-specific information
        if platform.system() == "Windows":
            info["win_edition"] = platform.win32_edition() if hasattr(platform, 'win32_edition') else None
            info["win_ver"] = platform.win32_ver() if hasattr(platform, 'win32_ver') else None
        
        # Add Linux-specific information
        elif platform.system() == "Linux":
            info["libc_ver"] = platform.libc_ver() if hasattr(platform, 'libc_ver') else None
            try:
                with open('/etc/os-release', 'r') as f:
                    lines = f.readlines()
                    info["distro"] = {}
                    for line in lines:
                        if '=' in line:
                            key, value = line.rstrip().split('=', 1)
                            info["distro"][key] = value.strip('"\'')
            except:
                pass
        
        # Add macOS-specific information
        elif platform.system() == "Darwin":
            info["mac_ver"] = platform.mac_ver() if hasattr(platform, 'mac_ver') else None
        
        # Get boot time if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                boot_time = psutil.boot_time()
                info["boot_time"] = datetime.fromtimestamp(boot_time).isoformat()
                info["uptime_seconds"] = int(datetime.now().timestamp() - boot_time)
            except:
                pass
        
        return info
    
    def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information"""
        info = {
            "count_logical": os.cpu_count(),
            "architecture": platform.architecture()
        }
        
        # Add detailed CPU info if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                info["count_physical"] = psutil.cpu_count(logical=False)
                info["percent"] = psutil.cpu_percent(interval=0.1)
                info["freq"] = {}
                
                if hasattr(psutil, 'cpu_freq'):
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        info["freq"]["current"] = cpu_freq.current
                        info["freq"]["min"] = cpu_freq.min
                        info["freq"]["max"] = cpu_freq.max
                
                if hasattr(psutil, 'cpu_stats'):
                    cpu_stats = psutil.cpu_stats()
                    info["stats"] = {
                        "ctx_switches": cpu_stats.ctx_switches,
                        "interrupts": cpu_stats.interrupts,
                        "soft_interrupts": cpu_stats.soft_interrupts,
                        "syscalls": cpu_stats.syscalls
                    }
            except:
                pass
        
        return info
    
    def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information"""
        info = {}
        
        # Get memory info if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                virtual_memory = psutil.virtual_memory()
                info["virtual"] = {
                    "total": virtual_memory.total,
                    "available": virtual_memory.available,
                    "percent": virtual_memory.percent,
                    "used": virtual_memory.used,
                    "free": virtual_memory.free
                }
                
                swap_memory = psutil.swap_memory()
                info["swap"] = {
                    "total": swap_memory.total,
                    "used": swap_memory.used,
                    "free": swap_memory.free,
                    "percent": swap_memory.percent
                }
            except:
                pass
        
        return info
    
    def _get_disk_info(self) -> Dict[str, Any]:
        """Get disk information"""
        info = {}
        
        # Get disk info if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                partitions = []
                for partition in psutil.disk_partitions():
                    part_info = {
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "opts": partition.opts
                    }
                    
                    try:
                        usage = psutil.disk_usage(partition.mountpoint)
                        part_info["total"] = usage.total
                        part_info["used"] = usage.used
                        part_info["free"] = usage.free
                        part_info["percent"] = usage.percent
                    except:
                        # Some mountpoints may not be accessible
                        pass
                    
                    partitions.append(part_info)
                
                info["partitions"] = partitions
                
                if hasattr(psutil, 'disk_io_counters'):
                    io_counters = psutil.disk_io_counters()
                    if io_counters:
                        info["io"] = {
                            "read_count": io_counters.read_count,
                            "write_count": io_counters.write_count,
                            "read_bytes": io_counters.read_bytes,
                            "write_bytes": io_counters.write_bytes
                        }
            except:
                pass
        
        return info
    
    def _get_network_info(self) -> Dict[str, Any]:
        """Get network information"""
        info = {
            "hostname": socket.gethostname()
        }
        
        # Try to get IP addresses
        try:
            info["ip_addresses"] = {}
            
            # Get primary IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            info["ip_addresses"]["primary"] = s.getsockname()[0]
            s.close()
            
            # Get all IP addresses
            all_ips = []
            for interface, addrs in socket.getaddrinfo(socket.gethostname(), None):
                all_ips.append(addrs[0])
            info["ip_addresses"]["all"] = list(set(all_ips))
        except:
            pass
        
        # Get network interfaces if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                interfaces = {}
                if hasattr(psutil, 'net_if_addrs'):
                    net_if_addrs = psutil.net_if_addrs()
                    for interface_name, addresses in net_if_addrs.items():
                        interfaces[interface_name] = []
                        for addr in addresses:
                            addr_info = {
                                "family": str(addr.family),
                                "address": addr.address
                            }
                            if hasattr(addr, 'netmask') and addr.netmask:
                                addr_info["netmask"] = addr.netmask
                            if hasattr(addr, 'broadcast') and addr.broadcast:
                                addr_info["broadcast"] = addr.broadcast
                            interfaces[interface_name].append(addr_info)
                
                info["interfaces"] = interfaces
                
                if hasattr(psutil, 'net_io_counters'):
                    io_counters = psutil.net_io_counters()
                    if io_counters:
                        info["io"] = {
                            "bytes_sent": io_counters.bytes_sent,
                            "bytes_recv": io_counters.bytes_recv,
                            "packets_sent": io_counters.packets_sent,
                            "packets_recv": io_counters.packets_recv
                        }
            except:
                pass
        
        return info
    
    def _get_python_info(self) -> Dict[str, Any]:
        """Get Python environment information"""
        info = {
            "version": sys.version,
            "version_info": {
                "major": sys.version_info.major,
                "minor": sys.version_info.minor,
                "micro": sys.version_info.micro
            },
            "executable": sys.executable,
            "platform": sys.platform
        }
        
        # Get installed packages
        try:
            import pkg_resources
            info["packages"] = []
            for pkg in pkg_resources.working_set:
                info["packages"].append({
                    "name": pkg.key,
                    "version": pkg.version
                })
        except:
            pass
        
        return info
    
    def _get_user_info(self) -> Dict[str, Any]:
        """Get user information"""
        info = {
            "username": os.getlogin() if hasattr(os, 'getlogin') else None,
            "home_dir": os.path.expanduser("~"),
            "cwd": os.getcwd()
        }
        
        # Get user info if psutil is available
        if PSUTIL_AVAILABLE:
            try:
                if hasattr(psutil, 'users'):
                    users = psutil.users()
                    if users:
                        info["logged_in_users"] = []
                        for user in users:
                            user_info = {
                                "name": user.name,
                                "terminal": user.terminal
                            }
                            if hasattr(user, 'started'):
                                user_info["started"] = user.started
                            info["logged_in_users"].append(user_info)
            except:
                pass
        
        return info
    
    def get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information only"""
        return self._get_cpu_info()
    
    def get_memory_info(self) -> Dict[str, Any]:
        """Get memory information only"""
        return self._get_memory_info()
    
    def get_disk_info(self) -> Dict[str, Any]:
        """Get disk information only"""
        return self._get_disk_info()
    
    def get_network_info(self) -> Dict[str, Any]:
        """Get network information only"""
        return self._get_network_info()
    
    def to_json(self, use_cache: bool = True) -> str:
        """
        Get system information as JSON string
        
        Args:
            use_cache: Whether to use cached data
            
        Returns:
            JSON string with system information
        """
        info = self.get_system_info(use_cache)
        return json.dumps(info, indent=2)
    
    def get_hardware_summary(self) -> str:
        """
        Get a human-readable summary of hardware information
        
        Returns:
            String with hardware summary
        """
        info = self.get_system_info()
        
        cpu_info = info.get("cpu", {})
        memory_info = info.get("memory", {}).get("virtual", {})
        
        summary = []
        summary.append(f"System: {info.get('platform', {}).get('system')} {info.get('platform', {}).get('release')}")
        summary.append(f"Machine: {info.get('platform', {}).get('machine')}")
        summary.append(f"Processor: {cpu_info.get('count_logical')} logical cores")
        
        if memory_info:
            total_gb = memory_info.get("total", 0) / (1024 ** 3)
            summary.append(f"Memory: {total_gb:.1f} GB total")
        
        return "\n".join(summary)

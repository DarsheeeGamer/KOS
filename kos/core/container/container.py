"""
KOS Container Class

Provides the core container implementation for KOS:
- Container state management
- Resource tracking and limits
- Integration with runtime and monitoring
"""

import os
import time
import json
import uuid
import logging
from typing import Dict, List, Any, Optional, Tuple

# Initialize logging
logger = logging.getLogger('KOS.container.container')

class ContainerState:
    """Container states"""
    CREATED = "created"
    RUNNING = "running"
    EXITED = "exited"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"

class ContainerConfig:
    """Container configuration"""
    def __init__(
        self,
        image: str,
        command: Optional[List[str]] = None,
        entrypoint: Optional[List[str]] = None,
        env: Dict[str, str] = None,
        volumes: List[Dict[str, str]] = None,
        ports: List[Dict[str, Any]] = None,
        network: str = "bridge",
        restart_policy: str = "no",
        max_restart_count: int = 3,
        health_check: Dict[str, Any] = None,
        resource_limits: Dict[str, Any] = None
    ):
        self.image = image
        self.command = command or []
        self.entrypoint = entrypoint or []
        self.env = env or {}
        self.volumes = volumes or []
        self.ports = ports or []
        self.network = network
        self.restart_policy = restart_policy
        self.max_restart_count = max_restart_count
        self.health_check = health_check
        self.resource_limits = resource_limits or {}

class Container:
    """
    Container class representing a KOS container
    """
    def __init__(self, name: str, config: ContainerConfig = None, container_dict: Dict[str, Any] = None):
        """
        Initialize a container
        
        Args:
            name: Container name
            config: Container configuration
            container_dict: Container data dictionary (for loading)
        """
        self.name = name
        self.id = str(uuid.uuid4())[:12]  # Short UUID for container ID
        
        if container_dict:
            # Load from dictionary
            self._load_from_dict(container_dict)
        else:
            # Initialize with config
            self.image = config.image
            self.command = config.command
            self.entrypoint = config.entrypoint
            self.env = config.env
            self.volumes = config.volumes
            self.ports = config.ports
            self.network = config.network
            self.restart_policy = config.restart_policy
            self.max_restart_count = config.max_restart_count
            self.health_check = config.health_check
            self.resource_limits = config.resource_limits
            
            # State and runtime data
            self.state = ContainerState.CREATED
            self.pid = None
            self.ip_address = None
            self.exit_code = None
            self.manually_stopped = False
            self.created = time.time()
            self.start_time = None
            self.exit_time = None
            self.restart_count = 0
            
            # Health status
            self.health_status = "starting"
            self.healthy = None
            self.unhealthy_count = 0
            
            # Metrics
            self.metrics = {
                'cpu_usage': 0.0,
                'memory_usage': 0,
                'memory_limit': self.resource_limits.get('memory'),
                'io_read': 0,
                'io_write': 0,
                'network_rx': 0,
                'network_tx': 0
            }
            
            # File paths
            self.rootfs = None
            self.config_path = None
            self.log_path = None
    
    def _load_from_dict(self, data: Dict[str, Any]):
        """Load container from dictionary"""
        self.id = data.get('id', str(uuid.uuid4())[:12])
        self.image = data.get('image')
        self.command = data.get('command', [])
        self.entrypoint = data.get('entrypoint', [])
        self.env = data.get('env', {})
        self.volumes = data.get('volumes', [])
        self.ports = data.get('ports', [])
        self.network = data.get('network', 'bridge')
        self.restart_policy = data.get('restart_policy', 'no')
        self.max_restart_count = data.get('max_restart_count', 3)
        self.health_check = data.get('health_check')
        self.resource_limits = data.get('resource_limits', {})
        
        # State and runtime data
        self.state = data.get('state', ContainerState.CREATED)
        self.pid = data.get('pid')
        self.ip_address = data.get('ip_address')
        self.exit_code = data.get('exit_code')
        self.manually_stopped = data.get('manually_stopped', False)
        self.created = data.get('created', time.time())
        self.start_time = data.get('start_time')
        self.exit_time = data.get('exit_time')
        self.restart_count = data.get('restart_count', 0)
        
        # Health status
        self.health_status = data.get('health_status', 'starting')
        self.healthy = data.get('healthy')
        self.unhealthy_count = data.get('unhealthy_count', 0)
        
        # Metrics
        self.metrics = data.get('metrics', {
            'cpu_usage': 0.0,
            'memory_usage': 0,
            'memory_limit': self.resource_limits.get('memory'),
            'io_read': 0,
            'io_write': 0,
            'network_rx': 0,
            'network_tx': 0
        })
        
        # File paths
        self.rootfs = data.get('rootfs')
        self.config_path = data.get('config_path')
        self.log_path = data.get('log_path')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary for serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'command': self.command,
            'entrypoint': self.entrypoint,
            'env': self.env,
            'volumes': self.volumes,
            'ports': self.ports,
            'network': self.network,
            'restart_policy': self.restart_policy,
            'max_restart_count': self.max_restart_count,
            'health_check': self.health_check,
            'resource_limits': self.resource_limits,
            
            'state': self.state,
            'pid': self.pid,
            'ip_address': self.ip_address,
            'exit_code': self.exit_code,
            'manually_stopped': self.manually_stopped,
            'created': self.created,
            'start_time': self.start_time,
            'exit_time': self.exit_time,
            'restart_count': self.restart_count,
            
            'health_status': self.health_status,
            'healthy': self.healthy,
            'unhealthy_count': self.unhealthy_count,
            
            'metrics': self.metrics,
            
            'rootfs': self.rootfs,
            'config_path': self.config_path,
            'log_path': self.log_path
        }
    
    def update_metrics(self):
        """Update container metrics from the runtime"""
        try:
            # This would normally use cgroups or process stats
            # For this implementation, we'll use psutil to get real metrics
            import psutil
            
            if self.pid:
                try:
                    process = psutil.Process(self.pid)
                    
                    # CPU usage
                    self.metrics['cpu_usage'] = process.cpu_percent(interval=0.1)
                    
                    # Memory usage
                    memory_info = process.memory_info()
                    self.metrics['memory_usage'] = memory_info.rss
                    
                    # I/O usage
                    io_counters = process.io_counters()
                    if 'io_read_prev' in self.metrics:
                        self.metrics['io_read'] = io_counters.read_bytes - self.metrics['io_read_prev']
                    self.metrics['io_read_prev'] = io_counters.read_bytes
                    
                    if 'io_write_prev' in self.metrics:
                        self.metrics['io_write'] = io_counters.write_bytes - self.metrics['io_write_prev']
                    self.metrics['io_write_prev'] = io_counters.write_bytes
                    
                    # Network usage
                    net_io = psutil.net_io_counters(pernic=True).get(self.network_interface)
                    if net_io:
                        if 'network_rx_prev' in self.metrics:
                            self.metrics['network_rx'] = net_io.bytes_recv - self.metrics['network_rx_prev']
                        self.metrics['network_rx_prev'] = net_io.bytes_recv
                        
                        if 'network_tx_prev' in self.metrics:
                            self.metrics['network_tx'] = net_io.bytes_sent - self.metrics['network_tx_prev']
                        self.metrics['network_tx_prev'] = net_io.bytes_sent
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    logger.warning(f"Failed to update metrics for container {self.name}: process {self.pid} not found")
                    self.pid = None
        
        except ImportError:
            # If psutil is not available, use dummy values
            self.metrics['cpu_usage'] = 0.1  # 0.1% CPU
            self.metrics['memory_usage'] += 1024  # Increase by 1KB
            self.metrics['io_read'] = 512  # 512 bytes
            self.metrics['io_write'] = 1024  # 1KB
            self.metrics['network_rx'] = 256  # 256 bytes
            self.metrics['network_tx'] = 512  # 512 bytes
            
            logger.debug(f"Using dummy metrics for container {self.name}")
    
    @property
    def network_interface(self):
        """Get the network interface name for this container"""
        return f"c-{self.id[:6]}"
    
    @property
    def runtime_config(self):
        """Get runtime configuration for this container"""
        return {
            'id': self.id,
            'name': self.name,
            'image': self.image,
            'command': self.command,
            'entrypoint': self.entrypoint,
            'env': self.env,
            'volumes': self.volumes,
            'ports': self.ports,
            'network': self.network,
            'resource_limits': self.resource_limits,
            'rootfs': self.rootfs,
            'log_path': self.log_path
        }

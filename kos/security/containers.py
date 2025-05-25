"""
KOS Containerization Extensions

This module provides containerization capabilities for KOS,
allowing enhanced isolation of processes and resources.
"""

import os
import sys
import logging
import threading
import json
import subprocess
import uuid
import time
import shutil
import tempfile
from typing import Dict, List, Any, Optional, Union, Tuple

from kos.security.users import UserManager
from kos.security.mac import MACManager, SecurityContext

# Set up logging
logger = logging.getLogger('KOS.security.containers')

# Lock for container operations
_container_lock = threading.RLock()

# Container registry
_containers = {}

# Maximum container resource limits
DEFAULT_MAX_MEMORY = 1024 * 1024 * 1024  # 1 GB
DEFAULT_MAX_CPU = 1.0  # 1 CPU core
DEFAULT_MAX_PROCESSES = 20
DEFAULT_MAX_FILES = 100
DEFAULT_MAX_DISK = 1024 * 1024 * 1024  # 1 GB


class ContainerResources:
    """Container resource limits and usage"""
    
    def __init__(self, 
                 max_memory: int = DEFAULT_MAX_MEMORY,
                 max_cpu: float = DEFAULT_MAX_CPU,
                 max_processes: int = DEFAULT_MAX_PROCESSES,
                 max_files: int = DEFAULT_MAX_FILES,
                 max_disk: int = DEFAULT_MAX_DISK):
        """
        Initialize container resources
        
        Args:
            max_memory: Maximum memory usage in bytes
            max_cpu: Maximum CPU usage (1.0 = 1 core)
            max_processes: Maximum number of processes
            max_files: Maximum number of open files
            max_processes: Maximum number of processes
            max_disk: Maximum disk usage in bytes
        """
        self.max_memory = max_memory
        self.max_cpu = max_cpu
        self.max_processes = max_processes
        self.max_files = max_files
        self.max_disk = max_disk
        
        # Current usage
        self.memory_usage = 0
        self.cpu_usage = 0.0
        self.process_count = 0
        self.file_count = 0
        self.disk_usage = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "max_memory": self.max_memory,
            "max_cpu": self.max_cpu,
            "max_processes": self.max_processes,
            "max_files": self.max_files,
            "max_disk": self.max_disk,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "process_count": self.process_count,
            "file_count": self.file_count,
            "disk_usage": self.disk_usage
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContainerResources':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            ContainerResources instance
        """
        resources = cls(
            max_memory=data.get("max_memory", DEFAULT_MAX_MEMORY),
            max_cpu=data.get("max_cpu", DEFAULT_MAX_CPU),
            max_processes=data.get("max_processes", DEFAULT_MAX_PROCESSES),
            max_files=data.get("max_files", DEFAULT_MAX_FILES),
            max_disk=data.get("max_disk", DEFAULT_MAX_DISK)
        )
        
        resources.memory_usage = data.get("memory_usage", 0)
        resources.cpu_usage = data.get("cpu_usage", 0.0)
        resources.process_count = data.get("process_count", 0)
        resources.file_count = data.get("file_count", 0)
        resources.disk_usage = data.get("disk_usage", 0)
        
        return resources


class NetworkPolicy:
    """Container network policy"""
    
    def __init__(self, 
                 allow_outbound: bool = True,
                 allow_inbound: bool = False,
                 allowed_hosts: List[str] = None,
                 allowed_ports: List[int] = None):
        """
        Initialize network policy
        
        Args:
            allow_outbound: Allow outbound connections
            allow_inbound: Allow inbound connections
            allowed_hosts: List of allowed hosts
            allowed_ports: List of allowed ports
        """
        self.allow_outbound = allow_outbound
        self.allow_inbound = allow_inbound
        self.allowed_hosts = allowed_hosts or []
        self.allowed_ports = allowed_ports or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "allow_outbound": self.allow_outbound,
            "allow_inbound": self.allow_inbound,
            "allowed_hosts": self.allowed_hosts,
            "allowed_ports": self.allowed_ports
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NetworkPolicy':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            NetworkPolicy instance
        """
        return cls(
            allow_outbound=data.get("allow_outbound", True),
            allow_inbound=data.get("allow_inbound", False),
            allowed_hosts=data.get("allowed_hosts", []),
            allowed_ports=data.get("allowed_ports", [])
        )
    
    def check_connection(self, host: str, port: int, direction: str) -> bool:
        """
        Check if a connection is allowed
        
        Args:
            host: Host address
            port: Port number
            direction: Connection direction ('inbound' or 'outbound')
        
        Returns:
            True if connection is allowed, False otherwise
        """
        if direction == 'inbound' and not self.allow_inbound:
            return False
        
        if direction == 'outbound' and not self.allow_outbound:
            return False
        
        # If no specific hosts or ports are defined, use the global setting
        if not self.allowed_hosts and not self.allowed_ports:
            return True
        
        # Check if host is allowed
        host_allowed = not self.allowed_hosts or host in self.allowed_hosts
        
        # Check if port is allowed
        port_allowed = not self.allowed_ports or port in self.allowed_ports
        
        return host_allowed and port_allowed


class MountPoint:
    """Container mount point"""
    
    def __init__(self, 
                 host_path: str,
                 container_path: str,
                 read_only: bool = False):
        """
        Initialize mount point
        
        Args:
            host_path: Path on host
            container_path: Path in container
            read_only: Mount as read-only
        """
        self.host_path = host_path
        self.container_path = container_path
        self.read_only = read_only
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "host_path": self.host_path,
            "container_path": self.container_path,
            "read_only": self.read_only
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MountPoint':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            MountPoint instance
        """
        return cls(
            host_path=data.get("host_path", ""),
            container_path=data.get("container_path", ""),
            read_only=data.get("read_only", False)
        )


class Container:
    """Container instance"""
    
    def __init__(self, 
                 name: str,
                 user_id: int,
                 security_context: SecurityContext = None,
                 resources: ContainerResources = None,
                 network_policy: NetworkPolicy = None,
                 mounts: List[MountPoint] = None):
        """
        Initialize container
        
        Args:
            name: Container name
            user_id: User ID
            security_context: Security context
            resources: Resource limits
            network_policy: Network policy
            mounts: Mount points
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.user_id = user_id
        self.security_context = security_context or SecurityContext(user="container", role="container_r", type="container_t")
        self.resources = resources or ContainerResources()
        self.network_policy = network_policy or NetworkPolicy()
        self.mounts = mounts or []
        
        # Runtime data
        self.created_at = time.time()
        self.status = "created"  # created, running, paused, stopped
        self.processes = []
        self.root_path = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "id": self.id,
            "name": self.name,
            "user_id": self.user_id,
            "security_context": self.security_context.__dict__ if self.security_context else None,
            "resources": self.resources.to_dict() if self.resources else None,
            "network_policy": self.network_policy.to_dict() if self.network_policy else None,
            "mounts": [mount.to_dict() for mount in self.mounts],
            "created_at": self.created_at,
            "status": self.status,
            "processes": self.processes,
            "root_path": self.root_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Container':
        """
        Create from dictionary
        
        Args:
            data: Dictionary representation
        
        Returns:
            Container instance
        """
        container = cls(
            name=data.get("name", ""),
            user_id=data.get("user_id", 0)
        )
        
        container.id = data.get("id", str(uuid.uuid4()))
        
        if "security_context" in data and data["security_context"]:
            context_data = data["security_context"]
            container.security_context = SecurityContext(
                user=context_data.get("user", "container"),
                role=context_data.get("role", "container_r"),
                type=context_data.get("type", "container_t"),
                level=context_data.get("level", "")
            )
        
        if "resources" in data and data["resources"]:
            container.resources = ContainerResources.from_dict(data["resources"])
        
        if "network_policy" in data and data["network_policy"]:
            container.network_policy = NetworkPolicy.from_dict(data["network_policy"])
        
        if "mounts" in data:
            container.mounts = [MountPoint.from_dict(mount_data) for mount_data in data["mounts"]]
        
        container.created_at = data.get("created_at", time.time())
        container.status = data.get("status", "created")
        container.processes = data.get("processes", [])
        container.root_path = data.get("root_path")
        
        return container


class ContainerManager:
    """Manager for container operations"""
    
    @classmethod
    def create_container(cls, 
                         name: str,
                         user_id: int = None,
                         security_context: SecurityContext = None,
                         resources: ContainerResources = None,
                         network_policy: NetworkPolicy = None,
                         mounts: List[MountPoint] = None) -> Tuple[bool, Union[Container, str]]:
        """
        Create a new container
        
        Args:
            name: Container name
            user_id: User ID
            security_context: Security context
            resources: Resource limits
            network_policy: Network policy
            mounts: Mount points
        
        Returns:
            (success, container or error message)
        """
        with _container_lock:
            # Check if container with this name already exists
            for container in _containers.values():
                if container.name == name:
                    return False, f"Container with name '{name}' already exists"
            
            # Use current user if not specified
            if user_id is None:
                # In a real implementation, this would use the current user ID
                # For now, just use a default value
                user_id = 1000
            
            # Create container
            container = Container(
                name=name,
                user_id=user_id,
                security_context=security_context,
                resources=resources,
                network_policy=network_policy,
                mounts=mounts
            )
            
            # Set up container filesystem
            try:
                # Create container root directory
                container_dir = os.path.join(os.path.expanduser('~'), '.kos', 'containers', container.id)
                os.makedirs(container_dir, exist_ok=True)
                
                # Create basic directory structure
                for subdir in ['bin', 'etc', 'home', 'tmp', 'var']:
                    os.makedirs(os.path.join(container_dir, subdir), exist_ok=True)
                
                container.root_path = container_dir
            except Exception as e:
                logger.error(f"Error setting up container filesystem: {e}")
                return False, str(e)
            
            # Register container
            _containers[container.id] = container
            
            logger.info(f"Container '{name}' created with ID {container.id}")
            
            return True, container
    
    @classmethod
    def delete_container(cls, container_id: str) -> Tuple[bool, str]:
        """
        Delete a container
        
        Args:
            container_id: Container ID
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is running
            if container.status == "running":
                return False, f"Container {container_id} is still running"
            
            # Clean up container filesystem
            try:
                if container.root_path and os.path.exists(container.root_path):
                    shutil.rmtree(container.root_path)
            except Exception as e:
                logger.error(f"Error cleaning up container filesystem: {e}")
            
            # Remove container from registry
            del _containers[container_id]
            
            logger.info(f"Container '{container.name}' ({container_id}) deleted")
            
            return True, f"Container {container_id} deleted"
    
    @classmethod
    def start_container(cls, container_id: str) -> Tuple[bool, str]:
        """
        Start a container
        
        Args:
            container_id: Container ID
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is already running
            if container.status == "running":
                return True, f"Container {container_id} is already running"
            
            # Start container
            container.status = "running"
            
            # Set up mounts
            for mount in container.mounts:
                host_path = mount.host_path
                container_path = os.path.join(container.root_path, mount.container_path.lstrip('/'))
                
                # Create target directory if it doesn't exist
                os.makedirs(os.path.dirname(container_path), exist_ok=True)
                
                # Create symlink
                if os.path.exists(host_path):
                    os.symlink(host_path, container_path)
            
            logger.info(f"Container '{container.name}' ({container_id}) started")
            
            return True, f"Container {container_id} started"
    
    @classmethod
    def stop_container(cls, container_id: str) -> Tuple[bool, str]:
        """
        Stop a container
        
        Args:
            container_id: Container ID
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is already stopped
            if container.status == "stopped":
                return True, f"Container {container_id} is already stopped"
            
            # Stop container processes
            # In a real implementation, this would kill all processes in the container
            # For now, just update the status
            container.status = "stopped"
            
            logger.info(f"Container '{container.name}' ({container_id}) stopped")
            
            return True, f"Container {container_id} stopped"
    
    @classmethod
    def pause_container(cls, container_id: str) -> Tuple[bool, str]:
        """
        Pause a container
        
        Args:
            container_id: Container ID
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is running
            if container.status != "running":
                return False, f"Container {container_id} is not running"
            
            # Pause container processes
            # In a real implementation, this would pause all processes in the container
            # For now, just update the status
            container.status = "paused"
            
            logger.info(f"Container '{container.name}' ({container_id}) paused")
            
            return True, f"Container {container_id} paused"
    
    @classmethod
    def resume_container(cls, container_id: str) -> Tuple[bool, str]:
        """
        Resume a paused container
        
        Args:
            container_id: Container ID
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is paused
            if container.status != "paused":
                return False, f"Container {container_id} is not paused"
            
            # Resume container processes
            # In a real implementation, this would resume all processes in the container
            # For now, just update the status
            container.status = "running"
            
            logger.info(f"Container '{container.name}' ({container_id}) resumed")
            
            return True, f"Container {container_id} resumed"
    
    @classmethod
    def execute_in_container(cls, container_id: str, command: str) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """
        Execute a command in a container
        
        Args:
            container_id: Container ID
            command: Command to execute
        
        Returns:
            (success, result dict or error message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is running
            if container.status != "running":
                return False, f"Container {container_id} is not running"
            
            # Check if we're within process limit
            if container.resources.process_count >= container.resources.max_processes:
                return False, "Maximum process limit reached"
            
            # Prepare command environment
            env = os.environ.copy()
            env['CONTAINER_ID'] = container_id
            env['CONTAINER_NAME'] = container.name
            env['CONTAINER_ROOT'] = container.root_path
            
            # In a real implementation, this would use proper containerization
            # Here we just execute the command in a separate process
            try:
                # Update process count
                container.resources.process_count += 1
                
                # Generate a process ID for tracking
                process_id = str(uuid.uuid4())
                
                # Execute command
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=container.root_path
                )
                
                # Add to container processes
                container.processes.append({
                    'id': process_id,
                    'command': command,
                    'pid': process.pid,
                    'start_time': time.time()
                })
                
                # Wait for process to complete
                stdout, stderr = process.communicate()
                
                # Get exit code
                exit_code = process.returncode
                
                # Update process count
                container.resources.process_count -= 1
                
                # Remove from container processes
                container.processes = [p for p in container.processes if p['id'] != process_id]
                
                # Return result
                return True, {
                    'exit_code': exit_code,
                    'stdout': stdout.decode('utf-8', errors='ignore'),
                    'stderr': stderr.decode('utf-8', errors='ignore')
                }
            except Exception as e:
                logger.error(f"Error executing command in container: {e}")
                
                # Update process count
                container.resources.process_count -= 1
                
                return False, str(e)
    
    @classmethod
    def list_containers(cls) -> List[Container]:
        """
        List all containers
        
        Returns:
            List of containers
        """
        with _container_lock:
            return list(_containers.values())
    
    @classmethod
    def get_container(cls, container_id: str) -> Optional[Container]:
        """
        Get container by ID
        
        Args:
            container_id: Container ID
        
        Returns:
            Container or None if not found
        """
        with _container_lock:
            return _containers.get(container_id)
    
    @classmethod
    def get_container_by_name(cls, name: str) -> Optional[Container]:
        """
        Get container by name
        
        Args:
            name: Container name
        
        Returns:
            Container or None if not found
        """
        with _container_lock:
            for container in _containers.values():
                if container.name == name:
                    return container
            return None
    
    @classmethod
    def add_mount(cls, container_id: str, host_path: str, container_path: str, 
                 read_only: bool = False) -> Tuple[bool, str]:
        """
        Add a mount point to a container
        
        Args:
            container_id: Container ID
            host_path: Path on host
            container_path: Path in container
            read_only: Mount as read-only
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is running
            if container.status == "running":
                return False, "Cannot add mount point to running container"
            
            # Check if mount point already exists
            for mount in container.mounts:
                if mount.container_path == container_path:
                    return False, f"Mount point {container_path} already exists"
            
            # Add mount point
            mount = MountPoint(
                host_path=host_path,
                container_path=container_path,
                read_only=read_only
            )
            
            container.mounts.append(mount)
            
            logger.info(f"Mount point added to container '{container.name}': {host_path} -> {container_path}")
            
            return True, "Mount point added"
    
    @classmethod
    def remove_mount(cls, container_id: str, container_path: str) -> Tuple[bool, str]:
        """
        Remove a mount point from a container
        
        Args:
            container_id: Container ID
            container_path: Path in container
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Check if container is running
            if container.status == "running":
                return False, "Cannot remove mount point from running container"
            
            # Find mount point
            for i, mount in enumerate(container.mounts):
                if mount.container_path == container_path:
                    # Remove mount point
                    container.mounts.pop(i)
                    
                    logger.info(f"Mount point removed from container '{container.name}': {container_path}")
                    
                    return True, "Mount point removed"
            
            return False, f"Mount point {container_path} not found"
    
    @classmethod
    def update_resources(cls, container_id: str, resources: ContainerResources) -> Tuple[bool, str]:
        """
        Update container resources
        
        Args:
            container_id: Container ID
            resources: Resource limits
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Update resources
            container.resources = resources
            
            logger.info(f"Resources updated for container '{container.name}'")
            
            return True, "Resources updated"
    
    @classmethod
    def update_network_policy(cls, container_id: str, network_policy: NetworkPolicy) -> Tuple[bool, str]:
        """
        Update container network policy
        
        Args:
            container_id: Container ID
            network_policy: Network policy
        
        Returns:
            (success, message)
        """
        with _container_lock:
            if container_id not in _containers:
                return False, f"Container {container_id} not found"
            
            container = _containers[container_id]
            
            # Update network policy
            container.network_policy = network_policy
            
            logger.info(f"Network policy updated for container '{container.name}'")
            
            return True, "Network policy updated"
    
    @classmethod
    def save_state(cls, state_file: str) -> Tuple[bool, str]:
        """
        Save container state to file
        
        Args:
            state_file: State file path
        
        Returns:
            (success, message)
        """
        with _container_lock:
            try:
                data = {}
                for container_id, container in _containers.items():
                    data[container_id] = container.to_dict()
                
                with open(state_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True, f"Container state saved to {state_file}"
            except Exception as e:
                logger.error(f"Error saving container state: {e}")
                return False, str(e)
    
    @classmethod
    def load_state(cls, state_file: str) -> Tuple[bool, str]:
        """
        Load container state from file
        
        Args:
            state_file: State file path
        
        Returns:
            (success, message)
        """
        with _container_lock:
            try:
                if not os.path.exists(state_file):
                    return False, f"State file {state_file} not found"
                
                with open(state_file, 'r') as f:
                    data = json.load(f)
                
                _containers.clear()
                for container_id, container_data in data.items():
                    _containers[container_id] = Container.from_dict(container_data)
                
                return True, "Container state loaded"
            except Exception as e:
                logger.error(f"Error loading container state: {e}")
                return False, str(e)


def initialize():
    """Initialize container system"""
    logger.info("Initializing container system")
    
    # Create container directory
    container_dir = os.path.join(os.path.expanduser('~'), '.kos', 'containers')
    os.makedirs(container_dir, exist_ok=True)
    
    # Load state if it exists
    state_file = os.path.join(os.path.expanduser('~'), '.kos', 'security', 'containers.json')
    if os.path.exists(state_file):
        ContainerManager.load_state(state_file)
    
    logger.info("Container system initialized")


# Initialize on module load
initialize()

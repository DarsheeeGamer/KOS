"""
KOS Container Implementation
Docker-like container support with namespaces and cgroups
"""

import os
import json
import time
import uuid
import shutil
import tarfile
import threading
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

logger = logging.getLogger('kos.container')


class ContainerState(Enum):
    """Container states"""
    CREATED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    DEAD = auto()


class NamespaceType(Enum):
    """Linux namespace types"""
    PID = "pid"      # Process ID namespace
    NET = "net"      # Network namespace
    MNT = "mnt"      # Mount namespace
    UTS = "uts"      # Hostname namespace
    IPC = "ipc"      # Inter-process communication
    USER = "user"    # User namespace
    CGROUP = "cgroup"  # Control group namespace


@dataclass
class ContainerConfig:
    """Container configuration"""
    image: str
    command: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    working_dir: str = "/"
    hostname: str = ""
    user: str = "root"
    volumes: List[str] = field(default_factory=list)  # host:container:mode
    ports: List[str] = field(default_factory=list)   # host:container/protocol
    networks: List[str] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    restart_policy: str = "no"  # no, always, on-failure, unless-stopped
    resources: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    security_opts: List[str] = field(default_factory=list)
    init: bool = False
    privileged: bool = False
    readonly_rootfs: bool = False
    stdin_open: bool = False
    tty: bool = False


@dataclass
class ContainerRuntime:
    """Container runtime state"""
    pid: int = 0
    start_time: float = 0
    ip_address: str = ""
    gateway: str = ""
    sandbox_key: str = ""
    namespace_paths: Dict[str, str] = field(default_factory=dict)
    cgroup_paths: Dict[str, str] = field(default_factory=dict)
    mounts: List[Dict[str, str]] = field(default_factory=list)
    exit_code: int = 0


class Container:
    """Container instance"""
    
    def __init__(self, id: str, name: str, config: ContainerConfig):
        self.id = id
        self.name = name
        self.config = config
        self.state = ContainerState.CREATED
        self.runtime = ContainerRuntime()
        self.created_at = time.time()
        self.started_at = 0
        self.finished_at = 0
        self._lock = threading.RLock()
        
        # Container paths
        self.base_path = f"/var/lib/kos/containers/{self.id}"
        self.rootfs_path = f"{self.base_path}/rootfs"
        self.config_path = f"{self.base_path}/config.json"
        self.state_path = f"{self.base_path}/state.json"
        self.log_path = f"{self.base_path}/container.log"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert container to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'state': self.state.name,
            'config': {
                'image': self.config.image,
                'command': self.config.command,
                'env': self.config.env,
                'working_dir': self.config.working_dir,
                'hostname': self.config.hostname,
                'user': self.config.user,
                'volumes': self.config.volumes,
                'ports': self.config.ports,
                'networks': self.config.networks,
                'labels': self.config.labels,
                'restart_policy': self.config.restart_policy,
                'resources': self.config.resources,
                'privileged': self.config.privileged
            },
            'runtime': {
                'pid': self.runtime.pid,
                'start_time': self.runtime.start_time,
                'ip_address': self.runtime.ip_address,
                'gateway': self.runtime.gateway
            },
            'created_at': self.created_at,
            'started_at': self.started_at,
            'finished_at': self.finished_at
        }


class ContainerImage:
    """Container image"""
    
    def __init__(self, name: str, tag: str = "latest"):
        self.name = name
        self.tag = tag
        self.id = str(uuid.uuid4())
        self.created = time.time()
        self.size = 0
        self.layers = []
        self.config = {}
        self.manifest = {}
        
    @property
    def full_name(self) -> str:
        """Get full image name with tag"""
        return f"{self.name}:{self.tag}"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert image to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'tag': self.tag,
            'created': self.created,
            'size': self.size,
            'layers': self.layers,
            'config': self.config
        }


class ContainerNamespace:
    """Container namespace management"""
    
    def __init__(self, container_id: str):
        self.container_id = container_id
        self.namespaces = {}
        self._lock = threading.Lock()
        
    def create_namespace(self, ns_type: NamespaceType) -> str:
        """Create new namespace"""
        with self._lock:
            # In real implementation, would use unshare() system call
            # For simulation, create namespace identifier
            ns_path = f"/proc/{os.getpid()}/ns/{ns_type.value}"
            self.namespaces[ns_type] = ns_path
            
            logger.info(f"Created {ns_type.value} namespace for container {self.container_id}")
            return ns_path
            
    def enter_namespace(self, ns_type: NamespaceType, ns_path: str):
        """Enter existing namespace"""
        # In real implementation, would use setns() system call
        logger.info(f"Entering {ns_type.value} namespace: {ns_path}")
        
    def setup_pid_namespace(self):
        """Setup PID namespace"""
        ns_path = self.create_namespace(NamespaceType.PID)
        # Container's PID 1 will be isolated
        return ns_path
        
    def setup_network_namespace(self) -> Tuple[str, str]:
        """Setup network namespace and return veth pair"""
        ns_path = self.create_namespace(NamespaceType.NET)
        
        # Create virtual ethernet pair
        host_veth = f"veth_{self.container_id[:8]}_h"
        container_veth = f"veth_{self.container_id[:8]}_c"
        
        # In real implementation, would create veth pair
        logger.info(f"Created veth pair: {host_veth} <-> {container_veth}")
        
        return host_veth, container_veth
        
    def setup_mount_namespace(self):
        """Setup mount namespace"""
        ns_path = self.create_namespace(NamespaceType.MNT)
        # Container will have isolated mount points
        return ns_path
        
    def setup_uts_namespace(self, hostname: str):
        """Setup UTS namespace with hostname"""
        ns_path = self.create_namespace(NamespaceType.UTS)
        # Set container hostname
        logger.info(f"Set container hostname: {hostname}")
        return ns_path
        
    def setup_ipc_namespace(self):
        """Setup IPC namespace"""
        ns_path = self.create_namespace(NamespaceType.IPC)
        # Isolate System V IPC and POSIX message queues
        return ns_path
        
    def setup_user_namespace(self, uid_map: str, gid_map: str):
        """Setup user namespace with UID/GID mapping"""
        ns_path = self.create_namespace(NamespaceType.USER)
        # Map container UIDs/GIDs to host
        logger.info(f"Setup user namespace mapping: {uid_map}, {gid_map}")
        return ns_path
        
    def cleanup(self):
        """Cleanup namespaces"""
        # In real implementation, namespaces are cleaned when last process exits
        self.namespaces.clear()


class ContainerCgroup:
    """Container cgroup management"""
    
    def __init__(self, container_id: str):
        self.container_id = container_id
        self.cgroup_root = f"/sys/fs/cgroup"
        self.container_cgroup = f"kos_container_{container_id}"
        self.subsystems = ['cpu', 'memory', 'devices', 'pids', 'blkio', 'net_cls']
        self._paths = {}
        
    def create_cgroups(self) -> Dict[str, str]:
        """Create cgroups for container"""
        for subsystem in self.subsystems:
            path = f"{self.cgroup_root}/{subsystem}/{self.container_cgroup}"
            self._paths[subsystem] = path
            
            # In real implementation, would create cgroup directory
            logger.info(f"Created cgroup: {path}")
            
        return self._paths
        
    def set_cpu_limit(self, cpu_shares: int = 1024, cpu_quota: int = -1):
        """Set CPU limits"""
        # cpu.shares: relative weight (default 1024)
        # cpu.cfs_quota_us: microseconds per period (-1 = unlimited)
        logger.info(f"Set CPU limits: shares={cpu_shares}, quota={cpu_quota}")
        
    def set_memory_limit(self, memory_limit: int, swap_limit: int = -1):
        """Set memory limits in bytes"""
        # memory.limit_in_bytes: memory limit
        # memory.memsw.limit_in_bytes: memory + swap limit
        logger.info(f"Set memory limit: {memory_limit} bytes")
        
    def set_device_access(self, allow_list: List[str]):
        """Set device access permissions"""
        # devices.allow/deny: device access control
        # Format: "type major:minor access"
        # Example: "c 1:3 mr" (char device 1:3, read/mknod)
        for device in allow_list:
            logger.info(f"Allow device: {device}")
            
    def set_pid_limit(self, max_pids: int):
        """Set maximum number of PIDs"""
        # pids.max: maximum number of tasks
        logger.info(f"Set PID limit: {max_pids}")
        
    def set_blkio_weight(self, weight: int = 500):
        """Set block I/O weight (100-1000)"""
        # blkio.weight: relative weight
        logger.info(f"Set block I/O weight: {weight}")
        
    def add_process(self, pid: int):
        """Add process to cgroup"""
        # Write PID to cgroup.procs
        logger.info(f"Added PID {pid} to container cgroup")
        
    def get_stats(self) -> Dict[str, Any]:
        """Get cgroup statistics"""
        stats = {
            'cpu': {
                'usage': 0,
                'system': 0,
                'user': 0
            },
            'memory': {
                'usage': 0,
                'limit': 0,
                'cache': 0
            },
            'pids': {
                'current': 0,
                'limit': 0
            }
        }
        
        # In real implementation, would read from cgroup files
        return stats
        
    def cleanup(self):
        """Remove cgroups"""
        # In real implementation, would remove cgroup directories
        for path in self._paths.values():
            logger.info(f"Removed cgroup: {path}")


class ContainerRuntime:
    """Container runtime engine"""
    
    def __init__(self, kernel):
        self.kernel = kernel
        self.containers: Dict[str, Container] = {}
        self.images: Dict[str, ContainerImage] = {}
        self.networks: Dict[str, Any] = {}
        self._lock = threading.RLock()
        
        # Default networks
        self._create_default_networks()
        
    def _create_default_networks(self):
        """Create default networks"""
        # Bridge network (default)
        self.networks['bridge'] = {
            'name': 'bridge',
            'driver': 'bridge',
            'subnet': '172.17.0.0/16',
            'gateway': '172.17.0.1'
        }
        
        # Host network (use host networking)
        self.networks['host'] = {
            'name': 'host',
            'driver': 'host'
        }
        
        # None network (no networking)
        self.networks['none'] = {
            'name': 'none',
            'driver': 'none'
        }
        
    def create_container(self, name: str, config: ContainerConfig) -> Container:
        """Create new container"""
        with self._lock:
            # Generate container ID
            container_id = str(uuid.uuid4())
            
            # Check if name already exists
            for container in self.containers.values():
                if container.name == name:
                    raise ValueError(f"Container name '{name}' already exists")
                    
            # Create container
            container = Container(container_id, name, config)
            
            # Setup container filesystem
            self._setup_container_filesystem(container)
            
            # Save container
            self.containers[container_id] = container
            self._save_container_state(container)
            
            logger.info(f"Created container {name} ({container_id})")
            return container
            
    def _setup_container_filesystem(self, container: Container):
        """Setup container filesystem"""
        # Create container directories
        os.makedirs(container.rootfs_path, exist_ok=True)
        
        # Extract image layers to rootfs
        if container.config.image in self.images:
            image = self.images[container.config.image]
            self._extract_image(image, container.rootfs_path)
            
        # Setup basic filesystem structure
        for dir in ['proc', 'sys', 'dev', 'tmp', 'etc', 'var']:
            os.makedirs(f"{container.rootfs_path}/{dir}", exist_ok=True)
            
        # Create resolv.conf
        with open(f"{container.rootfs_path}/etc/resolv.conf", 'w') as f:
            f.write("nameserver 8.8.8.8\n")
            
        # Create hostname
        with open(f"{container.rootfs_path}/etc/hostname", 'w') as f:
            f.write(f"{container.config.hostname or container.name}\n")
            
    def _extract_image(self, image: ContainerImage, target_path: str):
        """Extract image layers to target path"""
        # In real implementation, would extract OCI image layers
        logger.info(f"Extracting image {image.full_name} to {target_path}")
        
    def start_container(self, container_id: str) -> bool:
        """Start container"""
        with self._lock:
            container = self.containers.get(container_id)
            if not container:
                return False
                
            if container.state == ContainerState.RUNNING:
                return True
                
            try:
                # Setup namespaces
                namespace = ContainerNamespace(container_id)
                container.runtime.namespace_paths['pid'] = namespace.setup_pid_namespace()
                container.runtime.namespace_paths['mnt'] = namespace.setup_mount_namespace()
                container.runtime.namespace_paths['uts'] = namespace.setup_uts_namespace(
                    container.config.hostname or container.name
                )
                container.runtime.namespace_paths['ipc'] = namespace.setup_ipc_namespace()
                
                # Setup network
                if 'none' not in container.config.networks:
                    host_veth, container_veth = namespace.setup_network_namespace()
                    container.runtime.namespace_paths['net'] = namespace.namespaces[NamespaceType.NET]
                    
                    # Assign IP address
                    container.runtime.ip_address = self._allocate_ip_address()
                    container.runtime.gateway = self.networks['bridge']['gateway']
                    
                # Setup cgroups
                cgroup = ContainerCgroup(container_id)
                container.runtime.cgroup_paths = cgroup.create_cgroups()
                
                # Apply resource limits
                if 'cpu' in container.config.resources:
                    cgroup.set_cpu_limit(
                        container.config.resources['cpu'].get('shares', 1024),
                        container.config.resources['cpu'].get('quota', -1)
                    )
                    
                if 'memory' in container.config.resources:
                    cgroup.set_memory_limit(
                        container.config.resources['memory'].get('limit', 0),
                        container.config.resources['memory'].get('swap', -1)
                    )
                    
                # Create container process
                process = self.kernel.process_manager.create_process(
                    name=f"container-{container.name}",
                    command=container.config.command or ['/bin/sh'],
                    env=container.config.env,
                    cwd=container.config.working_dir,
                    uid=0,  # Root in container
                    gid=0
                )
                
                if process:
                    container.runtime.pid = process.pid
                    container.runtime.start_time = time.time()
                    container.state = ContainerState.RUNNING
                    container.started_at = time.time()
                    
                    # Add process to cgroup
                    cgroup.add_process(process.pid)
                    
                    # Mount container filesystem
                    self._setup_mounts(container)
                    
                    # Change root to container rootfs
                    self._chroot_container(container)
                    
                    self._save_container_state(container)
                    logger.info(f"Started container {container.name}")
                    return True
                    
            except Exception as e:
                logger.error(f"Failed to start container: {e}")
                container.state = ContainerState.DEAD
                
        return False
        
    def _allocate_ip_address(self) -> str:
        """Allocate IP address from bridge network"""
        # Simple IP allocation (in real implementation, would use IPAM)
        base_ip = "172.17.0."
        for i in range(2, 255):
            ip = f"{base_ip}{i}"
            # Check if IP is already allocated
            allocated = False
            for container in self.containers.values():
                if container.runtime.ip_address == ip:
                    allocated = True
                    break
            if not allocated:
                return ip
        raise RuntimeError("No IP addresses available")
        
    def _setup_mounts(self, container: Container):
        """Setup container mounts"""
        mounts = [
            {'source': 'proc', 'target': '/proc', 'type': 'proc', 'options': 'nosuid,noexec,nodev'},
            {'source': 'sysfs', 'target': '/sys', 'type': 'sysfs', 'options': 'nosuid,noexec,nodev,ro'},
            {'source': 'tmpfs', 'target': '/dev', 'type': 'tmpfs', 'options': 'nosuid,strictatime,mode=755'},
            {'source': 'devpts', 'target': '/dev/pts', 'type': 'devpts', 'options': 'nosuid,noexec,mode=600'},
            {'source': 'tmpfs', 'target': '/dev/shm', 'type': 'tmpfs', 'options': 'nosuid,nodev,noexec'},
        ]
        
        # Add volume mounts
        for volume in container.config.volumes:
            parts = volume.split(':')
            if len(parts) >= 2:
                host_path = parts[0]
                container_path = parts[1]
                mode = parts[2] if len(parts) > 2 else 'rw'
                
                mounts.append({
                    'source': host_path,
                    'target': container_path,
                    'type': 'bind',
                    'options': mode
                })
                
        container.runtime.mounts = mounts
        
        # In real implementation, would perform actual mounts
        for mount in mounts:
            logger.info(f"Mount {mount['source']} -> {mount['target']} ({mount['type']})")
            
    def _chroot_container(self, container: Container):
        """Change root to container filesystem"""
        # In real implementation, would use pivot_root or chroot
        logger.info(f"Changed root to {container.rootfs_path}")
        
    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """Stop container"""
        with self._lock:
            container = self.containers.get(container_id)
            if not container:
                return False
                
            if container.state != ContainerState.RUNNING:
                return True
                
            try:
                # Send SIGTERM to container process
                if container.runtime.pid:
                    self.kernel.process_manager.send_signal(
                        container.runtime.pid, 
                        15  # SIGTERM
                    )
                    
                    # Wait for graceful shutdown
                    start_time = time.time()
                    while time.time() - start_time < timeout:
                        process = self.kernel.process_manager.get_process(container.runtime.pid)
                        if not process:
                            break
                        time.sleep(0.1)
                    else:
                        # Force kill if still running
                        self.kernel.process_manager.kill_process(
                            container.runtime.pid,
                            9  # SIGKILL
                        )
                        
                # Cleanup namespaces and cgroups
                namespace = ContainerNamespace(container_id)
                namespace.cleanup()
                
                cgroup = ContainerCgroup(container_id)
                cgroup.cleanup()
                
                # Update container state
                container.state = ContainerState.STOPPED
                container.finished_at = time.time()
                container.runtime.exit_code = 0
                
                self._save_container_state(container)
                logger.info(f"Stopped container {container.name}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to stop container: {e}")
                
        return False
        
    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """Remove container"""
        with self._lock:
            container = self.containers.get(container_id)
            if not container:
                return False
                
            # Stop running container if force
            if container.state == ContainerState.RUNNING:
                if force:
                    self.stop_container(container_id)
                else:
                    raise ValueError("Cannot remove running container")
                    
            # Remove container filesystem
            if os.path.exists(container.base_path):
                shutil.rmtree(container.base_path)
                
            # Remove from containers
            del self.containers[container_id]
            
            logger.info(f"Removed container {container.name}")
            return True
            
    def list_containers(self, all: bool = False) -> List[Container]:
        """List containers"""
        with self._lock:
            containers = list(self.containers.values())
            
            if not all:
                # Filter only running containers
                containers = [c for c in containers if c.state == ContainerState.RUNNING]
                
            return containers
            
    def get_container(self, container_id: str) -> Optional[Container]:
        """Get container by ID"""
        return self.containers.get(container_id)
        
    def exec_in_container(self, container_id: str, command: List[str]) -> int:
        """Execute command in running container"""
        with self._lock:
            container = self.containers.get(container_id)
            if not container or container.state != ContainerState.RUNNING:
                return -1
                
            # Create new process in container namespaces
            process = self.kernel.process_manager.create_process(
                name=f"exec-{container.name}",
                command=command,
                env=container.config.env,
                cwd=container.config.working_dir,
                uid=0,
                gid=0
            )
            
            if process:
                # Enter container namespaces
                # In real implementation, would use setns()
                logger.info(f"Executing {' '.join(command)} in container {container.name}")
                
                # Wait for process to complete
                # Return exit code
                return 0
                
        return -1
        
    def _save_container_state(self, container: Container):
        """Save container state to disk"""
        state = container.to_dict()
        
        # Save to state file
        os.makedirs(os.path.dirname(container.state_path), exist_ok=True)
        with open(container.state_path, 'w') as f:
            json.dump(state, f, indent=2)
            
    def pull_image(self, image_name: str) -> ContainerImage:
        """Pull container image"""
        # Parse image name
        parts = image_name.split(':')
        name = parts[0]
        tag = parts[1] if len(parts) > 1 else 'latest'
        
        # Check if already exists
        full_name = f"{name}:{tag}"
        if full_name in self.images:
            return self.images[full_name]
            
        # Create new image (in real implementation, would download from registry)
        image = ContainerImage(name, tag)
        image.size = 100 * 1024 * 1024  # 100MB dummy size
        
        # Add some dummy layers
        image.layers = [
            {'digest': 'sha256:' + str(uuid.uuid4()).replace('-', ''), 'size': 50000000},
            {'digest': 'sha256:' + str(uuid.uuid4()).replace('-', ''), 'size': 30000000},
            {'digest': 'sha256:' + str(uuid.uuid4()).replace('-', ''), 'size': 20000000}
        ]
        
        # Set image config
        image.config = {
            'Env': ['PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'],
            'Cmd': ['/bin/sh'],
            'WorkingDir': '/',
            'User': 'root'
        }
        
        self.images[full_name] = image
        logger.info(f"Pulled image {full_name}")
        return image
        
    def list_images(self) -> List[ContainerImage]:
        """List available images"""
        return list(self.images.values())
        
    def remove_image(self, image_name: str) -> bool:
        """Remove image"""
        if image_name in self.images:
            # Check if any container is using this image
            for container in self.containers.values():
                if container.config.image == image_name:
                    raise ValueError(f"Image {image_name} is in use by container {container.name}")
                    
            del self.images[image_name]
            logger.info(f"Removed image {image_name}")
            return True
            
        return False


# Global container runtime instance
_container_runtime = None

def get_container_runtime(kernel) -> ContainerRuntime:
    """Get global container runtime"""
    global _container_runtime
    if _container_runtime is None:
        _container_runtime = ContainerRuntime(kernel)
    return _container_runtime
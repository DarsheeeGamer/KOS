"""
KOS Container Management System

Provides comprehensive container management capabilities:
- Container lifecycle management (create, start, stop, remove)
- Image management (pull, build, list, remove)
- Resource isolation and limits
- Container networking
- Integration with KOS services, IPC, and monitoring
"""

import logging
import os
import threading
import time
import json
import signal
import shutil
import uuid
import subprocess
from typing import Dict, List, Any, Optional, Tuple, Set

# Import container subsystems
from .container import Container, ContainerState, ContainerConfig
from .image import Image, ImageManager
from .network import ContainerNetwork
from .storage import StorageManager
from .runtime import ContainerRuntime

# Initialize logging
logger = logging.getLogger('KOS.container')

# Base directory for container data
CONTAINER_DIR = '/tmp/kos/containers'
os.makedirs(CONTAINER_DIR, exist_ok=True)

# Configuration files
CONTAINERS_CONFIG = os.path.join(CONTAINER_DIR, 'containers.json')
IMAGES_CONFIG = os.path.join(CONTAINER_DIR, 'images.json')
NETWORKS_CONFIG = os.path.join(CONTAINER_DIR, 'networks.json')

# Global state
_lock = threading.RLock()
_initialized = False
_container_thread = None
_stop_event = threading.Event()

# Component managers
_image_manager = None
_storage_manager = None
_network_manager = None
_runtime = None

# Container registry
_containers = {}  # name -> Container
_images = {}      # name -> Image
_networks = {}    # name -> ContainerNetwork

def initialize():
    """Initialize the container subsystem"""
    global _initialized, _container_thread, _image_manager, _storage_manager, _network_manager, _runtime
    
    if _initialized:
        logger.warning("Container subsystem already initialized")
        return True
    
    logger.info("Initializing KOS container subsystem")
    
    # Create container directories
    os.makedirs(os.path.join(CONTAINER_DIR, 'images'), exist_ok=True)
    os.makedirs(os.path.join(CONTAINER_DIR, 'containers'), exist_ok=True)
    os.makedirs(os.path.join(CONTAINER_DIR, 'volumes'), exist_ok=True)
    os.makedirs(os.path.join(CONTAINER_DIR, 'networks'), exist_ok=True)
    
    # Initialize component managers
    _image_manager = ImageManager(os.path.join(CONTAINER_DIR, 'images'))
    _storage_manager = StorageManager(os.path.join(CONTAINER_DIR, 'volumes'))
    _network_manager = ContainerNetwork(os.path.join(CONTAINER_DIR, 'networks'))
    _runtime = ContainerRuntime()
    
    # Load configurations
    _load_containers()
    _load_images()
    _load_networks()
    
    # Start container management thread
    _stop_event.clear()
    _container_thread = threading.Thread(
        target=_container_loop,
        daemon=True,
        name="KOSContainerThread"
    )
    _container_thread.start()
    
    # Register with service management if available
    try:
        from ..service import register_service_type
        register_service_type('container', {
            'start': start_container,
            'stop': stop_container,
            'restart': restart_container,
            'get_status': get_container_status
        })
        logger.info("Registered container service type with service manager")
    except ImportError:
        logger.warning("Service module not available, container service type not registered")
    
    # Register with network management if available
    try:
        from ..network import register_network_plugin
        register_network_plugin('container', {
            'create_interface': _network_manager.create_interface,
            'delete_interface': _network_manager.delete_interface,
            'get_interfaces': _network_manager.get_interfaces
        })
        logger.info("Registered container network plugin with network manager")
    except ImportError:
        logger.warning("Network module not available, container network plugin not registered")
    
    # Register with monitoring if available
    try:
        from ..monitor import register_monitor_plugin
        register_monitor_plugin('container', {
            'get_metrics': get_container_metrics,
            'list_containers': list_containers
        })
        logger.info("Registered container monitoring plugin with monitor manager")
    except ImportError:
        logger.warning("Monitor module not available, container monitoring plugin not registered")
    
    _initialized = True
    return True

def shutdown():
    """Shutdown the container subsystem"""
    global _initialized, _container_thread
    
    if not _initialized:
        logger.warning("Container subsystem not initialized")
        return True
    
    logger.info("Shutting down KOS container subsystem")
    
    # Stop container thread
    _stop_event.set()
    if _container_thread:
        _container_thread.join(timeout=10.0)
    
    # Stop all running containers
    for container in list(_containers.values()):
        if container.state == ContainerState.RUNNING:
            stop_container(container.name)
    
    # Save configurations
    _save_containers()
    _save_images()
    _save_networks()
    
    _initialized = False
    return True

def _container_loop():
    """Main container management loop"""
    logger.info("Container management loop started")
    
    while not _stop_event.is_set():
        try:
            # Update container states
            _update_container_states()
            
            # Check container health
            _check_container_health()
            
            # Handle auto-restart policies
            _handle_container_restarts()
            
            # Sleep until next iteration
            _stop_event.wait(5.0)  # Check every 5 seconds
        
        except Exception as e:
            logger.error(f"Error in container loop: {e}")
            time.sleep(5.0)
    
    logger.info("Container management loop stopped")

def _update_container_states():
    """Update the state of all containers"""
    with _lock:
        for name, container in list(_containers.items()):
            # Update container state from runtime
            if container.state == ContainerState.RUNNING:
                if not _runtime.is_running(container):
                    # Container exited
                    container.state = ContainerState.EXITED
                    container.exit_code = _runtime.get_exit_code(container)
                    container.exit_time = time.time()
                    logger.info(f"Container {name} exited with code {container.exit_code}")
                    
                    # Update container metrics one last time
                    container.update_metrics()
            
            # Update metrics for running containers
            if container.state == ContainerState.RUNNING:
                container.update_metrics()

def _check_container_health():
    """Check health status for containers with health checks"""
    with _lock:
        for name, container in list(_containers.items()):
            if container.state == ContainerState.RUNNING and container.health_check:
                # Run health check
                healthy = _runtime.run_health_check(container)
                
                # Update health status
                container.healthy = healthy
                
                if not healthy and container.health_status == 'healthy':
                    logger.warning(f"Container {name} health check failed")
                    container.health_status = 'unhealthy'
                    container.unhealthy_count += 1
                elif healthy and container.health_status == 'unhealthy':
                    logger.info(f"Container {name} health check recovered")
                    container.health_status = 'healthy'
                    container.unhealthy_count = 0

def _handle_container_restarts():
    """Handle auto-restart policies for containers"""
    with _lock:
        for name, container in list(_containers.items()):
            if container.state == ContainerState.EXITED and container.restart_policy != 'no':
                # Check restart policy
                should_restart = False
                
                if container.restart_policy == 'always':
                    should_restart = True
                elif container.restart_policy == 'on-failure' and container.exit_code != 0:
                    should_restart = True
                elif container.restart_policy == 'unless-stopped':
                    should_restart = not container.manually_stopped
                
                if should_restart:
                    # Check max restart count
                    if container.restart_count >= container.max_restart_count:
                        logger.warning(f"Container {name} reached max restart count ({container.max_restart_count})")
                        continue
                    
                    # Restart the container
                    logger.info(f"Auto-restarting container {name} (policy: {container.restart_policy})")
                    restart_container(name)

def _load_containers():
    """Load container configuration"""
    with _lock:
        if os.path.exists(CONTAINERS_CONFIG):
            try:
                with open(CONTAINERS_CONFIG, 'r') as f:
                    container_configs = json.load(f)
                
                for name, config in container_configs.items():
                    container = Container(name, config)
                    _containers[name] = container
                
                logger.info(f"Loaded {len(_containers)} container configurations")
            
            except Exception as e:
                logger.error(f"Error loading container configuration: {e}")

def _save_containers():
    """Save container configuration"""
    with _lock:
        try:
            container_configs = {}
            for name, container in _containers.items():
                container_configs[name] = container.to_dict()
            
            with open(CONTAINERS_CONFIG, 'w') as f:
                json.dump(container_configs, f, indent=2)
            
            logger.info(f"Saved {len(_containers)} container configurations")
        
        except Exception as e:
            logger.error(f"Error saving container configuration: {e}")

def _load_images():
    """Load image configuration"""
    with _lock:
        _image_manager.load_images()

def _save_images():
    """Save image configuration"""
    with _lock:
        _image_manager.save_images()

def _load_networks():
    """Load network configuration"""
    with _lock:
        _network_manager.load_networks()

def _save_networks():
    """Save network configuration"""
    with _lock:
        _network_manager.save_networks()

# ============================================================================
# Public API for container management
# ============================================================================

def create_container(name, image, command=None, **kwargs):
    """
    Create a new container
    
    Args:
        name: Container name
        image: Image name or ID
        command: Command to run
        **kwargs: Additional configuration options
    """
    with _lock:
        if name in _containers:
            logger.warning(f"Container {name} already exists")
            return False
        
        # Get the image
        img = _image_manager.get_image(image)
        if not img:
            logger.error(f"Image {image} not found")
            return False
        
        # Create container configuration
        config = ContainerConfig(
            image=image,
            command=command or img.default_command,
            entrypoint=kwargs.get('entrypoint', img.default_entrypoint),
            env=kwargs.get('env', {}),
            volumes=kwargs.get('volumes', []),
            ports=kwargs.get('ports', []),
            network=kwargs.get('network', 'bridge'),
            restart_policy=kwargs.get('restart_policy', 'no'),
            max_restart_count=kwargs.get('max_restart_count', 3),
            health_check=kwargs.get('health_check'),
            resource_limits=kwargs.get('resource_limits', {})
        )
        
        # Create the container
        container = Container(name, config)
        
        # Set up container filesystem
        if not _storage_manager.prepare_container_fs(container, img):
            logger.error(f"Failed to prepare filesystem for container {name}")
            return False
        
        # Save the container
        _containers[name] = container
        _save_containers()
        
        logger.info(f"Created container: {name} (image: {image})")
        return True

def start_container(name):
    """Start a container"""
    with _lock:
        if name not in _containers:
            logger.warning(f"Container {name} does not exist")
            return False
        
        container = _containers[name]
        
        if container.state == ContainerState.RUNNING:
            logger.warning(f"Container {name} is already running")
            return True
        
        # Set up networking
        if not _network_manager.setup_container_network(container):
            logger.error(f"Failed to set up networking for container {name}")
            return False
        
        # Start the container
        if not _runtime.start_container(container):
            logger.error(f"Failed to start container {name}")
            return False
        
        # Update container state
        container.state = ContainerState.RUNNING
        container.manually_stopped = False
        container.start_time = time.time()
        container.restart_count += 1
        _save_containers()
        
        logger.info(f"Started container: {name}")
        
        # Register container with service discovery if available
        try:
            from ..network import register_network_service
            
            for port_mapping in container.ports:
                register_network_service(
                    f"container-{name}-{port_mapping['container_port']}",
                    port_mapping['host_port'],
                    port_mapping['protocol'],
                    f"Container {name} service on port {port_mapping['container_port']}"
                )
        except ImportError:
            pass
        
        return True

def stop_container(name, timeout=10):
    """Stop a container"""
    with _lock:
        if name not in _containers:
            logger.warning(f"Container {name} does not exist")
            return False
        
        container = _containers[name]
        
        if container.state != ContainerState.RUNNING:
            logger.warning(f"Container {name} is not running")
            return True
        
        # Unregister container from service discovery
        try:
            from ..network import unregister_network_service
            
            for port_mapping in container.ports:
                unregister_network_service(
                    f"container-{name}-{port_mapping['container_port']}"
                )
        except ImportError:
            pass
        
        # Stop the container
        if not _runtime.stop_container(container, timeout):
            logger.error(f"Failed to stop container {name}")
            return False
        
        # Update container state
        container.state = ContainerState.EXITED
        container.manually_stopped = True
        container.exit_time = time.time()
        _save_containers()
        
        # Clean up networking
        _network_manager.cleanup_container_network(container)
        
        logger.info(f"Stopped container: {name}")
        return True

def restart_container(name, timeout=10):
    """Restart a container"""
    with _lock:
        if name not in _containers:
            logger.warning(f"Container {name} does not exist")
            return False
        
        # Stop the container
        if not stop_container(name, timeout):
            logger.error(f"Failed to stop container {name} for restart")
            return False
        
        # Start the container
        if not start_container(name):
            logger.error(f"Failed to start container {name} for restart")
            return False
        
        logger.info(f"Restarted container: {name}")
        return True

def remove_container(name, force=False):
    """Remove a container"""
    with _lock:
        if name not in _containers:
            logger.warning(f"Container {name} does not exist")
            return False
        
        container = _containers[name]
        
        # Stop the container if it's running
        if container.state == ContainerState.RUNNING:
            if not force:
                logger.warning(f"Container {name} is running, use force=True to remove")
                return False
            
            if not stop_container(name):
                logger.error(f"Failed to stop container {name} for removal")
                return False
        
        # Clean up container filesystem
        if not _storage_manager.cleanup_container_fs(container):
            logger.error(f"Failed to clean up filesystem for container {name}")
            return False
        
        # Remove the container
        del _containers[name]
        _save_containers()
        
        logger.info(f"Removed container: {name}")
        return True

def list_containers():
    """List all containers"""
    with _lock:
        return list(_containers.values())

def get_container(name):
    """Get container by name"""
    with _lock:
        return _containers.get(name)

def get_container_status(name):
    """Get container status"""
    with _lock:
        container = _containers.get(name)
        if not container:
            return None
        
        return {
            'name': container.name,
            'image': container.image,
            'state': container.state,
            'running': container.state == ContainerState.RUNNING,
            'exit_code': container.exit_code,
            'pid': container.pid,
            'ip_address': container.ip_address,
            'ports': container.ports,
            'created': container.created,
            'started': container.start_time,
            'exited': container.exit_time,
            'restart_count': container.restart_count,
            'health_status': container.health_status,
            'memory_usage': container.metrics.get('memory_usage'),
            'cpu_usage': container.metrics.get('cpu_usage')
        }

def get_container_logs(name, tail=None):
    """Get container logs"""
    with _lock:
        container = _containers.get(name)
        if not container:
            return None
        
        return _runtime.get_container_logs(container, tail)

def get_container_metrics(name=None):
    """Get container metrics"""
    with _lock:
        if name:
            container = _containers.get(name)
            if not container:
                return None
            
            return container.metrics
        
        # Get metrics for all containers
        metrics = {}
        for name, container in _containers.items():
            metrics[name] = container.metrics
        
        return metrics

def pull_image(image_name, tag='latest'):
    """Pull an image from a registry"""
    with _lock:
        if _image_manager.pull_image(image_name, tag):
            logger.info(f"Pulled image: {image_name}:{tag}")
            return True
        
        logger.error(f"Failed to pull image: {image_name}:{tag}")
        return False

def build_image(name, path, tag='latest'):
    """Build an image from a Dockerfile"""
    with _lock:
        if _image_manager.build_image(name, path, tag):
            logger.info(f"Built image: {name}:{tag}")
            return True
        
        logger.error(f"Failed to build image: {name}:{tag}")
        return False

def list_images():
    """List all images"""
    with _lock:
        return _image_manager.list_images()

def remove_image(name, force=False):
    """Remove an image"""
    with _lock:
        if _image_manager.remove_image(name, force):
            logger.info(f"Removed image: {name}")
            return True
        
        logger.error(f"Failed to remove image: {name}")
        return False

def create_network(name, subnet=None, gateway=None):
    """Create a container network"""
    with _lock:
        if _network_manager.create_network(name, subnet, gateway):
            logger.info(f"Created network: {name}")
            return True
        
        logger.error(f"Failed to create network: {name}")
        return False

def remove_network(name):
    """Remove a container network"""
    with _lock:
        if _network_manager.remove_network(name):
            logger.info(f"Removed network: {name}")
            return True
        
        logger.error(f"Failed to remove network: {name}")
        return False

def list_networks():
    """List all container networks"""
    with _lock:
        return _network_manager.list_networks()

def create_volume(name, path=None):
    """Create a container volume"""
    with _lock:
        if _storage_manager.create_volume(name, path):
            logger.info(f"Created volume: {name}")
            return True
        
        logger.error(f"Failed to create volume: {name}")
        return False

def remove_volume(name, force=False):
    """Remove a container volume"""
    with _lock:
        if _storage_manager.remove_volume(name, force):
            logger.info(f"Removed volume: {name}")
            return True
        
        logger.error(f"Failed to remove volume: {name}")
        return False

def list_volumes():
    """List all container volumes"""
    with _lock:
        return _storage_manager.list_volumes()

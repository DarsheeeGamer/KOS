"""
KOS Container Runtime

Provides the core container runtime capabilities:
- Container process management
- Resource isolation and limits
- Container lifecycle operations
"""

import os
import time
import json
import signal
import subprocess
import logging
import shutil
import threading
import pwd
import grp
from typing import Dict, List, Any, Optional, Tuple

# Initialize logging
logger = logging.getLogger('KOS.container.runtime')

class ContainerRuntime:
    """
    Container runtime for managing container processes
    """
    def __init__(self):
        """Initialize the container runtime"""
        self.running_containers = {}  # container_id -> process info
        self._lock = threading.RLock()
    
    def start_container(self, container) -> bool:
        """
        Start a container
        
        Args:
            container: Container object
        """
        try:
            with self._lock:
                if container.id in self.running_containers:
                    logger.warning(f"Container {container.name} is already running")
                    return True
                
                # Ensure rootfs exists
                if not container.rootfs or not os.path.exists(container.rootfs):
                    logger.error(f"Rootfs for container {container.name} does not exist")
                    return False
                
                # In a real implementation, this would:
                # 1. Create namespaces (user, pid, net, mount, ipc, uts)
                # 2. Set up cgroups for resource limits
                # 3. Mount proc, sys, dev filesystems
                # 4. Set up networking
                # 5. Execute the container command in the new namespaces
                
                # For this implementation, we'll execute the command directly and track the process
                
                # Create command line
                cmd = []
                
                # Add entrypoint if specified
                if container.entrypoint:
                    cmd.extend(container.entrypoint)
                
                # Add command if specified
                if container.command:
                    cmd.extend(container.command)
                
                # If neither entrypoint nor command is specified, use a default
                if not cmd:
                    cmd = ['/bin/sh', '-c', 'echo "KOS Container"; tail -f /dev/null']
                
                # Set up environment variables
                env = os.environ.copy()
                
                # Add container-specific environment variables
                for key, value in container.env.items():
                    env[key] = value
                
                # Add standard container variables
                env['HOSTNAME'] = container.name
                env['HOME'] = '/root'
                env['PATH'] = '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'
                env['TERM'] = 'xterm'
                
                # Open log files
                if container.log_path:
                    stdout_log = open(os.path.join(container.log_path, 'stdout.log'), 'w')
                    stderr_log = open(os.path.join(container.log_path, 'stderr.log'), 'w')
                else:
                    stdout_log = subprocess.PIPE
                    stderr_log = subprocess.PIPE
                
                # Start the process
                logger.info(f"Starting container {container.name} with command: {cmd}")
                
                process = subprocess.Popen(
                    cmd,
                    cwd=container.rootfs,
                    env=env,
                    stdout=stdout_log,
                    stderr=stderr_log,
                    # In a real implementation, we would use chroot, namespaces, etc.
                    # For now, we'll just run in the host namespace
                    preexec_fn=lambda: self._setup_container_process(container)
                )
                
                # Store process information
                self.running_containers[container.id] = {
                    'process': process,
                    'pid': process.pid,
                    'start_time': time.time(),
                    'stdout_log': stdout_log if stdout_log != subprocess.PIPE else None,
                    'stderr_log': stderr_log if stderr_log != subprocess.PIPE else None
                }
                
                # Update container information
                container.pid = process.pid
                container.state = 'running'
                
                logger.info(f"Container {container.name} started with PID {process.pid}")
                return True
        
        except Exception as e:
            logger.error(f"Error starting container {container.name}: {e}")
            return False
    
    def _setup_container_process(self, container):
        """
        Set up container process environment
        
        This would normally involve namespace setup, chroot, etc.
        For this implementation, we'll just do basic setup.
        
        Args:
            container: Container object
        """
        try:
            # Set process name
            import setproctitle
            setproctitle.setproctitle(f"kos-container: {container.name}")
        except ImportError:
            pass
        
        # Ignore SIGINT so container doesn't exit on Ctrl+C
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        
        # Set resource limits if specified
        if container.resource_limits:
            import resource
            
            # CPU limit
            if 'cpu' in container.resource_limits:
                cpu_limit = float(container.resource_limits['cpu'])
                # Not directly mappable to resource limits, would use cgroups in real implementation
            
            # Memory limit
            if 'memory' in container.resource_limits:
                memory_limit = int(container.resource_limits['memory'])
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            
            # File descriptors limit
            if 'fds' in container.resource_limits:
                fds_limit = int(container.resource_limits['fds'])
                resource.setrlimit(resource.RLIMIT_NOFILE, (fds_limit, fds_limit))
    
    def stop_container(self, container, timeout: int = 10) -> bool:
        """
        Stop a container
        
        Args:
            container: Container object
            timeout: Timeout in seconds before sending SIGKILL
        """
        try:
            with self._lock:
                if container.id not in self.running_containers:
                    logger.warning(f"Container {container.name} is not running")
                    return True
                
                container_info = self.running_containers[container.id]
                process = container_info['process']
                
                # Send SIGTERM
                logger.info(f"Sending SIGTERM to container {container.name} (PID {process.pid})")
                process.terminate()
                
                # Wait for container to exit
                try:
                    process.wait(timeout=timeout)
                    exit_code = process.returncode
                    logger.info(f"Container {container.name} exited with code {exit_code}")
                except subprocess.TimeoutExpired:
                    # Send SIGKILL
                    logger.warning(f"Container {container.name} did not exit, sending SIGKILL")
                    process.kill()
                    process.wait(timeout=5)
                    exit_code = process.returncode
                    logger.info(f"Container {container.name} killed with exit code {exit_code}")
                
                # Close log files
                if container_info['stdout_log']:
                    container_info['stdout_log'].close()
                
                if container_info['stderr_log']:
                    container_info['stderr_log'].close()
                
                # Remove from running containers
                del self.running_containers[container.id]
                
                # Update container information
                container.exit_code = exit_code
                
                return True
        
        except Exception as e:
            logger.error(f"Error stopping container {container.name}: {e}")
            return False
    
    def is_running(self, container) -> bool:
        """
        Check if a container is running
        
        Args:
            container: Container object
        """
        with self._lock:
            if container.id not in self.running_containers:
                return False
            
            # Check if process is still running
            process = self.running_containers[container.id]['process']
            return process.poll() is None
    
    def get_exit_code(self, container) -> Optional[int]:
        """
        Get container exit code
        
        Args:
            container: Container object
        """
        with self._lock:
            if container.id in self.running_containers:
                process = self.running_containers[container.id]['process']
                return process.poll()
            
            return container.exit_code
    
    def get_container_logs(self, container, tail: Optional[int] = None) -> Dict[str, Any]:
        """
        Get container logs
        
        Args:
            container: Container object
            tail: Number of lines to return from the end of the logs
        """
        try:
            if not container.log_path:
                return {'stdout': '', 'stderr': ''}
            
            stdout_log = os.path.join(container.log_path, 'stdout.log')
            stderr_log = os.path.join(container.log_path, 'stderr.log')
            
            stdout = self._read_log_file(stdout_log, tail)
            stderr = self._read_log_file(stderr_log, tail)
            
            return {
                'stdout': stdout,
                'stderr': stderr
            }
        
        except Exception as e:
            logger.error(f"Error getting logs for container {container.name}: {e}")
            return {'stdout': '', 'stderr': f"Error: {e}"}
    
    def _read_log_file(self, path: str, tail: Optional[int] = None) -> str:
        """
        Read a log file, optionally returning only the last N lines
        
        Args:
            path: Path to log file
            tail: Number of lines to return from the end
        """
        if not os.path.exists(path):
            return ''
        
        if tail is None:
            # Read entire file
            with open(path, 'r') as f:
                return f.read()
        else:
            # Read last N lines
            result = []
            with open(path, 'r') as f:
                lines = f.readlines()
                start = max(0, len(lines) - tail)
                result = lines[start:]
            
            return ''.join(result)
    
    def run_health_check(self, container) -> bool:
        """
        Run container health check
        
        Args:
            container: Container object
        """
        if not container.health_check:
            return True
        
        try:
            with self._lock:
                if container.id not in self.running_containers:
                    return False
                
                # Get health check command
                cmd = container.health_check.get('test')
                if not cmd:
                    return True
                
                # If cmd is a list, use it directly; otherwise parse it
                if isinstance(cmd, list):
                    health_cmd = cmd
                else:
                    health_cmd = ['/bin/sh', '-c', cmd]
                
                # Run the health check in the container's context
                # In a real implementation, this would use ns-enter or similar
                # For this implementation, we'll just run in the host namespace
                
                # Prepare environment
                env = os.environ.copy()
                for key, value in container.env.items():
                    env[key] = value
                
                # Run the command
                logger.debug(f"Running health check for container {container.name}: {health_cmd}")
                
                result = subprocess.run(
                    health_cmd,
                    cwd=container.rootfs,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=container.health_check.get('timeout', 30)
                )
                
                # Check the result
                healthy = result.returncode == 0
                
                if healthy:
                    logger.debug(f"Health check for container {container.name} passed")
                else:
                    logger.warning(f"Health check for container {container.name} failed with code {result.returncode}")
                    logger.debug(f"Health check output: {result.stdout.decode('utf-8')}")
                    logger.debug(f"Health check error: {result.stderr.decode('utf-8')}")
                
                return healthy
        
        except Exception as e:
            logger.error(f"Error running health check for container {container.name}: {e}")
            return False
    
    def exec_in_container(self, container, cmd: List[str], interactive: bool = False) -> Dict[str, Any]:
        """
        Execute a command in a running container
        
        Args:
            container: Container object
            cmd: Command to execute
            interactive: Whether the command is interactive
        """
        try:
            with self._lock:
                if container.id not in self.running_containers:
                    return {
                        'success': False,
                        'error': f"Container {container.name} is not running",
                        'stdout': '',
                        'stderr': '',
                        'exit_code': -1
                    }
                
                # In a real implementation, this would use ns-enter or similar
                # For this implementation, we'll just run in the host namespace
                
                # Prepare environment
                env = os.environ.copy()
                for key, value in container.env.items():
                    env[key] = value
                
                # Run the command
                logger.debug(f"Executing command in container {container.name}: {cmd}")
                
                if interactive:
                    # Interactive mode not fully implemented
                    return {
                        'success': False,
                        'error': "Interactive mode not supported",
                        'stdout': '',
                        'stderr': '',
                        'exit_code': -1
                    }
                else:
                    result = subprocess.run(
                        cmd,
                        cwd=container.rootfs,
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=60
                    )
                    
                    return {
                        'success': result.returncode == 0,
                        'error': '',
                        'stdout': result.stdout.decode('utf-8'),
                        'stderr': result.stderr.decode('utf-8'),
                        'exit_code': result.returncode
                    }
        
        except Exception as e:
            logger.error(f"Error executing command in container {container.name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'stdout': '',
                'stderr': f"Error: {e}",
                'exit_code': -1
            }
    
    def get_container_stats(self, container) -> Dict[str, Any]:
        """
        Get container resource usage statistics
        
        Args:
            container: Container object
        """
        try:
            with self._lock:
                if container.id not in self.running_containers:
                    return {}
                
                pid = self.running_containers[container.id]['pid']
                
                # In a real implementation, this would read from cgroups
                # For this implementation, we'll use psutil if available
                
                try:
                    import psutil
                    
                    process = psutil.Process(pid)
                    
                    # Get process and children statistics
                    with process.oneshot():
                        cpu_percent = process.cpu_percent(interval=0.1)
                        memory_info = process.memory_info()
                        io_counters = process.io_counters() if hasattr(process, 'io_counters') else None
                        num_threads = process.num_threads()
                        num_fds = process.num_fds() if hasattr(process, 'num_fds') else None
                        
                        # Get stats from children
                        children = process.children(recursive=True)
                        
                        for child in children:
                            try:
                                with child.oneshot():
                                    cpu_percent += child.cpu_percent(interval=0.1)
                                    
                                    child_memory = child.memory_info()
                                    memory_info.rss += child_memory.rss
                                    memory_info.vms += child_memory.vms
                                    
                                    if hasattr(child, 'io_counters') and io_counters:
                                        child_io = child.io_counters()
                                        io_counters.read_count += child_io.read_count
                                        io_counters.write_count += child_io.write_count
                                        io_counters.read_bytes += child_io.read_bytes
                                        io_counters.write_bytes += child_io.write_bytes
                                    
                                    num_threads += child.num_threads()
                                    
                                    if hasattr(child, 'num_fds'):
                                        num_fds = (num_fds or 0) + child.num_fds()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                continue
                    
                    stats = {
                        'cpu_percent': cpu_percent,
                        'memory': {
                            'rss': memory_info.rss,
                            'vms': memory_info.vms,
                            'percent': process.memory_percent()
                        },
                        'threads': num_threads,
                        'fds': num_fds
                    }
                    
                    if io_counters:
                        stats['io'] = {
                            'read_count': io_counters.read_count,
                            'write_count': io_counters.write_count,
                            'read_bytes': io_counters.read_bytes,
                            'write_bytes': io_counters.write_bytes
                        }
                    
                    return stats
                
                except ImportError:
                    # psutil not available, return minimal stats
                    return {
                        'cpu_percent': 0.0,
                        'memory': {
                            'rss': 0,
                            'vms': 0,
                            'percent': 0.0
                        },
                        'threads': 1,
                        'fds': 3
                    }
        
        except Exception as e:
            logger.error(f"Error getting stats for container {container.name}: {e}")
            return {}

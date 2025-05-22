"""
Advanced system monitoring commands for KOS shell
"""
import os
import time
import logging
import psutil
from typing import Dict, List, Any, Tuple, Optional, Union, Callable
from datetime import datetime

logger = logging.getLogger('KOS.shell.system_monitor')

class SystemMonitor:
    """Advanced system monitoring capabilities using KADVLayer's features"""
    
    @staticmethod
    def get_system_resources() -> Dict[str, Any]:
        """
        Get comprehensive system resource usage data
        
        Returns:
            Dictionary containing CPU, memory, disk, and network information
        """
        try:
            return {
                'cpu': {
                    'percent': psutil.cpu_percent(interval=0.1),
                    'count': psutil.cpu_count(),
                    'freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                    'stats': psutil.cpu_stats()._asdict(),
                    'times': psutil.cpu_times()._asdict()
                },
                'memory': {
                    'virtual': psutil.virtual_memory()._asdict(),
                    'swap': psutil.swap_memory()._asdict()
                },
                'disk': {
                    'usage': psutil.disk_usage('/')._asdict(),
                    'io': psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else None,
                    'partitions': [p._asdict() for p in psutil.disk_partitions()]
                },
                'network': {
                    'io': psutil.net_io_counters()._asdict() if psutil.net_io_counters() else None,
                    'connections': len(psutil.net_connections()),
                    'stats': [s._asdict() for s in psutil.net_if_stats().values()]
                },
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system resources: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def monitor_resource(resource_type: str, interval: int = 1, duration: int = 10, callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """
        Monitor a specific system resource over time
        
        Args:
            resource_type: Type of resource to monitor ('cpu', 'memory', 'disk', 'network')
            interval: Sampling interval in seconds
            duration: Total monitoring duration in seconds
            callback: Optional callback function to receive each sample
            
        Returns:
            List of resource samples
        """
        samples = []
        iterations = max(1, int(duration / interval))
        
        try:
            for _ in range(iterations):
                resources = SystemMonitor.get_system_resources()
                
                if resource_type in resources:
                    sample = {
                        'timestamp': resources['timestamp'],
                        'data': resources[resource_type]
                    }
                    samples.append(sample)
                    
                    if callback:
                        callback(sample)
                
                if _ < iterations - 1:  # Don't sleep after the last iteration
                    time.sleep(interval)
                    
            return samples
        except Exception as e:
            logger.error(f"Error monitoring {resource_type}: {e}")
            return [{'error': str(e)}]
    
    @staticmethod
    def get_process_info(pid: Optional[int] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get information about a specific process or all processes
        
        Args:
            pid: Process ID to get info for, or None for all processes
            
        Returns:
            Process information dictionary or list of dictionaries
        """
        try:
            if pid is not None:
                process = psutil.Process(pid)
                return {
                    'pid': process.pid,
                    'name': process.name(),
                    'status': process.status(),
                    'cpu_percent': process.cpu_percent(interval=0.1),
                    'memory_percent': process.memory_percent(),
                    'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                    'username': process.username(),
                    'cmdline': process.cmdline(),
                    'connections': len(process.connections()),
                    'num_threads': process.num_threads(),
                    'nice': process.nice()
                }
            else:
                processes = []
                for process in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_percent', 'create_time']):
                    try:
                        proc_info = process.info
                        if 'create_time' in proc_info:
                            proc_info['create_time'] = datetime.fromtimestamp(proc_info['create_time']).isoformat()
                        processes.append(proc_info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                return processes
        except Exception as e:
            logger.error(f"Error getting process info: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def get_process_tree() -> Dict[int, List[Dict[str, Any]]]:
        """
        Get hierarchical process tree
        
        Returns:
            Dictionary mapping parent PIDs to lists of child processes
        """
        try:
            # Build process tree
            tree = {}
            processes = SystemMonitor.get_process_info()
            
            if isinstance(processes, list):
                # Initialize the tree with empty child lists
                for proc in processes:
                    tree[proc['pid']] = []
                
                # Add each process to its parent's child list
                for proc in processes:
                    try:
                        parent = psutil.Process(proc['pid']).parent()
                        if parent and parent.pid in tree:
                            tree[parent.pid].append(proc)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                        
            return tree
        except Exception as e:
            logger.error(f"Error getting process tree: {e}")
            return {}
    
    @staticmethod
    def kill_process(pid: int, force: bool = False) -> bool:
        """
        Kill a process
        
        Args:
            pid: Process ID to kill
            force: Whether to forcefully terminate the process
            
        Returns:
            Success status
        """
        try:
            process = psutil.Process(pid)
            if force:
                process.kill()
            else:
                process.terminate()
            return True
        except Exception as e:
            logger.error(f"Error killing process {pid}: {e}")
            return False

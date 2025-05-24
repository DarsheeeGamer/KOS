"""
NetworkManager Component for KADVLayer

This module provides network management capabilities,
allowing KOS to monitor and control network interfaces and connections.
"""

import os
import sys
import logging
import threading
import socket
import time
import json
from typing import Dict, List, Any, Optional, Union, Callable

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.network_manager')

class NetworkInterface:
    """Information about a network interface"""
    
    def __init__(self, name: str, addresses: List[Dict[str, Any]] = None, stats: Dict[str, Any] = None):
        """
        Initialize a network interface
        
        Args:
            name: Interface name
            addresses: List of addresses
            stats: Interface statistics
        """
        self.name = name
        self.addresses = addresses or []
        self.stats = stats or {}
        self.status = "unknown"
        self.is_up = False
        self.previous_stats = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "addresses": self.addresses,
            "stats": self.stats,
            "status": self.status,
            "is_up": self.is_up
        }

class NetworkManager:
    """
    Manages network interfaces and connections
    
    This class provides methods to monitor and control
    network interfaces and connections on the host system.
    """
    
    def __init__(self):
        """Initialize the NetworkManager component"""
        self.lock = threading.RLock()
        self.monitoring = False
        self.monitor_thread = None
        
        # Interface tracking
        self.interfaces = {}  # name -> NetworkInterface
        
        # Connection tracking
        self.connections = []
        
        # Event callbacks
        self.callbacks = {
            "interface_up": [],
            "interface_down": [],
            "connection_opened": [],
            "connection_closed": [],
            "traffic_spike": [],
            "all": []
        }
        
        # Monitoring interval (seconds)
        self.interval = 5.0
        
        # Traffic spike threshold (bytes per second)
        self.traffic_spike_threshold = 1024 * 1024  # 1 MB/s
        
        logger.debug("NetworkManager component initialized")
    
    def start_monitoring(self, interval: Optional[float] = None) -> bool:
        """
        Start network monitoring
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.monitoring:
                logger.warning("Network monitoring already running")
                return False
            
            if not PSUTIL_AVAILABLE:
                logger.error("Cannot monitor network without psutil")
                return False
            
            if interval is not None:
                self.interval = max(1.0, interval)  # Minimum 1 second
            
            # Perform initial interface detection
            self._detect_interfaces()
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info(f"Started network monitoring with interval {self.interval}s")
            return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop network monitoring
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.monitoring:
                logger.warning("Network monitoring not running")
                return False
            
            self.monitoring = False
            
            # Wait for thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("Stopped network monitoring")
            return True
    
    def _monitor_loop(self):
        """Main network monitoring loop"""
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot monitor network without psutil")
            self.monitoring = False
            return
        
        while self.monitoring:
            try:
                # Update interface status
                self._update_interfaces()
                
                # Update connections
                self._update_connections()
                
                # Sleep until next check
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in network monitoring: {e}")
                time.sleep(self.interval)
    
    def _detect_interfaces(self) -> Dict[str, NetworkInterface]:
        """
        Detect network interfaces
        
        Returns:
            Dictionary of detected interfaces
        """
        interfaces = {}
        
        try:
            if hasattr(psutil, 'net_if_addrs'):
                net_if_addrs = psutil.net_if_addrs()
                
                for interface_name, addresses in net_if_addrs.items():
                    # Process addresses
                    addr_list = []
                    
                    for addr in addresses:
                        addr_info = {
                            "family": str(addr.family),
                            "address": addr.address
                        }
                        
                        if hasattr(addr, 'netmask') and addr.netmask:
                            addr_info["netmask"] = addr.netmask
                        
                        if hasattr(addr, 'broadcast') and addr.broadcast:
                            addr_info["broadcast"] = addr.broadcast
                        
                        addr_list.append(addr_info)
                    
                    # Get interface stats
                    stats = None
                    
                    if hasattr(psutil, 'net_io_counters'):
                        try:
                            net_io = psutil.net_io_counters(pernic=True)
                            if interface_name in net_io:
                                interface_io = net_io[interface_name]
                                stats = {
                                    "bytes_sent": interface_io.bytes_sent,
                                    "bytes_recv": interface_io.bytes_recv,
                                    "packets_sent": interface_io.packets_sent,
                                    "packets_recv": interface_io.packets_recv,
                                    "errin": interface_io.errin,
                                    "errout": interface_io.errout,
                                    "dropin": interface_io.dropin,
                                    "dropout": interface_io.dropout
                                }
                        except:
                            pass
                    
                    # Create interface
                    interface = NetworkInterface(
                        name=interface_name,
                        addresses=addr_list,
                        stats=stats
                    )
                    
                    # Determine if interface is up
                    interface.is_up = any(addr["address"] != "127.0.0.1" for addr in addr_list if addr["family"] == "2")
                    interface.status = "up" if interface.is_up else "down"
                    
                    interfaces[interface_name] = interface
            
            with self.lock:
                for name, interface in interfaces.items():
                    if name in self.interfaces:
                        # Update existing interface
                        self.interfaces[name].addresses = interface.addresses
                        self.interfaces[name].previous_stats = self.interfaces[name].stats
                        self.interfaces[name].stats = interface.stats
                        
                        # Check if status changed
                        if self.interfaces[name].is_up != interface.is_up:
                            self.interfaces[name].is_up = interface.is_up
                            self.interfaces[name].status = interface.status
                            
                            # Trigger event
                            if interface.is_up:
                                self._trigger_event("interface_up", {"interface": self.interfaces[name].to_dict()})
                            else:
                                self._trigger_event("interface_down", {"interface": self.interfaces[name].to_dict()})
                    else:
                        # Add new interface
                        self.interfaces[name] = interface
                        
                        # Trigger event if up
                        if interface.is_up:
                            self._trigger_event("interface_up", {"interface": interface.to_dict()})
            
            return interfaces
        except Exception as e:
            logger.error(f"Error detecting interfaces: {e}")
            return {}
    
    def _update_interfaces(self):
        """Update interface status and statistics"""
        try:
            if hasattr(psutil, 'net_io_counters'):
                net_io = psutil.net_io_counters(pernic=True)
                
                with self.lock:
                    for name, interface in self.interfaces.items():
                        if name in net_io:
                            # Update previous stats
                            interface.previous_stats = interface.stats
                            
                            # Update current stats
                            interface_io = net_io[name]
                            interface.stats = {
                                "bytes_sent": interface_io.bytes_sent,
                                "bytes_recv": interface_io.bytes_recv,
                                "packets_sent": interface_io.packets_sent,
                                "packets_recv": interface_io.packets_recv,
                                "errin": interface_io.errin,
                                "errout": interface_io.errout,
                                "dropin": interface_io.dropin,
                                "dropout": interface_io.dropout
                            }
                            
                            # Check for traffic spike
                            if interface.previous_stats:
                                # Calculate bandwidth
                                bytes_sent_diff = interface.stats["bytes_sent"] - interface.previous_stats["bytes_sent"]
                                bytes_recv_diff = interface.stats["bytes_recv"] - interface.previous_stats["bytes_recv"]
                                
                                bytes_total_diff = bytes_sent_diff + bytes_recv_diff
                                bytes_per_second = bytes_total_diff / self.interval
                                
                                # Check if exceeds threshold
                                if bytes_per_second > self.traffic_spike_threshold:
                                    self._trigger_event("traffic_spike", {
                                        "interface": interface.to_dict(),
                                        "bytes_per_second": bytes_per_second,
                                        "threshold": self.traffic_spike_threshold
                                    })
        except Exception as e:
            logger.error(f"Error updating interfaces: {e}")
    
    def _update_connections(self):
        """Update network connections"""
        try:
            if hasattr(psutil, 'net_connections'):
                # Get current connections
                current_connections = []
                
                try:
                    connections = psutil.net_connections()
                    
                    for conn in connections:
                        conn_info = {
                            "fd": conn.fd,
                            "family": conn.family,
                            "type": conn.type,
                            "laddr": conn.laddr._asdict() if conn.laddr else None,
                            "raddr": conn.raddr._asdict() if conn.raddr else None,
                            "status": conn.status,
                            "pid": conn.pid
                        }
                        
                        current_connections.append(conn_info)
                except:
                    # May require admin privileges
                    pass
                
                with self.lock:
                    # Find new connections
                    new_connections = [conn for conn in current_connections if conn not in self.connections]
                    
                    # Find closed connections
                    closed_connections = [conn for conn in self.connections if conn not in current_connections]
                    
                    # Trigger events for new connections
                    for conn in new_connections:
                        self._trigger_event("connection_opened", {"connection": conn})
                    
                    # Trigger events for closed connections
                    for conn in closed_connections:
                        self._trigger_event("connection_closed", {"connection": conn})
                    
                    # Update connections
                    self.connections = current_connections
        except Exception as e:
            logger.error(f"Error updating connections: {e}")
    
    def _trigger_event(self, event_type: str, event_data: Dict[str, Any]):
        """
        Trigger a network event
        
        Args:
            event_type: Event type
            event_data: Event data
        """
        # Add timestamp
        event_data["timestamp"] = time.time()
        
        # Call event callbacks
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(event_data)
                except Exception as e:
                    logger.error(f"Error in network event callback: {e}")
        
        # Call all callbacks
        for callback in self.callbacks["all"]:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Error in network event callback: {e}")
    
    def register_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for network events
        
        Args:
            event_type: Event type
            callback: Callback function
            
        Returns:
            Success status
        """
        if event_type not in self.callbacks:
            logger.error(f"Invalid event type: {event_type}")
            return False
        
        with self.lock:
            self.callbacks[event_type].append(callback)
            logger.debug(f"Registered callback for {event_type} network events")
            return True
    
    def unregister_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Unregister a callback for network events
        
        Args:
            event_type: Event type
            callback: Callback function
            
        Returns:
            Success status
        """
        if event_type not in self.callbacks:
            logger.error(f"Invalid event type: {event_type}")
            return False
        
        with self.lock:
            if callback in self.callbacks[event_type]:
                self.callbacks[event_type].remove(callback)
                logger.debug(f"Unregistered callback for {event_type} network events")
                return True
            else:
                logger.warning(f"Callback not found for {event_type} network events")
                return False
    
    def get_interfaces(self) -> List[Dict[str, Any]]:
        """
        Get network interfaces
        
        Returns:
            List of interfaces
        """
        with self.lock:
            return [interface.to_dict() for interface in self.interfaces.values()]
    
    def get_interface(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get interface by name
        
        Args:
            name: Interface name
            
        Returns:
            Interface or None if not found
        """
        with self.lock:
            interface = self.interfaces.get(name)
            return interface.to_dict() if interface else None
    
    def get_connections(self) -> List[Dict[str, Any]]:
        """
        Get network connections
        
        Returns:
            List of connections
        """
        with self.lock:
            return self.connections.copy()
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics
        
        Returns:
            Dictionary with connection statistics
        """
        with self.lock:
            # Count connections by status
            status_counts = {}
            for conn in self.connections:
                status = conn.get("status", "UNKNOWN")
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count connections by type
            type_counts = {}
            for conn in self.connections:
                conn_type = conn.get("type", 0)
                type_counts[str(conn_type)] = type_counts.get(str(conn_type), 0) + 1
            
            return {
                "total": len(self.connections),
                "by_status": status_counts,
                "by_type": type_counts
            }
    
    def ping(self, host: str, count: int = 4, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Ping a host
        
        Args:
            host: Host to ping
            count: Number of pings
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with ping results
        """
        try:
            # Resolve hostname
            try:
                ip_address = socket.gethostbyname(host)
            except socket.gaierror:
                return {
                    "success": False,
                    "error": f"Could not resolve hostname: {host}"
                }
            
            # Check if platform-specific ping is available
            if hasattr(self, f"_ping_{sys.platform}"):
                return getattr(self, f"_ping_{sys.platform}")(host, count, timeout)
            
            # Fallback to socket ping
            return self._ping_socket(host, count, timeout)
        except Exception as e:
            logger.error(f"Error pinging host: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _ping_socket(self, host: str, count: int, timeout: float) -> Dict[str, Any]:
        """
        Ping a host using socket
        
        Args:
            host: Host to ping
            count: Number of pings
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with ping results
        """
        try:
            results = []
            
            for i in range(count):
                start_time = time.time()
                
                # Try to connect to host
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                
                try:
                    s.connect((host, 80))
                    s.shutdown(socket.SHUT_RDWR)
                    end_time = time.time()
                    rtt = (end_time - start_time) * 1000  # ms
                    results.append(rtt)
                except:
                    results.append(None)
                finally:
                    s.close()
                
                # Sleep between pings
                if i < count - 1:
                    time.sleep(0.5)
            
            # Calculate statistics
            successful = [r for r in results if r is not None]
            
            if successful:
                return {
                    "success": True,
                    "host": host,
                    "sent": count,
                    "received": len(successful),
                    "lost": count - len(successful),
                    "min": min(successful),
                    "max": max(successful),
                    "avg": sum(successful) / len(successful),
                    "results": results
                }
            else:
                return {
                    "success": False,
                    "host": host,
                    "sent": count,
                    "received": 0,
                    "lost": count,
                    "error": "All pings failed"
                }
        except Exception as e:
            logger.error(f"Error in socket ping: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _ping_win32(self, host: str, count: int, timeout: float) -> Dict[str, Any]:
        """
        Ping a host on Windows
        
        Args:
            host: Host to ping
            count: Number of pings
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with ping results
        """
        try:
            import subprocess
            
            # Build command
            timeout_ms = int(timeout * 1000)
            cmd = ["ping", "-n", str(count), "-w", str(timeout_ms), host]
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse output
            output = result.stdout
            
            if "Reply from" in output:
                # Extract statistics
                stats_line = output.split("Ping statistics for")[1].split("\n")[1]
                packets_line = stats_line.strip()
                
                sent = int(packets_line.split("Sent = ")[1].split(",")[0])
                received = int(packets_line.split("Received = ")[1].split(",")[0])
                lost = int(packets_line.split("Lost = ")[1].split(" ")[0])
                
                # Extract times if available
                times = {}
                if "Minimum = " in output:
                    times_line = output.split("Approximate round trip times in milli-seconds:")[1].split("\n")[1]
                    times_text = times_line.strip()
                    
                    min_time = int(times_text.split("Minimum = ")[1].split("ms")[0])
                    max_time = int(times_text.split("Maximum = ")[1].split("ms")[0])
                    avg_time = int(times_text.split("Average = ")[1].split("ms")[0])
                    
                    times = {
                        "min": min_time,
                        "max": max_time,
                        "avg": avg_time
                    }
                
                return {
                    "success": received > 0,
                    "host": host,
                    "sent": sent,
                    "received": received,
                    "lost": lost,
                    **times,
                    "output": output
                }
            else:
                return {
                    "success": False,
                    "host": host,
                    "error": "Ping failed",
                    "output": output
                }
        except Exception as e:
            logger.error(f"Error in Windows ping: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _ping_linux(self, host: str, count: int, timeout: float) -> Dict[str, Any]:
        """
        Ping a host on Linux
        
        Args:
            host: Host to ping
            count: Number of pings
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with ping results
        """
        try:
            import subprocess
            
            # Build command
            cmd = ["ping", "-c", str(count), "-W", str(int(timeout)), host]
            
            # Run command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse output
            output = result.stdout
            
            if "bytes from" in output:
                # Extract statistics
                stats_line = output.split("---")[1].split("\n")[1]
                packets_line = stats_line.strip()
                
                # Parse packets
                packets_parts = packets_line.split(", ")
                sent = int(packets_parts[0].split(" ")[0])
                received = int(packets_parts[1].split(" ")[0])
                lost_pct = float(packets_parts[2].split("%")[0])
                
                # Extract times if available
                times = {}
                if "min/avg/max" in output:
                    times_line = output.split("min/avg/max")[1].strip()
                    time_values = times_line.split(" = ")[1].split("/")
                    
                    min_time = float(time_values[0])
                    avg_time = float(time_values[1])
                    max_time = float(time_values[2])
                    
                    times = {
                        "min": min_time,
                        "avg": avg_time,
                        "max": max_time
                    }
                
                return {
                    "success": received > 0,
                    "host": host,
                    "sent": sent,
                    "received": received,
                    "lost": sent - received,
                    "lost_percent": lost_pct,
                    **times,
                    "output": output
                }
            else:
                return {
                    "success": False,
                    "host": host,
                    "error": "Ping failed",
                    "output": output
                }
        except Exception as e:
            logger.error(f"Error in Linux ping: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def traceroute(self, host: str, max_hops: int = 30, timeout: float = 2.0) -> Dict[str, Any]:
        """
        Perform a traceroute to a host
        
        Args:
            host: Host to trace
            max_hops: Maximum number of hops
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with traceroute results
        """
        try:
            # Resolve hostname
            try:
                ip_address = socket.gethostbyname(host)
            except socket.gaierror:
                return {
                    "success": False,
                    "error": f"Could not resolve hostname: {host}"
                }
            
            # Check if platform-specific traceroute is available
            if hasattr(self, f"_traceroute_{sys.platform}"):
                return getattr(self, f"_traceroute_{sys.platform}")(host, max_hops, timeout)
            
            # Fallback to socket traceroute
            return self._traceroute_socket(host, max_hops, timeout)
        except Exception as e:
            logger.error(f"Error in traceroute: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _traceroute_socket(self, host: str, max_hops: int, timeout: float) -> Dict[str, Any]:
        """
        Perform a traceroute to a host using socket
        
        Args:
            host: Host to trace
            max_hops: Maximum number of hops
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with traceroute results
        """
        try:
            # Socket traceroute is not implemented
            return {
                "success": False,
                "error": "Socket traceroute not implemented"
            }
        except Exception as e:
            logger.error(f"Error in socket traceroute: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def http_get(self, url: str, headers: Dict[str, str] = None, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Perform an HTTP GET request
        
        Args:
            url: URL to request
            headers: Request headers
            timeout: Timeout in seconds
            
        Returns:
            Dictionary with request results
        """
        if not REQUESTS_AVAILABLE:
            return {
                "success": False,
                "error": "Requests module not available"
            }
        
        try:
            # Perform request
            response = requests.get(url, headers=headers, timeout=timeout)
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content_type": response.headers.get("Content-Type"),
                "content_length": len(response.content),
                "elapsed": response.elapsed.total_seconds(),
                "url": response.url,
                "text": response.text if len(response.text) < 1024 else response.text[:1024] + "..."
            }
        except Exception as e:
            logger.error(f"Error in HTTP GET request: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def set_traffic_spike_threshold(self, threshold: float) -> bool:
        """
        Set traffic spike threshold
        
        Args:
            threshold: Threshold in bytes per second
            
        Returns:
            Success status
        """
        with self.lock:
            self.traffic_spike_threshold = threshold
            logger.debug(f"Set traffic spike threshold to {threshold} bytes per second")
            return True
    
    def get_traffic_spike_threshold(self) -> float:
        """
        Get traffic spike threshold
        
        Returns:
            Threshold in bytes per second
        """
        with self.lock:
            return self.traffic_spike_threshold

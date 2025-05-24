"""
HardwareManager Component for KADVLayer

This module provides hardware management capabilities,
allowing KOS to interact with system hardware devices.
"""

import os
import sys
import logging
import threading
import platform
from typing import Dict, List, Any, Optional, Union, Callable

# Try to import optional dependencies
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

logger = logging.getLogger('KOS.advlayer.hardware_manager')

class HardwareDevice:
    """Information about a hardware device"""
    
    def __init__(self, device_id: str, device_type: str, name: str, info: Dict[str, Any] = None):
        """
        Initialize a hardware device
        
        Args:
            device_id: Device ID
            device_type: Device type (disk, network, usb, etc.)
            name: Device name
            info: Additional device information
        """
        self.device_id = device_id
        self.device_type = device_type
        self.name = name
        self.info = info or {}
        self.status = "unknown"
        self.is_connected = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "name": self.name,
            "status": self.status,
            "is_connected": self.is_connected,
            "info": self.info
        }
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.name} ({self.device_type}, {self.status})"

class HardwareManager:
    """
    Manages hardware devices on the host system
    
    This class provides methods to detect, monitor, and control
    hardware devices on the host system.
    """
    
    def __init__(self):
        """Initialize the HardwareManager component"""
        self.lock = threading.RLock()
        self.monitoring = False
        self.monitor_thread = None
        
        # Device tracking
        self.devices = {}  # device_id -> HardwareDevice
        
        # Event callbacks
        self.callbacks = {
            "connected": [],
            "disconnected": [],
            "changed": [],
            "all": []
        }
        
        # Monitoring interval (seconds)
        self.interval = 10.0
        
        logger.debug("HardwareManager component initialized")
    
    def start_monitoring(self, interval: Optional[float] = None) -> bool:
        """
        Start hardware monitoring
        
        Args:
            interval: Monitoring interval in seconds
            
        Returns:
            Success status
        """
        with self.lock:
            if self.monitoring:
                logger.warning("Hardware monitoring already running")
                return False
            
            if not PSUTIL_AVAILABLE:
                logger.error("Cannot monitor hardware without psutil")
                return False
            
            if interval is not None:
                self.interval = max(1.0, interval)  # Minimum 1 second
            
            # Perform initial device detection
            self._detect_devices()
            
            self.monitoring = True
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.monitor_thread.start()
            
            logger.info(f"Started hardware monitoring with interval {self.interval}s")
            return True
    
    def stop_monitoring(self) -> bool:
        """
        Stop hardware monitoring
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.monitoring:
                logger.warning("Hardware monitoring not running")
                return False
            
            self.monitoring = False
            
            # Wait for thread to finish
            if self.monitor_thread and self.monitor_thread.is_alive():
                self.monitor_thread.join(timeout=2.0)
            
            logger.info("Stopped hardware monitoring")
            return True
    
    def _monitor_loop(self):
        """Main hardware monitoring loop"""
        if not PSUTIL_AVAILABLE:
            logger.error("Cannot monitor hardware without psutil")
            self.monitoring = False
            return
        
        while self.monitoring:
            try:
                # Detect current devices
                current_devices = self._detect_devices(update_existing=False)
                
                # Compare with existing devices
                self._update_device_status(current_devices)
                
                # Sleep until next check
                import time
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in hardware monitoring: {e}")
                import time
                time.sleep(self.interval)
    
    def _detect_devices(self, update_existing: bool = True) -> Dict[str, HardwareDevice]:
        """
        Detect hardware devices
        
        Args:
            update_existing: Whether to update existing devices
            
        Returns:
            Dictionary of detected devices
        """
        detected_devices = {}
        
        try:
            # Detect disks
            self._detect_disks(detected_devices)
            
            # Detect network devices
            self._detect_network_devices(detected_devices)
            
            # Detect USB devices (platform-specific)
            self._detect_usb_devices(detected_devices)
            
            # Update existing devices if requested
            if update_existing:
                with self.lock:
                    self.devices.update(detected_devices)
            
            return detected_devices
        except Exception as e:
            logger.error(f"Error detecting devices: {e}")
            return {}
    
    def _detect_disks(self, devices: Dict[str, HardwareDevice]):
        """
        Detect disk devices
        
        Args:
            devices: Dictionary to update with detected devices
        """
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            for partition in psutil.disk_partitions():
                # Create device ID
                device_id = f"disk:{partition.device}"
                
                # Create device info
                device_info = {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "opts": partition.opts
                }
                
                # Try to get disk usage
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    device_info.update({
                        "total": usage.total,
                        "used": usage.used,
                        "free": usage.free,
                        "percent": usage.percent
                    })
                except:
                    pass
                
                # Create device
                device = HardwareDevice(
                    device_id=device_id,
                    device_type="disk",
                    name=f"Disk {partition.device}",
                    info=device_info
                )
                
                device.status = "online"
                device.is_connected = True
                
                devices[device_id] = device
        except Exception as e:
            logger.error(f"Error detecting disks: {e}")
    
    def _detect_network_devices(self, devices: Dict[str, HardwareDevice]):
        """
        Detect network devices
        
        Args:
            devices: Dictionary to update with detected devices
        """
        if not PSUTIL_AVAILABLE:
            return
        
        try:
            if hasattr(psutil, 'net_if_addrs'):
                net_if_addrs = psutil.net_if_addrs()
                
                for interface_name, addresses in net_if_addrs.items():
                    # Create device ID
                    device_id = f"net:{interface_name}"
                    
                    # Create device info
                    device_info = {
                        "name": interface_name,
                        "addresses": []
                    }
                    
                    # Add addresses
                    for addr in addresses:
                        addr_info = {
                            "family": str(addr.family),
                            "address": addr.address
                        }
                        
                        if hasattr(addr, 'netmask') and addr.netmask:
                            addr_info["netmask"] = addr.netmask
                        
                        if hasattr(addr, 'broadcast') and addr.broadcast:
                            addr_info["broadcast"] = addr.broadcast
                        
                        device_info["addresses"].append(addr_info)
                    
                    # Try to get network stats
                    if hasattr(psutil, 'net_io_counters'):
                        try:
                            net_io = psutil.net_io_counters(pernic=True)
                            if interface_name in net_io:
                                interface_io = net_io[interface_name]
                                device_info["io"] = {
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
                    
                    # Create device
                    device = HardwareDevice(
                        device_id=device_id,
                        device_type="network",
                        name=f"Network {interface_name}",
                        info=device_info
                    )
                    
                    device.status = "online"
                    device.is_connected = True
                    
                    devices[device_id] = device
        except Exception as e:
            logger.error(f"Error detecting network devices: {e}")
    
    def _detect_usb_devices(self, devices: Dict[str, HardwareDevice]):
        """
        Detect USB devices
        
        Args:
            devices: Dictionary to update with detected devices
        """
        system = platform.system().lower()
        
        try:
            if system == 'windows':
                self._detect_usb_devices_windows(devices)
            elif system == 'linux':
                self._detect_usb_devices_linux(devices)
            elif system == 'darwin':
                self._detect_usb_devices_macos(devices)
        except Exception as e:
            logger.error(f"Error detecting USB devices: {e}")
    
    def _detect_usb_devices_windows(self, devices: Dict[str, HardwareDevice]):
        """
        Detect USB devices on Windows
        
        Args:
            devices: Dictionary to update with detected devices
        """
        try:
            import subprocess
            
            # Run PowerShell command to list USB devices
            cmd = "Get-PnpDevice -Class USB | Select-Object Status, Class, FriendlyName, InstanceId | ConvertTo-Json"
            result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                
                # Parse JSON output
                output = result.stdout.strip()
                if output:
                    usb_devices = json.loads(output)
                    
                    # Ensure we have a list
                    if not isinstance(usb_devices, list):
                        usb_devices = [usb_devices]
                    
                    for usb_device in usb_devices:
                        if not isinstance(usb_device, dict):
                            continue
                        
                        # Skip devices without an instance ID
                        if "InstanceId" not in usb_device:
                            continue
                        
                        # Create device ID
                        device_id = f"usb:{usb_device['InstanceId']}"
                        
                        # Create device info
                        device_info = {
                            "instance_id": usb_device.get("InstanceId"),
                            "class": usb_device.get("Class"),
                            "status": usb_device.get("Status")
                        }
                        
                        # Create device
                        device = HardwareDevice(
                            device_id=device_id,
                            device_type="usb",
                            name=usb_device.get("FriendlyName", "USB Device"),
                            info=device_info
                        )
                        
                        # Set status based on device status
                        if usb_device.get("Status") == "OK":
                            device.status = "online"
                            device.is_connected = True
                        else:
                            device.status = "offline"
                            device.is_connected = False
                        
                        devices[device_id] = device
        except Exception as e:
            logger.error(f"Error detecting USB devices on Windows: {e}")
    
    def _detect_usb_devices_linux(self, devices: Dict[str, HardwareDevice]):
        """
        Detect USB devices on Linux
        
        Args:
            devices: Dictionary to update with detected devices
        """
        try:
            # Check if lsusb is available
            import subprocess
            
            result = subprocess.run(["which", "lsusb"], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Run lsusb to list USB devices
                result = subprocess.run(["lsusb"], capture_output=True, text=True)
                
                if result.returncode == 0:
                    # Parse output
                    for line in result.stdout.strip().split("\n"):
                        if not line:
                            continue
                        
                        # Example: Bus 001 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub
                        parts = line.split(":")
                        if len(parts) < 2:
                            continue
                        
                        # Extract bus and device info
                        bus_device = parts[0].strip()
                        id_name = parts[1].strip()
                        
                        # Extract device ID and name
                        id_parts = id_name.split(" ", 1)
                        if len(id_parts) < 2:
                            continue
                        
                        device_id_raw = id_parts[0].strip()
                        device_name = id_parts[1].strip()
                        
                        # Create device ID
                        device_id = f"usb:{bus_device}:{device_id_raw}"
                        
                        # Create device info
                        device_info = {
                            "bus_device": bus_device,
                            "device_id_raw": device_id_raw,
                            "raw_info": line
                        }
                        
                        # Create device
                        device = HardwareDevice(
                            device_id=device_id,
                            device_type="usb",
                            name=device_name,
                            info=device_info
                        )
                        
                        device.status = "online"
                        device.is_connected = True
                        
                        devices[device_id] = device
        except Exception as e:
            logger.error(f"Error detecting USB devices on Linux: {e}")
    
    def _detect_usb_devices_macos(self, devices: Dict[str, HardwareDevice]):
        """
        Detect USB devices on macOS
        
        Args:
            devices: Dictionary to update with detected devices
        """
        try:
            # Check if system_profiler is available
            import subprocess
            
            result = subprocess.run(["which", "system_profiler"], capture_output=True, text=True)
            
            if result.returncode == 0:
                # Run system_profiler to list USB devices
                result = subprocess.run(["system_profiler", "SPUSBDataType", "-json"], capture_output=True, text=True)
                
                if result.returncode == 0:
                    import json
                    
                    # Parse JSON output
                    output = result.stdout.strip()
                    if output:
                        usb_data = json.loads(output)
                        
                        if "SPUSBDataType" in usb_data and isinstance(usb_data["SPUSBDataType"], list):
                            for usb_controller in usb_data["SPUSBDataType"]:
                                self._process_macos_usb_device(usb_controller, devices)
        except Exception as e:
            logger.error(f"Error detecting USB devices on macOS: {e}")
    
    def _process_macos_usb_device(self, device_data: Dict[str, Any], devices: Dict[str, HardwareDevice], parent_id: str = None):
        """
        Process macOS USB device data
        
        Args:
            device_data: Device data from system_profiler
            devices: Dictionary to update with detected devices
            parent_id: Parent device ID
        """
        if not isinstance(device_data, dict):
            return
        
        # Get device info
        location_id = device_data.get("location_id", "")
        vendor_id = device_data.get("vendor_id", "")
        product_id = device_data.get("product_id", "")
        device_name = device_data.get("_name", "USB Device")
        
        # Create device ID
        if location_id and (vendor_id or product_id):
            device_id = f"usb:{location_id}:{vendor_id}:{product_id}"
        elif parent_id:
            device_id = f"{parent_id}:sub:{len(devices)}"
        else:
            device_id = f"usb:controller:{len(devices)}"
        
        # Create device info
        device_info = {key: value for key, value in device_data.items() if key != "_items"}
        
        # Create device
        device = HardwareDevice(
            device_id=device_id,
            device_type="usb",
            name=device_name,
            info=device_info
        )
        
        device.status = "online"
        device.is_connected = True
        
        devices[device_id] = device
        
        # Process child devices
        if "_items" in device_data and isinstance(device_data["_items"], list):
            for child_device in device_data["_items"]:
                self._process_macos_usb_device(child_device, devices, device_id)
    
    def _update_device_status(self, current_devices: Dict[str, HardwareDevice]):
        """
        Update device status based on current devices
        
        Args:
            current_devices: Dictionary of current devices
        """
        with self.lock:
            # Find connected devices
            connected_devices = set(current_devices.keys()) - set(self.devices.keys())
            
            # Find disconnected devices
            disconnected_devices = set(self.devices.keys()) - set(current_devices.keys())
            
            # Find changed devices
            changed_devices = []
            
            for device_id in set(current_devices.keys()) & set(self.devices.keys()):
                current_device = current_devices[device_id]
                existing_device = self.devices[device_id]
                
                # Check if device has changed
                if current_device.to_dict() != existing_device.to_dict():
                    changed_devices.append(device_id)
            
            # Update devices
            for device_id in connected_devices:
                self.devices[device_id] = current_devices[device_id]
                
                # Trigger connected event
                self._trigger_event("connected", self.devices[device_id])
            
            for device_id in disconnected_devices:
                # Update status
                self.devices[device_id].status = "offline"
                self.devices[device_id].is_connected = False
                
                # Trigger disconnected event
                self._trigger_event("disconnected", self.devices[device_id])
            
            for device_id in changed_devices:
                # Update device
                self.devices[device_id] = current_devices[device_id]
                
                # Trigger changed event
                self._trigger_event("changed", self.devices[device_id])
    
    def _trigger_event(self, event_type: str, device: HardwareDevice):
        """
        Trigger a device event
        
        Args:
            event_type: Event type
            device: Device object
        """
        # Create event data
        event_data = {
            "event_type": event_type,
            "device": device.to_dict(),
            "timestamp": import time; time.time()
        }
        
        # Call event callbacks
        if event_type in self.callbacks:
            for callback in self.callbacks[event_type]:
                try:
                    callback(event_data)
                except Exception as e:
                    logger.error(f"Error in device event callback: {e}")
        
        # Call all callbacks
        for callback in self.callbacks["all"]:
            try:
                callback(event_data)
            except Exception as e:
                logger.error(f"Error in device event callback: {e}")
    
    def register_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Register a callback for device events
        
        Args:
            event_type: Event type (connected, disconnected, changed, all)
            callback: Callback function
            
        Returns:
            Success status
        """
        if event_type not in self.callbacks:
            logger.error(f"Invalid event type: {event_type}")
            return False
        
        with self.lock:
            self.callbacks[event_type].append(callback)
            logger.debug(f"Registered callback for {event_type} device events")
            return True
    
    def unregister_callback(self, event_type: str, callback: Callable) -> bool:
        """
        Unregister a callback for device events
        
        Args:
            event_type: Event type (connected, disconnected, changed, all)
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
                logger.debug(f"Unregistered callback for {event_type} device events")
                return True
            else:
                logger.warning(f"Callback not found for {event_type} device events")
                return False
    
    def get_devices(self, device_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get devices
        
        Args:
            device_type: Device type filter
            
        Returns:
            List of devices
        """
        with self.lock:
            if device_type:
                return [device.to_dict() for device in self.devices.values() if device.device_type == device_type]
            else:
                return [device.to_dict() for device in self.devices.values()]
    
    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        Get device by ID
        
        Args:
            device_id: Device ID
            
        Returns:
            Device or None if not found
        """
        with self.lock:
            device = self.devices.get(device_id)
            return device.to_dict() if device else None
    
    def rescan_devices(self) -> Dict[str, Any]:
        """
        Rescan devices
        
        Returns:
            Dictionary with scan results
        """
        try:
            # Detect devices
            devices = self._detect_devices()
            
            return {
                "success": True,
                "devices_count": len(devices),
                "devices": [device.to_dict() for device in devices.values()]
            }
        except Exception as e:
            logger.error(f"Error rescanning devices: {e}")
            return {
                "success": False,
                "error": str(e)
            }

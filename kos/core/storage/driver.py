"""
Storage Drivers for KOS Storage Subsystem

This module implements storage drivers for the KOS storage subsystem,
providing different backend implementations for persistent volumes.
"""

import os
import shutil
import logging
import threading
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple

# Logging setup
logger = logging.getLogger(__name__)

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
VOLUME_DATA_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/storage/data')


class StorageDriverException(Exception):
    """Exception raised for storage driver errors."""
    pass


class StorageDriver(ABC):
    """
    Abstract base class for storage drivers.
    
    Storage drivers provide the actual implementation for different storage backends,
    such as local filesystem, network storage, or cloud storage.
    """
    
    @abstractmethod
    def create_volume(self, volume_path: str, size: str) -> bool:
        """
        Create a new volume.
        
        Args:
            volume_path: Path to the volume
            size: Volume size (e.g., "1Gi")
            
        Returns:
            bool: Success or failure
        """
        pass
    
    @abstractmethod
    def delete_volume(self, volume_path: str) -> bool:
        """
        Delete a volume.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            bool: Success or failure
        """
        pass
    
    @abstractmethod
    def resize_volume(self, volume_path: str, new_size: str) -> bool:
        """
        Resize a volume.
        
        Args:
            volume_path: Path to the volume
            new_size: New volume size (e.g., "2Gi")
            
        Returns:
            bool: Success or failure
        """
        pass
    
    @abstractmethod
    def mount_volume(self, volume_path: str, mount_path: str) -> bool:
        """
        Mount a volume.
        
        Args:
            volume_path: Path to the volume
            mount_path: Path to mount the volume at
            
        Returns:
            bool: Success or failure
        """
        pass
    
    @abstractmethod
    def unmount_volume(self, mount_path: str) -> bool:
        """
        Unmount a volume.
        
        Args:
            mount_path: Path where the volume is mounted
            
        Returns:
            bool: Success or failure
        """
        pass
    
    @abstractmethod
    def get_volume_info(self, volume_path: str) -> Dict[str, Any]:
        """
        Get information about a volume.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            Dict with volume information
        """
        pass
    
    def parse_size(self, size: str) -> int:
        """
        Parse a size string into bytes.
        
        Args:
            size: Size string (e.g., "1Gi", "500Mi")
            
        Returns:
            Size in bytes
        """
        size = size.strip()
        
        # Extract numeric part and unit
        if size[-1].isalpha():
            if size[-2].isalpha():
                unit = size[-2:]
                numeric = size[:-2]
            else:
                unit = size[-1]
                numeric = size[:-1]
        else:
            unit = ""
            numeric = size
        
        try:
            value = float(numeric)
        except ValueError:
            raise StorageDriverException(f"Invalid size format: {size}")
        
        # Convert to bytes
        unit = unit.upper()
        if unit == "K" or unit == "KI":
            return int(value * 1024)
        elif unit == "M" or unit == "MI":
            return int(value * 1024 * 1024)
        elif unit == "G" or unit == "GI":
            return int(value * 1024 * 1024 * 1024)
        elif unit == "T" or unit == "TI":
            return int(value * 1024 * 1024 * 1024 * 1024)
        elif unit == "KB":
            return int(value * 1000)
        elif unit == "MB":
            return int(value * 1000 * 1000)
        elif unit == "GB":
            return int(value * 1000 * 1000 * 1000)
        elif unit == "TB":
            return int(value * 1000 * 1000 * 1000 * 1000)
        else:
            return int(value)
    
    def format_size(self, size_bytes: int) -> str:
        """
        Format a size in bytes to a human-readable string.
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Human-readable size string
        """
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti']:
            if abs(size_bytes) < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        
        return f"{size_bytes:.1f}Pi"


class LocalDriver(StorageDriver):
    """
    Local filesystem storage driver.
    
    This driver uses the local filesystem for volume storage.
    """
    
    def __init__(self):
        """Initialize the local filesystem driver."""
        self._lock = threading.Lock()
    
    def create_volume(self, volume_path: str, size: str) -> bool:
        """
        Create a new volume on the local filesystem.
        
        Args:
            volume_path: Path to the volume
            size: Volume size (e.g., "1Gi")
            
        Returns:
            bool: Success or failure
        """
        try:
            # Ensure the volume directory exists
            os.makedirs(volume_path, exist_ok=True)
            
            # For local filesystem, we don't enforce size limits directly,
            # but we store the requested size in a metadata file
            with open(os.path.join(volume_path, ".volume_size"), "w") as f:
                f.write(size)
            
            logger.info(f"Created local volume at {volume_path} with size {size}")
            return True
        except Exception as e:
            logger.error(f"Failed to create local volume: {e}")
            return False
    
    def delete_volume(self, volume_path: str) -> bool:
        """
        Delete a volume from the local filesystem.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            bool: Success or failure
        """
        try:
            if os.path.exists(volume_path):
                shutil.rmtree(volume_path)
            
            logger.info(f"Deleted local volume at {volume_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete local volume: {e}")
            return False
    
    def resize_volume(self, volume_path: str, new_size: str) -> bool:
        """
        Resize a volume on the local filesystem.
        
        Args:
            volume_path: Path to the volume
            new_size: New volume size (e.g., "2Gi")
            
        Returns:
            bool: Success or failure
        """
        try:
            # Update the size metadata file
            with open(os.path.join(volume_path, ".volume_size"), "w") as f:
                f.write(new_size)
            
            logger.info(f"Resized local volume at {volume_path} to {new_size}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize local volume: {e}")
            return False
    
    def mount_volume(self, volume_path: str, mount_path: str) -> bool:
        """
        Mount a volume from the local filesystem.
        
        For local filesystem, this creates a symlink or bind mount.
        
        Args:
            volume_path: Path to the volume
            mount_path: Path to mount the volume at
            
        Returns:
            bool: Success or failure
        """
        try:
            # Ensure the mount directory exists
            os.makedirs(os.path.dirname(mount_path), exist_ok=True)
            
            # For local filesystem, we can use a symlink or bind mount
            # Try symlink first, fall back to bind mount
            try:
                if os.path.exists(mount_path):
                    if os.path.islink(mount_path):
                        os.unlink(mount_path)
                    else:
                        shutil.rmtree(mount_path)
                
                os.symlink(volume_path, mount_path)
            except Exception:
                # Fall back to bind mount
                try:
                    result = subprocess.run(
                        ["mount", "--bind", volume_path, mount_path],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to bind mount: {e.stderr}")
                    raise
            
            logger.info(f"Mounted local volume from {volume_path} to {mount_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to mount local volume: {e}")
            return False
    
    def unmount_volume(self, mount_path: str) -> bool:
        """
        Unmount a volume from the local filesystem.
        
        Args:
            mount_path: Path where the volume is mounted
            
        Returns:
            bool: Success or failure
        """
        try:
            if os.path.islink(mount_path):
                # Remove symlink
                os.unlink(mount_path)
            elif os.path.ismount(mount_path):
                # Unmount bind mount
                try:
                    result = subprocess.run(
                        ["umount", mount_path],
                        check=True,
                        capture_output=True,
                        text=True
                    )
                except subprocess.CalledProcessError as e:
                    logger.error(f"Failed to unmount: {e.stderr}")
                    raise
            
            logger.info(f"Unmounted local volume from {mount_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to unmount local volume: {e}")
            return False
    
    def get_volume_info(self, volume_path: str) -> Dict[str, Any]:
        """
        Get information about a volume on the local filesystem.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            Dict with volume information
        """
        try:
            info = {
                "path": volume_path,
                "exists": os.path.exists(volume_path),
                "size": "0",
                "used": "0",
                "available": "0"
            }
            
            if info["exists"]:
                # Get size from metadata file
                size_file = os.path.join(volume_path, ".volume_size")
                if os.path.exists(size_file):
                    with open(size_file, "r") as f:
                        info["size"] = f.read().strip()
                
                # Get actual disk usage
                stat = os.statvfs(volume_path)
                total = stat.f_blocks * stat.f_frsize
                free = stat.f_bfree * stat.f_frsize
                used = total - free
                
                info["used"] = self.format_size(used)
                info["available"] = self.format_size(free)
            
            return info
        except Exception as e:
            logger.error(f"Failed to get local volume info: {e}")
            return {"path": volume_path, "exists": False, "error": str(e)}


class LoopDeviceDriver(StorageDriver):
    """
    Loop device storage driver.
    
    This driver uses loop devices to create fixed-size volumes.
    """
    
    def __init__(self, loop_dir: Optional[str] = None):
        """
        Initialize the loop device driver.
        
        Args:
            loop_dir: Directory to store loop device files
        """
        self._lock = threading.Lock()
        self._loop_dir = loop_dir or os.path.join(VOLUME_DATA_DIR, "loop")
        os.makedirs(self._loop_dir, exist_ok=True)
    
    def create_volume(self, volume_path: str, size: str) -> bool:
        """
        Create a new volume using a loop device.
        
        Args:
            volume_path: Path to the volume
            size: Volume size (e.g., "1Gi")
            
        Returns:
            bool: Success or failure
        """
        try:
            # Ensure the volume directory exists
            os.makedirs(volume_path, exist_ok=True)
            
            # Create the loop file
            loop_file = os.path.join(self._loop_dir, os.path.basename(volume_path) + ".img")
            
            # Convert size to bytes
            size_bytes = self.parse_size(size)
            
            # Create a sparse file of the specified size
            with open(loop_file, "wb") as f:
                f.truncate(size_bytes)
            
            # Format the loop file with a filesystem
            try:
                result = subprocess.run(
                    ["mkfs.ext4", loop_file],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to format loop device: {e.stderr}")
                os.unlink(loop_file)
                raise
            
            # Store loop file path in volume metadata
            with open(os.path.join(volume_path, ".loop_file"), "w") as f:
                f.write(loop_file)
            
            logger.info(f"Created loop device volume at {volume_path} with size {size}")
            return True
        except Exception as e:
            logger.error(f"Failed to create loop device volume: {e}")
            return False
    
    def delete_volume(self, volume_path: str) -> bool:
        """
        Delete a volume using a loop device.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            bool: Success or failure
        """
        try:
            # Get loop file path from metadata
            loop_file_path = os.path.join(volume_path, ".loop_file")
            if os.path.exists(loop_file_path):
                with open(loop_file_path, "r") as f:
                    loop_file = f.read().strip()
                
                # Check if the loop file is mounted
                try:
                    result = subprocess.run(
                        ["grep", "-q", loop_file, "/proc/mounts"],
                        check=False,
                        capture_output=True
                    )
                    
                    if result.returncode == 0:
                        # Unmount it
                        mount_info = subprocess.run(
                            ["grep", loop_file, "/proc/mounts"],
                            check=True,
                            capture_output=True,
                            text=True
                        ).stdout.strip().split(" ")[1]
                        
                        subprocess.run(
                            ["umount", mount_info],
                            check=True,
                            capture_output=True
                        )
                except Exception as e:
                    logger.warning(f"Error checking or unmounting loop device: {e}")
                
                # Delete the loop file
                if os.path.exists(loop_file):
                    os.unlink(loop_file)
            
            # Delete the volume directory
            if os.path.exists(volume_path):
                shutil.rmtree(volume_path)
            
            logger.info(f"Deleted loop device volume at {volume_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete loop device volume: {e}")
            return False
    
    def resize_volume(self, volume_path: str, new_size: str) -> bool:
        """
        Resize a volume using a loop device.
        
        Args:
            volume_path: Path to the volume
            new_size: New volume size (e.g., "2Gi")
            
        Returns:
            bool: Success or failure
        """
        try:
            # Get loop file path from metadata
            loop_file_path = os.path.join(volume_path, ".loop_file")
            if not os.path.exists(loop_file_path):
                logger.error(f"Loop file metadata not found for volume {volume_path}")
                return False
            
            with open(loop_file_path, "r") as f:
                loop_file = f.read().strip()
            
            if not os.path.exists(loop_file):
                logger.error(f"Loop file not found: {loop_file}")
                return False
            
            # Convert new size to bytes
            new_size_bytes = self.parse_size(new_size)
            
            # Check current size
            current_size = os.path.getsize(loop_file)
            
            if new_size_bytes <= current_size:
                logger.warning(f"New size ({new_size}) is not larger than current size ({self.format_size(current_size)})")
                return True
            
            # Resize the loop file
            with open(loop_file, "rb+") as f:
                f.truncate(new_size_bytes)
            
            # Resize the filesystem
            try:
                result = subprocess.run(
                    ["resize2fs", loop_file],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to resize filesystem: {e.stderr}")
                raise
            
            logger.info(f"Resized loop device volume at {volume_path} to {new_size}")
            return True
        except Exception as e:
            logger.error(f"Failed to resize loop device volume: {e}")
            return False
    
    def mount_volume(self, volume_path: str, mount_path: str) -> bool:
        """
        Mount a volume using a loop device.
        
        Args:
            volume_path: Path to the volume
            mount_path: Path to mount the volume at
            
        Returns:
            bool: Success or failure
        """
        try:
            # Get loop file path from metadata
            loop_file_path = os.path.join(volume_path, ".loop_file")
            if not os.path.exists(loop_file_path):
                logger.error(f"Loop file metadata not found for volume {volume_path}")
                return False
            
            with open(loop_file_path, "r") as f:
                loop_file = f.read().strip()
            
            if not os.path.exists(loop_file):
                logger.error(f"Loop file not found: {loop_file}")
                return False
            
            # Ensure the mount directory exists
            os.makedirs(mount_path, exist_ok=True)
            
            # Mount the loop file
            try:
                result = subprocess.run(
                    ["mount", "-o", "loop", loop_file, mount_path],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to mount loop device: {e.stderr}")
                raise
            
            logger.info(f"Mounted loop device volume from {volume_path} to {mount_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to mount loop device volume: {e}")
            return False
    
    def unmount_volume(self, mount_path: str) -> bool:
        """
        Unmount a volume using a loop device.
        
        Args:
            mount_path: Path where the volume is mounted
            
        Returns:
            bool: Success or failure
        """
        try:
            # Check if the path is mounted
            if not os.path.ismount(mount_path):
                logger.warning(f"Path is not a mount point: {mount_path}")
                return True
            
            # Unmount the loop device
            try:
                result = subprocess.run(
                    ["umount", mount_path],
                    check=True,
                    capture_output=True,
                    text=True
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to unmount loop device: {e.stderr}")
                raise
            
            logger.info(f"Unmounted loop device volume from {mount_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to unmount loop device volume: {e}")
            return False
    
    def get_volume_info(self, volume_path: str) -> Dict[str, Any]:
        """
        Get information about a volume using a loop device.
        
        Args:
            volume_path: Path to the volume
            
        Returns:
            Dict with volume information
        """
        try:
            info = {
                "path": volume_path,
                "exists": os.path.exists(volume_path),
                "size": "0",
                "used": "0",
                "available": "0",
                "type": "loop"
            }
            
            if info["exists"]:
                # Get loop file path from metadata
                loop_file_path = os.path.join(volume_path, ".loop_file")
                if os.path.exists(loop_file_path):
                    with open(loop_file_path, "r") as f:
                        loop_file = f.read().strip()
                    
                    if os.path.exists(loop_file):
                        # Get file size
                        size = os.path.getsize(loop_file)
                        info["size"] = self.format_size(size)
                        
                        # Check if it's mounted
                        try:
                            result = subprocess.run(
                                ["df", "--output=used,avail", loop_file],
                                check=True,
                                capture_output=True,
                                text=True
                            )
                            
                            lines = result.stdout.strip().split("\n")
                            if len(lines) > 1:
                                used, available = lines[1].split()
                                info["used"] = self.format_size(int(used) * 1024)
                                info["available"] = self.format_size(int(available) * 1024)
                        except Exception as e:
                            logger.warning(f"Failed to get loop device usage: {e}")
            
            return info
        except Exception as e:
            logger.error(f"Failed to get loop device volume info: {e}")
            return {"path": volume_path, "exists": False, "error": str(e)}


class VolumeManager:
    """
    Volume manager for the KOS storage subsystem.
    
    This class provides a unified interface for working with volumes
    using different storage drivers.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VolumeManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the volume manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._drivers = {
            "local": LocalDriver(),
            "loop": LoopDeviceDriver()
        }
        self._default_driver = "local"
    
    def get_driver(self, driver_type: str) -> StorageDriver:
        """
        Get a storage driver by type.
        
        Args:
            driver_type: Driver type (e.g., "local", "loop")
            
        Returns:
            StorageDriver instance
            
        Raises:
            StorageDriverException: If the driver type is not supported
        """
        if driver_type not in self._drivers:
            raise StorageDriverException(f"Unsupported driver type: {driver_type}")
        
        return self._drivers[driver_type]
    
    def create_volume(self, volume_path: str, size: str, driver_type: Optional[str] = None) -> bool:
        """
        Create a new volume.
        
        Args:
            volume_path: Path to the volume
            size: Volume size (e.g., "1Gi")
            driver_type: Driver type, or None for default
            
        Returns:
            bool: Success or failure
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.create_volume(volume_path, size)
    
    def delete_volume(self, volume_path: str, driver_type: Optional[str] = None) -> bool:
        """
        Delete a volume.
        
        Args:
            volume_path: Path to the volume
            driver_type: Driver type, or None for default
            
        Returns:
            bool: Success or failure
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.delete_volume(volume_path)
    
    def resize_volume(self, volume_path: str, new_size: str, driver_type: Optional[str] = None) -> bool:
        """
        Resize a volume.
        
        Args:
            volume_path: Path to the volume
            new_size: New volume size (e.g., "2Gi")
            driver_type: Driver type, or None for default
            
        Returns:
            bool: Success or failure
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.resize_volume(volume_path, new_size)
    
    def mount_volume(self, volume_path: str, mount_path: str, driver_type: Optional[str] = None) -> bool:
        """
        Mount a volume.
        
        Args:
            volume_path: Path to the volume
            mount_path: Path to mount the volume at
            driver_type: Driver type, or None for default
            
        Returns:
            bool: Success or failure
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.mount_volume(volume_path, mount_path)
    
    def unmount_volume(self, mount_path: str, driver_type: Optional[str] = None) -> bool:
        """
        Unmount a volume.
        
        Args:
            mount_path: Path where the volume is mounted
            driver_type: Driver type, or None for default
            
        Returns:
            bool: Success or failure
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.unmount_volume(mount_path)
    
    def get_volume_info(self, volume_path: str, driver_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a volume.
        
        Args:
            volume_path: Path to the volume
            driver_type: Driver type, or None for default
            
        Returns:
            Dict with volume information
        """
        driver = self.get_driver(driver_type or self._default_driver)
        return driver.get_volume_info(volume_path)

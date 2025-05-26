"""
Persistent Volume Management for KOS Orchestration System

This module implements persistent volume management for the KOS orchestration system,
providing storage capabilities for containers.
"""

import os
import json
import uuid
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Set, Tuple, Union

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
VOLUME_ROOT = os.path.join(ORCHESTRATION_ROOT, 'volumes')
PV_PATH = os.path.join(VOLUME_ROOT, 'persistentvolumes')
PVC_PATH = os.path.join(VOLUME_ROOT, 'persistentvolumeclaims')

# Ensure directories exist
os.makedirs(PV_PATH, exist_ok=True)
os.makedirs(PVC_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class VolumeMode(str):
    """Volume access modes."""
    FILESYSTEM = "Filesystem"
    BLOCK = "Block"


class AccessMode(str):
    """Volume access modes."""
    READ_WRITE_ONCE = "ReadWriteOnce"
    READ_ONLY_MANY = "ReadOnlyMany"
    READ_WRITE_MANY = "ReadWriteMany"


class PersistentVolumePhase(str):
    """Persistent volume phase."""
    AVAILABLE = "Available"
    BOUND = "Bound"
    RELEASED = "Released"
    FAILED = "Failed"


class PersistentVolumeClaimPhase(str):
    """Persistent volume claim phase."""
    PENDING = "Pending"
    BOUND = "Bound"
    LOST = "Lost"


class VolumeSpec:
    """Specification for a persistent volume."""
    
    def __init__(self, capacity: Dict[str, str] = None,
                 access_modes: List[str] = None,
                 volume_mode: str = VolumeMode.FILESYSTEM,
                 storage_class: str = "",
                 local_path: str = "",
                 mount_options: List[str] = None):
        """
        Initialize a volume specification.
        
        Args:
            capacity: Volume capacity
            access_modes: Access modes
            volume_mode: Volume mode
            storage_class: Storage class
            local_path: Local path for the volume
            mount_options: Mount options
        """
        self.capacity = capacity or {"storage": "1Gi"}
        self.access_modes = access_modes or [AccessMode.READ_WRITE_ONCE]
        self.volume_mode = volume_mode
        self.storage_class = storage_class
        self.local_path = local_path
        self.mount_options = mount_options or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the volume specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "capacity": self.capacity,
            "accessModes": self.access_modes,
            "volumeMode": self.volume_mode,
            "storageClass": self.storage_class,
            "localPath": self.local_path,
            "mountOptions": self.mount_options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VolumeSpec':
        """
        Create a volume specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            VolumeSpec object
        """
        return cls(
            capacity=data.get("capacity", {"storage": "1Gi"}),
            access_modes=data.get("accessModes", [AccessMode.READ_WRITE_ONCE]),
            volume_mode=data.get("volumeMode", VolumeMode.FILESYSTEM),
            storage_class=data.get("storageClass", ""),
            local_path=data.get("localPath", ""),
            mount_options=data.get("mountOptions", [])
        )


class PersistentVolumeClaimSpec:
    """Specification for a persistent volume claim."""
    
    def __init__(self, access_modes: List[str] = None,
                 volume_mode: str = VolumeMode.FILESYSTEM,
                 resources: Dict[str, Dict[str, str]] = None,
                 storage_class: str = "",
                 volume_name: str = ""):
        """
        Initialize a persistent volume claim specification.
        
        Args:
            access_modes: Access modes
            volume_mode: Volume mode
            resources: Resource requests
            storage_class: Storage class
            volume_name: Volume name to bind to
        """
        self.access_modes = access_modes or [AccessMode.READ_WRITE_ONCE]
        self.volume_mode = volume_mode
        self.resources = resources or {"requests": {"storage": "1Gi"}}
        self.storage_class = storage_class
        self.volume_name = volume_name
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the PVC specification to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "accessModes": self.access_modes,
            "volumeMode": self.volume_mode,
            "resources": self.resources,
            "storageClass": self.storage_class,
            "volumeName": self.volume_name
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistentVolumeClaimSpec':
        """
        Create a PVC specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PersistentVolumeClaimSpec object
        """
        return cls(
            access_modes=data.get("accessModes", [AccessMode.READ_WRITE_ONCE]),
            volume_mode=data.get("volumeMode", VolumeMode.FILESYSTEM),
            resources=data.get("resources", {"requests": {"storage": "1Gi"}}),
            storage_class=data.get("storageClass", ""),
            volume_name=data.get("volumeName", "")
        )


class PersistentVolume:
    """
    Persistent volume in the KOS orchestration system.
    
    A PersistentVolume (PV) is a piece of storage in the cluster that has been 
    provisioned by an administrator.
    """
    
    def __init__(self, name: str, spec: Optional[VolumeSpec] = None):
        """
        Initialize a persistent volume.
        
        Args:
            name: Volume name
            spec: Volume specification
        """
        self.name = name
        self.spec = spec or VolumeSpec()
        self.metadata = {
            "name": name,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self.status = {
            "phase": PersistentVolumePhase.AVAILABLE,
            "claim": "",
            "reason": "",
            "message": ""
        }
        self._lock = threading.RLock()
        
        # Ensure volume directory exists
        self._ensure_volume_dir()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this persistent volume."""
        return os.path.join(PV_PATH, f"{self.name}.json")
    
    def _volume_dir(self) -> str:
        """Get the directory path for this persistent volume's data."""
        return os.path.join(VOLUME_ROOT, 'data', self.name)
    
    def _ensure_volume_dir(self) -> None:
        """Ensure the volume directory exists."""
        if not self.spec.local_path:
            # Create a directory for this volume
            volume_dir = self._volume_dir()
            os.makedirs(volume_dir, exist_ok=True)
            self.spec.local_path = volume_dir
    
    def _load(self) -> bool:
        """
        Load the persistent volume from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update spec
            spec_data = data.get("spec", {})
            self.spec = VolumeSpec.from_dict(spec_data)
            
            # Update status
            self.status = data.get("status", self.status)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load persistent volume {self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the persistent volume to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                data = {
                    "kind": "PersistentVolume",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status
                }
                
                with open(self._file_path(), 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save persistent volume {self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the persistent volume.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Check if the volume is bound
            if self.status["phase"] == PersistentVolumePhase.BOUND:
                logger.error(f"Cannot delete bound persistent volume {self.name}")
                return False
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete persistent volume {self.name}: {e}")
            return False
    
    def bind(self, claim_name: str, claim_namespace: str) -> bool:
        """
        Bind the persistent volume to a claim.
        
        Args:
            claim_name: Claim name
            claim_namespace: Claim namespace
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update status
                self.status["phase"] = PersistentVolumePhase.BOUND
                self.status["claim"] = f"{claim_namespace}/{claim_name}"
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to bind persistent volume {self.name}: {e}")
            return False
    
    def release(self) -> bool:
        """
        Release the persistent volume from a claim.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update status
                self.status["phase"] = PersistentVolumePhase.RELEASED
                self.status["claim"] = ""
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to release persistent volume {self.name}: {e}")
            return False
    
    def reclaim(self) -> bool:
        """
        Reclaim the persistent volume.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update status
                self.status["phase"] = PersistentVolumePhase.AVAILABLE
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to reclaim persistent volume {self.name}: {e}")
            return False
    
    @staticmethod
    def list_volumes() -> List['PersistentVolume']:
        """
        List all persistent volumes.
        
        Returns:
            List of persistent volumes
        """
        volumes = []
        
        try:
            for filename in os.listdir(PV_PATH):
                if not filename.endswith('.json'):
                    continue
                
                volume_name = filename[:-5]  # Remove .json extension
                volume = PersistentVolume(volume_name)
                volumes.append(volume)
        except Exception as e:
            logger.error(f"Failed to list persistent volumes: {e}")
        
        return volumes
    
    @staticmethod
    def get_volume(name: str) -> Optional['PersistentVolume']:
        """
        Get a persistent volume by name.
        
        Args:
            name: Volume name
            
        Returns:
            PersistentVolume object or None if not found
        """
        volume = PersistentVolume(name)
        
        if os.path.exists(volume._file_path()):
            return volume
        
        return None


class PersistentVolumeClaim:
    """
    Persistent volume claim in the KOS orchestration system.
    
    A PersistentVolumeClaim (PVC) is a request for storage by a user.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[PersistentVolumeClaimSpec] = None):
        """
        Initialize a persistent volume claim.
        
        Args:
            name: Claim name
            namespace: Namespace
            spec: Claim specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or PersistentVolumeClaimSpec()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self.status = {
            "phase": PersistentVolumeClaimPhase.PENDING,
            "accessModes": [],
            "capacity": {},
            "volume": ""
        }
        self._lock = threading.RLock()
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this persistent volume claim."""
        return os.path.join(PVC_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the persistent volume claim from disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        if not os.path.exists(file_path):
            return False
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Update metadata
            self.metadata = data.get("metadata", self.metadata)
            
            # Update spec
            spec_data = data.get("spec", {})
            self.spec = PersistentVolumeClaimSpec.from_dict(spec_data)
            
            # Update status
            self.status = data.get("status", self.status)
            
            return True
        except Exception as e:
            logger.error(f"Failed to load persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the persistent volume claim to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "PersistentVolumeClaim",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the persistent volume claim.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Release the bound volume if any
            if self.status["phase"] == PersistentVolumeClaimPhase.BOUND and self.status["volume"]:
                volume = PersistentVolume.get_volume(self.status["volume"])
                if volume:
                    volume.release()
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    def bind(self, volume: PersistentVolume) -> bool:
        """
        Bind the persistent volume claim to a volume.
        
        Args:
            volume: Persistent volume
            
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Update status
                self.status["phase"] = PersistentVolumeClaimPhase.BOUND
                self.status["accessModes"] = volume.spec.access_modes
                self.status["capacity"] = volume.spec.capacity
                self.status["volume"] = volume.name
                
                # Bind the volume
                volume.bind(self.name, self.namespace)
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to bind persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def list_claims(namespace: Optional[str] = None) -> List['PersistentVolumeClaim']:
        """
        List all persistent volume claims.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of persistent volume claims
        """
        claims = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = PVC_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List claims in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(PVC_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    claim_name = filename[:-5]  # Remove .json extension
                    claim = PersistentVolumeClaim(claim_name, ns)
                    claims.append(claim)
        except Exception as e:
            logger.error(f"Failed to list persistent volume claims: {e}")
        
        return claims
    
    @staticmethod
    def get_claim(name: str, namespace: str = "default") -> Optional['PersistentVolumeClaim']:
        """
        Get a persistent volume claim by name and namespace.
        
        Args:
            name: Claim name
            namespace: Namespace
            
        Returns:
            PersistentVolumeClaim object or None if not found
        """
        claim = PersistentVolumeClaim(name, namespace)
        
        if os.path.exists(claim._file_path()):
            return claim
        
        return None


class VolumeController:
    """
    Controller for persistent volumes in the KOS orchestration system.
    
    This class manages the binding of persistent volume claims to persistent volumes.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VolumeController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the volume controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the volume controller.
        
        Returns:
            bool: Success or failure
        """
        if self._reconcile_thread and self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.clear()
        self._reconcile_thread = threading.Thread(
            target=self._reconcile_loop,
            daemon=True
        )
        self._reconcile_thread.start()
        
        return True
    
    def stop(self) -> bool:
        """
        Stop the volume controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the volume controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in volume controller reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(30)  # Check every 30 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile all persistent volume claims.
        
        Returns:
            bool: Success or failure
        """
        try:
            # List all persistent volume claims
            claims = PersistentVolumeClaim.list_claims()
            
            # Process pending claims
            for claim in claims:
                try:
                    if claim.status["phase"] == PersistentVolumeClaimPhase.PENDING:
                        self._bind_claim(claim)
                except Exception as e:
                    logger.error(f"Failed to reconcile claim {claim.namespace}/{claim.name}: {e}")
            
            # List all persistent volumes
            volumes = PersistentVolume.list_volumes()
            
            # Process released volumes
            for volume in volumes:
                try:
                    if volume.status["phase"] == PersistentVolumePhase.RELEASED:
                        volume.reclaim()
                except Exception as e:
                    logger.error(f"Failed to reconcile volume {volume.name}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile volumes: {e}")
            return False
    
    def _bind_claim(self, claim: PersistentVolumeClaim) -> bool:
        """
        Bind a persistent volume claim to a suitable volume.
        
        Args:
            claim: Persistent volume claim
            
        Returns:
            bool: Success or failure
        """
        # Check if the claim already specifies a volume
        if claim.spec.volume_name:
            volume = PersistentVolume.get_volume(claim.spec.volume_name)
            if volume and volume.status["phase"] == PersistentVolumePhase.AVAILABLE:
                return claim.bind(volume)
            
            return False
        
        # Find a suitable volume
        volumes = PersistentVolume.list_volumes()
        
        for volume in volumes:
            # Skip volumes that are not available
            if volume.status["phase"] != PersistentVolumePhase.AVAILABLE:
                continue
            
            # Check storage class
            if claim.spec.storage_class and claim.spec.storage_class != volume.spec.storage_class:
                continue
            
            # Check volume mode
            if claim.spec.volume_mode != volume.spec.volume_mode:
                continue
            
            # Check access modes
            if not all(mode in volume.spec.access_modes for mode in claim.spec.access_modes):
                continue
            
            # Check capacity
            claim_storage = claim.spec.resources.get("requests", {}).get("storage", "0")
            volume_storage = volume.spec.capacity.get("storage", "0")
            
            if self._parse_storage(claim_storage) > self._parse_storage(volume_storage):
                continue
            
            # Bind the claim to the volume
            return claim.bind(volume)
        
        return False
    
    def _parse_storage(self, storage: str) -> int:
        """
        Parse storage value to bytes.
        
        Args:
            storage: Storage value (e.g., "1Gi", "500Mi")
            
        Returns:
            Storage value in bytes
        """
        try:
            if storage.endswith("Ki"):
                return int(storage[:-2]) * 1024
            elif storage.endswith("Mi"):
                return int(storage[:-2]) * 1024 * 1024
            elif storage.endswith("Gi"):
                return int(storage[:-2]) * 1024 * 1024 * 1024
            elif storage.endswith("Ti"):
                return int(storage[:-2]) * 1024 * 1024 * 1024 * 1024
            
            return int(storage)
        except (ValueError, TypeError):
            return 0
    
    @staticmethod
    def instance() -> 'VolumeController':
        """
        Get the singleton instance.
        
        Returns:
            VolumeController instance
        """
        return VolumeController()


def get_volume_controller() -> VolumeController:
    """
    Get the volume controller instance.
    
    Returns:
        VolumeController instance
    """
    return VolumeController.instance()


def start_volume_controller() -> bool:
    """
    Start the volume controller.
    
    Returns:
        bool: Success or failure
    """
    controller = VolumeController.instance()
    return controller.start()


def stop_volume_controller() -> bool:
    """
    Stop the volume controller.
    
    Returns:
        bool: Success or failure
    """
    controller = VolumeController.instance()
    return controller.stop()

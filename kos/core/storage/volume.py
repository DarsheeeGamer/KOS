"""
Volume Management for KOS Storage Subsystem

This module implements persistent volume management for the KOS storage subsystem,
including persistent volumes, persistent volume claims, and storage classes.
"""

import os
import uuid
import json
import time
import shutil
import logging
import threading
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Union, Any

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
VOLUMES_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/storage/volumes')
VOLUME_CLAIMS_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/storage/claims')
STORAGE_CLASSES_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/storage/classes')
VOLUME_DATA_DIR = os.path.join(KOS_ROOT, 'var/lib/kos/storage/data')

# Ensure directories exist
for directory in [VOLUMES_DIR, VOLUME_CLAIMS_DIR, STORAGE_CLASSES_DIR, VOLUME_DATA_DIR]:
    os.makedirs(directory, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class VolumeStatus(str, Enum):
    """Status of a persistent volume."""
    AVAILABLE = "Available"
    BOUND = "Bound"
    RELEASED = "Released"
    FAILED = "Failed"


class AccessMode(str, Enum):
    """Access modes for persistent volumes."""
    READ_WRITE_ONCE = "ReadWriteOnce"
    READ_ONLY_MANY = "ReadOnlyMany"
    READ_WRITE_MANY = "ReadWriteMany"


class PersistentVolumeReclaimPolicy(str, Enum):
    """Reclaim policies for persistent volumes."""
    RETAIN = "Retain"
    DELETE = "Delete"
    RECYCLE = "Recycle"


class StorageClass:
    """
    Storage class for persistent volumes.
    
    A StorageClass provides a way for administrators to describe the "classes"
    of storage they offer.
    """
    
    def __init__(self, name: str, provisioner: str = "kos.local",
                 parameters: Optional[Dict[str, str]] = None,
                 reclaim_policy: PersistentVolumeReclaimPolicy = PersistentVolumeReclaimPolicy.DELETE,
                 mount_options: Optional[List[str]] = None,
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 uid: Optional[str] = None):
        """
        Initialize a storage class.
        
        Args:
            name: Storage class name
            provisioner: Volume provisioner
            parameters: Provisioner-specific parameters
            reclaim_policy: Volume reclaim policy
            mount_options: Mount options
            labels: Labels
            annotations: Annotations
            uid: Unique ID
        """
        self.name = name
        self.provisioner = provisioner
        self.parameters = parameters or {}
        self.reclaim_policy = reclaim_policy
        self.mount_options = mount_options or []
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.uid = uid or str(uuid.uuid4())
        self.creation_timestamp = time.time()
        
        # Runtime-specific fields (not serialized)
        self._lock = threading.Lock()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the storage class to a dictionary.
        
        Returns:
            Dict representation of the storage class
        """
        return {
            "kind": "StorageClass",
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "labels": self.labels,
                "annotations": self.annotations
            },
            "provisioner": self.provisioner,
            "parameters": self.parameters,
            "reclaimPolicy": self.reclaim_policy,
            "mountOptions": self.mount_options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StorageClass':
        """
        Create a storage class from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            StorageClass object
        """
        metadata = data.get("metadata", {})
        
        return cls(
            name=metadata.get("name", ""),
            provisioner=data.get("provisioner", "kos.local"),
            parameters=data.get("parameters", {}),
            reclaim_policy=data.get("reclaimPolicy", PersistentVolumeReclaimPolicy.DELETE),
            mount_options=data.get("mountOptions", []),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            uid=metadata.get("uid", str(uuid.uuid4()))
        )
    
    def save(self) -> bool:
        """
        Save the storage class state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            storage_class_file = os.path.join(STORAGE_CLASSES_DIR, f"{self.name}.json")
            with open(storage_class_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved storage class {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save storage class {self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str) -> Optional['StorageClass']:
        """
        Load a storage class from disk.
        
        Args:
            name: Storage class name
            
        Returns:
            StorageClass object or None if not found
        """
        storage_class_file = os.path.join(STORAGE_CLASSES_DIR, f"{name}.json")
        if not os.path.exists(storage_class_file):
            logger.error(f"Storage class not found: {name}")
            return None
        
        try:
            with open(storage_class_file, 'r') as f:
                data = json.load(f)
            
            return StorageClass.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load storage class {name}: {e}")
            return None
    
    @staticmethod
    def list_storage_classes() -> List['StorageClass']:
        """
        List all storage classes.
        
        Returns:
            List of StorageClass objects
        """
        storage_classes = []
        
        if not os.path.exists(STORAGE_CLASSES_DIR):
            return []
        
        for filename in os.listdir(STORAGE_CLASSES_DIR):
            if not filename.endswith('.json'):
                continue
            
            storage_class_file = os.path.join(STORAGE_CLASSES_DIR, filename)
            try:
                with open(storage_class_file, 'r') as f:
                    data = json.load(f)
                
                storage_classes.append(StorageClass.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load storage class from {filename}: {e}")
        
        return storage_classes
    
    def delete(self) -> bool:
        """
        Delete the storage class from disk.
        
        Returns:
            bool: Success or failure
        """
        storage_class_file = os.path.join(STORAGE_CLASSES_DIR, f"{self.name}.json")
        if not os.path.exists(storage_class_file):
            logger.warning(f"Storage class not found for deletion: {self.name}")
            return False
        
        try:
            os.remove(storage_class_file)
            logger.info(f"Deleted storage class {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete storage class {self.name}: {e}")
            return False


class PersistentVolume:
    """
    Persistent volume in the KOS storage subsystem.
    
    A PersistentVolume (PV) is a piece of storage in the cluster that has been
    provisioned by an administrator or dynamically provisioned using a StorageClass.
    """
    
    def __init__(self, name: str, storage: str,
                 storage_class: Optional[str] = None,
                 access_modes: Optional[List[AccessMode]] = None,
                 reclaim_policy: PersistentVolumeReclaimPolicy = PersistentVolumeReclaimPolicy.DELETE,
                 status: VolumeStatus = VolumeStatus.AVAILABLE,
                 claim_ref: Optional[Dict[str, str]] = None,
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 uid: Optional[str] = None):
        """
        Initialize a persistent volume.
        
        Args:
            name: Volume name
            storage: Storage size (e.g., "1Gi")
            storage_class: Storage class name
            access_modes: Access modes
            reclaim_policy: Reclaim policy
            status: Volume status
            claim_ref: Reference to the PVC that bound this volume
            labels: Labels
            annotations: Annotations
            uid: Unique ID
        """
        self.name = name
        self.storage = storage
        self.storage_class = storage_class
        self.access_modes = access_modes or [AccessMode.READ_WRITE_ONCE]
        self.reclaim_policy = reclaim_policy
        self.status = status
        self.claim_ref = claim_ref
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.uid = uid or str(uuid.uuid4())
        self.creation_timestamp = time.time()
        
        # Runtime-specific fields (not serialized)
        self._lock = threading.Lock()
        self._data_path = os.path.join(VOLUME_DATA_DIR, self.uid)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the persistent volume to a dictionary.
        
        Returns:
            Dict representation of the persistent volume
        """
        return {
            "kind": "PersistentVolume",
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "labels": self.labels,
                "annotations": self.annotations
            },
            "spec": {
                "capacity": {
                    "storage": self.storage
                },
                "accessModes": self.access_modes,
                "persistentVolumeReclaimPolicy": self.reclaim_policy,
                "storageClassName": self.storage_class
            },
            "status": {
                "phase": self.status,
                "claimRef": self.claim_ref
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistentVolume':
        """
        Create a persistent volume from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PersistentVolume object
        """
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})
        
        capacity = spec.get("capacity", {})
        storage = capacity.get("storage", "1Gi")
        
        return cls(
            name=metadata.get("name", ""),
            storage=storage,
            storage_class=spec.get("storageClassName"),
            access_modes=spec.get("accessModes", [AccessMode.READ_WRITE_ONCE]),
            reclaim_policy=spec.get("persistentVolumeReclaimPolicy", PersistentVolumeReclaimPolicy.DELETE),
            status=status.get("phase", VolumeStatus.AVAILABLE),
            claim_ref=status.get("claimRef"),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            uid=metadata.get("uid", str(uuid.uuid4()))
        )
    
    def save(self) -> bool:
        """
        Save the persistent volume state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            volume_file = os.path.join(VOLUMES_DIR, f"{self.name}.json")
            with open(volume_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved persistent volume {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save persistent volume {self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str) -> Optional['PersistentVolume']:
        """
        Load a persistent volume from disk.
        
        Args:
            name: Volume name
            
        Returns:
            PersistentVolume object or None if not found
        """
        volume_file = os.path.join(VOLUMES_DIR, f"{name}.json")
        if not os.path.exists(volume_file):
            logger.error(f"Persistent volume not found: {name}")
            return None
        
        try:
            with open(volume_file, 'r') as f:
                data = json.load(f)
            
            return PersistentVolume.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load persistent volume {name}: {e}")
            return None
    
    @staticmethod
    def list_volumes() -> List['PersistentVolume']:
        """
        List all persistent volumes.
        
        Returns:
            List of PersistentVolume objects
        """
        volumes = []
        
        if not os.path.exists(VOLUMES_DIR):
            return []
        
        for filename in os.listdir(VOLUMES_DIR):
            if not filename.endswith('.json'):
                continue
            
            volume_file = os.path.join(VOLUMES_DIR, filename)
            try:
                with open(volume_file, 'r') as f:
                    data = json.load(f)
                
                volumes.append(PersistentVolume.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load persistent volume from {filename}: {e}")
        
        return volumes
    
    def delete(self) -> bool:
        """
        Delete the persistent volume from disk.
        
        Returns:
            bool: Success or failure
        """
        volume_file = os.path.join(VOLUMES_DIR, f"{self.name}.json")
        if not os.path.exists(volume_file):
            logger.warning(f"Persistent volume not found for deletion: {self.name}")
            return False
        
        try:
            # Delete volume data if it exists
            if os.path.exists(self._data_path):
                shutil.rmtree(self._data_path)
            
            # Delete volume metadata
            os.remove(volume_file)
            logger.info(f"Deleted persistent volume {self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete persistent volume {self.name}: {e}")
            return False
    
    def get_data_path(self) -> str:
        """
        Get the path to the volume data.
        
        Returns:
            Path to volume data
        """
        # Create data directory if it doesn't exist
        os.makedirs(self._data_path, exist_ok=True)
        
        return self._data_path
    
    def bind(self, claim_namespace: str, claim_name: str, claim_uid: str) -> bool:
        """
        Bind this volume to a claim.
        
        Args:
            claim_namespace: Namespace of the claim
            claim_name: Name of the claim
            claim_uid: UID of the claim
            
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if self.status != VolumeStatus.AVAILABLE:
                logger.error(f"Cannot bind volume {self.name}: status is {self.status}")
                return False
            
            # Set claim reference
            self.claim_ref = {
                "namespace": claim_namespace,
                "name": claim_name,
                "uid": claim_uid
            }
            
            # Update status
            self.status = VolumeStatus.BOUND
            
            # Save changes
            return self.save()
    
    def release(self) -> bool:
        """
        Release this volume from its claim.
        
        Returns:
            bool: Success or failure
        """
        with self._lock:
            if self.status != VolumeStatus.BOUND:
                logger.error(f"Cannot release volume {self.name}: status is {self.status}")
                return False
            
            # Handle according to reclaim policy
            if self.reclaim_policy == PersistentVolumeReclaimPolicy.RETAIN:
                # Keep the volume but mark it as released
                self.status = VolumeStatus.RELEASED
                # Keep claim_ref so we know which claim previously bound this volume
                
                # Save changes
                return self.save()
                
            elif self.reclaim_policy == PersistentVolumeReclaimPolicy.DELETE:
                # Delete the volume
                return self.delete()
                
            elif self.reclaim_policy == PersistentVolumeReclaimPolicy.RECYCLE:
                # Clear data but keep the volume
                try:
                    if os.path.exists(self._data_path):
                        for item in os.listdir(self._data_path):
                            item_path = os.path.join(self._data_path, item)
                            if os.path.isfile(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                    
                    # Clear claim reference
                    self.claim_ref = None
                    
                    # Update status
                    self.status = VolumeStatus.AVAILABLE
                    
                    # Save changes
                    return self.save()
                except Exception as e:
                    logger.error(f"Failed to recycle volume {self.name}: {e}")
                    
                    # Mark as failed
                    self.status = VolumeStatus.FAILED
                    self.save()
                    
                    return False
            
            return False


class PersistentVolumeClaim:
    """
    Persistent volume claim in the KOS storage subsystem.
    
    A PersistentVolumeClaim (PVC) is a request for storage by a user.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 storage_class: Optional[str] = None,
                 access_modes: Optional[List[str]] = None,
                 storage: str = "1Gi",
                 volume_name: Optional[str] = None,
                 status: VolumeStatus = VolumeStatus.AVAILABLE,
                 labels: Optional[Dict[str, str]] = None,
                 annotations: Optional[Dict[str, str]] = None,
                 uid: Optional[str] = None):
        """
        Initialize a persistent volume claim.
        
        Args:
            name: Claim name
            namespace: Namespace
            storage_class: Storage class name
            access_modes: Access modes
            storage: Storage size (e.g., "1Gi")
            volume_name: Name of the volume bound to this claim
            status: Claim status
            labels: Labels
            annotations: Annotations
            uid: Unique ID
        """
        self.name = name
        self.namespace = namespace
        self.storage_class = storage_class
        self.access_modes = access_modes or [AccessMode.READ_WRITE_ONCE]
        self.storage = storage
        self.volume_name = volume_name
        self.status = status
        self.labels = labels or {}
        self.annotations = annotations or {}
        self.uid = uid or str(uuid.uuid4())
        self.creation_timestamp = time.time()
        
        # Runtime-specific fields (not serialized)
        self._lock = threading.Lock()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the persistent volume claim to a dictionary.
        
        Returns:
            Dict representation of the persistent volume claim
        """
        return {
            "kind": "PersistentVolumeClaim",
            "apiVersion": "v1",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "uid": self.uid,
                "creationTimestamp": self.creation_timestamp,
                "labels": self.labels,
                "annotations": self.annotations
            },
            "spec": {
                "accessModes": self.access_modes,
                "resources": {
                    "requests": {
                        "storage": self.storage
                    }
                },
                "storageClassName": self.storage_class,
                "volumeName": self.volume_name
            },
            "status": {
                "phase": self.status
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PersistentVolumeClaim':
        """
        Create a persistent volume claim from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            PersistentVolumeClaim object
        """
        metadata = data.get("metadata", {})
        spec = data.get("spec", {})
        status = data.get("status", {})
        
        resources = spec.get("resources", {})
        requests = resources.get("requests", {})
        storage = requests.get("storage", "1Gi")
        
        return cls(
            name=metadata.get("name", ""),
            namespace=metadata.get("namespace", "default"),
            storage_class=spec.get("storageClassName"),
            access_modes=spec.get("accessModes", [AccessMode.READ_WRITE_ONCE]),
            storage=storage,
            volume_name=spec.get("volumeName"),
            status=status.get("phase", VolumeStatus.AVAILABLE),
            labels=metadata.get("labels", {}),
            annotations=metadata.get("annotations", {}),
            uid=metadata.get("uid", str(uuid.uuid4()))
        )
    
    def save(self) -> bool:
        """
        Save the persistent volume claim state to disk.
        
        Returns:
            bool: Success or failure
        """
        try:
            namespace_dir = os.path.join(VOLUME_CLAIMS_DIR, self.namespace)
            os.makedirs(namespace_dir, exist_ok=True)
            
            claim_file = os.path.join(namespace_dir, f"{self.name}.json")
            with open(claim_file, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"Saved persistent volume claim {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    @staticmethod
    def load(name: str, namespace: str = "default") -> Optional['PersistentVolumeClaim']:
        """
        Load a persistent volume claim from disk.
        
        Args:
            name: Claim name
            namespace: Namespace
            
        Returns:
            PersistentVolumeClaim object or None if not found
        """
        claim_file = os.path.join(VOLUME_CLAIMS_DIR, namespace, f"{name}.json")
        if not os.path.exists(claim_file):
            logger.error(f"Persistent volume claim not found: {namespace}/{name}")
            return None
        
        try:
            with open(claim_file, 'r') as f:
                data = json.load(f)
            
            return PersistentVolumeClaim.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load persistent volume claim {namespace}/{name}: {e}")
            return None
    
    @staticmethod
    def list_claims(namespace: Optional[str] = None) -> List['PersistentVolumeClaim']:
        """
        List persistent volume claims.
        
        Args:
            namespace: Namespace to list claims from, or None for all namespaces
            
        Returns:
            List of PersistentVolumeClaim objects
        """
        claims = []
        
        if namespace:
            # List claims in a specific namespace
            namespace_dir = os.path.join(VOLUME_CLAIMS_DIR, namespace)
            if not os.path.exists(namespace_dir):
                return []
            
            namespaces = [namespace]
        else:
            # List claims in all namespaces
            if not os.path.exists(VOLUME_CLAIMS_DIR):
                return []
            
            namespaces = os.listdir(VOLUME_CLAIMS_DIR)
        
        for ns in namespaces:
            namespace_dir = os.path.join(VOLUME_CLAIMS_DIR, ns)
            if not os.path.isdir(namespace_dir):
                continue
            
            for filename in os.listdir(namespace_dir):
                if not filename.endswith('.json'):
                    continue
                
                claim_file = os.path.join(namespace_dir, filename)
                try:
                    with open(claim_file, 'r') as f:
                        data = json.load(f)
                    
                    claims.append(PersistentVolumeClaim.from_dict(data))
                except Exception as e:
                    logger.error(f"Failed to load persistent volume claim from {claim_file}: {e}")
        
        return claims
    
    def delete(self) -> bool:
        """
        Delete the persistent volume claim from disk.
        
        Returns:
            bool: Success or failure
        """
        claim_file = os.path.join(VOLUME_CLAIMS_DIR, self.namespace, f"{self.name}.json")
        if not os.path.exists(claim_file):
            logger.warning(f"Persistent volume claim not found for deletion: {self.namespace}/{self.name}")
            return False
        
        try:
            # Release the bound volume if there is one
            if self.volume_name and self.status == VolumeStatus.BOUND:
                volume = PersistentVolume.load(self.volume_name)
                if volume:
                    volume.release()
            
            # Delete claim metadata
            os.remove(claim_file)
            logger.info(f"Deleted persistent volume claim {self.namespace}/{self.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    def create(self) -> bool:
        """
        Create a new persistent volume claim.
        
        This method will attempt to find a suitable volume to bind to,
        or create one if a dynamic provisioner is available.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Save the claim first
            if not self.save():
                return False
            
            # Check if a specific volume was requested
            if self.volume_name:
                volume = PersistentVolume.load(self.volume_name)
                if not volume:
                    logger.error(f"Requested volume {self.volume_name} not found")
                    self.status = VolumeStatus.FAILED
                    self.save()
                    return False
                
                # Bind to the requested volume
                if volume.bind(self.namespace, self.name, self.uid):
                    self.status = VolumeStatus.BOUND
                    self.save()
                    return True
                else:
                    logger.error(f"Failed to bind to volume {self.volume_name}")
                    self.status = VolumeStatus.FAILED
                    self.save()
                    return False
            
            # Look for a matching volume
            volumes = PersistentVolume.list_volumes()
            for volume in volumes:
                # Skip volumes that are not available
                if volume.status != VolumeStatus.AVAILABLE:
                    continue
                
                # Check storage class
                if self.storage_class and volume.storage_class != self.storage_class:
                    continue
                
                # Check access modes
                if not all(mode in volume.access_modes for mode in self.access_modes):
                    continue
                
                # TODO: Check storage size (requires parsing storage size strings)
                
                # Bind to this volume
                if volume.bind(self.namespace, self.name, self.uid):
                    self.volume_name = volume.name
                    self.status = VolumeStatus.BOUND
                    self.save()
                    return True
            
            # No suitable volume found, try dynamic provisioning
            if self.storage_class:
                storage_class = StorageClass.load(self.storage_class)
                if storage_class and storage_class.provisioner == "kos.local":
                    # Create a new volume
                    volume = PersistentVolume(
                        name=f"pv-{self.uid[:8]}",
                        storage=self.storage,
                        storage_class=self.storage_class,
                        access_modes=self.access_modes,
                        reclaim_policy=storage_class.reclaim_policy
                    )
                    
                    if volume.save():
                        # Bind to the new volume
                        if volume.bind(self.namespace, self.name, self.uid):
                            self.volume_name = volume.name
                            self.status = VolumeStatus.BOUND
                            self.save()
                            return True
            
            # Could not find or provision a volume
            logger.warning(f"No suitable volume found for claim {self.namespace}/{self.name}")
            return True  # Claim was created, but not bound
            
        except Exception as e:
            logger.error(f"Failed to create persistent volume claim {self.namespace}/{self.name}: {e}")
            return False
    
    def get_volume_path(self) -> Optional[str]:
        """
        Get the path to the volume data.
        
        Returns:
            Path to volume data or None if not bound
        """
        if not self.volume_name or self.status != VolumeStatus.BOUND:
            logger.error(f"Claim {self.namespace}/{self.name} is not bound to a volume")
            return None
        
        volume = PersistentVolume.load(self.volume_name)
        if not volume:
            logger.error(f"Bound volume {self.volume_name} not found")
            return None
        
        return volume.get_data_path()

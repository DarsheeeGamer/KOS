"""
Controller Manager for KOS Orchestration System

This module implements the controller manager for the KOS orchestration system,
which manages the lifecycle of various controllers such as ReplicaSet, Deployment,
and StatefulSet controllers.
"""

import os
import json
import time
import logging
import threading
import signal
from typing import Dict, List, Any, Optional, Set, Tuple

from kos.core.orchestration.controllers.replicaset import ReplicaSet
from kos.core.orchestration.controllers.deployment import Deployment
from kos.core.orchestration.controllers.statefulset import StatefulSet
from kos.core.orchestration.pod import Pod
from kos.core.orchestration.service import Service
from kos.core.orchestration.service_discovery import ServiceDiscovery

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
MANAGER_CONFIG_PATH = os.path.join(ORCHESTRATION_ROOT, 'controller_manager.json')

# Ensure directories exist
os.makedirs(os.path.dirname(MANAGER_CONFIG_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class ControllerManagerConfig:
    """Configuration for the controller manager."""
    
    def __init__(self, sync_period: int = 30, 
                 enable_replicaset_controller: bool = True,
                 enable_deployment_controller: bool = True,
                 enable_statefulset_controller: bool = True,
                 enable_service_controller: bool = True,
                 enable_service_discovery: bool = True,
                 reconcile_batch_size: int = 10):
        """
        Initialize controller manager configuration.
        
        Args:
            sync_period: Period between sync cycles (in seconds)
            enable_replicaset_controller: Whether to enable the ReplicaSet controller
            enable_deployment_controller: Whether to enable the Deployment controller
            enable_statefulset_controller: Whether to enable the StatefulSet controller
            enable_service_controller: Whether to enable the Service controller
            enable_service_discovery: Whether to enable service discovery
            reconcile_batch_size: Number of resources to reconcile in each batch
        """
        self.sync_period = sync_period
        self.enable_replicaset_controller = enable_replicaset_controller
        self.enable_deployment_controller = enable_deployment_controller
        self.enable_statefulset_controller = enable_statefulset_controller
        self.enable_service_controller = enable_service_controller
        self.enable_service_discovery = enable_service_discovery
        self.reconcile_batch_size = reconcile_batch_size
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the configuration to a dictionary.
        
        Returns:
            Dict representation
        """
        return {
            "sync_period": self.sync_period,
            "enable_replicaset_controller": self.enable_replicaset_controller,
            "enable_deployment_controller": self.enable_deployment_controller,
            "enable_statefulset_controller": self.enable_statefulset_controller,
            "enable_service_controller": self.enable_service_controller,
            "enable_service_discovery": self.enable_service_discovery,
            "reconcile_batch_size": self.reconcile_batch_size
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControllerManagerConfig':
        """
        Create a configuration from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            ControllerManagerConfig object
        """
        return cls(
            sync_period=data.get("sync_period", 30),
            enable_replicaset_controller=data.get("enable_replicaset_controller", True),
            enable_deployment_controller=data.get("enable_deployment_controller", True),
            enable_statefulset_controller=data.get("enable_statefulset_controller", True),
            enable_service_controller=data.get("enable_service_controller", True),
            enable_service_discovery=data.get("enable_service_discovery", True),
            reconcile_batch_size=data.get("reconcile_batch_size", 10)
        )


class ControllerManager:
    """
    Controller manager for the KOS orchestration system.
    
    This class manages the lifecycle of various controllers in the KOS orchestration
    system, including ReplicaSet, Deployment, and StatefulSet controllers.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ControllerManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the controller manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self.config = self._load_config()
        self._stop_event = threading.Event()
        self._sync_thread = None
        
        # Initialize controllers
        self._replicaset_controller = None
        self._deployment_controller = None
        self._statefulset_controller = None
        self._service_controller = None
        self._service_discovery = None
        
        # Register signal handlers
        self._register_signal_handlers()
    
    def _load_config(self) -> ControllerManagerConfig:
        """
        Load configuration from disk.
        
        Returns:
            ControllerManagerConfig object
        """
        if os.path.exists(MANAGER_CONFIG_PATH):
            try:
                with open(MANAGER_CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                
                return ControllerManagerConfig.from_dict(data)
            except Exception as e:
                logger.error(f"Failed to load controller manager config: {e}")
        
        # Create default configuration
        config = ControllerManagerConfig()
        self._save_config(config)
        
        return config
    
    def _save_config(self, config: ControllerManagerConfig) -> bool:
        """
        Save configuration to disk.
        
        Args:
            config: Configuration to save
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(MANAGER_CONFIG_PATH, 'w') as f:
                json.dump(config.to_dict(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save controller manager config: {e}")
            return False
    
    def update_config(self, config: ControllerManagerConfig) -> bool:
        """
        Update configuration.
        
        Args:
            config: New configuration
            
        Returns:
            bool: Success or failure
        """
        if self._save_config(config):
            self.config = config
            
            # Restart sync thread
            self.stop()
            self.start()
            
            return True
        
        return False
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers."""
        try:
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
        except (ValueError, AttributeError):
            # Signal handlers can only be registered in the main thread
            pass
    
    def _handle_signal(self, signum: int, frame) -> None:
        """
        Handle signal.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, shutting down")
        self.stop()
    
    def start(self) -> bool:
        """
        Start the controller manager.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Start service discovery
            if self.config.enable_service_discovery:
                self._service_discovery = ServiceDiscovery()
                self._service_discovery.start_dns_server()
            
            # Start sync thread
            self._stop_event.clear()
            self._sync_thread = threading.Thread(
                target=self._sync_loop,
                daemon=True
            )
            self._sync_thread.start()
            
            logger.info("Controller manager started")
            return True
        except Exception as e:
            logger.error(f"Failed to start controller manager: {e}")
            return False
    
    def stop(self) -> bool:
        """
        Stop the controller manager.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Stop sync thread
            self._stop_event.set()
            
            if self._sync_thread and self._sync_thread.is_alive():
                self._sync_thread.join(timeout=5)
            
            # Stop service discovery
            if self._service_discovery:
                self._service_discovery.stop_dns_server()
                self._service_discovery = None
            
            logger.info("Controller manager stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop controller manager: {e}")
            return False
    
    def _sync_loop(self) -> None:
        """Sync loop for the controller manager."""
        while not self._stop_event.is_set():
            try:
                self._sync_controllers()
            except Exception as e:
                logger.error(f"Error in controller manager sync loop: {e}")
            
            # Sleep for sync period
            self._stop_event.wait(self.config.sync_period)
    
    def _sync_controllers(self) -> None:
        """Sync controllers."""
        # Sync ReplicaSet controller
        if self.config.enable_replicaset_controller:
            self._sync_replicaset_controller()
        
        # Sync Deployment controller
        if self.config.enable_deployment_controller:
            self._sync_deployment_controller()
        
        # Sync StatefulSet controller
        if self.config.enable_statefulset_controller:
            self._sync_statefulset_controller()
        
        # Sync Service controller
        if self.config.enable_service_controller:
            self._sync_service_controller()
    
    def _sync_replicaset_controller(self) -> None:
        """Sync ReplicaSet controller."""
        try:
            # Get all ReplicaSets
            replicasets = ReplicaSet.list_replicasets()
            
            # Reconcile in batches
            batch_size = self.config.reconcile_batch_size
            
            for i in range(0, len(replicasets), batch_size):
                batch = replicasets[i:i+batch_size]
                
                for rs in batch:
                    try:
                        rs.reconcile()
                    except Exception as e:
                        logger.error(f"Failed to reconcile ReplicaSet {rs.namespace}/{rs.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to sync ReplicaSet controller: {e}")
    
    def _sync_deployment_controller(self) -> None:
        """Sync Deployment controller."""
        try:
            # Get all Deployments
            deployments = Deployment.list_deployments()
            
            # Reconcile in batches
            batch_size = self.config.reconcile_batch_size
            
            for i in range(0, len(deployments), batch_size):
                batch = deployments[i:i+batch_size]
                
                for deployment in batch:
                    try:
                        deployment.reconcile()
                    except Exception as e:
                        logger.error(f"Failed to reconcile Deployment {deployment.namespace}/{deployment.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to sync Deployment controller: {e}")
    
    def _sync_statefulset_controller(self) -> None:
        """Sync StatefulSet controller."""
        try:
            # Get all StatefulSets
            statefulsets = StatefulSet.list_statefulsets()
            
            # Reconcile in batches
            batch_size = self.config.reconcile_batch_size
            
            for i in range(0, len(statefulsets), batch_size):
                batch = statefulsets[i:i+batch_size]
                
                for statefulset in batch:
                    try:
                        statefulset.reconcile()
                    except Exception as e:
                        logger.error(f"Failed to reconcile StatefulSet {statefulset.namespace}/{statefulset.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to sync StatefulSet controller: {e}")
    
    def _sync_service_controller(self) -> None:
        """Sync Service controller."""
        try:
            # Get all Services
            services = Service.list_services()
            
            # Reconcile in batches
            batch_size = self.config.reconcile_batch_size
            
            for i in range(0, len(services), batch_size):
                batch = services[i:i+batch_size]
                
                for service in batch:
                    try:
                        service.reconcile()
                    except Exception as e:
                        logger.error(f"Failed to reconcile Service {service.namespace}/{service.name}: {e}")
            
            # Update service discovery
            if self._service_discovery:
                self._service_discovery.update_records()
        except Exception as e:
            logger.error(f"Failed to sync Service controller: {e}")
    
    def reconcile_all(self) -> bool:
        """
        Reconcile all resources.
        
        Returns:
            bool: Success or failure
        """
        try:
            self._sync_controllers()
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile all resources: {e}")
            return False
    
    @staticmethod
    def instance() -> 'ControllerManager':
        """
        Get the singleton instance.
        
        Returns:
            ControllerManager instance
        """
        return ControllerManager()


def start_controller_manager() -> bool:
    """
    Start the controller manager.
    
    Returns:
        bool: Success or failure
    """
    manager = ControllerManager.instance()
    return manager.start()


def stop_controller_manager() -> bool:
    """
    Stop the controller manager.
    
    Returns:
        bool: Success or failure
    """
    manager = ControllerManager.instance()
    return manager.stop()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    
    # Start controller manager
    manager = ControllerManager.instance()
    manager.start()
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Stop controller manager
        manager.stop()

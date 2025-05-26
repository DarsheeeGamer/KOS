"""
Initialization System for KOS Orchestration

This module provides initialization and coordination for all KOS orchestration components,
ensuring they start in the correct order and are properly configured.
"""

import os
import sys
import time
import logging
import threading
import json
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable

# Import orchestration components
from kos.core.orchestration.controllers.manager import ControllerManager
from kos.core.orchestration.scheduler import Scheduler
from kos.core.orchestration.admission import get_admission_controller
from kos.core.orchestration.admission_webhook import get_webhook_manager
from kos.core.orchestration.service_discovery import ServiceDiscovery
from kos.core.orchestration.network_policy import NetworkPolicyController
from kos.core.orchestration.autoscaler import start_autoscaler_controller
from kos.core.orchestration.quota import start_quota_controller
from kos.core.orchestration.volume import start_volume_controller
from kos.core.orchestration.controllers.job import start_job_controller, stop_job_controller
from kos.core.orchestration.controllers.cronjob import start_cronjob_controller, stop_cronjob_controller
from kos.core.monitoring.metrics import MetricsCollector

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
CONFIG_PATH = os.path.join(KOS_ROOT, 'etc/kos/orchestration/config.json')

# Ensure directories exist
os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class OrchestrationInit:
    """
    Initialization system for KOS orchestration.
    
    This class manages the startup and shutdown of all orchestration components.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(OrchestrationInit, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the orchestration initialization system."""
        if self._initialized:
            return
        
        self._initialized = True
        self._config = self._load_config()
        self._components = {}
        self._stop_event = threading.Event()
        self._healthcheck_thread = None
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from disk.
        
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load orchestration config: {e}")
        
        # Create default configuration
        config = {
            "enabled": True,
            "components": {
                "metrics_collector": True,
                "controller_manager": True,
                "scheduler": True,
                "admission_controller": True,
                "webhook_manager": True,
                "service_discovery": True,
                "network_policy_controller": True,
                "autoscaler_controller": True,
                "quota_controller": True,
                "volume_controller": True,
                "job_controller": True,
                "cronjob_controller": True
            },
            "healthcheck_interval": 60
        }
        
        self._save_config(config)
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> bool:
        """
        Save configuration to disk.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            bool: Success or failure
        """
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save orchestration config: {e}")
            return False
    
    def start(self) -> bool:
        """
        Start all orchestration components.
        
        Returns:
            bool: Success or failure
        """
        if not self._config.get("enabled", True):
            logger.info("Orchestration system is disabled")
            return False
        
        # Start components in order
        self._start_component("metrics_collector", self._start_metrics_collector)
        self._start_component("admission_controller", self._start_admission_controller)
        self._start_component("webhook_manager", self._start_webhook_manager)
        self._start_component("service_discovery", self._start_service_discovery)
        self._start_component("network_policy_controller", self._start_network_policy_controller)
        self._start_component("scheduler", self._start_scheduler)
        self._start_component("controller_manager", self._start_controller_manager)
        self._start_component("autoscaler_controller", self._start_autoscaler_controller)
        self._start_component("quota_controller", self._start_quota_controller)
        self._start_component("volume_controller", self._start_volume_controller)
        self._start_component("job_controller", self._start_job_controller)
        self._start_component("cronjob_controller", self._start_cronjob_controller)
        
        # Start healthcheck thread
        self._start_healthcheck()
        
        logger.info("Orchestration system started")
        return True
    
    def stop(self) -> bool:
        """
        Stop all orchestration components.
        
        Returns:
            bool: Success or failure
        """
        # Stop healthcheck thread
        self._stop_healthcheck()
        
        # Stop components in reverse order
        self._stop_component("cronjob_controller", self._stop_cronjob_controller)
        self._stop_component("job_controller", self._stop_job_controller)
        self._stop_component("volume_controller", self._stop_volume_controller)
        self._stop_component("quota_controller", self._stop_quota_controller)
        self._stop_component("autoscaler_controller", self._stop_autoscaler_controller)
        self._stop_component("controller_manager", self._stop_controller_manager)
        self._stop_component("scheduler", self._stop_scheduler)
        self._stop_component("network_policy_controller", self._stop_network_policy_controller)
        self._stop_component("service_discovery", self._stop_service_discovery)
        self._stop_component("webhook_manager", self._stop_webhook_manager)
        self._stop_component("admission_controller", self._stop_admission_controller)
        self._stop_component("metrics_collector", self._stop_metrics_collector)
        
        logger.info("Orchestration system stopped")
        return True
    
    def _start_component(self, name: str, start_func: Callable[[], bool]) -> None:
        """
        Start a component.
        
        Args:
            name: Component name
            start_func: Function to start the component
        """
        if not self._config.get("components", {}).get(name, True):
            logger.info(f"Component {name} is disabled")
            return
        
        try:
            logger.info(f"Starting component {name}")
            result = start_func()
            self._components[name] = {
                "enabled": True,
                "healthy": result,
                "last_check": time.time()
            }
        except Exception as e:
            logger.error(f"Failed to start component {name}: {e}")
            self._components[name] = {
                "enabled": True,
                "healthy": False,
                "last_check": time.time(),
                "error": str(e)
            }
    
    def _stop_component(self, name: str, stop_func: Callable[[], bool]) -> None:
        """
        Stop a component.
        
        Args:
            name: Component name
            stop_func: Function to stop the component
        """
        if name not in self._components:
            return
        
        try:
            logger.info(f"Stopping component {name}")
            result = stop_func()
            self._components[name]["healthy"] = False
            self._components[name]["last_check"] = time.time()
        except Exception as e:
            logger.error(f"Failed to stop component {name}: {e}")
            self._components[name]["healthy"] = False
            self._components[name]["last_check"] = time.time()
            self._components[name]["error"] = str(e)
    
    def _start_metrics_collector(self) -> bool:
        """
        Start the metrics collector.
        
        Returns:
            bool: Success or failure
        """
        collector = MetricsCollector.instance()
        return collector.start_collection()
    
    def _stop_metrics_collector(self) -> bool:
        """
        Stop the metrics collector.
        
        Returns:
            bool: Success or failure
        """
        collector = MetricsCollector.instance()
        return collector.stop_collection()
    
    def _start_admission_controller(self) -> bool:
        """
        Start the admission controller.
        
        Returns:
            bool: Success or failure
        """
        controller = get_admission_controller()
        return controller.is_enabled()
    
    def _stop_admission_controller(self) -> bool:
        """
        Stop the admission controller.
        
        Returns:
            bool: Success or failure
        """
        controller = get_admission_controller()
        controller.disable()
        return True
    
    def _start_webhook_manager(self) -> bool:
        """
        Start the webhook manager.
        
        Returns:
            bool: Success or failure
        """
        manager = get_webhook_manager()
        return True
    
    def _stop_webhook_manager(self) -> bool:
        """
        Stop the webhook manager.
        
        Returns:
            bool: Success or failure
        """
        manager = get_webhook_manager()
        return True
    
    def _start_service_discovery(self) -> bool:
        """
        Start the service discovery.
        
        Returns:
            bool: Success or failure
        """
        discovery = ServiceDiscovery.instance()
        return discovery.start()
    
    def _stop_service_discovery(self) -> bool:
        """
        Stop the service discovery.
        
        Returns:
            bool: Success or failure
        """
        discovery = ServiceDiscovery.instance()
        return discovery.stop()
    
    def _start_network_policy_controller(self) -> bool:
        """
        Start the network policy controller.
        
        Returns:
            bool: Success or failure
        """
        controller = NetworkPolicyController.instance()
        return controller.start()
    
    def _stop_network_policy_controller(self) -> bool:
        """
        Stop the network policy controller.
        
        Returns:
            bool: Success or failure
        """
        controller = NetworkPolicyController.instance()
        return controller.stop()
    
    def _start_scheduler(self) -> bool:
        """
        Start the scheduler.
        
        Returns:
            bool: Success or failure
        """
        scheduler = Scheduler.instance()
        return scheduler.start()
    
    def _stop_scheduler(self) -> bool:
        """
        Stop the scheduler.
        
        Returns:
            bool: Success or failure
        """
        scheduler = Scheduler.instance()
        return scheduler.stop()
    
    def _start_controller_manager(self) -> bool:
        """
        Start the controller manager.
        
        Returns:
            bool: Success or failure
        """
        manager = ControllerManager.instance()
        return manager.start()
    
    def _stop_controller_manager(self) -> bool:
        """
        Stop the controller manager.
        
        Returns:
            bool: Success or failure
        """
        manager = ControllerManager.instance()
        return manager.stop()
    
    def _start_autoscaler_controller(self) -> bool:
        """
        Start the autoscaler controller.
        
        Returns:
            bool: Success or failure
        """
        return start_autoscaler_controller()
    
    def _stop_autoscaler_controller(self) -> bool:
        """
        Stop the autoscaler controller.
        
        Returns:
            bool: Success or failure
        """
        from kos.core.orchestration.autoscaler import stop_autoscaler_controller
        return stop_autoscaler_controller()
    
    def _start_quota_controller(self) -> bool:
        """
        Start the quota controller.
        
        Returns:
            bool: Success or failure
        """
        return start_quota_controller()
    
    def _stop_quota_controller(self) -> bool:
        """
        Stop the quota controller.
        
        Returns:
            bool: Success or failure
        """
        from kos.core.orchestration.quota import stop_quota_controller
        return stop_quota_controller()
    
    def _start_volume_controller(self) -> bool:
        """
        Start the volume controller.
        
        Returns:
            bool: Success or failure
        """
        return start_volume_controller()
    
    def _stop_volume_controller(self) -> bool:
        """
        Stop the volume controller.
        
        Returns:
            bool: Success or failure
        """
        from kos.core.orchestration.volume import stop_volume_controller
        return stop_volume_controller()
    
    def _start_healthcheck(self) -> None:
        """Start the healthcheck thread."""
        self._stop_event.clear()
        self._healthcheck_thread = threading.Thread(
            target=self._healthcheck_loop,
            daemon=True
        )
        self._healthcheck_thread.start()
    
    def _stop_healthcheck(self) -> None:
        """Stop the healthcheck thread."""
        if self._healthcheck_thread and self._healthcheck_thread.is_alive():
            self._stop_event.set()
            self._healthcheck_thread.join(timeout=5)
    
    def _healthcheck_loop(self) -> None:
        """Healthcheck loop."""
        while not self._stop_event.is_set():
            try:
                self._healthcheck()
            except Exception as e:
                logger.error(f"Error in healthcheck loop: {e}")
            
            # Sleep for a while
            interval = self._config.get("healthcheck_interval", 60)
            self._stop_event.wait(interval)
    
    def _healthcheck(self) -> None:
        """Perform healthcheck on all components."""
        for name, component in self._components.items():
            try:
                if not component.get("enabled", True):
                    continue
                
                # Check component health
                health_func = getattr(self, f"_check_{name}", None)
                if health_func:
                    healthy = health_func()
                    component["healthy"] = healthy
                    component["last_check"] = time.time()
                    
                    if not healthy:
                        logger.warning(f"Component {name} is unhealthy")
                        
                        # Try to restart the component
                        restart_func = getattr(self, f"_restart_{name}", None)
                        if restart_func:
                            logger.info(f"Restarting component {name}")
                            restart_func()
            except Exception as e:
                logger.error(f"Error checking health of component {name}: {e}")
                component["healthy"] = False
                component["last_check"] = time.time()
                component["error"] = str(e)
    
    def _check_metrics_collector(self) -> bool:
        """
        Check the health of the metrics collector.
        
        Returns:
            bool: True if healthy
        """
        collector = MetricsCollector.instance()
        return collector.is_collecting()
    
    def _restart_metrics_collector(self) -> bool:
        """
        Restart the metrics collector.
        
        Returns:
            bool: Success or failure
        """
        collector = MetricsCollector.instance()
        collector.stop_collection()
        return collector.start_collection()
    
    def _check_controller_manager(self) -> bool:
        """
        Check the health of the controller manager.
        
        Returns:
            bool: True if healthy
        """
        manager = ControllerManager.instance()
        return manager.is_running()
    
    def _restart_controller_manager(self) -> bool:
        """
        Restart the controller manager.
        
        Returns:
            bool: Success or failure
        """
        manager = ControllerManager.instance()
        manager.stop()
        return manager.start()
    
    def _check_scheduler(self) -> bool:
        """
        Check the health of the scheduler.
        
        Returns:
            bool: True if healthy
        """
        scheduler = Scheduler.instance()
        return scheduler.is_running()
    
    def _restart_scheduler(self) -> bool:
        """
        Restart the scheduler.
        
        Returns:
            bool: Success or failure
        """
        scheduler = Scheduler.instance()
        scheduler.stop()
        return scheduler.start()
    
    def _check_service_discovery(self) -> bool:
        """
        Check the health of the service discovery.
        
        Returns:
            bool: True if healthy
        """
        discovery = ServiceDiscovery.instance()
        return discovery.is_running()
    
    def _restart_service_discovery(self) -> bool:
        """
        Restart the service discovery.
        
        Returns:
            bool: Success or failure
        """
        discovery = ServiceDiscovery.instance()
        discovery.stop()
        return discovery.start()
    
    def _check_network_policy_controller(self) -> bool:
        """
        Check the health of the network policy controller.
        
        Returns:
            bool: True if healthy
        """
        controller = NetworkPolicyController.instance()
        return controller.is_running()
    
    def _restart_network_policy_controller(self) -> bool:
        """
        Restart the network policy controller.
        
        Returns:
            bool: Success or failure
        """
        controller = NetworkPolicyController.instance()
        controller.stop()
        return controller.start()
    
    def _start_job_controller(self) -> bool:
        """
        Start the job controller.
        
        Returns:
            bool: Success or failure
        """
        return start_job_controller()
    
    def _stop_job_controller(self) -> bool:
        """
        Stop the job controller.
        
        Returns:
            bool: Success or failure
        """
        return stop_job_controller()
    
    def _check_job_controller(self) -> bool:
        """
        Check the health of the job controller.
        
        Returns:
            bool: True if healthy
        """
        from kos.core.orchestration.controllers.job import JobController
        controller = JobController.instance()
        return controller.is_running()
    
    def _restart_job_controller(self) -> bool:
        """
        Restart the job controller.
        
        Returns:
            bool: Success or failure
        """
        stop_job_controller()
        return start_job_controller()
    
    def _start_cronjob_controller(self) -> bool:
        """
        Start the cronjob controller.
        
        Returns:
            bool: Success or failure
        """
        return start_cronjob_controller()
    
    def _stop_cronjob_controller(self) -> bool:
        """
        Stop the cronjob controller.
        
        Returns:
            bool: Success or failure
        """
        return stop_cronjob_controller()
    
    def _check_cronjob_controller(self) -> bool:
        """
        Check the health of the cronjob controller.
        
        Returns:
            bool: True if healthy
        """
        from kos.core.orchestration.controllers.cronjob import CronJobController
        controller = CronJobController.instance()
        return controller.is_running()
    
    def _restart_cronjob_controller(self) -> bool:
        """
        Restart the cronjob controller.
        
        Returns:
            bool: Success or failure
        """
        stop_cronjob_controller()
        return start_cronjob_controller()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of all components.
        
        Returns:
            Dict[str, Any]: Status dictionary
        """
        return {
            "enabled": self._config.get("enabled", True),
            "components": self._components
        }
    
    def enable_component(self, name: str) -> bool:
        """
        Enable a component.
        
        Args:
            name: Component name
            
        Returns:
            bool: Success or failure
        """
        if name not in self._config.get("components", {}):
            return False
        
        self._config["components"][name] = True
        self._save_config(self._config)
        
        # Start the component if system is enabled
        if self._config.get("enabled", True):
            start_func = getattr(self, f"_start_{name}", None)
            if start_func:
                self._start_component(name, start_func)
        
        return True
    
    def disable_component(self, name: str) -> bool:
        """
        Disable a component.
        
        Args:
            name: Component name
            
        Returns:
            bool: Success or failure
        """
        if name not in self._config.get("components", {}):
            return False
        
        self._config["components"][name] = False
        self._save_config(self._config)
        
        # Stop the component if it's running
        if name in self._components:
            stop_func = getattr(self, f"_stop_{name}", None)
            if stop_func:
                self._stop_component(name, stop_func)
        
        return True
    
    def enable(self) -> bool:
        """
        Enable the orchestration system.
        
        Returns:
            bool: Success or failure
        """
        self._config["enabled"] = True
        self._save_config(self._config)
        return self.start()
    
    def disable(self) -> bool:
        """
        Disable the orchestration system.
        
        Returns:
            bool: Success or failure
        """
        self._config["enabled"] = False
        self._save_config(self._config)
        return self.stop()
    
    @staticmethod
    def instance() -> 'OrchestrationInit':
        """
        Get the singleton instance.
        
        Returns:
            OrchestrationInit instance
        """
        return OrchestrationInit()


def start_orchestration() -> bool:
    """
    Start the orchestration system.
    
    Returns:
        bool: Success or failure
    """
    init = OrchestrationInit.instance()
    return init.start()


def stop_orchestration() -> bool:
    """
    Stop the orchestration system.
    
    Returns:
        bool: Success or failure
    """
    init = OrchestrationInit.instance()
    return init.stop()


def get_orchestration_status() -> Dict[str, Any]:
    """
    Get the status of the orchestration system.
    
    Returns:
        Dict[str, Any]: Status dictionary
    """
    init = OrchestrationInit.instance()
    return init.get_status()


# Start orchestration if this script is executed directly
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse command-line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'start':
            start_orchestration()
        elif command == 'stop':
            stop_orchestration()
        elif command == 'status':
            status = get_orchestration_status()
            print(json.dumps(status, indent=2))
        else:
            print(f"Unknown command: {command}")
            print("Usage: python -m kos.core.orchestration.init [start|stop|status]")
    else:
        # Default to start
        start_orchestration()

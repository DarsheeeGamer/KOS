"""
Job Controller for KOS Orchestration System

This module implements Job controllers for the KOS orchestration system,
allowing batch processing of pods that should run to completion.
"""

import os
import json
import logging
import threading
import time
import uuid
import random
from typing import Dict, List, Any, Optional, Set, Tuple, Union

from kos.core.orchestration.pod import Pod, PodSpec, PodPhase

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
JOB_PATH = os.path.join(ORCHESTRATION_ROOT, 'jobs')

# Ensure directories exist
os.makedirs(JOB_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class JobSpec:
    """Specification for a Job."""
    
    def __init__(self, template: Dict[str, Any] = None,
                 parallelism: int = 1,
                 completions: int = 1,
                 active_deadline_seconds: Optional[int] = None,
                 backoff_limit: int = 6,
                 ttl_seconds_after_finished: Optional[int] = None):
        """
        Initialize a Job specification.
        
        Args:
            template: Pod template
            parallelism: Max number of pods that can run in parallel
            completions: Desired number of successfully finished pods
            active_deadline_seconds: Deadline in seconds for the Job
            backoff_limit: Number of retries before marking the Job failed
            ttl_seconds_after_finished: TTL for finished Jobs
        """
        self.template = template or {}
        self.parallelism = parallelism
        self.completions = completions
        self.active_deadline_seconds = active_deadline_seconds
        self.backoff_limit = backoff_limit
        self.ttl_seconds_after_finished = ttl_seconds_after_finished
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Job specification to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "template": self.template,
            "parallelism": self.parallelism,
            "completions": self.completions,
            "backoffLimit": self.backoff_limit
        }
        
        if self.active_deadline_seconds is not None:
            result["activeDeadlineSeconds"] = self.active_deadline_seconds
        
        if self.ttl_seconds_after_finished is not None:
            result["ttlSecondsAfterFinished"] = self.ttl_seconds_after_finished
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobSpec':
        """
        Create a Job specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            JobSpec object
        """
        return cls(
            template=data.get("template", {}),
            parallelism=data.get("parallelism", 1),
            completions=data.get("completions", 1),
            active_deadline_seconds=data.get("activeDeadlineSeconds"),
            backoff_limit=data.get("backoffLimit", 6),
            ttl_seconds_after_finished=data.get("ttlSecondsAfterFinished")
        )


class JobStatus:
    """Status for a Job."""
    
    def __init__(self, active: int = 0, succeeded: int = 0, failed: int = 0,
                 start_time: Optional[float] = None,
                 completion_time: Optional[float] = None,
                 conditions: List[Dict[str, Any]] = None):
        """
        Initialize a Job status.
        
        Args:
            active: Number of actively running pods
            succeeded: Number of pods which reached phase Succeeded
            failed: Number of pods which reached phase Failed
            start_time: Time when the Job was started
            completion_time: Time when the Job was completed
            conditions: Current Job conditions
        """
        self.active = active
        self.succeeded = succeeded
        self.failed = failed
        self.start_time = start_time
        self.completion_time = completion_time
        self.conditions = conditions or []
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Job status to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "active": self.active,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "conditions": self.conditions
        }
        
        if self.start_time is not None:
            result["startTime"] = self.start_time
        
        if self.completion_time is not None:
            result["completionTime"] = self.completion_time
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobStatus':
        """
        Create a Job status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            JobStatus object
        """
        return cls(
            active=data.get("active", 0),
            succeeded=data.get("succeeded", 0),
            failed=data.get("failed", 0),
            start_time=data.get("startTime"),
            completion_time=data.get("completionTime"),
            conditions=data.get("conditions", [])
        )


class Job:
    """
    Job in the KOS orchestration system.
    
    A Job creates one or more pods and ensures that a specified number of them
    successfully terminate.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[JobSpec] = None):
        """
        Initialize a Job.
        
        Args:
            name: Job name
            namespace: Namespace
            spec: Job specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or JobSpec()
        self.status = JobStatus()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        self._pods: List[str] = []
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this Job."""
        return os.path.join(JOB_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the Job from disk.
        
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
            self.spec = JobSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = JobStatus.from_dict(status_data)
            
            # Update pods
            self._pods = data.get("pods", [])
            
            return True
        except Exception as e:
            logger.error(f"Failed to load Job {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the Job to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "Job",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict(),
                    "pods": self._pods
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save Job {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the Job.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete all pods
            for pod_name in self._pods:
                pod = Pod.get_pod(pod_name, self.namespace)
                if pod:
                    pod.delete()
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete Job {self.namespace}/{self.name}: {e}")
            return False
    
    def reconcile(self) -> bool:
        """
        Reconcile the Job to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Initialize start time if not set
                if self.status.start_time is None:
                    self.status.start_time = time.time()
                
                # Check if job is past its deadline
                if self.spec.active_deadline_seconds is not None:
                    elapsed = time.time() - self.status.start_time
                    if elapsed > self.spec.active_deadline_seconds:
                        self._set_failed("DeadlineExceeded", "Job was active longer than specified deadline")
                        return self.save()
                
                # Get current pods
                active_pods = []
                succeeded_pods = []
                failed_pods = []
                
                for pod_name in self._pods:
                    pod = Pod.get_pod(pod_name, self.namespace)
                    if not pod:
                        continue
                    
                    if pod.status.phase == PodPhase.SUCCEEDED:
                        succeeded_pods.append(pod)
                    elif pod.status.phase == PodPhase.FAILED:
                        failed_pods.append(pod)
                    elif pod.status.phase in [PodPhase.PENDING, PodPhase.RUNNING]:
                        active_pods.append(pod)
                
                # Update status
                self.status.active = len(active_pods)
                self.status.succeeded = len(succeeded_pods)
                self.status.failed = len(failed_pods)
                
                # Check if job has completed successfully
                if self.status.succeeded >= self.spec.completions:
                    if self.status.completion_time is None:
                        self.status.completion_time = time.time()
                    
                    self._set_complete()
                    
                    # Check TTL for deletion
                    if self.spec.ttl_seconds_after_finished is not None:
                        elapsed = time.time() - self.status.completion_time
                        if elapsed > self.spec.ttl_seconds_after_finished:
                            self.delete()
                            return True
                    
                    return self.save()
                
                # Check if job has failed
                if self.status.failed > self.spec.backoff_limit:
                    self._set_failed("BackoffLimitExceeded", "Job has reached the specified backoff limit")
                    return self.save()
                
                # Create more pods if needed
                if self.status.active < self.spec.parallelism and self.status.succeeded < self.spec.completions:
                    # How many pods to create
                    to_create = min(
                        self.spec.parallelism - self.status.active,
                        self.spec.completions - self.status.succeeded
                    )
                    
                    for _ in range(to_create):
                        self._create_pod()
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to reconcile Job {self.namespace}/{self.name}: {e}")
            return False
    
    def _create_pod(self) -> Optional[Pod]:
        """
        Create a pod for this Job.
        
        Returns:
            Created Pod or None if creation failed
        """
        try:
            # Create a unique name for the pod
            pod_name = f"{self.name}-{uuid.uuid4().hex[:5]}"
            
            # Create pod from template
            pod_template = self.spec.template
            
            # Create pod spec
            pod_spec = PodSpec(
                containers=pod_template.get("spec", {}).get("containers", []),
                volumes=pod_template.get("spec", {}).get("volumes", []),
                restart_policy="Never"  # Jobs should not restart
            )
            
            # Create pod
            pod = Pod(
                name=pod_name,
                namespace=self.namespace,
                spec=pod_spec
            )
            
            # Set owner reference
            pod.metadata["ownerReferences"] = [{
                "apiVersion": "v1",
                "kind": "Job",
                "name": self.name,
                "uid": self.metadata["uid"]
            }]
            
            # Copy labels from template
            pod.metadata["labels"] = pod_template.get("metadata", {}).get("labels", {}).copy()
            pod.metadata["labels"]["job-name"] = self.name
            
            # Save pod
            if pod.save():
                # Add pod to job
                self._pods.append(pod_name)
                return pod
        except Exception as e:
            logger.error(f"Failed to create pod for Job {self.namespace}/{self.name}: {e}")
        
        return None
    
    def _set_complete(self) -> None:
        """Set the Job as complete."""
        # Check if already complete
        for condition in self.status.conditions:
            if condition.get("type") == "Complete" and condition.get("status") == "True":
                return
        
        # Add Complete condition
        self.status.conditions.append({
            "type": "Complete",
            "status": "True",
            "lastProbeTime": time.time(),
            "lastTransitionTime": time.time()
        })
    
    def _set_failed(self, reason: str, message: str) -> None:
        """
        Set the Job as failed.
        
        Args:
            reason: Failure reason
            message: Failure message
        """
        # Check if already failed
        for condition in self.status.conditions:
            if condition.get("type") == "Failed" and condition.get("status") == "True":
                return
        
        # Add Failed condition
        self.status.conditions.append({
            "type": "Failed",
            "status": "True",
            "lastProbeTime": time.time(),
            "lastTransitionTime": time.time(),
            "reason": reason,
            "message": message
        })
    
    @staticmethod
    def list_jobs(namespace: Optional[str] = None) -> List['Job']:
        """
        List all Jobs.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of Jobs
        """
        jobs = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = JOB_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List Jobs in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(JOB_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    job_name = filename[:-5]  # Remove .json extension
                    job = Job(job_name, ns)
                    jobs.append(job)
        except Exception as e:
            logger.error(f"Failed to list Jobs: {e}")
        
        return jobs
    
    @staticmethod
    def get_job(name: str, namespace: str = "default") -> Optional['Job']:
        """
        Get a Job by name and namespace.
        
        Args:
            name: Job name
            namespace: Namespace
            
        Returns:
            Job object or None if not found
        """
        job = Job(name, namespace)
        
        if os.path.exists(job._file_path()):
            return job
        
        return None


class JobController:
    """
    Controller for Jobs in the KOS orchestration system.
    
    This class manages the reconciliation of Jobs.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(JobController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the Job controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the Job controller.
        
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
        Stop the Job controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the Job controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in Job controller reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(10)  # Check every 10 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile all Jobs.
        
        Returns:
            bool: Success or failure
        """
        try:
            # List all Jobs
            jobs = Job.list_jobs()
            
            # Reconcile each Job
            for job in jobs:
                try:
                    job.reconcile()
                except Exception as e:
                    logger.error(f"Failed to reconcile Job {job.namespace}/{job.name}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile Jobs: {e}")
            return False
    
    def is_running(self) -> bool:
        """
        Check if the controller is running.
        
        Returns:
            bool: True if running
        """
        return self._reconcile_thread is not None and self._reconcile_thread.is_alive()
    
    @staticmethod
    def instance() -> 'JobController':
        """
        Get the singleton instance.
        
        Returns:
            JobController instance
        """
        return JobController()


def start_job_controller() -> bool:
    """
    Start the Job controller.
    
    Returns:
        bool: Success or failure
    """
    controller = JobController.instance()
    return controller.start()


def stop_job_controller() -> bool:
    """
    Stop the Job controller.
    
    Returns:
        bool: Success or failure
    """
    controller = JobController.instance()
    return controller.stop()

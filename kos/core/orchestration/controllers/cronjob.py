"""
CronJob Controller for KOS Orchestration System

This module implements CronJob controllers for the KOS orchestration system,
allowing scheduled execution of jobs based on cron expressions.
"""

import os
import json
import logging
import threading
import time
import uuid
import re
import calendar
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Union, Callable

from kos.core.orchestration.controllers.job import Job, JobSpec

# Configuration paths
KOS_ROOT = os.environ.get('KOS_ROOT', '/tmp/kos')
ORCHESTRATION_ROOT = os.path.join(KOS_ROOT, 'var/lib/kos/orchestration')
CRONJOB_PATH = os.path.join(ORCHESTRATION_ROOT, 'cronjobs')

# Ensure directories exist
os.makedirs(CRONJOB_PATH, exist_ok=True)

# Logging setup
logger = logging.getLogger(__name__)


class CronSchedule:
    """Cron schedule parser and matcher."""
    
    # Special schedule shortcuts
    SHORTCUTS = {
        "@yearly": "0 0 1 1 *",
        "@annually": "0 0 1 1 *",
        "@monthly": "0 0 1 * *",
        "@weekly": "0 0 * * 0",
        "@daily": "0 0 * * *",
        "@midnight": "0 0 * * *",
        "@hourly": "0 * * * *"
    }
    
    def __init__(self, schedule: str):
        """
        Initialize a cron schedule.
        
        Args:
            schedule: Cron schedule expression
        """
        # Expand shortcuts
        if schedule in self.SHORTCUTS:
            schedule = self.SHORTCUTS[schedule]
        
        # Parse schedule
        parts = schedule.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron schedule: {schedule}")
        
        self.minute = self._parse_field(parts[0], 0, 59)
        self.hour = self._parse_field(parts[1], 0, 23)
        self.day = self._parse_field(parts[2], 1, 31)
        self.month = self._parse_field(parts[3], 1, 12)
        self.day_of_week = self._parse_field(parts[4], 0, 6)
        
        # Store original schedule
        self.schedule = schedule
    
    def _parse_field(self, field: str, min_val: int, max_val: int) -> Set[int]:
        """
        Parse a cron field.
        
        Args:
            field: Field to parse
            min_val: Minimum value
            max_val: Maximum value
            
        Returns:
            Set of valid values
        """
        result = set()
        
        # Handle wildcards
        if field == "*":
            for i in range(min_val, max_val + 1):
                result.add(i)
            return result
        
        # Handle multiple values
        for part in field.split(','):
            # Handle ranges
            if '-' in part:
                start, end = part.split('-', 1)
                start = int(start)
                end = int(end)
                
                for i in range(start, end + 1):
                    if min_val <= i <= max_val:
                        result.add(i)
            
            # Handle steps
            elif '/' in part:
                base, step = part.split('/', 1)
                
                # Parse base
                if base == '*':
                    base_vals = set(range(min_val, max_val + 1))
                elif '-' in base:
                    base_start, base_end = base.split('-', 1)
                    base_vals = set(range(int(base_start), int(base_end) + 1))
                else:
                    base_vals = {int(base)}
                
                # Apply step
                step = int(step)
                for i in sorted(base_vals):
                    if i % step == 0 and min_val <= i <= max_val:
                        result.add(i)
            
            # Handle single values
            else:
                i = int(part)
                if min_val <= i <= max_val:
                    result.add(i)
        
        return result
    
    def next_execution_time(self, from_time: Optional[datetime] = None) -> datetime:
        """
        Get the next execution time.
        
        Args:
            from_time: Time to start from (default: now)
            
        Returns:
            Next execution time
        """
        if from_time is None:
            from_time = datetime.now()
        
        # Start searching from the next minute
        next_time = from_time + timedelta(minutes=1)
        next_time = next_time.replace(second=0, microsecond=0)
        
        # Maximum iterations to prevent infinite loops
        max_iterations = 1000
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            
            # Check if the current time matches the schedule
            if (next_time.minute in self.minute and
                next_time.hour in self.hour and
                next_time.day in self.day and
                next_time.month in self.month and
                next_time.weekday() in self.day_of_week):
                return next_time
            
            # Move to the next minute
            next_time += timedelta(minutes=1)
        
        # Fallback if we couldn't find a match
        return next_time
    
    def __str__(self) -> str:
        """String representation."""
        return self.schedule


class CronJobSpec:
    """Specification for a CronJob."""
    
    def __init__(self, schedule: str,
                 job_template: Dict[str, Any] = None,
                 concurrency_policy: str = "Allow",
                 starting_deadline_seconds: Optional[int] = None,
                 successful_jobs_history_limit: int = 3,
                 failed_jobs_history_limit: int = 1,
                 suspend: bool = False):
        """
        Initialize a CronJob specification.
        
        Args:
            schedule: Cron schedule
            job_template: Job template
            concurrency_policy: How to handle concurrent executions
            starting_deadline_seconds: Deadline for starting jobs
            successful_jobs_history_limit: Limit for successful job history
            failed_jobs_history_limit: Limit for failed job history
            suspend: Whether to suspend the job
        """
        self.schedule = CronSchedule(schedule)
        self.job_template = job_template or {"spec": {}}
        self.concurrency_policy = concurrency_policy
        self.starting_deadline_seconds = starting_deadline_seconds
        self.successful_jobs_history_limit = successful_jobs_history_limit
        self.failed_jobs_history_limit = failed_jobs_history_limit
        self.suspend = suspend
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the CronJob specification to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "schedule": str(self.schedule),
            "jobTemplate": self.job_template,
            "concurrencyPolicy": self.concurrency_policy,
            "successfulJobsHistoryLimit": self.successful_jobs_history_limit,
            "failedJobsHistoryLimit": self.failed_jobs_history_limit,
            "suspend": self.suspend
        }
        
        if self.starting_deadline_seconds is not None:
            result["startingDeadlineSeconds"] = self.starting_deadline_seconds
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CronJobSpec':
        """
        Create a CronJob specification from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            CronJobSpec object
        """
        return cls(
            schedule=data.get("schedule", "0 * * * *"),
            job_template=data.get("jobTemplate", {"spec": {}}),
            concurrency_policy=data.get("concurrencyPolicy", "Allow"),
            starting_deadline_seconds=data.get("startingDeadlineSeconds"),
            successful_jobs_history_limit=data.get("successfulJobsHistoryLimit", 3),
            failed_jobs_history_limit=data.get("failedJobsHistoryLimit", 1),
            suspend=data.get("suspend", False)
        )


class CronJobStatus:
    """Status for a CronJob."""
    
    def __init__(self, active: List[Dict[str, str]] = None,
                 last_schedule_time: Optional[float] = None,
                 last_successful_time: Optional[float] = None):
        """
        Initialize a CronJob status.
        
        Args:
            active: List of active jobs
            last_schedule_time: Last time the job was scheduled
            last_successful_time: Last time the job was successfully scheduled
        """
        self.active = active or []
        self.last_schedule_time = last_schedule_time
        self.last_successful_time = last_successful_time
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the CronJob status to a dictionary.
        
        Returns:
            Dict representation
        """
        result = {
            "active": self.active
        }
        
        if self.last_schedule_time is not None:
            result["lastScheduleTime"] = self.last_schedule_time
        
        if self.last_successful_time is not None:
            result["lastSuccessfulTime"] = self.last_successful_time
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CronJobStatus':
        """
        Create a CronJob status from a dictionary.
        
        Args:
            data: Dictionary representation
            
        Returns:
            CronJobStatus object
        """
        return cls(
            active=data.get("active", []),
            last_schedule_time=data.get("lastScheduleTime"),
            last_successful_time=data.get("lastSuccessfulTime")
        )


class CronJob:
    """
    CronJob in the KOS orchestration system.
    
    A CronJob creates Jobs on a time-based schedule.
    """
    
    def __init__(self, name: str, namespace: str = "default",
                 spec: Optional[CronJobSpec] = None):
        """
        Initialize a CronJob.
        
        Args:
            name: CronJob name
            namespace: Namespace
            spec: CronJob specification
        """
        self.name = name
        self.namespace = namespace
        self.spec = spec or CronJobSpec("0 * * * *")
        self.status = CronJobStatus()
        self.metadata = {
            "name": name,
            "namespace": namespace,
            "uid": str(uuid.uuid4()),
            "created": time.time(),
            "labels": {},
            "annotations": {}
        }
        self._lock = threading.RLock()
        self._jobs: List[str] = []
        
        # Load if exists
        self._load()
    
    def _file_path(self) -> str:
        """Get the file path for this CronJob."""
        return os.path.join(CRONJOB_PATH, self.namespace, f"{self.name}.json")
    
    def _load(self) -> bool:
        """
        Load the CronJob from disk.
        
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
            self.spec = CronJobSpec.from_dict(spec_data)
            
            # Update status
            status_data = data.get("status", {})
            self.status = CronJobStatus.from_dict(status_data)
            
            # Update jobs
            self._jobs = data.get("jobs", [])
            
            return True
        except Exception as e:
            logger.error(f"Failed to load CronJob {self.namespace}/{self.name}: {e}")
            return False
    
    def save(self) -> bool:
        """
        Save the CronJob to disk.
        
        Returns:
            bool: Success or failure
        """
        file_path = self._file_path()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        try:
            with self._lock:
                data = {
                    "kind": "CronJob",
                    "apiVersion": "v1",
                    "metadata": self.metadata,
                    "spec": self.spec.to_dict(),
                    "status": self.status.to_dict(),
                    "jobs": self._jobs
                }
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return True
        except Exception as e:
            logger.error(f"Failed to save CronJob {self.namespace}/{self.name}: {e}")
            return False
    
    def delete(self) -> bool:
        """
        Delete the CronJob.
        
        Returns:
            bool: Success or failure
        """
        try:
            # Delete all jobs
            for job_name in self._jobs:
                job = Job.get_job(job_name, self.namespace)
                if job:
                    job.delete()
            
            # Delete file
            file_path = self._file_path()
            if os.path.exists(file_path):
                os.remove(file_path)
            
            return True
        except Exception as e:
            logger.error(f"Failed to delete CronJob {self.namespace}/{self.name}: {e}")
            return False
    
    def reconcile(self) -> bool:
        """
        Reconcile the CronJob to match the desired state.
        
        Returns:
            bool: Success or failure
        """
        try:
            with self._lock:
                # Skip if suspended
                if self.spec.suspend:
                    return True
                
                # Get current time
                now = datetime.now()
                
                # Check if it's time to schedule a new job
                next_schedule_time = None
                if self.status.last_schedule_time is not None:
                    last_time = datetime.fromtimestamp(self.status.last_schedule_time)
                    next_schedule_time = self.spec.schedule.next_execution_time(last_time)
                else:
                    next_schedule_time = self.spec.schedule.next_execution_time()
                
                # Check if we need to create a new job
                if next_schedule_time <= now:
                    # Update last schedule time
                    self.status.last_schedule_time = time.time()
                    
                    # Check deadline
                    if self.spec.starting_deadline_seconds is not None:
                        deadline = now - timedelta(seconds=self.spec.starting_deadline_seconds)
                        if next_schedule_time < deadline:
                            logger.warning(f"Missed starting deadline for CronJob {self.namespace}/{self.name}")
                            return self.save()
                    
                    # Check concurrency policy
                    if self.spec.concurrency_policy != "Allow" and self.status.active:
                        if self.spec.concurrency_policy == "Forbid":
                            logger.info(f"Skipping job creation due to concurrency policy for CronJob {self.namespace}/{self.name}")
                            return self.save()
                        elif self.spec.concurrency_policy == "Replace":
                            # Delete active jobs
                            for active_job in self.status.active:
                                job_name = active_job.get("name")
                                if job_name:
                                    job = Job.get_job(job_name, self.namespace)
                                    if job:
                                        job.delete()
                            
                            # Clear active jobs
                            self.status.active = []
                    
                    # Create a new job
                    job = self._create_job()
                    if job:
                        # Add to active jobs
                        self.status.active.append({
                            "name": job.name,
                            "uid": job.metadata["uid"]
                        })
                        self.status.last_successful_time = self.status.last_schedule_time
                
                # Update job status
                active_jobs = []
                for active_job in self.status.active:
                    job_name = active_job.get("name")
                    if job_name:
                        job = Job.get_job(job_name, self.namespace)
                        if job:
                            # Check if job is still active
                            if job.status.active > 0:
                                active_jobs.append(active_job)
                
                self.status.active = active_jobs
                
                # Clean up old jobs
                self._cleanup_jobs()
                
                return self.save()
        except Exception as e:
            logger.error(f"Failed to reconcile CronJob {self.namespace}/{self.name}: {e}")
            return False
    
    def _create_job(self) -> Optional[Job]:
        """
        Create a job for this CronJob.
        
        Returns:
            Created Job or None if creation failed
        """
        try:
            # Create a unique name for the job
            job_name = f"{self.name}-{int(time.time())}"
            
            # Create job from template
            job_template = self.spec.job_template
            
            # Create job spec
            job_spec = JobSpec.from_dict(job_template.get("spec", {}))
            
            # Create job
            job = Job(
                name=job_name,
                namespace=self.namespace,
                spec=job_spec
            )
            
            # Set owner reference
            job.metadata["ownerReferences"] = [{
                "apiVersion": "v1",
                "kind": "CronJob",
                "name": self.name,
                "uid": self.metadata["uid"]
            }]
            
            # Copy labels from template
            job.metadata["labels"] = job_template.get("metadata", {}).get("labels", {}).copy()
            job.metadata["labels"]["cronjob-name"] = self.name
            
            # Save job
            if job.save():
                # Add job to cronjob
                self._jobs.append(job_name)
                return job
        except Exception as e:
            logger.error(f"Failed to create job for CronJob {self.namespace}/{self.name}: {e}")
        
        return None
    
    def _cleanup_jobs(self) -> None:
        """Clean up old jobs based on history limits."""
        # Get all jobs
        jobs = []
        for job_name in self._jobs:
            job = Job.get_job(job_name, self.namespace)
            if job:
                jobs.append(job)
        
        # Separate successful and failed jobs
        successful_jobs = []
        failed_jobs = []
        
        for job in jobs:
            # Check job conditions
            for condition in job.status.conditions:
                if condition.get("type") == "Complete" and condition.get("status") == "True":
                    successful_jobs.append(job)
                    break
                elif condition.get("type") == "Failed" and condition.get("status") == "True":
                    failed_jobs.append(job)
                    break
        
        # Sort by completion time
        successful_jobs.sort(key=lambda j: j.status.completion_time or 0)
        failed_jobs.sort(key=lambda j: j.status.completion_time or 0)
        
        # Delete excess successful jobs
        if len(successful_jobs) > self.spec.successful_jobs_history_limit:
            excess = len(successful_jobs) - self.spec.successful_jobs_history_limit
            for job in successful_jobs[:excess]:
                # Remove from job list
                if job.name in self._jobs:
                    self._jobs.remove(job.name)
                
                # Delete job
                job.delete()
        
        # Delete excess failed jobs
        if len(failed_jobs) > self.spec.failed_jobs_history_limit:
            excess = len(failed_jobs) - self.spec.failed_jobs_history_limit
            for job in failed_jobs[:excess]:
                # Remove from job list
                if job.name in self._jobs:
                    self._jobs.remove(job.name)
                
                # Delete job
                job.delete()
    
    @staticmethod
    def list_cron_jobs(namespace: Optional[str] = None) -> List['CronJob']:
        """
        List all CronJobs.
        
        Args:
            namespace: Namespace to filter by
            
        Returns:
            List of CronJobs
        """
        cron_jobs = []
        
        try:
            # Check namespace
            if namespace:
                namespaces = [namespace]
            else:
                # List all namespaces
                namespaces = []
                namespace_dir = CRONJOB_PATH
                if os.path.exists(namespace_dir):
                    namespaces = os.listdir(namespace_dir)
            
            # List CronJobs in each namespace
            for ns in namespaces:
                namespace_dir = os.path.join(CRONJOB_PATH, ns)
                if not os.path.isdir(namespace_dir):
                    continue
                
                for filename in os.listdir(namespace_dir):
                    if not filename.endswith('.json'):
                        continue
                    
                    cron_job_name = filename[:-5]  # Remove .json extension
                    cron_job = CronJob(cron_job_name, ns)
                    cron_jobs.append(cron_job)
        except Exception as e:
            logger.error(f"Failed to list CronJobs: {e}")
        
        return cron_jobs
    
    @staticmethod
    def get_cron_job(name: str, namespace: str = "default") -> Optional['CronJob']:
        """
        Get a CronJob by name and namespace.
        
        Args:
            name: CronJob name
            namespace: Namespace
            
        Returns:
            CronJob object or None if not found
        """
        cron_job = CronJob(name, namespace)
        
        if os.path.exists(cron_job._file_path()):
            return cron_job
        
        return None


class CronJobController:
    """
    Controller for CronJobs in the KOS orchestration system.
    
    This class manages the reconciliation of CronJobs.
    """
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        """Create or return the singleton instance."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CronJobController, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the CronJob controller."""
        if self._initialized:
            return
        
        self._initialized = True
        self._stop_event = threading.Event()
        self._reconcile_thread = None
        
        # Start reconciliation thread
        self.start()
    
    def start(self) -> bool:
        """
        Start the CronJob controller.
        
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
        Stop the CronJob controller.
        
        Returns:
            bool: Success or failure
        """
        if not self._reconcile_thread or not self._reconcile_thread.is_alive():
            return True
        
        self._stop_event.set()
        self._reconcile_thread.join(timeout=5)
        
        return not self._reconcile_thread.is_alive()
    
    def _reconcile_loop(self) -> None:
        """Reconciliation loop for the CronJob controller."""
        while not self._stop_event.is_set():
            try:
                self.reconcile()
            except Exception as e:
                logger.error(f"Error in CronJob controller reconciliation loop: {e}")
            
            # Sleep for a while
            self._stop_event.wait(30)  # Check every 30 seconds
    
    def reconcile(self) -> bool:
        """
        Reconcile all CronJobs.
        
        Returns:
            bool: Success or failure
        """
        try:
            # List all CronJobs
            cron_jobs = CronJob.list_cron_jobs()
            
            # Reconcile each CronJob
            for cron_job in cron_jobs:
                try:
                    cron_job.reconcile()
                except Exception as e:
                    logger.error(f"Failed to reconcile CronJob {cron_job.namespace}/{cron_job.name}: {e}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to reconcile CronJobs: {e}")
            return False
    
    def is_running(self) -> bool:
        """
        Check if the controller is running.
        
        Returns:
            bool: True if running
        """
        return self._reconcile_thread is not None and self._reconcile_thread.is_alive()
    
    @staticmethod
    def instance() -> 'CronJobController':
        """
        Get the singleton instance.
        
        Returns:
            CronJobController instance
        """
        return CronJobController()


def start_cronjob_controller() -> bool:
    """
    Start the CronJob controller.
    
    Returns:
        bool: Success or failure
    """
    controller = CronJobController.instance()
    return controller.start()


def stop_cronjob_controller() -> bool:
    """
    Stop the CronJob controller.
    
    Returns:
        bool: Success or failure
    """
    controller = CronJobController.instance()
    return controller.stop()

"""
KOS Task Scheduler

This module provides a cron-like task scheduling system for KOS,
allowing for time-based job scheduling.
"""

import os
import sys
import time
import json
import logging
import threading
import re
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

# Set up logging
logger = logging.getLogger('KOS.scheduler')

# Job registry
JOBS = {}
JOB_LOCK = threading.Lock()

class JobStatus:
    """Job status constants"""
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DISABLED = "disabled"

class JobRecord:
    """Record of a job execution"""
    
    def __init__(self, job_id: str, start_time: float):
        """Initialize job record"""
        self.job_id = job_id
        self.start_time = start_time
        self.end_time = None
        self.exit_code = None
        self.output = ""
        self.error = ""
        self.duration = None
    
    def complete(self, exit_code: int, output: str, error: str):
        """Mark job as completed"""
        self.end_time = time.time()
        self.exit_code = exit_code
        self.output = output
        self.error = error
        self.duration = self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "job_id": self.job_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "exit_code": self.exit_code,
            "output": self.output,
            "error": self.error,
            "duration": self.duration
        }

class CronExpression:
    """Cron expression parser and matcher"""
    
    def __init__(self, expression: str):
        """
        Initialize cron expression
        
        Args:
            expression: Cron expression (e.g., "* * * * *")
        """
        self.expression = expression
        self.minutes = None
        self.hours = None
        self.days_of_month = None
        self.months = None
        self.days_of_week = None
        self.is_valid = False
        self.error = None
        
        self._parse()
    
    def _parse(self):
        """Parse cron expression"""
        # Special expressions
        if self.expression == "@yearly" or self.expression == "@annually":
            self.expression = "0 0 1 1 *"
        elif self.expression == "@monthly":
            self.expression = "0 0 1 * *"
        elif self.expression == "@weekly":
            self.expression = "0 0 * * 0"
        elif self.expression == "@daily" or self.expression == "@midnight":
            self.expression = "0 0 * * *"
        elif self.expression == "@hourly":
            self.expression = "0 * * * *"
        
        # Parse fields
        fields = self.expression.split()
        
        if len(fields) != 5:
            self.is_valid = False
            self.error = "Invalid cron expression format"
            return
        
        try:
            self.minutes = self._parse_field(fields[0], 0, 59)
            self.hours = self._parse_field(fields[1], 0, 23)
            self.days_of_month = self._parse_field(fields[2], 1, 31)
            self.months = self._parse_field(fields[3], 1, 12)
            self.days_of_week = self._parse_field(fields[4], 0, 6)  # 0 = Sunday
            
            self.is_valid = True
        except ValueError as e:
            self.is_valid = False
            self.error = str(e)
    
    def _parse_field(self, field: str, min_val: int, max_val: int) -> List[int]:
        """
        Parse a cron field
        
        Args:
            field: Field string
            min_val: Minimum valid value
            max_val: Maximum valid value
            
        Returns:
            List of valid values for the field
        """
        result = set()
        
        # Handle all values
        if field == "*":
            return list(range(min_val, max_val + 1))
        
        # Handle comma-separated values
        for part in field.split(","):
            if "-" in part:
                # Handle ranges
                start, end = map(int, part.split("-"))
                if start < min_val or end > max_val:
                    raise ValueError(f"Value out of range: {part}")
                result.update(range(start, end + 1))
            elif "/" in part:
                # Handle step values
                if part.startswith("*/"):
                    # Every n starting from min_val
                    step = int(part[2:])
                    result.update(range(min_val, max_val + 1, step))
                else:
                    # Every n starting from specified value
                    start, step = part.split("/")
                    start = int(start)
                    step = int(step)
                    if start < min_val:
                        raise ValueError(f"Value out of range: {part}")
                    result.update(range(start, max_val + 1, step))
            else:
                # Handle single values
                value = int(part)
                if value < min_val or value > max_val:
                    raise ValueError(f"Value out of range: {part}")
                result.add(value)
        
        return sorted(list(result))
    
    def matches(self, dt: datetime) -> bool:
        """
        Check if datetime matches cron expression
        
        Args:
            dt: Datetime to check
            
        Returns:
            True if matches, False otherwise
        """
        if not self.is_valid:
            return False
        
        return (
            dt.minute in self.minutes and
            dt.hour in self.hours and
            dt.day in self.days_of_month and
            dt.month in self.months and
            dt.weekday() in [(x + 1) % 7 for x in self.days_of_week]  # Convert to Python's weekday (0 = Monday)
        )
    
    def next_run(self, after: datetime = None) -> Optional[datetime]:
        """
        Get next run time
        
        Args:
            after: Find next run after this time (default: now)
            
        Returns:
            Next run time or None if expression is invalid
        """
        if not self.is_valid:
            return None
        
        if after is None:
            after = datetime.now().replace(second=0, microsecond=0)
        else:
            after = after.replace(second=0, microsecond=0)
        
        # Try for up to a year of minutes
        for _ in range(525600):  # 60 * 24 * 365 = minutes in a year
            after += timedelta(minutes=1)
            if self.matches(after):
                return after
        
        return None

class Job:
    """Scheduled job"""
    
    def __init__(self, job_id: str, name: str, command: str, schedule: str, 
                 enabled: bool = True, working_dir: str = None, 
                 environment: Dict[str, str] = None, user: str = None):
        """
        Initialize job
        
        Args:
            job_id: Job ID
            name: Job name
            command: Command to execute
            schedule: Cron expression
            enabled: Whether job is enabled
            working_dir: Working directory
            environment: Environment variables
            user: User to run as
        """
        self.id = job_id
        self.name = name
        self.command = command
        self.schedule_expression = schedule
        self.schedule = CronExpression(schedule)
        self.enabled = enabled
        self.working_dir = working_dir or os.getcwd()
        self.environment = environment or {}
        self.user = user
        
        # Runtime state
        self.status = JobStatus.WAITING
        self.last_run = None
        self.next_run = self.schedule.next_run()
        self.execution_count = 0
        self.history = []  # List of JobRecord objects
        self.max_history = 100  # Maximum number of historical records to keep
    
    def should_run(self, now: datetime) -> bool:
        """
        Check if job should run at the specified time
        
        Args:
            now: Current time
            
        Returns:
            True if job should run, False otherwise
        """
        if not self.enabled or self.status == JobStatus.RUNNING:
            return False
        
        return self.schedule.matches(now)
    
    def run(self) -> JobRecord:
        """
        Run the job
        
        Returns:
            Job record
        """
        if self.status == JobStatus.RUNNING:
            raise RuntimeError("Job is already running")
        
        # Update state
        self.status = JobStatus.RUNNING
        self.last_run = datetime.now()
        self.next_run = self.schedule.next_run(self.last_run)
        
        # Create job record
        record = JobRecord(self.id, time.time())
        
        try:
            # Prepare environment
            env = os.environ.copy()
            env.update(self.environment)
            
            # Run command
            process = subprocess.Popen(
                self.command,
                shell=True,
                cwd=self.working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            # Update record
            record.complete(process.returncode, stdout, stderr)
            
            # Update state
            self.status = JobStatus.COMPLETED if process.returncode == 0 else JobStatus.FAILED
            self.execution_count += 1
            
            # Add to history
            self.history.append(record)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            
            # Log completion
            logger.info(f"Job {self.name} completed with exit code {process.returncode}")
            
            return record
        
        except Exception as e:
            # Update record with error
            record.complete(1, "", str(e))
            
            # Update state
            self.status = JobStatus.FAILED
            self.execution_count += 1
            
            # Add to history
            self.history.append(record)
            if len(self.history) > self.max_history:
                self.history.pop(0)
            
            # Log error
            logger.error(f"Error running job {self.name}: {str(e)}")
            
            return record
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "command": self.command,
            "schedule": self.schedule_expression,
            "enabled": self.enabled,
            "working_dir": self.working_dir,
            "environment": self.environment,
            "user": self.user,
            "status": self.status,
            "last_run": self.last_run.timestamp() if self.last_run else None,
            "next_run": self.next_run.timestamp() if self.next_run else None,
            "execution_count": self.execution_count,
            "history": [record.to_dict() for record in self.history[-10:]]  # Last 10 records
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create from dictionary"""
        job = cls(
            job_id=data["id"],
            name=data["name"],
            command=data["command"],
            schedule=data["schedule"],
            enabled=data["enabled"],
            working_dir=data["working_dir"],
            environment=data["environment"],
            user=data["user"]
        )
        
        job.status = data.get("status", JobStatus.WAITING)
        job.execution_count = data.get("execution_count", 0)
        
        if data.get("last_run"):
            job.last_run = datetime.fromtimestamp(data["last_run"])
        
        # History is not restored from dict to avoid excessive memory usage
        
        return job

class Scheduler:
    """Task scheduler"""
    
    def __init__(self):
        """Initialize scheduler"""
        self.running = False
        self.scheduler_thread = None
        self.executor_thread = None
        self.lock = threading.RLock()
        self.execution_queue = []  # Jobs queued for execution
        self.queue_lock = threading.Lock()
    
    def start(self) -> bool:
        """
        Start scheduler
        
        Returns:
            Success status
        """
        with self.lock:
            if self.running:
                logger.warning("Scheduler is already running")
                return False
            
            self.running = True
            
            # Start scheduler thread
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            
            # Start executor thread
            self.executor_thread = threading.Thread(target=self._executor_loop)
            self.executor_thread.daemon = True
            self.executor_thread.start()
            
            logger.info("Scheduler started")
            return True
    
    def stop(self) -> bool:
        """
        Stop scheduler
        
        Returns:
            Success status
        """
        with self.lock:
            if not self.running:
                logger.warning("Scheduler is not running")
                return False
            
            self.running = False
            
            # Threads will terminate on their own due to running flag
            logger.info("Scheduler stopped")
            return True
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self.running
    
    def _scheduler_loop(self):
        """Scheduler thread loop"""
        logger.info("Scheduler loop started")
        
        last_minute = -1
        
        while self.running:
            try:
                # Check once per second
                time.sleep(1)
                
                # Get current time
                now = datetime.now()
                
                # Check if minute has changed
                if now.minute == last_minute:
                    continue
                
                last_minute = now.minute
                
                # Check all jobs
                with JOB_LOCK:
                    for job in JOBS.values():
                        if job.should_run(now):
                            # Queue job for execution
                            with self.queue_lock:
                                self.execution_queue.append(job)
                            
                            logger.info(f"Queued job for execution: {job.name}")
            
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(5)  # Sleep longer on error
        
        logger.info("Scheduler loop stopped")
    
    def _executor_loop(self):
        """Job executor thread loop"""
        logger.info("Executor loop started")
        
        while self.running:
            try:
                # Check if there are jobs to execute
                job = None
                with self.queue_lock:
                    if self.execution_queue:
                        job = self.execution_queue.pop(0)
                
                if job:
                    # Execute job
                    logger.info(f"Executing job: {job.name}")
                    job.run()
                else:
                    # Sleep for a bit
                    time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in executor loop: {str(e)}")
                time.sleep(1)  # Sleep longer on error
        
        logger.info("Executor loop stopped")

class SchedulerManager:
    """Manager for scheduler operations"""
    
    @staticmethod
    def create_job(name: str, command: str, schedule: str, 
                  enabled: bool = True, working_dir: str = None,
                  environment: Dict[str, str] = None, user: str = None) -> Tuple[bool, str, Optional[Job]]:
        """
        Create a new job
        
        Args:
            name: Job name
            command: Command to execute
            schedule: Cron expression
            enabled: Whether job is enabled
            working_dir: Working directory
            environment: Environment variables
            user: User to run as
            
        Returns:
            (success, message, job)
        """
        # Validate cron expression
        cron = CronExpression(schedule)
        if not cron.is_valid:
            return False, f"Invalid cron expression: {cron.error}", None
        
        # Generate job ID
        job_id = str(uuid.uuid4())[:8]
        
        # Create job
        job = Job(
            job_id=job_id,
            name=name,
            command=command,
            schedule=schedule,
            enabled=enabled,
            working_dir=working_dir,
            environment=environment,
            user=user
        )
        
        # Add to registry
        with JOB_LOCK:
            JOBS[job_id] = job
        
        return True, f"Job created: {name}", job
    
    @staticmethod
    def get_job(job_id: str) -> Optional[Job]:
        """
        Get job by ID
        
        Args:
            job_id: Job ID
            
        Returns:
            Job or None if not found
        """
        with JOB_LOCK:
            return JOBS.get(job_id)
    
    @staticmethod
    def get_job_by_name(name: str) -> Optional[Job]:
        """
        Get job by name
        
        Args:
            name: Job name
            
        Returns:
            Job or None if not found
        """
        with JOB_LOCK:
            for job in JOBS.values():
                if job.name == name:
                    return job
            
            return None
    
    @staticmethod
    def list_jobs() -> List[Job]:
        """
        List all jobs
        
        Returns:
            List of jobs
        """
        with JOB_LOCK:
            return list(JOBS.values())
    
    @staticmethod
    def update_job(job_id: str, name: str = None, command: str = None,
                  schedule: str = None, enabled: bool = None,
                  working_dir: str = None, environment: Dict[str, str] = None,
                  user: str = None) -> Tuple[bool, str]:
        """
        Update a job
        
        Args:
            job_id: Job ID
            name: New name (None to keep current)
            command: New command (None to keep current)
            schedule: New schedule (None to keep current)
            enabled: New enabled status (None to keep current)
            working_dir: New working directory (None to keep current)
            environment: New environment variables (None to keep current)
            user: New user (None to keep current)
            
        Returns:
            (success, message)
        """
        with JOB_LOCK:
            if job_id not in JOBS:
                return False, f"Job not found: {job_id}"
            
            job = JOBS[job_id]
            
            if name is not None:
                job.name = name
            
            if command is not None:
                job.command = command
            
            if schedule is not None:
                # Validate cron expression
                cron = CronExpression(schedule)
                if not cron.is_valid:
                    return False, f"Invalid cron expression: {cron.error}"
                
                job.schedule_expression = schedule
                job.schedule = cron
                job.next_run = cron.next_run()
            
            if enabled is not None:
                job.enabled = enabled
            
            if working_dir is not None:
                job.working_dir = working_dir
            
            if environment is not None:
                job.environment = environment
            
            if user is not None:
                job.user = user
            
            return True, f"Job updated: {job.name}"
    
    @staticmethod
    def delete_job(job_id: str) -> Tuple[bool, str]:
        """
        Delete a job
        
        Args:
            job_id: Job ID
            
        Returns:
            (success, message)
        """
        with JOB_LOCK:
            if job_id not in JOBS:
                return False, f"Job not found: {job_id}"
            
            job = JOBS[job_id]
            del JOBS[job_id]
            
            return True, f"Job deleted: {job.name}"
    
    @staticmethod
    def enable_job(job_id: str) -> Tuple[bool, str]:
        """
        Enable a job
        
        Args:
            job_id: Job ID
            
        Returns:
            (success, message)
        """
        with JOB_LOCK:
            if job_id not in JOBS:
                return False, f"Job not found: {job_id}"
            
            job = JOBS[job_id]
            job.enabled = True
            
            return True, f"Job enabled: {job.name}"
    
    @staticmethod
    def disable_job(job_id: str) -> Tuple[bool, str]:
        """
        Disable a job
        
        Args:
            job_id: Job ID
            
        Returns:
            (success, message)
        """
        with JOB_LOCK:
            if job_id not in JOBS:
                return False, f"Job not found: {job_id}"
            
            job = JOBS[job_id]
            job.enabled = False
            
            return True, f"Job disabled: {job.name}"
    
    @staticmethod
    def run_job_now(job_id: str) -> Tuple[bool, str]:
        """
        Run a job immediately
        
        Args:
            job_id: Job ID
            
        Returns:
            (success, message)
        """
        with JOB_LOCK:
            if job_id not in JOBS:
                return False, f"Job not found: {job_id}"
            
            job = JOBS[job_id]
            
            if job.status == JobStatus.RUNNING:
                return False, f"Job is already running: {job.name}"
            
            # Run in a separate thread
            threading.Thread(target=job.run).start()
            
            return True, f"Job started: {job.name}"
    
    @staticmethod
    def save_jobs(filepath: str) -> Tuple[bool, str]:
        """
        Save jobs to file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            with JOB_LOCK:
                data = {jid: job.to_dict() for jid, job in JOBS.items()}
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True, f"Jobs saved to {filepath}"
        except Exception as e:
            return False, f"Failed to save jobs: {str(e)}"
    
    @staticmethod
    def load_jobs(filepath: str) -> Tuple[bool, str]:
        """
        Load jobs from file
        
        Args:
            filepath: File path
            
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"File not found: {filepath}"
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            with JOB_LOCK:
                JOBS.clear()
                for jid, job_data in data.items():
                    JOBS[jid] = Job.from_dict(job_data)
            
            return True, f"Jobs loaded from {filepath}"
        except Exception as e:
            return False, f"Failed to load jobs: {str(e)}"

# Singleton scheduler instance
_scheduler = Scheduler()

def get_scheduler() -> Scheduler:
    """Get scheduler instance"""
    return _scheduler

def initialize():
    """Initialize scheduler system"""
    logger.info("Initializing scheduler system")
    
    # Create scheduler directory
    scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
    os.makedirs(scheduler_dir, exist_ok=True)
    
    # Load jobs if they exist
    jobs_db = os.path.join(scheduler_dir, 'jobs.json')
    if os.path.exists(jobs_db):
        SchedulerManager.load_jobs(jobs_db)
    
    # Start scheduler
    _scheduler.start()
    
    logger.info("Scheduler system initialized")

# Initialize on import
initialize()

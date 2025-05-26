"""
KOS Task Scheduling System

This module provides cron-like task scheduling capabilities, including:
- Cron expression parsing and matching
- Job scheduling with customizable timing
- Job history tracking and output/error capture
- Special time expressions (@yearly, @monthly, etc.)
- Immediate job execution capability
"""

import logging
import os
import threading
import time
import json
import uuid
import re
import datetime
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable, Set, Tuple

from .. import process
from .. import ipc

# Initialize logging
logger = logging.getLogger('KOS.scheduler')

# Scheduler constants
SCHEDULER_BASE_DIR = "/tmp/kos/scheduler"
SCHEDULER_CONFIG_DIR = os.path.join(SCHEDULER_BASE_DIR, "config")
SCHEDULER_STATE_DIR = os.path.join(SCHEDULER_BASE_DIR, "state")
SCHEDULER_HISTORY_DIR = os.path.join(SCHEDULER_BASE_DIR, "history")

# Job status
class JobStatus(Enum):
    PENDING = auto()    # Job is scheduled but hasn't run yet
    RUNNING = auto()    # Job is currently running
    SUCCEEDED = auto()  # Job completed successfully
    FAILED = auto()     # Job failed with an error
    SKIPPED = auto()    # Job was skipped (e.g. due to previous job still running)
    CANCELLED = auto()  # Job was cancelled

# Special time expressions
SPECIAL_EXPRESSIONS = {
    '@yearly': '0 0 1 1 *',
    '@annually': '0 0 1 1 *',
    '@monthly': '0 0 1 * *',
    '@weekly': '0 0 * * 0',
    '@daily': '0 0 * * *',
    '@midnight': '0 0 * * *',
    '@hourly': '0 * * * *'
}

# Scheduler global state
_jobs = {}  # All registered jobs
_scheduler_lock = threading.RLock()  # Lock for thread-safe operations
_scheduler_thread = None  # Scheduler thread that checks for jobs to run
_executor_thread = None  # Executor thread that runs jobs
_job_queue = []  # Queue of jobs to be executed
_queue_condition = threading.Condition()  # Condition variable for the job queue
_is_initialized = False  # Whether the scheduler is initialized

class CronExpression:
    """
    Parse and match cron expressions
    
    Format: minute hour day_of_month month day_of_week
    
    Values:
    - minute: 0-59
    - hour: 0-23
    - day_of_month: 1-31
    - month: 1-12 or JAN-DEC
    - day_of_week: 0-6 or SUN-SAT (0 is Sunday)
    
    Special characters:
    - *: any value
    - ,: value list separator
    - -: range of values
    - /: step values
    """
    def __init__(self, expression):
        """Initialize with a cron expression"""
        self.original = expression
        
        # Handle special expressions
        if expression in SPECIAL_EXPRESSIONS:
            expression = SPECIAL_EXPRESSIONS[expression]
        
        # Parse the expression
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression format: {expression}")
        
        self.minute = self._parse_field(parts[0], 0, 59)
        self.hour = self._parse_field(parts[1], 0, 23)
        self.day = self._parse_field(parts[2], 1, 31)
        self.month = self._parse_field(parts[3], 1, 12)
        self.weekday = self._parse_field(parts[4], 0, 6)
        
        # For month and weekday, also accept names
        self.month_names = {
            'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
            'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
        }
        
        self.weekday_names = {
            'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6
        }
    
    def _parse_field(self, field, min_val, max_val):
        """Parse a cron field into a set of valid values"""
        if field == '*':
            return set(range(min_val, max_val + 1))
        
        values = set()
        
        # Handle comma-separated lists
        for part in field.split(','):
            # Handle step values
            if '/' in part:
                range_part, step = part.split('/')
                step = int(step)
                
                # Handle range with steps
                if '-' in range_part:
                    start, end = map(int, range_part.split('-'))
                    values.update(range(start, end + 1, step))
                # Handle wildcard with steps
                elif range_part == '*':
                    values.update(range(min_val, max_val + 1, step))
                else:
                    start = int(range_part)
                    values.update(range(start, max_val + 1, step))
            
            # Handle ranges
            elif '-' in part:
                start, end = map(int, part.split('-'))
                values.update(range(start, end + 1))
            
            # Handle single values
            else:
                values.add(int(part))
        
        # Validate values
        for val in values:
            if val < min_val or val > max_val:
                raise ValueError(f"Value {val} out of range for cron field")
        
        return values
    
    def matches(self, dt=None):
        """Check if the cron expression matches the given datetime"""
        if dt is None:
            dt = datetime.datetime.now()
        
        return (dt.minute in self.minute and
                dt.hour in self.hour and
                dt.day in self.day and
                dt.month in self.month and
                dt.weekday() in self.weekday)
    
    def next_run_time(self, after=None):
        """
        Calculate the next time this cron expression will match
        
        Args:
            after: The time to start looking from (default: now)
        
        Returns:
            datetime of next match
        """
        if after is None:
            after = datetime.datetime.now()
        
        # Start checking from the next minute
        candidate = after.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
        
        # Check up to 10 years in the future (to avoid infinite loop for impossible schedules)
        max_check = candidate + datetime.timedelta(days=365*10)
        
        while candidate < max_check:
            if self.matches(candidate):
                return candidate
            
            candidate += datetime.timedelta(minutes=1)
        
        return None  # No match found within reasonable time
    
    def __str__(self):
        return self.original

class Job:
    """Represents a scheduled job (task)"""
    def __init__(self, name, command, schedule=None, enabled=True, working_dir=None, 
                 environment=None, user=None, description=None):
        """
        Initialize a scheduled job
        
        Args:
            name: Unique job name
            command: Command to execute
            schedule: Cron expression or special expression
            enabled: Whether the job is enabled
            working_dir: Working directory
            environment: Environment variables
            user: User to run as
            description: Job description
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self.command = command
        self.schedule = schedule
        if schedule:
            self.cron_expression = CronExpression(schedule)
        else:
            self.cron_expression = None
        self.enabled = enabled
        self.working_dir = working_dir
        self.environment = environment or {}
        self.user = user
        self.description = description or f"KOS job: {name}"
        
        # Runtime state
        self.status = JobStatus.PENDING
        self.last_run_time = None
        self.next_run_time = None
        self.last_run_duration = None
        self.last_exit_code = None
        self.run_count = 0
        self.success_count = 0
        self.fail_count = 0
        self.current_pid = None
        
        # Configuration paths
        self.config_path = os.path.join(SCHEDULER_CONFIG_DIR, f"{name}.job")
        self.state_path = os.path.join(SCHEDULER_STATE_DIR, f"{name}.state")
        
        # Calculate next run time
        self.update_next_run_time()
    
    def update_next_run_time(self):
        """Update the next scheduled run time"""
        if self.cron_expression and self.enabled:
            self.next_run_time = self.cron_expression.next_run_time()
        else:
            self.next_run_time = None
    
    def save_config(self) -> bool:
        """Save job configuration to disk"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            config = {
                'id': self.id,
                'name': self.name,
                'command': self.command,
                'schedule': self.schedule,
                'enabled': self.enabled,
                'working_dir': self.working_dir,
                'environment': self.environment,
                'user': self.user,
                'description': self.description
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving job configuration for {self.name}: {e}")
            return False
    
    def save_state(self) -> bool:
        """Save job state to disk"""
        try:
            os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
            
            state = {
                'id': self.id,
                'name': self.name,
                'status': self.status.name,
                'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
                'next_run_time': self.next_run_time.isoformat() if self.next_run_time else None,
                'last_run_duration': self.last_run_duration,
                'last_exit_code': self.last_exit_code,
                'run_count': self.run_count,
                'success_count': self.success_count,
                'fail_count': self.fail_count,
                'current_pid': self.current_pid
            }
            
            with open(self.state_path, 'w') as f:
                json.dump(state, f, indent=2)
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving job state for {self.name}: {e}")
            return False
    
    @classmethod
    def load_from_config(cls, config_path) -> 'Job':
        """Load job from configuration file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            job = cls(
                name=config['name'],
                command=config['command'],
                schedule=config['schedule'],
                enabled=config['enabled'],
                working_dir=config['working_dir'],
                environment=config['environment'],
                user=config['user'],
                description=config['description']
            )
            
            job.id = config['id']
            
            # Load state if available
            state_path = os.path.join(SCHEDULER_STATE_DIR, f"{job.name}.state")
            if os.path.exists(state_path):
                try:
                    with open(state_path, 'r') as f:
                        state = json.load(f)
                    
                    job.status = JobStatus[state['status']]
                    
                    if state['last_run_time']:
                        job.last_run_time = datetime.datetime.fromisoformat(state['last_run_time'])
                    
                    if state['next_run_time']:
                        job.next_run_time = datetime.datetime.fromisoformat(state['next_run_time'])
                    
                    job.last_run_duration = state['last_run_duration']
                    job.last_exit_code = state['last_exit_code']
                    job.run_count = state['run_count']
                    job.success_count = state['success_count']
                    job.fail_count = state['fail_count']
                    job.current_pid = state['current_pid']
                except Exception as e:
                    logger.warning(f"Error loading job state for {job.name}: {e}")
            
            # Make sure next run time is up to date
            job.update_next_run_time()
            
            return job
        
        except Exception as e:
            logger.error(f"Error loading job from {config_path}: {e}")
            return None
    
    def run(self) -> bool:
        """Run the job now"""
        try:
            logger.info(f"Running job {self.name}")
            
            # Update state
            self.status = JobStatus.RUNNING
            self.last_run_time = datetime.datetime.now()
            self.current_pid = None
            self.run_count += 1
            self.save_state()
            
            # Prepare stdout/stderr pipes
            stdout_pipe = ipc.create_pipe(name=f"job_{self.id}_stdout")
            stderr_pipe = ipc.create_pipe(name=f"job_{self.id}_stderr")
            
            # Prepare environment
            env = os.environ.copy()
            env.update(self.environment)
            
            # Add special environment variables
            env['KOS_JOB_NAME'] = self.name
            env['KOS_JOB_ID'] = self.id
            env['KOS_STDOUT_PIPE'] = stdout_pipe
            env['KOS_STDERR_PIPE'] = stderr_pipe
            
            # Start the process
            start_time = time.time()
            
            self.current_pid = process.create_process(
                command=self.command,
                working_dir=self.working_dir,
                env=env,
                user=self.user
            )
            
            if not self.current_pid:
                logger.error(f"Failed to start process for job {self.name}")
                self.status = JobStatus.FAILED
                self.fail_count += 1
                self.save_state()
                return False
            
            logger.info(f"Job {self.name} started with PID {self.current_pid}")
            
            # Wait for process to complete
            exit_code = process.wait_for_process(self.current_pid)
            end_time = time.time()
            
            # Calculate duration
            self.last_run_duration = end_time - start_time
            self.last_exit_code = exit_code
            
            # Update status
            if exit_code == 0:
                self.status = JobStatus.SUCCEEDED
                self.success_count += 1
            else:
                self.status = JobStatus.FAILED
                self.fail_count += 1
            
            # Read output from pipes
            stdout_data = b""
            stderr_data = b""
            
            try:
                # Read up to 1MB from each pipe
                stdout_data = ipc.read_pipe(stdout_pipe, 1024*1024, nonblocking=True)
                stderr_data = ipc.read_pipe(stderr_pipe, 1024*1024, nonblocking=True)
            except Exception as e:
                logger.warning(f"Error reading job output: {e}")
            
            # Close pipes
            ipc.close_pipe(stdout_pipe)
            ipc.close_pipe(stderr_pipe)
            
            # Save job history
            self._save_job_history(stdout_data, stderr_data)
            
            # Update next run time
            self.current_pid = None
            self.update_next_run_time()
            self.save_state()
            
            logger.info(f"Job {self.name} completed with status {self.status.name}")
            return self.status == JobStatus.SUCCEEDED
        
        except Exception as e:
            logger.error(f"Error running job {self.name}: {e}")
            self.status = JobStatus.FAILED
            self.fail_count += 1
            self.current_pid = None
            self.update_next_run_time()
            self.save_state()
            return False
    
    def _save_job_history(self, stdout_data, stderr_data):
        """Save job execution history"""
        try:
            history_dir = os.path.join(SCHEDULER_HISTORY_DIR, self.name)
            os.makedirs(history_dir, exist_ok=True)
            
            # Use timestamp for history file name
            timestamp = self.last_run_time.strftime("%Y%m%d_%H%M%S")
            history_file = os.path.join(history_dir, f"{timestamp}.json")
            
            history = {
                'id': self.id,
                'name': self.name,
                'command': self.command,
                'status': self.status.name,
                'start_time': self.last_run_time.isoformat(),
                'duration': self.last_run_duration,
                'exit_code': self.last_exit_code,
                'stdout': stdout_data.decode('utf-8', errors='replace'),
                'stderr': stderr_data.decode('utf-8', errors='replace')
            }
            
            with open(history_file, 'w') as f:
                json.dump(history, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error saving job history for {self.name}: {e}")
    
    def cancel(self) -> bool:
        """Cancel a running job"""
        try:
            if self.status != JobStatus.RUNNING or not self.current_pid:
                logger.warning(f"Job {self.name} is not running, cannot cancel")
                return False
            
            logger.info(f"Cancelling job {self.name} (PID {self.current_pid})")
            
            # Send termination signal
            process.send_signal(self.current_pid, signal.SIGTERM)
            
            # Wait for process to terminate
            for _ in range(5):
                if not process.process_exists(self.current_pid):
                    break
                time.sleep(0.5)
            
            # Force kill if it's still running
            if process.process_exists(self.current_pid):
                process.send_signal(self.current_pid, signal.SIGKILL)
            
            # Update state
            self.status = JobStatus.CANCELLED
            self.fail_count += 1
            self.current_pid = None
            self.update_next_run_time()
            self.save_state()
            
            logger.info(f"Job {self.name} cancelled")
            return True
        
        except Exception as e:
            logger.error(f"Error cancelling job {self.name}: {e}")
            return False
    
    def get_history(self, limit=10) -> List[Dict[str, Any]]:
        """Get job execution history"""
        try:
            history_dir = os.path.join(SCHEDULER_HISTORY_DIR, self.name)
            if not os.path.exists(history_dir):
                return []
            
            # Get all history files sorted by timestamp (newest first)
            import glob
            history_files = glob.glob(os.path.join(history_dir, "*.json"))
            history_files.sort(reverse=True)
            
            result = []
            for i, history_file in enumerate(history_files):
                if i >= limit:
                    break
                
                try:
                    with open(history_file, 'r') as f:
                        history = json.load(f)
                    
                    # Truncate stdout/stderr to avoid huge amounts of data
                    if 'stdout' in history and len(history['stdout']) > 1000:
                        history['stdout'] = history['stdout'][:1000] + "...(truncated)"
                    
                    if 'stderr' in history and len(history['stderr']) > 1000:
                        history['stderr'] = history['stderr'][:1000] + "...(truncated)"
                    
                    result.append(history)
                except Exception as e:
                    logger.warning(f"Error loading history file {history_file}: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error getting history for job {self.name}: {e}")
            return []

# Scheduler manager functions
def initialize() -> bool:
    """Initialize the scheduler subsystem"""
    global _is_initialized, _scheduler_thread, _executor_thread
    
    if _is_initialized:
        return True
    
    try:
        logger.info("Initializing scheduler subsystem")
        
        # Create scheduler directories
        os.makedirs(SCHEDULER_BASE_DIR, exist_ok=True)
        os.makedirs(SCHEDULER_CONFIG_DIR, exist_ok=True)
        os.makedirs(SCHEDULER_STATE_DIR, exist_ok=True)
        os.makedirs(SCHEDULER_HISTORY_DIR, exist_ok=True)
        
        # Load existing jobs
        _load_jobs()
        
        # Start scheduler thread
        _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
        _scheduler_thread.start()
        
        # Start executor thread
        _executor_thread = threading.Thread(target=_executor_loop, daemon=True)
        _executor_thread.start()
        
        _is_initialized = True
        logger.info("Scheduler subsystem initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize scheduler subsystem: {e}")
        return False

def shutdown() -> bool:
    """Shutdown the scheduler subsystem"""
    global _is_initialized, _scheduler_thread, _executor_thread
    
    if not _is_initialized:
        return True
    
    try:
        logger.info("Shutting down scheduler subsystem")
        
        # Cancel all running jobs
        with _scheduler_lock:
            for job_name, job in _jobs.items():
                if job.status == JobStatus.RUNNING:
                    job.cancel()
        
        _is_initialized = False
        
        # Notify executor thread to exit
        with _queue_condition:
            _queue_condition.notify_all()
        
        # Wait for threads to terminate
        if _scheduler_thread and _scheduler_thread.is_alive():
            _scheduler_thread.join(timeout=3.0)
        
        if _executor_thread and _executor_thread.is_alive():
            _executor_thread.join(timeout=3.0)
        
        logger.info("Scheduler subsystem shut down successfully")
        return True
    
    except Exception as e:
        logger.error(f"Failed to shutdown scheduler subsystem: {e}")
        return False

def _load_jobs():
    """Load existing jobs from disk"""
    try:
        import glob
        
        # Find all job configuration files
        config_files = glob.glob(os.path.join(SCHEDULER_CONFIG_DIR, "*.job"))
        
        for config_path in config_files:
            job = Job.load_from_config(config_path)
            if job:
                _jobs[job.name] = job
                logger.info(f"Loaded job: {job.name}")
        
        logger.info(f"Loaded {len(_jobs)} jobs")
    
    except Exception as e:
        logger.error(f"Error loading jobs: {e}")

def _scheduler_loop():
    """Main scheduler loop that checks for jobs to run"""
    logger.info("Scheduler thread started")
    
    while _is_initialized:
        try:
            # Get current time
            now = datetime.datetime.now()
            
            # Check for jobs to run
            with _scheduler_lock:
                for job_name, job in _jobs.items():
                    if (job.enabled and job.next_run_time and 
                        job.next_run_time <= now and 
                        job.status not in (JobStatus.RUNNING, JobStatus.PENDING)):
                        
                        logger.info(f"Scheduling job {job_name} for execution")
                        job.status = JobStatus.PENDING
                        
                        # Add job to execution queue
                        with _queue_condition:
                            _job_queue.append(job_name)
                            _queue_condition.notify()
            
            # Sleep until the next minute
            # This ensures we wake up right at the start of a new minute
            next_minute = (now + datetime.timedelta(minutes=1)).replace(
                second=0, microsecond=0
            )
            sleep_time = (next_minute - now).total_seconds()
            time.sleep(max(0.5, min(sleep_time, 60)))  # At least 0.5s, at most 60s
            
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
            time.sleep(5.0)  # Sleep longer on error
    
    logger.info("Scheduler thread stopped")

def _executor_loop():
    """Job executor loop that runs jobs from the queue"""
    logger.info("Executor thread started")
    
    while _is_initialized:
        try:
            job_name = None
            
            # Wait for a job to be queued
            with _queue_condition:
                while not _job_queue and _is_initialized:
                    _queue_condition.wait(timeout=1.0)
                
                if not _is_initialized:
                    break
                
                if _job_queue:
                    job_name = _job_queue.pop(0)
            
            # Run the job
            if job_name and job_name in _jobs:
                with _scheduler_lock:
                    job = _jobs[job_name]
                    # Run the job in this thread
                    job.run()
                    # Update job next run time
                    job.update_next_run_time()
                    job.save_state()
            
        except Exception as e:
            logger.error(f"Error in executor loop: {e}")
            time.sleep(1.0)  # Sleep on error
    
    logger.info("Executor thread stopped")

def create_job(name: str, command: str, schedule: str = None, enabled: bool = True,
              working_dir: str = None, environment: Dict[str, str] = None,
              user: str = None, description: str = None) -> Optional[Job]:
    """Create a new job"""
    with _scheduler_lock:
        try:
            # Check if job already exists
            if name in _jobs:
                logger.warning(f"Job {name} already exists")
                return _jobs[name]
            
            # Validate schedule if provided
            if schedule:
                try:
                    CronExpression(schedule)
                except ValueError as e:
                    logger.error(f"Invalid schedule for job {name}: {e}")
                    return None
            
            # Create the job
            job = Job(
                name=name,
                command=command,
                schedule=schedule,
                enabled=enabled,
                working_directory=working_dir,
                environment=environment,
                user=user,
                description=description
            )
            
            # Save job configuration
            if not job.save_config():
                logger.error(f"Failed to save configuration for job {name}")
                return None
            
            # Add to registry
            _jobs[name] = job
            
            logger.info(f"Created job: {name}")
            return job
        
        except Exception as e:
            logger.error(f"Error creating job {name}: {e}")
            return None

def delete_job(name: str) -> bool:
    """Delete a job"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return False
            
            job = _jobs[name]
            
            # Cancel if running
            if job.status == JobStatus.RUNNING:
                job.cancel()
            
            # Remove configuration and state files
            if os.path.exists(job.config_path):
                os.remove(job.config_path)
            
            if os.path.exists(job.state_path):
                os.remove(job.state_path)
            
            # Remove from registry
            del _jobs[name]
            
            logger.info(f"Deleted job: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting job {name}: {e}")
            return False

def run_job_now(name: str) -> bool:
    """Run a job immediately"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return False
            
            job = _jobs[name]
            
            # Check if job is already running
            if job.status == JobStatus.RUNNING:
                logger.warning(f"Job {name} is already running")
                return False
            
            # Queue the job for immediate execution
            job.status = JobStatus.PENDING
            
            with _queue_condition:
                _job_queue.append(name)
                _queue_condition.notify()
            
            logger.info(f"Queued job {name} for immediate execution")
            return True
        
        except Exception as e:
            logger.error(f"Error running job {name}: {e}")
            return False

def enable_job(name: str, enabled: bool = True) -> bool:
    """Enable or disable a job"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return False
            
            job = _jobs[name]
            job.enabled = enabled
            job.update_next_run_time()
            job.save_config()
            
            logger.info(f"{'Enabled' if enabled else 'Disabled'} job: {name}")
            return True
        
        except Exception as e:
            logger.error(f"Error {'enabling' if enabled else 'disabling'} job {name}: {e}")
            return False

def list_jobs() -> List[Dict[str, Any]]:
    """List all jobs and their basic status"""
    with _scheduler_lock:
        try:
            return [
                {
                    'name': job.name,
                    'description': job.description,
                    'schedule': job.schedule,
                    'status': job.status.name,
                    'enabled': job.enabled,
                    'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                    'last_run_time': job.last_run_time.isoformat() if job.last_run_time else None,
                    'run_count': job.run_count,
                    'success_count': job.success_count,
                    'fail_count': job.fail_count
                }
                for job in _jobs.values()
            ]
        
        except Exception as e:
            logger.error(f"Error listing jobs: {e}")
            return []

def get_job_status(name: str) -> Optional[Dict[str, Any]]:
    """Get detailed status of a job"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return None
            
            job = _jobs[name]
            
            status = {
                'id': job.id,
                'name': job.name,
                'description': job.description,
                'command': job.command,
                'schedule': job.schedule,
                'status': job.status.name,
                'enabled': job.enabled,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'last_run_time': job.last_run_time.isoformat() if job.last_run_time else None,
                'last_run_duration': job.last_run_duration,
                'last_exit_code': job.last_exit_code,
                'run_count': job.run_count,
                'success_count': job.success_count,
                'fail_count': job.fail_count,
                'current_pid': job.current_pid,
                'working_dir': job.working_dir,
                'user': job.user
            }
            
            return status
        
        except Exception as e:
            logger.error(f"Error getting job status for {name}: {e}")
            return None

def get_job_history(name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get execution history for a job"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return []
            
            job = _jobs[name]
            return job.get_history(limit)
        
        except Exception as e:
            logger.error(f"Error getting job history for {name}: {e}")
            return []

def update_job(name: str, command: str = None, schedule: str = None, enabled: bool = None,
              working_dir: str = None, environment: Dict[str, str] = None,
              user: str = None, description: str = None) -> Optional[Job]:
    """Update an existing job"""
    with _scheduler_lock:
        try:
            # Check if job exists
            if name not in _jobs:
                logger.warning(f"Job {name} does not exist")
                return None
            
            job = _jobs[name]
            
            # Update fields if provided
            if command is not None:
                job.command = command
            
            if schedule is not None:
                # Validate schedule
                try:
                    CronExpression(schedule)
                    job.schedule = schedule
                    job.cron_expression = CronExpression(schedule)
                except ValueError as e:
                    logger.error(f"Invalid schedule for job {name}: {e}")
                    return None
            
            if enabled is not None:
                job.enabled = enabled
            
            if working_dir is not None:
                job.working_dir = working_dir
            
            if environment is not None:
                job.environment = environment
            
            if user is not None:
                job.user = user
            
            if description is not None:
                job.description = description
            
            # Update next run time
            job.update_next_run_time()
            
            # Save changes
            job.save_config()
            job.save_state()
            
            logger.info(f"Updated job: {name}")
            return job
        
        except Exception as e:
            logger.error(f"Error updating job {name}: {e}")
            return None

# Initialize locks
_scheduler_lock = threading.RLock()  # Lock for thread-safe operations

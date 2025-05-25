"""
Job Control Utilities for KOS Shell

This module provides Unix-like job control capabilities including
background processes, foreground/background switching, and job management.
"""

import os
import sys
import time
import signal
import logging
import shlex
import subprocess
import threading
from typing import Dict, List, Any, Optional, Union, Tuple

# Set up logging
logger = logging.getLogger('KOS.shell.commands.job_control')

# Job management globals
_jobs = {}  # job_id -> job_info
_job_lock = threading.RLock()
_next_job_id = 1
_current_job_id = None

# Signal names mapping
SIGNAL_NAMES = {
    signal.SIGINT: "INT",
    signal.SIGTERM: "TERM",
    signal.SIGKILL: "KILL",
    signal.SIGSTOP: "STOP",
    signal.SIGCONT: "CONT",
    signal.SIGHUP: "HUP",
    signal.SIGQUIT: "QUIT"
}


class Job:
    """Class representing a shell job (process or process group)"""
    
    def __init__(self, job_id: int, command: str, process: subprocess.Popen,
                 is_background: bool = False):
        """
        Initialize a new job
        
        Args:
            job_id: Job ID
            command: Command string
            process: Process object
            is_background: Whether job is running in background
        """
        self.job_id = job_id
        self.command = command
        self.process = process
        self.pid = process.pid
        self.is_background = is_background
        self.status = "Running"
        self.start_time = time.time()
        self.exit_code = None
        self.is_stopped = False
    
    def send_signal(self, sig: int) -> bool:
        """
        Send signal to job
        
        Args:
            sig: Signal number
        
        Returns:
            Success status
        """
        try:
            self.process.send_signal(sig)
            return True
        except Exception as e:
            logger.error(f"Error sending signal {sig} to job {self.job_id}: {e}")
            return False
    
    def poll(self) -> Optional[int]:
        """
        Check if job has terminated
        
        Returns:
            Exit code or None if still running
        """
        if self.exit_code is not None:
            return self.exit_code
        
        exit_code = self.process.poll()
        if exit_code is not None:
            self.exit_code = exit_code
            self.status = "Done" if exit_code == 0 else f"Exit {exit_code}"
        
        return exit_code
    
    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """
        Wait for job to complete
        
        Args:
            timeout: Timeout in seconds
        
        Returns:
            Exit code or None if timeout
        """
        try:
            exit_code = self.process.wait(timeout=timeout)
            self.exit_code = exit_code
            self.status = "Done" if exit_code == 0 else f"Exit {exit_code}"
            return exit_code
        except subprocess.TimeoutExpired:
            return None
    
    def stop(self) -> bool:
        """
        Stop job (SIGSTOP)
        
        Returns:
            Success status
        """
        result = self.send_signal(signal.SIGSTOP)
        if result:
            self.is_stopped = True
            self.status = "Stopped"
        return result
    
    def continue_job(self) -> bool:
        """
        Continue job (SIGCONT)
        
        Returns:
            Success status
        """
        result = self.send_signal(signal.SIGCONT)
        if result:
            self.is_stopped = False
            self.status = "Running"
        return result
    
    def terminate(self) -> bool:
        """
        Terminate job (SIGTERM)
        
        Returns:
            Success status
        """
        return self.send_signal(signal.SIGTERM)
    
    def kill(self) -> bool:
        """
        Kill job (SIGKILL)
        
        Returns:
            Success status
        """
        return self.send_signal(signal.SIGKILL)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary
        
        Returns:
            Dictionary representation
        """
        return {
            "job_id": self.job_id,
            "command": self.command,
            "pid": self.pid,
            "is_background": self.is_background,
            "status": self.status,
            "start_time": self.start_time,
            "exit_code": self.exit_code,
            "is_stopped": self.is_stopped
        }


class JobManager:
    """Manager for job operations"""
    
    @classmethod
    def create_job(cls, command: str, is_background: bool = False,
                  shell: bool = True, cwd: str = None,
                  env: Dict[str, str] = None) -> Tuple[bool, str, Optional[Job]]:
        """
        Create a new job
        
        Args:
            command: Command string
            is_background: Whether to run in background
            shell: Whether to use shell
            cwd: Working directory
            env: Environment variables
        
        Returns:
            (success, message, job)
        """
        global _next_job_id, _current_job_id
        
        try:
            # Start process
            process = subprocess.Popen(
                command,
                shell=shell,
                cwd=cwd or os.getcwd(),
                env=env or os.environ.copy(),
                stdout=None if is_background else subprocess.PIPE,
                stderr=None if is_background else subprocess.PIPE,
                text=True
            )
            
            # Create job
            with _job_lock:
                job_id = _next_job_id
                _next_job_id += 1
                
                job = Job(job_id, command, process, is_background)
                _jobs[job_id] = job
                
                if not is_background:
                    _current_job_id = job_id
                
                return True, f"Created job {job_id}", job
        
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            return False, str(e), None
    
    @classmethod
    def get_job(cls, job_id: int) -> Optional[Job]:
        """
        Get job by ID
        
        Args:
            job_id: Job ID
        
        Returns:
            Job object or None
        """
        with _job_lock:
            return _jobs.get(job_id)
    
    @classmethod
    def get_job_by_pid(cls, pid: int) -> Optional[Job]:
        """
        Get job by process ID
        
        Args:
            pid: Process ID
        
        Returns:
            Job object or None
        """
        with _job_lock:
            for job in _jobs.values():
                if job.pid == pid:
                    return job
            return None
    
    @classmethod
    def get_current_job(cls) -> Optional[Job]:
        """
        Get current job
        
        Returns:
            Current job or None
        """
        global _current_job_id
        
        with _job_lock:
            if _current_job_id is not None:
                return _jobs.get(_current_job_id)
            return None
    
    @classmethod
    def set_current_job(cls, job_id: int) -> bool:
        """
        Set current job
        
        Args:
            job_id: Job ID
        
        Returns:
            Success status
        """
        global _current_job_id
        
        with _job_lock:
            if job_id in _jobs:
                _current_job_id = job_id
                return True
            return False
    
    @classmethod
    def list_jobs(cls) -> List[Job]:
        """
        List all jobs
        
        Returns:
            List of jobs
        """
        with _job_lock:
            # Update status of all jobs
            for job in _jobs.values():
                job.poll()
            
            return list(_jobs.values())
    
    @classmethod
    def remove_job(cls, job_id: int) -> bool:
        """
        Remove job from registry
        
        Args:
            job_id: Job ID
        
        Returns:
            Success status
        """
        global _current_job_id
        
        with _job_lock:
            if job_id in _jobs:
                del _jobs[job_id]
                
                if _current_job_id == job_id:
                    _current_job_id = None
                
                return True
            return False
    
    @classmethod
    def cleanup_jobs(cls) -> int:
        """
        Remove completed jobs
        
        Returns:
            Number of jobs removed
        """
        with _job_lock:
            removed = 0
            job_ids = list(_jobs.keys())
            
            for job_id in job_ids:
                job = _jobs[job_id]
                if job.poll() is not None:
                    cls.remove_job(job_id)
                    removed += 1
            
            return removed


class JobUtilities:
    """Job control commands for KOS shell"""
    
    @staticmethod
    def do_jobs(fs, cwd, arg):
        """
        List all jobs
        
        Usage: jobs [options]
        
        Options:
          -l        Show process IDs
          -p        Show process IDs only
          -r        Show running jobs only
          -s        Show stopped jobs only
        """
        args = shlex.split(arg)
        
        # Parse options
        show_pid = False
        pid_only = False
        running_only = False
        stopped_only = False
        
        for arg in args:
            if arg == "-l":
                show_pid = True
            elif arg == "-p":
                pid_only = True
            elif arg == "-r":
                running_only = True
            elif arg == "-s":
                stopped_only = True
        
        # Get jobs
        jobs = JobManager.list_jobs()
        
        # Filter jobs
        if running_only:
            jobs = [j for j in jobs if j.status == "Running"]
        if stopped_only:
            jobs = [j for j in jobs if j.is_stopped]
        
        # Build output
        if pid_only:
            return "\n".join(str(j.pid) for j in jobs)
        
        current_job = JobManager.get_current_job()
        current_job_id = current_job.job_id if current_job else None
        
        output = []
        for job in jobs:
            job_marker = "+" if job.job_id == current_job_id else "-"
            status_str = job.status
            
            if pid_only:
                output.append(str(job.pid))
            elif show_pid:
                output.append(f"[{job.job_id}]{job_marker} {job.pid} {status_str} {job.command}")
            else:
                output.append(f"[{job.job_id}]{job_marker} {status_str} {job.command}")
        
        return "\n".join(output)
    
    @staticmethod
    def do_fg(fs, cwd, arg):
        """
        Bring job to foreground
        
        Usage: fg [job_id]
        """
        args = shlex.split(arg)
        
        # Get job ID
        job_id = None
        if args:
            try:
                # Handle %n syntax
                if args[0].startswith('%'):
                    job_id = int(args[0][1:])
                else:
                    job_id = int(args[0])
            except ValueError:
                return "fg: invalid job ID"
        else:
            # Get current job
            current_job = JobManager.get_current_job()
            if current_job:
                job_id = current_job.job_id
        
        if job_id is None:
            return "fg: no current job"
        
        # Get job
        job = JobManager.get_job(job_id)
        if not job:
            return f"fg: job {job_id} not found"
        
        # Continue job if stopped
        if job.is_stopped:
            job.continue_job()
        
        # Set as foreground job
        job.is_background = False
        JobManager.set_current_job(job_id)
        
        # Wait for job (this would be in a separate thread in a real shell)
        try:
            if job.poll() is None:
                # In a real implementation, this would handle keyboard input and signals
                # Here we just simulate waiting for the job
                job.wait(timeout=0.1)  # Small timeout to not block the shell
                
                # Check job status
                if job.poll() is None:
                    # Job still running, print info and return control
                    return f"{job.command} (still running)"
                else:
                    # Job completed
                    return f"{job.command} (completed with exit code {job.exit_code})"
            else:
                # Job already completed
                return f"{job.command} (already completed with exit code {job.exit_code})"
        except KeyboardInterrupt:
            # Handle Ctrl+C
            job.send_signal(signal.SIGINT)
            return f"Interrupted {job.command}"
    
    @staticmethod
    def do_bg(fs, cwd, arg):
        """
        Continue job in background
        
        Usage: bg [job_id]
        """
        args = shlex.split(arg)
        
        # Get job ID
        job_id = None
        if args:
            try:
                # Handle %n syntax
                if args[0].startswith('%'):
                    job_id = int(args[0][1:])
                else:
                    job_id = int(args[0])
            except ValueError:
                return "bg: invalid job ID"
        else:
            # Get current job
            current_job = JobManager.get_current_job()
            if current_job:
                job_id = current_job.job_id
        
        if job_id is None:
            return "bg: no current job"
        
        # Get job
        job = JobManager.get_job(job_id)
        if not job:
            return f"bg: job {job_id} not found"
        
        # Job must be stopped
        if not job.is_stopped:
            return f"bg: job {job_id} already in background"
        
        # Continue job
        job.continue_job()
        
        # Set as background job
        job.is_background = True
        
        return f"[{job_id}] {job.command} &"
    
    @staticmethod
    def do_kill(fs, cwd, arg):
        """
        Send signal to process
        
        Usage: kill [options] pid/job_id...
        
        Options:
          -l            List signal names
          -s signal     Specify signal (name or number)
          -n signal     Specify signal (number)
        """
        args = shlex.split(arg)
        
        if not args:
            return JobUtilities.do_kill.__doc__
        
        # List signals
        if args[0] == "-l":
            signal_list = []
            for sig_num, sig_name in SIGNAL_NAMES.items():
                signal_list.append(f"{sig_num}) {sig_name}")
            return "\n".join(signal_list)
        
        # Parse options
        signal_value = signal.SIGTERM  # Default signal
        targets = []
        
        i = 0
        while i < len(args):
            if args[i] in ["-s", "--signal"]:
                if i + 1 < len(args):
                    sig_arg = args[i+1]
                    try:
                        # Try as number
                        signal_value = int(sig_arg)
                    except ValueError:
                        # Try as name
                        sig_name = sig_arg.upper()
                        if sig_name.startswith("SIG"):
                            sig_name = sig_name[3:]  # Remove SIG prefix
                        
                        for sig_num, name in SIGNAL_NAMES.items():
                            if name == sig_name:
                                signal_value = sig_num
                                break
                        else:
                            return f"kill: unknown signal: {sig_arg}"
                    
                    i += 2
                else:
                    return "kill: option requires an argument -- '-s'"
            elif args[i] == "-n":
                if i + 1 < len(args):
                    try:
                        signal_value = int(args[i+1])
                    except ValueError:
                        return f"kill: invalid signal number: {args[i+1]}"
                    i += 2
                else:
                    return "kill: option requires an argument -- '-n'"
            else:
                # Job or process ID
                targets.append(args[i])
                i += 1
        
        if not targets:
            return "kill: no process or job specified"
        
        # Send signal to each target
        results = []
        for target in targets:
            try:
                # Check if job ID
                if target.startswith('%'):
                    job_id = int(target[1:])
                    job = JobManager.get_job(job_id)
                    
                    if job:
                        if job.send_signal(signal_value):
                            results.append(f"Sent signal {signal_value} to job {job_id}")
                        else:
                            results.append(f"Failed to send signal to job {job_id}")
                    else:
                        results.append(f"kill: job {job_id} not found")
                else:
                    # Process ID
                    pid = int(target)
                    
                    # Check if it's one of our jobs
                    job = JobManager.get_job_by_pid(pid)
                    if job:
                        if job.send_signal(signal_value):
                            results.append(f"Sent signal {signal_value} to process {pid}")
                        else:
                            results.append(f"Failed to send signal to process {pid}")
                    else:
                        # External process (would need more handling in a real shell)
                        try:
                            os.kill(pid, signal_value)
                            results.append(f"Sent signal {signal_value} to process {pid}")
                        except ProcessLookupError:
                            results.append(f"kill: process {pid} not found")
                        except PermissionError:
                            results.append(f"kill: permission denied for process {pid}")
            
            except ValueError:
                results.append(f"kill: invalid process/job ID: {target}")
        
        return "\n".join(results)
    
    @staticmethod
    def do_disown(fs, cwd, arg):
        """
        Remove jobs from shell job control
        
        Usage: disown [options] [job_id...]
        
        Options:
          -a        Remove all jobs
          -h        Do not send SIGHUP when shell exits
          -r        Remove only running jobs
        """
        args = shlex.split(arg)
        
        # Parse options
        remove_all = False
        no_sighup = False
        running_only = False
        job_ids = []
        
        for arg in args:
            if arg == "-a":
                remove_all = True
            elif arg == "-h":
                no_sighup = True
            elif arg == "-r":
                running_only = True
            elif arg.startswith('%'):
                try:
                    job_id = int(arg[1:])
                    job_ids.append(job_id)
                except ValueError:
                    return f"disown: invalid job ID: {arg}"
            else:
                try:
                    job_id = int(arg)
                    job_ids.append(job_id)
                except ValueError:
                    return f"disown: invalid job ID: {arg}"
        
        # Get jobs to disown
        if remove_all:
            jobs_to_disown = JobManager.list_jobs()
            if running_only:
                jobs_to_disown = [j for j in jobs_to_disown if j.status == "Running"]
        elif job_ids:
            jobs_to_disown = []
            for job_id in job_ids:
                job = JobManager.get_job(job_id)
                if job:
                    if not running_only or job.status == "Running":
                        jobs_to_disown.append(job)
                else:
                    return f"disown: job {job_id} not found"
        else:
            # Current job
            current_job = JobManager.get_current_job()
            if current_job:
                if not running_only or current_job.status == "Running":
                    jobs_to_disown = [current_job]
                else:
                    jobs_to_disown = []
            else:
                return "disown: no current job"
        
        if not jobs_to_disown:
            return "disown: no jobs to disown"
        
        # Disown jobs
        results = []
        for job in jobs_to_disown:
            # In a real implementation, this would set a flag to prevent SIGHUP
            # when the shell exits, and/or remove the job from job control
            if no_sighup:
                # Only mark to not send SIGHUP
                results.append(f"Job {job.job_id} marked to not receive SIGHUP")
            else:
                # Remove from job control
                JobManager.remove_job(job.job_id)
                results.append(f"Job {job.job_id} removed from job control")
        
        return "\n".join(results)
    
    @staticmethod
    def do_nohup(fs, cwd, arg):
        """
        Run command immune to hangups
        
        Usage: nohup command [arg...]
        """
        if not arg:
            return JobUtilities.do_nohup.__doc__
        
        # Create nohup.out file
        nohup_out = os.path.join(os.getcwd(), "nohup.out")
        
        try:
            # In a real implementation, this would set up proper redirection
            # to nohup.out and ignore SIGHUP
            
            # Create job
            success, message, job = JobManager.create_job(
                command=arg,
                is_background=True,
                shell=True,
                cwd=os.getcwd()
            )
            
            if not success:
                return f"nohup: {message}"
            
            return f"nohup: ignoring input and appending output to '{nohup_out}'"
        
        except Exception as e:
            return f"nohup: {str(e)}"


def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("jobs", JobUtilities.do_jobs)
    shell.register_command("fg", JobUtilities.do_fg)
    shell.register_command("bg", JobUtilities.do_bg)
    shell.register_command("kill", JobUtilities.do_kill)
    shell.register_command("disown", JobUtilities.do_disown)
    shell.register_command("nohup", JobUtilities.do_nohup)

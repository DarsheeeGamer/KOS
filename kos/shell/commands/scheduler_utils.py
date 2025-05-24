"""
Scheduler Utilities for KOS Shell

This module provides cron-like job scheduling commands for KOS.
"""

import os
import sys
import time
import logging
import json
import shlex
import datetime
from typing import Dict, List, Any, Optional, Union

# Import KOS components
from kos.scheduler import SchedulerManager, CronExpression, JobStatus, get_scheduler

# Set up logging
logger = logging.getLogger('KOS.shell.commands.scheduler_utils')

class SchedulerUtilities:
    """Job scheduling commands for KOS shell"""
    
    @staticmethod
    def do_crontab(fs, cwd, arg):
        """
        Maintain crontab files for individual users
        
        Usage: crontab [-l | -e | -r] [file]
        
        Options:
          -l         List crontab
          -e         Edit crontab
          -r         Remove crontab
          -u USER    Specify user
        """
        args = shlex.split(arg)
        
        # Default action is list
        action = "list"
        file_path = None
        user = None
        
        # Parse options
        i = 0
        while i < len(args):
            if args[i] == "-l":
                action = "list"
                i += 1
            elif args[i] == "-e":
                action = "edit"
                i += 1
            elif args[i] == "-r":
                action = "remove"
                i += 1
            elif args[i] == "-u":
                if i + 1 < len(args):
                    user = args[i+1]
                    i += 2
                else:
                    return "crontab: option requires an argument -- '-u'"
            else:
                file_path = args[i]
                i += 1
        
        # Process actions
        if action == "list":
            return SchedulerUtilities._crontab_list(user)
        elif action == "edit":
            return "crontab: editing not supported in this environment. Use crontab [file] to install a crontab."
        elif action == "remove":
            return SchedulerUtilities._crontab_remove(user)
        elif file_path:
            return SchedulerUtilities._crontab_install(file_path, user)
        else:
            return SchedulerUtilities.do_crontab.__doc__
    
    @staticmethod
    def do_cronjob(fs, cwd, arg):
        """
        Manage scheduled jobs
        
        Usage: cronjob COMMAND [options]
        
        Commands:
          list                List scheduled jobs
          add [options]       Add a new job
          remove JOB_ID       Remove a job
          enable JOB_ID       Enable a job
          disable JOB_ID      Disable a job
          show JOB_ID         Show job details
          run JOB_ID          Run job immediately
          status              Show scheduler status
        """
        args = shlex.split(arg)
        
        if not args:
            return SchedulerUtilities.do_cronjob.__doc__
        
        command = args[0]
        options = args[1:]
        
        # Process commands
        if command == "list":
            return SchedulerUtilities._cronjob_list()
        elif command == "add":
            return SchedulerUtilities._cronjob_add(options)
        elif command == "remove":
            return SchedulerUtilities._cronjob_remove(options)
        elif command == "enable":
            return SchedulerUtilities._cronjob_enable(options)
        elif command == "disable":
            return SchedulerUtilities._cronjob_disable(options)
        elif command == "show":
            return SchedulerUtilities._cronjob_show(options)
        elif command == "run":
            return SchedulerUtilities._cronjob_run(options)
        elif command == "status":
            return SchedulerUtilities._cronjob_status()
        else:
            return f"cronjob: unknown command '{command}'"
    
    @staticmethod
    def _crontab_list(user=None):
        """List crontab entries"""
        # In a full implementation, this would check for user-specific crontabs
        # For now, we just list all jobs
        jobs = SchedulerManager.list_jobs()
        
        if not jobs:
            return "No crontab entries found"
        
        result = ["# min hour dom month dow command"]
        
        for job in jobs:
            schedule = job.schedule_expression
            command = job.command
            
            if not job.enabled:
                result.append(f"#{schedule} {command}  # disabled")
            else:
                result.append(f"{schedule} {command}")
        
        return "\n".join(result)
    
    @staticmethod
    def _crontab_remove(user=None):
        """Remove all crontab entries"""
        # Remove all jobs
        jobs = SchedulerManager.list_jobs()
        
        if not jobs:
            return "No crontab for current user"
        
        removed_count = 0
        for job in jobs:
            success, _ = SchedulerManager.delete_job(job.id)
            if success:
                removed_count += 1
        
        # Save changes
        scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
        jobs_db = os.path.join(scheduler_dir, 'jobs.json')
        SchedulerManager.save_jobs(jobs_db)
        
        return f"Removed {removed_count} crontab entries"
    
    @staticmethod
    def _crontab_install(file_path, user=None):
        """Install crontab from file"""
        try:
            # Read crontab file
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Remove existing jobs
            SchedulerUtilities._crontab_remove(user)
            
            # Parse and add jobs
            added_count = 0
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse crontab entry
                parts = line.split(None, 5)  # Split into 6 parts max
                
                if len(parts) < 6:
                    return f"Error: Invalid crontab entry on line {line_num}: {line}"
                
                schedule = " ".join(parts[0:5])
                command = parts[5]
                
                # Validate cron expression
                cron = CronExpression(schedule)
                if not cron.is_valid:
                    return f"Error: Invalid cron expression on line {line_num}: {schedule} - {cron.error}"
                
                # Add job
                job_name = f"crontab-{line_num}"
                success, _, _ = SchedulerManager.create_job(
                    name=job_name,
                    command=command,
                    schedule=schedule
                )
                
                if success:
                    added_count += 1
            
            # Save changes
            scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
            jobs_db = os.path.join(scheduler_dir, 'jobs.json')
            SchedulerManager.save_jobs(jobs_db)
            
            return f"Installed {added_count} crontab entries"
        
        except Exception as e:
            return f"Error installing crontab: {str(e)}"
    
    @staticmethod
    def _cronjob_list():
        """List all scheduled jobs"""
        jobs = SchedulerManager.list_jobs()
        
        if not jobs:
            return "No scheduled jobs found"
        
        result = ["ID        NAME                  SCHEDULE         NEXT RUN             STATUS"]
        
        for job in jobs:
            # Format next run
            next_run = job.next_run.strftime("%Y-%m-%d %H:%M") if job.next_run else "N/A"
            
            # Format schedule (truncate if too long)
            schedule = job.schedule_expression
            if len(schedule) > 14:
                schedule = schedule[:11] + "..."
            
            status = job.status
            if not job.enabled:
                status = JobStatus.DISABLED
            
            result.append(f"{job.id:<10} {job.name[:20]:<20} {schedule:<15} {next_run:<20} {status}")
        
        return "\n".join(result)
    
    @staticmethod
    def _cronjob_add(options):
        """Add a new scheduled job"""
        # Parse options
        name = None
        command = None
        schedule = None
        working_dir = None
        
        i = 0
        while i < len(options):
            if options[i] == "--name":
                if i + 1 < len(options):
                    name = options[i+1]
                    i += 2
                else:
                    return "cronjob add: option requires an argument -- '--name'"
            elif options[i] == "--command":
                if i + 1 < len(options):
                    command = options[i+1]
                    i += 2
                else:
                    return "cronjob add: option requires an argument -- '--command'"
            elif options[i] == "--schedule":
                if i + 1 < len(options):
                    schedule = options[i+1]
                    i += 2
                else:
                    return "cronjob add: option requires an argument -- '--schedule'"
            elif options[i] == "--working-dir":
                if i + 1 < len(options):
                    working_dir = options[i+1]
                    i += 2
                else:
                    return "cronjob add: option requires an argument -- '--working-dir'"
            else:
                i += 1
        
        # Validate required options
        if not name:
            return "cronjob add: missing required option '--name'"
        
        if not command:
            return "cronjob add: missing required option '--command'"
        
        if not schedule:
            return "cronjob add: missing required option '--schedule'"
        
        # Create job
        success, message, job = SchedulerManager.create_job(
            name=name,
            command=command,
            schedule=schedule,
            working_dir=working_dir
        )
        
        if not success:
            return f"Failed to create job: {message}"
        
        # Save changes
        scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
        jobs_db = os.path.join(scheduler_dir, 'jobs.json')
        SchedulerManager.save_jobs(jobs_db)
        
        return f"Job created: {job.id} ({job.name})"
    
    @staticmethod
    def _cronjob_remove(options):
        """Remove a scheduled job"""
        if not options:
            return "cronjob remove: job ID is required"
        
        job_id = options[0]
        
        # Delete job
        success, message = SchedulerManager.delete_job(job_id)
        
        if not success:
            return f"Failed to remove job: {message}"
        
        # Save changes
        scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
        jobs_db = os.path.join(scheduler_dir, 'jobs.json')
        SchedulerManager.save_jobs(jobs_db)
        
        return message
    
    @staticmethod
    def _cronjob_enable(options):
        """Enable a scheduled job"""
        if not options:
            return "cronjob enable: job ID is required"
        
        job_id = options[0]
        
        # Enable job
        success, message = SchedulerManager.enable_job(job_id)
        
        if not success:
            return f"Failed to enable job: {message}"
        
        # Save changes
        scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
        jobs_db = os.path.join(scheduler_dir, 'jobs.json')
        SchedulerManager.save_jobs(jobs_db)
        
        return message
    
    @staticmethod
    def _cronjob_disable(options):
        """Disable a scheduled job"""
        if not options:
            return "cronjob disable: job ID is required"
        
        job_id = options[0]
        
        # Disable job
        success, message = SchedulerManager.disable_job(job_id)
        
        if not success:
            return f"Failed to disable job: {message}"
        
        # Save changes
        scheduler_dir = os.path.join(os.path.expanduser('~'), '.kos', 'scheduler')
        jobs_db = os.path.join(scheduler_dir, 'jobs.json')
        SchedulerManager.save_jobs(jobs_db)
        
        return message
    
    @staticmethod
    def _cronjob_show(options):
        """Show job details"""
        if not options:
            return "cronjob show: job ID is required"
        
        job_id = options[0]
        
        # Get job
        job = SchedulerManager.get_job(job_id)
        
        if not job:
            return f"Job not found: {job_id}"
        
        # Format job details
        result = [f"Job: {job.name} ({job.id})"]
        result.append(f"Command: {job.command}")
        result.append(f"Schedule: {job.schedule_expression}")
        result.append(f"Working directory: {job.working_dir}")
        result.append(f"Enabled: {job.enabled}")
        result.append(f"Status: {job.status}")
        
        if job.last_run:
            result.append(f"Last run: {job.last_run.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            result.append("Last run: Never")
        
        if job.next_run:
            result.append(f"Next run: {job.next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            result.append("Next run: N/A")
        
        result.append(f"Execution count: {job.execution_count}")
        
        # Show history
        if job.history:
            result.append("\nExecution history:")
            for record in reversed(job.history[-5:]):  # Last 5 executions
                start_time = datetime.datetime.fromtimestamp(record.start_time).strftime('%Y-%m-%d %H:%M:%S')
                exit_code = record.exit_code
                duration = f"{record.duration:.2f}s" if record.duration is not None else "N/A"
                
                result.append(f"  {start_time} - Exit code: {exit_code}, Duration: {duration}")
                
                # Show output and error if available
                if record.output:
                    output_lines = record.output.splitlines()
                    if len(output_lines) > 3:
                        output_preview = "\n    ".join(output_lines[:3]) + "\n    ..."
                    else:
                        output_preview = "\n    ".join(output_lines)
                    
                    result.append(f"    Output: {output_preview}")
                
                if record.error:
                    error_lines = record.error.splitlines()
                    if len(error_lines) > 3:
                        error_preview = "\n    ".join(error_lines[:3]) + "\n    ..."
                    else:
                        error_preview = "\n    ".join(error_lines)
                    
                    result.append(f"    Error: {error_preview}")
        
        return "\n".join(result)
    
    @staticmethod
    def _cronjob_run(options):
        """Run job immediately"""
        if not options:
            return "cronjob run: job ID is required"
        
        job_id = options[0]
        
        # Run job
        success, message = SchedulerManager.run_job_now(job_id)
        
        if not success:
            return f"Failed to run job: {message}"
        
        return message
    
    @staticmethod
    def _cronjob_status():
        """Show scheduler status"""
        scheduler = get_scheduler()
        
        is_running = scheduler.is_running()
        job_count = len(SchedulerManager.list_jobs())
        
        result = [f"Scheduler status: {'RUNNING' if is_running else 'STOPPED'}"]
        result.append(f"Jobs configured: {job_count}")
        
        # Count jobs by status
        status_counts = {}
        for job in SchedulerManager.list_jobs():
            status = job.status
            if not job.enabled:
                status = JobStatus.DISABLED
            
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Show status counts
        for status, count in status_counts.items():
            result.append(f"  {status}: {count}")
        
        return "\n".join(result)

def register_commands(shell):
    """Register commands with the shell"""
    shell.register_command("crontab", SchedulerUtilities.do_crontab)
    shell.register_command("cronjob", SchedulerUtilities.do_cronjob)

#!/usr/bin/env python3
"""
KOS crontab - Task Scheduling Command

This command provides cron-like task scheduling capabilities, including:
- Creating and managing scheduled jobs
- Linux-compatible crontab management (list, install, remove)
- Viewing job status and execution history
"""

import argparse
import os
import sys
import datetime
import tempfile
import subprocess
import textwrap
from typing import List, Dict, Any, Optional

from ...core import scheduler
from ...core.scheduler import JobStatus
from ...utils import formatting, logging

# Initialize the scheduler subsystem
scheduler.initialize()

def edit_crontab(username=None):
    """Edit crontab entries using an editor"""
    # Get current crontab entries
    jobs = scheduler.list_jobs()
    
    # Create a temporary file with current entries
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.crontab', delete=False) as f:
        temp_file = f.name
        
        # Write header
        f.write("# KOS Crontab - Edit job schedule\n")
        f.write("# Format: minute hour day month weekday command\n")
        f.write("# Example: 30 2 * * * /path/to/command arg1 arg2\n")
        f.write("# Special schedules: @yearly, @monthly, @weekly, @daily, @hourly\n")
        f.write("# Use # at the beginning of a line to comment it out\n\n")
        
        # Write current jobs
        for job in jobs:
            if job['schedule']:
                f.write(f"{job['schedule']} # {job['name']}: {job['description']}\n")
        
    # Launch editor
    editor = os.environ.get('EDITOR', 'notepad')
    try:
        result = subprocess.call([editor, temp_file])
        
        # Read the edited file
        if result == 0:
            with open(temp_file, 'r') as f:
                new_content = f.readlines()
            
            # Parse the edited content
            new_jobs = []
            line_num = 0
            
            for line in new_content:
                line_num += 1
                line = line.strip()
                
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse the line
                try:
                    # Find any comment on the line
                    if '#' in line:
                        job_line, comment = line.split('#', 1)
                        job_line = job_line.strip()
                    else:
                        job_line = line
                        comment = ""
                    
                    # Split into schedule and command
                    parts = job_line.split(None, 5)
                    
                    if parts[0].startswith('@'):
                        # Special schedule
                        schedule = parts[0]
                        command = ' '.join(parts[1:])
                    elif len(parts) >= 6:
                        # Standard schedule (min hour day month weekday command)
                        schedule = ' '.join(parts[:5])
                        command = parts[5]
                    else:
                        print(f"Error on line {line_num}: Invalid crontab entry format")
                        continue
                    
                    # Create a name from the command or comment
                    if comment:
                        name_match = re.match(r'^\s*([^:]+):', comment)
                        if name_match:
                            name = name_match.group(1).strip()
                        else:
                            name = f"job_{len(new_jobs) + 1}"
                    else:
                        name = f"job_{len(new_jobs) + 1}"
                    
                    # Create the job
                    new_jobs.append({
                        'name': name,
                        'command': command,
                        'schedule': schedule,
                        'description': comment.strip()
                    })
                
                except Exception as e:
                    print(f"Error on line {line_num}: {e}")
                    continue
            
            # First, disable all current jobs
            for job in jobs:
                scheduler.enable_job(job['name'], False)
            
            # Create or update new jobs
            for job_data in new_jobs:
                # Check if job already exists
                existing_job = None
                for job in jobs:
                    if job['name'] == job_data['name']:
                        existing_job = job
                        break
                
                if existing_job:
                    # Update existing job
                    scheduler.update_job(
                        name=job_data['name'],
                        command=job_data['command'],
                        schedule=job_data['schedule'],
                        enabled=True,
                        description=job_data['description'] or existing_job['description']
                    )
                else:
                    # Create new job
                    scheduler.create_job(
                        name=job_data['name'],
                        command=job_data['command'],
                        schedule=job_data['schedule'],
                        enabled=True,
                        description=job_data['description'] or f"Job: {job_data['name']}"
                    )
            
            print(f"Updated crontab with {len(new_jobs)} jobs")
    
    except Exception as e:
        print(f"Error editing crontab: {e}", file=sys.stderr)
        return 1
    
    finally:
        # Remove temporary file
        try:
            os.unlink(temp_file)
        except:
            pass
    
    return 0

def list_crontab(username=None):
    """List crontab entries"""
    jobs = scheduler.list_jobs()
    
    if not jobs:
        print("No crontab entries found")
        return 0
    
    # Print as crontab format
    print("# KOS Crontab")
    print("# min hour day month weekday command")
    print()
    
    for job in jobs:
        if job['schedule']:
            desc = f"# {job['name']}: {job['description']}" if job['description'] else f"# {job['name']}"
            print(f"{job['schedule']} {job['command']} {desc}")
    
    return 0

def format_job_status(status: Dict[str, Any]) -> str:
    """Format job status for display"""
    if not status:
        return "Job not found"
    
    # Format next/last run times
    next_run = "not scheduled"
    if status['next_run_time']:
        try:
            dt = datetime.datetime.fromisoformat(status['next_run_time'])
            next_run = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            next_run = status['next_run_time']
    
    last_run = "never"
    if status['last_run_time']:
        try:
            dt = datetime.datetime.fromisoformat(status['last_run_time'])
            last_run = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            last_run = status['last_run_time']
    
    # Format duration
    duration = "n/a"
    if status['last_run_duration'] is not None:
        secs = int(status['last_run_duration'])
        if secs < 60:
            duration = f"{secs}s"
        else:
            mins, secs = divmod(secs, 60)
            duration = f"{mins}m {secs}s"
    
    lines = [
        f"Job: {status['name']} - {status['description']}",
        f"Command: {status['command']}",
        f"Schedule: {status['schedule'] or 'manual execution only'}",
        f"Status: {status['status'].lower()}",
        f"Enabled: {'yes' if status['enabled'] else 'no'}",
        f"Next run: {next_run}",
        f"Last run: {last_run} (duration: {duration})",
        f"Exit code: {status['last_exit_code'] if status['last_exit_code'] is not None else 'n/a'}",
        f"Run count: {status['run_count']} (successes: {status['success_count']}, failures: {status['fail_count']})"
    ]
    
    if status['current_pid']:
        lines.append(f"Currently running with PID: {status['current_pid']}")
    
    if status['working_dir']:
        lines.append(f"Working directory: {status['working_dir']}")
    
    if status['user']:
        lines.append(f"User: {status['user']}")
    
    return "\n".join(lines)

def create_job(args):
    """Create a new scheduled job"""
    # Create the job
    job = scheduler.create_job(
        name=args.name,
        command=args.command,
        schedule=args.schedule,
        enabled=not args.disabled,
        working_dir=args.working_directory,
        environment=args.environment,
        user=args.user,
        description=args.description
    )
    
    if job:
        print(f"Created job: {args.name}")
        
        # Run immediately if requested
        if args.run_now:
            if scheduler.run_job_now(args.name):
                print(f"Scheduled job {args.name} for immediate execution")
            else:
                print(f"Failed to run job {args.name}", file=sys.stderr)
                return 1
        
        return 0
    else:
        print(f"Failed to create job: {args.name}", file=sys.stderr)
        return 1

def delete_job(args):
    """Delete a scheduled job"""
    if scheduler.delete_job(args.name):
        print(f"Deleted job: {args.name}")
        return 0
    else:
        print(f"Failed to delete job: {args.name}", file=sys.stderr)
        return 1

def run_job(args):
    """Run a job now"""
    if scheduler.run_job_now(args.name):
        print(f"Scheduled job {args.name} for immediate execution")
        return 0
    else:
        print(f"Failed to run job {args.name}", file=sys.stderr)
        return 1

def enable_job(args):
    """Enable or disable a job"""
    if scheduler.enable_job(args.name, not args.disable):
        action = "Disabled" if args.disable else "Enabled"
        print(f"{action} job: {args.name}")
        return 0
    else:
        action = "disable" if args.disable else "enable"
        print(f"Failed to {action} job: {args.name}", file=sys.stderr)
        return 1

def show_job_status(args):
    """Show job status"""
    if args.name:
        # Show status for a specific job
        status = scheduler.get_job_status(args.name)
        if status:
            print(format_job_status(status))
            
            # Show history if requested
            if args.history:
                print("\nExecution History:")
                history = scheduler.get_job_history(args.name, args.history)
                if history:
                    for i, entry in enumerate(history):
                        print(f"\nRun {i+1} - {entry['start_time']} (exit code: {entry['exit_code']}):")
                        if entry['stdout']:
                            print("\nStandard Output:")
                            print(textwrap.indent(entry['stdout'], '  '))
                        
                        if entry['stderr']:
                            print("\nStandard Error:")
                            print(textwrap.indent(entry['stderr'], '  '))
                else:
                    print("No execution history available")
            
            return 0
        else:
            print(f"Job not found: {args.name}", file=sys.stderr)
            return 1
    else:
        # Show status for all jobs
        jobs = scheduler.list_jobs()
        if not jobs:
            print("No jobs found")
            return 0
        
        # Format as a table
        headers = ["Name", "Schedule", "Status", "Next Run", "Last Run", "Success/Fail"]
        rows = []
        
        for job in jobs:
            next_run = "n/a"
            if job['next_run_time']:
                try:
                    dt = datetime.datetime.fromisoformat(job['next_run_time'])
                    next_run = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    next_run = job['next_run_time']
            
            last_run = "never"
            if job['last_run_time']:
                try:
                    dt = datetime.datetime.fromisoformat(job['last_run_time'])
                    last_run = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    last_run = job['last_run_time']
            
            schedule = job['schedule'] or "manual"
            if len(schedule) > 20:
                schedule = schedule[:17] + "..."
            
            rows.append([
                job['name'],
                schedule,
                job['status'].lower(),
                next_run,
                last_run,
                f"{job['success_count']}/{job['fail_count']}"
            ])
        
        print(formatting.format_table(headers, rows))
        return 0

def edit_job(args):
    """Edit a job"""
    # First, check if the job exists
    status = scheduler.get_job_status(args.name)
    if not status:
        print(f"Job not found: {args.name}", file=sys.stderr)
        return 1
    
    # Update the job
    job = scheduler.update_job(
        name=args.name,
        command=args.command,
        schedule=args.schedule,
        enabled=not args.disabled if args.disabled is not None else None,
        working_dir=args.working_directory,
        environment=args.environment,
        user=args.user,
        description=args.description
    )
    
    if job:
        print(f"Updated job: {args.name}")
        return 0
    else:
        print(f"Failed to update job: {args.name}", file=sys.stderr)
        return 1

def main(args=None):
    """Main entry point"""
    parser = argparse.ArgumentParser(description="KOS crontab - Task Scheduling Command")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # crontab command (linux-compatible)
    crontab_parser = subparsers.add_parser("crontab", help="Manage crontab entries")
    crontab_parser.add_argument("-l", "--list", action="store_true", help="List crontab entries")
    crontab_parser.add_argument("-e", "--edit", action="store_true", help="Edit crontab entries")
    crontab_parser.add_argument("-r", "--remove", action="store_true", help="Remove all crontab entries")
    crontab_parser.add_argument("-u", "--user", help="User whose crontab to modify")
    
    # Create job
    create_parser = subparsers.add_parser("create", help="Create a new scheduled job")
    create_parser.add_argument("name", help="Job name")
    create_parser.add_argument("--command", "-c", required=True, help="Command to execute")
    create_parser.add_argument("--schedule", "-s", help="Cron schedule expression")
    create_parser.add_argument("--description", "-d", help="Job description")
    create_parser.add_argument("--working-directory", "-w", help="Working directory")
    create_parser.add_argument("--user", help="User to run as")
    create_parser.add_argument("--environment", "-e", action="append", 
                             help="Environment variables (KEY=VALUE)")
    create_parser.add_argument("--disabled", action="store_true", help="Create job as disabled")
    create_parser.add_argument("--run-now", action="store_true", help="Run the job immediately")
    create_parser.set_defaults(func=create_job)
    
    # Delete job
    delete_parser = subparsers.add_parser("delete", help="Delete a scheduled job")
    delete_parser.add_argument("name", help="Job name")
    delete_parser.set_defaults(func=delete_job)
    
    # Run job
    run_parser = subparsers.add_parser("run", help="Run a job now")
    run_parser.add_argument("name", help="Job name")
    run_parser.set_defaults(func=run_job)
    
    # Enable/disable job
    enable_parser = subparsers.add_parser("enable", help="Enable or disable a job")
    enable_parser.add_argument("name", help="Job name")
    enable_parser.add_argument("--disable", action="store_true", help="Disable instead of enable")
    enable_parser.set_defaults(func=enable_job)
    
    # Status
    status_parser = subparsers.add_parser("status", help="Show job status")
    status_parser.add_argument("name", nargs="?", help="Job name (optional)")
    status_parser.add_argument("--history", "-n", type=int, default=3, 
                             help="Number of history entries to show")
    status_parser.set_defaults(func=show_job_status)
    
    # Edit job
    edit_parser = subparsers.add_parser("edit", help="Edit a job")
    edit_parser.add_argument("name", help="Job name")
    edit_parser.add_argument("--command", "-c", help="Command to execute")
    edit_parser.add_argument("--schedule", "-s", help="Cron schedule expression")
    edit_parser.add_argument("--description", "-d", help="Job description")
    edit_parser.add_argument("--working-directory", "-w", help="Working directory")
    edit_parser.add_argument("--user", help="User to run as")
    edit_parser.add_argument("--environment", "-e", action="append", 
                            help="Environment variables (KEY=VALUE)")
    edit_parser.add_argument("--disabled", action="store_true", help="Disable the job")
    edit_parser.set_defaults(func=edit_job)
    
    # Parse arguments
    args = parser.parse_args(args)
    
    # Handle crontab command specially
    if args.command == "crontab":
        if args.list:
            return list_crontab(args.user)
        elif args.edit:
            return edit_crontab(args.user)
        elif args.remove:
            # Remove all crontab entries
            jobs = scheduler.list_jobs()
            for job in jobs:
                scheduler.delete_job(job['name'])
            print("Removed all crontab entries")
            return 0
        else:
            # Default to listing
            return list_crontab(args.user)
    
    if not args.command:
        parser.print_help()
        return 1
    
    if not hasattr(args, 'func'):
        parser.print_help()
        return 1
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
